from __future__ import annotations

from types import MappingProxyType
from uuid import uuid4


class ContextCoordinator:

    def __init__(self, config: MappingProxyType):
        self.config = config
        self._history: list[dict] = []
        self._checkpoints: list[dict] = []

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

    def compile_history(self, look_back: int = 5, keep_system: bool = True) -> str:
        """Return recent conversation as a formatted string for prompt context."""
        turns = self.full_conversation(keep_system=keep_system)
        recent = turns[-look_back:]
        return '\n'.join(recent)

    def full_conversation(self, keep_system: bool = True) -> list[str]:
        """Return all utterance turns as formatted strings."""
        allowed = {'User', 'Agent'}
        if keep_system:
            allowed.add('System')
        return [
            f"{t['speaker']}: {t['text']}"
            for t in self._history
            if t['speaker'] in allowed
        ]

    def recent_turns(self, n: int = 3) -> list[dict]:
        """Return last n raw turn dicts."""
        return self._history[-n:]

    def get_turn(self, turn_id: str) -> dict | None:
        for turn in self._history:
            if turn['turn_id'] == turn_id:
                return turn
        return None

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

    @property
    def last_user_turn(self) -> dict | None:
        for turn in reversed(self._history):
            if turn['speaker'] == 'User':
                return turn
        return None
