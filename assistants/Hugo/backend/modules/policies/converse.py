from backend.modules.policies.base import BasePolicy
from backend.components.task_artifact import TaskArtifact


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
                return TaskArtifact()

    def chat_policy(self, flow, state, context, tools):
        text, tool_log = self.llm_execute(flow, state, context, tools)
        ok, result = self.engineer.tool_succeeded(tool_log, 'call_flow_stack')

        if flow.stage == 'default' and ok and result.get('stacked'):
            flow.stage = 'dispatch'
            state.has_plan = True
            state.keep_going = True
            return TaskArtifact(origin='chat')

        flow.stage = 'direct'
        flow.status = 'Completed'
        state.has_plan = False
        state.keep_going = False
        return TaskArtifact(origin='chat', thoughts=text)

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
                return TaskArtifact(flow.name())

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
        return TaskArtifact(origin='preference', thoughts=text)

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
        return TaskArtifact(origin='suggest', thoughts=text)

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
            return self.error_artifact(flow, 'tool_error',
                thoughts=f'explain_action failed: {result["_error"]}.',
                code=result['_message'],
                failed_tool='explain_action')
        return TaskArtifact(origin='explain', thoughts=result.get('explanation', ''))

    def endorse_policy(self, flow, state, context, tools):
        artifact = TaskArtifact(origin='endorse')
        if self.flow_stack.stack_size() > 1:
            state.keep_going = True
            endorsement = 'User accepted the suggestion and wants to proceed.'
            artifact.thoughts = endorsement
            self.memory.write_scratchpad('endorse', endorsement)
        else:
            convo_history = context.compile_history()
            scratch = self.memory.read_scratchpad()
            artifact.thoughts = self.engineer.skill_call(flow, convo_history, scratch, skill_name='endorse')

        flow.status = 'Completed'
        return artifact

    def dismiss_policy(self, flow, state, context, tools):
        artifact = TaskArtifact(origin='dismiss')
        if self.flow_stack.stack_size() > 1:
            state.keep_going = True
            self.memory.write_scratchpad('dismiss', 'User rejected the suggestion and wants to proceed.')
        else:
            convo_history = context.compile_history()
            scratch = self.memory.read_scratchpad()
            artifact.thoughts = self.engineer.skill_call(flow, convo_history, scratch, skill_name='dismiss')

        flow.status = 'Completed'
        return artifact

    def undo_policy(self, flow, state, context, tools):
        if artifact := self._guard_entity(flow): return artifact
        post_id = flow.slots['target'].values[0]['post']

        rewind = flow.slots['rewind']
        if not rewind.check_if_filled():
            self.ambiguity.declare('specific', metadata={'missing': 'rewind'})
            return TaskArtifact(origin='undo')

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
            artifact = TaskArtifact(origin='undo', thoughts='Reverted your change.')
            artifact.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
            artifact.add_block({'type': 'toast', 'data': {'message': 'Undo successful', 'level': 'success'}})
            return artifact
        error_msg = f"rollback_post {post_id} failed: {result['_message']}"
        return self.toast_error(flow, 'tool_error', error_msg)