from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.components.dialogue_state import DialogueState
    from backend.components.display_frame import DisplayFrame


_BATCH_1 = {'recap', 'remember', 'recall', 'study'}


class InternalPolicy:

    def __init__(self, components: dict):
        self.memory = components['memory']
        self.world = components['world']

    def execute(self, flow_name: str, flow_info: dict,
                state: 'DialogueState', tool_dispatcher) -> 'DisplayFrame':
        handler = getattr(self, f'_do_{flow_name}', None)
        if handler:
            return handler(state, tool_dispatcher)

        from backend.components.display_frame import DisplayFrame
        frame = DisplayFrame(self.world.config)
        frame.set_frame('default', {'content': ''})
        return frame

    def _do_recap(self, state, tool_dispatcher):
        from backend.components.display_frame import DisplayFrame

        key = state.slots.get('key')
        if key:
            val = self.memory.read_scratchpad(key)
            content = val or ''
        else:
            content = str(self.memory.read_scratchpad())

        frame = DisplayFrame(self.world.config)
        frame.set_frame('default', {'content': content})
        return frame

    def _do_remember(self, state, tool_dispatcher):
        from backend.components.display_frame import DisplayFrame

        frame = DisplayFrame(self.world.config)
        frame.set_frame('default', {'content': ''})
        return frame

    def _do_recall(self, state, tool_dispatcher):
        from backend.components.display_frame import DisplayFrame

        key = state.slots.get('key')
        if key:
            val = self.memory.read_preference(key)
            content = str(val) if val else ''
        else:
            content = ''

        frame = DisplayFrame(self.world.config)
        frame.set_frame('default', {'content': content})
        return frame

    def _do_study(self, state, tool_dispatcher):
        from backend.components.display_frame import DisplayFrame

        post_id = state.slots.get('post_id', '')
        result = tool_dispatcher('post_get', {'post_id': post_id})
        if result.get('status') == 'success':
            post = result.get('result', {})
            self.memory.write_scratchpad(
                f'post:{post_id}',
                f'{post.get("title", "")}: {post.get("content", "")[:500]}',
            )

        frame = DisplayFrame(self.world.config)
        frame.set_frame('default', {'content': ''})
        return frame
