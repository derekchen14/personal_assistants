"""
Slot-filling prompt builder for Hugo NLU.

Hybrid structure: XML tags for top-level sections, Markdown inside tags for prose.
The per-flow content (instructions/rules/slots/examples) lives in backend/prompts/nlu/<intent>_slots.py.

  <role>...</role>
  <task>
    ## Background      — shared constant
    ## Instructions    — per-flow (first paragraph is the per-flow intro)
    ## Rules           — per-flow
  </task>
  <slot_schema>
    ## {Flow} Slots    — per-flow (entity slots already grounded are filtered out)
    ## Slot Reference
      ### Priorities   — shared boilerplate
      ### Slot Types   — filtered to slot types the flow uses
  </slot_schema>
  <example_scenarios>
    ...per-flow <positive_example>/<edge_case> blocks. Each carries
    `## Conversation History`, `## Input` (active post), and `## Output`.
  </example_scenarios>
  Reminder: reply with JSON only.
  <current_scenario>
    ## Conversation History
    ## Input            — `Active post: <title>` or `Active post: None`
  </current_scenario>

Output shape is `{"reasoning": "...", "slots": {name: value}}`, enforced by a JSON schema
from the provider. Use `null` for any slot the user did not specify — inside entity
dicts, set individual keys to `null` rather than omitting them.
"""

from backend.prompts.nlu import get_prompt


ROLE = (
    'You are operating as the slot-filling component of a blog-writing assistant (named Hugo). Extract slot values '
    'from the current user utterance as part of the fuller conversation history for the flow described below.'
)

BACKGROUND_STATIC = (
    '## Background\n\n'
    'An upstream component decided to route the current user turn to one of Hugo\'s **flows** — '
    'units of work that share a goal (drafting a post, releasing it, browsing notes, etc.). '
    'Every flow declares a schema of named **slots** that capture what the agent needs to act.\n'
    'Given the recent conversation history, slot-filling is responsible for finding values for each '
    'slot in the active flow. The shape of a value is set by the slot\'s type — e.g. `SourceSlot` '
    'returns `{post, sec, snip, chl}`; `CategorySlot` is choosing a single option from a finite set; '
    '`ChecklistSlot` returns a list of items.\n'
    'The purpose of slot-filling is to ground the conversation to the artifacts and ideas in the user\'s '
    'mind. Populated slots allow the policy to decide whether to act immediately, gather more info, or ask '
    'for clarification. Missing slots trigger clarification; missing electives may prompt defaults; filled '
    'slots feed into tool calls and response wording. Thus, a wrong fill is worse than a null — fabricating '
    'values you cannot justify causes downstream actions on the wrong data. NEVER make up values.\n\n'
    'Additional notes:\n'
    '  - **Key entities** are domain-specific: `post` (a blog article), `sec` (a section within a post), '
    '`snip` (a shorter snippet — tweet, comment), and `chl` (a publishing channel: Substack, Medium, '
    'Twitter/X, LinkedIn, blog); often used to for the "source" slot. \n'
    '  - **Unfilled slots**: Use `null` whenever a slot value is not present or not deducible. Inside '
    'entity dicts, set individual entity-values to `null` rather than omitting them when missing.\n'
    '  - **Precedence**: Flow-specific content in `## Instructions`, `## Rules`, and `## {Flow} Slots` '
    'overrides anything in `## Slot Reference`. When guidance conflicts, trust the flow-specific side.'
)

PRIORITIES_DOC = (
    '### Priorities\n\n'
    '- **required**: must be filled for the flow to proceed.\n'
    '- **elective**: at least one elective slot must be filled for the flow to proceed. Extract when stated '
    'or clearly implied; leave `null` if not.\n'
    '- **optional**: low priority — only populate when explicitly stated. Never infer an optional slot from weak signals.'
)

SLOT_TYPE_GUIDES = {
    'SourceSlot': (
        '#### SourceSlot\n'
        'References existing entities. Returns a dict (or list of dicts for multiple entities) with keys: '
        '`post`, `sec`, `snip`, `chl`.\n'
        '- `post`: the post title. Strip status words like "draft", "post", "article", "note" from the end.\n'
        '- `sec`: a section within the post (e.g. "introduction", "methods").\n'
        '- `snip`: a shorter snippet (tweet, comment, quote).\n'
        '- `chl`: a publishing channel — only when the entity itself IS a channel.\n'
        'Omit keys whose values would be empty. At minimum include `post`. When the user says "my X post" '
        'or "the X draft", extract X as the post title.'
    ),
    'TargetSlot': (
        '#### TargetSlot\n'
        'A new entity being created. Same dict shape as SourceSlot: `{post, sec, snip, chl}`. Populate only '
        'the keys relevant to the new entity (e.g. a new post title fills `post`; a new section fills `sec`).'
    ),
    'RemovalSlot': (
        '#### RemovalSlot\n'
        'Content to remove from the document. Describe what to remove as a short string (e.g. "the second '
        'paragraph", "the anecdote about Slack"). Same dict shape as SourceSlot for structured references.'
    ),
    'FreeTextSlot': (
        '#### FreeTextSlot\n'
        'Open-ended prose. Returns a list of one or more free-form strings extracted from the utterance. Use '
        'when the user gives interpretive feedback or multi-sentence guidance that should be carried verbatim.'
    ),
    'ChecklistSlot': (
        '#### ChecklistSlot\n'
        'An ordered list of discrete, actionable items. Returns a list where each item is either a short '
        'string or a dict `{"name": ..., "description": ..., "checked": false}`.\n'
        'Fill this slot when the user enumerates named headings, bulleted directives, or a sequence of '
        'steps. Do not fold enumerated items into prose slots in the same flow — ChecklistSlot is '
        'structured, prose slots are interpretive.'
    ),
    'ProposalSlot': (
        '#### ProposalSlot\n'
        'Selectable options for the user to choose from. Typically populated by the agent, not by NLU. '
        'Leave `null` unless the utterance clearly picks among agent-offered options.'
    ),
    'LevelSlot': (
        '#### LevelSlot\n'
        'A numeric threshold or count. Extract the integer or float directly.'
    ),
    'PositionSlot': (
        '#### PositionSlot\n'
        'A non-negative integer indicating a position in a sequence (e.g. "the 3rd section"). Zero and '
        'positive integers only.'
    ),
    'ProbabilitySlot': (
        '#### ProbabilitySlot\n'
        'A numeric value in the range [0, 1]. Convert percentages and inequalities: "40%" → 0.4, '
        '"above 0.3" → 0.3, "at least 95%" → 0.95.'
    ),
    'ScoreSlot': (
        '#### ScoreSlot\n'
        'A numeric value for ranking, filtering, or comparison. Fill only when the utterance expresses a '
        'threshold ("over X", "at least X", "under X"). Raw counts or descriptive numbers without '
        'comparison do not fill a ScoreSlot.'
    ),
    'CategorySlot': (
        '#### CategorySlot\n'
        'Choose one from a predefined list. Map synonyms to the closest valid option (e.g. "laid back" → '
        '"casual", "professional" → "formal"). Emit `null` when no option is a reasonable match.'
    ),
    'ExactSlot': (
        '#### ExactSlot\n'
        'A specific term or phrase. For title slots, distill the subject into a short Proper Case title '
        '(e.g. "write about how transformers work" → "How Transformers Work"). For non-title ExactSlots, '
        'preserve the user\'s phrasing verbatim (the exact words they typed).'
    ),
    'DictionarySlot': (
        '#### DictionarySlot\n'
        'Key-value pairs. Parse paired directives into a structured dict (e.g. "normalize headings, use '
        'h2" → `{"headings": "h2", "spacing": "normalize"}`).'
    ),
    'RangeSlot': (
        '#### RangeSlot\n'
        'A time or value range. Return the raw date/time expression as a string (e.g. "Friday 8am EST", '
        '"next Monday morning", "March 20th"). Do not attempt to parse or reformat.'
    ),
    'ChannelSlot': (
        '#### ChannelSlot\n'
        'A publishing destination. Always returns a list of channel name strings: `["Substack", ...]`. '
        'A single channel returns a one-item list (`["Substack"]`); multiple channels return multiple '
        'items; no channel mentioned returns an empty list `[]`. Common values: Substack, Medium, '
        'Twitter/X, LinkedIn, blog (the user\'s primary, MoreThanOneTurn). Map misspellings and '
        'implied references to the canonical channel name.'
    ),
    'ImageSlot': (
        '#### ImageSlot\n'
        'An image reference. Returns a dict with `image_type` (one of `hero`, `diagram`, `photo`) and a '
        'short description of the image.'
    ),
}

ENTITY_SLOT_TYPES = ('source', 'target', 'removal', 'channel')


def _build_type_guides(slot_types:set) -> str:
    guides = [SLOT_TYPE_GUIDES[st] for st in slot_types if st in SLOT_TYPE_GUIDES]
    return '\n\n'.join(guides)


def _procedural_slots_md(flow, skip_names:set) -> str:
    """Fallback when authored `slots` is empty — render one `### name (priority)` block per slot."""
    blocks = []
    for name, slot in flow.slots.items():
        if name in skip_names:
            continue
        slot_type = type(slot).__name__
        line = f'### {name} ({slot.priority})\n\nType: {slot_type}.'
        if hasattr(slot, 'options') and getattr(slot, 'options', None):
            line += f' Options: {list(slot.options)}.'
        if hasattr(slot, 'purpose') and slot.purpose:
            line += f' Purpose: {slot.purpose}.'
        blocks.append(line)
    return '\n\n'.join(blocks)


def _filter_slot_sections(slots_md:str, skip_names:set) -> str:
    """Drop `### <name> (...)` sub-sections from authored slots markdown."""
    if not skip_names:
        return slots_md
    out_lines, skipping = [], False
    for line in slots_md.splitlines():
        if line.startswith('### '):
            header = line[4:].strip()
            name = header.split()[0] if header else ''
            skipping = name in skip_names
            if skipping:
                continue
        if not skipping:
            out_lines.append(line)
    return '\n'.join(out_lines).strip()


def _render_input(active_post:dict|None) -> str:
    if active_post:
        return f"## Input\n\nActive post: **{active_post['title']}** (id: `{active_post['id']}`)"
    return '## Input\n\nActive post: None'


def build_slot_filling_prompt(flow_name:str, flow, convo_history:str,
                              active_post:dict=None, ent_needs_filling:set=None) -> str:
    prompt_fields = get_prompt(flow_name)
    instructions = prompt_fields['instructions'].strip()
    rules = prompt_fields['rules'].strip()
    slots_md = prompt_fields['slots'].strip()
    examples = prompt_fields['examples'].strip()

    slot_types = {type(slot).__name__ for slot in flow.slots.values()}
    type_guides = _build_type_guides(slot_types)

    skip_names = set()
    if ent_needs_filling is not None:
        for name, slot in flow.slots.items():
            if slot.slot_type in ENTITY_SLOT_TYPES and name not in ent_needs_filling:
                skip_names.add(name)
    if slots_md:
        slots_md = _filter_slot_sections(slots_md, skip_names)
    else:
        slots_md = _procedural_slots_md(flow, skip_names)

    flow_heading = f'{flow_name.title()} Slots'
    task_body = f'{BACKGROUND_STATIC}\n\n## Instructions\n\n{instructions}\n\n## Rules\n\n{rules}'
    slot_schema_body = (
        f'## {flow_heading}\n\n{slots_md}\n\n'
        f'## Slot Reference\n\n{PRIORITIES_DOC}\n\n### Slot Types\n\n{type_guides}'
    )

    convo_block = convo_history.strip() if convo_history else '(empty)'
    input_block = _render_input(active_post)
    current_scenario = f'## Conversation History\n\n{convo_block}\n\n{input_block}'

    parts = [
        f'<role>{ROLE}</role>',
        f'<task>\n{task_body}\n</task>',
        f'<slot_schema>\n{slot_schema_body}\n</slot_schema>',
        f'<example_scenarios>\n{examples}\n</example_scenarios>',
        f'<current_scenario>\n{current_scenario}\n</current_scenario>',
    ]
    return '\n\n'.join(parts)
