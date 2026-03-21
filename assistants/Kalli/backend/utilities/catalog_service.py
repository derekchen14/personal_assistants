from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from backend.utilities.services import ToolService

_DB_DIR = Path(__file__).resolve().parents[2] / 'database'
_REQS_FILE = _DB_DIR / 'requirements.json'
_TOOLS_FILE = _DB_DIR / 'tools.json'


def _load_requirements() -> list[dict]:
    if not _REQS_FILE.exists():
        return []
    data = json.loads(_REQS_FILE.read_text(encoding='utf-8'))
    return data.get('entries', [])


def _save_requirements(entries:list[dict]):
    _REQS_FILE.write_text(json.dumps({'entries': entries}, indent=2), encoding='utf-8')


def _load_tools() -> list[dict]:
    if not _TOOLS_FILE.exists():
        return []
    data = json.loads(_TOOLS_FILE.read_text(encoding='utf-8'))
    return data.get('entries', [])


def _save_tools(entries:list[dict]):
    _TOOLS_FILE.write_text(json.dumps({'entries': entries}, indent=2), encoding='utf-8')


class RequirementService(ToolService):

    def list_all(self) -> list[dict]:
        entries = _load_requirements()
        return [{**item, 'entity': 'requirement'} for item in entries]

    def create(self, text:str) -> dict:
        entries = _load_requirements()
        entry = {
            'req_id': str(uuid.uuid4()),
            'text': text,
            'created_at': datetime.now(timezone.utc).isoformat(),
        }
        entries.append(entry)
        _save_requirements(entries)
        return {**entry, 'entity': 'requirement'}

    def delete(self, req_id:str) -> bool:
        entries = _load_requirements()
        new_entries = [item for item in entries if item['req_id'] != req_id]
        if len(new_entries) == len(entries):
            return False
        _save_requirements(new_entries)
        return True

    def update(self, req_id:str, text:str) -> dict | None:
        entries = _load_requirements()
        for entry in entries:
            if entry['req_id'] == req_id:
                entry['text'] = text
                _save_requirements(entries)
                return {**entry, 'entity': 'requirement'}
        return None

    def get(self, req_id:str) -> dict | None:
        for entry in _load_requirements():
            if entry['req_id'] == req_id:
                return {**entry, 'entity': 'requirement'}
        return None


class ToolDefService(ToolService):

    def list_all(self) -> list[dict]:
        entries = _load_tools()
        return [{**item, 'entity': 'tool'} for item in entries]

    def create(self, name:str, description:str='') -> dict:
        entries = _load_tools()
        entry = {
            'tool_id': str(uuid.uuid4()),
            'name': name,
            'description': description,
            'created_at': datetime.now(timezone.utc).isoformat(),
        }
        entries.append(entry)
        _save_tools(entries)
        return {**entry, 'entity': 'tool'}

    def delete(self, tool_id:str) -> bool:
        entries = _load_tools()
        new_entries = [item for item in entries if item['tool_id'] != tool_id]
        if len(new_entries) == len(entries):
            return False
        _save_tools(new_entries)
        return True

    def update(self, tool_id:str, name:str, description:str) -> dict | None:
        entries = _load_tools()
        for entry in entries:
            if entry['tool_id'] == tool_id:
                entry['name'] = name
                entry['description'] = description
                _save_tools(entries)
                return {**entry, 'entity': 'tool'}
        return None

    def get(self, tool_id:str) -> dict | None:
        for entry in _load_tools():
            if entry['tool_id'] == tool_id:
                return {**entry, 'entity': 'tool'}
        return None


class LessonService(ToolService):

    def __init__(self, db_conn=None):
        self.db = db_conn
        self._lessons: list[dict] = []
        self._next_id = 1

    def store(self, content:str, category:str|None=None,
              tags:list[str]|None=None) -> dict:
        """tool_id: lesson_store"""
        lesson = {
            'lesson_id': str(self._next_id),
            'content': content,
            'category': category,
            'tags': tags or [],
        }
        self._lessons.append(lesson)
        self._next_id += 1
        return {
            'status': 'success',
            'result': {'lesson_id': lesson['lesson_id']},
            'metadata': {'total_lessons': len(self._lessons)},
        }

    def search(self, query:str, category:str|None=None,
               limit:int=10) -> dict:
        """tool_id: lesson_search"""
        results = []
        query_lower = query.lower()
        for lesson in self._lessons:
            if category and lesson.get('category') != category:
                continue
            if query_lower in lesson['content'].lower():
                results.append(lesson)
            elif any(query_lower in tag.lower() for tag in lesson.get('tags', [])):
                results.append(lesson)
        results = results[:limit]
        return {
            'status': 'success',
            'result': results,
            'metadata': {
                'total_matches': len(results),
                'total_lessons': len(self._lessons),
            },
        }
