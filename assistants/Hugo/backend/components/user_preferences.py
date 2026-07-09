import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

# L2's per-account store lives beside sessions/: database/memory/<username>.json
_MEMORY_DIR = Path(__file__).resolve().parents[2] / 'database' / 'memory'

@dataclass
class Preference:
    """A typed L2 preference. A bare string is the degenerate case (endorsed, full confidence)."""
    value: str
    endorsed: bool = True
    rankings: list = field(default_factory=list)   # ordered runner-up values
    triggers: list = field(default_factory=list)   # keywords that surface this preference
    confidence: float = 1.0                        # [0,1], nudged by feedback
    # caution dial: a reserved Preference whose value is in {ignore, warning, alert} — SHAPE ONLY,
    # not yet wired to nlu_confidence_min. # designed-not-built

class UserPreferences:
    """MEM's L2 tier — per-account defaults, the single preference store. Holds typed records and
    renders them endorsed-vs-guessed for the frozen system prompt. Reached as `memory.preferences`."""

    def __init__(self, config, username):
        self.config = config
        self._preferences: dict[str, Preference] = {}
        self._store_path: Path = _MEMORY_DIR / f'{username}.json'
        self.load()

    def load(self):
        """Read the per-account store bound at construction; every later write saves through it."""
        if self._store_path.exists():
            records = json.loads(self._store_path.read_text())
            self._preferences = {key: Preference(**record) for key, record in records.items()}

    def save(self):
        """Write the full typed records to the bound per-account file."""
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        records = {key: asdict(pref) for key, pref in self._preferences.items()}
        self._store_path.write_text(json.dumps(records, indent=2))

    def store_preference(self, key:str, value_or_record):
        """A bare string stores the degenerate record (endorsed, confidence 1.0); a dict or a
        Preference stores the typed form. Every write lands on disk immediately."""
        if isinstance(value_or_record, Preference):
            self._preferences[key] = value_or_record
        elif isinstance(value_or_record, dict):
            self._preferences[key] = Preference(**value_or_record)
        else:
            self._preferences[key] = Preference(value=value_or_record)
        self.save()

    def get_preference(self, key:str, default:str='') -> str:
        pref = self._preferences.get(key)
        return pref.value if pref else default

    def read(self, query=None) -> dict:
        """What `recall` returns: a flat {key: value} view. Semantic filtering by `query` is
        deferred (no vector store yet), so this returns every preference for now."""
        return {key: pref.value for key, pref in self._preferences.items()}

    def render(self) -> str:
        """Sorted-by-key (cache-stable) prompt fragment. Endorsed → a standing instruction;
        guessed → an overridable default the user can correct."""
        lines = []
        for key in sorted(self._preferences):
            pref = self._preferences[key]
            if pref.endorsed:
                lines.append(f'- Remember, the user wants {pref.value}.')
            else:
                lines.append(f"- If the user hasn't said otherwise, assume {pref.value} — but "
                             'confirm if it matters.')
        return '\n'.join(lines)
