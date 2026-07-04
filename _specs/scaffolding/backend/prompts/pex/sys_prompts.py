"""Per-intent Background blocks for the PEX system prompt.

Layer 1 of the three-layer prompt architecture. `build_skill_system`
concatenates the universal persona (from `prompts/general.py`) with the
per-intent Background here, the universal `## Handling Ambiguity and Errors`
table, and finally the skill body from `pex/skills/<flow>.md`.

PROMPTS is keyed by intent name. Domain-specific intents add their own keys;
the three universal intents (Plan, Converse, Internal) ship with defaults
the domain can override."""


PROMPTS:dict[str, str] = {
    'Plan': (
        '## Background\n\n'
        'You are decomposing a complex user request into sub-flows. Your job is to '
        'pick the smallest set of flows that achieves the goal, in the right order, '
        'with verification points along the way.'
    ),
    'Converse': (
        '## Background\n\n'
        'You are handling a conversational turn — chat, FAQ, accept/decline, '
        'preference toggle, undo. Stay grounded in the conversation; do not start '
        'new domain work.'
    ),
    'Internal': (
        '## Background\n\n'
        'You are running a system housekeeping flow — memory recall, scratchpad '
        'recap, or business-context retrieval. Findings go to the scratchpad with '
        'the structured fields; the user-facing flow consumes them on the next '
        'turn.'
    ),
    # Domain-specific: add per-intent Background blocks for the four
    # domain-specific intents the domain defines.
}


def get(intent:str) -> str:
    return PROMPTS.get(intent, '')
