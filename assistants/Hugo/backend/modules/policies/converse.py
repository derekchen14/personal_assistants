from backend.modules.policies.base import BasePolicy
from backend.components.display_frame import DisplayFrame


class ConversePolicy(BasePolicy):

    def __init__(self, components):
        super().__init__(components)
        self.flow_stack = components['flow_stack']
        self.content = components['content_service']

    def execute(self, state, context, tools):
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
        if not flow.slots['target'].check_if_filled():
            convo_history = context.compile_history(look_back=3)
            prompt = f'{convo_history}\n\nExtract the preference key and value. Reply with JSON: {{"key": "...", "value": "..."}}.'
            raw_output = self.engineer(prompt, 'fill_slots')
            parsed = self.engineer.apply_guardrails(raw_output)
            if parsed:
                flow.fill_slots_by_label({'target': parsed})
            if not flow.slots['target'].check_if_filled():
                self.ambiguity.declare('specific', metadata={'missing': 'target'})
                return DisplayFrame(flow.name())

        slots = flow.slot_values_dict()
        setting = slots.get('target', {})
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
        if result['_success']:
            items = result['items']
            if items:
                titles = [it['title'] for it in items[:5]]
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
        topic_slot = flow.slots['topic']
        if topic_slot.check_if_filled():
            params['topic'] = str(topic_slot.to_dict())
        result = tools('explain_action', params)
        flow.status = 'Completed'
        if not result['_success']:
            return self.error_frame(flow, 'tool_error',
                thoughts=f'explain_action failed: {result["_error"]}.',
                code=result['_message'],
                failed_tool='explain_action')
        return DisplayFrame(origin='explain', thoughts=result.get('explanation', ''))

    def endorse_policy(self, flow, state, context, tools):
        frame = DisplayFrame(origin='endorse')
        if self.flow_stack.stack_size() > 1:
            state.keep_going = True
            endorsement = 'User accepted the suggestion and wants to proceed.'
            frame.thoughts = endorsement
            self.memory.write_scratchpad('endorse', endorsement)
        else:
            convo_history = context.compile_history()
            scratch = self.memory.read_scratchpad()
            frame.thoughts = self.engineer.skill_call(flow, convo_history, scratch, skill_name='endorse')

        flow.status = 'Completed'
        return frame

    def dismiss_policy(self, flow, state, context, tools):
        frame = DisplayFrame(origin='dismiss')
        if self.flow_stack.stack_size() > 1:
            state.keep_going = True
            self.memory.write_scratchpad('dismiss', 'User rejected the suggestion and wants to proceed.')
        else:
            convo_history = context.compile_history()
            scratch = self.memory.read_scratchpad()
            frame.thoughts = self.engineer.skill_call(flow, convo_history, scratch, skill_name='dismiss')

        flow.status = 'Completed'
        return frame

    def undo_policy(self, flow, state, context, tools):
        if frame := self._guard_entity(flow): return frame
        post_id = flow.slots['target'].values[0]['post']

        rewind = flow.slots['rewind']
        if not rewind.check_if_filled():
            self.ambiguity.declare('specific', metadata={'missing': 'rewind'})
            return DisplayFrame(origin='undo')

        snapshot_ids = self.content.list_snapshots()
        max_steps = min(self.content.max_snapshots, len(snapshot_ids))
        if rewind.level > max_steps:
            error_msg = f"Undo can only go back {max_steps} steps; got {rewind.level}."
            return self.toast_error(flow, 'invalid_input', error_msg)

        snap_id = snapshot_ids[rewind.level - 1]
        bundle = self.content.read_snapshot(snap_id)
        if bundle['post_id'] != post_id:
            error_msg = f'No content history for post: {post_id}.'
            return self.toast_error(flow, 'missing_reference', error_msg)

        result = tools('rollback_post', {'snapshot_id': snap_id})
        if result['_success']:
            # delete the snapshots we just consumed
            for consumed_id in snapshot_ids[:rewind.level]:
                (self.content._snap_root / f'{consumed_id}.json').unlink()

            state.active_post = post_id
            flow.status = 'Completed'
            frame = DisplayFrame(origin='undo', thoughts='Reverted your change.')
            frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
            frame.add_block({'type': 'toast', 'data': {'message': 'Undo successful', 'level': 'success'}})
            return frame
        error_msg = f"rollback_post {post_id} failed: {result['_message']}"
        return self.toast_error(flow, 'tool_error', error_msg)