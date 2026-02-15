"""Service classes for Kalli's tools.

Each tool is a method on a service class. All methods return structured
envelopes: {'status': 'success'|'error', 'result': ..., 'metadata': ...}
"""

import json
import os
from pathlib import Path


SPECS_DIR = Path(__file__).resolve().parents[4] / '_specs'


class SpecService:
    """Reads spec files from the _specs/ directory."""

    def __init__(self, specs_dir: Path = SPECS_DIR):
        self.specs_dir = specs_dir
        self._index = self._build_index()

    def _build_index(self) -> dict[str, Path]:
        """Build a mapping of spec names to file paths."""
        index = {}
        for md_file in self.specs_dir.rglob('*.md'):
            name = md_file.stem
            # Prefer shorter paths (top-level over nested)
            if name not in index or len(md_file.parts) < len(index[name].parts):
                index[name] = md_file
        return index

    def read(self, spec_name: str, section: str | None = None) -> dict:
        """tool_id: spec_read"""
        path = self._index.get(spec_name)
        if not path or not path.exists():
            return {
                'status': 'error',
                'error_category': 'not_found',
                'message': f"Spec '{spec_name}' not found",
                'retryable': False,
                'metadata': {'tool_id': 'spec_read', 'attempt': 1},
            }
        content = path.read_text(encoding='utf-8')
        if section:
            content = self._extract_section(content, section)
            if content is None:
                return {
                    'status': 'error',
                    'error_category': 'not_found',
                    'message': f"Section '{section}' not found in '{spec_name}'",
                    'retryable': False,
                    'metadata': {'tool_id': 'spec_read', 'attempt': 1},
                }
        return {
            'status': 'success',
            'result': {
                'content': content,
                'spec_name': spec_name,
                'section': section,
            },
            'metadata': {
                'source': str(path.relative_to(self.specs_dir)),
                'char_count': len(content),
            },
        }

    def _extract_section(self, content: str, heading: str) -> str | None:
        """Extract content under a markdown heading."""
        lines = content.split('\n')
        capturing = False
        result = []
        target_level = None
        for line in lines:
            if line.startswith('#'):
                level = len(line) - len(line.lstrip('#'))
                title = line.lstrip('#').strip()
                if title.lower() == heading.lower():
                    capturing = True
                    target_level = level
                    result.append(line)
                    continue
                elif capturing and level <= target_level:
                    break
            if capturing:
                result.append(line)
        return '\n'.join(result) if result else None


class ConfigService:
    """Manages the partially-filled assistant config being built."""

    def __init__(self, db_conn=None):
        self.db = db_conn
        self._config: dict = {}

    def read(self, section: str | None = None) -> dict:
        """tool_id: config_read"""
        if section:
            data = self._config.get(section)
            if data is None:
                return {
                    'status': 'error',
                    'error_category': 'not_found',
                    'message': f"Config section '{section}' not yet defined",
                    'retryable': False,
                    'metadata': {'tool_id': 'config_read', 'attempt': 1},
                }
            return {
                'status': 'success',
                'result': {'config': {section: data}, 'section': section},
                'metadata': {'sections_defined': list(self._config.keys())},
            }
        return {
            'status': 'success',
            'result': {'config': self._config, 'section': None},
            'metadata': {'sections_defined': list(self._config.keys())},
        }

    def write(self, section: str, data: dict,
              merge: bool = True) -> dict:
        """tool_id: config_write"""
        if merge and section in self._config:
            self._config[section].update(data)
        else:
            self._config[section] = data
        return {
            'status': 'success',
            'result': {
                'section': section,
                'updated_fields': list(data.keys()),
            },
            'metadata': {'sections_defined': list(self._config.keys())},
        }


class GeneratorService:
    """Generates domain files (ontology.py, YAML) from config state."""

    def __init__(self, config_service: ConfigService):
        self.config_service = config_service

    def ontology(self, target_dir: str | None = None,
                 dry_run: bool = False) -> dict:
        """tool_id: ontology_generate"""
        config = self.config_service._config
        content = self._render_ontology(config)
        if not dry_run and target_dir:
            path = Path(target_dir) / 'ontology.py'
            path.write_text(content, encoding='utf-8')
        return {
            'status': 'success',
            'result': {
                'content': content,
                'file_path': str(target_dir) + '/ontology.py' if target_dir else None,
            },
            'metadata': {'dry_run': dry_run, 'char_count': len(content)},
        }

    def yaml(self, target_dir: str | None = None,
             dry_run: bool = False) -> dict:
        """tool_id: yaml_generate"""
        config = self.config_service._config
        content = self._render_yaml(config)
        domain = config.get('scope', {}).get('name', 'domain').lower()
        if not dry_run and target_dir:
            path = Path(target_dir) / f'{domain}.yaml'
            path.write_text(content, encoding='utf-8')
        return {
            'status': 'success',
            'result': {
                'content': content,
                'file_path': f'{target_dir}/{domain}.yaml' if target_dir else None,
            },
            'metadata': {'dry_run': dry_run, 'char_count': len(content)},
        }

    def _render_ontology(self, config: dict) -> str:
        """Generate ontology.py source from config."""
        intents = config.get('intents', {})
        intent_lines = []
        for name, desc in intents.items():
            intent_lines.append(
                f"    {name.upper()} = '{name}'"
                f"       # {desc.get('abstract_slot', '')}: {desc.get('description', '')}"
            )
        return (
            "from enum import Enum\n\n\n"
            "class Intent(str, Enum):\n"
            "    PLAN = 'Plan'\n"
            "    CONVERSE = 'Converse'\n"
            "    INTERNAL = 'Internal'\n"
            + '\n'.join(f'    {line}' for line in intent_lines) + '\n'
        )

    def _render_yaml(self, config: dict) -> str:
        """Generate domain YAML from config."""
        import yaml
        output = {}
        if 'persona' in config:
            output['persona'] = config['persona']
        if 'guardrails' in config:
            output['guardrails'] = config['guardrails']
        if 'entities' in config:
            output['key_entities'] = config['entities']
        return yaml.dump(output, default_flow_style=False, sort_keys=False)


class CodeService:
    """Executes Python code via exec()."""

    def execute(self, code: str, timeout_ms: int = 30000) -> dict:
        """tool_id: python_execute"""
        import io
        import contextlib
        try:
            stdout = io.StringIO()
            namespace = {}
            with contextlib.redirect_stdout(stdout):
                exec(code, namespace)
            output = stdout.getvalue()
            return_value = namespace.get('result', None)
            return {
                'status': 'success',
                'result': {'output': output, 'return_value': return_value},
                'metadata': {'tool_id': 'python_execute'},
            }
        except Exception as e:
            return {
                'status': 'error',
                'error_category': 'server_error',
                'message': f'{type(e).__name__}: {e}',
                'retryable': False,
                'metadata': {'tool_id': 'python_execute', 'attempt': 1},
            }


class LessonService:
    """Stores and searches lessons/patterns in the database."""

    def __init__(self, db_conn=None):
        self.db = db_conn
        self._lessons: list[dict] = []
        self._next_id = 1

    def store(self, content: str, category: str | None = None,
              tags: list[str] | None = None) -> dict:
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

    def search(self, query: str, category: str | None = None,
               limit: int = 10) -> dict:
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
