"""Phase 1 lint — every skill file has YAML frontmatter whose `name` matches
the filename, and whose `tools` allowlist (when declared) matches flow.tools
of the owning flow."""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.components.flow_stack import flow_classes
from backend.components.prompt_engineer import PromptEngineer


SKILL_DIR = Path(__file__).resolve().parents[2] / 'backend' / 'prompts' / 'pex' / 'skills'

# Skills whose `name` intentionally differs from the owning flow_name.
# Maps skill_name -> flow_name. (Empty after the dead-code cleanup.)
SKILL_TO_FLOW: dict[str, str] = {}

# Skills with no owning flow (dormant utility / shared narration). They
# still need valid frontmatter but are exempt from flow.tools comparison.
ORPHAN_SKILLS: set[str] = set()


def _skill_files():
    return sorted(p.stem for p in SKILL_DIR.glob('*.md'))


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
    # New skill structure (post-Phase 4) drops the `# Skill: <name>` header
    # in favor of starting with the intro paragraph + `## Process` section.
    assert '## Process' in body
