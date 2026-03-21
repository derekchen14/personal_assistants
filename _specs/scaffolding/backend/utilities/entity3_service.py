from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from backend.utilities.services import ToolService, _DB_DIR

_ENTITY3_FILE = _DB_DIR / 'entity3s.json'


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_entity3() -> list[dict]:
    if _ENTITY3_FILE.exists():
        data = json.loads(_ENTITY3_FILE.read_text(encoding='utf-8'))
        return data.get('entries', [])
    return []


def _save_entity3(entries:list[dict]) -> None:
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    _ENTITY3_FILE.write_text(
        json.dumps({'entries': entries}, indent=2, default=str),
        encoding='utf-8',
    )


class Entity3Service(ToolService):

    def list_all(self) -> dict:
        entries = _load_entity3()
        tagged = [{**ent, 'entity': 'entity3'} for ent in entries]
        return self._success(tagged)

    def select(self, entity3_id:str) -> dict:
        entries = _load_entity3()
        item = next((ent for ent in entries if ent.get('entity3_id') == entity3_id), None)
        if item is None:
            return self._error(f'entity3 not found: {entity3_id}')
        return self._success(item)

    def create(self, name:str, definition:str='') -> dict:
        if not name.strip():
            return self._error('name is required')
        entries = _load_entity3()
        new_item = {
            'entity3_id': str(uuid.uuid4())[:8],
            'name': name.strip(),
            'definition': definition.strip(),
            'created_at': _now(),
        }
        entries.append(new_item)
        _save_entity3(entries)
        return self._success(new_item)

    def update(self, entity3_id:str, name:str, definition:str='') -> dict:
        entries = _load_entity3()
        for idx, ent in enumerate(entries):
            if ent.get('entity3_id') == entity3_id:
                entries[idx] = {**ent, 'name': name.strip(), 'definition': definition.strip()}
                _save_entity3(entries)
                return self._success(entries[idx])
        return self._error(f'entity3 not found: {entity3_id}')

    def delete(self, entity3_id:str) -> dict:
        entries = _load_entity3()
        remaining = [ent for ent in entries if ent.get('entity3_id') != entity3_id]
        if len(remaining) == len(entries):
            return self._error(f'entity3 not found: {entity3_id}')
        _save_entity3(remaining)
        return self._success({'entity3_id': entity3_id})
