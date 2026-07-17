"""
Flow-detection prompt builders for Hugo NLU.

Intent classification (hop 1) runs on TypeSafe, not an LLM — its questions and gate live as
the audit-surface constants below (T17). Flow detection (hop 2) shares the hybrid
XML + Markdown shell used by slot-filling (`backend/prompts/for_nlu.py`):

  <role>...</role>
  <task>
    ## Background      — shared constant
    ## Instructions    — per-stage (intent) or per-intent (flow)
    ## Rules           — per-stage (intent) or per-intent (flow)
  </task>
  <flow_ontology>                  (flow stage only)
    ## Candidate Flows — flat `### name (dax)` list; in-intent + edge flows
  </flow_ontology>
  <example_scenarios>
    <positive_example>...</positive_example>
    <edge_case>...</edge_case>
  </example_scenarios>
  Reminder: reply with JSON only.
  <current_scenario>
    ## Conversation History
    ## Input           — `Active post: ...` + (flow stage) `Predicted intent: ...`
  </current_scenario>

Flow detection's output shape is enforced by a provider-side JSON schema
(`_flow_detection_schema` in `backend/components/dialogue_state.py`):
  - flow: {"reasoning": str, "flow_name": one-of-candidates}"""

from backend.prompts.experts import get_prompt
from schemas.ontology import FLOW_ONTOLOGY


ROLE_FLOW = (
    'You are operating as the flow-detection component of a blog-writing assistant (named Hugo). '
    'Given the predicted intent, choose the specific flow that best captures what the user wants.'
)

BACKGROUND_STATIC = (
    '## Background\n\n'
    'Hugo is a blog-writing assistant. Work is organized into **flows** — units of work that share a '
    'goal (drafting a post, releasing it, finding posts, etc.). Flows group under one of six flow-owning '
    '**intents**:\n'
    '- **Research**: find posts and notes, inspect metrics and metadata, summarize drafts, compare posts.\n'
    '- **Draft**: brainstorm ideas, generate outlines, compose prose from an outline, '
    'refine sections.\n'
    '- **Revise**: restructure and rework drafts, edit sentences and phrasing, audit voice and '
    'consistency, propose alternatives for placeholder gaps.\n'
    '- **Publish**: publish to the blog, cross-post to channels, schedule, add citations.\n'
    '- **Converse**: greetings, open-ended questions about writing, general discussion.\n'
    '- **Plan**: lay out a multi-step writing plan that spans the intents above.\n\n'
    'A seventh label — **Clarify** — owns no flows: predict it when the request is too ambiguous to '
    'commit to another intent, instead of guessing.\n\n'
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

# ── Intent stage: the TypeSafe questions (no LLM prompt; T17) ────────────
# classify_intent's audit surface (SKILL.md: question text and gate values live as named
# constants in one module). One call, three questions fanned out: a Choice over the domain
# intents (+ Continue when a continuable flow is grounded — its rubric is built at call time
# naming that flow) and the two nouls. A noul at or above NOUL_THRESHOLD IS the intent.
# The document stays lean ({history, utterance}) — exp3 showed grounding context hurts here.

INTENT_CRITERIA = {
    'Research': 'Find posts and notes, inspect metrics and metadata, summarize drafts, '
                'compare posts.',
    'Draft': 'Brainstorm ideas, generate outlines, compose prose from an outline, refine '
             'sections.',
    'Revise': 'Restructure and rework drafts, edit sentences and phrasing, audit voice and '
              'consistency, propose alternatives for placeholder gaps.',
    'Publish': 'Publish to the blog, cross-post to channels, schedule, add citations.',
    'Converse': 'Greetings, open-ended questions about writing, general discussion, setting '
                'a preference.',
}

INTENT_QUESTION = 'Which intent is the user requesting?'

NOUL_THRESHOLD = 0.8   # either noul at/above this IS the intent (the higher of the two wins)

PLAN_NOUL = {'type': 'noul', 'instructions': 'Is this a multi-step plan?', 'criteria': {
    'true': 'The user is asking for two or more distinct operations in one message — no '
            'single action covers the whole request on its own',
    'false': 'A single operation covers the whole request'}}

CLARIFY_NOUL = {'type': 'noul',
                'instructions': 'Is there uncertainty that we need to clarify?', 'criteria': {
    'true': 'The request is too vague or underspecified to act on without asking the user '
            'a question first',
    'false': 'The request is clear enough to act on'}}


JSON_ONLY_REMINDER = 'Reply with the JSON object only. No prose, no markdown fences around the object.'


# ── Flow ontology rendering ───────────────────────────────────────────────

def _slots_desc(cls) -> str:
    if not cls:
        return ''
    inst = cls()
    return ', '.join(f'{name} ({slot.priority})' for name, slot in inst.slots.items())


def render_flow_ontology(candidate_names:list[str], flow_ontology:dict,
                        flow_classes:dict) -> str:
    """Flat `### name (dax=...)` list of candidate flows. In-intent and edge
    flows sit in the same list — no separation."""
    blocks = ['## Candidate Flows', '']
    for name in candidate_names:
        cat = flow_ontology.get(name, {})
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

def detection_snippet(intent:str, hint:str='') -> str:
    """The extra detection-prompt block NLU's check() picks for the classified intent — the
    working-intent guidance appended after the base flow prompt. Continue (an Active flow in
    the hint) reads very differently from Plan or Clarify (round 3.4)."""
    if hint in FLOW_ONTOLOGY:
        return (f'<working_intent>\nAn Active flow `{hint}` is mid-task. The most likely '
                f'reading of this turn is that it CONTINUES that work — prefer `{hint}` or '
                f'one of its edge flows unless the message clearly starts different work.'
                f'\n</working_intent>')
    intent = intent or hint    # an intent-shaped hint (the tie-break re-detect) keys the block
    if intent == 'Plan':
        return ('<working_intent>\nThe working intent is Plan: the request spans multiple '
                'steps. Detect the flow the FIRST concrete step would run — the plan is '
                'decomposed elsewhere; your job is only the entry flow.\n</working_intent>')
    if intent == 'Clarify':
        return ('<working_intent>\nThe working intent is Clarify: the request is '
                'underspecified. Detect the closest flow anyway — low agreement is expected '
                'and raises a clarification downstream.\n</working_intent>')
    if intent:
        return (f'<working_intent>\nThe working intent is {intent} — prefer its flows, and '
                f'leave it only on a clear signal.\n</working_intent>')
    return ''


def build_flow_prompt(user_text:str, intent:str, convo_history:str,
                       candidate_ontology:str, active_post:dict=None) -> str:
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
        f'<flow_ontology>\n{candidate_ontology}\n</flow_ontology>',
        f'<example_scenarios>\n{examples}\n</example_scenarios>',
        JSON_ONLY_REMINDER,
        f'<current_scenario>\n{current}\n</current_scenario>',
    ]
    return '\n\n'.join(parts)
