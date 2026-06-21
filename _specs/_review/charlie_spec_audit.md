# Charlie ↔ Phoenix Spec Audit

Round 2 of idea-mining: instead of legacy Soleda, we compare the **Charlie implementation** against the
**Phoenix spec** to catch details the spec missed or drifted on. Seven parallel audits, one per subsystem.

**Categories**
- **(a)** Charlie does X, the spec is silent → a chance to strengthen the spec.
- **(b)** Conflict — spec says Y, Charlie does Z → confirm whether Charlie is deprecated or the spec is wrong.
- **(c)** Spec says Y but is thin on the how → call out the forking decisions so implementation goes smoothly.

Nothing here is edited into the specs yet — **held for review**, same as the last batch.

---

## Big decisions (read these first)

These are cross-cutting calls. Each one resolves a whole cluster of the per-subsystem findings below.

### D1. Legacy substrate vs. orchestrator — confirm what's deprecated
Charlie carries **both** paths, switched by `config['feature_flags']['orchestrator']` (`agent.py:63`):
- **Legacy**: `_take_turn` runs a fixed `NLU.understand() → PEX.execute() (while keep_going) → RES.respond()`
  pipeline (`agent.py:70-111`), with `res.py`, `templates/`, a `naturalize()` second LLM pass, and
  `state.keep_going` as a stored flag.
- **Orchestrator**: `_orchestrate` / `agent.py:_run_loop` (`agent.py:207-264`) — one bounded LLM loop
  (`_MAX_ROUNDS`), Hermes termination, `write_state` ops, frozen three-tier system prompt.

The spec describes **only** the orchestrator. If the orchestrator is canonical (per our prior work it is),
then this single decision confirms a large batch of (b) findings as "Charlie legacy, correctly dropped":
`res.py`, `templates/`, `naturalize()`, `keep_going`-as-flag, the fixed pipeline, the `orchestrated`
substrate flag, `BaseFlow.interjected`/`fall_back`. **Decision: is the legacy substrate dead, or still a
supported fallback the spec should acknowledge?**

### D2. Where does coarse intent classification live — NLU or PEX?
Genuine conflict. Charlie classifies intent **inside NLU** (`nlu.py:379-388` `_classify_intent`, with its own
`build_intent_prompt`). The spec (`nlu.md:100-104`) says coarse intent lives **up in PEX** (System-1), passed
as the optional `intent` hint to narrow `detect_flow`. One of the two is stale. **Decision needed.**

### D3. Is MEM actually a continuous parallel loop?
Three audits independently found MEM is **synchronous / post-hook only** in Charlie — not an event-triggered
continuous loop, and the **proactive push channel** (prefetch + scratchpad notes) is not implemented. The
spec (`mem.md`, `architecture.md`) leans hard on "three continuous LLM-loops running in parallel." **Decision:
is the parallel-loop framing aspirational (soften/mark the spec) or an implementation gap to close?**

### D4. How elaborate is the NLU ensemble, really?
Spec (`nlu.md:132-153`) describes a 3-round escalating ensemble with alignment-as-multiplier and abstention.
Charlie (`nlu.py:396-427`, `_tally_votes` 589-604) does a **single round** of 3 fixed-weight voters
(0.20/0.45/0.35), no escalation, no alignment multiplier, no abstention path. **Decision: is the elaborate
ensemble the target (keep spec, mark as not-yet-built) or over-specified (simplify spec to match Charlie)?**

### D5. Spec-ahead-of-code items — label them as "designed, not built"
Several spec sections describe behavior Charlie has **not** implemented. These aren't errors, but a future
implementer will trip if the spec reads as present-tense. Candidates to tag explicitly: typed preference
record + caution dial (we just added these), trajectory playbooks, scratchpad auto-promotion (salience +
`used_count` judge), Plan lifecycle / replanning / LATS, `Turn.form` multi-modal (speech/image), proactive
push channel. **Decision: add a consistent "designed, not yet wired" marker to these?**

---

## (b) Conflicts — verify deprecated vs. spec error

| # | Finding | Charlie | Spec | Call |
|---|---|---|---|---|
| b1 | Intent classification location | `nlu.py:379-388` does it in NLU | `nlu.md:100-104` puts coarse intent in PEX | **D2** |
| b2 | RES module exists | `res.py` (template fill + naturalize + flow-pop + checkpoint) | `pex.md:59` PEX words reply directly, no RES | **D1** |
| b3 | Response templates | `templates/*.py` intent-keyed TEMPLATES + `block_hint` | `blocks.md:70` "no response templates" | **D1** |
| b4 | Naturalization pass | `res.py:93-110` second LLM call to smooth filled template | spec: single-pass voice skill | **D1** |
| b5 | `keep_going` stored | `pex.py:964` reads `state.keep_going`; `draft.py:168` writes it | spec: loop control, not stored | **D1** |
| b6 | Intent taxonomy / `Clarify` | `nlu.py:40` 6 flow-owning intents, no `Clarify` | `dialogue_state.md:12-20` 7 incl. NLU-only `Clarify` | verify |
| b7 | Flow flags on state | `dialogue_state.py:59-62` keeps `keep_going/has_issues/has_plan/natural_birth` | `dialogue_state.md:105-116` "no flag block" | **D1** |
| b8 | `Turn.form` field | `context_coordinator.py:36-62` text-only, no `form` | spec requires text/speech/image/action | **D5** (multimodal future) |
| b9 | Config key `response_constraints` | `config.py:17` requires `response_constraints` | `configuration.md:255` `response:` w/ `composition`+`constraints` | concrete fix — pick one |
| b10 | Closing reminder (slot 7) | `general.py:10` defines `SLOT_7_REMINDER`, **never injected** | `style_guide.md:171` mandates it | gap or aspirational? |
| b11 | Exemplar counts | many PEX skills 1-4; intent 21 | style guide 7-10 PEX, ~32 intent | spec targets realistic? |
| b12 | Plan policy | `policies/plan.py` empty ("removed in 48→16") | `workflow_planner.md:319-378` full Plan lifecycle | **D5** |
| b13 | Checkpoints | `context_coordinator.py:117-129` in-memory, ephemeral | `context_coordinator.md` long-term resumption | gap |
| b14 | Canonical vs domain tool split | all Charlie tools domain-specific, no split structure | `tool_smith.md:656-694` canonical/domain split | content domain — likely fine, confirm |

---

## (a) Charlie has it, spec silent — strengthen the spec

**NLU / detection**
- a1. `nlu.py:114-156` `detect_and_fill()` — a single orchestrator-facing entry that detects + fills + repairs
  and returns predictions **without** mutating state (PEX decides to stack/clarify). Spec only lists the
  separate `detect_flow`/`fill_slots` tools. Worth documenting as the orchestrator's NLU surface.
- a2. `ambiguity_handler.py:25` hard `nlu_confidence_min=0.64` gate, and `:70` cross-turn escalation
  (`ambiguity_escalation_turns=3`). Spec is silent on the threshold and the escalation trigger.

**PEX / flow stack**
- a3. `pex.py:498-501` `write_state op=pop_completed` **dual-writes** the state file *and* the live
  `flow_stack`. Spec implies the state file is the single authority — clarify the mirror.
- a4. `READ_ONLY_DOMAIN_TOOLS` allowlist (`pex.py:36`) the orchestrator may call directly. Spec mentions a
  read-only allowlist but never lists it.

**Slots / services**
- a5. `slots.py` `add_one` (GroupSlots, append) vs `assign_one` (single-value, replace) mutation semantics —
  clean and consistent, but the slot spec says nothing about the contract.
- a6. Service-layer **validation** raising caught at the PEX boundary → `_error:'validation'`
  (`services.py:249-285` outline checks; `post_service.py:195`; `content_service.py:155`). Spec's error
  contract says tools report failures but never says where validation runs.
- a7. `slots.py` every class emits its own `json_schema()` fragment — slot-type → JSON-schema mapping lives on
  the class. Spec shows tool schemas but never how slots map to schema. (c)-ish; document the pattern.
- a8. `ImageSlot.position` (`slots.py:553`) for insertion point; `RangeSlot` default time keywords
  (`slots.py:474`). Reasonable domain extensions, undocumented.
- a9. Dead/unused fields worth a cleanup note (not spec gaps per se): `SourceSlot.active_post` (`slots.py:115`),
  `FreeTextSlot.verified` (`slots.py:212`), `BaseFlow.interjected`/`fall_back` (`parents.py:7,11`).

**MEM / context**
- a10. `context_coordinator.py` keeps **two** overlapping logs — in-memory `Turn` history + `messages.jsonl`;
  `compress_messages` (`:174-261`) rewrites the file wholesale on compaction. Spec treats the message list as
  an unmentioned implementation detail; worth a sentence.
- a11. Compaction writes its rolling summary into a **checkpoint**, whereas the spec says the summary should be
  a special **turn entry in the event log**. Different placement, same goal — pick one.
- a12. `faq_service.py:9-34` L3 retrieval is **whole-corpus LLM rerank in RAM**, no embeddings/vector DB
  (embeddings are our declared TODO). Document this as the interim retrieval until the vector rung lands.

**Agent core / config**
- a13. `world.py:47-89` session persistence layout: `database/sessions/<id>/` holding
  `state.json` + `messages.jsonl` + `scratchpad.jsonl`, lazily created on `open_session`. Spec says "the dir
  is the persistence format" but never gives the layout.
- a14. Compaction is fully wired in code (`agent.py:326-345`, threshold + protect-tail) but
  `configuration.md` has **no `compression` section**. Add the config surface.
- a15. `agent.py:23-34` loop guardrail constants `_MAX_ROUNDS=8`, `_MAX_CORRECTIVE=3`, nudge/wrap-up
  messages — concrete numbers the spec leaves abstract. Consider promoting to config.
- a16. `prompt_engineer.py:216-218` per-flow call-cap bump (8 → 16 for audit/refine/rework/compose/simplify/
  add). Spec mentions an 8-iteration cap but not the overrides.

---

## (c) Spec thin on the how — call out the forking decisions

- c1. **Entity repair → clarification gate.** `nlu.py:227-308` runs the exact→lexical→LLM ladder but **commits
  the repaired value silently**; it never declares `confirmation` on a low-confidence repair the way
  `nlu.md:173-182` implies. Spec should state when a repair commits vs. asks.
- c2. **Slot-fill validation fallback.** `nlu.py:456-466` makes a single LLM call and logs+returns on an
  invalid slot shape (`:461`). Spec describes the two phases but never the schema-violation fallback.
- c3. **`pred_flows` cap.** `nlu.py:600-604` stores *all* ranked candidates; `dialogue_state.md:131` says top-3.
  Decide whether to cap or keep-all-for-logging.
- c4. **Slot priority in the LLM schema.** `nlu.py:69-82` filters by priority in Python; the schema handed to
  the model carries no `priority`/`criteria`. Spec should say whether priority rides in the schema or the prose.
- c5. **Data-first ordering in starters.** Starters emit `<task>` before `<resolved_details>`
  (`prompts/pex/starters/*`), but `style_guide.md:128` makes grounding slot-1. Likely a layer conflation
  (system-prompt grounding vs. per-turn message), but worth an explicit note so it isn't "fixed" wrongly.
- c6. **Completion-record vehicle.** Charlie writes completions via `memory.write_completion()`
  (`base.py:230`) keyed by flow name; the spec implies the scratchpad is the vehicle and that dialogue state
  owns the flow↔`turn_id` mapping. Reconcile the path.
- c7. **Plan decomposition / replanning / LATS** (`workflow_planner.md:319-385`) — no code exists. If kept,
  mark as designed-not-built and note the open forks (where the agenda lives, replanning trigger). → **D5**
- c8. **Grounding-gated completion.** Spec is clear an entity-grounded flow can't `complete_flow` while
  `grounding.post` is empty; Charlie enforces via `_verify_active_post` (`pex.py:246`) + grounding block.
  Aligned — but the spec should point at the enforcement site so it isn't re-litigated.

---

## Confirmed aligned (no action — recorded so we don't re-audit)

- SourceSlot entity parts `{post, sec, snip, chl, ver}` and the `ver`/verified mechanic match exactly
  (`slots.py:124-147` ↔ `dialogue_state.md:52`).
- Slot type hierarchy 12 universal + 4 domain-specific (ChannelSlot, ImageSlot, ProbabilitySlot, ScoreSlot).
- Service `_success` / `_error` / `_message` error contract (`services.py:100` ↔ `tool_smith.md:592`).
- No code-execution tools — content domain correctly skips the code-gen robustness section.
- Snapshot/undo grounding-repair pattern (`services.py:329-385`, `post_service.py:371`) matches the spec's
  "kept as-is" note.
- Prompt caching is Claude-only by design; reasonable, just undocumented as such.

## Expected divergences (spec enrichments we just added — do NOT "fix" Charlie to match)

- Typed Preference Record + caution dial — Charlie stores bare `dict[str,str]` (`memory_manager.py:15`);
  compatible as the degenerate case. Not yet wired, by design.
- Trajectory playbooks — no L2 trajectory store in Charlie.
- Scratchpad auto-promotion (salience + `used_count` LLM-judge) — `used_count` exists, scoring/promotion does not.
- Embedding/vector retrieval — declared TODO; Charlie uses keyword/ID + LLM rerank.
- Endorsed-vs-guessed preference rendering — `for_orchestrator.py:184` renders flat bullets today.
