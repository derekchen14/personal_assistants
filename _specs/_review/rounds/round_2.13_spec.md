# Round 2.13 — Grounding and Stack-Transition Correctness

Maps to **Master Plan · Round 2 (PEX)**. Proposal spec — evidence comes from the round-2.12 eval
run (2026-07-09, seed 212, report `evals_trace_20260709_234431.jsonl`, 13/36 turns completion-ok).
The failures decomposed into four buckets; this round takes the high-priority correctness failures
whose root causes are established in code. Model near-misses and provider weather are recorded out
of scope rather than mixed into the stack/grounding implementation. Already shipped ahead
of this round: the `_expand_query` hyphen fix (a hyphenated query like "Roman-engineering" now also
searches its spaced form — one retrieval miss caused 5 of the 23 failed turns).

---

## 2.13.1 — Ground plural references from the shown list (the biggest win)

### Problem

Evidence: `B01.C07` turn 2. Turn 1's `find` displayed 4 posts; the user said "how do those two
published posts differ in tone." NLU detected `compare` correctly and filled `category=tone`, but
`source` stayed empty and the orchestrator asked "which two?" — a question the screen had already
answered. Scored fail; three follow-up turns cascaded.

This is high priority because the agent has already done the expensive and user-visible work: it
found the records, rendered them, and stored stable entity ids in `grounding.choices`. Failing to
use that data is not ordinary model uncertainty. It is a broken handoff between turns. The user is
forced to repeat information that is simultaneously visible on screen and present in state, which
makes the system appear forgetful and turns a one-step follow-up into an ambiguity loop. One missed
reference caused four failed turns in the cited trace; the downstream cost is much larger than the
single initial slot miss.

The failure is systematic, not limited to "those two." Any deictic or filtered plural reference —
"both," "all four," "the published ones," "the drafts," "the first and third" — is impossible on
a fresh flow even when the shown list uniquely determines the answer. This blocks compare, batch
summarize, multi-target revise, and any later flow that consumes a prior selection list.

### Root cause

`grounding.choices` (the candidate records `find` writes) is only offered to
slot-filling on a STALLED flow — `build_pending_question` rides the fill prompt via the
`stalled=True` flag in `_fill_slots` (`nlu.py`). A freshly detected flow never sees the candidates,
so "those two", "the published ones", "all four" cannot resolve.

The data model is otherwise sufficient: choices already carry stable labels and entity ids, and
`SourceSlot` already accepts multiple entities. The missing link is prompt availability. Status is
the one absent discriminator needed for phrases such as "the published ones." Re-querying the
database during slot fill would introduce needless I/O and could disagree with the exact list the
user saw; the shown candidate record should remain the reference frame.

### Target changes

Changes:

1. **Slot-filling prompt always includes Choices if they exist**, not just stalled ones. In Phase 3:
   `NLU._fill_slots`, if `state.grounding['choices']` is non-empty, append a `<shown_candidates>` block 
   to the fill_slots prompt so that the model is aware of the choices shown to the user.
2. **Plural selection guidance** in that same block: a reference that picks SEVERAL candidates fills
   the source slot with one entity per pick ("those two published posts" → the two records whose
   status is published; "all of them" → every record). `SourceSlot.add_one` already accepts
   multiple entities; `SourceSlot(2)` on compare already demands two.
3. The record shape in the planner/3.3 specs updates to match.

### Verification

- Replay `B01.C07`; turn 2 fills `compare.source` with the two published posts and runs without a
  clarification.
- Add deterministic cases for "both," "all of them," "the drafts," and ordinal subsets.
- Verify selection is limited to the currently shown choice records; NLU must not invent an id or
  silently pull a record from an older list.
- Verify consumed choices still clear under the existing lifecycle rule after a non-source flow
  completes.

## 2.13.2 — `pop` runs only the Pending flow it actually promotes

### Problem

The permanent dispatch contract is narrower than the current implementation: `pop` runs a policy
ONLY when removing terminal entries exposes a Pending flow and promotes it to Active. The fact that
the operation is named `pop` is not itself a run signal. A pop that empties the stack, removes
nothing, or leaves an already-Active flow on top has no newly runnable work.

Today `PEX._manage_flows` treats every `pop` as a run event:

```python
run = params['op'] in ('fallback', 'pop') or ...
if run:
    return self._top_policy(state, document)
```

`_top_policy` then accepts both Pending and Active tops. That combination silently turns
`pop` into a general "run whatever is on top" button. The ordinary happy path hides the problem:
a Completed child is removed, its Pending parent is promoted, and running the parent is correct.
The same code is wrong in three neighboring cases:

1. **No terminal entry exists.** An accidental/repeated `pop` against `[outline·active]` re-runs
   outline even though the stack did not change.
2. **A terminal sibling is removed while an Active flow survives.** The survivor is run a second
   time, risking duplicate domain writes, duplicate completion records, repeated tool costs, or a
   clarification being asked twice.
3. **The stack becomes empty.** A run is attempted even though there is no promoted task. The
   current helper happens to return state, but correctness depends on a downstream no-op rather
   than on the transition contract.

This is targeted because policy execution may change external state. A run must follow an
observed lifecycle transition, not an operation name. A duplicated read is wasteful; a duplicated
publish, schedule, write, or delete can be user-visible and irreversible.

### Target contract

`FlowStack.pop()` identifies whether it promoted a Pending flow. PEX executes only that flow's policy:

```python
completed, promoted = stack.pop()
if promoted is not None:
    return execute_policy(promoted)
return state_only_result
```

The implementation does not have to use this exact tuple, but the promotion fact must be explicit
and derived inside the stack operation. Do not infer it merely from "the top is Active" after the
write; that cannot distinguish a newly promoted flow from an Active flow that was already running.

Recommended shape:

- `FlowStack.pop()` returns an operation result containing `completed` and `promoted`.
- `DialogueState.write_state(..., op='pop')` preserves that transition result for its caller while
  still persisting the ordinary state document. Do not serialize transient run metadata into
  `state.json`.
- `_manage_flows` calls `_top_policy` only when `promoted` is present.
- `_top_policy` may continue accepting Active because a promoted flow has already become
  Active, but the caller must name/pass the promoted flow so a different Active entry cannot be
  selected accidentally.

### Verification

- `[outline·completed] → pop → []`: no policy call.
- `[compose·pending, outline·completed] → pop`: compose is promoted and called exactly once.
- `[compose·active] → pop`: no stack change and no policy call.
- A repeated pop after successful cleanup does not repeat the prior policy.
- Mixed terminal cleanup still removes all Completed/Invalid entries in one sweep and runs
  at most one promoted Pending flow.
- Assert policy invocation counts, scratchpad completion-record counts, and domain mutation counts;
  checking only the final status would miss duplicate execution.

## 2.13.3 — Same-type dedupe compares entity identity, not merely entity presence

### Problem and why it matters

Scenario 12b requires the stack to distinguish "the same flow again" from "another instance of the
same flow for a different target." The current `FlowStack.stackon` does not perform that comparison.
It looks only at the existing flow:

```python
if curr_flow.flow_type == flow_name:
    entity = curr_flow.slots.get(curr_flow.entity_slot)
    if not (entity and entity.check_if_filled()):
        return curr_flow
```

That implements **entity present vs. absent**, not **existing entity vs. incoming entity**. Once a
`summarize` flow is grounded to post A, another `stackon('summarize')` always creates a new task —
even if the incoming request is also post A. Conversely, while the first flow is not yet grounded,
a real second task can be collapsed into it because the incoming target is not available to the
dedupe decision.

The timing makes this unavoidable with the current API: NLU fills a transient flow, calls
`stackon(flow_name)`, and copies slots only AFTER stackon returns. PEX likewise pushes first and
applies belief slots afterward. The stack therefore decides identity before it can see the new
identity. Comments call this entity-aware, but the information required for entity awareness is
not present at the decision point.

This matters beyond avoiding a duplicate stack entry. Reusing two distinct targets loses requested
work; creating two entries for the same target can run the same mutation twice. Multi-post summarize
is the clearest example, but every domain relies on `BaseFlow.entity_slot` to define what its task is
about. Dedupe belongs at this shared choke point so NLU staging, PEX routing, and policy prerequisite
pushes cannot drift into three different definitions of task identity.

### Target contract

Make incoming slots/entity available before the push decision:

```python
stackon(flow_name, slots=None, transfer=True)
```

`stackon` constructs the candidate flow, applies the incoming values, then compares the candidate's
entity slot with the newest live same-type flow. The comparison ignores verification bookkeeping
(`ver`) and uses the domain entity parts (`post`, `sec`, `snip`, `chl`) represented by that slot.

Required outcomes:

| Existing same type | Incoming same type | Result |
|---|---|---|
| same normalized entity | same entity | reuse existing flow; merge non-conflicting new slots |
| entity A | entity B | push a distinct flow |
| neither has an entity | unknown | reuse conservatively |
| existing unknown | incoming known | fill/reuse the existing entry when it represents the same unstarted task |
| existing terminal | any | push new; terminal entries never dedupe or transfer |

The comparison must use the flow's declared `entity_slot`, not assume every domain has a `post`.
Normalization must make equivalent serialized shapes compare equal (one entity dict vs. the slot's
one-item list form). If a flow deliberately supports several entities in one instance, compare the
normalized entity collection rather than only its first member.

Call-site changes:

- NLU `_stack_detected_flow` passes the transient flow's `slot_values_dict()` into `stackon` instead
  of copying values after identity was decided.
- PEX `manage_flows(stackon)` accepts initial slots for planned same-type batches, or supplies the
  matching belief slots before the stack call. A multi-target plan must be able to queue post A,
  post B, and post C as three distinguishable entries.
- Matching-slot transfer from the prior flow happens after candidate identity is established and
  remains disabled while an ambiguity is open.

Parallel execution remains out of scope. This task only ensures the correct number and identity of
stack entries; the existing runtime may execute them sequentially.

### Verification

- Summarize post A twice → one live summarize entry and one policy execution.
- Summarize post A, then post B → two entries preserving their respective sources.
- Three-post plan → three distinct entries, no slot overwrite between them.
- Two ungrounded repeats → one live entry, not an unbounded duplicate tower.
- A terminal summarize for post A does not block a new summarize for post A on a later turn.
- Cover both NLU staging and PEX-authored `stackon`; testing `FlowStack` alone is insufficient
  because the original bug is caused by call-site ordering.

## 2.13.4 — Always record a stack-on transition over an incomplete Active flow

### Problem

When NLU detects a different flow while another flow is Active and incomplete, it stacks the new
flow and the stack reverts the old one to Pending. That transition needs a scratchpad record so PEX,
the new flow, and the resumed old flow can see why the stack changed.

The current code records this transition only when an ambiguity is present:

```python
if stalled and self.ambiguity_handler.is_present:
    self._note_detour(stalled, flow_name)
```

An Active flow can be incomplete without currently being represented by the Ambiguity Handler:

- it is waiting at a confirmation or checkpoint;
- its policy returned early without declaring ambiguity;
- restored state retained the Active flow but lost or cleared ambiguity metadata.

In each case the lifecycle transition is identical: the old Active flow becomes Pending and a new
flow is placed above it. Yet the ambiguity guard suppresses the scratchpad write, leaving no durable
explanation for the stack change. When the upper flow later completes and pop resumes the lower
flow, the relevant conversation may already be compacted and neither policy can reliably reconstruct
why the newer flow was introduced.

### Root cause

The implementation incorrectly treats the transition record as ambiguity metadata. Stack state and
ambiguity state are independent: ambiguity is one reason a flow may remain incomplete, not a
prerequisite for another flow being stacked above it.

The earlier wording also invented a new “detour” concept and a dedicated `detour` scratchpad entry.
That abstraction is unnecessary and misleading. The event is simply an ordinary `stackon`
transition from one flow to another. It does not imply that the user will return, that the old flow
was abandoned, or that an ambiguity exists.

### Target change

Remove the ambiguity guard. Whenever NLU has an incomplete Active top and detection selects and
stacks a different flow, record the transition unconditionally:

```python
if stalled:
    self._record_stack_transition(stalled, stacked)
```

Rename `_note_detour` to `_record_stack_transition` and remove all `detour` vocabulary. Do not:

- append an entry with `origin='detour'`;
- write a `detour` field into Ambiguity Handler metadata;
- modify or append to the ambiguity observation;
- create an ambiguity when none exists.

Write a normal scratchpad entry under the newly stacked flow's origin, describing the immediately
preceding stack relationship:

```python
self.world.scratchpad.append_entry(stacked.name(), {
    'version': 1,
    'turn_number': self.world.context.turn_id,
    'used_count': 0,
    'stacked_over': previous.name(),
})
```

The new flow name is already stamped as `origin`; `stacked_over` is sufficient to explain the
transition without inventing a separate entry type. The write occurs only after stackon succeeds.
The matching-flow fill-in-place path does not write it because no new flow was stacked.

### Verification

- Incomplete Active flow with ambiguity + different detected flow → transition entry written.
- Incomplete Active flow without ambiguity + different detected flow → the same entry is written.
- Confirmation/checkpoint Active flow + new flow → transition entry written.
- Matching detection filled in place → no transition entry.
- Failed stackon → no transition entry.
- Entry origin is the newly stacked flow; no `origin='detour'`, `detour` metadata, or ambiguity
  mutation remains anywhere in the implementation.

## 2.13.5 — Enforce the turn-end stack invariant (no Pending top at the boundary)

### Problem

Evidence: `B02.C15` ended with a five-deep Pending tower (`rework, audit, audit, write, release`).
NLU places every detection on the stack; when the PEX agent legitimately stops to ask a question
instead of running that flow, the placed flow stays Pending, and the next turn's detection lands on
top of it. The turn-end shape check (`MEM._check_turn_end_shape`) fired 13 times across the eval
run — but it only logs. Each leftover distorts the next turn's stack reads and dedupe checks.

An earlier proposal distinguished Pending flows by whether `turn_ids` was empty (placed but never
executed) and superseded only those. That distinction is dropped: all Pending flows are treated
uniformly, and the already-canonical invariant does the work.

### Target contract

The Workflow Planner invariant is: **a turn ends with an empty stack or an incomplete Active top —
never a Pending top.** Enforce it at PEX's end of turn instead of logging it: when the reply is
about to go out and the top flow is Pending, mark it Invalid and `pop` it. The PEX agent already
chose not to act on it this turn, and the belief still carries the detection, so nothing is lost —
the next turn re-detects fresh. Plan steps are unaffected: they sit beneath the top and are
promoted by `pop`, so they never linger as a Pending top across the boundary.

Decision to confirm: invalidate (recommended) vs. auto-run the Pending top at the boundary.
Auto-running would override the PEX agent's judgment mid-reply and can surprise the user.

### Verification

- Replay `B02.C15`: no Pending tower forms; turn-end shape warnings drop to zero across the
  8-sample suite.
- Deterministic case: a turn ends with a Pending top → boundary enforcement marks it Invalid and
  pops; the stack shape is empty or Active-incomplete.
- Plan case: queued plan steps beneath an Active top survive the boundary untouched.

## Out of scope (recorded, not taken)

- Continue-intent coordination and voter composition. The current proposals are
  not settled enough for this implementation round; none of 2.13.1–2.13.4 depends on changing them.
- Detection near-miss exemplar tuning. Five `wrong_belief` turns were observed, but the evidence does
  not isolate missing exemplars as their root cause (candidate restriction, history, labels, and model
  variance remain plausible). Editing prompts against the same dev utterances before that diagnosis
  risks overfitting without fixing a systematic defect. Re-open only with a confusion matrix across
  repeated runs and a held-out verification set.
- Orchestrator-call resilience under 529 due to `anthropic.OverloadedError`
- Parallel same-type execution (planner spec 12b) — the asyncio Concurrency Model upgrade.
- `B02.C06`'s ambiguity_pending chain — re-diagnose AFTER 2.13.1 and Round 3.4.1 land; its
  turns 1-4 mix the plural-grounding gap with stale Pending flows, so it is not a clean signal yet.
- Langfuse observability layer (deferred since round 1).

## Verification

1. `run_suite.py --tests` green throughout; add the focused deterministic cases named by each task.
2. Full suite (`run_suite.py`, default 8-sample) with seed 212 for a like-for-like read against
   `evals_trace_20260709_234431.jsonl`: expect B01.C07 to flip on 2.13.1 plus the shipped hyphen fix.
3. Focused stack-transition tests for 2.13.2/2.13.3: assert policy invocation counts and preserved
   entity values, not only final lifecycle status.
4. Focused transition-record tests for 2.13.4: with and without ambiguity, plus negative cases for
   same-flow fills and failed pushes. Assert that no dedicated detour origin or ambiguity mutation
   remains.

---

## Audit against current code (2026-07-17, post rounds 3.4/3.5)

This spec was written 2026-07-09; rounds 3.4 (NLU↔PEX flow handoff) and 3.5 (list detection)
rebuilt much of the code it targets. Per-section status:

- **2.13.1 — VALID, still the biggest win.** The mechanism moved but the gap is identical:
  slot-fill is now `DialogueState.fill_slots` (not `NLU._fill_slots`), and the gate is
  `ambiguity.is_present` (not a `stalled=True` flag) — candidates still ride the fill prompt only
  through `build_pending_question` when an ambiguity is open (`dialogue_state.py:295-297`). A
  fresh flow still never sees the shown list. One addition the spec predicted: the choice record
  (`research.py:93-97`) carries `{kind, label, entity, source, turn_number}` but NO `status` —
  "the published ones" cannot resolve until the record gains it.
- **2.13.2 — VALID, confirmed live.** `_manage_flows` still runs `_top_policy` on every pop
  (`pex.py:604`), and `_top_policy` accepts a Pending OR Active top — the accidental-pop re-run
  is real today. Two stale details: `DialogueState.write_state` no longer exists (manage_flows
  owns stack ops since 3.4), so the recommended plumbing shape needs rewording; and `pop()`'s
  return (the Completed list) is consumed by `activate_flow`'s `popped` field and the round-3.5
  plan-marker handling, so a changed return shape touches those too.
- **2.13.3 — problem VALID, prescribed fix STALE.** The dedupe in `stackon` still compares
  entity presence, not identity. But the fix as written cannot be applied: there is no transient
  flow anymore — since 3.4, think stacks the LIVE flow first and `fill_slots` fills it afterward,
  so slot values do not exist at the stackon decision point at all. The `stackon(flow_name,
  slots=...)` signature has nothing to feed it from NLU's call site. Needs a design ruling — see
  Unresolved Issues U1.
- **2.13.4 — ALREADY SATISFIED by round 3.4.** `_note_detour` and every trace of `detour`
  vocabulary are gone. validate's announcement entry now records every stackon over an in-flight
  top unconditionally — `{prev_flow, new_flow, is_newborn, summary, rationale, question, tally}`
  with no ambiguity gate (`nlu.py` validate). `prev_flow` carries what `stacked_over` was
  proposed for. Remaining work is the verification list only, confirming the negative cases.
- **2.13.5 — LARGELY DISSOLVED by rounds 3.4/3.5.** The B02.C15 Pending-tower mechanism was
  "NLU places every detection as Pending"; since 3.4, `stackon` sets the new flow Active by
  default, so detections land Active and plan steps sit beneath an Active top. MEM's turn-end
  check was aligned 2026-07-17 to warn only on a non-Active top. What remains is the narrower
  boundary decision (U2) and a re-measurement before building anything.

## Unresolved Issues

- **U1 — where does 2.13.3's incoming entity come from?** The dedupe comparison needs the NEW
  task's entity at the stackon decision point, but under the 3.4 design NLU stacks first and
  fills afterward — the values genuinely do not exist yet. Candidate resolutions: (a) pass what
  IS known at decision time (the session's grounded active entity + any payload entity) as a
  partial identity for the comparison; (b) move the dedupe decision to after `fill_slots`, and
  merge/split flows post-fill when identity turns out equal/different; (c) NLU runs a cheap
  entity pre-extraction before stackon on same-type collisions only. Each has costs: (a) can
  compare stale grounding, (b) re-opens the stack after the announcement entry was written,
  (c) adds a model call to a hot path.
  **RESOLUTION (pending Derek).**
- **U2 — 2.13.5 boundary enforcement: still needed, and if so, invalidate or auto-run?** The
  Pending-tower mechanism is gone with stackon-Active; a Pending top can still form only through
  the agent's own `active=false` stackon it never runs. Options: measure first and drop the task
  if the warning stays quiet across a fresh 8-sample run (recommended); or land the spec's
  invalidate-and-pop enforcement anyway as a cheap invariant.
  **RESOLUTION (pending Derek).**
- **U3 — 2.13.1 prompt shape: one candidates block or two?** The spec adds a `<shown_candidates>`
  block alongside the existing `<pending_question>` (which already renders the same records when
  an ambiguity is open). Two blocks can render the same list twice with different guidance.
  Recommendation: one rendering — always append the candidates block when `grounding['choices']`
  is non-empty, with the pending-question framing added on top only when an ambiguity is open.
  **RESOLUTION (pending Derek).**

## Todo List

Ordered by dependency; U-numbers reference the Unresolved Issues above.

- [ ] **T1 — design rulings (Derek).** U1 (the 2.13.3 identity source — blocks T4), U2 (whether
  2.13.5 still gets built), U3 (the 2.13.1 block shape — cheap to settle, affects T2).
- [ ] **T2 — 2.13.1 plural grounding.** Add `status` to the choice record at the write site
  (`research.py:93`); render the candidates into the fill prompt whenever `grounding['choices']`
  is non-empty (per the U3 ruling); plural-selection guidance (one entity per pick; status/ordinal
  filters resolve against the shown records only). Deterministic cases: "both", "all of them",
  "the drafts", ordinal subsets; consumed-choice clearing unchanged. No dependency on T3/T4.
- [ ] **T3 — 2.13.2 pop-promotion contract.** `FlowStack.pop()` makes the promotion explicit;
  `_manage_flows` runs `_top_policy` only when a promotion happened; `_top_policy` receives the
  promoted flow so it cannot select a different Active entry. Reconcile the call sites the 3.4/3.5
  work added: `activate_flow`'s `popped` list, the plan-marker removal (both spots), and the
  `_execute_click` path. Verification: the five stack cases + invocation counts.
- [ ] **T4 — 2.13.3 entity-identity dedupe.** Per U1's ruling. Depends: T1.
- [ ] **T5 — 2.13.4 verification only.** Confirm the 3.4 announcement entry satisfies every case
  in the section's list (with/without ambiguity, confirmation-waiting, same-flow fill, failed
  stackon) — tests only, no production change expected.
- [ ] **T6 — 2.13.5 per U2's ruling.** Either drop with a recorded measurement, or the
  invalidate-and-pop boundary enforcement. Depends: T1.
- [ ] **T7 — verification.** Suites green; seed-212 8-sample run read against the 2026-07-09
  baseline; expect B01.C07 to flip on T2.
