"""
Flow-detection prompt builders for Hugo NLU.

Two stages — intent classification (hop 1) and flow detection (hop 2) — share
the same hybrid XML + Markdown shell used by slot-filling
(`backend/prompts/for_nlu.py`):

  <role>...</role>
  <task>
    ## Background      — shared constant
    ## Instructions    — per-stage (intent) or per-intent (flow)
    ## Rules           — per-stage (intent) or per-intent (flow)
  </task>
  <flow_catalog>                  (flow stage only)
    ## Candidate Flows — flat `### name (dax)` list; in-intent + edge flows
  </flow_catalog>
  <example_scenarios>
    <positive_example>...</positive_example>
    <edge_case>...</edge_case>
  </example_scenarios>
  Reminder: reply with JSON only.
  <current_scenario>
    ## Conversation History
    ## Input           — `Active post: ...` + (flow stage) `Predicted intent: ...`
  </current_scenario>

Output shapes are enforced by provider-side JSON schemas in
`backend/modules/nlu.py`:
  - intent:  {"reasoning": str, "intent": one-of-6}
  - flow:    {"reasoning": str, "flow_name": one-of-candidates, "confidence": float}"""

from backend.prompts.experts import get_prompt


ROLE_INTENT = (
    'You are operating as the intent classifier component of a blog-writing assistant (named Hugo). '
    'Route the current user utterance to exactly one of Hugo\'s user-facing intents.'
)

ROLE_FLOW = (
    'You are operating as the flow-detection component of a blog-writing assistant (named Hugo). '
    'Given the predicted intent, choose the specific flow that best captures what the user wants.'
)

BACKGROUND_STATIC = (
    '## Background\n\n'
    'Hugo is a blog-writing assistant. Work is organized into **flows** — units of work that share a '
    'goal (drafting a post, releasing it, browsing notes, etc.). Flows group under one of six user-facing '
    '**intents**:\n'
    '- **Research**: browse topics, search posts, view drafts, check channels, explain concepts, '
    'find related content, compare posts.\n'
    '- **Draft**: brainstorm, generate outlines, write or expand content, create new posts, '
    'add/refine sections.\n'
    '- **Revise**: deep revision, polish sections, adjust tone, check consistency, format for '
    'publication, accept/reject changes, compare drafts.\n'
    '- **Publish**: publish, cross-post, schedule, preview, promote, cancel publication.\n'
    '- **Converse**: greetings, next-step suggestions, feedback, preferences, style, '
    'endorse/dismiss suggestions.\n'
    '- **Plan**: plan a post, plan revision, content calendar, research plan, series planning.\n\n'
    'A seventh intent — **Internal** — is system-only. Never predict Internal.\n\n'
    'Routing to the wrong intent or flow causes the agent to act on the wrong data or ask the wrong '
    'clarifying question. Reason first: name the key signals that separate the top candidates, then '
    'commit. Output is a single JSON object whose shape is enforced by a provider-side schema. The '
    '`reasoning` field comes first so subsequent fields are conditioned on it — keep it under 100 '
    'tokens. Do not paraphrase flow descriptions or enumerate every candidate.'
)

PRECEDENCE_NOTE = (
    'When flow-specific guidance in `## Rules` or `## Candidate Flows` conflicts with the general '
    'framing in `## Background`, trust the flow-specific side.'
)

# ── Intent stage: module-level (no per-intent registry) ──────────────────

INTENT_INSTRUCTIONS = (
    'Classify the user utterance into exactly one intent from the six user-facing intents listed in '
    '## Background. Think step-by-step about the user\'s goal, then commit.'
)

INTENT_RULES = (
    f'{PRECEDENCE_NOTE}'
)

INTENT_EXAMPLES = '''<positive_example>
## Conversation History

User: "I want to write about AI trends"
## Output

```json
{"reasoning": "User wants to create new content about a topic.", "intent": "Draft"}
```
</positive_example>

<positive_example>
## Conversation History

User: "show me my drafts"
## Output

```json
{"reasoning": "User wants to see current draft status.", "intent": "Research"}
```
</positive_example>

<positive_example>
## Conversation History

User: "revise the intro to be more engaging"
## Output

```json
{"reasoning": "User wants to improve existing content.", "intent": "Revise"}
```
</positive_example>

<positive_example>
## Conversation History

User: "publish it to Medium"
## Output

```json
{"reasoning": "User wants to publish content to a channel.", "intent": "Publish"}
```
</positive_example>

<positive_example>
## Conversation History

User: "hi there"
## Output

```json
{"reasoning": "Simple greeting.", "intent": "Converse"}
```
</positive_example>

<positive_example>
## Conversation History

User: "what should I do next?"
## Output

```json
{"reasoning": "Asking for next-step guidance.", "intent": "Converse"}
```
</positive_example>

<positive_example>
## Conversation History

User: "let's plan out a 5-part series on cooking"
## Output

```json
{"reasoning": "Planning a multi-part content series.", "intent": "Plan"}
```
</positive_example>

<positive_example>
## Conversation History

User: "find posts about productivity"
## Output

```json
{"reasoning": "Searching through existing content.", "intent": "Research"}
```
</positive_example>

<positive_example>
## Conversation History

User: "make the tone more professional"
## Output

```json
{"reasoning": "Adjusting writing style of existing content.", "intent": "Revise"}
```
</positive_example>

<positive_example>
## Conversation History

User: "brainstorm some ideas for a tech blog"
## Output

```json
{"reasoning": "Generating new content ideas.", "intent": "Draft"}
```
</positive_example>

<positive_example>
## Conversation History

User: "schedule the post for next Monday"
## Output

```json
{"reasoning": "Scheduling a post for future publication.", "intent": "Publish"}
```
</positive_example>

<positive_example>
## Conversation History

User: "what channels do I have connected?"
## Output

```json
{"reasoning": "Checking channel configuration.", "intent": "Research"}
```
</positive_example>

<positive_example>
## Conversation History

User: "I prefer shorter paragraphs"
## Output

```json
{"reasoning": "Setting a writing preference.", "intent": "Converse"}
```
</positive_example>

<positive_example>
## Conversation History

User: "plan the revision for my latest post"
## Output

```json
{"reasoning": "Planning a revision sequence.", "intent": "Plan"}
```
</positive_example>

<positive_example>
## Conversation History

User: "approve those changes"
## Output

```json
{"reasoning": "Accepting a revision.", "intent": "Revise"}
```
</positive_example>

<positive_example>
## Conversation History

User: "compare my last two posts"
## Output

```json
{"reasoning": "Comparing existing content.", "intent": "Research"}
```
</positive_example>

<positive_example>
## Conversation History

User: "sure, go ahead"
## Output

```json
{"reasoning": "Endorsing a suggestion.", "intent": "Converse"}
```
</positive_example>

<positive_example>
## Conversation History

User: "create a content calendar for the next month"
## Output

```json
{"reasoning": "Planning content schedule.", "intent": "Plan"}
```
</positive_example>

<positive_example>
## Conversation History

User: "how do I structure a listicle?"
## Output

```json
{"reasoning": "Asking about a writing concept.", "intent": "Research"}
```
</positive_example>

<positive_example>
## Conversation History

User: "start a new post about remote work tips"
## Output

```json
{"reasoning": "Creating new content.", "intent": "Draft"}
```
</positive_example>'''

JSON_ONLY_REMINDER = 'Reply with the JSON object only. No prose, no markdown fences around the object.'


# ── Flow catalog rendering ───────────────────────────────────────────────

def _slots_desc(cls) -> str:
    if not cls:
        return ''
    inst = cls()
    return ', '.join(f'{name} ({slot.priority})' for name, slot in inst.slots.items())


def render_flow_catalog(candidate_names:list[str], flow_catalog:dict,
                        flow_classes:dict) -> str:
    """Flat `### name (dax=...)` list of candidate flows. In-intent and edge
    flows sit in the same list — no separation."""
    blocks = ['## Candidate Flows', '']
    for name in candidate_names:
        cat = flow_catalog.get(name, {})
        dax = cat.get('dax', '')
        desc = cat.get('description', '')
        cls = flow_classes.get(name)
        slots = _slots_desc(cls)
        blocks.append(f'### {name} (dax={dax})')
        blocks.append(desc)
        if slots:
            blocks.append(f'Slots: {slots}')
        blocks.append('')
    return '\n'.join(blocks).rstrip()


# ── Current-scenario rendering ───────────────────────────────────────────

def _render_input(active_post:dict|None, intent:str|None=None) -> str:
    lines = ['## Input', '']
    if active_post:
        lines.append(f"Active post: **{active_post['title']}** (id: `{active_post['id']}`)")
    else:
        lines.append('Active post: None')
    if intent:
        lines.append(f'Predicted intent: **{intent}**')
    return '\n'.join(lines)


def _render_current_scenario(user_text:str, convo_history:str,
                              active_post:dict|None, intent:str|None=None) -> str:
    convo_block = convo_history.strip() if convo_history else '(empty)'
    history = f'## Conversation History\n\n{convo_block}\n\nUser: "{user_text}"'
    input_block = _render_input(active_post, intent)
    return f'{history}\n\n{input_block}'


# ── Builders ─────────────────────────────────────────────────────────────

def build_intent_prompt(user_text:str, convo_history:str,
                         active_post:dict=None) -> str:
    task_body = (
        f'{BACKGROUND_STATIC}\n\n'
        f'## Instructions\n\n{INTENT_INSTRUCTIONS}\n\n'
        f'## Rules\n\n{INTENT_RULES}'
    )
    current = _render_current_scenario(user_text, convo_history, active_post)
    parts = [
        f'<role>{ROLE_INTENT}</role>',
        f'<task>\n{task_body}\n</task>',
        f'<example_scenarios>\n{INTENT_EXAMPLES}\n</example_scenarios>',
        JSON_ONLY_REMINDER,
        f'<current_scenario>\n{current}\n</current_scenario>',
    ]
    return '\n\n'.join(parts)


def build_flow_prompt(user_text:str, intent:str, convo_history:str,
                       candidate_catalog:str, active_post:dict=None) -> str:
    prompt_fields = get_prompt(intent)
    instructions = prompt_fields['instructions'].strip()
    rules = prompt_fields['rules'].strip()
    examples = prompt_fields['examples'].strip()

    rules_body = rules if rules else PRECEDENCE_NOTE
    task_body = (
        f'{BACKGROUND_STATIC}\n\n'
        f'## Instructions\n\n{instructions}\n\n'
        f'## Rules\n\n{rules_body}'
    )
    current = _render_current_scenario(user_text, convo_history, active_post, intent)
    parts = [
        f'<role>{ROLE_FLOW}</role>',
        f'<task>\n{task_body}\n</task>',
        f'<flow_catalog>\n{candidate_catalog}\n</flow_catalog>',
        f'<example_scenarios>\n{examples}\n</example_scenarios>',
        JSON_ONLY_REMINDER,
        f'<current_scenario>\n{current}\n</current_scenario>',
    ]
    return '\n\n'.join(parts)
