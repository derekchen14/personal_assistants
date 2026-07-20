import re
import difflib

from backend.components.task_artifact import TaskArtifact
from backend.utilities.services import ToolService


class BasePolicy:
    """Toolkit of reusable utility methods for per-flow policy methods. No lifecycle
    orchestration — each flow method decides what to call and when."""

    _STATUS_SUFFIXES = (' draft', ' post', ' note', ' published')

    def __init__(self, components):
        self.engineer = components['engineer']
        self.scratchpad = components['scratchpad']
        self.config = components['config']
        self.ambiguity = components['ambiguity']
        self._get_tools_fn = components['get_tools']
        self.flow_stack = components['flow_stack']
        self._completion = None  # entry written by complete_flow, handed off via pop_completion

    def llm_execute(self, flow, state, context, tools, include_preview:bool=False,
                    extra_resolved:dict|None=None, exclude_tools:tuple=(),
                    tier:str='med', schema:dict|None=None):
        """Agentic tool-use loop for multi-tool flows. Returns (text, tool_log).

        Pass include_preview=True to preload per-section previews in the resolved-entities block,
        so the skill can plan without re-fetching. Pass extra_resolved to merge already-fetched
        data (e.g. the current outline) into the resolved-entities block so the skill skips a
        redundant tool call. Pass exclude_tools to hard-strip tool names from the skill's tool
        inventory for this call (e.g. forbid `generate_outline` in propose mode). The tool call
        will error on the model side if it tries anyway. Pass `tier='high'` to swap the skill
        onto a stronger tier; pass `schema=<json-schema dict>` to force a schema-constrained
        terminal emit when the tool loop would otherwise return empty text."""
        resolved = self._build_resolved_context(flow, state, tools, include_preview=include_preview)
        if extra_resolved:
            resolved = {**(resolved or {}), **extra_resolved}
        convo_history = context.compile_history()
        tool_defs = self._get_tools_fn(flow)
        if exclude_tools:
            tool_defs = [td for td in tool_defs if td['name'] not in exclude_tools]
        result = self.engineer.flow_execute(
            flow, convo_history, self.scratchpad.read(),
            tool_defs, tools, resolved=resolved,
            user_text=context.last_user_utt,
            tier=tier, schema=schema,
        )
        return result

    # -- Content readback ---------------------------------------------------

    def _read_post_content(self, post_id, tools) -> dict:
        """Read back full post content from disk for artifact display.

        Pulls the raw outline via `read_metadata(include_outline=True)` so markdown structure
        (newlines between bullets, blank lines between paragraphs) is preserved. Going through
        `read_section` here would flatten everything to a single space-joined sentence stream."""
        if not post_id:
            return {}
        meta = tools('read_metadata', {'post_id': post_id, 'include_outline': True})

        post = {}
        if meta['_success']:
            # Strip the hidden-section marker heading so prose-only posts display cleanly without the marker
            content = re.sub(r'^## _hidden_section_title\n', '', meta['outline'], flags=re.M)
            post = {'post_id': post_id, 'title': meta['title'], 'status': meta['status'], 'content': content}
        return post

    # -- Post helpers -------------------------------------------------------

    def _resolve_post_id(self, identifier, tools):
        """Resolve a title or post_id without guessing among several candidates.

        Verification is owned by ``resolve_source_ids`` because the string return value cannot
        carry it. This helper may return one unique fuzzy result, but callers must keep that
        prediction ``ver=False`` unless the id/title was exact or the user selected it.
        """
        if not identifier:
            return None
        # A raw post id resolves directly, whatever its shape (eval-seeded ids like
        # 'SeedBulb04' are valid too); a title/nickname errors clean and falls through
        result = tools('read_metadata', {'post_id': identifier})
        if result['_success']:
            return identifier

        # Try with and without status suffixes; a hyphenated form also tries its spaced form
        candidates = [identifier]
        lower = identifier.lower()
        for suffix in self._STATUS_SUFFIXES:
            if lower.endswith(suffix):
                candidates.append(identifier[:len(identifier) - len(suffix)])
        candidates += [cand.replace('-', ' ') for cand in list(candidates) if '-' in cand]

        for query in candidates:
            result = tools('find_posts', {'query': query})
            if not result['_success']:
                continue
            items = result['items']
            for item in items:
                if item['title'].lower() == query.lower():
                    return item['post_id']
            if len(items) == 1:
                return items[0]['post_id']

        # Fuzzy title pass (2.15.2) — mirror _resolve_sec_id's difflib matching over the library
        result = tools('find_posts', {'limit': 50})
        listing = {'items': [item for item in result['items'] if item['title']]} \
            if result['_success'] else {'items': []}
        titles = [item['title'].lower() for item in listing['items']]
        for query in candidates:
            matches = difflib.get_close_matches(query.lower(), titles, n=2, cutoff=0.6)
            if len(matches) == 1:
                return listing['items'][titles.index(matches[0])]['post_id']
        return None

    def _resolve_sec_id(self, identifier, tools, post_id):
        sec_id = None
        if identifier:
            section_ids = tools('read_metadata', {'post_id': post_id})['section_ids']
            slug = ToolService._slugify(identifier)
            if slug in section_ids:
                sec_id = slug
            else:
                matches = difflib.get_close_matches(slug, section_ids, n=1, cutoff=0.6)
                sec_id = matches[0] if matches else None
        return sec_id


    # -- Persistence helpers ------------------------------------------------

    def verify_grounding(self, post_id, reference, state, tools, verified=False):
        """Upgrade a fuzzy post_id to verified. True when `reference` is an exact id/title match,
        or when an already-verified active post is anaphoric to / overlaps `reference` — in which
        case post_id switches to that active post. Returns (post_id, verified)."""
        if post_id:
            meta = tools('read_metadata', {'post_id': post_id})
            exact = reference == post_id or (
                meta['_success'] and meta['title'].strip().lower() == reference.strip().lower())
            verified = verified or exact
        active = state.get_active_entity()
        if post_id and not verified and active.get('post') and active.get('ver'):
            active_meta = tools('read_metadata', {'post_id': active['post']})
            tokens = lambda text: {t for t in re.findall(r'[a-z0-9]+', text.lower())
                                   if len(t) > 3 and t not in {'this', 'that', 'post', 'draft', 'note'}}
            overlap = (not reference or reference == active['post'] or
                       bool(tokens(reference) & tokens(active_meta.get('title', ''))))
            if active_meta['_success'] and overlap:
                post_id, verified = active['post'], True
        return post_id, verified

    def resolve_source_ids(self, flow, state, tools):
        """Extract (post_id, sec_id, error) from the state file's grounding block — the single source
        of truth for the active entity. A user-typed reference in the entity slot (this turn's
        utterance) still resolves through the fuzzy _resolve_post_id; resolved ids are written back to
        the grounding block. When the reference doesn't resolve to a real post, the third return is
        an empty artifact with a `partial` ambiguity open and near-miss titles written as grounding
        choices (2.15.3); callers early-return via
        `post_id, _, error = self.resolve_source_ids(...); if error: return error`."""
        slot = flow.slots[flow.entity_slot]
        part = slot.entity_part
        vals = None
        if slot.values:
            vals = next((ent for ent in slot.values if ent['post'] and (not part or ent[part])),
                        slot.values[0])
        active_entity = state.get_active_entity()
        reference = vals['post'] if vals and vals['post'] else active_entity.get('post', '')
        if not reference:
            return None, None, None
        post_id = self._resolve_post_id(reference, tools)
        post_id, verified = self.verify_grounding(post_id, reference, state, tools,
                                                  bool(vals and vals.get('ver')))
        if not post_id:
            if slot.priority != 'required':
                # An elective entity slot means the flow proceeds without it (cite's url-only
                # path) — keep the plain error the caller may ignore, no ambiguity side effect.
                error = self.error_artifact(flow, 'missing_reference',
                    thoughts='Could not find the specified post.', missing_entity='post')
                return None, None, error
            # Near-miss choices instead of a dead end (2.15.3): one best-token query (else the
            # latest posts) becomes grounding choices, so the next turn's fill resolves a pick
            # through the standing shown-candidates path.
            token = max(reference.replace('-', ' ').split(), key=len)
            result = tools('find_posts', {'query': token})
            hits = result['items'] if result['_success'] else []
            items = [item for item in hits if item['title']]  # untitled entries aren't options
            if not items:
                items = [item for item in tools('find_posts', {})['items'] if item['title']]
            state.grounding['choices'] = [
                {'kind': 'post', 'label': item['title'], 'status': item['status'],
                 'entity': {'post': item['post_id'], 'sec': '', 'snip': '', 'chl': '', 'ver': True},
                 'source': flow.name()}
                for item in items]
            titles = ', '.join(f"'{item['title']}'" for item in items)
            self.ambiguity.recognize('partial',
                metadata={'missing': flow.entity_slot, 'entity': 'post'},
                observation=f"I couldn't find '{reference}'. Did you mean one of these: {titles}?")
            return None, None, TaskArtifact(flow.name())
        sec_ref = vals['sec'] if vals else active_entity.get('sec', '')
        sec_id = self._resolve_sec_id(sec_ref, tools, post_id)
        state.set_active_entity(post=post_id, sec=sec_id or '', ver=verified)
        if vals:
            vals['post'] = post_id
            vals['sec'] = sec_id or ''
            vals['ver'] = verified
            slot._rebuild_keys()
            slot.check_if_filled()
        return post_id, sec_id, None

    def _build_resolved_context(self, flow, state, tools, include_preview:bool=False) -> dict|None:
        """Pre-resolve post/section IDs so the LLM gets deterministic entities.

        When include_preview=True, also fetches a per-section preview (title +
        first 3 lines) so skills don't need a follow-up read_metadata call.
        Substrate-aware through resolve_source_ids: under the orchestrator the ids come
        from the grounding block."""
        post_id, sec_id, _ = self.resolve_source_ids(flow, state, tools)
        if not post_id:
            post_id = state.get_active_post()
        if not post_id:
            return None
        meta = tools('read_metadata', {'post_id': post_id, 'include_preview': include_preview})
        if not meta['_success']:
            return {'post_id': post_id}
        resolved = {
            'post_id': post_id,
            'post_title': meta['title'],
            'section_ids': meta['section_ids'],
        }
        if include_preview and meta['preview']:
            resolved['section_preview'] = meta['preview']
        if sec_id:
            resolved['target_section'] = sec_id
        return resolved

    def _guard_entity(self, flow):
        """Entity-missing guard. Declares `partial` and returns an empty artifact with
        origin=flow.name() when the entity slot is unfilled. Callers early-return on a
        non-None result via `if artifact := self._guard_entity(flow): return artifact`."""
        ent_slot = flow.entity_slot
        if not flow.slots[ent_slot].check_if_filled():
            self.ambiguity.recognize('partial', metadata={'missing': ent_slot, 'entity': 'post'})
            return TaskArtifact(flow.name())
        return None

    # -- Flow completion ------------------------------------------------------

    def complete_flow(self, flow, state, context, summary:str, metadata:dict|None=None) -> dict|None:
        """The single call a policy makes at the moment its flow finishes. The status flips to
        Completed on the live flow (MEM saves state.json at turn end) and the completion entry
        {summary, metadata} is appended to the session scratchpad under the flow's origin;
        pex.call_policy collects it via pop_completion and execute() returns it as the tool
        result. NLU may
        stack a divergent flow above mid-run (round 3.4), so completion never requires being
        top of stack — a Completed flow buried under live work waits there, and pop's top-down
        loop clears it once the flows above it resolve."""
        flow.status = 'Completed'
        entry = {'turn_number': context.num_utterances,
                 'summary': summary, 'metadata': metadata or {}}
        self.scratchpad.append_entry(flow.name(), entry)   # stamps version / used_count
        self._completion = {**entry, 'origin': flow.name()}
        return self._completion

    def pop_completion(self) -> dict|None:
        """Hand the entry written by complete_flow to pex.call_policy exactly once."""
        entry, self._completion = self._completion, None
        return entry

    # -- Helper Functions --------------------------------------

    def error_artifact(self, flow, violation:str, thoughts:str='', code:str|None=None, **extra_parts):
        """Construct an error artifact with the standard violation classification. `violation` must
        be one of the 8-item vocabulary (failed_to_save, scope_mismatch, missing_reference,
        parse_failure, empty_output, invalid_input, conflict, tool_error). `thoughts` carries the
        human-readable description; `code` carries the raw payload (failing JSON, tool error
        string). `extra_parts` merges into the artifact's `parts` alongside `violation`."""
        parts = {'violation': violation, **extra_parts}
        return TaskArtifact(origin=flow.name(), parts=parts, thoughts=thoughts, code=code)

    def toast_error(self, flow, violation, message):
        """Render errors as toast blocks to surface failures visually to the user."""
        artifact = self.error_artifact(flow, violation, thoughts=message)
        artifact.add_block({'type': 'toast', 'data': {'message': message, 'level': 'warning'}})
        return artifact

    def record_snapshot(self, content, flow, context, post_id,
                        sec_ids:list|None=None, summary:str|None=None) -> str:
        """Capture pre-state and write a JSON snapshot bundle. Returns snapshot_id.

        `content` is the ContentService — passed in by the caller (Draft/Revise/Converse
        each set `self.content`); BasePolicy stays free of that dependency. Pass
        `sec_ids=[<sec>]` for section-scoped snapshots, leave None for whole-post.
        Section ids are expected to be canonical slugs — `resolve_source_ids` already
        normalizes them via `resolve_sec_id`."""
        ent = content._require_entry(post_id)[0]
        all_sections = content._extract_sections(content._read_content(ent['filename']))

        if sec_ids is None:
            sections = [{'sec_id': sec['sec_id'], 'lines': sec['lines']}
                        for sec in all_sections]
        else:
            sections = [{'sec_id': sec['sec_id'], 'lines': sec['lines']}
                        for sec in all_sections if sec['sec_id'] in sec_ids]

        if summary is None:
            scope = ', '.join(sec_ids) if sec_ids else 'whole post'
            summary = f'{flow.name()} on {scope}'

        return content.take_snapshot(post_id=post_id, turn_id=context.num_utterances,
            flow_name=flow.name(), summary=summary, sections=sections)

    def retry_tool(self, tools, tool_name:str, params:dict, max_attempts:int=2) -> dict:
        """Call a tool with transient-failure retries. Returns the final result.

        Retries on `_success=False` up to `max_attempts` total calls. The last result (success or
        final failure) is returned verbatim; callers inspect `_success` / `_error` as usual. Keep
        `max_attempts` small — retry is for transient network/lock errors, not validation
        failures."""
        result = tools(tool_name, params)
        attempts = 1
        while not result['_success'] and attempts < max_attempts:
            result = tools(tool_name, params)
            attempts += 1
        return result
