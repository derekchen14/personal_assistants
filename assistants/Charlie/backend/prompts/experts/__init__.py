"""Per-intent flow-detection prompt registry.

Each `<intent>_flows.py` exports a module-level `PROMPTS: dict[str, dict[str, str]]`
keyed by intent name (exactly one entry per module). Each entry has three
authored fields:
  - 'instructions'  markdown body for `## Instructions`
  - 'rules'         markdown body for `## Rules` (may be empty; builder
                    falls back to the shared PRECEDENCE_NOTE)
  - 'examples'      XML-tagged `<positive_example>` / `<edge_case>` blocks

The `## Background` section is shared across all intents (see
`backend/prompts/for_experts.py:BACKGROUND_STATIC`) — intent modules do not
author background."""

from __future__ import annotations

from backend.prompts.experts import (
    research_flows, draft_flows, revise_flows, publish_flows,
    converse_flows, plan_flows,
)

_MODULES = (research_flows, draft_flows, revise_flows, publish_flows,
            converse_flows, plan_flows)

PROMPTS: dict[str, dict[str, str]] = {}
for _mod in _MODULES:
    PROMPTS.update(_mod.PROMPTS)


def get_prompt(intent:str) -> dict[str, str]:
    return PROMPTS[intent]
