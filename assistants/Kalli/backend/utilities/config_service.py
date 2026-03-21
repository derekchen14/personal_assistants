from __future__ import annotations

from pathlib import Path

from backend.utilities.services import ToolService


class ConfigService:
    """Manages the partially-filled assistant config being built."""

    def __init__(self, db_conn=None):
        self.db = db_conn
        self._config: dict = {}

    def read(self, section:str|None=None) -> dict:
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

    def write(self, section:str, data:dict,
              merge:bool=True) -> dict:
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

    def __init__(self, config_service:ConfigService):
        self.config_service = config_service

    def ontology(self, target_dir:str|None=None,
                 dry_run:bool=False) -> dict:
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

    def yaml(self, target_dir:str|None=None,
             dry_run:bool=False) -> dict:
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

    def _render_ontology(self, config:dict) -> str:
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

    def _render_yaml(self, config:dict) -> str:
        import yaml
        output = {}
        if 'persona' in config:
            output['persona'] = config['persona']
        if 'guardrails' in config:
            output['guardrails'] = config['guardrails']
        if 'entities' in config:
            output['key_entities'] = config['entities']
        return yaml.dump(output, default_flow_style=False, sort_keys=False)
