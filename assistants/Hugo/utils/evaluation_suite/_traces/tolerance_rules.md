# Trace replay tolerance rules (changes.md §9.2 item 4) — DRAFT for review

These rules define when a replayed orchestrator run **matches** an approved trajectory in this
directory. They live next to the sidecars, not hard-coded in the harness, so approving a
behavior change means editing this file (plus the sidecar) in the same PR. Status: draft —
finalized with the user when the 10 sidecars are approved.

## Vocabulary — call classes

Every tool call in a trace belongs to one class:

- **required-ordered** — must appear, in the listed relative order. Other calls may interleave.
- **counted** — must appear exactly N times anywhere in the turn (order-free). Used for
  persistence-class tools where double-writes are bugs.
- **incidental** — may appear any number of times, anywhere; never order-pinned and never
  counted. Reads only.
- **forbidden** — must not appear at all in the named turn.
- **bypass** — code-synthesized calls on a pure-click turn (decision 13). Guaranteed by the
  bypass code path, so a replay matches them by construction; listed for completeness only.

## Global rules (apply to every trajectory)

G1. `detect_and_fill` precedes any `write_state` that fills slots (`op=update_flow` with
    `fields.slots`) for the same flow, and precedes the first `activate_flow` of the turn.
G2. Persistence-class calls are **counted**: `activate_flow` per flow per turn, and
    `write_state` with op in {`stackon`, `fallback`, `pop_completed`} per target flow.
    A replay with extra stacked or re-run flows does not match.
G3. `read_state`, `read_scratchpad`, and the read-only domain allowlist (`find_posts`,
    `read_metadata`, `read_section`, `search_notes`, `list_channels`, `channel_status`) are
    **incidental** — never order-pinned, never counted.
G4. On clarification turns (the agent ends the turn with a question, no flow completed):
    domain writes are **forbidden** — no `activate_flow` may complete a flow that mutates a
    post or channel. `handle_ambiguity` is the expected ask path.
G5. Each completed flow produces exactly one completion record `{flow, summary, metadata}`,
    visible either as the `activate_flow` tool result (loop turns) or in the scratchpad
    (bypass turns). Summary wording is free; the `flow` key and metadata KEYS must match.
G6. The final utterance is never compared by string equality — task adequacy is judged on the
    parity harness axis 3, not here. A trace replay only checks the call structure.
G7. `write_state` op=update_flow slot VALUES must carry the same entity grounding (post / sec
    ids) as the approved trace when the trajectory pins specific posts; free-text slot values
    (instructions, style notes) are not compared.
G8. Failed calls that the model immediately corrects (an `ok=false` followed by a successful
    retry with fixed args) are tolerated and not counted, as long as the corrected call obeys
    the rules above. Three consecutive failures = no match (the loop's corrective cap).

## Per-trajectory rules

Each rule block names the sidecar it constrains. N/A classes are omitted.

### 01_draft_create
- required-ordered: `detect_and_fill` → `write_state(op=stackon, create)` →
  `activate_flow(create)`
- counted: `activate_flow(create)` ×1
- forbidden: running any second flow; `handle_ambiguity(declare)`
- completion: `create` with metadata keys ⊇ {post_id}

### 02_revise_simplify
- required-ordered: `detect_and_fill` → `write_state(op=stackon, simplify)` →
  `activate_flow(simplify)`
- counted: `activate_flow(simplify)` ×1
- forbidden: running any other Revise-family flow (the near-synonym trap: polish, rework)
- completion: `simplify` grounded on the seeded post (G7)

### 03_publish_preview
- required-ordered: `detect_and_fill` → `write_state(op=stackon, preview)` →
  `activate_flow(preview)`
- counted: `activate_flow(preview)` ×1
- forbidden: `release`, `syndicate`, `schedule` runs (preview is read-only on channels)

### 04_research_compare
- required-ordered: `detect_and_fill` → `write_state(op=stackon, compare)` →
  `write_state(op=update_flow)` carrying BOTH seeded posts in the source slot →
  `activate_flow(compare)`
- counted: `activate_flow(compare)` ×1
- forbidden: any domain write; answering from direct reads without running the flow
  (compare needs analysis tools outside the allowlist — a replay that never runs the flow does not match)

### 05_slot_clarify
- turn 1 required-ordered: `detect_and_fill` → the turn ends asking for the missing tone.
  The ask may be plain text after detect_and_fill reports the unfilled elective, a
  `handle_ambiguity(declare)`, or a `activate_flow(tone)` returning a question — any ask
  path matches. The flow may or may not be staged on turn 1.
- turn 1 forbidden: a completed `tone` run; any content write.
- turn 2 required-ordered: tone slot filled (`write_state op=update_flow` carrying
  `custom_tone` or `chosen_tone`) → `activate_flow(tone)` completing.
- counted: completed `activate_flow(tone)` ×1 across the round (turn 2 only).

### 06_ambiguity_escalation
- turn 1 required: the agent surfaces the two candidate posts and asks — no flow run
  completes, no flow staged.
- turn 2: a second, more pointed ask (concrete options); still no domain write.
- forbidden (both turns): `activate_flow` of any flow that writes content; `write_state`
  marking any flow Completed.
- NOTE for review: the design intent (decision 18) is that asks go through
  `handle_ambiguity(declare)` so AmbiguityHandler keeps the escalation bookkeeping. The
  recorded run asks directly in plain text without declaring (it does so on 05's turn 1 in
  some runs). The user decides at approval whether bare-text asks are acceptable here or
  whether `handle_ambiguity(declare)` becomes a required call — the rule above encodes the
  observed trace until then.

### 07_plan_chain
- required-ordered: `detect_and_fill` → `write_state(op=stackon, triage)` →
  `activate_flow(triage)` (the plan) → first plan sub-flow staged and run on the
  later turns (recorded: rework on the Motivation section), ending with the sub-flow's
  completion record.
- handoff: the sub-flow must run AFTER triage's plan result is available to the
  loop (the activate_flow tool result or a `read_scratchpad` of completion records); the
  sequence ends with at least one sub-flow completion record.
- counted: each flow run ×1 per turn; a clarification round inside the sub-flow
  (rework asking for direction) is a legitimate extra run of the SAME flow once the
  answer arrives.
- NOTE for review: `plan_id` was removed in round 5.1 — the stack itself holds the plan
  (all sub-flows stacked at once); whether stronger plan-linkage evidence is needed is an
  approval decision.

### 08_click_bypass
- turn 1: same shape as 01 (create).
- turn 2 (pure click): bypass-class only — `activate_flow(outline)` + `respond(outline)`
  synthesized by code; **no loop calls may appear** (a `detect_and_fill` or LLM round on a
  pure click is a regression of decision 13).
- completion: `outline` present in the scratchpad for turn 2.

### 09_memory_recall
- turn 1: the preference write goes through `activate_flow(preference)` (the flow owns L2
  writes) — exactly one persistence write; key/value naming free.
- turn 2 required: a real L2 read (`manage_memory read_preferences` or `activate_flow(recall)`)
  BEFORE the final utterance — answering from the frozen prompt alone does not match, because
  the turn-1 write postdates the snapshot (decision 8). The reply must surface BOTH the
  pre-seeded tone preference (snapshot) and the turn-1 word-count preference (live read).
- forbidden: any post/content write in either turn; storing the preference only in the L1
  scratchpad (wrong memory tier).

### 10_grounding_switch
- turn 1 required-ordered: `detect_and_fill` → stack and run `inspect` grounded on post A;
  completion metadata references post A.
- turn 2 required-ordered: grounding moves to post B (`write_state` with grounding.post=B, or
  a fresh `detect_and_fill`+fill carrying B) BEFORE `activate_flow` runs; the flow that ran
  must have completion metadata that must reference post B, not A.
- forbidden: turn 2 acting on post A — stale grounding is the failure this trajectory exists
  to catch (it caught the real `_stage_flow` completed-flow-reuse bug when first recorded).

## Re-approval discipline

A deliberate behavior change that alters any approved trace requires: re-record, re-render the
sidecar, the user re-checks `APPROVED: [x]`, and the PR body justifies the diff — the same rule
as snapshot sidecars (AGENTS.md).
