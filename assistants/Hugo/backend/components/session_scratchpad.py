import json
from collections import OrderedDict
from pathlib import Path


class SessionScratchpad:
    """The open-ended working ledger — the cross-flow channel where the swarm shares findings within
    one conversation. A shared resource owned by the World; NLU sees it as `nlu.scratchpad` (beside
    `nlu.ambiguity`), and PEX + the policies read/write it through the same instance.

    Two modes behind the same method names:
      * no path  — in-memory key/value dict.
      * path set — append-only JSONL in the session dir; entries are free-form dicts, each stamped
        with `writer` by this code (never trusted from LLM input).
    """

    def __init__(self, config, scratchpad_path:str|None=None):
        scratchpad_cfg = config.get('memory', {}).get('scratchpad', {})
        self._max_snippets: int = scratchpad_cfg.get('max_snippets', 64)
        self._scratchpad = OrderedDict()
        self._scratchpad_path = Path(scratchpad_path) if scratchpad_path else None

    def write(self, key:str|dict, value:str|dict|None=None, writer:str='orchestrator'):
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

    def read(self, key:str|None=None, writer:str|None=None,
             keys:list[str]|None=None) -> str | dict | list[dict]:
        """In-memory mode: `key` lookup or the full dict. File mode: list of entries in append
        order (newest last), optionally filtered by `writer` and/or by `keys` that must all be
        present on an entry."""
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
        """Completion record: the structured handoff a flow writes on reaching Completed. Just a
        stamped append; returned so activate_flow can use it as the tool result."""
        record = {'flow': flow, 'summary': summary, 'metadata': metadata or {}}
        self.write(record, writer=flow)
        return {**record, 'writer': flow}

    def clear(self):
        if self._scratchpad_path is None:
            self._scratchpad.clear()
            return
        self._scratchpad_path.write_text('', encoding='utf-8')

    @property
    def size(self) -> int:
        if self._scratchpad_path is None:
            return len(self._scratchpad)
        if not self._scratchpad_path.exists():
            return 0
        return len(self._scratchpad_path.read_text(encoding='utf-8').splitlines())
