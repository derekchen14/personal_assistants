from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from backend.utilities.services import ToolService, _DB_DIR

_ENTITY2_FILE = _DB_DIR / 'entity2s.json'


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_entity2() -> list[dict]:
    if _ENTITY2_FILE.exists():
        data = json.loads(_ENTITY2_FILE.read_text(encoding='utf-8'))
        return data.get('entries', [])
    return []


def _save_entity2(entries:list[dict]) -> None:
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    _ENTITY2_FILE.write_text(
        json.dumps({'entries': entries}, indent=2, default=str),
        encoding='utf-8',
    )


class Entity2Service(ToolService):

    def list_all(self) -> dict:
        entries = _load_entity2()
        tagged = [{**ent, 'entity': 'entity2'} for ent in entries]
        return self._success(tagged)

    def select(self, entity2_id:str) -> dict:
        entries = _load_entity2()
        item = next((ent for ent in entries if ent.get('entity2_id') == entity2_id), None)
        if item is None:
            return self._error(f'entity2 not found: {entity2_id}')
        return self._success(item)

    def create(self, text:str) -> dict:
        if not text.strip():
            return self._error('text is required')
        entries = _load_entity2()
        new_item = {
            'entity2_id': str(uuid.uuid4())[:8],
            'text': text.strip(),
            'created_at': _now(),
        }
        entries.append(new_item)
        _save_entity2(entries)
        return self._success(new_item)

    def update(self, entity2_id:str, text:str) -> dict:
        entries = _load_entity2()
        for idx, ent in enumerate(entries):
            if ent.get('entity2_id') == entity2_id:
                entries[idx] = {**ent, 'text': text.strip()}
                _save_entity2(entries)
                return self._success(entries[idx])
        return self._error(f'entity2 not found: {entity2_id}')

    def delete(self, entity2_id:str) -> dict:
        entries = _load_entity2()
        remaining = [ent for ent in entries if ent.get('entity2_id') != entity2_id]
        if len(remaining) == len(entries):
            return self._error(f'entity2 not found: {entity2_id}')
        _save_entity2(remaining)
        return self._success({'entity2_id': entity2_id})
