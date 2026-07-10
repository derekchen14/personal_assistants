from backend.modules.policies.base import BasePolicy
from backend.components.task_artifact import TaskArtifact


class PublishPolicy(BasePolicy):

    def __init__(self, components):
        super().__init__(components)
        self.flow_stack = components['flow_stack']
        self.content = components['content_service']

    def execute(self, state, context, tools):
        flow = self.flow_stack.get_flow()

        match flow.name():
            case 'release': return self.release_policy(flow, state, context, tools)
            case 'schedule': return self.schedule_policy(flow, state, context, tools)
            case 'cite': return self.cite_policy(flow, state, context, tools)
            case _:
                return TaskArtifact()

    def _slot_steps(self, flow):
        steps = []
        for sn, slot in flow.slots.items():
            if slot.priority == 'required':
                steps.append({'name': sn, 'filled': slot.filled})
        current = next((i for i, s in enumerate(steps) if not s['filled']), len(steps))
        return steps, current

    def _clarify_with_steps(self, flow):
        """Publish-specific clarifier: toast-block showing the step the user
        needs to fill. Called when ambiguity is already declared."""
        steps, current = self._slot_steps(flow)
        artifact = TaskArtifact(flow.name())
        artifact.add_block({'type': 'toast', 'data': {
            'message': self.ambiguity.ask(flow.name()),
            'level': 'info',
            'steps': steps,
            'current_step': current,
        }})
        return artifact

    def release_policy(self, flow, state, context, tools):
        if artifact := self._guard_entity(flow): return artifact

        post_id, _, error = self.resolve_source_ids(flow, state, tools)
        if error: return error
        text, tool_log = self.llm_execute(flow, state, context, tools)

        # Skill may declare ambiguity (e.g. an unknown channel name); leave the flow Active
        # and ask — never publish in the same breath as the question.
        if self.ambiguity.is_present:
            return self._clarify_with_steps(flow)

        failed = self._first_failed_platform_tool(tool_log)
        artifact = TaskArtifact(flow.name(), thoughts=text)
        if failed:
            failed_tool, result = failed
            err_msg = result['_message'] if '_message' in result else result.get('_error', f'{failed_tool} failed')
            toast = {'message': f'{failed_tool} failed: {err_msg}'}
            if 'level' in result:
                toast['level'] = result['level']
            artifact.add_block({'type': 'toast', 'data': toast})
            self.complete_flow(flow, state, context, f'Release attempted but {failed_tool} failed: {err_msg}',
                metadata={'post_id': post_id, 'failed_tool': failed_tool})
        else:
            self.retry_tool(tools, 'update_post',
                {'post_id': post_id, 'updates': {'status': 'published'}})
            title = tools('read_metadata', {'post_id': post_id})['title']
            artifact.add_block({'type': 'toast', 'data': {'message': f'Published "{title}".', 'level': 'success'}})
            self.complete_flow(flow, state, context, f'Published "{title}".',
                metadata={'post_id': post_id, 'title': title})
        return artifact

    @staticmethod
    def _first_failed_platform_tool(tool_log):
        """First channel whose FINAL platform-tool result failed. Keyed per (tool, platform)
        so a self-corrected retry clears an earlier transient failure; calls missing the
        required `platform` arg never reached a channel (arg-shape mistake) and are skipped."""
        last = {}
        for entry in tool_log:
            if entry['tool'] in ('channel_status', 'release_post') and 'platform' in entry['input']:
                last[(entry['tool'], entry['input']['platform'])] = entry['result']
        for (tool_name, _), result in last.items():
            if not result['_success']:
                return tool_name, result
        return None

    def schedule_policy(self, flow, state, context, tools):
        missing = self._first_missing_required(flow, (flow.entity_slot, 'channel'))
        if missing:
            self.ambiguity.recognize('specific', metadata={'missing': missing})
            artifact = self._clarify_with_steps(flow)
        else:
            text, tool_log = self.llm_execute(flow, state, context, tools)
            self.complete_flow(flow, state, context, text or 'Publication scheduled.')
            artifact = TaskArtifact(flow.name(), thoughts=text)
            artifact.add_block({'type': 'toast', 'data': {'message': text}})
        return artifact

    @staticmethod
    def _first_missing_required(flow, slot_names):
        for name in slot_names:
            slot = flow.slots[name]
            if slot.priority == 'required' and not slot.check_if_filled():
                return name
        return None

    def cite_policy(self, flow, state, context, tools):
        target_slot = flow.slots['target']
        url_slot = flow.slots['url']
        if not target_slot.check_if_filled() and not url_slot.check_if_filled():
            self.ambiguity.recognize('specific', metadata={'missing': 'target'})
            return TaskArtifact()

        # Cite may proceed url-only without a grounded post, so an unresolvable reference is
        # not an early-return here — fall back to the prior active post and skip the snapshot.
        post_id, sec_id, _ = self.resolve_source_ids(flow, state, tools)
        if not post_id and state.get_active_post():
            post_id, sec_id = state.get_active_post(), None
        if post_id:
            self.record_snapshot(self.content, flow, context, post_id,
                sec_ids=[sec_id] if sec_id else None)

        text, tool_log = self.llm_execute(flow, state, context, tools)
        self.complete_flow(flow, state, context, 'Added the requested citation.',
            metadata={'post_id': post_id} if post_id else None)
        return TaskArtifact(origin='cite', thoughts=text)
