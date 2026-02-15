from __future__ import annotations

import copy
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


def load_config() -> MappingProxyType:
    shared = _load_yaml(_SHARED)
    domain = _load_yaml(_DOMAIN)
    merged = _merge_configs(shared, domain)
    _validate(merged)
    return _deep_freeze(merged)
