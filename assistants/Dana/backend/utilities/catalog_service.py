from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from backend.utilities.services import ToolService

_DB_DIR = Path(__file__).resolve().parents[2] / 'database'
_QUERIES_FILE = _DB_DIR / 'queries.json'
_METRICS_FILE = _DB_DIR / 'metrics.json'


def _load_queries() -> list[dict]:
    if not _QUERIES_FILE.exists():
        return []
    return json.loads(_QUERIES_FILE.read_text(encoding='utf-8')).get('entries', [])


def _save_queries(entries:list[dict]):
    _QUERIES_FILE.write_text(json.dumps({'entries': entries}, indent=2), encoding='utf-8')


def _load_metrics() -> list[dict]:
    if not _METRICS_FILE.exists():
        return []
    return json.loads(_METRICS_FILE.read_text(encoding='utf-8')).get('entries', [])


def _save_metrics(entries:list[dict]):
    _METRICS_FILE.write_text(json.dumps({'entries': entries}, indent=2), encoding='utf-8')


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SavedQueryService(ToolService):

    def list_all(self) -> list[dict]:
        return [{**entry, 'entity': 'query'} for entry in _load_queries()]

    def create(self, text:str) -> dict:
        entries = _load_queries()
        entry = {'query_id': str(uuid.uuid4()), 'text': text, 'created_at': _now()}
        entries.append(entry)
        _save_queries(entries)
        return entry

    def delete(self, query_id:str) -> bool:
        entries = _load_queries()
        new = [entry for entry in entries if entry['query_id'] != query_id]
        if len(new) == len(entries):
            return False
        _save_queries(new)
        return True

    def update(self, query_id:str, text:str) -> dict | None:
        entries = _load_queries()
        for entry in entries:
            if entry['query_id'] == query_id:
                entry['text'] = text
                _save_queries(entries)
                return entry
        return None

    def get(self, query_id:str) -> dict | None:
        for entry in _load_queries():
            if entry['query_id'] == query_id:
                return entry
        return None


class MetricService(ToolService):

    def list_all(self) -> list[dict]:
        return [{**entry, 'entity': 'metric'} for entry in _load_metrics()]

    def create(self, name:str, definition:str='') -> dict:
        entries = _load_metrics()
        entry = {
            'metric_id': str(uuid.uuid4()), 'name': name,
            'definition': definition, 'created_at': _now(),
        }
        entries.append(entry)
        _save_metrics(entries)
        return entry

    def delete(self, metric_id:str) -> bool:
        entries = _load_metrics()
        new = [entry for entry in entries if entry['metric_id'] != metric_id]
        if len(new) == len(entries):
            return False
        _save_metrics(new)
        return True

    def update(self, metric_id:str, name:str, definition:str) -> dict | None:
        entries = _load_metrics()
        for entry in entries:
            if entry['metric_id'] == metric_id:
                entry['name'] = name
                entry['definition'] = definition
                _save_metrics(entries)
                return entry
        return None

    def get(self, metric_id:str) -> dict | None:
        for entry in _load_metrics():
            if entry['metric_id'] == metric_id:
                return entry
        return None
