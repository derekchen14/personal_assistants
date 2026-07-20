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
        schema-free dict). This component owns the Entry contract fields (round 5.2): `origin`
        and the `version` / `used_count` stamps land here, never in the callers — `turn_number`
        stays the caller's field (every caller holds the context, the scratchpad does not). A
        caller-passed `version`/`used_count` wins (e.g. re-filing an already-consumed entry).
        The session dir is created lazily on the first append (open_session stays
        side-effect free)."""
        stamped = {'version': 1, 'used_count': 0, **entry, 'origin': origin}
        self._scratchpad_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._scratchpad_path, 'a', encoding='utf-8') as file:
            file.write(json.dumps(stamped) + '\n')

    def read(self, origin:str|None=None, keys:list[str]|None=None, consume:bool=True) -> list[dict]:
        """Entries in append order (newest last), optionally filtered by `origin` and/or by `keys`
        that must all be present on an entry.

        Reading IS consuming (round 3.4): any returned entry with `used_count == 0` is bumped
        to 1 on disk — `used_count == 0` therefore means first appearance, and PEX's round
        refresh uses it as its seen-cursor (round 5.2). The returned dicts keep the pre-bump
        value so callers can still filter on it. Pass `consume=False` for maintenance scans
        and context renders that must not advance the cursor (NLU's review pass, the skill
        prompt's pad view)."""
        selected = entries = self._load()
        if origin:
            selected = [entry for entry in selected if entry['origin'] == origin]
        if keys:
            selected = [entry for entry in selected if all(name in entry for name in keys)]
        consumed = {id(entry) for entry in selected if entry.get('used_count') == 0}
        if consume and consumed:
            returned = [dict(entry) for entry in selected]     # pre-bump copies for the caller
            for entry in entries:
                if id(entry) in consumed:
                    entry['used_count'] += 1
            self._rewrite(entries)
            return returned
        return selected

    def amend_entry(self, origin:str, turn_number:int, entry:dict, reset:bool=False):
        """NLU-only (the review pass): modify an EXISTING entry in place — origin + turn_number
        is the pad's unique ID. Everyone else appends; only NLU may amend history. The amender
        decides whether the entry becomes consumable again: `reset=True` restarts `used_count`
        at 0; by default the stored count is kept untouched (round 5.2)."""
        entries = self._load()
        idx = self._locate(entries, origin, turn_number)
        count = 0 if reset else entries[idx].get('used_count', 0)
        entries[idx] = {'version': 1, **entry, 'origin': origin, 'used_count': count}
        self._rewrite(entries)

    def prune_entry(self, origin:str, turn_number:int):
        """NLU-only (the review pass): remove the entry identified by origin + turn_number —
        e.g. a stale note or a merged duplicate. The file is rewritten without it."""
        entries = self._load()
        entries.pop(self._locate(entries, origin, turn_number))
        self._rewrite(entries)

    def _load(self) -> list[dict]:
        """All entries, no filtering, no consuming — the shared loader for read/amend/prune."""
        if not self._scratchpad_path.exists():
            return []
        lines = self._scratchpad_path.read_text(encoding='utf-8').splitlines()
        return [json.loads(line) for line in lines]

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
