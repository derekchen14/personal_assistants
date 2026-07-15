import json
from pathlib import Path


class SessionScratchpad:
    """The open-ended working ledger — the cross-flow channel where the swarm shares findings within
    one conversation. A shared resource owned by the World; NLU sees it as `nlu.scratchpad` (beside
    `nlu.ambiguity`), and PEX + the policies read/write it through the same instance.

    One storage mode: an append-only JSONL file in the session dir (bound by World.open_session via
    `attach`), so every agent and sub-agent shares the same pad on disk. Entries are free-form dicts,
    each stamped with `origin` by this code — never trusted from LLM input. When an origin is written
    more than once, the newest entry wins on read."""

    def __init__(self, scratchpad_path:str|None=None):
        self._scratchpad_path = Path(scratchpad_path) if scratchpad_path else None

    def attach(self, scratchpad_path):
        """Bind the pad to its session file — World.open_session calls this."""
        self._scratchpad_path = Path(scratchpad_path)

    def append_entry(self, origin:str, entry:dict):
        """The write surface for PEX, the policies, and every sub-agent — append one entry (a
        schema-free dict). `origin` — the flow or module the entry is from, and its lookup
        handle — is stamped here, never trusted from LLM input. The session dir is created
        lazily on the first append (open_session stays side-effect free)."""
        stamped = {**entry, 'origin': origin}
        self._scratchpad_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._scratchpad_path, 'a', encoding='utf-8') as file:
            file.write(json.dumps(stamped) + '\n')

    def read(self, origin:str|None=None, keys:list[str]|None=None) -> list[dict]:
        """Entries in append order (newest last), optionally filtered by `origin` and/or by `keys`
        that must all be present on an entry."""
        if not self._scratchpad_path.exists():
            return []
        lines = self._scratchpad_path.read_text(encoding='utf-8').splitlines()
        entries = [json.loads(line) for line in lines]
        if origin:
            entries = [entry for entry in entries if entry['origin'] == origin]
        if keys:
            entries = [entry for entry in entries if all(name in entry for name in keys)]
        return entries

    def amend_entry(self, origin:str, turn_number:int, entry:dict):
        """NLU-only (the review pass): modify an EXISTING entry in place — origin + turn_number
        is the pad's unique ID. Everyone else appends; only NLU may amend history. The file is
        rewritten with the amended entry on the matched line."""
        entries = self.read()
        entries[self._locate(entries, origin, turn_number)] = {**entry, 'origin': origin}
        self._rewrite(entries)

    def prune_entry(self, origin:str, turn_number:int):
        """NLU-only (the review pass): remove the entry identified by origin + turn_number —
        e.g. a stale note or a merged duplicate. The file is rewritten without it."""
        entries = self.read()
        entries.pop(self._locate(entries, origin, turn_number))
        self._rewrite(entries)

    def _locate(self, entries:list, origin:str, turn_number:int) -> int:
        """Index of the entry carrying the unique ID (the newest match, should duplicate appends
        exist). Raises when no entry carries it."""
        matches = [idx for idx, entry in enumerate(entries)
                   if entry['origin'] == origin and entry.get('turn_number') == turn_number]
        if not matches:
            raise KeyError(f'scratchpad: no entry with origin={origin!r} turn_number={turn_number!r}')
        return matches[-1]

    def _rewrite(self, entries:list):
        lines = [json.dumps(entry) for entry in entries]
        self._scratchpad_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    def clear(self):
        if self._scratchpad_path and self._scratchpad_path.exists():
            self._scratchpad_path.write_text('', encoding='utf-8')

    @property
    def size(self) -> int:
        if not self._scratchpad_path.exists():
            return 0
        return len(self._scratchpad_path.read_text(encoding='utf-8').splitlines())
