"""Static lints on the artifacts that wire the system together.

Replaces and consolidates three earlier files:
  - test_skill_frontmatter.py   — YAML frontmatter on skill .md files.
  - test_skill_tool_alignment.py — Few-shot tool calls match flow.tools.
  - test_nlu_contract.py         — replaced with offline schema rules (no LLM).

All checks are offline. No API keys required, no network, no LLM. Run:
    pytest utils/tests/test_artifacts.py
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from backend.components.flow_stack import flow_classes
from backend.components.prompt_engineer import PromptEngineer
from backend.modules.nlu import (
    _intent_schema, _flow_detection_schema, _fill_slots_schema,
)


SKILL_DIR = Path(__file__).resolve().parents[2] / 'backend' / 'prompts' / 'pex' / 'skills'
TOOLS_YAML = Path(__file__).resolve().parents[2] / 'schemas' / 'tools.yaml'

# Skills whose `name` intentionally differs from the owning flow_name.
SKILL_TO_FLOW: dict[str, str] = {}

# Skills with no owning flow (dormant utility / shared narration). Still need
# valid frontmatter but are exempt from flow.tools comparison.
ORPHAN_SKILLS: set[str] = set()

# Component-level tools that skills may reference but that aren't in flow.tools
# (they live in PEX._component_tool_definitions). Must stay in sync with pex.py.
COMPONENT_TOOLS = {
    'handle_ambiguity', 'coordinate_context', 'manage_memory',
    'call_flow_stack', 'execution_error', 'save_findings',
}


# ── Helpers ──────────────────────────────────────────────────────────────

def _skill_files():
    return sorted(p.stem for p in SKILL_DIR.glob('*.md'))


def _skill_flow_pairs():
    pairs = []
    for path in sorted(SKILL_DIR.glob('*.md')):
        skill = path.stem
        if skill in ORPHAN_SKILLS:
            continue
        flow_name = SKILL_TO_FLOW.get(skill, skill)
        if flow_name not in flow_classes:
            continue
        pairs.append((skill, flow_name))
    return pairs


def _few_shot_tool_calls(body:str) -> set[str]:
    """Pull every `name(` token inside the skill's `## Few-shot` block."""
    idx = body.lower().find('## few-shot')
    if idx == -1:
        return set()
    return set(re.findall(r'`([a-z][a-z0-9_]+)\(', body[idx:]))


@pytest.fixture(scope='module')
def yaml_tools():
    with TOOLS_YAML.open() as fh:
        cfg = yaml.safe_load(fh)
    return set((cfg.get('tools') or {}).keys())


# ── 1. Skill frontmatter ─────────────────────────────────────────────────
# Every skill .md has YAML frontmatter; declared `tools:` must match flow.tools.

@pytest.mark.parametrize('skill_name', _skill_files())
def test_skill_tools_match_flow(skill_name):
    meta = PromptEngineer.load_skill_meta(skill_name)
    if skill_name in ORPHAN_SKILLS:
        pytest.skip(f'{skill_name} has no owning flow')
    flow_name = SKILL_TO_FLOW.get(skill_name, skill_name)
    if flow_name not in flow_classes:
        pytest.skip(f'{flow_name} not in flow_classes')
    declared = meta.get('tools') or []
    flow = flow_classes[flow_name]()
    assert list(declared) == list(flow.tools), (
        f'{skill_name}.md tools={declared!r} != {flow_name}.tools={flow.tools!r}'
    )


def test_loader_strips_frontmatter():
    body = PromptEngineer.load_skill_template('outline')
    assert body is not None
    assert not body.startswith('---'), 'frontmatter leaked into body'
    assert '## Process' in body


# ── 2. Few-shot tool alignment ───────────────────────────────────────────
# Every tool referenced in a `## Few-shot` block must be in flow.tools or be
# a component-level tool. Every tool in flow.tools must be defined in tools.yaml.

@pytest.mark.parametrize('skill_name,flow_name', _skill_flow_pairs())
def test_few_shot_tools_are_allowlisted(skill_name, flow_name):
    body = PromptEngineer.load_skill_template(skill_name)
    assert body is not None
    referenced = _few_shot_tool_calls(body)
    if not referenced:
        pytest.skip('no Few-shot tool calls referenced')
    flow_tools = set(flow_classes[flow_name]().tools)
    allowed = flow_tools | COMPONENT_TOOLS
    unknown = referenced - allowed
    assert not unknown, (
        f'{skill_name}.md references tools {sorted(unknown)!r} in its Few-shot block that are '
        f'NOT in flow.tools of {flow_name} ({sorted(flow_tools)!r}) or in component tools.'
    )


def test_flow_tools_are_registered(yaml_tools):
    bad = []
    for flow_name, cls in flow_classes.items():
        flow = cls()
        for tool_name in flow.tools:
            if tool_name not in yaml_tools:
                bad.append((flow_name, tool_name))
    assert not bad, (
        f'flow.tools entries with no schemas/tools.yaml definition: {bad!r}'
    )


# ── 3. NLU schema lint (offline) ─────────────────────────────────────────
# Encodes Anthropic structured-output rules empirically observed via API
# rejections. Add a new rule here the moment a future provider-rejection bug
# is diagnosed in dev so it never resurfaces at runtime.
#
# Rules currently enforced:
#   A. Anthropic rejects `minimum` / `maximum` (and exclusive variants) on `number`.
#   B. Anthropic rejects `enum` combined with a list-valued `type` (use `anyOf`).
#   C. Anthropic rejects `additionalProperties` set to a schema object — must be `false`.

_BANNED_NUMBER_KEYS = ('minimum', 'maximum', 'exclusiveMinimum', 'exclusiveMaximum')


def _walk_schema(node, path=''):
    """Yield (path, subschema) for every nested schema dict."""
    if not isinstance(node, dict):
        return
    yield path, node
    for key, val in node.items():
        if key == 'properties' and isinstance(val, dict):
            for prop, sub in val.items():
                yield from _walk_schema(sub, f'{path}.properties.{prop}')
        elif key == 'items':
            yield from _walk_schema(val, f'{path}.items')
        elif key == 'additionalProperties' and isinstance(val, dict):
            yield from _walk_schema(val, f'{path}.additionalProperties')
        elif key in ('anyOf', 'oneOf', 'allOf') and isinstance(val, list):
            for idx, sub in enumerate(val):
                yield from _walk_schema(sub, f'{path}.{key}[{idx}]')


def _lint_schema(schema):
    """Return a list of (path, rule, message) violations."""
    violations = []
    for path, node in _walk_schema(schema):
        if node.get('type') == 'number':
            for bad in _BANNED_NUMBER_KEYS:
                if bad in node:
                    violations.append((path, 'A', f'`{bad}` not supported on number type'))
        if 'enum' in node and isinstance(node.get('type'), list):
            violations.append((path, 'B',
                f'enum combined with list-valued type {node["type"]!r} — split via anyOf'))
        ap = node.get('additionalProperties')
        if isinstance(ap, dict):
            violations.append((path, 'C',
                '`additionalProperties` is a schema object; Anthropic requires `false`'))
    return violations


def test_intent_schema_valid():
    assert _lint_schema(_intent_schema()) == []


@pytest.mark.parametrize('candidates', [
    ['chat'],
    ['outline', 'refine', 'create', 'compose'],
    list(flow_classes.keys()),
])
def test_flow_detection_schema_valid(candidates):
    assert _lint_schema(_flow_detection_schema(candidates)) == []


@pytest.mark.parametrize('flow_name', sorted(flow_classes.keys()))
def test_fill_slots_schema_valid(flow_name):
    flow = flow_classes[flow_name]()
    violations = _lint_schema(_fill_slots_schema(flow))
    assert violations == [], f'{flow_name}: {violations}'


# Self-tests: the linter must detect each rule it claims to enforce.

def test_lint_detects_rule_A():
    bad = {'type': 'object', 'properties': {'n': {'type': 'number', 'minimum': 0}}}
    assert any(rule == 'A' for _, rule, _ in _lint_schema(bad))


def test_lint_detects_rule_B():
    bad = {'type': 'object', 'properties': {
        'x': {'type': ['string', 'null'], 'enum': ['a', 'b', None]},
    }}
    assert any(rule == 'B' for _, rule, _ in _lint_schema(bad))


def test_lint_detects_rule_C():
    bad = {'type': 'object', 'additionalProperties': {'type': 'string'}}
    assert any(rule == 'C' for _, rule, _ in _lint_schema(bad))
