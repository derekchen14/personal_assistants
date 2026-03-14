from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.components.dialogue_state import DialogueState
    from backend.components.context_coordinator import ContextCoordinator
    from backend.components.display_frame import DisplayFrame
    from backend.components.flow_stack.parents import BaseFlow


_BATCH_1 = {'recap', 'calculate', 'search', 'peek', 'recall', 'retrieve'}


class InternalPolicy:

    def __init__(self, components: dict):
        self.memory = components['memory']
        self.config = components['config']

    def execute(self, flow: 'BaseFlow', state: 'DialogueState',
                context: 'ContextCoordinator', tools) -> 'DisplayFrame':
        handler = getattr(self, f'_do_{flow.name()}', None)
        if handler:
            return handler(flow, tools)

        from backend.components.display_frame import DisplayFrame
        frame = DisplayFrame(self.config)
        frame.set_frame('default', {'content': ''})
        return frame

    def _do_recap(self, flow, tools):
        from backend.components.display_frame import DisplayFrame

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

    def _do_recall(self, flow, tools):
        from backend.components.display_frame import DisplayFrame

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

    def _do_calculate(self, flow, tools):
        from backend.components.display_frame import DisplayFrame

        slot = flow.slots.get('expression')
        expression = slot.to_dict() if slot and slot.filled else ''
        try:
            result = eval(expression, {'__builtins__': {}}, {})
            content = str(result)
        except Exception as e:
            content = f'Error: {e}'

        self.memory.write_scratchpad('last_calculation', content)

        frame = DisplayFrame(self.config)
        frame.set_frame('default', {'content': content})
        return frame

    def _do_search(self, flow, tools):
        from backend.components.display_frame import DisplayFrame
        from backend.utilities.services import _workspace

        slot = flow.slots.get('query')
        query = (slot.to_dict() if slot and slot.filled else '').lower()
        matches = []
        for name, df in _workspace.items():
            for col in df.columns:
                if query in col.lower():
                    matches.append(f'{name}.{col}')
            # Also check values in string columns
            for col in df.select_dtypes(include='object').columns:
                if df[col].astype(str).str.contains(query, case=False, na=False).any():
                    matches.append(f'{name}.{col} (values)')

        if matches:
            self.memory.write_scratchpad(f'search:{query}', str(matches[:10]))

        frame = DisplayFrame(self.config)
        frame.set_frame('default', {'content': str(matches[:10]) if matches else ''})
        return frame

    def _do_peek(self, flow, tools):
        from backend.components.display_frame import DisplayFrame
        from backend.utilities.services import _workspace

        slot = flow.slots.get('dataset')
        dataset = slot.to_dict() if slot and slot.filled else None
        if dataset and dataset in _workspace:
            df = _workspace[dataset]
            content = f'{dataset}: {len(df)} rows, columns: {list(df.columns)}'
        else:
            summaries = []
            for name, df in _workspace.items():
                summaries.append(f'{name}: {len(df)} rows, {len(df.columns)} cols')
            content = '; '.join(summaries) if summaries else 'No datasets loaded'

        self.memory.write_scratchpad('peek', content)

        frame = DisplayFrame(self.config)
        frame.set_frame('default', {'content': content})
        return frame

    def _do_retrieve(self, flow, tools):
        from backend.components.display_frame import DisplayFrame
        from backend.utilities.services import _workspace

        slot_ds = flow.slots.get('dataset')
        dataset = slot_ds.to_dict() if slot_ds and slot_ds.filled else None
        slot_key = flow.slots.get('key')
        key = slot_key.to_dict() if slot_key and slot_key.filled else None
        slot_val = flow.slots.get('value')
        value = slot_val.to_dict() if slot_val and slot_val.filled else None

        content = ''
        if dataset and dataset in _workspace:
            df = _workspace[dataset]
            if key and value:
                mask = df[key].astype(str).str.contains(str(value), case=False, na=False)
                matched = df[mask]
                content = matched.to_string(index=False) if not matched.empty else ''
            else:
                content = df.head(10).to_string(index=False)

        self.memory.write_scratchpad('retrieve', content)

        frame = DisplayFrame(self.config)
        frame.set_frame('default', {'content': content})
        return frame
