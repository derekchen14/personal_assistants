"""Phase 3 lint — Option C enforcement.

For every skill file that has a `## Few-shot` block, every tool call
pattern `<tool_name>(` mentioned there must appear in `flow.tools` of the
owning flow. And every tool in `flow.tools` must have an entry in
`schemas/tools.yaml`. Catches trajectory drift before it hits runtime.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from backend.components.flow_stack import flow_classes
from backend.components.prompt_engineer import PromptEngineer


SKILL_DIR = Path(__file__).resolve().parents[2] / 'backend' / 'prompts' / 'pex' / 'skills'
TOOLS_YAML = Path(__file__).resolve().parents[2] / 'schemas' / 'tools.yaml'

SKILL_TO_FLOW: dict[str, str] = {}
ORPHAN_SKILLS: set[str] = set()

# Component-level tools that skills may reference but that aren't in
# `flow.tools` (they live in PEX._component_tool_definitions instead).
# Must match the tools registered in pex.py::_component_tool_definitions.
COMPONENT_TOOLS = {
    'handle_ambiguity', 'coordinate_context', 'manage_memory',
    'call_flow_stack', 'execution_error', 'save_findings',
}


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


def _tool_call_names(body:str) -> set[str]:
    """Extract `name(` occurrences inside the Few-shot section only."""
    idx = body.lower().find('## few-shot')
    if idx == -1:
        return set()
    section = body[idx:]
    # Match Python-style identifiers immediately followed by `(` in the
    # skill's example code/prose.
    return set(re.findall(r'`([a-z][a-z0-9_]+)\(', section))


@pytest.fixture(scope='module')
def yaml_tools():
    with TOOLS_YAML.open() as fh:
        cfg = yaml.safe_load(fh)
    return set((cfg.get('tools') or {}).keys())


@pytest.mark.parametrize('skill_name,flow_name', _skill_flow_pairs())
def test_few_shot_tools_are_allowlisted(skill_name, flow_name):
    body = PromptEngineer.load_skill_template(skill_name)
    assert body is not None
    referenced = _tool_call_names(body)
    if not referenced:
        pytest.skip('no Few-shot tool calls referenced')
    flow_tools = set(flow_classes[flow_name]().tools)
    allowed = flow_tools | COMPONENT_TOOLS
    unknown = referenced - allowed
    assert not unknown, (
        f'{skill_name}.md references tools {sorted(unknown)!r} in its Few-shot '
        f'block that are NOT in flow.tools of {flow_name} '
        f'({sorted(flow_tools)!r}) or in component tools.'
    )


def test_flow_tools_are_registered(yaml_tools):
    bad = []
    for flow_name, cls in flow_classes.items():
        flow = cls()
        for tool_name in flow.tools:
            if tool_name not in yaml_tools:
                bad.append((flow_name, tool_name))
    assert not bad, (
        f'The following flow.tools entries have no schemas/tools.yaml '
        f'definition: {bad!r}'
    )
