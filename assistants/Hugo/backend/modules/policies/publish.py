from backend.modules.policies.base import BasePolicy
from backend.components.display_frame import DisplayFrame


class PublishPolicy(BasePolicy):

    def __init__(self, components):
        super().__init__(components)
        self.flow_stack = components['flow_stack']

    def execute(self, state, context, tools):
        flow = self.flow_stack.get_flow()

        match flow.name():
            case 'release': return self.release_policy(flow, state, context, tools)
            case 'syndicate': return self.syndicate_policy(flow, state, context, tools)
            case 'schedule': return self.schedule_policy(flow, state, context, tools)
            case 'preview': return self.preview_policy(flow, state, context, tools)
            case 'promote': return self.promote_policy(flow, state, context, tools)
            case 'cancel': return self.cancel_policy(flow, state, context, tools)
            case 'survey': return self.survey_policy(flow, state, context, tools)
            case _:
                return DisplayFrame()

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
        frame = DisplayFrame(flow.name())
        frame.add_block({'type': 'toast', 'data': {
            'message': self.ambiguity.ask(),
            'level': 'info',
            'steps': steps,
            'current_step': current,
        }})
        return frame

    def release_policy(self, flow, state, context, tools):
        if frame := self._guard_entity(flow): return frame

        post_id, _, error = self.resolve_source_ids(flow, state, tools)
        if error: return error
        text, tool_log = self.llm_execute(flow, state, context, tools)

        failed = self._first_failed_platform_tool(tool_log)
        flow.status = 'Completed'
        frame = DisplayFrame(flow.name(), thoughts=text)
        if failed:
            failed_tool, result = failed
            err_msg = result['_message'] if '_message' in result else result.get('_error', f'{failed_tool} failed')
            toast = {'message': f'{failed_tool} failed: {err_msg}'}
            if 'level' in result:
                toast['level'] = result['level']
            frame.add_block({'type': 'toast', 'data': toast})
        else:
            self.retry_tool(tools, 'update_post',
                {'post_id': post_id, 'updates': {'status': 'published'}})
            title = tools('read_metadata', {'post_id': post_id})['title']
            frame.add_block({'type': 'toast', 'data': {'message': f'Published "{title}".', 'level': 'success'}})
        return frame

    @staticmethod
    def _first_failed_platform_tool(tool_log):
        for entry in tool_log:
            if entry['tool'] not in ('channel_status', 'release_post'):
                continue
            if not entry['result']['_success']:
                return entry['tool'], entry['result']
        return None

    def syndicate_policy(self, flow, state, context, tools):
        if not flow.slots['channel'].check_if_filled():
            self.ambiguity.declare('specific', metadata={'missing': 'channel'})
            frame = self._clarify_with_steps(flow)
        else:
            text, tool_log = self.llm_execute(flow, state, context, tools)
            flow.status = 'Completed'
            frame = DisplayFrame(flow.name(), thoughts=text)
            frame.add_block({'type': 'toast', 'data': {'message': text}})
        return frame

    def schedule_policy(self, flow, state, context, tools):
        missing = self._first_missing_required(flow, (flow.entity_slot, 'channel'))
        if missing:
            self.ambiguity.declare('specific', metadata={'missing': missing})
            frame = self._clarify_with_steps(flow)
        else:
            text, tool_log = self.llm_execute(flow, state, context, tools)
            flow.status = 'Completed'
            frame = DisplayFrame(flow.name(), thoughts=text)
            frame.add_block({'type': 'toast', 'data': {'message': text}})
        return frame

    @staticmethod
    def _first_missing_required(flow, slot_names):
        for name in slot_names:
            slot = flow.slots[name]
            if slot.priority == 'required' and not slot.check_if_filled():
                return name
        return None

    def preview_policy(self, flow, state, context, tools):
        if frame := self._guard_entity(flow): return frame

        post_id, _, error = self.resolve_source_ids(flow, state, tools)
        if error: return error
        text, tool_log = self.llm_execute(flow, state, context, tools)
        flow.status = 'Completed'
        frame = DisplayFrame(flow.name(), thoughts=text)
        frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        return frame

    def promote_policy(self, flow, state, context, tools):
        if frame := self._guard_entity(flow): return frame

        source_id, _, error = self.resolve_source_ids(flow, state, tools)
        if error: return error
        text, tool_log = self.llm_execute(flow, state, context, tools)

        flow.status = 'Completed'
        frame = DisplayFrame(flow.name(), thoughts=text)
        frame.add_block({'type': 'card', 'data': self._read_post_content(source_id, tools)})
        return frame

    def cancel_policy(self, flow, state, context, tools):
        if frame := self._guard_entity(flow): return frame

        post_id, _, error = self.resolve_source_ids(flow, state, tools)
        if error: return error
        result = tools('update_post', {
            'post_id': post_id,
            'updates': {'status': 'draft'},
        })

        if result['_success']:
            flow.status = 'Completed'
            frame = DisplayFrame(flow.name())
            frame.add_block({'type': 'toast', 'data': {'message': 'Publication cancelled.'}})
        else:
            frame = self.error_frame(flow, 'tool_error',
                thoughts='Could not cancel publication.',
                code=result['_message'],
                failed_tool='update_post')
        return frame

    def survey_policy(self, flow, state, context, tools):
        text, tool_log = self.llm_execute(flow, state, context, tools)
        flow.status = 'Completed'
        return DisplayFrame(flow.name(), thoughts=text)
