from collections import OrderedDict
from types import MappingProxyType


class MemoryManager:
    """Three-tier memory: scratchpad (L1), preferences (L2), business context (L3).

    Scratchpad entries are structured dicts keyed by `flow.name()`. Each entry
    carries a required envelope `{version, turn_number, used_count}` plus
    flow-specific payload keys. Producers write at policy entry; consumers
    read by key and increment `used_count` on entries they reference."""

    def __init__(self, config:MappingProxyType):
        self.config = config
        memory_cfg = config.get('memory', {})
        scratchpad_cfg = memory_cfg.get('scratchpad', {})
        self._max_entries:int = scratchpad_cfg.get('max_entries', 64)
        self._scratchpad:OrderedDict[str, dict] = OrderedDict()
        self._preferences:dict[str, str] = {}

        summarization = memory_cfg.get('summarization', {})
        self._summarize_turn_count:int = summarization.get('trigger_turn_count', 20)

    # ── Scratchpad (session-scoped, L1) ──────────────────────────────

    def write_scratchpad(self, name:str, payload:dict):
        """Write/update a structured entry. `name` is `flow.name()`. `payload`
        must include envelope keys (version, turn_number, used_count) plus
        flow-specific data."""
        if name in self._scratchpad:
            self._scratchpad.move_to_end(name)
        self._scratchpad[name] = payload
        while len(self._scratchpad) > self._max_entries:
            self._scratchpad.popitem(last=False)

    def read_scratchpad(self, name:str|None=None) -> dict|None:
        """Read a single entry by name (returns None if absent), or the whole
        pad as a dict-of-dicts when called with no args."""
        if name:
            return self._scratchpad.get(name)
        return dict(self._scratchpad)

    def clear_scratchpad(self, name:str|None=None):
        if name is None:
            self._scratchpad.clear()
        elif name in self._scratchpad:
            del self._scratchpad[name]

    @property
    def scratchpad_size(self) -> int:
        return len(self._scratchpad)

    # ── User Preferences (persistent, RAM) ───────────────────────────

    def read_preferences(self) -> dict:
        return dict(self._preferences)

    def read_preference(self, key:str, default:str='') -> str:
        return self._preferences.get(key, default)

    def write_preference(self, key:str, value:str):
        self._preferences[key] = value

    # ── Summarization trigger check ──────────────────────────────────

    def should_summarize(self, turn_count:int) -> bool:
        return turn_count >= self._summarize_turn_count

    # ── Component tool interface (skill-facing) ──────────────────────

    def dispatch_tool(self, action:str, params:dict|None=None) -> dict:
        params = params or {}
        if action == 'read_scratchpad':
            return {'status': 'success', 'result': self.read_scratchpad(params.get('name'))}
        elif action == 'write_scratchpad':
            name = params.get('name', '')
            payload = params.get('payload', {})
            if name:
                self.write_scratchpad(name, payload)
                return {'status': 'success', 'result': 'written'}
            return {'status': 'error', 'message': 'name is required'}
        elif action == 'read_preferences':
            return {'status': 'success', 'result': self.read_preferences()}
        return {'status': 'error', 'message': f'Unknown action: {action}'}
