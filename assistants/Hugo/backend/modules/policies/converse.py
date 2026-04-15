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
            case 'next': return self.next_policy(flow, state, context, tools)
            case 'feedback': return self.feedback_policy(flow, state, context, tools)
            case 'preference': return self.preference_policy(flow, state, context, tools)
            case 'suggest': return self.suggest_policy(flow, state, context, tools)
            case 'explain': return self.explain_policy(flow, state, context, tools)
            case 'endorse': return self.endorse_policy(flow, state, context, tools)
            case 'dismiss': return self.dismiss_policy(flow, state, context, tools)
            case 'undo': return self.undo_policy(flow, state, context, tools)
            case _:
                return self.build_frame()

    def chat_policy(self, flow, state, context, tools):
        convo_history = context.compile_history()
        text = self.engineer.call(convo_history)
        flow.status = 'Completed'
        return self.build_frame(origin='chat', thoughts=text)

    def next_policy(self, flow, state, context, tools):
        convo_history = context.compile_history()
        skill_prompt = self._load_skill_template('next')
        messages = self.engineer.build_skill_prompt(flow, convo_history, self.memory.read_scratchpad(), skill_prompt)
        text = self.engineer.call(messages)
        flow.status = 'Completed'
        return self.build_frame(origin='next', thoughts=text)

    def feedback_policy(self, flow, state, context, tools):
        convo_history = context.compile_history()
        skill_prompt = self._load_skill_template('feedback')
        messages = self.engineer.build_skill_prompt(flow, convo_history, self.memory.read_scratchpad(), skill_prompt)
        text = self.engineer.call(messages)
        flow.status = 'Completed'
        return self.build_frame(origin='feedback', thoughts=text)

    def preference_policy(self, flow, state, context, tools):
        if not flow.slots['setting'].check_if_filled():
            convo_history = context.compile_history(look_back=3)
            text = self.engineer.call(convo_history, system="Extract the preference key and value from the conversation.")
            parsed = self._parse_value(text)
            if parsed:
                flow.fill_slots_by_label({'setting': parsed})
            if not flow.slots['setting'].check_if_filled():
                self.ambiguity.declare('specific', metadata={'missing_slot': 'setting'})
                return self.build_frame()

        slots = flow.slot_values_dict()
        setting = slots.get('setting', {})
        if isinstance(setting, dict):
            key = setting.get('key', '')
            value = setting.get('value', '')
            if key and value:
                self.memory.write_scratchpad(f'pref:{key}', value)

        convo_history = context.compile_history()
        skill_prompt = self._load_skill_template('preference')
        messages = self.engineer.build_skill_prompt(flow, convo_history, self.memory.read_scratchpad(), skill_prompt)
        text = self.engineer.call(messages)
        flow.status = 'Completed'
        return self.build_frame(origin='preference', thoughts=text)

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

        skill_prompt = self._load_skill_template(flow.name())
        messages = self.engineer.build_skill_prompt(flow, history_with_data, self.memory.read_scratchpad(), skill_prompt)
        text = self.engineer.call(messages)
        flow.status = 'Completed'
        return self.build_frame(origin='suggest', thoughts=text)

    def explain_policy(self, flow, state, context, tools):
        text, tool_log = self.llm_execute(flow, state, context, tools)
        flow.status = 'Completed'
        return self.build_frame(origin='explain', thoughts=text)

    def endorse_policy(self, flow, state, context, tools):
        convo_history = context.compile_history()
        skill_prompt = self._load_skill_template('endorse')
        messages = self.engineer.build_skill_prompt(flow, convo_history, self.memory.read_scratchpad(), skill_prompt)
        text = self.engineer.call(messages)
        flow.status = 'Completed'
        return self.build_frame(origin='endorse', thoughts=text)

    def dismiss_policy(self, flow, state, context, tools):
        convo_history = context.compile_history()
        skill_prompt = self._load_skill_template('dismiss')
        messages = self.engineer.build_skill_prompt(flow, convo_history, self.memory.read_scratchpad(), skill_prompt)
        text = self.engineer.call(messages)
        flow.status = 'Completed'
        return self.build_frame(origin='dismiss', thoughts=text)

    def undo_policy(self, flow, state, context, tools):
        text, tool_log = self.llm_execute(flow, state, context, tools)
        flow.status = 'Completed'
        return self.build_frame(origin='undo', thoughts=text)
