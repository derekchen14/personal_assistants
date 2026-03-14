from __future__ import annotations

from typing import TYPE_CHECKING

from backend.components.display_frame import DisplayFrame

if TYPE_CHECKING:
    from backend.components.dialogue_state import DialogueState
    from backend.components.context_coordinator import ContextCoordinator
    from backend.components.flow_stack.parents import BaseFlow


class InternalPolicy:

    def __init__(self, components: dict):
        self.memory = components['memory']
        self.config = components['config']

    def execute(self, flow: 'BaseFlow', state: 'DialogueState',
                context: 'ContextCoordinator', tools) -> 'DisplayFrame':
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

        frame = DisplayFrame(self.config)
        frame.set_frame('default', {'content': content})
        return frame

    def remember_policy(self, flow, tools):
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

        frame = DisplayFrame(self.config)
        frame.set_frame('default', {'content': ''})
        return frame

    def retrieve_policy(self, flow, tools):
        result = tools('memory_manager', {'action': 'read_scratchpad'})
        content = ''
        if result.get('status') == 'success':
            content = str(result.get('result', ''))

        frame = DisplayFrame(self.config)
        frame.set_frame('default', {'content': content})
        return frame

    def search_policy(self, flow, tools):
        query_slot = flow.slots.get('query')
        query = str(query_slot.to_dict()) if query_slot and query_slot.filled else ''

        content = ''
        if query:
            result = tools('search_reference', {'query': query})
            if result.get('status') == 'success':
                content = str(result.get('result', ''))

        frame = DisplayFrame(self.config)
        frame.set_frame('default', {'content': content})
        return frame

    def reference_policy(self, flow, tools):
        frame = DisplayFrame(self.config)
        frame.set_frame('default', {'content': ''})
        return frame

    def study_policy(self, flow, tools):
        source_slot = flow.slots.get('source')
        post_id = source_slot.to_dict() if source_slot and source_slot.filled else ''
        if isinstance(post_id, list) and post_id:
            post_id = post_id[0].get('post', '')
        result = tools('post_get', {'post_id': post_id})
        if result.get('status') == 'success':
            post = result.get('result', {})
            self.memory.write_scratchpad(
                f'post:{post_id}',
                f'{post.get("title", "")}: {post.get("content", "")[:500]}',
            )

        frame = DisplayFrame(self.config)
        frame.set_frame('default', {'content': ''})
        return frame
