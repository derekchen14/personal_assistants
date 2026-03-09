from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.components.dialogue_state import DialogueState
    from backend.components.display_frame import DisplayFrame


_BATCH_1 = {'recap', 'calculate', 'search', 'peek', 'recall', 'retrieve'}


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

    def _do_calculate(self, state, tool_dispatcher):
        from backend.components.display_frame import DisplayFrame

        expression = state.slots.get('expression', '')
        try:
            result = eval(expression, {'__builtins__': {}}, {})
            content = str(result)
        except Exception as e:
            content = f'Error: {e}'

        self.memory.write_scratchpad('last_calculation', content)

        frame = DisplayFrame(self.world.config)
        frame.set_frame('default', {'content': content})
        return frame

    def _do_search(self, state, tool_dispatcher):
        from backend.components.display_frame import DisplayFrame
        from backend.utilities.services import _workspace

        query = state.slots.get('query', '').lower()
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

        frame = DisplayFrame(self.world.config)
        frame.set_frame('default', {'content': str(matches[:10]) if matches else ''})
        return frame

    def _do_peek(self, state, tool_dispatcher):
        from backend.components.display_frame import DisplayFrame
        from backend.utilities.services import _workspace

        dataset = state.slots.get('dataset')
        if dataset and dataset in _workspace:
            df = _workspace[dataset]
            content = f'{dataset}: {len(df)} rows, columns: {list(df.columns)}'
        else:
            summaries = []
            for name, df in _workspace.items():
                summaries.append(f'{name}: {len(df)} rows, {len(df.columns)} cols')
            content = '; '.join(summaries) if summaries else 'No datasets loaded'

        self.memory.write_scratchpad('peek', content)

        frame = DisplayFrame(self.world.config)
        frame.set_frame('default', {'content': content})
        return frame

    def _do_retrieve(self, state, tool_dispatcher):
        from backend.components.display_frame import DisplayFrame
        from backend.utilities.services import _workspace

        dataset = state.slots.get('dataset')
        key = state.slots.get('key')
        value = state.slots.get('value')

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

        frame = DisplayFrame(self.world.config)
        frame.set_frame('default', {'content': content})
        return frame
