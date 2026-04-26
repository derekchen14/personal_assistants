"""Per-flow slot-filling prompt registry.

Each `<intent>_slots.py` exports a module-level `PROMPTS: dict[str, dict[str, str]]`
keyed by flow_name. Each entry has four authored fields:
  - 'instructions'  markdown body for `## Instructions`. By convention the first
                     paragraph is a per-flow intro (e.g. "The Brainstorm Flow is
                     called when…"); the rest is per-slot extraction guidance.
  - 'rules'         markdown body for `## Rules`
  - 'slots'         markdown body for `## {Flow} Slots` (per-slot `### name (priority)`
                     blocks; empty string triggers procedural rendering from `flow.slots`)
  - 'examples'      XML-tagged `<positive_example>` / `<edge_case>` blocks

The `## Background` section is shared across all flows (see
`backend/prompts/for_nlu.py:BACKGROUND_STATIC`) — flows do not author background."""

from __future__ import annotations

from backend.prompts.nlu import (
    research_slots, draft_slots, revise_slots, publish_slots,
    converse_slots, plan_slots, internal_slots,
)

_MODULES = (research_slots, draft_slots, revise_slots, publish_slots,
            converse_slots, plan_slots, internal_slots)

PROMPTS: dict[str, dict[str, str]] = {}
for _mod in _MODULES:
    PROMPTS.update(_mod.PROMPTS)


def get_prompt(flow_name:str) -> dict[str, str]:
    return PROMPTS[flow_name]
