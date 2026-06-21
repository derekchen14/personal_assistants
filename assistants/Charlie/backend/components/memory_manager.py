import json
from collections import OrderedDict
from pathlib import Path


class MemoryManager:

    def __init__(self, config, scratchpad_path:str|None=None):
        self.config = config
        memory_cfg = config.get('memory', {})
        scratchpad_cfg = memory_cfg.get('scratchpad', {})
        self._max_snippets: int = scratchpad_cfg.get('max_snippets', 64)
        self._scratchpad = OrderedDict()
        self._scratchpad_path = Path(scratchpad_path) if scratchpad_path else None
        self._preferences: dict[str, str] = {}

        summarization = memory_cfg.get('summarization', {})
        self._summarize_turn_count: int = summarization.get('trigger_turn_count', 20)

    # ── Scratchpad (session-scoped, L1) ──────────────────────────────
    # Two modes behind the same method names (parallel build, changes.md §5.3):
    #   * no path (old pipeline)  — in-memory key/value dict, unchanged behavior.
    #   * path set (orchestrator) — append-only JSONL in the session dir; entries are
    #     schema-free dicts, each stamped with `writer` by this code (decision 17).
    # The in-memory branch is deleted at cutover.

    def write_scratchpad(self, key:str|dict, value:str|dict|None=None, writer:str='orchestrator'):
        if self._scratchpad_path is None:
            if key in self._scratchpad:
                self._scratchpad.move_to_end(key)
            self._scratchpad[key] = value
            while len(self._scratchpad) > self._max_snippets:
                self._scratchpad.popitem(last=False)
            return
        entry = dict(key) if isinstance(key, dict) else {key: value}
        entry['writer'] = writer  # stamped by code, never trusted from LLM input
        with open(self._scratchpad_path, 'a', encoding='utf-8') as file:
            file.write(json.dumps(entry) + '\n')

    def read_scratchpad(self, key:str|None=None, writer:str|None=None,
                        keys:list[str]|None=None) -> str | dict | list[dict]:
        """In-memory mode: `key` lookup or full dict (old contract). File mode: list of
        entries in append order (newest last), optionally filtered by `writer` and/or by
        `keys` that must all be present on an entry."""
        if self._scratchpad_path is None:
            if key:
                return self._scratchpad.get(key, '')
            return dict(self._scratchpad)
        if not self._scratchpad_path.exists():
            return []
        lines = self._scratchpad_path.read_text(encoding='utf-8').splitlines()
        entries = [json.loads(line) for line in lines]
        if writer:
            entries = [entry for entry in entries if entry['writer'] == writer]
        if keys:
            entries = [entry for entry in entries if all(name in entry for name in keys)]
        return entries

    def write_completion(self, flow:str, summary:str, metadata:dict|None=None) -> dict:
        """Completion record (decision 7): the structured handoff a flow writes on reaching
        Completed. Just a stamped append; returned so activate_flow can use it as the tool
        result."""
        record = {'flow': flow, 'summary': summary, 'metadata': metadata or {}}
        self.write_scratchpad(record, writer=flow)
        return {**record, 'writer': flow}

    def clear_scratchpad(self):
        if self._scratchpad_path is None:
            self._scratchpad.clear()
            return
        self._scratchpad_path.write_text('', encoding='utf-8')

    @property
    def scratchpad_size(self) -> int:
        if self._scratchpad_path is None:
            return len(self._scratchpad)
        if not self._scratchpad_path.exists():
            return 0
        return len(self._scratchpad_path.read_text(encoding='utf-8').splitlines())

    # ── User Preferences (persistent, RAM) ───────────────────────────

    def read_preferences(self) -> dict:
        return dict(self._preferences)

    def read_preference(self, key:str, default:str='') -> str:
        return self._preferences.get(key, default)

    def write_preference(self, key:str, value:str):
        self._preferences[key] = value

    def should_summarize(self, turn_count:int) -> bool:
        return turn_count >= self._summarize_turn_count

    def dispatch_tool(self, action:str, params:dict|None=None) -> dict:
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
