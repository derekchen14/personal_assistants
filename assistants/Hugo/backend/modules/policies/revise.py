from backend.modules.policies.base import BasePolicy
from backend.components.display_frame import DisplayFrame
from backend.prompts.pex.support.revise_prompts import ROUTE_FINDINGS_SCHEMA, build_route_findings_prompt

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
            case 'tone': return self.tone_policy(flow, state, context, tools)
            case 'audit': return self.audit_policy(flow, state, context, tools)
            case 'simplify': return self.simplify_policy(flow, state, context, tools)
            case 'remove': return self.remove_policy(flow, state, context, tools)
            case 'tidy': return self.tidy_policy(flow, state, context, tools)
            case _:
                return DisplayFrame()

    def rework_policy(self, flow, state, context, tools):
        if frame := self._guard_entity(flow): return frame
        post_id, _, error = self.resolve_source_ids(flow, state, tools)
        if error: return error

        # Category dispatch: each option resolves deterministically (move, fallback, or ambiguity).
        if flow.slots['category'].check_if_filled():
            return self._dispatch_rework_category(flow, state, post_id, context, tools)

        # Null-category agentic path: skill handles itemized changes via `suggestions` / `remove`.
        if not flow.slots['suggestions'].check_if_filled() and not flow.slots['remove'].check_if_filled():
            self.ambiguity.declare('specific', metadata={'missing': 'category_or_suggestions'})
            return DisplayFrame(origin=flow.name())

        self.record_snapshot(self.content, flow, context, post_id)
        text, tool_log = self.llm_execute(flow, state, context, tools, include_preview=True)
        parsed = self.engineer.apply_guardrails(text)
        saved, _ = self.engineer.tool_succeeded(tool_log, 'revise_content')

        frame = DisplayFrame(flow.name(), thoughts=text)
        if saved:
            for step_name in parsed['done']:
                flow.slots['suggestions'].mark_as_complete(step_name)

            if state.has_plan:
                scratch = {'version': '1', 'turn_number': context.turn_id, 'used_count': 0, 'summary': text[:200]}
                self.memory.write_scratchpad(flow.name(), scratch)
                audit = self.flow_stack.find_by_name('audit')
                audit.slots['delegates'].mark_as_complete(flow.name())

            flow.status = 'Completed'
            frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        else:
            frame.set_frame(new_data={'violation': 'failed_to_save'})

        return frame

    def _dispatch_rework_category(self, flow, state, post_id, context, tools):
        cat = flow.slots['category'].value
        if cat == 'swap':
            return self._rework_swap(flow, context, post_id, tools)
        if cat in ('to_top', 'to_end'):
            return self._rework_move(flow, context, post_id, tools, where=cat)
        if cat == 'trim':
            self.flow_stack.fallback('simplify')
            state.keep_going = True
            return DisplayFrame(flow.name(), thoughts='Trimming reads as Simplify, rerouting.')
        if cat == 'sharpen':
            self.flow_stack.fallback('add')
            state.keep_going = True
            return DisplayFrame(flow.name(), thoughts='Sharpening reads as Add, rerouting.')
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
        return DisplayFrame(origin=flow.name())

    def _rework_swap(self, flow, context, post_id, tools):
        sec_ids = [e['sec'] for e in flow.slots['source'].values if e['sec']]
        if len(sec_ids) < 2:
            self.ambiguity.declare('specific', metadata={'missing': 'second_section'})
            return DisplayFrame(origin=flow.name())
        section_ids = list(tools('read_metadata', {'post_id': post_id})['section_ids'])
        sec_a, sec_b = sec_ids[0], sec_ids[1]
        if section_ids.index(sec_a) > section_ids.index(sec_b):
            sec_a, sec_b = sec_b, sec_a
        idx_a, idx_b = section_ids.index(sec_a), section_ids.index(sec_b)
        a = tools('read_section', {'post_id': post_id, 'sec_id': sec_a})
        b = tools('read_section', {'post_id': post_id, 'sec_id': sec_b})
        # Reorder is a structural change; snapshot the whole post pre-mutation.
        self.record_snapshot(self.content, flow, context, post_id)
        tools('remove_content', {'post_id': post_id, 'sec_id': sec_a})
        tools('remove_content', {'post_id': post_id, 'sec_id': sec_b})
        anchor_b = section_ids[idx_a - 1] if idx_a > 0 else ''
        anchor_a = section_ids[idx_b - 1]  # idx_b > idx_a >= 0, so this is always defined
        tools('insert_section', {'post_id': post_id, 'sec_id': anchor_b,
            'section_title': b['title'], 'content': b['content']})
        tools('insert_section', {'post_id': post_id, 'sec_id': anchor_a,
            'section_title': a['title'], 'content': a['content']})
        flow.status = 'Completed'
        frame = DisplayFrame(flow.name(), thoughts=f'Swapped sections {sec_a} and {sec_b}.')
        frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        return frame

    def _rework_move(self, flow, context, post_id, tools, where):
        sec_ids = [e['sec'] for e in flow.slots['source'].values if e['sec']]
        if not sec_ids:
            self.ambiguity.declare('specific', metadata={'missing': 'section'})
            return DisplayFrame(origin=flow.name())
        sec = sec_ids[0]
        section_ids = list(tools('read_metadata', {'post_id': post_id})['section_ids'])
        body = tools('read_section', {'post_id': post_id, 'sec_id': sec})
        # Reorder is a structural change; snapshot the whole post pre-mutation.
        self.record_snapshot(self.content, flow, context, post_id)
        tools('remove_content', {'post_id': post_id, 'sec_id': sec})
        remaining = [s for s in section_ids if s != sec]
        anchor = '' if where == 'to_top' else (remaining[-1] if remaining else '')
        tools('insert_section', {'post_id': post_id, 'sec_id': anchor,
            'section_title': body['title'], 'content': body['content']})
        flow.status = 'Completed'
        frame = DisplayFrame(flow.name(), thoughts=f'Moved {sec} to {where}.')
        frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        return frame

    def polish_policy(self, flow, state, context, tools):
        if frame := self._guard_entity(flow): return frame
        post_id, sec_id, error = self.resolve_source_ids(flow, state, tools)
        if error: return error
        self.record_snapshot(self.content, flow, context, post_id,
            sec_ids=[sec_id] if sec_id else None)
        text, tool_log = self.llm_execute(flow, state, context, tools)

        # Skill may declare ambiguity (e.g. confirmation on vague direction); leave flow
        # Active so the next turn can resolve rather than treating completion as final.
        if self.ambiguity.present():
            return DisplayFrame(origin=flow.name())

        # Bump used_count on scratchpad entries the skill actually consumed.
        parsed = self.engineer.apply_guardrails(text)
        if isinstance(parsed, dict):
            for key in parsed.get('used', []):
                entry = self.memory.read_scratchpad(str(key))
                if isinstance(entry, dict):
                    entry['used_count'] = entry.get('used_count', 0) + 1
                    self.memory.write_scratchpad(str(key), entry)

        # Scope-mismatch fallback: if inspect_post flagged structural issues,
        # re-route to rework rather than committing the polish.
        inspect_result = self.engineer.extract_tool_result(tool_log, 'inspect_post')
        if inspect_result.get('structural_issues'):
            self.flow_stack.fallback('rework')
            state.keep_going = True
            return DisplayFrame(flow.name(), thoughts='Structural issues found, rerouting to rework.')

        saved, _ = self.engineer.tool_succeeded(tool_log, 'revise_content')
        if not saved:
            error_msg = 'Polish flow did not persist any content; revise_content was not called or returned as failed.'
            return self.error_frame(flow, 'failed_to_save', thoughts=error_msg, code=text)

        flow.status = 'Completed'
        frame = DisplayFrame(flow.name(), thoughts=text)
        frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        if state.has_plan:
            self.memory.write_scratchpad(flow.name(), {
                'version': '1', 'turn_number': context.turn_id,
                'used_count': 0, 'summary': text[:200],
            })
            audit = self.flow_stack.find_by_name('audit')
            audit.slots['delegates'].mark_as_complete(flow.name())
        return frame

    def tone_policy(self, flow, state, context, tools):
        if frame := self._guard_entity(flow): return frame

        # Default-commit: at least one tone elective must land before dispatch.
        if not flow.slots['chosen_tone'].check_if_filled() and not flow.slots['custom_tone'].check_if_filled():
            pref = self.memory.read_preference('tone')
            flow.fill_slot_values({'chosen_tone': pref or 'natural'})

        post_id, _, error = self.resolve_source_ids(flow, state, tools)
        if error: return error
        self.record_snapshot(self.content, flow, context, post_id)
        text, tool_log = self.llm_execute(flow, state, context, tools)

        flow.status = 'Completed'
        frame = DisplayFrame(flow.name(), thoughts=text)
        frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        # Record brief result for downstream plan steps to consume.
        if state.has_plan:
            self.memory.write_scratchpad(flow.name(), {
                'version': '1',
                'turn_number': context.turn_id,
                'used_count': 0,
                'summary': text[:200],
            })
            audit = self.flow_stack.find_by_name('audit')
            audit.slots['delegates'].mark_as_complete(flow.name())
        return frame

    def audit_policy(self, flow, state, context, tools):
        if frame := self._guard_entity(flow): return frame

        if flow.slots['delegates'].is_verified():
            flow.status = 'Completed'
            reports = {}
            for step in flow.slots['delegates'].steps:
                reports[step['name']] = self.memory.read_scratchpad(step['name'])['summary']

            state.has_plan = False
            state.keep_going = False
            finish_msg = f'Audit completed with {len(flow.slots["delegates"].steps)} delegated flows.'
            post_id, _, error = self.resolve_source_ids(flow, state, tools)
            if error: return error
            frame = DisplayFrame('audit', thoughts=finish_msg, metadata={'reports': reports})
            frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})

        elif flow.stage == 'discovery' and len(state.slices['choices']) > 0:
            flow.stage = 'delegation'
            frame = self._audit_dispatch(flow, state)

        else:
            self.resolve_source_ids(flow, state, tools)
            _, tool_log = self.llm_execute(flow, state, context, tools)
            saved = self.engineer.extract_tool_result(tool_log, 'save_findings')
            if saved:
                flow.stage = 'discovery'
                findings, summary = saved['findings'], saved['summary']
                frame = DisplayFrame(flow.name(), metadata={'findings': findings, 'summary': summary})
                if findings:
                    options = []
                    for idx, f in enumerate(findings):
                        location = f['sec_id'] or 'whole post'
                        opt = {'label': f"[{f['severity']}] {f['issue']} ({location})", 'payload': idx, 'body': f['note']}
                        options.append(opt)

                    block_msg = f'Audit found {len(findings)} issues — pick which to fix'
                    block_data = {'title': block_msg, 'options': options, 'submit_dax': '{13A}', 'submit_label': 'Send to fix'}
                    frame.add_block({'type': 'checklist', 'data': block_data})
                else:
                    flow.status = 'Completed'
            else:
                state.has_plan = False
                state.keep_going = False
                frame = self.error_frame(flow, 'parse_failure', thoughts='Audit did not emit structured findings.')

        return frame

    def _audit_dispatch(self, flow, state):
        saved = self.memory.read_scratchpad('audit')
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
                if grp['flow_name'] not in ('rework', 'polish', 'simplify', 'tone'):
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
        frame = DisplayFrame('audit', thoughts=f'Routing {num_picks} fix(es) to {num_delegates} flow(s).',
            metadata={'group_count': num_delegates, 'flow_names': [g['flow_name'] for g in groups]})
        return frame

    def simplify_policy(self, flow, state, context, tools):
        if frame := self._guard_entity(flow): return frame

        post_id, sec_id, error = self.resolve_source_ids(flow, state, tools)
        if error: return error
        if not sec_id:
            self.ambiguity.declare('partial', metadata={'missing': 'source', 'entity': 'section'})
            return DisplayFrame(flow.name())

        if not any(flow.slots[name].check_if_filled() for name in ('suggestions', 'guidance', 'image')):
            obs_message = f'What did you want to simplify within the {sec_id} section?'
            self.ambiguity.declare('specific', observation=obs_message, metadata={'missing': 'suggestions'})
            return DisplayFrame(flow.name())

        frame = DisplayFrame(origin='simplify')
        extra = {}
        sec = tools('read_section', {'post_id': post_id, 'sec_id': sec_id})
        if sec['_success']:
            extra['section_content'] = sec['content']
        self.record_snapshot(self.content, flow, context, post_id, sec_ids=[sec_id])
        text, tool_log = self.llm_execute(flow, state, context, tools, extra_resolved=extra or None)

        if self.ambiguity.present():
            return frame
        already_saved, _ = self.engineer.tool_succeeded(tool_log, 'revise_content')
        if text and already_saved:
            frame.thoughts = text
            frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
            flow.status = 'Completed'
        else:
            error_msg = 'Simplify flow did not persist any content; revise_content was not called or returned as failed.'
            return self.error_frame(flow, 'failed_to_save', thoughts=error_msg, code=text)

        if state.has_plan:
            new_memory = {'version': '1', 'turn_number': context.turn_id, 'used_count': 0, 'summary': text[:200]}
            self.memory.write_scratchpad('simplify', new_memory)
            audit = self.flow_stack.find_by_name('audit')
            audit.slots['delegates'].mark_as_complete('simplify')
        return frame

    def remove_policy(self, flow, state, context, tools):
        if not flow.is_filled():
            self.ambiguity.declare('partial', metadata={'missing': 'target'})
            return DisplayFrame(flow.name())

        if flow.slots['type'].check_if_filled():
            post_id, _, error = self.resolve_source_ids(flow, state, tools)
            if error: return error
            self.record_snapshot(self.content, flow, context, post_id)
            text, tool_log = self.llm_execute(flow, state, context, tools)
            flow.status = 'Completed'
            frame = DisplayFrame(flow.name(), thoughts=text)
            frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        else:
            self.ambiguity.declare('specific', metadata={'missing': 'type'})
            frame = DisplayFrame(flow.name())

        return frame

    def tidy_policy(self, flow, state, context, tools):
        if frame := self._guard_entity(flow): return frame

        if not flow.slots['settings'].check_if_filled():
            self.ambiguity.declare('specific',
                observation='Which formatting rules should I apply?',
                metadata={'missing': 'settings'})
            return DisplayFrame(flow.name())

        post_id, _, error = self.resolve_source_ids(flow, state, tools)
        if error: return error
        self.record_snapshot(self.content, flow, context, post_id)
        result = tools('read_metadata', {'post_id': post_id, 'include_outline': True})
        content = result['outline']
        settings = flow.slots['settings'].to_dict()

        convo_history = context.compile_history()
        history_with_data = (
            f"{convo_history}\n\n[Post content]\nTitle: {result['title']}\n"
            f"Content ({len(content)} chars): {content[:500]}\n\n"
            f"[Settings] {settings}"
        )
        text = self.engineer.skill_call(flow, history_with_data, self.memory.read_scratchpad(), max_tokens=4096)

        flow.status = 'Completed'
        frame = DisplayFrame(flow.name(), thoughts=text)
        frame.add_block({'type': 'card', 'data': {
            'post_id': post_id,
            'title': result['title'],
            'content': text,
        }})
        return frame
