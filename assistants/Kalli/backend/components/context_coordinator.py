"""Context Coordinator — conversation history, turn IDs, checkpoints."""

from __future__ import annotations

from types import MappingProxyType
from uuid import uuid4


class ContextCoordinator:

    def __init__(self, config: MappingProxyType):
        self.config = config
        self._history: list[dict] = []
        self._checkpoints: list[dict] = []
        self._fast_window_size: int = 7

    def add_turn(self, speaker: str, text: str,
                 form: str = 'text', turn_type: str | None = None) -> str:
        turn_id = str(uuid4())[:8]
        turn = {
            'turn_id': turn_id,
            'speaker': speaker,
            'text': text,
            'form': form,
        }
        if turn_type:
            turn['turn_type'] = turn_type
        self._history.append(turn)
        return turn_id

    def compile_history(self, turns: int = 5,
                        keep_system: bool = False) -> list[dict]:
        if keep_system:
            source = self._history
        else:
            source = [t for t in self._history if t['speaker'] != 'System']
        return source[-turns:]

    def get_turn(self, turn_id: str) -> dict | None:
        for turn in self._history:
            if turn['turn_id'] == turn_id:
                return turn
        return None

    def get_recent(self) -> list[dict]:
        utterances = [
            t for t in self._history
            if t['speaker'] in ('User', 'Agent')
        ]
        return utterances[-self._fast_window_size:]

    def save_checkpoint(self, label: str, data: dict | None = None):
        self._checkpoints.append({
            'label': label,
            'turn_count': len(self._history),
            'history_snapshot': [dict(t) for t in self._history],
            'data': data or {},
        })

    def get_checkpoint(self, label: str) -> dict | None:
        for cp in reversed(self._checkpoints):
            if cp['label'] == label:
                return cp
        return None

    def reset(self):
        self._history.clear()
        self._checkpoints.clear()

    @property
    def turn_count(self) -> int:
        return len(self._history)

    @property
    def last_user_text(self) -> str | None:
        for turn in reversed(self._history):
            if turn['speaker'] == 'User':
                return turn['text']
        return None
