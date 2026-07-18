import re

from backend.modules.policies.base import BasePolicy
from backend.components.task_artifact import TaskArtifact

# Placeholder markers the propose flow fills (<fill in here>, [TODO], a bare TODO). Matched
# conservatively — the bracketed forms must carry a fill/here/todo/placeholder/ellipsis token, so
# real prose and markdown links pass through untouched.
_PLACEHOLDER_RE = re.compile(
    r'<[^>\n]*?(?:fill|\.\.\.|here|todo|placeholder)[^>\n]*?>'
    r'|\[[^\]\n]*?(?:fill|todo|placeholder)[^\]\n]*?\]'
    r'|\bTODO\b', re.I)

class RevisePolicy(BasePolicy):

    def __init__(self, components):
        super().__init__(components)
        self.flow_stack = components['flow_stack']
        self.content = components['content_service']

    def execute(self, state, context, tools):
        flow = self.flow_stack.get_flow()

        match flow.name():
            case 'rework': return self.rework_policy(flow, state, context, tools)
            case 'write': return self.write_policy(flow, state, context, tools)
            case 'audit': return self.audit_policy(flow, state, context, tools)
            case 'propose': return self.propose_policy(flow, state, context, tools)
            case _:
                return TaskArtifact()

    def _read_scratch_value(self, origin):
        """Newest scratchpad entry stored under `origin` (flat single-dict shape)."""
        entries = self.scratchpad.read(origin=origin)
        return entries[-1] if entries else ''

    def rework_policy(self, flow, state, context, tools):
        if artifact := self._guard_entity(flow): return artifact
        post_id, _, error = self.resolve_source_ids(flow, state, tools)
        if error: return error

        # Whole-entity deletion: type in {post, draft, note} deletes the post
        # outright. Section / paragraph / image removals fall through to the agentic path below.
        type_slot = flow.slots['type']
        if type_slot.check_if_filled() and type_slot.value in ('post', 'draft', 'note'):
            return self._rework_delete(flow, state, context, post_id, tools)

        # Category routing: each option resolves deterministically (move, fallback, or ambiguity).
        if flow.slots['category'].check_if_filled():
            return self._rework_category(flow, state, post_id, context, tools)

        # Null-category agentic path: skill handles itemized changes via `suggestions` / `remove`.
        if not flow.slots['suggestions'].check_if_filled() and not flow.slots['remove'].check_if_filled():
            self.ambiguity.recognize('specific', metadata={'missing': 'category_or_suggestions'})
            return TaskArtifact(origin=flow.name())

        self.record_snapshot(self.content, flow, context, post_id)
        text, tool_log = self.llm_execute(flow, state, context, tools, include_preview=True)
        parsed = self.engineer.parse(text)
        saved, _ = self.engineer.tool_succeeded(tool_log, 'revise_content')

        artifact = TaskArtifact(flow.name(), thoughts=text)
        if saved:
            for step_name in parsed['done']:
                flow.slots['suggestions'].mark_as_complete(step_name)

            # The skill's own summary line, never the raw JSON blob (2.14.4)
            summary = parsed.get('summary') or text[:200]
            self.complete_flow(flow, state, context, summary, metadata={'post_id': post_id})
            artifact.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        else:
            artifact.set_artifact(new_data={'violation': 'failed_to_save'})

        return artifact

    def _rework_delete(self, flow, state, context, post_id, tools):
        """Whole-entity deletion. Published posts aren't deletable —
        confirm an unpublish intent first. delete_post runs through the `tools` callable (not the skill's
        tool registry); the post is gone afterward, so emit a toast and skip any content readback.
        Grounding is left on the now-deleted id because _check_grounding only forbids an EMPTY
        grounding.post at completion — it does no existence check."""
        meta = tools('read_metadata', {'post_id': post_id})
        if meta['_success'] and meta['status'] == 'published':
            self.ambiguity.recognize('confirmation', metadata={
                'missing': 'unpublish_intent',
                'question': 'That post is already published — unpublish it first, or cancel?'})
            return TaskArtifact(flow.name())
        kind = flow.slots['type'].value
        result = tools('delete_post', {'post_id': post_id})
        if not result['_success']:
            return self.toast_error(flow, 'tool_error',
                f"Couldn't delete the {kind}: {result.get('_error', 'delete_post failed')}")
        self.complete_flow(flow, state, context, f'Deleted the {kind}.', metadata={'post_id': post_id})
        artifact = TaskArtifact(flow.name(), thoughts=f'Deleted the {kind}.')
        artifact.add_block({'type': 'toast', 'data': {'message': f'Deleted the {kind}.', 'level': 'success'}})
        return artifact

    def _rework_category(self, flow, state, post_id, context, tools):
        cat = flow.slots['category'].value
        if cat == 'swap':
            return self._rework_swap(flow, state, context, post_id, tools)
        if cat in ('to_top', 'to_end'):
            return self._rework_move(flow, state, context, post_id, tools)
        if cat == 'trim':
            self.flow_stack.fallback('write')
            return TaskArtifact(flow.name(), thoughts='Trimming reads as a write edit, rerouting.')
        if cat == 'sharpen':
            self.flow_stack.fallback('refine')
            return TaskArtifact(flow.name(), thoughts='Sharpening reads as Refine, rerouting.')
        # cat == 'reframe'
        self.ambiguity.recognize(
            'confirmation',
            metadata={
                'missing': 'rework_changes',
                'question': 'Reframing the post is broad. List the concrete changes you want as bullets.',
                'naturalize': True, 'category': 'reframe',
            },
        )
        flow.slots['category'].reset()
        return TaskArtifact(origin=flow.name())

    def _rework_swap(self, flow, state, context, post_id, tools):
        raw_secs = [e['sec'] for e in flow.slots['source'].values if e['sec']]
        if len(raw_secs) < 2:
            self.ambiguity.recognize('specific', metadata={'missing': 'second_section'})
            return TaskArtifact(origin=flow.name())
        section_ids = list(tools('read_metadata', {'post_id': post_id})['section_ids'])
        # LLM fills source.sec with raw text ("Process"); canonicalize to slug ("process").
        resolved = [r for r in (self._resolve_sec_id(raw, tools, post_id) for raw in raw_secs[:2]) if r]
        if len(resolved) < 2:
            self.ambiguity.recognize('specific',
                observation="I couldn't match both sections to the post — name them as they appear in the outline.",
                metadata={'missing': 'second_section'})
            return TaskArtifact(origin=flow.name())
        sec_a, sec_b = resolved[0], resolved[1]
        if section_ids.index(sec_a) > section_ids.index(sec_b):
            sec_a, sec_b = sec_b, sec_a
        idx_a, idx_b = section_ids.index(sec_a), section_ids.index(sec_b)
        a = tools('read_section', {'post_id': post_id, 'sec_id': sec_a})
        b = tools('read_section', {'post_id': post_id, 'sec_id': sec_b})
        # Reorder is a structural change; snapshot the whole post pre-mutation.
        self.record_snapshot(self.content, flow, context, post_id)
        tools('remove_content', {'post_id': post_id, 'sec_id': sec_a})
        tools('remove_content', {'post_id': post_id, 'sec_id': sec_b})
        # After removing both, insert sec_b at sec_a's original position. Then insert
        # sec_a immediately after sec_b. The previous code anchored sec_a to section_ids[idx_b-1],
        # which equals sec_a itself when sec_a and sec_b are adjacent — and sec_a was just removed.
        anchor_b = section_ids[idx_a - 1] if idx_a > 0 else ''
        tools('insert_section', {'post_id': post_id, 'sec_id': anchor_b,
            'section_title': b['title'], 'content': b['content']})
        tools('insert_section', {'post_id': post_id, 'sec_id': sec_b,
            'section_title': a['title'], 'content': a['content']})
        self.complete_flow(flow, state, context, f'Swapped sections {sec_a} and {sec_b}.',
            metadata={'post_id': post_id})
        artifact = TaskArtifact(flow.name(), thoughts=f'Swapped sections {sec_a} and {sec_b}.')
        artifact.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        return artifact

    def _rework_move(self, flow, state, context, post_id, tools):
        where = flow.slots['category'].value  # 'to_top' or 'to_end' — guaranteed by _rework_category
        raw_secs = [e['sec'] for e in flow.slots['source'].values if e['sec']]
        if not raw_secs:
            self.ambiguity.recognize('specific', metadata={'missing': 'section'})
            return TaskArtifact(origin=flow.name())
        sec = self._resolve_sec_id(raw_secs[0], tools, post_id)
        if not sec:
            self.ambiguity.recognize('specific',
                observation=f"I couldn't find a section matching {raw_secs[0]!r} in this post.",
                metadata={'missing': 'section'})
            return TaskArtifact(origin=flow.name())
        section_ids = list(tools('read_metadata', {'post_id': post_id})['section_ids'])
        body = tools('read_section', {'post_id': post_id, 'sec_id': sec})
        # Reorder is a structural change; snapshot the whole post pre-mutation.
        self.record_snapshot(self.content, flow, context, post_id)
        tools('remove_content', {'post_id': post_id, 'sec_id': sec})
        remaining = [s for s in section_ids if s != sec]
        anchor = '' if where == 'to_top' else (remaining[-1] if remaining else '')
        tools('insert_section', {'post_id': post_id, 'sec_id': anchor,
            'section_title': body['title'], 'content': body['content']})
        self.complete_flow(flow, state, context, f'Moved {sec} to {where}.', metadata={'post_id': post_id})
        artifact = TaskArtifact(flow.name(), thoughts=f'Moved {sec} to {where}.')
        artifact.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        return artifact

    def write_policy(self, flow, state, context, tools):
        if artifact := self._guard_entity(flow): return artifact
        post_id, sec_id, error = self.resolve_source_ids(flow, state, tools)
        if error: return error
        self.record_snapshot(self.content, flow, context, post_id,
            sec_ids=[sec_id] if sec_id else None)
        text, tool_log = self.llm_execute(flow, state, context, tools)

        # Skill may declare ambiguity (e.g. confirmation on vague direction); leave flow
        # Active so the next turn can resolve rather than treating completion as final.
        if self.ambiguity.is_present:
            return TaskArtifact(origin=flow.name())

        # Bump used_count on scratchpad entries the skill actually consumed.
        parsed = self.engineer.parse(text)
        if isinstance(parsed, dict):
            for key in parsed.get('used', []):
                entry = self._read_scratch_value(str(key))
                if isinstance(entry, dict):
                    entry['used_count'] = entry['used_count'] + 1
                    self.scratchpad.append_entry(entry['origin'], entry)

        # Scope-mismatch fallback: if inspect_post flagged structural issues,
        # re-route to rework rather than committing the edit.
        inspect_result = self.engineer.extract_tool_result(tool_log, 'inspect_post')
        if inspect_result.get('structural_issues'):
            self.flow_stack.fallback('rework')
            return TaskArtifact(flow.name(), thoughts='Structural issues found, rerouting to rework.')

        saved, _ = self.engineer.tool_succeeded(tool_log, 'revise_content')
        if not saved:
            error_msg = 'Write flow did not persist any content; revise_content was not called or returned as failed.'
            return self.error_artifact(flow, 'failed_to_save', thoughts=error_msg, code=text)

        # Write's skill reply may be JSON ({used: [...]}) — store a sentence, not the blob (2.14.4)
        parsed = self.engineer.parse(text)
        summary = (parsed.get('summary') if parsed else text[:200]) or 'Saved the edit.'
        self.complete_flow(flow, state, context, summary, metadata={'post_id': post_id})
        artifact = TaskArtifact(flow.name(), thoughts=text)
        artifact.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        return artifact

    def audit_policy(self, flow, state, context, tools):
        """Audit detects voice/style drift (and applies a requested tone shift) and fixes it itself
        via revise_content. It may make no edits when the post already matches the user's voice;
        then it completes with a summary only."""
        if artifact := self._guard_entity(flow): return artifact
        post_id, _, error = self.resolve_source_ids(flow, state, tools)
        if error: return error

        self.record_snapshot(self.content, flow, context, post_id)
        pre = self._read_post_content(post_id, tools)
        text, tool_log = self.llm_execute(flow, state, context, tools,
            extra_resolved={'post_prose': pre.get('content', '')})
        if self.ambiguity.is_present:
            return TaskArtifact(flow.name())

        saved, _ = self.engineer.tool_succeeded(tool_log, 'revise_content')
        # Audit's contract is a plain line, but the model sometimes wraps JSON — parse it out (2.14.4)
        parsed = self.engineer.parse(text)
        summary = (parsed.get('summary') if parsed else text[:200]) or (
            'Revised the post to match your voice.' if saved else 'Audited the post — no changes needed.')
        self.complete_flow(flow, state, context, summary, metadata={'post_id': post_id})
        artifact = TaskArtifact('audit', thoughts=text)
        if saved:
            artifact.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        return artifact

    def propose_policy(self, flow, state, context, tools):
        """Two-phase discovery→pick split. Phase 1 (utterance turn): the
        sub-agent writes 2-3 candidates itself (no write_text), persisted to the scratchpad and
        rendered as a clickable selection — the flow stays Active in stage 'discovery'. Phase 2 (the
        pick click, an action turn carrying {39B} + choices): the chosen candidate fills the gap via
        revise_content, then the flow completes."""
        if flow.stage == 'discovery' and state.grounding.get('choices'):
            return self._propose_insert(flow, state, context, tools)
        return self._propose_generate(flow, state, context, tools)

    def _propose_generate(self, flow, state, context, tools):
        if artifact := self._guard_entity(flow): return artifact
        post_id, sec_id, error = self.resolve_source_ids(flow, state, tools)
        if error: return error
        if not sec_id:
            self.ambiguity.recognize('partial', metadata={'missing': 'source', 'entity': 'section'})
            return TaskArtifact(flow.name())

        extra = {}
        sec = tools('read_section', {'post_id': post_id, 'sec_id': sec_id})
        if sec['_success']:
            extra['section_content'] = sec['content']
        text, _ = self.llm_execute(flow, state, context, tools,
            extra_resolved=extra or None, exclude_tools=('revise_content',))
        if self.ambiguity.is_present:
            return TaskArtifact(flow.name())

        # Skill replies one candidate per line, numbered — strip the list marker and quotes.
        stripped = (re.sub(r'^\s*(?:\d+[.)]|[-*])\s*', '', ln).strip().strip('"')
                    for ln in (text or '').splitlines())
        candidates = [cand for cand in stripped if cand]
        if not candidates:
            return self.error_artifact(flow, 'empty_output',
                thoughts='Propose produced no candidate alternatives.', code=text)

        self.scratchpad.append_entry('propose',
            {'version': 1, 'turn_number': context.turn_id, 'used_count': 0,
             'candidates': candidates, 'post_id': post_id, 'sec_id': sec_id})
        flow.stage = 'discovery'
        block_options = [{'label': opt[:80], 'payload': idx, 'body': opt}
                         for idx, opt in enumerate(candidates)]
        artifact = TaskArtifact(flow.name(), thoughts=text)
        artifact.add_block({'type': 'selection', 'data': {
            'title': 'Pick an option to fill the gap', 'options': block_options,
            'submit_dax': '{39B}', 'submit_label': 'Use this',
        }})
        return artifact

    def _propose_insert(self, flow, state, context, tools):
        saved = self._read_scratch_value('propose')
        if not isinstance(saved, dict) or 'candidates' not in saved:
            self.ambiguity.recognize('specific',
                observation='The proposed options were lost between turns — run propose again.',
                metadata={'missing': 'candidates'})
            return TaskArtifact(flow.name())

        candidates, post_id, sec_id = saved['candidates'], saved['post_id'], saved['sec_id']
        # Choices accumulate across the session's grounding block, so the just-clicked pick is last.
        idx = list(state.grounding.get('choices', []))[-1]
        chosen = candidates[idx] if idx < len(candidates) else candidates[0]

        self.record_snapshot(self.content, flow, context, post_id, sec_ids=[sec_id])
        section = tools('read_section', {'post_id': post_id, 'sec_id': sec_id})
        body = section['content'] if section['_success'] else ''
        # lambda repl keeps `chosen` literal — LLM prose may contain backslashes or \g group refs.
        filled, count = _PLACEHOLDER_RE.subn(lambda _m: chosen, body, count=1)
        if count == 0:  # no marker left (gap already gone / loosely described) — append the pick
            filled = f'{body}\n{chosen}' if body else chosen
        tools('revise_content', {'post_id': post_id, 'sec_id': sec_id, 'content': filled})

        self.complete_flow(flow, state, context, f'Filled the gap in {sec_id}.',
            metadata={'post_id': post_id, 'sec_id': sec_id})
        artifact = TaskArtifact(flow.name(), thoughts=f'Filled the gap with: {chosen}')
        artifact.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        return artifact
