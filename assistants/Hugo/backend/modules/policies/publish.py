from __future__ import annotations

from typing import TYPE_CHECKING

from backend.modules.policies.base import BasePolicy

if TYPE_CHECKING:
    from backend.components.dialogue_state import DialogueState
    from backend.components.context_coordinator import ContextCoordinator
    from backend.components.display_frame import DisplayFrame
    from backend.components.flow_stack.parents import BaseFlow


class PublishPolicy(BasePolicy):

    def execute(self, flow: 'BaseFlow', state: 'DialogueState',
                context: 'ContextCoordinator', tools) -> 'DisplayFrame':
        match flow.name():
            case 'release': return self.release_policy(flow, state, context, tools)
            case 'syndicate': return self.syndicate_policy(flow, state, context, tools)
            case 'schedule': return self.schedule_policy(flow, state, context, tools)
            case 'preview': return self.preview_policy(flow, state, context, tools)
            case 'promote': return self.promote_policy(flow, state, context, tools)
            case 'cancel': return self.cancel_policy(flow, state, context, tools)
            case 'survey': return self.survey_policy(flow, state, context, tools)
            case _:
                return self.build_frame('default', {'content': ''})

    def release_policy(self, flow, state, context, tools):
        if not flow.slots.get('source', None) or not flow.slots['source'].filled:
            identifier = self.extract_source(flow, state)
            if identifier:
                flow.fill_slots_by_label({'source': identifier})
            if not flow.slots.get('source') or not flow.slots['source'].filled:
                self.ambiguity.declare('specific', metadata={'missing_slot': 'source'})
                return self.build_frame('default', {'content': self.ambiguity.ask()})
        if not flow.slots.get('channel', None) or not flow.slots['channel'].filled:
            self.ambiguity.declare('specific', metadata={'missing_slot': 'channel'})
            return self.build_frame('default', {'content': self.ambiguity.ask()})

        text, tool_log = self.llm_execute(flow, state, context, tools)
        block_data = self.build_block_data(flow, text, tool_log)
        return self.build_frame('toast', block_data, source='release')

    def syndicate_policy(self, flow, state, context, tools):
        if not flow.slots.get('channel', None) or not flow.slots['channel'].filled:
            self.ambiguity.declare('specific', metadata={'missing_slot': 'channel'})
            return self.build_frame('default', {'content': self.ambiguity.ask()})

        text, tool_log = self.llm_execute(flow, state, context, tools)
        block_data = self.build_block_data(flow, text, tool_log)
        return self.build_frame('toast', block_data, source='syndicate')

    def schedule_policy(self, flow, state, context, tools):
        for slot_name in ('source', 'channel'):
            slot = flow.slots.get(slot_name)
            if slot and slot.priority == 'required' and not slot.filled:
                if slot_name == 'source':
                    identifier = self.extract_source(flow, state)
                    if identifier:
                        flow.fill_slots_by_label({'source': identifier})
                if not slot or not slot.filled:
                    self.ambiguity.declare('specific', metadata={'missing_slot': slot_name})
                    return self.build_frame('default', {'content': self.ambiguity.ask()})

        text, tool_log = self.llm_execute(flow, state, context, tools)
        block_data = self.build_block_data(flow, text, tool_log)
        return self.build_frame('toast', block_data, source='schedule')

    def preview_policy(self, flow, state, context, tools):
        if not flow.slots.get('source', None) or not flow.slots['source'].filled:
            identifier = self.extract_source(flow, state)
            if identifier:
                flow.fill_slots_by_label({'source': identifier})
            if not flow.slots.get('source') or not flow.slots['source'].filled:
                self.ambiguity.declare('specific', metadata={'missing_slot': 'source'})
                return self.build_frame('default', {'content': self.ambiguity.ask()})

        text, tool_log = self.llm_execute(flow, state, context, tools)
        block_data = self.build_block_data(flow, text, tool_log)
        return self.build_frame('card', block_data, source='preview')

    def promote_policy(self, flow, state, context, tools):
        if not flow.slots.get('source', None) or not flow.slots['source'].filled:
            identifier = self.extract_source(flow, state)
            if identifier:
                flow.fill_slots_by_label({'source': identifier})
            if not flow.slots.get('source') or not flow.slots['source'].filled:
                self.ambiguity.declare('specific', metadata={'missing_slot': 'source'})
                return self.build_frame('default', {'content': self.ambiguity.ask()})

        text, tool_log = self.llm_execute(flow, state, context, tools)
        block_data = self.build_block_data(flow, text, tool_log)
        return self.build_frame('toast', block_data, source='promote')

    def cancel_policy(self, flow, state, context, tools):
        if not flow.slots.get('source', None) or not flow.slots['source'].filled:
            identifier = self.extract_source(flow, state)
            if identifier:
                flow.fill_slots_by_label({'source': identifier})
            if not flow.slots.get('source') or not flow.slots['source'].filled:
                self.ambiguity.declare('specific', metadata={'missing_slot': 'source'})
                return self.build_frame('default', {'content': self.ambiguity.ask()})

        slots = flow.slot_values_dict()
        identifier = self.extract_source(flow, state)
        post_id = self.resolve_post_id(identifier, tools) if identifier else None

        cancel_params = {'post_id': post_id or identifier}
        reason = slots.get('reason')
        if reason:
            cancel_params['reason'] = reason
        result = tools('manage_schedule', {'action': 'cancel', **cancel_params})

        content = 'Publication cancelled.' if result.get('status') == 'success' else 'Could not cancel.'
        return self.build_frame('toast', {'content': content}, source='cancel')

    def survey_policy(self, flow, state, context, tools):
        text, tool_log = self.llm_execute(flow, state, context, tools)
        block_data = self.build_block_data(flow, text, tool_log)
        return self.build_frame('list', block_data, source='survey')
