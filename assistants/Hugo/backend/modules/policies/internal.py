from __future__ import annotations
from backend.components.display_frame import DisplayFrame


class InternalPolicy:

    def __init__(self, components:dict):
        self.memory = components['memory']
        self.config = components['config']
        self.flow_stack = components['flow_stack']

    def execute(self, state, context, tools) -> 'DisplayFrame':
        flow = self.flow_stack.get_flow()

        match flow.name():
            case 'recap': return self.recap_policy(flow, tools)
            case 'remember': return self.remember_policy(flow, tools)
            case 'recall': return self.recall_policy(flow, tools)
            case 'store': return self.store_policy(flow, tools)
            case 'retrieve': return self.retrieve_policy(flow, tools)
            case 'search': return self.search_policy(flow, tools)
            case 'reference': return self.reference_policy(flow, tools)
            case 'study': return self.study_policy(flow, tools)
            case _: return DisplayFrame(self.config)

    def recap_policy(self, flow, tools):
        slot = flow.slots['key']
        if slot.check_if_filled():
            key = slot.to_dict()
            val = self.memory.read_scratchpad(key)
            if val:
                self.memory.write_scratchpad(f'recap:{key}', val)
        flow.status = 'Completed'
        return DisplayFrame(flow.name())

    def remember_policy(self, flow, tools):
        flow.status = 'Completed'
        return DisplayFrame(flow.name())

    def recall_policy(self, flow, tools):
        slot = flow.slots['key']
        if slot.check_if_filled():
            key = slot.to_dict()
            val = self.memory.read_preference(key)
            if val:
                self.memory.write_scratchpad(f'recall:{key}', str(val))
        flow.status = 'Completed'
        return DisplayFrame(flow.name())

    def store_policy(self, flow, tools):
        key_slot = flow.slots.get('key')
        val_slot = flow.slots.get('value')
        key = key_slot.to_dict() if key_slot and key_slot.filled else ''
        value = val_slot.to_dict() if val_slot and val_slot.filled else ''
        if key and value:
            self.memory.write_scratchpad(key, value)
        flow.status = 'Completed'
        return DisplayFrame(flow.name())

    def retrieve_policy(self, flow, tools):
        result = tools('manage_memory', {'action': 'read_scratchpad'})
        if result.get('_success'):
            payload = result.get('scratchpad', result.get('result', ''))
            self.memory.write_scratchpad('retrieve:last', str(payload))
        flow.status = 'Completed'
        return DisplayFrame(flow.name())

    def search_policy(self, flow, tools):
        query_slot = flow.slots['query']
        if query_slot.check_if_filled():
            query = str(query_slot.to_dict())
            result = tools('find_posts', {'query': query})
            if result.get('_success'):
                items = result.get('items', [])
                self.memory.write_scratchpad(f'search:{query}', str(items))
        flow.status = 'Completed'
        return DisplayFrame(flow.name())

    def reference_policy(self, flow, tools):
        flow.status = 'Completed'
        return DisplayFrame(flow.name())

    def study_policy(self, flow, tools):
        grounding = flow.slots[flow.entity_slot]
        post_id = grounding.values[0]['post'] if grounding.check_if_filled() else ''
        result = tools('read_metadata', {'post_id': post_id, 'include_outline': True})
        if result.get('_success'):
            self.memory.write_scratchpad(
                f'post:{post_id}',
                f'{result.get("title", "")}: {result.get("outline", "")[:500]}',
            )
        flow.status = 'Completed'
        return DisplayFrame(flow.name())
