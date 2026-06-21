# Master Plan — Transfer the spec → Hugo

The roadmap for bringing the **Hugo** implementation up to the master spec (`_specs/`). This is the
analogue of the spec's `checklist/` build phases, but adapted: Hugo already has working code, so each
step is a *transfer/refactor* against current state, not a from-scratch build.

- **Master Plan** (this file) = the major steps. Each has a goal, a deliverable, and a sub-plan.
- **Sub-plans** = `step_<N>_<slug>.md` in this directory = the minor steps of major step N, with file:line
  detail, new-concept shapes for approval, per-step verification, and embedded decisions.

Source material: `architecture.md`, `modules/{nlu,pex,mem}.md`, the 9 `components/*.md`, the 6
`utilities/*.md`, and the prior gap audit `_review/charlie_spec_audit.md` (stale on the legacy/RES items —
those are already removed; superseded where it conflicts with current code).

---

## Already done (do not re-build)

The recent cleanup landed most of the PEX/agent core. Verified present and spec-conformant:

- Orchestrator-only turn loop — `_MAX_ROUNDS`, `_final_emit` wrap-up, dedup/`_guarded_call`, no RES, no
  `_take_turn`, no response templates (`agent.py`, `pex.py`).
- 7-intent taxonomy with `Clarify`, no `Internal` (`ontology.py:4-11`); 16 flows.
- Three-tier frozen system prompt — stable/context/volatile, built once (`for_orchestrator.py:192-208`).
- Read-only domain allowlist — exact match to spec's six (`pex.py:47-48`).
- Grounding-gated `complete_flow` (`dialogue_state.py:221-228`); 6-hook framework; 8-code violation vocab.
- `store_preference` + `append_to_scratchpad` tools wired (`pex.py:157-159`); `compression` config +
  compaction (prune + middle-out summary + protect head/tail).
- Flow/tool grammar fully conformant — all 16 dax codes valid ascending-order, 12+4 slot hierarchy,
  `_success/_error/_message` contract, service-raises→PEX-boundary validation.
- `understand(op=react/think/contemplate)` single NLU entry + parallel-thread gating for the active-entity
  branch (`agent.py:67-80`).
- **Identity & dead-config cleanup (former Step 0, done 2026-06-21):** Hugo-local `naturalize` override +
  `_TASK_SUFFIXES` entry dropped; `key_entities`→`[post, section, snippet, channel]`; RES / template /
  file-identity comment residue removed. Offline suites green (324 passed / 0 skipped / 0 failed).
  `persona.name` is Hugo (E15 resolved).

---

## Decisions (locked with Derek, 2026-06-21)

- **Scope = core now, defer aspirational.** Build the structural skeleton; ship the speculative tier
  as marked "designed-not-built" stubs. See the Deferred register below.
- **New concepts = MEM approved, Plan-flow held.** Approved to create: the L2 `user_preferences` + L3
  `business_context` components and a typed `Preference` record, with `MemoryManager` as the facade over the
  three tiers. **Held for separate discussion:** the Plan-flow sentinel. Each approved concept's shape is
  described in its sub-plan before any code.
- **Intent model = adopt the spec's PEX System-1 hint.** PEX emits a coarse-intent hint inside its own
  reasoning; NLU drops its separate `_classify_intent` call (`nlu.py:259,309`) and flow-detection becomes the
  authoritative intent write. Highest-regression-risk change → gated behind the trace eval (Step 1).
- **Plan lifecycle = minimal.** Decomposition into ordered `stackon`s + `plan_id` progress + depth
  8→16. Defer replanning, completion-assessment, multi-active concurrency, LATS.

---

## The major steps

Effort key: S ≈ <½ day, M ≈ 1–2 days, L ≈ 3+ days. "Gated" = waits on a listed decision (above) or an embedded decision (below).

> **Step 0 (Identity & dead-config cleanup) — DONE 2026-06-21, dropped from the roadmap.** Recorded under
> "Already done" above; its sub-plan file is retired. The one open thread it surfaced (`persona.name`) lives
> on as decision **E15**.

### Step 1 — Eval gate: the L2a trace-replay runner · **M–L** · `step_1_evals.md`
- **Goal:** Turn the 10 approved trajectories + `tolerance_rules.md` into a runnable regression gate before
  any risky behavioral change.
- **Deliverable:** A trace-replay runner that runs a fresh orchestrator session, compares its tool-call
  trajectory against the approved `<nn>_*.json` under the tolerance call-classes, and reports the spec's
  scoring modes; plus a cached-vote mechanism for deterministic replay. Resolve the two approval TODOs inside
  `tolerance_rules.md` (06 ambiguity-ask shape; 07 `plan_id` linkage).
- **Depends on:** nothing structural. **Early enabler** — gates Step 3 especially.

### Step 2 — MEM, the Head · **L** · `step_2_mem.md`
- **Goal:** Stand up memory as a real module with the three tiers and the skill surface (synchronous facade;
  the continuous loop is deferred).
- **Deliverable:** `MemoryManager` as the facade owning L1 (Context Coordinator) / L2 (`user_preferences`) /
  L3 (`business_context`); `recap`/`recall`/`retrieve` as the public skill surface; a typed `Preference`
  record with endorsed-vs-guessed rendering + the caution dial (shape only). Auto-promotion, proactive push,
  and vector retrieval land as designed-not-built stubs.
- **Depends on:** the component shapes approved above (confirm in the sub-plan). Foundational facade other steps read.

### Step 3 — NLU belief, ambiguity & the intent rework, the Heart · **L** · `step_3_nlu.md`
- **Goal:** Bring NLU belief + ambiguity behavior to spec, and execute the intent-model change (PEX System-1 hint).
- **Deliverable:** PEX-hint intent model (remove `_classify_intent`); minimal-schema scratchpad entries
  (`version`/`turn_number`/`used_count`) + synchronous NLU review at turn points; cross-turn ambiguity
  binding (treat the reply as the *answer*, not a re-detect); gate low-confidence entity repairs instead of
  committing silently; halt-on-intent-split; wire the idle `contemplate` trigger; wire the unused
  `should_escalate` cross-turn escalation; cap `pred_flows` to top-3 (`dialogue_state.md:131`, moved from
  former Step 0 — it's a belief-shape change).
- **Depends on:** Step 1 (eval gate) for the intent rework; Step 2 (scratchpad/MEM ownership).
- **Gated:** continuous scratchpad review is the deferred (stub) variant.

### Step 4 — PEX rendering & prompt conformance · **M** · `step_4_pex.md`
- **Goal:** Close the style-guide and prompt-assembly gaps.
- **Deliverable:** inject the defined-but-dead closing reminder (slot 7, `general.py:12`); resolve the
  agentic-skill style-guide exemption; raise exemplar counts toward 7–10; config-promote the loop bounds +
  per-flow call-caps. Multi-artifact curation stays deferred (needs concurrency).
- **Depends on:** mostly independent; can run alongside Step 2/3.

### Step 5 — Plan / Workflow Planner (minimal) · **M** · `step_5_plan.md`
- **Goal:** Make the `Plan` intent functional (minimal lifecycle).
- **Deliverable:** a decomposition vehicle that turns a multi-step request into ordered `stackon`s under one
  `plan_id`; `plan_id` minting + progress count + cascade-invalidate; depth 8→16. Agenda tracked via
  `plan_id` + scratchpad (no Plan-flow object — that's held). Replanning/completion/concurrency/LATS
  deferred.
- **Depends on:** Step 1 (eval); benefits from Step 2/3.

### Step 6 — Config / Eval / Server / Blocks infra · **M–L** · `step_6_infra.md`
- **Goal:** Conform the remaining infrastructure surfaces.
- **Deliverable:** a validating config loader + ontology merge (`config.flows`); resolve
  `content_validation`↔`response_constraints`; enforce session limits (`max_turns`/`max_flow_depth`); WS
  mid-turn progress streaming; reconcile the blocks rendering model (spec fix); re-baseline the parity oracle;
  apply consistent designed-not-built markers across config.
- **Depends on:** Step 1 (parity oracle convergence).

---

## Sequencing

```
Step 1 (eval gate)─┐─► Step 3 (NLU + intent rework, gated by Step 1)
Step 2 (MEM) ──────┘        │
Step 4 (PEX) — parallel     ▼
Step 5 (Plan minimal) ◄── after 1/2/3
Step 6 (infra) ◄── after Step 1 (oracle)
```

(Step 0 cleanup is already done.) Start 1 and 2 in parallel — 1 is the gate, 2 is the foundation. 3 (the
risky intent change) only after 1 can verify it. 4 is independent. 5 and 6 last.

---

## Embedded decisions (resolve in the relevant sub-plan; recommendations given)

These don't reshape the roadmap, so they're tracked here and decided in-flight, not up front.

| # | Decision | Step | Recommendation |
|---|---|---|---|
| E1 | Memory tools: alias `recap/recall/retrieve` over existing impls vs. rename outright | 2 | Add the 3 as the public surface over `compile_history`/`manage_memory`/`search_faqs`; don't rename. |
| E2 | Decomposition vehicle: discrete `plan` skill vs. prompt-only orchestrator guidance | 5 | Discrete `plan` skill — testable, reusable for any later replan/complete. |
| E3 | Blocks rendering model: `inline` attr vs. `top/bottom` panel zones (spec self-conflict) | 6 | Converge the spec to Hugo's panel-zone model; don't add `inline`. |
| E4 | `content_validation` (flow allowlist) vs. `response_constraints` (output bounds) | 6 | Keep `content_validation`; have spec §12 absorb it; wire `response_constraints` only if length-bounds wanted. |
| E5 | Compaction summary placement: checkpoint vs. event-log turn entry | 6 | Keep checkpoint; document it as the vehicle. |
| E6 | Panel CRUD: direct router handlers vs. route through NLU `react()` | 6 | Keep direct handlers; add a spec note. |
| E7 | Tool manifest `scope`/`dispatch`/`output_schema` fields | 6 | Document Hugo's code-side routing; don't back-fill the manifest. |
| E8 | Parity oracle provenance (captured from deleted legacy pipeline) | 1/6 | Re-baseline from an approved orchestrator run; converge with the L2a trace model. |
| E9 | Style guide: 8-slot/JSON format for agentic PEX skills | 4 | Exempt agentic skill bodies (they use tools, not a JSON return); keep 8-slot/JSON for single-shot prompts. |
| E10 | Config-promote loop constants (`_MAX_ROUNDS`/`_MAX_CORRECTIVE`) | 4 | Promote, for consistency with the already-config-driven `compression`. |
| E11 | Basic-tier persistence story (`session.persistence.backend: postgres` unused; sessions are file-based) | 6 | Document file-based as the basic-tier truth; fix the config key. |
| E12 | Re-route ownership: NLU `contemplate` vs policy `fallback()` (Hugo's docs conflict) | 3 | `contemplate` owns cross-flow re-routes; `fallback()` owns within-policy recovery. |
| E13 | Scratchpad physical location: keep on `MemoryManager` vs relocate to the World | 2 | **RESOLVED 2026-06-21:** extract to a `SessionScratchpad` component owned by the World; NLU sees it as `nlu.scratchpad` beside `nlu.ambiguity`. Done as part of Step 2. |
| E14 | Low-confidence entity-repair contract: commit value vs withhold until verified | 3 | Write as prediction (`ver=False`); PEX won't act until verification flips `ver=True`. |
| E15 | Assistant display name | — | **RESOLVED 2026-06-21:** the assistant is Hugo (the orchestrator setup was promoted to the official `assistants/Hugo/`). `persona.name: "Hugo"` is correct; tool-desc refs `tools.yaml:492,599` are correct as-is. |

---

## Deferred register — "designed, not yet built"

Parked by scope. Each gets a stub + a `# designed-not-built` marker where the seam lives, so the spec stops
reading present-tense and a future implementer finds the hook.

- Real parallel **continuous** loops (NLU/PEX/MEM as event-triggered background loops). Today: synchronous
  at the turn points.
- MEM **scratchpad auto-promotion** (salience + `used_count` LLM-judge). `used_count` plumbing stays.
- MEM **proactive push** channel (prefetch + anticipatory scratchpad notes).
- **Multi-active flow concurrency** + the contiguous-Active invariant + N-artifact curation.
- **LATS** decomposition search (spec itself marks optional).
- L3 **vector/embedding** retrieval + `agent.md` cold-start ingestion. Today: in-RAM LLM rerank
  (`faq_service.py`).
- **Plan-flow sentinel** — held for discussion; minimal Plan avoids it.
- `Turn.form` multimodal (speech/image); tool-approval / lethal-trifecta HITL gate; telemetry endpoint;
  responsive block hints.

---

## Verification strategy

- **Offline gate suites** (no LLM, fast) — keep green after every step:
  `test_artifacts.py`, `unit_tests.py`, `test_nlu_module.py` (baseline 324 passed, 0 failed — no skips).
- **Test cwd gotcha:** run pytest with cwd + `sys.path[0]` set to the `assistants/Hugo` dir, or
  `import backend` may resolve to another assistant's backend. Use the wrapper documented in the test sub-plans.
- **Trace gate** (Step 1 deliverable) — the L2a replay runner gates behavioral steps (esp. Step 3).
- **Parity harness** (`run_parity.py`, 3-axis) — CLI, expensive; re-baseline per E8.
- Each sub-plan ends with its own concrete verify commands.
