"""Static lints on the artifacts that wire the system together.

Replaces and consolidates three earlier files:
  - test_skill_frontmatter.py   — YAML frontmatter on skill .md files.
  - test_skill_tool_alignment.py — Few-shot tool calls match flow.tools.
  - test_nlu_contract.py         — replaced with offline schema rules (no LLM).

All checks are offline. No API keys required, no network, no LLM. Run:
    pytest utils/tests/test_artifacts.py
"""
from __future__ import annotations

import inspect
import json
import re
from pathlib import Path

import pytest
import yaml

from backend.components.flow_stack import flow_classes
from backend.components.flow_stack.slots import ExactSlot
from backend.components.prompt_engineer import PromptEngineer, _TASK_SUFFIXES
from backend.modules.nlu import (
    _intent_schema, _flow_detection_schema, _fill_slots_schema,
)
from backend.prompts import general
from backend.prompts.for_pex import build_skill_system
from backend.prompts.nlu import PROMPTS as _SLOT_FILL_PROMPTS


SKILL_DIR = Path(__file__).resolve().parents[2] / 'backend' / 'prompts' / 'pex' / 'skills'
TOOLS_YAML = Path(__file__).resolve().parents[2] / 'schemas' / 'tools.yaml'

# Skills invoked directly by the PEX orchestrator, not owned by a flow/sub-agent. Validated
# against the tool registry (their declared tools must be real) rather than a flow's tool list.
PEX_AGENT_SKILLS: set[str] = {'promote'}

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
    """Skill/flow pairs for few-shot linting; PEX-agent skills have no owning flow."""
    return [(skill, skill) for skill in _skill_files() if skill in flow_classes]


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
def test_skill_tools_match_flow(skill_name, yaml_tools):
    meta = PromptEngineer.load_skill_meta(skill_name)
    declared = list(meta.get('tools') or [])
    if skill_name in PEX_AGENT_SKILLS:
        # PEX-orchestrator skill (no owning flow): its declared tools must be registered.
        unknown = [tool for tool in declared
                   if tool not in yaml_tools and tool not in COMPONENT_TOOLS]
        assert not unknown, (
            f'{skill_name} (PEX-agent skill) declares unregistered tools {unknown!r}; '
            f'valid tools are defined in tools.yaml'
        )
        return
    assert skill_name in flow_classes, (
        f'{skill_name}.md has no owning flow in flow_classes — delete the orphan skill '
        f'or add it to PEX_AGENT_SKILLS'
    )
    flow = flow_classes[skill_name]()
    assert list(declared) == list(flow.tools), (
        f'{skill_name}.md tools={declared!r} != {skill_name}.tools={flow.tools!r}'
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
    referenced = _few_shot_tool_calls(body)  # empty when the skill has no Few-shot block → passes
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


def test_flow_detection_schema_valid():
    """Lint rules are flow-set-agnostic — one all-flows case covers every branch."""
    assert _lint_schema(_flow_detection_schema(list(flow_classes.keys()))) == []


# Representative flows spanning intent classes and slot-type combinations.
# The schema generator branches on slot type, not on flow identity, so a handful
# of flows exercising the diverse slot families is enough — running all 35 was overkill.
_SCHEMA_REPRESENTATIVES = ['outline', 'audit', 'release', 'compare', 'schedule']


@pytest.mark.parametrize('flow_name', _SCHEMA_REPRESENTATIVES)
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


# ── 4. Flow declaration invariants ───────────────────────────────────────
# Catch slot-name drift between flow.entity_slot, flow.slots dict keys,
# fill_slot_values reads, and the NLU prompt's hand-authored slot headings.
# Surfaced after a RemoveFlow crash where entity_slot defaulted to 'source'
# but the slot dict declared 'target' — the kind of bug that's invisible
# until the flow is actually exercised end-to-end.

@pytest.mark.parametrize('flow_name', sorted(flow_classes.keys()))
def test_entity_slot_is_a_declared_slot(flow_name):
    flow = flow_classes[flow_name]()
    if flow.parent_type == 'Internal':
        return  # Internal flows opt out of grounding by family — no entity required.
    assert flow.entity_slot in flow.slots, (
        f'{flow_name}: entity_slot={flow.entity_slot!r} but flow.slots keys are '
        f'{sorted(flow.slots.keys())!r}. Either set self.entity_slot in __init__ '
        f'or rename the slot dict key to match.'
    )


@pytest.mark.parametrize('flow_name', sorted(flow_classes.keys()))
def test_target_slot_is_not_an_exact_slot(flow_name):
    """Rule: the `'target'` dict key must never pair with `ExactSlot`. ExactSlot is
    shape-anonymous; `'target'` carries an entity-grounding role that needs structured
    payload (TargetSlot/RemovalSlot) or another shape-explicit class. Bare strings live
    in TargetSlot's `snip` field — same pattern cite uses for snippet-citation targets."""
    flow = flow_classes[flow_name]()
    if 'target' not in flow.slots:
        return
    slot = flow.slots['target']
    assert not isinstance(slot, ExactSlot), (
        f"{flow_name}: slots['target'] is ExactSlot. Use TargetSlot (with entity_part) for "
        f"bare-string targets, RemovalSlot for destructive targets, or DictionarySlot for "
        f"key-value writes. ExactSlot under 'target' is shape-anonymous and forbidden."
    )


_VALUES_PATTERNS = (
    re.compile(r"values\.get\(\s*['\"]([a-z_]+)['\"]"),    # values.get('x', ...)
    re.compile(r"values\[\s*['\"]([a-z_]+)['\"]\s*\]"),     # values['x']
    re.compile(r"['\"]([a-z_]+)['\"]\s+in\s+values"),       # 'x' in values
)


def _fill_slot_keys(src:str) -> set[str]:
    keys:set[str] = set()
    for pattern in _VALUES_PATTERNS:
        keys.update(pattern.findall(src))
    return keys


@pytest.mark.parametrize('flow_name', sorted(flow_classes.keys()))
def test_fill_slot_values_reads_declared_keys(flow_name):
    flow = flow_classes[flow_name]()
    src = inspect.getsource(flow.fill_slot_values)
    keys_read = _fill_slot_keys(src)
    declared = set(flow.slots.keys())
    bogus = keys_read - declared
    assert not bogus, (
        f'{flow_name}.fill_slot_values reads {sorted(bogus)!r} from `values`, '
        f'but declared slot keys are {sorted(declared)!r}. NLU output for those '
        f'keys will be silently dropped.'
    )


_HEADING_PATTERN = re.compile(r'^###\s+([a-z_]+)\s+\(', re.MULTILINE)


def _flows_with_authored_slots():
    """Flows whose NLU prompt hand-authors `slots:` markdown — the only ones drift can hit.
    Procedural-rendering flows generate headings from `flow.slots`, so drift is impossible
    by construction and there is nothing to assert."""
    return sorted(
        name for name, prompt in _SLOT_FILL_PROMPTS.items()
        if (prompt.get('slots') or '').strip()
    )


@pytest.mark.parametrize('flow_name', _flows_with_authored_slots())
def test_prompt_slot_headings_match_flow_slots(flow_name):
    """Each `### name (priority)` heading in the NLU slot-fill prompt must
    name a real slot AND every declared slot must have a heading. The auto-generated
    JSON schema is built from flow.slots.keys() so it can't drift, but the prompt's
    hand-authored prose can — silently confusing the LLM about which key to fill."""
    slots_md = _SLOT_FILL_PROMPTS[flow_name]['slots']
    flow = flow_classes[flow_name]()
    headings = set(_HEADING_PATTERN.findall(slots_md))
    declared = set(flow.slots.keys())
    bogus = headings - declared
    missing = declared - headings
    assert not bogus, (
        f'{flow_name} PROMPTS slot block declares headings {sorted(bogus)!r} '
        f'that are not in flow.slots ({sorted(declared)!r}). Rename the heading '
        f'or the slot dict key so they match.'
    )
    assert not missing, (
        f'{flow_name} PROMPTS slot block is missing headings for {sorted(missing)!r} '
        f'(declared in flow.slots but absent from the prose). Add `### {{name}} (priority)` '
        f'headings or switch to procedural rendering by setting slots="".'
    )


_FENCED_JSON = re.compile(r'```json\s*(\{.*?\})\s*```', re.DOTALL)


@pytest.mark.parametrize('flow_name', sorted(flow_classes.keys()))
def test_few_shot_example_keys_match_flow_slots(flow_name):
    """Top-level `slots` keys in fenced ```json``` blocks inside `examples` must be
    declared in `flow.slots`. Catches CANCEL_PROMPT-style drift where prose examples
    name a stale slot key while the schema (auto-generated) emits the canonical one."""
    # No registered slot-fill prompt or no examples → no example JSON to mismatch (passes).
    examples = (_SLOT_FILL_PROMPTS.get(flow_name) or {}).get('examples', '') or ''
    declared = set(flow_classes[flow_name]().slots.keys())
    bogus = set()
    for block in _FENCED_JSON.findall(examples):
        try:
            payload = json.loads(block)
        except json.JSONDecodeError:
            continue
        slots_obj = payload.get('slots') or {}
        if isinstance(slots_obj, dict):
            bogus |= (set(slots_obj.keys()) - declared)
    assert not bogus, (
        f'{flow_name} examples reference top-level slot keys {sorted(bogus)!r} that are not in '
        f'flow.slots ({sorted(declared)!r}). Update the example JSON to match the canonical keys.'
    )


# ── 5. Closing reminder (slot 7) ─────────────────────────────────────────
# The agentic reminder must end every assembled sub-agent system prompt, while
# the single-shot NLU prompts keep their JSON demands via _TASK_SUFFIXES.

@pytest.mark.parametrize('skill_prompt', ['skill body', None])
def test_skill_system_ends_with_reminder(skill_prompt):
    flow = flow_classes['outline']()
    system = build_skill_system('base', flow, skill_prompt)
    assert system.endswith(general.SLOT_7_REMINDER)


def test_json_reminder_deleted():
    assert not hasattr(general, 'JSON_REMINDER')


def test_reminder_is_agentic():
    assert 'valid JSON' not in general.SLOT_7_REMINDER
    assert 'valid JSON' in _TASK_SUFFIXES['classify_intent']
