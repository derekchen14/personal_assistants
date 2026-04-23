from __future__ import annotations
from backend.modules.policies.base import BasePolicy
from backend.components.display_frame import DisplayFrame


class PublishPolicy(BasePolicy):

    def __init__(self, components:dict):
        super().__init__(components)
        self.flow_stack = components['flow_stack']

    def execute(self, state, context, tools) -> 'DisplayFrame':
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
        grounding = flow.slots[flow.entity_slot]
        if not grounding.check_if_filled():
            self.ambiguity.declare('partial', metadata={'missing_entity': 'post'})
            return DisplayFrame(flow.name())

        # Default-commit: channel defaults to 'mt1t' when unset.
        if not flow.slots['channel'].filled:
            flow.fill_slot_values({'channel': 'mt1t'})

        post_id, _ = self._resolve_source_ids(flow, state, tools)
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
            if post_id:
                self.retry_tool(tools, 'update_post',
                    {'post_id': post_id, 'updates': {'status': 'published'}})
            title = tools('read_metadata', {'post_id': post_id}).get('title', 'the post') if post_id else 'the post'
            channels = [v.get('chl') if isinstance(v, dict) else str(v) for v in flow.slots['channel'].values]
            message = f'Published "{title}" to {", ".join(channels)}.' if channels else f'Published "{title}".'
            frame.add_block({'type': 'toast', 'data': {'message': message, 'level': 'success'}})
        return frame

    @staticmethod
    def _first_failed_platform_tool(tool_log):
        for entry in tool_log:
            if entry['tool'] not in ('channel_status', 'release_post'):
                continue
            if not entry['result'].get('_success'):
                return entry['tool'], entry['result']
        return None

    def syndicate_policy(self, flow, state, context, tools):
        if not flow.slots['channel'].check_if_filled():
            self.ambiguity.declare('specific', metadata={'missing_slot': 'channel'})
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
            self.ambiguity.declare('specific', metadata={'missing_slot': missing})
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
        grounding = flow.slots[flow.entity_slot]
        if not grounding.check_if_filled():
            self.ambiguity.declare('partial', metadata={'missing_entity': 'post'})
            return DisplayFrame(flow.name())

        post_id, _ = self._resolve_source_ids(flow, state, tools)
        text, tool_log = self.llm_execute(flow, state, context, tools)
        flow.status = 'Completed'
        frame = DisplayFrame(flow.name(), thoughts=text)
        if post_id:
            frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        return frame

    def promote_policy(self, flow, state, context, tools):
        grounding = flow.slots[flow.entity_slot]
        if not grounding.check_if_filled():
            self.ambiguity.declare('partial', metadata={'missing_entity': 'post'})
            return DisplayFrame(flow.name())

        source_id, _ = self._resolve_source_ids(flow, state, tools)
        text, tool_log = self.llm_execute(flow, state, context, tools)

        post_data = self._read_post_content(source_id, tools) if source_id else {}
        if not post_data:
            source_meta = tools('read_metadata', {'post_id': source_id}) if source_id else {}
            source_title = source_meta.get('title', 'Untitled') if source_meta.get('_success') else 'Untitled'
            post_data = {'post_id': source_id or '', 'title': source_title}

        flow.status = 'Completed'
        frame = DisplayFrame(flow.name(), thoughts=text)
        frame.add_block({'type': 'card', 'data': post_data})
        return frame

    def cancel_policy(self, flow, state, context, tools):
        grounding = flow.slots[flow.entity_slot]
        if not grounding.check_if_filled():
            self.ambiguity.declare('partial', metadata={'missing_entity': 'post'})
            return DisplayFrame(flow.name())

        post_id, _ = self._resolve_source_ids(flow, state, tools)
        result = tools('update_post', {
            'post_id': post_id or '',
            'updates': {'status': 'draft'},
        })

        if result.get('_success'):
            flow.status = 'Completed'
            frame = DisplayFrame(flow.name())
            frame.add_block({'type': 'toast', 'data': {'message': 'Publication cancelled.'}})
        else:
            frame = self.error_frame(flow, 'tool_error',
                thoughts='Could not cancel publication.',
                code=result.get('_message', ''),
                failed_tool='update_post')
        return frame

    def survey_policy(self, flow, state, context, tools):
        text, tool_log = self.llm_execute(flow, state, context, tools)
        flow.status = 'Completed'
        return DisplayFrame(flow.name(), thoughts=text)
