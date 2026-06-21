import re

from backend.modules.policies.base import BasePolicy
from backend.components.task_artifact import TaskArtifact
from backend.prompts.pex.support.revise_prompts import ROUTE_FINDINGS_SCHEMA, build_route_findings_prompt

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
            case 'polish': return self.polish_policy(flow, state, context, tools)
            case 'audit': return self.audit_policy(flow, state, context, tools)
            case 'propose': return self.propose_policy(flow, state, context, tools)
            case _:
                return TaskArtifact()

    def _read_scratch_value(self, key):
        """Keyed scratchpad lookup: newest matching JSONL entry (changes.md §5.3)."""
        entries = self.memory.read_scratchpad(keys=[key])
        return entries[-1][key] if entries else ''

    def rework_policy(self, flow, state, context, tools):
        if artifact := self._guard_entity(flow): return artifact
        post_id, _, error = self.resolve_source_ids(flow, state, tools)
        if error: return error

        # Category dispatch: each option resolves deterministically (move, fallback, or ambiguity).
        if flow.slots['category'].check_if_filled():
            return self._dispatch_rework_category(flow, state, post_id, context, tools)

        # Null-category agentic path: skill handles itemized changes via `suggestions` / `remove`.
        if not flow.slots['suggestions'].check_if_filled() and not flow.slots['remove'].check_if_filled():
            self.ambiguity.declare('specific', metadata={'missing': 'category_or_suggestions'})
            return TaskArtifact(origin=flow.name())

        self.record_snapshot(self.content, flow, context, post_id)
        text, tool_log = self.llm_execute(flow, state, context, tools, include_preview=True)
        parsed = self.engineer.apply_guardrails(text)
        saved, _ = self.engineer.tool_succeeded(tool_log, 'revise_content')

        artifact = TaskArtifact(flow.name(), thoughts=text)
        if saved:
            for step_name in parsed['done']:
                flow.slots['suggestions'].mark_as_complete(step_name)

            if state.has_plan:
                scratch = {'version': '1', 'turn_number': context.turn_id, 'used_count': 0, 'summary': text[:200]}
                self.memory.write_scratchpad(flow.name(), scratch, writer=flow.name())
                audit = self.flow_stack.find_by_name('audit')
                audit.slots['delegates'].mark_as_complete(flow.name())

            self.complete_flow(flow, state, text[:200], metadata={'post_id': post_id})
            artifact.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        else:
            artifact.set_artifact(new_data={'violation': 'failed_to_save'})

        return artifact

    def _dispatch_rework_category(self, flow, state, post_id, context, tools):
        cat = flow.slots['category'].value
        if cat == 'swap':
            return self._rework_swap(flow, state, context, post_id, tools)
        if cat in ('to_top', 'to_end'):
            return self._rework_move(flow, state, context, post_id, tools)
        if cat == 'trim':
            self.flow_stack.fallback('polish')
            state.keep_going = True
            return TaskArtifact(flow.name(), thoughts='Trimming reads as Polish, rerouting.')
        if cat == 'sharpen':
            self.flow_stack.fallback('refine')
            state.keep_going = True
            return TaskArtifact(flow.name(), thoughts='Sharpening reads as Refine, rerouting.')
        # cat == 'reframe'
        self.ambiguity.declare(
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
            self.ambiguity.declare('specific', metadata={'missing': 'second_section'})
            return TaskArtifact(origin=flow.name())
        section_ids = list(tools('read_metadata', {'post_id': post_id})['section_ids'])
        # LLM fills source.sec with raw text ("Process"); canonicalize to slug ("process").
        resolved = [r for r in (self._resolve_sec_id(raw, tools, post_id) for raw in raw_secs[:2]) if r]
        if len(resolved) < 2:
            self.ambiguity.declare('specific',
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
        self.complete_flow(flow, state, f'Swapped sections {sec_a} and {sec_b}.',
            metadata={'post_id': post_id})
        artifact = TaskArtifact(flow.name(), thoughts=f'Swapped sections {sec_a} and {sec_b}.')
        artifact.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        return artifact

    def _rework_move(self, flow, state, context, post_id, tools):
        where = flow.slots['category'].value  # 'to_top' or 'to_end' — guaranteed by the dispatch
        raw_secs = [e['sec'] for e in flow.slots['source'].values if e['sec']]
        if not raw_secs:
            self.ambiguity.declare('specific', metadata={'missing': 'section'})
            return TaskArtifact(origin=flow.name())
        sec = self._resolve_sec_id(raw_secs[0], tools, post_id)
        if not sec:
            self.ambiguity.declare('specific',
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
        self.complete_flow(flow, state, f'Moved {sec} to {where}.', metadata={'post_id': post_id})
        artifact = TaskArtifact(flow.name(), thoughts=f'Moved {sec} to {where}.')
        artifact.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        return artifact

    def polish_policy(self, flow, state, context, tools):
        if artifact := self._guard_entity(flow): return artifact
        post_id, sec_id, error = self.resolve_source_ids(flow, state, tools)
        if error: return error
        self.record_snapshot(self.content, flow, context, post_id,
            sec_ids=[sec_id] if sec_id else None)
        text, tool_log = self.llm_execute(flow, state, context, tools)

        # Skill may declare ambiguity (e.g. confirmation on vague direction); leave flow
        # Active so the next turn can resolve rather than treating completion as final.
        if self.ambiguity.present():
            return TaskArtifact(origin=flow.name())

        # Bump used_count on scratchpad entries the skill actually consumed.
        parsed = self.engineer.apply_guardrails(text)
        if isinstance(parsed, dict):
            for key in parsed.get('used', []):
                entry = self._read_scratch_value(str(key))
                if isinstance(entry, dict):
                    entry['used_count'] = entry.get('used_count', 0) + 1
                    self.memory.write_scratchpad(str(key), entry, writer=flow.name())

        # Scope-mismatch fallback: if inspect_post flagged structural issues,
        # re-route to rework rather than committing the polish.
        inspect_result = self.engineer.extract_tool_result(tool_log, 'inspect_post')
        if inspect_result.get('structural_issues'):
            self.flow_stack.fallback('rework')
            state.keep_going = True
            return TaskArtifact(flow.name(), thoughts='Structural issues found, rerouting to rework.')

        saved, _ = self.engineer.tool_succeeded(tool_log, 'revise_content')
        if not saved:
            error_msg = 'Polish flow did not persist any content; revise_content was not called or returned as failed.'
            return self.error_artifact(flow, 'failed_to_save', thoughts=error_msg, code=text)

        self.complete_flow(flow, state, text[:200], metadata={'post_id': post_id})
        artifact = TaskArtifact(flow.name(), thoughts=text)
        artifact.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        if state.has_plan:
            self.memory.write_scratchpad(flow.name(), {
                'version': '1', 'turn_number': context.turn_id,
                'used_count': 0, 'summary': text[:200],
            }, writer=flow.name())
            audit = self.flow_stack.find_by_name('audit')
            audit.slots['delegates'].mark_as_complete(flow.name())
        return artifact

    def audit_policy(self, flow, state, context, tools):
        if artifact := self._guard_entity(flow): return artifact

        if flow.slots['delegates'].is_verified():
            reports = {}
            for step in flow.slots['delegates'].steps:
                entry = self._read_scratch_value(step['name'])
                reports[step['name']] = (
                    entry['summary'] if isinstance(entry, dict) and 'summary' in entry
                    else '(no summary recorded)'
                )

            state.has_plan = False
            state.keep_going = False
            finish_msg = f'Audit completed with {len(flow.slots["delegates"].steps)} delegated flows.'
            post_id, _, error = self.resolve_source_ids(flow, state, tools)
            if error: return error
            self.complete_flow(flow, state, finish_msg, metadata={'reports': reports})
            artifact = TaskArtifact('audit', thoughts=finish_msg, parts={'reports': reports})
            artifact.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})

        elif flow.stage == 'discovery' and len(state.slices['choices']) > 0:
            flow.stage = 'delegation'
            artifact = self._audit_dispatch(flow, state)

        else:
            self.resolve_source_ids(flow, state, tools)
            _, tool_log = self.llm_execute(flow, state, context, tools)
            saved = self.engineer.extract_tool_result(tool_log, 'save_findings')
            if saved:
                flow.stage = 'discovery'
                findings, summary = saved['findings'], saved['summary']
                artifact = TaskArtifact(flow.name(), parts={'findings': findings, 'summary': summary})
                if findings:
                    options = []
                    for idx, f in enumerate(findings):
                        location = f['sec_id'] or 'whole post'
                        opt = {'label': f"[{f['severity']}] {f['issue']} ({location})", 'payload': idx, 'body': f['note']}
                        options.append(opt)

                    block_msg = f'Audit found {len(findings)} issues — pick which to fix'
                    block_data = {'title': block_msg, 'options': options, 'submit_dax': '{13A}', 'submit_label': 'Send to fix'}
                    artifact.add_block({'type': 'checklist', 'data': block_data})
                else:
                    self.complete_flow(flow, state, summary or 'Audit found no issues.')
            else:
                state.has_plan = False
                state.keep_going = False
                artifact = self.error_artifact(flow, 'parse_failure', thoughts='Audit did not emit structured findings.')

        return artifact

    def _audit_dispatch(self, flow, state):
        saved = self._read_scratch_value('audit')
        if not isinstance(saved, dict) or 'findings' not in saved:
            self.ambiguity.declare('specific',
                observation='Audit findings were lost between turns — run the audit again.',
                metadata={'missing': 'findings'})
            return TaskArtifact(flow.name())
        findings = saved['findings']
        picked_idxs = list(state.slices['choices'])
        picked = [findings[i] for i in picked_idxs]

        # Short-circuit: all selected → single rework, skips routing LLM call.
        if len(picked) == len(findings):
            groups = [{'flow_name': 'rework', 'finding_idxs': picked_idxs}]
        else:
            prompt = build_route_findings_prompt(picked)
            result = self.engineer(prompt, task='skill', schema=ROUTE_FINDINGS_SCHEMA)
            groups = result['groups']

            for grp in groups:
                if grp['flow_name'] not in ('rework', 'polish'):
                    grp['flow_name'] = 'polish'

        for delegate in groups:
            new_flow = delegate['flow_name']
            suggestions = []
            for index in delegate['finding_idxs']:
                finding = findings[index]
                suggestions.append({
                    'name': f"[{finding['severity']}] {finding['issue']}",
                    'description': finding['note'],
                })
            child = self.flow_stack.stackon(delegate['flow_name'])
            child.fill_slot_values({'suggestions': suggestions})
            description = '; '.join(f"{s['name']}: {s['description']}" for s in suggestions)[:200]
            flow.slots['delegates'].add_one(name=new_flow, description=description)

        state.has_plan = True
        state.keep_going = True
        num_picks, num_delegates = len(picked), len(groups)
        artifact = TaskArtifact('audit', thoughts=f'Routing {num_picks} fix(es) to {num_delegates} flow(s).',
            parts={'group_count': num_delegates, 'flow_names': [g['flow_name'] for g in groups]})
        return artifact

    def propose_policy(self, flow, state, context, tools):
        """Two-phase, mirroring audit's discovery→delegation split. Phase 1 (utterance turn): the
        sub-agent writes 2-3 candidates itself (no write_text), persisted to the scratchpad and
        rendered as a clickable selection — the flow stays Active in stage 'discovery'. Phase 2 (the
        pick click, an action turn carrying {39B} + choices): the chosen candidate fills the gap via
        revise_content, then the flow completes."""
        if flow.stage == 'discovery' and state.slices['choices']:
            return self._propose_insert(flow, state, context, tools)
        return self._propose_generate(flow, state, context, tools)

    def _propose_generate(self, flow, state, context, tools):
        if artifact := self._guard_entity(flow): return artifact
        post_id, sec_id, error = self.resolve_source_ids(flow, state, tools)
        if error: return error
        if not sec_id:
            self.ambiguity.declare('partial', metadata={'missing': 'source', 'entity': 'section'})
            return TaskArtifact(flow.name())

        extra = {}
        sec = tools('read_section', {'post_id': post_id, 'sec_id': sec_id})
        if sec['_success']:
            extra['section_content'] = sec['content']
        text, _ = self.llm_execute(flow, state, context, tools,
            extra_resolved=extra or None, exclude_tools=('revise_content',))
        if self.ambiguity.present():
            return TaskArtifact(flow.name())

        # Skill replies one candidate per line, numbered — strip the list marker and quotes.
        stripped = (re.sub(r'^\s*(?:\d+[.)]|[-*])\s*', '', ln).strip().strip('"')
                    for ln in (text or '').splitlines())
        candidates = [cand for cand in stripped if cand]
        if not candidates:
            return self.error_artifact(flow, 'empty_output',
                thoughts='Propose produced no candidate alternatives.', code=text)

        self.memory.write_scratchpad('propose',
            {'candidates': candidates, 'post_id': post_id, 'sec_id': sec_id}, writer='propose')
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
            self.ambiguity.declare('specific',
                observation='The proposed options were lost between turns — run propose again.',
                metadata={'missing': 'candidates'})
            return TaskArtifact(flow.name())

        candidates, post_id, sec_id = saved['candidates'], saved['post_id'], saved['sec_id']
        # Slices accumulate across the session's single state, so the just-clicked pick is last.
        idx = list(state.slices['choices'])[-1]
        chosen = candidates[idx] if idx < len(candidates) else candidates[0]

        self.record_snapshot(self.content, flow, context, post_id, sec_ids=[sec_id])
        section = tools('read_section', {'post_id': post_id, 'sec_id': sec_id})
        body = section['content'] if section['_success'] else ''
        # lambda repl keeps `chosen` literal — LLM prose may contain backslashes or \g group refs.
        filled, count = _PLACEHOLDER_RE.subn(lambda _m: chosen, body, count=1)
        if count == 0:  # no marker left (gap already gone / loosely described) — append the pick
            filled = f'{body}\n{chosen}' if body else chosen
        tools('revise_content', {'post_id': post_id, 'sec_id': sec_id, 'content': filled})

        self.complete_flow(flow, state, f'Filled the gap in {sec_id}.',
            metadata={'post_id': post_id, 'sec_id': sec_id})
        artifact = TaskArtifact(flow.name(), thoughts=f'Filled the gap with: {chosen}')
        artifact.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        return artifact
