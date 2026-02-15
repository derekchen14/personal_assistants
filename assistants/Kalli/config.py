"""Config loader: merge shared defaults + domain YAML, validate, freeze.

Produces a read-only config object consumed by every module and component.
Section-level override: if the domain YAML defines a top-level section,
it fully replaces the shared default for that section.
"""

from __future__ import annotations

import copy
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml

_ROOT = Path(__file__).resolve().parent
_SHARED = _ROOT.parent.parent / 'shared' / 'shared_defaults.yaml'
_DOMAIN = _ROOT / 'schemas' / 'onboarding.yaml'

# Sections that must exist in the merged config
_REQUIRED_SECTIONS = frozenset({
    'environment', 'models', 'persona', 'guardrails', 'session',
    'memory', 'resilience', 'context_window', 'logging', 'display',
    'thresholds', 'response_constraints', 'human_in_the_loop',
})


def _deep_freeze(obj: Any) -> Any:
    """Recursively convert dicts to MappingProxyType and lists to tuples."""
    if isinstance(obj, dict):
        return MappingProxyType({k: _deep_freeze(v) for k, v in obj.items()})
    if isinstance(obj, list):
        return tuple(_deep_freeze(item) for item in obj)
    return obj


def _load_yaml(path: Path) -> dict:
    """Load a YAML file and return its contents as a dict."""
    with open(path, encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def _merge_configs(shared: dict, domain: dict) -> dict:
    """Merge shared defaults with domain overrides (section-level replacement)."""
    merged = copy.deepcopy(shared)
    for key, value in domain.items():
        # Section-level full replacement
        merged[key] = copy.deepcopy(value)
    return merged


def _validate(config: dict) -> None:
    """Validate the merged config has all required sections."""
    missing = _REQUIRED_SECTIONS - set(config.keys())
    if missing:
        raise ValueError(f'Missing required config sections: {sorted(missing)}')

    # Validate persona has required fields
    persona = config.get('persona', {})
    for field in ('name', 'tone', 'response_style'):
        if field not in persona:
            raise ValueError(f'persona.{field} is required')

    # Validate models has a default entry
    models = config.get('models', {})
    if 'default' not in models:
        raise ValueError('models.default is required')


def load_config() -> MappingProxyType:
    """Load, merge, validate, and freeze the config.

    Returns a deeply-frozen MappingProxyType. Raises ValueError if
    validation fails (agent should refuse to start).
    """
    shared = _load_yaml(_SHARED)
    domain = _load_yaml(_DOMAIN)
    merged = _merge_configs(shared, domain)
    _validate(merged)
    return _deep_freeze(merged)
