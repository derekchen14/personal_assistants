SLOT_FILLING_PREAMBLE = (
    'Extract slot values from the user utterance and conversation context.\n\n'
    'For each slot in the flow schema:\n'
    '1. Check if the value is explicitly stated in the current utterance\n'
    '2. Check if it can be inferred from recent conversation history\n'
    '3. Mark as null if not found\n\n'
    'Only extract values you are confident about. Do not guess or fabricate.\n\n'
    '### Slot Priorities\n'
    '- **required**: Must be filled for the flow to proceed. '
    'If the value cannot be found, add the slot name to "missing".\n'
    '- **elective**: At least one elective slot must be filled for the flow to proceed. '
    'Extract if stated or clearly implied. Do NOT add to "missing" if absent.\n'
    '- **optional**: Low priority — only extract if explicitly stated. '
    'Never add to "missing".'
)

SLOT_TYPE_GUIDES = {
    'SourceSlot': (
        '### SourceSlot\n'
        'References existing posts, sections, notes, or channels. Returns a dict '
        '(or list of dicts for multiple entities) with keys: post, sec, snip, chl, ver.\n'
        '- "post": the post title. Strip status words like "draft", "post", "article" from the end.\n'
        '- "sec": section within the post (e.g. "introduction", "conclusion").\n'
        '- "snip": a shorter snippet (tweet, comment).\n'
        '- "chl": channel/platform (only when the entity IS a channel).\n'
        '- "ver": boolean, true if user references a specific version.\n'
        'Omit keys that are empty. At minimum include "post".\n'
        'When the user says "my X post" or "the X draft", extract X as the post title.'
    ),
    'TargetSlot': (
        '### TargetSlot\n'
        'New entities being created. Returns a dict with keys: post, sec, snip, chl, ver.\n'
        '- "post": the new post title.\n'
        '- "sec": a new section name.\n'
        'Omit keys that are empty.'
    ),
    'RemovalSlot': (
        '### RemovalSlot\n'
        'Content to remove from the document. Return a description of what to remove '
        'as a string (e.g. "the anecdote about Slack", "the second paragraph").'
    ),
    'FreeTextSlot': (
        '### FreeTextSlot\n'
        'Open-ended text. Extract the relevant free-form content from the utterance.'
    ),
    'ChecklistSlot': (
        '### ChecklistSlot\n'
        'An ordered list of items. Each item has keys: '
        'name (short title), description (detail, often empty), checked (always false).\n'
        'When the user lists section names, topics to cover, or headings, those go here — '
        'NOT into topic or instructions.'
    ),
    'ProposalSlot': (
        '### ProposalSlot\n'
        'Selectable options for the user to choose from. '
        'Typically agent-generated — not user-filled during extraction.'
    ),
    'LevelSlot': (
        '### LevelSlot\n'
        'A numeric value representing a count or threshold. Extract the number directly.'
    ),
    'PositionSlot': (
        '### PositionSlot\n'
        'A non-negative integer indicating position in a sequence or a count.'
    ),
    'ProbabilitySlot': (
        '### ProbabilitySlot\n'
        'A numeric value between 0 and 1. Convert percentages: "40%%" → 0.4, "above 0.3" → 0.3.'
    ),
    'ScoreSlot': (
        '### ScoreSlot\n'
        'A numeric value for ranking, filtering, or comparison. Extract the number directly.'
    ),
    'CategorySlot': (
        '### CategorySlot\n'
        'Choose one from a predefined list. The user may use synonyms or related terms. '
        'Map to the closest valid option '
        '(e.g. "laid back" → "casual", "professional" → "formal"). '
        'Return null only if no option is a reasonable match.'
    ),
    'ExactSlot': (
        '### ExactSlot\n'
        'A specific term or phrase. For title slots, distill the core topic into a '
        'short Proper Case title (e.g. "write about how transformers work" → '
        '"How Transformers Work"). For other ExactSlots, use the user\'s phrasing verbatim.'
    ),
    'DictionarySlot': (
        '### DictionarySlot\n'
        'Key-value pairs. Parse instructions into structured pairs '
        '(e.g. "normalize headings, use h2" → {{"headings": "h2", "spacing": "normalize"}}).'
    ),
    'RangeSlot': (
        '### RangeSlot\n'
        'A time or value range. Return the raw date/time expression as a string '
        '(e.g. "Friday 8am EST", "next Monday morning", "March 20th"). '
        'Do not attempt to parse or reformat.'
    ),
    'ChannelSlot': (
        '### ChannelSlot\n'
        'A publishing destination. Return the channel name as a string '
        '(e.g. "Substack", "Medium", "Twitter/X", "LinkedIn", "blog").'
    ),
    'ImageSlot': (
        '### ImageSlot\n'
        'An image reference with type (hero, diagram, photo) and description.'
    ),
}


def _build_type_guides(slot_types:set) -> str:
    guides = [SLOT_TYPE_GUIDES[st] for st in slot_types if st in SLOT_TYPE_GUIDES]
    return '\n\n'.join(guides)

SLOT_FILLING_OUTPUT_SHAPE = (
    '```json\n'
    '{{\n'
    '  "slots": {{"<slot_name>": "<value_or_null>", ...}},\n'
    '  "missing": ["<slot_names_still_needed>"]\n'
    '}}\n'
    '```'
)

from backend.prompts.nlu import get_exemplars, get_instructions


def build_slot_filling_prompt(flow_name:str, slot_schema:str, convo_history:str, slot_types:set=None) -> str:
    exemplars = get_exemplars(flow_name)
    flow_context = get_instructions(flow_name)
    type_guides = _build_type_guides(slot_types) if slot_types else ''
    parts = [
        f'## Flow: {flow_name}\n',
        f'## Slot Schema\n\n{slot_schema}\n',
        f'## Flow Context\n\n{flow_context}\n' if flow_context else '',
        f'## Instructions\n\n{SLOT_FILLING_PREAMBLE}\n',
        f'## Slot Type Reference\n\n{type_guides}\n' if type_guides else '',
        f'## Output Format\n\n{SLOT_FILLING_OUTPUT_SHAPE}\n',
        f'## Examples\n{exemplars}\n' if exemplars else '',
        f'_Conversation History_\n{convo_history}\n' if convo_history else '',
        '_Output_',
    ]
    return '\n'.join(p for p in parts if p)
