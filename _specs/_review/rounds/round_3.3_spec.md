# Round 3.3 — Clarification Binding & Grounding Continuity

Maps to **Master Plan · Round 3**. This round is about understanding why Hugo loses the thread after it asks,
shows, or implies a grounding choice. The goal of this spec is to define the problem and root cause clearly
before choosing an implementation.

**Demo target:** Hugo can ask a targeted grounding question or show candidate posts, then correctly interpret
the user's next turn as an answer to that question before moving on to outline, compose, revise, or publish.

Primary trace evidence:

- `B05.C09`: Hugo finds two red-teaming drafts. The next user turn says, "Maybe we just make a start?" Hugo
  does not preserve a clear pending decision about whether to create a new post or choose one of the found
  drafts. Later, "That title's good" is not cleanly bound as an answer to a known question.
- `B06.C12`: Hugo repeatedly asks for a post/topic while stacking flows that cannot run usefully. The system
  has flow intent, but not a grounded object or a durable clarification state.
- `B05.C06`: A fresh-topic workflow gets misread as refinement/write/publish on a missing post. The problem is
  not just "pick a candidate"; it is failure to represent the pending conversational commitment.

---

## Problem

Hugo currently treats each user utterance mostly as a fresh NLU event. When a prior turn created a pending
decision, the next turn is not reliably interpreted against that pending decision.

Examples:

- Hugo asks "which post?" and the user answers "that title's good."
- Hugo shows two drafts and the user says "make a start."
- Hugo asks whether to create a new post or use an existing draft, and the next turn supplies a vague but
  contextually meaningful answer.

In these cases, the next turn should be processed as an **answer to a pending grounding/clarification frame**
before normal intent/flow detection. Instead, Hugo may:

- run normal flow detection and choose the wrong flow;
- create or stack a flow with no usable source;
- create vague content such as `topic="blog post"`;
- ask a second clarification that does not use the prior candidate set;
- keep stale Pending/Active flows around without resolving the original missing entity.

---

## Root Cause Hypothesis

The issue is not primarily a missing regex for phrases like "this one" or "second." The root cause is that
Hugo has no explicit, durable **pending clarification frame** that says:

- what question was asked;
- what kind of answer is expected;
- what candidate entities or options are available;
- which flow/slot should receive the answer;
- whether the answer should resume an existing flow, replace it, or start a different flow.

The current state surfaces are close but incomplete:

- `grounding.entities` stores the active entity, not the unresolved choice set.
- `grounding.choices` exists, but is overloaded: proposal clicks already use numeric choices, and it does not
  currently carry an explicit "answer this question" contract.
- `AmbiguityHandler` records level/metadata/observation, but the metadata does not consistently include
  candidate entities, target flow id, target slot, or expected answer type.
- `SessionScratchpad` can store findings, but scratchpad entries are not the active clarification contract.
- PEX prompt/lifecycle instructions can ask questions, but the system does not reliably force the next NLU pass
  to bind the reply to the pending question before classifying it as a fresh task.

So the failed behavior is expected: if the state does not encode "the next turn may answer this specific
question," NLU has no robust basis for deciding whether "that title's good" means selecting an existing post,
approving a new title, continuing an outline, or just chatting.

---

## Non-Goals

- Do not add code-based lifecycle guards in PEX. PEX lifecycle management should stay agent/prompt/skill driven.
- Do not solve this with phrase regexes over deictic language.
- Do not revive `active_post` or `slices`.
- Do not introduce a second dialogue state.
- Do not globally block on `ver=False`.
- Do not run live evals as part of this spec unless explicitly requested.

---

## Option A — Candidate Records in `grounding.choices`

This was the initial proposed direction: when Hugo shows candidate posts, store typed candidate records in
`grounding.choices`; before fresh detection, NLU tries to resolve the user reply against those candidates.

Sketch:

```python
{
  'kind': 'post',
  'label': 'Prompt Injection Has No Fix, Only Blast Radius',
  'entity': {'post': 'a6f7d276', 'sec': '', 'snip': '', 'chl': '', 'ver': True},
  'source': 'find',
  'turn_number': 3,
}
```

Pros:

- Makes visible candidates inspectable in dialogue state.
- Connects list/search results to later grounding.
- Useful for UI clicks and explicit ordinal selections.
- Small surface area if limited to find/list artifacts.

Cons:

- `choices` is already overloaded by proposal-selection flows.
- Candidate storage alone does not say what question is pending or which slot should be filled.
- Easy to drift into brittle phrase matching: "that one", "this", "go ahead", "that title's good."
- Does not handle non-candidate clarifications, such as create-new-vs-use-existing.
- Risks binding when the user is actually changing tasks.

Assessment:

Useful as a supporting representation, but not sufficient as the main solution. It records options, not the
clarification contract.

---

## Option B — Pending Clarification Frame in Ambiguity State

Extend ambiguity metadata into a typed, explicit frame whenever Hugo asks a clarification question.

Sketch:

```python
{
  'level': 'confirmation',
  'missing': 'source',
  'expected': 'select_entity',
  'target_flow': {'flow_id': '...', 'flow_name': 'outline'},
  'target_slot': 'source',
  'candidates': [
    {'label': 'Guardrails...', 'entity': {'post': 'd0fda7f7', 'sec': '', 'snip': '', 'chl': '', 'ver': True}},
    {'label': 'Prompt Injection...', 'entity': {'post': 'a6f7d276', 'sec': '', 'snip': '', 'chl': '', 'ver': True}},
  ],
  'question': 'Which draft should I outline?'
}
```

At the next user turn, NLU first runs a **clarification-resolution pass** against this frame:

- resolved: fill target slot/entity, clear ambiguity, and continue or activate the target flow;
- not resolved: either keep ambiguity and ask again, or clear it if the user clearly changed tasks;
- ambiguous answer: ask a more specific follow-up.

Pros:

- Directly models the real missing concept: "the next reply may answer this question."
- Works for entity choices, yes/no confirmations, missing slots, and create-new-vs-existing decisions.
- Avoids regex as the primary mechanism; the resolver can be LLM-judged with a schema.
- Keeps responsibility in NLU/AmbiguityHandler, where Round 3 says it belongs.
- Gives PEX a clear prompt contract: ask via ambiguity frames, then let NLU bind the answer.

Cons:

- Requires tightening all places that declare ambiguity so metadata is well-formed.
- Needs a small resolver prompt/schema and careful failure behavior.
- More invasive than simply storing candidates.
- Requires deciding how PEX should resume after an ambiguity is resolved.

Assessment:

This is the most coherent direction. It solves the root cause instead of a symptom.

---

## Option C — Scratchpad-Based Candidate Memory

Use `SessionScratchpad` as the durable place where find/list results and pending questions are written. NLU's
turn-point review reads the scratchpad and resolves answers from there.

Pros:

- Reuses an existing cross-agent memory surface.
- Can store rich context without bloating dialogue state.
- Search/find results already have scratchpad write paths in some policies.

Cons:

- Scratchpad is an open-ended ledger, not an active state contract.
- Harder to know which entry is the current question versus stale context.
- Adds indirection: NLU must infer active clarification from notes.
- The failure mode becomes "wrong scratchpad note" instead of "missing pending frame."

Assessment:

Good as supporting evidence for the resolver, not as the primary source of truth.

---

## Option D — Prompt-Only PEX Repair

Strengthen the orchestrator prompt and relevant flow skills so PEX asks better questions and references prior
candidate lists more explicitly.

Pros:

- No new data model.
- Aligns with the principle that PEX lifecycle is agent-managed, not guarded in code.
- Can improve language quality quickly.

Cons:

- Does not give NLU a durable frame for the next turn.
- Fails when the next turn enters through NLU before PEX can reason over it.
- Prompt compliance is variable; traces already show PEX can ask plausible questions while state remains
  unresolved.

Assessment:

Necessary but not sufficient. Prompt improvements should accompany, not replace, an explicit clarification
frame.

---

## Option E — UI/Action-First Binding

Lean into clickable list/selection UI: when Hugo shows candidate posts, the UI sends `dax + payload` with the
chosen entity. Free-text replies remain ambiguous and may be clarified.

Pros:

- Robust when the user clicks.
- Uses existing `react`/payload pathway.
- Avoids natural-language binding complexity for the happy path.

Cons:

- Does not solve free-text replies like "that title's good."
- Depends on UI behavior and user interaction style.
- Still needs a fallback clarification-resolution path.

Assessment:

Useful product affordance, but not enough for conversational continuity.

---

## Recommendation

Build **Option B: Pending Clarification Frame in Ambiguity State**, with Option A as a subordinate data shape
only when the pending question has candidate entities.

The central change should be:

1. When Hugo asks a clarification, it records a typed ambiguity frame with `expected`, `target_flow`,
   `target_slot`, optional `candidates`, and `question`.
2. On the next `understand(op='think')`, NLU first attempts to resolve the user's reply against that frame via
   a schema-constrained resolver.
3. Only if the reply is not an answer does NLU proceed to normal flow detection.
4. If resolved, NLU fills the target slot/entity and clears ambiguity; PEX then resumes through prompt/skill
   lifecycle, not code guards.

This keeps the design aligned with Round 3:

- ambiguity handling belongs to NLU/AmbiguityHandler;
- PEX remains the lifecycle agent;
- dialogue state remains single-source;
- grounding stays in `{'choices': [], 'notes': [], 'entities': [...]}`;
- no brittle regex-based binding is needed.

---

## Next Spec Revision Needed

Before implementation, revise this spec into an execution plan that answers:

- What exact ambiguity-frame schema should be allowed?
- Which existing ambiguity declarations need to be upgraded first?
- Should `candidates` live inside ambiguity metadata, `grounding.choices`, or both?
- What should the resolver schema return?
- When a clarification resolves, should NLU activate/resume the target flow indirectly by updating stack slots,
  or should PEX decide from the resolved belief on its next loop?
- What are the smallest trace cases that prove improvement without running broad live evals?
