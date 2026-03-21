from __future__ import annotations
from backend.components.display_frame import DisplayFrame


class InternalPolicy:

    def __init__(self, components:dict):
        self.memory = components['memory']
        self.config = components['config']
        self.flow_stack = components['flow_stack']

    def execute(self, state, context, tools) -> 'DisplayFrame':
        flow = self.flow_stack.get_active_flow()

        match flow.name():
            case 'recap': return self.recap_policy(flow, tools)
            case 'remember': return self.remember_policy(flow, tools)
            case 'recall': return self.recall_policy(flow, tools)
            case 'store': return self.store_policy(flow, tools)
            case 'retrieve': return self.retrieve_policy(flow, tools)
            case 'search': return self.search_policy(flow, tools)
            case 'reference': return self.reference_policy(flow, tools)
            case 'study': return self.study_policy(flow, tools)
            case _:
                frame = DisplayFrame(self.config)
                frame.set_frame('default', {'content': ''})
                return frame

    def recap_policy(self, flow, tools):
        slot = flow.slots.get('key')
        key = slot.to_dict() if slot and slot.filled else None
        if key:
            val = self.memory.read_scratchpad(key)
            content = val or ''
        else:
            content = str(self.memory.read_scratchpad())

        flow.status = 'Completed'
        frame = DisplayFrame(self.config)
        frame.set_frame('default', {'content': content})
        return frame

    def remember_policy(self, flow, tools):
        flow.status = 'Completed'
        frame = DisplayFrame(self.config)
        frame.set_frame('default', {'content': ''})
        return frame

    def recall_policy(self, flow, tools):
        slot = flow.slots.get('key')
        key = slot.to_dict() if slot and slot.filled else None
        if key:
            val = self.memory.read_preference(key)
            content = str(val) if val else ''
        else:
            content = ''

        flow.status = 'Completed'
        frame = DisplayFrame(self.config)
        frame.set_frame('default', {'content': content})
        return frame

    def store_policy(self, flow, tools):
        key_slot = flow.slots.get('key')
        val_slot = flow.slots.get('value')
        key = key_slot.to_dict() if key_slot and key_slot.filled else ''
        value = val_slot.to_dict() if val_slot and val_slot.filled else ''
        if key and value:
            self.memory.write_scratchpad(key, value)

        flow.status = 'Completed'
        frame = DisplayFrame(self.config)
        frame.set_frame('default', {'content': ''})
        return frame

    def retrieve_policy(self, flow, tools):
        result = tools('manage_memory', {'action': 'read_scratchpad'})
        content = ''
        if result.get('_success'):
            content = str(result.get('scratchpad', result.get('result', '')))

        flow.status = 'Completed'
        frame = DisplayFrame(self.config)
        frame.set_frame('default', {'content': content})
        return frame

    def search_policy(self, flow, tools):
        query_slot = flow.slots.get('query')
        query = str(query_slot.to_dict()) if query_slot and query_slot.filled else ''

        content = ''
        if query:
            result = tools('find_posts', {'query': query})
            if result.get('_success'):
                items = result.get('items', [])
                content = str(items)

        flow.status = 'Completed'
        frame = DisplayFrame(self.config)
        frame.set_frame('default', {'content': content})
        return frame

    def reference_policy(self, flow, tools):
        flow.status = 'Completed'
        frame = DisplayFrame(self.config)
        frame.set_frame('default', {'content': ''})
        return frame

    def study_policy(self, flow, tools):
        grounding = flow.slots.get(flow.entity_slot)
        post_id = grounding.values[0]['post'] if grounding and grounding.filled else ''
        result = tools('read_metadata', {'post_id': post_id, 'include_outline': True})
        if result.get('_success'):
            self.memory.write_scratchpad(
                f'post:{post_id}',
                f'{result.get("title", "")}: {result.get("outline", "")[:500]}',
            )

        flow.status = 'Completed'
        frame = DisplayFrame(self.config)
        frame.set_frame('default', {'content': ''})
        return frame
