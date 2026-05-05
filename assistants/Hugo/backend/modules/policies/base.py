import re
from backend.components.display_frame import DisplayFrame

class BasePolicy:
    """Toolkit of reusable utility methods for per-flow policy methods. No lifecycle
    orchestration — each flow method decides what to call and when."""

    _STATUS_SUFFIXES = (' draft', ' post', ' note', ' published')

    def __init__(self, components):
        self.engineer = components['engineer']
        self.memory = components['memory']
        self.config = components['config']
        self.ambiguity = components['ambiguity']
        self._get_tools_fn = components['get_tools']

    def llm_execute(self, flow, state, context, tools, include_preview:bool=False,
                    extra_resolved:dict|None=None, exclude_tools:tuple=()):
        """Agentic tool-use loop for multi-tool flows. Returns (text, tool_log).

        Pass include_preview=True to preload per-section previews in the resolved-entities block,
        so the skill can plan without re-fetching. Pass extra_resolved to merge already-fetched
        data (e.g. the current outline) into the resolved-entities block so the skill skips a
        redundant tool call. Pass exclude_tools to hard-strip tool names from the skill's tool
        registry for this call (e.g. forbid `generate_outline` in propose mode). The tool call
        will error on the model side if it tries anyway."""
        resolved = self._build_resolved_context(flow, state, tools, include_preview=include_preview)
        if extra_resolved:
            resolved = {**(resolved or {}), **extra_resolved}
        convo_history = context.compile_history()
        tool_defs = self._get_tools_fn(flow)
        if exclude_tools:
            tool_defs = [td for td in tool_defs if td['name'] not in exclude_tools]
        return self.engineer.tool_call(
            flow, convo_history, self.memory.read_scratchpad(),
            tool_defs, tools, resolved=resolved,
            user_text=context.last_user_text,
        )

    # -- Content readback ---------------------------------------------------

    def _read_post_content(self, post_id, tools) -> dict:
        """Read back full post content from disk for frame display.

        Pulls the raw outline via `read_metadata(include_outline=True)` so markdown structure
        (newlines between bullets, blank lines between paragraphs) is preserved. Going through
        `read_section` here would flatten everything to a single space-joined sentence stream."""
        if not post_id:
            return {}
        meta = tools('read_metadata', {'post_id': post_id, 'include_outline': True})

        post = {}
        if meta['_success']:
            # Strip the hidden-section sentinel heading so prose-only posts display cleanly without the marker
            content = re.sub(r'^## _hidden_section_title\n', '', meta['outline'], flags=re.M)
            post = {'post_id': post_id, 'title': meta['title'], 'status': meta['status'], 'content': content}
        return post

    # -- Post helpers -------------------------------------------------------

    def resolve_post_id(self, identifier, tools):
        """Resolve a title or post_id string to an actual post_id."""
        if not identifier:
            return None
        # If it looks like a UUID, use it directly
        if len(identifier) == 8 or '-' in identifier:
            result = tools('read_metadata', {'post_id': identifier})
            if result['_success']:
                return identifier

        # Try with and without status suffixes
        candidates = [identifier]
        lower = identifier.lower()
        for suffix in self._STATUS_SUFFIXES:
            if lower.endswith(suffix):
                candidates.append(identifier[:len(identifier) - len(suffix)])

        for query in candidates:
            result = tools('find_posts', {'query': query})
            if not result['_success']:
                continue
            items = result['items']
            for item in items:
                if item['title'].lower() == query.lower():
                    return item['post_id']
            if items:
                return items[0]['post_id']
        return None

    # -- Persistence helpers ------------------------------------------------

    def _resolve_source_ids(self, flow, state, tools):
        """Extract (post_id, sec_id, error) from entity slot. Picks the first entity
        that satisfies the slot's entity_part criteria — skips Phase-2 placeholder
        entries that have post but no section/snippet yet. Syncs state.active_post.

        The third return is a missing-reference error frame when the slot was filled
        with a title/id that doesn't resolve to a real post; callers early-return via
        `post_id, _, error = self._resolve_source_ids(...); if error: return error`."""
        grounding = flow.slots[flow.entity_slot]
        if not grounding.values:
            return None, None, None
        part = grounding.entity_part
        vals = next((e for e in grounding.values if e['post'] and (not part or e[part])),
                    grounding.values[0])
        post_id = self.resolve_post_id(vals['post'], tools)
        sec_id = vals['sec'] or None
        if post_id:
            state.active_post = post_id
            return post_id, sec_id, None
        error = self.error_frame(flow, 'missing_reference',
            thoughts='Could not find the specified post.', missing_entity='post')
        return None, sec_id, error

    def _build_resolved_context(self, flow, state, tools, include_preview:bool=False) -> dict|None:
        """Pre-resolve post/section IDs so the LLM gets deterministic entities.

        When include_preview=True, also fetches a per-section preview (title +
        first 3 lines) so skills don't need a follow-up read_metadata call."""
        post_id, sec_id, _ = self._resolve_source_ids(flow, state, tools)
        if not post_id and state.active_post:
            post_id = state.active_post
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
        """Entity-missing guard. Declares `partial` and returns an empty frame with
        origin=flow.name() when the entity slot is unfilled. Callers early-return on a
        non-None result via `if frame := self._guard_entity(flow): return frame`."""
        grounding = flow.slots[flow.entity_slot]
        if not grounding.check_if_filled():
            self.ambiguity.declare('partial', metadata={'missing': 'source', 'entity': 'post'})
            return DisplayFrame(flow.name())
        return None

    # -- Error frame helper (Phase 3+) --------------------------------------

    def error_frame(self, flow, violation:str, thoughts:str='', code:str|None=None, **extra_metadata):
        """Construct an error frame with the standard violation classification. `violation` must
        be one of the 8-item vocabulary (failed_to_save, scope_mismatch, missing_reference,
        parse_failure, empty_output, invalid_input, conflict, tool_error). `thoughts` carries the
        human-readable description; `code` carries the raw payload (failing JSON, tool error
        string). `extra_metadata` merges into metadata alongside `violation`."""
        metadata = {'violation': violation, **extra_metadata}
        return DisplayFrame(
            origin=flow.name(),
            metadata=metadata,
            thoughts=thoughts,
            code=code,
        )

    # -- Retry helper (Phase 5) ---------------------------------------------

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
