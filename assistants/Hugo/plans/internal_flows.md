# Phase 3 — Chat dispatching to Internal sub-flows

## Current state

`chat_policy` (`backend/modules/policies/converse.py:26-30`) is two lines of work:

```python
def chat_policy(self, flow, state, context, tools):
    convo_history = context.compile_history()
    raw_output = self.engineer(convo_history)
    flow.status = 'Completed'
    return TaskArtifact(origin='chat', thoughts=raw_output)
```

Single LLM pass over conversation history, no dispatch, no tools, no FAQ awareness.

We will add a router stage that classifies the latest user utterance into
`{search, reference, direct}`, and either:
- pushes a sub-flow via `flow_stack.stackon(...)` and returns `keep_going=True`
  so the inner loop runs the sub-flow, OR
- proceeds to the existing single-LLM-call path for the `direct` branch.

After the sub-flow completes, the inner loop re-enters `chat_policy`, which now reads
the sub-flow's findings from the scratchpad and composes a grounded final response.

## Prior art: `audit_policy`

`backend/modules/policies/revise.py:211-296` is the canonical template:

- `flow.stage` is a string attribute on the flow that progresses through phases
  (`'discovery'` → `'delegation'` → `'completed'` for audit).
- `_audit_dispatch` (revise.py:259) calls a routing-LLM with a JSON-schema-validated
  output, picks `flow_stack.stackon(name)` for each delegate, fills slots, sets
  `state.has_plan = True; state.keep_going = True`, returns a frame describing the
  routing decision.
- Sub-flows (rework, polish, etc.) run in subsequent inner-loop passes. Each writes
  a summary to the scratchpad keyed by `flow.name()` and marks the parent's
  `delegates` checklist complete (revise.py:201-208).
- When all delegates verify complete, the parent's `audit_policy` enters its
  collection branch (revise.py:214-226) and reads back from scratchpad.

We use the same control flow with simpler bookkeeping (single dispatch, no
checklist).

## Decisions

- **Router lives in a helper** at `backend/prompts/pex/support/converse_prompts.py`
  (alongside the FAQ/reference schemas from phases 1-2): `build_chat_dispatch_prompt`
  + `CHAT_DISPATCH_SCHEMA`. Keeps `chat_policy` body short; mirrors the
  `revise_prompts.py` precedent.
- **Stage attribute on `ChatFlow`**: `flow.stage` defaults to `'pre_dispatch'`,
  flips to `'post_dispatch'` on the second pass. Identical to how audit uses
  `flow.stage`.
- **Single dispatch per turn (v1).** Router emits one of three branches; no
  multi-stack.
- **`keep_going` mechanics**: when router picks `search` or `reference`, set
  `state.keep_going = True` so the orchestrator re-enters the loop. (We do NOT set
  `state.has_plan` because Chat is `Converse` intent, not `Plan`. `keep_going` alone
  is sufficient for inner-loop continuation; `has_plan` is only used by RES to
  suppress naturalization on Plan completion.)
- **Slot transfer at stackon**: `FlowStack.stackon()` already auto-transfers matching
  slot values from parent to child (`stack.py:30-33`). ChatFlow's only slot is
  `topic`, which doesn't match SearchFlow's `query` or ReferenceFlow's `target`. So
  we fill the child slots manually after stackon — same as audit does at
  `revise.py:286-289`.

## Implementation steps

### Step 1 — Router prompt + schema

`backend/prompts/pex/support/converse_prompts.py`:

```python
CHAT_DISPATCH_SCHEMA = {
    'type': 'object',
    'properties': {
        'route': {'type': 'string', 'enum': ['search', 'reference', 'direct']},
        'query': {'type': 'string'},   # FAQ query for search; word for reference; ignored for direct
    },
    'required': ['route', 'query'],
    'additionalProperties': False,
}


def build_chat_dispatch_prompt(user_text:str, convo_history:str) -> str:
    """Classify a chat utterance into search / reference / direct.

    search   — meta-questions about Hugo or its capabilities; FAQ-style.
    reference — dictionary/thesaurus lookups; definitions, synonyms, antonyms.
    direct   — conversational, opinion, advice, or general chat with no factual lookup.

    `query` carries the FAQ keywords (search) or the target word/phrase (reference);
    for direct, return an empty string."""
    return (
        f"Conversation so far:\n{convo_history}\n\n"
        f"Latest user message: {user_text}\n\n"
        "Classify the user's message into ONE of three routes:\n\n"
        "- search    — questions about Hugo itself: capabilities, scope, who built it, "
        "privacy, supported channels, pricing. Examples: 'what can you do?', "
        "'tell me about who made you', 'how do you handle SEO?'.\n"
        "- reference — dictionary or thesaurus lookups: definitions, synonyms, "
        "antonyms, usage. Examples: 'synonym for important', 'definition of ephemeral', "
        "'formal alternatives to good'.\n"
        "- direct    — conversational chat, advice, opinion, off-topic, or general "
        "Q&A about writing craft that doesn't need a vetted FAQ.\n\n"
        "Return JSON. For search/reference, set `query` to the FAQ keywords or the "
        "target word/phrase. For direct, set `query` to an empty string."
    )
```

### Step 2 — Add `stage` to `ChatFlow`

`backend/components/flow_stack/flows.py` (around line 638). The `BaseFlow` base class
already has `stage` (audit and others use it) — confirm by grepping. If not, add it
to `ChatFlow.__init__`:

```python
class ChatFlow(ConverseParentFlow):
    def __init__(self):
        super().__init__()
        self.flow_type = 'chat'
        self.dax = '{000}'
        self.stage = 'pre_dispatch'    # ← NEW (or omit if BaseFlow.stage exists)
        ...
```

(Verify `BaseFlow.stage` exists in `parents.py` first — audit uses it without
re-declaring, suggesting it's already on the base.)

### Step 3 — Rewrite `chat_policy`

`backend/modules/policies/converse.py:26-30` becomes:

```python
def chat_policy(self, flow, state, context, tools):
    convo_history = context.compile_history()

    if flow.stage == 'post_dispatch':
        return self._chat_compose_with_findings(flow, convo_history)

    # Stage 1: route
    user_text = context.last_user_text
    prompt = build_chat_dispatch_prompt(user_text, convo_history)
    decision = self.engineer(prompt, task='skill', schema=CHAT_DISPATCH_SCHEMA)

    route = decision['route']
    if route == 'direct':
        flow.status = 'Completed'
        text = self.engineer(convo_history)
        return TaskArtifact(origin='chat', thoughts=text)

    # Stage 1b: dispatch
    sub_flow_name = 'search' if route == 'search' else 'reference'
    child = self.flow_stack.stackon(sub_flow_name)
    if route == 'search':
        child.fill_slot_values({'query': decision['query']})
    else:  # reference
        child.fill_slot_values({'target': [{'word': decision['query']}]})

    flow.stage = 'post_dispatch'
    state.keep_going = True
    return TaskArtifact(origin='chat',
        metadata={'dispatched_to': sub_flow_name, 'query': decision['query']})


def _chat_compose_with_findings(self, flow, convo_history):
    # Read back from whichever scratchpad key was just written
    findings = self.memory.read_scratchpad('search') or self.memory.read_scratchpad('reference')
    summary = findings['summary'] if findings else ''

    prompt = (f"{convo_history}\n\n"
              f"[Internal lookup result]\n{summary}\n\n"
              "Compose a natural conversational reply that incorporates the lookup result.")
    text = self.engineer(prompt)
    flow.status = 'Completed'
    return TaskArtifact(origin='chat', thoughts=text)
```

Imports added at the top of `converse.py`:

```python
from backend.prompts.pex.support.converse_prompts import (
    build_chat_dispatch_prompt, CHAT_DISPATCH_SCHEMA,
)
```

### Step 4 — Verify the inner-loop chain

The orchestrator already supports `keep_going`-driven re-entry — `audit_policy` relies
on this and works. No PEX/RES change needed.

Two non-obvious checks during smoke test:
- After the sub-flow completes, does the inner loop re-enter `chat_policy` (not pop
  off Chat)? **Yes** — `flow_stack.pop_completed()` removes only `Completed`/`Invalid`
  flows, and Chat is in `pre_dispatch` → `post_dispatch` (still `Active`).
- Does the scratchpad survive between inner-loop turns? **Yes** —
  `MemoryManager.scratchpad` persists for the duration of the session.

## Verification

- **Free tier**: `pytest utils/tests/unit_tests.py utils/tests/test_artifacts.py` —
  must stay green.
- **New e2e scenario** in `utils/tests/e2e_multiturn_evals.py`, three sub-cases:
  - `chat_dispatch_search`: user says "what can Hugo do?" → assert response cites
    the FAQ corpus answer.
  - `chat_dispatch_reference`: user says "synonym for important" → assert response
    contains 3+ synonyms.
  - `chat_dispatch_direct`: user says "what's your favorite color?" → assert
    response is composed without a sub-flow being pushed (check world-state log).
- **Manual smoke**: in dev mode, log the router's classification + final stack at
  the end of each turn; eyeball that direct/search/reference each route as expected.

## Risks

- **Two-pass adds latency**. Search-routed turns now run: router LLM (~1s) + search
  rerank LLM (~1s) + composition LLM (~1s) ≈ 3s end-to-end. Reference is similar.
  Acceptable for v1; cache the router decision per turn-id if it bites.
- **Router missclassifies "what does *X* mean" as reference when *X* is a Hugo
  feature.** "What does the audit flow do?" should route to *search*, not *reference*.
  The router prompt's examples need to nail this — verify in eval.
- **The `keep_going` chain is bounded by `max_flow_depth=8`** (`stack.py:11`). In
  practice we add 1 sub-flow per dispatch, so we're nowhere near the limit. But if
  Chat ever recursively dispatches (Search → Chat → Reference), watch the depth.
  v1 has no recursion.
- **Direct-branch UX regression risk.** The direct branch must remain
  indistinguishable from today's `chat_policy` behavior. The current implementation
  short-circuits before any state mutation, so this should be a no-op for direct
  conversations.
