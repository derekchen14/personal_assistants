"""Offline validation of NLU structured-output JSON schemas.

No live LLM calls. Encodes provider-specific rules we have empirical evidence
for and applies them recursively to every schema NLU hands to the Messages API.

Rules currently enforced:
  A. Anthropic rejects `minimum` / `maximum` (and exclusive variants) on `number`.
  B. Anthropic rejects `enum` combined with a list-valued `type` (use `anyOf`).
  C. Anthropic rejects `additionalProperties` set to a schema object — must be `false`.

Add a new rule here the moment a future provider-rejection bug is diagnosed,
so we never rediscover the same schema shape at live-API time.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_HUGO_ROOT = Path(__file__).resolve().parents[2]
if str(_HUGO_ROOT) not in sys.path:
    sys.path.insert(0, str(_HUGO_ROOT))

from backend.components.flow_stack import flow_classes
from backend.modules.nlu import (
    _intent_schema, _flow_detection_schema, _fill_slots_schema,
)


_BANNED_NUMBER_KEYS = ('minimum', 'maximum', 'exclusiveMinimum', 'exclusiveMaximum')


def _walk(node, path=''):
    """Yield (path, subschema) for every nested schema dict."""
    if not isinstance(node, dict):
        return
    yield path, node
    for key, val in node.items():
        if key == 'properties' and isinstance(val, dict):
            for prop, sub in val.items():
                yield from _walk(sub, f'{path}.properties.{prop}')
        elif key == 'items':
            yield from _walk(val, f'{path}.items')
        elif key == 'additionalProperties' and isinstance(val, dict):
            yield from _walk(val, f'{path}.additionalProperties')
        elif key in ('anyOf', 'oneOf', 'allOf') and isinstance(val, list):
            for idx, sub in enumerate(val):
                yield from _walk(sub, f'{path}.{key}[{idx}]')


def _lint(schema):
    """Return a list of (path, rule, message) violations."""
    violations = []
    for path, node in _walk(schema):
        if node.get('type') == 'number':
            for bad in _BANNED_NUMBER_KEYS:
                if bad in node:
                    violations.append((path, 'A', f'`{bad}` not supported on number type'))
        if 'enum' in node and isinstance(node.get('type'), list):
            violations.append((path, 'B', f'enum combined with list-valued type {node["type"]!r} — split via anyOf'))
        ap = node.get('additionalProperties')
        if isinstance(ap, dict):
            violations.append((path, 'C', '`additionalProperties` is a schema object; Anthropic requires `false`'))
    return violations


def test_intent_schema_valid():
    assert _lint(_intent_schema()) == []


@pytest.mark.parametrize('candidates', [
    ['chat'],
    ['outline', 'refine', 'create', 'compose'],
    list(flow_classes.keys()),
])
def test_flow_detection_schema_valid(candidates):
    assert _lint(_flow_detection_schema(candidates)) == []


@pytest.mark.parametrize('flow_name', sorted(flow_classes.keys()))
def test_fill_slots_schema_valid(flow_name):
    flow = flow_classes[flow_name]()
    violations = _lint(_fill_slots_schema(flow))
    assert violations == [], f'{flow_name}: {violations}'


# ── Self-tests: the linter must detect the bugs we just fixed ────────

def test_lint_detects_rule_A():
    bad = {'type': 'object', 'properties': {'n': {'type': 'number', 'minimum': 0}}}
    violations = _lint(bad)
    assert any(rule == 'A' for _, rule, _ in violations)


def test_lint_detects_rule_B():
    bad = {'type': 'object', 'properties': {
        'x': {'type': ['string', 'null'], 'enum': ['a', 'b', None]},
    }}
    violations = _lint(bad)
    assert any(rule == 'B' for _, rule, _ in violations)


def test_lint_detects_rule_C():
    bad = {'type': 'object', 'additionalProperties': {'type': 'string'}}
    violations = _lint(bad)
    assert any(rule == 'C' for _, rule, _ in violations)
