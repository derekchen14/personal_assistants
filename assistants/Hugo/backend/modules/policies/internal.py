from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.modules.nlu import NLUResult
    from backend.modules.pex import PEXResult


_BATCH_1 = {'recap', 'remember', 'recall', 'study'}
_UNSUPPORTED = {'tidy', 'suggest'}


class InternalPolicy:

    def __init__(self, components: dict):
        self.memory = components['memory']
        self.context = components['context']

    def execute(self, flow_name: str, flow_info: dict,
                nlu_result: 'NLUResult', tool_dispatcher) -> 'PEXResult':
        from backend.modules.pex import PEXResult

        if flow_name in _UNSUPPORTED:
            return PEXResult(message='', block_type='default')

        handler = getattr(self, f'_do_{flow_name}', None)
        if handler:
            return handler(nlu_result, tool_dispatcher)

        return PEXResult(message='', block_type='default')

    def _do_recap(self, nlu_result, tool_dispatcher):
        from backend.modules.pex import PEXResult

        key = nlu_result.slots.get('key')
        if key:
            val = self.memory.read_scratchpad(key)
            return PEXResult(message=val or '', block_type='default')
        return PEXResult(
            message=str(self.memory.read_scratchpad()),
            block_type='default',
        )

    def _do_remember(self, nlu_result, tool_dispatcher):
        from backend.modules.pex import PEXResult
        return PEXResult(message='', block_type='default')

    def _do_recall(self, nlu_result, tool_dispatcher):
        from backend.modules.pex import PEXResult

        key = nlu_result.slots.get('key')
        if key:
            val = self.memory.read_preference(key)
            return PEXResult(message=str(val) if val else '', block_type='default')
        return PEXResult(message='', block_type='default')

    def _do_study(self, nlu_result, tool_dispatcher):
        from backend.modules.pex import PEXResult

        post_id = nlu_result.slots.get('post_id', '')
        result = tool_dispatcher('post_get', {'post_id': post_id})
        if result.get('status') == 'success':
            post = result.get('result', {})
            self.memory.write_scratchpad(
                f'post:{post_id}',
                f'{post.get("title", "")}: {post.get("content", "")[:500]}',
            )
        return PEXResult(message='', block_type='default')
