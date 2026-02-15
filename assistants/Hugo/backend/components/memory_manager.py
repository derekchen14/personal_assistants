from __future__ import annotations

from collections import OrderedDict
from types import MappingProxyType


class MemoryManager:

    def __init__(self, config: MappingProxyType):
        self.config = config
        memory_cfg = config.get('memory', {})
        scratchpad_cfg = memory_cfg.get('scratchpad', {})
        self._max_snippets: int = scratchpad_cfg.get('max_snippets', 64)
        self._scratchpad: OrderedDict[str, str] = OrderedDict()
        self._preferences: dict[str, str] = {}

        summarization = memory_cfg.get('summarization', {})
        self._summarize_turn_count: int = summarization.get('trigger_turn_count', 20)

    # ── Scratchpad (session-scoped, L1) ──────────────────────────────

    def write_scratchpad(self, key: str, value: str):
        if key in self._scratchpad:
            self._scratchpad.move_to_end(key)
        self._scratchpad[key] = value
        while len(self._scratchpad) > self._max_snippets:
            self._scratchpad.popitem(last=False)

    def read_scratchpad(self, key: str | None = None) -> str | dict:
        if key:
            return self._scratchpad.get(key, '')
        return dict(self._scratchpad)

    def clear_scratchpad(self):
        self._scratchpad.clear()

    @property
    def scratchpad_size(self) -> int:
        return len(self._scratchpad)

    # ── User Preferences (persistent, RAM) ───────────────────────────

    def read_preferences(self) -> dict:
        return dict(self._preferences)

    def read_preference(self, key: str, default: str = '') -> str:
        return self._preferences.get(key, default)

    def write_preference(self, key: str, value: str):
        self._preferences[key] = value

    # ── Summarization trigger check ──────────────────────────────────

    def should_summarize(self, turn_count: int) -> bool:
        return turn_count >= self._summarize_turn_count

    # ── Component tool interface ─────────────────────────────────────

    def dispatch_tool(self, action: str, params: dict | None = None) -> dict:
        params = params or {}
        if action == 'read_scratchpad':
            key = params.get('key')
            data = self.read_scratchpad(key)
            return {'status': 'success', 'result': data}
        elif action == 'write_scratchpad':
            key = params.get('key', '')
            value = params.get('value', '')
            if key:
                self.write_scratchpad(key, value)
                return {'status': 'success', 'result': 'written'}
            return {'status': 'error', 'message': 'key is required'}
        elif action == 'read_preferences':
            return {'status': 'success', 'result': self.read_preferences()}
        return {'status': 'error', 'message': f'Unknown action: {action}'}
