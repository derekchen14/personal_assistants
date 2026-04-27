from __future__ import annotations
from backend.modules.policies.base import BasePolicy
from backend.components.display_frame import DisplayFrame
from backend.prompts.pex.support.revise_prompts import ROUTE_FINDINGS_SCHEMA, build_route_findings_prompt

class RevisePolicy(BasePolicy):

    def __init__(self, components:dict):
        super().__init__(components)
        self.flow_stack = components['flow_stack']

    def execute(self, state, context, tools) -> 'DisplayFrame':
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

    def _guard_entity(self, flow):
        """Entity-missing guard. Declares `partial` and returns an empty frame with origin=flow.name() 
        when the entity slot is unfilled. Callers early-return on non-None result"""
        grounding = flow.slots[flow.entity_slot]
        if not grounding.check_if_filled():
            self.ambiguity.declare('partial', metadata={'missing_entity': 'post'})
            return DisplayFrame(flow.name())
        return None

    def rework_policy(self, flow, state, context, tools):
        if not flow.slots['source'].filled:
            self.ambiguity.declare('partial', metadata={'missing_entity': 'post'})
            return DisplayFrame(origin=flow.name())

        if flow.slots['changes'].filled:
            ideas = flow.slots['changes'].values
        elif flow.slots['suggestions'].filled:
            ideas = flow.slots['suggestions'].values
        else:
            self.ambiguity.declare('specific', metadata={'missing_slot': 'changes or suggestions'})
            return DisplayFrame(origin=flow.name())

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
            post_id, _ = self._resolve_source_ids(flow, state, tools)
            frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        else:
            frame.set_frame(new_data={'violation': 'failed_to_save'})

        return frame

    def polish_policy(self, flow, state, context, tools):
        if not flow.slots['source'].filled:
            self.ambiguity.declare('partial', metadata={'missing_entity': 'post'})
            return DisplayFrame(origin=flow.name())

        post_id, sec_id = self._resolve_source_ids(flow, state, tools)
        text, tool_log = self.llm_execute(flow, state, context, tools)

        if post_id and sec_id and text:
            self._persist_section(post_id, sec_id, text, tools)

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
            frame = DisplayFrame(flow.name(), thoughts='Structural issues found, rerouting to rework.')
        else:
            flow.status = 'Completed'
            frame = DisplayFrame(flow.name(), thoughts=text)
            if post_id:
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
        if not flow.slots['source'].filled:
            self.ambiguity.declare('partial', metadata={'missing_entity': 'post'})
            return DisplayFrame(origin=flow.name())

        # Default-commit: at least one tone elective must land before dispatch.
        if not flow.slots['chosen_tone'].check_if_filled() and not flow.slots['custom_tone'].check_if_filled():
            pref = self.memory.read_preference('tone')
            flow.fill_slot_values({'chosen_tone': pref or 'natural'})

        post_id, _ = self._resolve_source_ids(flow, state, tools)
        text, tool_log = self.llm_execute(flow, state, context, tools)

        flow.status = 'Completed'
        frame = DisplayFrame(flow.name(), thoughts=text)
        if post_id:
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
        if not flow.slots['source'].filled:
            self.ambiguity.declare('partial', metadata={'missing_entity': 'post'})
            return DisplayFrame(origin=flow.name())
        if not flow.slots['reference_count'].filled:
            flow.fill_slot_values({'reference_count': 5})

        if flow.slots['delegates'].is_verified():
            flow.status = 'Completed'
            reports = {}
            for step in flow.slots['delegates'].steps:
                reports[step['name']] = self.memory.read_scratchpad(step['name'])['summary']

            state.has_plan = False
            state.keep_going = False
            finish_msg = f'Audit completed with {len(flow.slots["delegates"].steps)} delegated flows.'
            frame = DisplayFrame('audit', thoughts=finish_msg, metadata={'reports': reports})

        elif flow.stage == 'discovery' and len(state.slices['choices']) > 0:
            flow.stage = 'delegation'
            frame = self._audit_dispatch(flow, state)

        else:
            self._resolve_source_ids(flow, state, tools)
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
                suggestions.append(f"[{finding['severity']}] {finding['issue']}: {finding['note']}")
            child = self.flow_stack.stackon(delegate['flow_name'])
            child.fill_slot_values({'suggestions': suggestions})
            flow.slots['delegates'].add_one(name=new_flow, description='; '.join(suggestions)[:200])

        state.has_plan = True
        state.keep_going = True
        num_picks, num_delegates = len(picked), len(groups)
        frame = DisplayFrame('audit', thoughts=f'Routing {num_picks} fix(es) to {num_delegates} flow(s).',
            metadata={'group_count': num_delegates, 'flow_names': [g['flow_name'] for g in groups]})
        return frame

    def simplify_policy(self, flow, state, context, tools):
        # Disjunction entity: source OR image must be filled.
        if not flow.slots['source'].check_if_filled() and not flow.slots['image'].check_if_filled():
            self.ambiguity.declare('partial', metadata={'missing_entity': 'post_or_image'})
            return DisplayFrame(flow.name())

        post_id, sec_id = self._resolve_source_ids(flow, state, tools)

        # Preload target section so the skill skips a runtime read_section.
        extra = {}
        if post_id and sec_id:
            sec = tools('read_section', {'post_id': post_id, 'sec_id': sec_id})
            if sec.get('_success'):
                extra['section_content'] = sec.get('content', '')

        text, tool_log = self.llm_execute(flow, state, context, tools, extra_resolved=extra or None)

        # Fallback persistence: if skill produced prose but didn't call revise_content.
        already_saved, _ = self.engineer.tool_succeeded(tool_log, 'revise_content')
        if post_id and sec_id and text and not already_saved:
            self._persist_section(post_id, sec_id, text, tools)

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

    def remove_policy(self, flow, state, context, tools):
        if not flow.is_filled():
            missing = 'section to remove' if not flow.slots['target'].filled else 'image to remove'
            self.ambiguity.declare('partial', metadata={'missing_entity': missing})
            return DisplayFrame(flow.name())

        if flow.slots['type'].check_if_filled():
            post_id, _ = self._resolve_source_ids(flow, state, tools)
            text, tool_log = self.llm_execute(flow, state, context, tools)
            flow.status = 'Completed'
            frame = DisplayFrame(flow.name(), thoughts=text)
            frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        else:
            self.ambiguity.declare('specific', metadata={'missing_slot': 'type'})
            frame = DisplayFrame(flow.name())

        return frame

    def tidy_policy(self, flow, state, context, tools):
        early = self._guard_entity(flow)
        if early is not None:
            return early

        post_id, _ = self._resolve_source_ids(flow, state, tools)
        result = tools('read_metadata', {'post_id': post_id, 'include_outline': True}) if post_id else {'_success': False}

        if not result.get('_success'):
            frame = self.error_frame(flow, 'missing_reference',
                thoughts='Could not find the specified post.',
                missing_entity='post')
        else:
            content = result.get('outline', '')
            settings_slot = flow.slots['settings']
            settings = settings_slot.to_dict() if settings_slot.filled else {}

            convo_history = context.compile_history()
            history_with_data = (
                f"{convo_history}\n\n[Post content]\nTitle: {result.get('title', '')}\n"
                f"Content ({len(content)} chars): {content[:500]}\n\n"
                f"[Settings] {settings if settings else 'default normalization'}"
            )
            text = self.engineer.skill_call(flow, history_with_data, self.memory.read_scratchpad(), max_tokens=4096)

            flow.status = 'Completed'
            frame = DisplayFrame(flow.name(), thoughts=text)
            frame.add_block({'type': 'card', 'data': {
                'post_id': post_id,
                'title': result.get('title', ''),
                'content': text,
            }})
        return frame
