import re
import difflib
import logging
from dataclasses import dataclass

from backend.components.task_artifact import TaskArtifact
from backend.utilities.services import ToolService

log = logging.getLogger(__name__)

# The six sub-agent hook points (pex.md). A policy runs a sub-agent that can take destructive
# action, so each point is an interception seam for an NLU signal (read from belief) or a user
# interrupt. Three already have bodies elsewhere: pre_tool ← PEX._security_check,
# verification ← PEX._validate_artifact, tool_retry ← retry_tool. pre_llm/post_llm are wired
# live in llm_execute; post_tool's body lives in the engineer.tool_call loop (integration seam).
HOOK_POINTS = ('pre_llm', 'pre_tool', 'post_tool', 'tool_retry', 'post_llm', 'verification')


@dataclass
class HookDecision:
    """A hook's verdict: severity of any pending signal + whether to keep going."""
    point: str
    severity: str = 'low'   # 'high' (user interrupt — TODO) | 'medium' (signal diverges) | 'low'
    proceed: bool = True
    reason: str = ''


class BasePolicy:
    """Toolkit of reusable utility methods for per-flow policy methods. No lifecycle
    orchestration — each flow method decides what to call and when."""

    _STATUS_SUFFIXES = (' draft', ' post', ' note', ' published')

    def __init__(self, components):
        self.engineer = components['engineer']
        self.memory = components['memory']
        self.scratchpad = components['scratchpad']
        self.config = components['config']
        self.ambiguity = components['ambiguity']
        self._get_tools_fn = components['get_tools']
        self.flow_stack = components['flow_stack']
        self._state_file = components['state_file']  # callable → path of the session state.json
        self._completion = None  # record written by complete_flow, handed off via pop_completion

    # -- Sub-agent hook framework ------------------------------------------

    def run_hook(self, point:str, flow, state) -> HookDecision:
        """Evaluate one of the six hook points (HOOK_POINTS) against the live belief signal.

        Signal channel = the belief itself (no side channel): NLU writes `pred_intent`, and a
        hook compares it to the active flow's intent — they DIVERGE (medium) or ALIGN (low). A
        user interrupt would be high, but its channel is a TODO, so high never fires in 2a.
        Bespoke stop/go-on: high → stop (mid-task); low/medium → go on (medium also logs so a
        diverging signal is visible for the Batch 2b reconsider rule)."""
        severity = 'low' if state.pred_intent == flow.intent else 'medium'
        decision = HookDecision(point=point, severity=severity, proceed=severity != 'high')
        if severity != 'low':
            decision.reason = f'belief intent {state.pred_intent!r} diverges from {flow.intent!r}'
            log.info('[hook] %s severity=%s flow=%s %s', point, severity, flow.name(), decision.reason)
        return decision

    def llm_execute(self, flow, state, context, tools, include_preview:bool=False,
                    extra_resolved:dict|None=None, exclude_tools:tuple=(),
                    model:str='med', schema:dict|None=None):
        """Agentic tool-use loop for multi-tool flows. Returns (text, tool_log).

        Pass include_preview=True to preload per-section previews in the resolved-entities block,
        so the skill can plan without re-fetching. Pass extra_resolved to merge already-fetched
        data (e.g. the current outline) into the resolved-entities block so the skill skips a
        redundant tool call. Pass exclude_tools to hard-strip tool names from the skill's tool
        registry for this call (e.g. forbid `generate_outline` in propose mode). The tool call
        will error on the model side if it tries anyway. Pass `model='high'` to swap the skill
        onto a stronger tier; pass `schema=<json-schema dict>` to force a schema-constrained
        terminal emit when the tool loop would otherwise return empty text."""
        self.run_hook('pre_llm', flow, state)  # ① intercept any pending signal before the loop
        resolved = self._build_resolved_context(flow, state, tools, include_preview=include_preview)
        if extra_resolved:
            resolved = {**(resolved or {}), **extra_resolved}
        convo_history = context.compile_history()
        tool_defs = self._get_tools_fn(flow)
        if exclude_tools:
            tool_defs = [td for td in tool_defs if td['name'] not in exclude_tools]
        result = self.engineer.tool_call(
            flow, convo_history, self.scratchpad.read(),
            tool_defs, tools, resolved=resolved,
            user_text=context.last_user_text,
            model=model, schema=schema,
        )
        self.run_hook('post_llm', flow, state)  # ⑤ intercept after the sub-agent completes
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
            # Strip the hidden-section sentinel heading so prose-only posts display cleanly without the marker
            content = re.sub(r'^## _hidden_section_title\n', '', meta['outline'], flags=re.M)
            post = {'post_id': post_id, 'title': meta['title'], 'status': meta['status'], 'content': content}
        return post

    # -- Post helpers -------------------------------------------------------

    def _resolve_post_id(self, identifier, tools):
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

    def resolve_source_ids(self, flow, state, tools):
        """Extract (post_id, sec_id, error) from the state file's grounding block — the single source
        of truth for the active entity. A user-typed reference in the entity slot (this turn's
        utterance) still resolves through the fuzzy _resolve_post_id; resolved ids are written back to
        the grounding block (state.active_post mirrors it). The third return is a missing-reference
        error artifact when the slot was filled with a title/id that doesn't resolve to a real post;
        callers early-return via `post_id, _, error = self.resolve_source_ids(...); if error: return error`."""
        slot = flow.slots[flow.entity_slot]
        part = slot.entity_part
        vals = None
        if slot.values:
            vals = next((ent for ent in slot.values if ent['post'] and (not part or ent[part])),
                        slot.values[0])
        reference = vals['post'] if vals and vals['post'] else state.grounding['post']
        if not reference:
            return None, None, None
        post_id = self._resolve_post_id(reference, tools)
        if not post_id:
            error = self.error_artifact(flow, 'missing_reference',
                thoughts='Could not find the specified post.', missing_entity='post')
            return None, None, error
        sec_ref = vals['sec'] if vals else state.grounding['sec']
        sec_id = self._resolve_sec_id(sec_ref, tools, post_id)
        state.grounding['post'] = post_id
        state.grounding['sec'] = sec_id or ''
        state.active_post = post_id
        return post_id, sec_id, None

    def _build_resolved_context(self, flow, state, tools, include_preview:bool=False) -> dict|None:
        """Pre-resolve post/section IDs so the LLM gets deterministic entities.

        When include_preview=True, also fetches a per-section preview (title +
        first 3 lines) so skills don't need a follow-up read_metadata call.
        Substrate-aware through resolve_source_ids: under the orchestrator the ids come
        from the grounding block (state.active_post mirrors it, so the fallback below
        serves both substrates)."""
        post_id, sec_id, _ = self.resolve_source_ids(flow, state, tools)
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
        """Entity-missing guard. Declares `partial` and returns an empty artifact with
        origin=flow.name() when the entity slot is unfilled. Callers early-return on a
        non-None result via `if artifact := self._guard_entity(flow): return artifact`."""
        ent_slot = flow.entity_slot
        if not flow.slots[ent_slot].check_if_filled():
            self.ambiguity.declare('partial', metadata={'missing': ent_slot, 'entity': 'post'})
            return TaskArtifact(flow.name())
        return None

    # -- Flow completion ------------------------------------------------------

    def complete_flow(self, flow, state, summary:str, metadata:dict|None=None) -> dict|None:
        """The single call a policy makes at the moment its flow finishes. The status change goes
        through write_state op='update_flow' (so the grounding validation fires and state.json is
        rewritten) and the completion record {flow, summary, metadata} is appended to the session
        scratchpad; activate_flow collects it via pop_completion and returns it as the tool result.
        Call it before stacking any follow-up flow — the completing flow must be top of stack."""
        state.flow_stack = self.flow_stack.to_list()  # live stack → block so write_state sees it
        if state.flow_stack[-1]['flow_id'] != flow.flow_id:
            raise ValueError(f'complete_flow: {flow.name()!r} is not top of stack — finish or '
                             f'pop the flows above it first')
        state.write_state(self._state_file(), 'update_flow', status='Completed')
        flow.status = 'Completed'  # mirror onto the live flow object
        self._completion = self.scratchpad.write_completion(flow.name(), summary, metadata=metadata)
        return self._completion

    def pop_completion(self) -> dict|None:
        """Hand the record written by complete_flow to activate_flow exactly once."""
        record, self._completion = self._completion, None
        return record

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

        return content.take_snapshot(post_id=post_id, turn_id=context.turn_id,
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
