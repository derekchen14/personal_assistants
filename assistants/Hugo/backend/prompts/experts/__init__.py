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
    converse_flows,
)

_MODULES = (research_flows, draft_flows, revise_flows, publish_flows,
            converse_flows)

PROMPTS: dict[str, dict[str, str]] = {}
for _mod in _MODULES:
    PROMPTS.update(_mod.PROMPTS)


# ── Generic (intent-agnostic) flow prompt — used on the first pass when hint='' ──────
# One <positive_example> per flow-owning intent (find / outline / rework / release / chat), so an
# 18-way choice still sees every intent family represented.
GENERIC_FLOW_EXAMPLES = '''<positive_example>
## Conversation History

User: "find my posts about onboarding"
## Output

```json
{"reasoning": "Locating existing posts.", "flow_name": "find"}
```
</positive_example>

<positive_example>
## Conversation History

User: "outline a post about remote work"
## Output

```json
{"reasoning": "Generating an outline.", "flow_name": "outline"}
```
</positive_example>

<positive_example>
## Conversation History

User: "restructure the draft, the sections are out of order"
## Output

```json
{"reasoning": "Reworking the draft structure.", "flow_name": "rework"}
```
</positive_example>

<positive_example>
## Conversation History

User: "publish it to the blog"
## Output

```json
{"reasoning": "Releasing the post.", "flow_name": "release"}
```
</positive_example>

<positive_example>
## Conversation History

User: "hi there"
## Output

```json
{"reasoning": "Simple greeting.", "flow_name": "chat"}
```
</positive_example>'''

GENERIC_FLOW_PROMPT = {
    'instructions': ('Choose the single flow that best matches what the user wants across ALL '
                     'intents. The candidate list spans every flow; the detected flow fixes the '
                     'intent, so do not pre-commit to one intent family.'),
    'rules': '',                       # build_flow_prompt falls back to PRECEDENCE_NOTE
    'examples': GENERIC_FLOW_EXAMPLES,
}


def get_prompt(intent:str) -> dict[str, str]:
    return PROMPTS[intent] if intent else GENERIC_FLOW_PROMPT
