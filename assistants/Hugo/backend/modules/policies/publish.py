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
                return self.build_frame()

    def _slot_steps(self, flow):
        steps = []
        for sn, slot in flow.slots.items():
            if slot.priority == 'required':
                steps.append({'name': sn, 'filled': slot.filled})
        current = next((i for i, s in enumerate(steps) if not s['filled']), len(steps))
        return steps, current

    def _clarify_with_steps(self, flow):
        steps, current = self._slot_steps(flow)
        frame = self.build_frame(origin=flow.name())
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
            self.ambiguity.declare('specific', metadata={'missing_slot': flow.entity_slot})
            return self._clarify_with_steps(flow)
        if not flow.slots['channel'].filled:
            flow.fill_slot_values({'channel': 'mt1t'})

        post_id, _ = self._resolve_source_ids(flow, state, tools)
        text, tool_log = self.llm_execute(flow, state, context, tools)
        if post_id:
            tools('update_post', {'post_id': post_id, 'updates': {'status': 'published'}})
        flow.status = 'Completed'
        frame = self.build_frame(origin='release', thoughts=text)
        frame.add_block({'type': 'toast', 'data': {'message': text}})
        return frame

    def syndicate_policy(self, flow, state, context, tools):
        if not flow.slots['channel'].check_if_filled():
            self.ambiguity.declare('specific', metadata={'missing_slot': 'channel'})
            return self._clarify_with_steps(flow)

        text, tool_log = self.llm_execute(flow, state, context, tools)
        flow.status = 'Completed'
        frame = self.build_frame(origin='syndicate', thoughts=text)
        frame.add_block({'type': 'toast', 'data': {'message': text}})
        return frame

    def schedule_policy(self, flow, state, context, tools):
        for slot_name in (flow.entity_slot, 'channel'):
            slot = flow.slots[slot_name]
            if slot.priority == 'required' and not slot.check_if_filled():
                self.ambiguity.declare('specific', metadata={'missing_slot': slot_name})
                return self._clarify_with_steps(flow)

        text, tool_log = self.llm_execute(flow, state, context, tools)
        flow.status = 'Completed'
        frame = self.build_frame(origin='schedule', thoughts=text)
        frame.add_block({'type': 'toast', 'data': {'message': text}})
        return frame

    def preview_policy(self, flow, state, context, tools):
        grounding = flow.slots[flow.entity_slot]
        if not grounding.check_if_filled():
            self.ambiguity.declare('specific', metadata={'missing_slot': flow.entity_slot})
            return self._clarify_with_steps(flow)

        post_id, _ = self._resolve_source_ids(flow, state, tools)
        text, tool_log = self.llm_execute(flow, state, context, tools)
        flow.status = 'Completed'
        frame = self.build_frame(origin='preview', thoughts=text)
        if post_id:
            frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        return frame

    def promote_policy(self, flow, state, context, tools):
        grounding = flow.slots[flow.entity_slot]
        if not grounding.check_if_filled():
            self.ambiguity.declare('specific', metadata={'missing_slot': flow.entity_slot})
            return self._clarify_with_steps(flow)

        source_id, _ = self._resolve_source_ids(flow, state, tools)

        text, tool_log = self.llm_execute(flow, state, context, tools)

        source_meta = {}
        if source_id:
            get_result = tools('read_metadata', {'post_id': source_id})
            if get_result.get('_success'):
                source_meta = get_result

        source_title = source_meta.get('title', 'Untitled')

        post_data = self._read_post_content(source_id, tools) if source_id else {}
        flow.status = 'Completed'
        frame = self.build_frame(origin='promote', thoughts=text)
        card_data = post_data if post_data else {'post_id': source_id or '', 'title': source_title}
        frame.add_block({'type': 'card', 'data': card_data})
        return frame

    def cancel_policy(self, flow, state, context, tools):
        grounding = flow.slots[flow.entity_slot]
        if not grounding.check_if_filled():
            self.ambiguity.declare('specific', metadata={'missing_slot': flow.entity_slot})
            return self._clarify_with_steps(flow)

        post_id, _ = self._resolve_source_ids(flow, state, tools)

        result = tools('update_post', {
            'post_id': post_id or '',
            'updates': {'status': 'draft'},
        })

        message = 'Publication cancelled.' if result.get('_success') else 'Could not cancel.'
        flow.status = 'Completed'
        frame = self.build_frame(origin='cancel')
        frame.add_block({'type': 'toast', 'data': {'message': message}})
        return frame

    def survey_policy(self, flow, state, context, tools):
        text, tool_log = self.llm_execute(flow, state, context, tools)
        flow.status = 'Completed'
        return self.build_frame(origin='survey', thoughts=text)
