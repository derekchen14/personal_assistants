from __future__ import annotations

import copy
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml

_ROOT = Path(__file__).resolve().parent
_SHARED = _ROOT.parent.parent / 'shared' / 'shared_defaults.yaml'
_DOMAIN = _ROOT / 'schemas' / 'blogger.yaml'

_REQUIRED_SECTIONS = frozenset({
    'environment', 'models', 'persona', 'guardrails', 'session',
    'memory', 'resilience', 'context_window', 'logging', 'display',
    'thresholds', 'response_constraints', 'human_in_the_loop',
})

_CAPABILITY_KEYS = frozenset({
    'accesses_private_data', 'receives_untrusted_input', 'communicates_externally',
})


def _deep_freeze(obj: Any) -> Any:
    if isinstance(obj, dict):
        return MappingProxyType({k: _deep_freeze(v) for k, v in obj.items()})
    if isinstance(obj, list):
        return tuple(_deep_freeze(item) for item in obj)
    return obj


def _load_yaml(path: Path) -> dict:
    with open(path, encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def _merge_configs(shared: dict, domain: dict) -> dict:
    merged = copy.deepcopy(shared)
    for key, value in domain.items():
        merged[key] = copy.deepcopy(value)
    return merged


def _resolve_tool_schema(schema_ref: str, root: Path) -> dict:
    schema_path = root / schema_ref
    if schema_path.exists():
        return json.loads(schema_path.read_text(encoding='utf-8'))
    return {'type': 'object', 'properties': {}}


def _resolve_tools(tools_raw: dict, root: Path) -> dict:
    resolved = {}
    for tool_id, tool_def in tools_raw.items():
        entry = copy.deepcopy(tool_def)

        if isinstance(entry.get('input_schema'), str):
            entry['input_schema'] = _resolve_tool_schema(entry['input_schema'], root)

        caps = {}
        for key in _CAPABILITY_KEYS:
            if key in entry:
                caps[key] = entry.pop(key)
        entry['capabilities'] = caps

        resolved[tool_id] = entry
    return resolved


def _validate(config: dict) -> None:
    missing = _REQUIRED_SECTIONS - set(config.keys())
    if missing:
        raise ValueError(f'Missing required config sections: {sorted(missing)}')

    persona = config.get('persona', {})
    for field in ('name', 'tone', 'response_style'):
        if field not in persona:
            raise ValueError(f'persona.{field} is required')

    models = config.get('models', {})
    if 'default' not in models:
        raise ValueError('models.default is required')


def load_config(overrides: dict | None = None) -> MappingProxyType:
    shared = _load_yaml(_SHARED)
    domain = _load_yaml(_DOMAIN)
    merged = _merge_configs(shared, domain)
    if overrides:
        merged.update(overrides)

    if 'tools' in merged and isinstance(merged['tools'], dict):
        merged['tools'] = _resolve_tools(merged['tools'], _ROOT)

    _validate(merged)
    return _deep_freeze(merged)
