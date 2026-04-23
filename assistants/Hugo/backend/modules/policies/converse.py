from __future__ import annotations
from backend.modules.policies.base import BasePolicy
from backend.components.display_frame import DisplayFrame


class ConversePolicy(BasePolicy):

    def __init__(self, components:dict):
        super().__init__(components)
        self.flow_stack = components['flow_stack']

    def execute(self, state, context, tools) -> 'DisplayFrame':
        flow = self.flow_stack.get_flow()

        match flow.name():
            case 'chat': return self.chat_policy(flow, state, context, tools)
            case 'preference': return self.preference_policy(flow, state, context, tools)
            case 'suggest': return self.suggest_policy(flow, state, context, tools)
            case 'explain': return self.explain_policy(flow, state, context, tools)
            case 'endorse': return self.endorse_policy(flow, state, context, tools)
            case 'dismiss': return self.dismiss_policy(flow, state, context, tools)
            case 'undo': return self.undo_policy(flow, state, context, tools)
            case _:
                return DisplayFrame()

    def chat_policy(self, flow, state, context, tools):
        convo_history = context.compile_history()
        raw_output = self.engineer(convo_history)
        flow.status = 'Completed'
        return DisplayFrame(origin='chat', thoughts=raw_output)

    def preference_policy(self, flow, state, context, tools):
        if not flow.slots['setting'].check_if_filled():
            convo_history = context.compile_history(look_back=3)
            prompt = f'{convo_history}\n\nExtract the preference key and value. Reply with JSON: {{"key": "...", "value": "..."}}.'
            raw_output = self.engineer(prompt, 'fill_slots')
            parsed = self.engineer.apply_guardrails(raw_output)
            if parsed:
                flow.fill_slots_by_label({'setting': parsed})
            if not flow.slots['setting'].check_if_filled():
                self.ambiguity.declare('specific', metadata={'missing_slot': 'setting'})
                return DisplayFrame(flow.name())

        slots = flow.slot_values_dict()
        setting = slots.get('setting', {})
        if isinstance(setting, dict):
            key = setting.get('key', '')
            value = setting.get('value', '')
            if key and value:
                self.memory.write_scratchpad(f'pref:{key}', value)

        convo_history = context.compile_history()
        text = self.engineer.skill_call(flow, convo_history, self.memory.read_scratchpad(), skill_name='preference')
        flow.status = 'Completed'
        return DisplayFrame(origin='preference', thoughts=text)

    def suggest_policy(self, flow, state, context, tools):
        scratchpad = self.memory.read_scratchpad()
        active_post = state.active_post if state else None

        summary_parts = []
        if active_post:
            summary_parts.append(f'Active post: {active_post}')
        if scratchpad:
            summary_parts.append(f'Session notes: {str(scratchpad)[:300]}')

        result = tools('find_posts', {})
        if result.get('_success'):
            items = result.get('items', [])
            if items:
                titles = [it.get('title', 'Untitled') for it in items[:5]]
                summary_parts.append(f'Recent posts: {", ".join(titles)}')

        convo_history = context.compile_history()
        context_summary = '\n'.join(summary_parts)
        history_with_data = f"{convo_history}\n\n[Context]\n{context_summary}"

        text = self.engineer.skill_call(flow, history_with_data, self.memory.read_scratchpad())
        flow.status = 'Completed'
        return DisplayFrame(origin='suggest', thoughts=text)

    def explain_policy(self, flow, state, context, tools):
        params = {}
        turn_slot = flow.slots['turn_id']
        if turn_slot.check_if_filled():
            params['turn_id'] = str(turn_slot.to_dict())
        result = tools('explain_action', params)
        flow.status = 'Completed'
        if not result.get('_success'):
            reason = result.get('_error', '') or 'unknown'
            return self.error_frame(flow, 'tool_error',
                thoughts=f'explain_action failed: {reason}.',
                code=result.get('_message', ''),
                failed_tool='explain_action')
        return DisplayFrame(origin='explain', thoughts=result.get('explanation', ''))

    def endorse_policy(self, flow, state, context, tools):
        convo_history = context.compile_history()
        text = self.engineer.skill_call(flow, convo_history, self.memory.read_scratchpad(), skill_name='endorse')
        flow.status = 'Completed'
        return DisplayFrame(origin='endorse', thoughts=text)

    def dismiss_policy(self, flow, state, context, tools):
        convo_history = context.compile_history()
        text = self.engineer.skill_call(flow, convo_history, self.memory.read_scratchpad(), skill_name='dismiss')
        flow.status = 'Completed'
        return DisplayFrame(origin='dismiss', thoughts=text)

    def undo_policy(self, flow, state, context, tools):
        if not state.active_post:
            self.ambiguity.declare('partial', metadata={'missing_entity': 'post'})
            return DisplayFrame(flow.name())
        params = {'post_id': state.active_post}
        turn_slot = flow.slots['turn']
        if turn_slot.check_if_filled():
            try:
                params['version'] = int(turn_slot.level)
            except (TypeError, ValueError):
                pass
        result = tools('rollback_post', params)
        flow.status = 'Completed'
        if not result.get('_success'):
            reason = result.get('_error', '') or 'unknown'
            return self.error_frame(flow, 'tool_error',
                thoughts=f'rollback_post failed: {reason}.',
                code=result.get('_message', ''),
                failed_tool='rollback_post')
        message = result.get('message') or f"Rolled back to version {params.get('version', 1)}."
        return DisplayFrame(origin='undo', thoughts=message)
