# Round 3.3 — Clarification Answers & Grounding Continuity

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

In these cases, the next turn should be processed as an **answer to the pending question** before normal
intent/flow detection. Instead, Hugo may:

- run normal flow detection and choose the wrong flow;
- create or stack a flow with no usable source;
- create vague content such as `topic="blog post"`;
- ask a second clarification that does not use the prior candidate set;
- keep stale Pending/Active flows around without resolving the original missing entity.

---

## Root Cause

The issue is not a missing regex for phrases like "this one" or "second," and it is not a missing data
structure either. Every piece of a would-be "pending clarification frame" already lives in an existing
component:

| Frame field | Where it already lives |
| --- | --- |
| question asked | `ambiguity_handler.observation` — persists across turns; `ask()` returns it verbatim |
| level / missing / expected | `ambiguity_handler.metadata` + `counts` — also persists |
| target flow / target slot | the flow stack — the Active/Pending flow with the unfilled slot IS the target |
| candidates | `grounding.choices` — exists; `_fill_slices` already writes into it |
| resolver + schema | `_fill_slots` Phase 3 with `_fill_slots_schema(flow)` — already a schema-constrained resolver over convo_history, which already contains Hugo's question and the shown candidates |

The root cause is control flow in NLU. `think()` (`nlu.py:100-123`) unconditionally runs fresh
`_detect_flow`, instantiates a **new** transient flow, and pushes it via `_stack_detected_flow` → `stackon`.
It never looks at the top of the stack. So when Hugo asked "which draft should I outline?" last turn, the
outline flow is sitting on the stack Active with its `source` slot unfilled, the question is sitting in
`observation`, and NLU ignores both and classifies "that title's good" from scratch. That is the whole
failure in all three traces — B06.C12's flow pileup is `stackon` being called every turn while the original
flow's slot never fills.

---

## Non-Goals

- Do not add code-based lifecycle guards in PEX. PEX lifecycle management should stay agent/prompt/skill driven.
- Do not solve this with phrase regexes over deictic language.
- Do not revive `active_post` or `slices`.
- Do not introduce a second dialogue state.
- Do not globally block on `ver=False`.
- Do not run live evals as part of this spec unless explicitly requested.

---

## Solution — Detect, Then Fill the Active Flow In Place

No new data model. Three changes, all against existing surfaces. NLU's order of operations stays
uniform across `react` / `think` / `contemplate`: flow detection first (which indirectly classifies
the intent), then slot-filling. A stalled Active flow does not reorder anything — it only changes
where the fill lands.

1. **Fill the Active flow in place.** In `think()`, detection runs as always; the conversation
   history carries the open question, so an answer turn detects the SAME flow that is already
   Active on the stack. When detection matches the Active flow, run the existing `_fill_slots` pass
   against that flow (the one with the unfilled or possibly incorrect slot) — not a fresh instance,
   and no new `stackon`.
   - Detection matches the Active flow → fill it; PEX resumes its policy.
   - Detection returns a different flow → the user detoured or abandoned; the normal stack rules
     apply (see `_specs/components/workflow_planner.md`).
2. **Write shown candidates to `grounding.choices`** when a policy displays them — typed records like
   `{'kind': 'post', 'label': ..., 'entity': {post, sec, snip, chl, ver}, 'source': 'find',
   'turn_number': 3}` — so the fill prompt can offer them as the options for the source slot. This is the
   only new *write*, and it is a write to a field that already exists.
3. **Prompt work rides along.** PEX asking questions through `recognize()` consistently is what keeps the
   pending question in `observation`; that is prompt/skill wording, not new mechanics.

### The four reply outcomes

After "Which draft should I outline?", the next turn resolves one of four ways. Flow detection
decides which — the history carries the open question, so detection routes an answer back to the
same flow:

- **Clear answer** ("the prompt injection one") — detection lands on `outline`, matching the Active
  flow; slot-filling fills `source`, the ambiguity resolves, done.
- **Vague answer** ("that title's good") — same path; the fill call resolves the referent using convo
  history and `grounding.choices`. This is also where NLU having `attempt_recovery()` is powerful:
  preferences and scratchpad can supply the referent when the words alone cannot.
- **Task change** ("actually, when did I last publish anything?") — detection lands on a different
  flow; `stackon` places it and `outline` reverts to Pending beneath it. Record why in the ambiguity
  observation and in the SessionScratchpad, so every agent can see the detour. The ambiguity stays
  **unresolved** — the grounding goal was never met.
- **On-task but non-selecting** ("neither is right, look again") — detection lands on `find`; also a
  `stackon`. Flows continue: when `find` completes, PEX pops it, `outline` is promoted back to
  Active, and the work carries on. The ambiguity again stays **unresolved**.

Within a matching fill the guidance still leans conservative — `_fill_slots_schema` permits returning
nothing for a slot, and a fabricated value is worse than an empty one: a wrong fill makes Hugo act on
the wrong post (visible damage), while an empty fill just leaves the flow asking (annoying,
recoverable).

### Stack invariants this leans on

- **No Pending flow is ever on top of the stack at the start of a turn.** PEX continually pops completed
  flows and continues onto the next as long as there is work to do; a turn can only end with an Active
  (but incomplete) flow that needs more information, or an empty stack. So NLU's detection is always
  compared against a live Active flow, never a stale one.
- The full detour/abandonment rules (detour `stackon` reverts the stalled flow to Pending; abandonment
  marks it Invalid; `fallback` is only for re-routing a wrongly predicted flow) live in
  `_specs/components/workflow_planner.md` — see its stack invariants and scenario matrix.

---

## Decisions (settled 2026-07-09)

- **D1 — Answer vs. task-change:** flow detection decides — the same flow as the Active one means
  answer/continuation; a different flow means detour or abandonment. The fill guidance stays
  conservative within a match: an empty fill rather than a fabricated value. (Supersedes the earlier
  "empty fill = not an answer" routing rule.)
- **D2 — Fill target:** always the top of the stack. That is what makes the stack useful to begin with.
  Naming a target flow in ambiguity metadata would be the Rejected Direction in miniature.
- **D3 — Belief written on a successful fill:** `think()` writes the latest intent and flow to dialogue state — the
  same values already there, so effectively a no-op. A bit of extra work, not dangerous.
- **D4 — Ambiguity across a detour:** the per-turn `counts` reset (new turn), but the ambiguity remains
  **unresolved** until grounding completes. An ambiguity that lives across turns and across tasks is
  exactly why the Handler is a separate object from the Flow Stack.
- **D5 — `grounding.choices` lifecycle:** policies that display a pick-one list write. When the flow
  completes, MEM stores the result (including the slots) and tells NLU to clear `choices` — the chosen
  value already lives in the flow's slots, so nothing else needs saving. Proposal clicks keep working
  because they resolve through `react`, not the utterance slot-fill path.
- **D6 — Confirmation ambiguities** ("Did you mean *Guardrails*?", slot already filled): same fill pass —
  on "yes" the slot keeps its value and the ambiguity resolves; on "no" the slot resets and the ambiguity
  stands. If expressing this through the fill schema gets too complicated, ship without it and revisit.

---

## Rejected Direction — the Pending Clarification Frame (kept as a reminder)

The earlier draft of this spec surveyed five options and recommended introducing a typed "pending
clarification frame" in ambiguity metadata:

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

The described *behavior* was right; the data model was wrong. Per the Root Cause table, every field is a
copy of state another component already owns — `question` is `observation`, `target_flow`/`target_slot` are
the stack top, `candidates` fits `grounding.choices`. The frame is a shadow copy of the flow stack plus the
ambiguity handler: the "second dialogue state" the Non-Goals forbid, with all the drift and
double-bookkeeping that implies.

The lesson: when a design wants a new object whose fields are all pointers into existing components, the
missing piece is code that *reads* those components, not a new place to copy them.

---

## Smallest Proof

Replay the three trace cases (`B05.C09`, `B06.C12`, `B05.C06`) after the `think()` change: the reply turn
should fill the stacked flow's slot and resolve the ambiguity instead of stacking a new flow. No broad live
evals needed.
