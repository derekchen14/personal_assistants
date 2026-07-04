# Master Plan — Transfer the spec → Hugo

The roadmap for bringing the **Hugo** implementation up to the master spec (`_specs/`). Hugo already has
working code, so each step is a *transfer/refactor* against current state, not a from-scratch build.

**We build in demo order, not component order.** Start with the end in mind: every step leaves Hugo able to
do something you can *show*. What sequences the work is "which demo does this unlock?" — not the module
dependency graph alone.

- **Master Plan** (this file) = the major steps in build order. Each leads with the demo it unlocks, then its
  goal and deliverable.
- **Sub-plans** = `step_<N>_<slug>.md` = the minor steps of each major step, with file:line detail,
  new-concept shapes, per-step verification, and embedded decisions. **The `<N>` in a file name is a
  historical identifier — the build order is the demo order below, not the file number.**

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

## Decisions (locked with the user, 2026-06-21)

- **Scope = core now, defer aspirational.** Build the structural skeleton; ship the speculative tier
  as marked "designed-not-built" stubs. See the Deferred register below.
- **New concepts = MEM approved.** Approved to create: the L2 `user_preferences` + L3 `business_context`
  components and a typed `Preference` record, with `MemoryManager` as the facade over the three tiers. Each
  approved concept's shape is described in its sub-plan before any code. There is **no Plan-flow object** — the
  Plan is a skill that stacks existing flows, and PEX judges goal completion.
- **Intent model = adopt the spec's PEX System-1 hint.** PEX emits a coarse-intent hint inside its own
  reasoning; NLU drops its separate `_classify_intent` call (`nlu.py:259,309`) and flow-detection becomes the
  authoritative intent write. Highest-regression-risk change → gated behind the trace eval (Step 1).
- **Plan lifecycle = minimal.** The Workflow Planner skill guides PEX to stack ordered flows; depth 8→16;
  **PEX judges goal completion** (no `plan_id`, no Plan-flow object). Defer replanning and multi-active
  concurrency; LATS dropped.

---

## The end in mind

The whole point of Hugo: **a user collaborates across a multi-turn session to research, draft, revise, and
publish a blog post** — Hugo remembers their style preferences, pulls in business context, asks a clarifying
question when a request is ambiguous, and handles multi-step requests by planning and showing progress.

Working backward, each milestone is the smallest slice that adds **one visible capability** on top of the
last. Build in this order:

| # | Demo you can show once the step is done | Sub-plan |
|---|---|---|
| 1 | **Hugo replies.** A single-flow request ("draft an intro about X") returns a well-formed reply + an artifact the UI renders; the voice matches the style guide. | `step_4_pex.md` |
| 2 | **Hugo remembers.** "I prefer short paragraphs" changes the next draft; a business-context question is answered from L3; session recap works. | `step_2_mem.md` |
| 3 | **Hugo clarifies.** An ambiguous request gets a targeted question; next turn the answer binds correctly; intent routing is right. | `step_3_nlu.md` |
| 4 | **Hugo plans.** A multi-step request decomposes into ordered flows and Hugo runs them to the goal, reporting what got done. | `step_5_plan.md` |
| 5 | **Hugo ships.** Progress streams to the UI mid-turn; session limits are enforced; config is validated on load. | `step_6_infra.md` |

**Why PEX is first.** The turn loop is the substrate of *every* demo: until a user message produces a
well-formed reply + artifact, there is nothing to show for memory, ambiguity, or planning. The orchestrator
loop already exists (see "Already done"), so this step is not a from-scratch build — it makes the turn
*demo-quality* (voice, exemplars, prompt conformance, config-driven bounds) and verifies it end-to-end.

**The eval gate is a parallel track, not a milestone.** The trace-replay runner (`step_1_evals.md`) is owned
by a separate coding agent. It is the measurement track that gates the behavioral steps (exemplars in 1, the
intent rework in 3) and converges the parity oracle for 5 — it does not itself unlock a user-facing demo, so
it sits beside the sequence rather than inside it.

---

## The major steps (build order)

Effort key: S ≈ <½ day, M ≈ 1–2 days, L ≈ 3+ days. "Gated" = waits on a listed decision (above) or an
embedded decision (below). File numbers are historical; the order below is the build order.

> **Step 0 (Identity & dead-config cleanup) — DONE 2026-06-21.** Recorded under "Already done"; its sub-plan
> file is retired. The one open thread it surfaced (`persona.name`) lives on as decision **E15**.

### 1 · Hugo replies — PEX turn & prompt conformance · **M** · `step_4_pex.md`
- **Demo unlocked:** talk to Hugo and get a well-formed reply + a rendered artifact for a single flow — the
  voice matches the style guide and the flow behaves.
- **Goal:** close the style-guide and prompt-assembly gaps so the turn loop's output is demo-quality.
- **Deliverable:** inject the defined-but-dead closing reminder (slot 7 — DONE 2026-07-02); resolve the
  agentic-skill style-guide exemption (E9); raise exemplar counts toward 7–10 (worst: `propose`=1);
  config-promote the loop bounds + per-flow call-caps (E10). Multi-artifact curation stays deferred (needs
  concurrency).
- **Depends on:** mostly independent — starts immediately. Exemplars are a behavior surface; re-check against
  the eval gate as it comes online.

### 2 · Hugo remembers — MEM, the Head · **L** · `step_2_mem.md`
- **Demo unlocked:** "I prefer short paragraphs" changes the next draft (preference recall); a
  business-context question is answered from L3 (`retrieve`); session recap works.
- **Goal:** stand up memory as a real module — three tiers + the skill surface (synchronous facade; the
  continuous loop is deferred).
- **Deliverable:** `MemoryManager` as the facade owning L1 (Context Coordinator) / L2 (`user_preferences`) /
  L3 (`business_context`); `recap`/`recall`/`retrieve` as the public skill surface; a typed `Preference`
  record with endorsed-vs-guessed rendering + the caution dial (shape only). Auto-promotion, proactive push,
  and vector retrieval land as designed-not-built stubs.
- **Depends on:** the component shapes approved above (confirm in the sub-plan). Foundational facade the later
  steps read.

### 3 · Hugo clarifies — NLU belief, ambiguity & the intent rework, the Heart · **L** · `step_3_nlu.md`
- **Demo unlocked:** an ambiguous request gets a targeted clarifying question; next turn the answer binds as
  the *answer* (not re-detected); intent routing is right under the PEX-hint model.
- **Goal:** bring NLU belief + ambiguity behavior to spec and execute the intent-model change (PEX System-1
  hint).
- **Deliverable:** PEX-hint intent model (remove `_classify_intent`); minimal-schema scratchpad entries
  (`version`/`turn_number`/`used_count`) + synchronous NLU review at turn points; cross-turn ambiguity
  binding; gate low-confidence entity repairs (`ver=False`) instead of committing silently; halt-on-intent
  -split; wire the idle `contemplate` trigger; wire the unused `should_escalate` escalation; cap `pred_flows`
  to top-3 (`dialogue_state.md:131`).
- **Depends on:** the eval gate (parallel) for the intent rework; **Step 2 / MEM** for scratchpad ownership.
  Riskiest change — the strongest reason the eval gate must be running when it lands.
- **Gated:** continuous scratchpad review is the deferred (stub) variant.

### 4 · Hugo plans — Plan / Workflow Planner (minimal) · **M** · `step_5_plan.md`
- **Demo unlocked:** a multi-step request ("research competitors, outline, then write the intro") decomposes
  into ordered flows and Hugo runs them to the goal, reporting what got done.
- **Goal:** make the `Plan` intent functional (minimal lifecycle).
- **Deliverable:** the Workflow Planner skill (guidance PEX follows to issue the ordered `stackon`s); depth
  8→16; Plan-aware chaining; **PEX judges goal completion** (no `plan_id`, no Plan-flow object). Replanning +
  concurrency deferred; LATS dropped.
- **Depends on:** working flows (**Step 1 / PEX**); benefits from Steps 2/3; the eval gate covers
  `07_plan_chain`.

### 5 · Hugo ships — Config / Server / Blocks infra · **M–L** · `step_6_infra.md`
- **Demo unlocked:** progress streams to the UI mid-turn; session limits are enforced
  (`max_turns`/`max_flow_depth`); config is validated on load; blocks render via the agreed model.
- **Goal:** conform the remaining infrastructure surfaces.
- **Deliverable:** a validating config loader + ontology merge (`config.flows`); remove
  `content_validation` + `response_constraints` (E4); enforce session limits; WS mid-turn progress streaming;
  reconcile the blocks rendering model (E3); delete the RES test tombstones; re-baseline the parity oracle;
  consistent designed-not-built markers across config.
- **Depends on:** the eval gate (parity-oracle convergence, E8).

### Parallel · Eval gate — the trace-replay runner · **M–L** · `step_1_evals.md`
**Round E1 — DONE 2026-07-03** (PR #2, `round/E1-fast-evals`): the live runner seeds all 96
scenarios (canonical post shape + normalizer), prints wall times against the
`evaluation_suite.md` latency budget, and runs the 8-scenario release gate via `--ids`
(8.4 min live; completion 0.36 post high-voter trim). Record/replay of model calls was built,
proven, and removed by the user's call — evals judge the 7 E2E criteria, no byte-exact replay.
Trace replay (approved trajectories + cached votes) remains the future work here.

Owned by a **separate coding agent**, so it is not one of our milestones — but it is the measurement track the
behavioral steps lean on. It runs a fresh orchestrator session, compares the tool-call trajectory against the
approved `<nn>_*.json` under the tolerance call-classes, and reports the scoring modes. Until it is online,
Steps 1 and 3 verify against the offline suites + the manual demo, then re-check against the trace gate. It
also resolves the two approval TODOs in `tolerance_rules.md` (06 ambiguity-ask shape; 07 plan-chain step
ordering — `plan_id` is gone).

---

## Sequencing

```
            ┌──────────────────────────────────────────────┐
 parallel ▸ │  Eval gate (step_1_evals.md, separate agent)  │ ── gates ──┐
            └──────────────────────────────────────────────┘            │
                                                            ▼            ▼
  1. PEX  ───►  2. MEM  ───►  3. NLU  ───►  4. Plan  ───►  5. infra
 (replies)    (remembers)   (clarifies)    (plans)        (ships)
```

Build in demo order. **PEX first** — nothing is showable without a turn. **MEM before NLU** — NLU's scratchpad
lives in MEM. **Plan** needs working flows (PEX) and reads better with memory + clarify in place. **Infra**
hardens what the earlier demos rely on. PEX and MEM have no hard dependency, so a second person could overlap
them; everything else follows the chain. The eval gate runs alongside throughout.

---

## Embedded decisions (resolve in the relevant sub-plan; recommendations given)

These don't reshape the roadmap, so they're tracked here and decided in-flight, not up front. (The **Step**
column is the sub-plan file number, not the build-order position above.)

| # | Decision | Step | Recommendation |
|---|---|---|---|
| E1 | Memory tools: alias `recap/recall/retrieve` over existing impls vs. rename outright | 2 | Add the 3 as the public surface over `compile_history`/`manage_memory`/`search_faqs`; don't rename. |
| E2 | Decomposition vehicle: discrete skill vs. prompt-only orchestrator guidance | 5 | **DECIDED: the Workflow Planner skill** (how-to guidance PEX follows; returns nothing — not a flow policy, not a returning call). |
| E3 | Blocks rendering model (spec self-conflict) | 6 | **DECIDED: one `panel` ∈ {top, bottom, left}** — `left` = chat container (old `inline` → `panel:'left'`); spec rewritten + small code change to accept `'left'`. |
| E4 | `content_validation` + `response_constraints` | 6 | **DECIDED: remove both** (half-wired — quality-check call commented out, response_constraints unread; quality lives in prompts/exemplars). |
| E5 | Compaction summary placement | 6 | **DECIDED:** summary = in-stream **`user`-message** handoff (`SUMMARY_PREFIX`, the vehicle); compaction **diagnostic = `system` turn**, treated differently (excluded from user-facing history). |
| E6 | Post/note CRUD: direct router handlers vs. route through NLU `react()` | 6 | **DECIDED: keep direct** + record a user-action turn in the ContextCoordinator; wire vocab `dax`+`payload`. |
| E7 | Tool manifest `scope`/`dispatch`/`output_schema` fields | 6 | **DECIDED: don't back-fill** — code is the single source; document code-side routing; drop the fields from the required manifest. |
| E8 | Parity oracle provenance (captured from deleted legacy pipeline) | 1/6 | Re-baseline from an approved orchestrator run; converge with the L2a trace model. |
| E9 | Prompt taxonomy: does the 8-slot/JSON rule apply to skills? | 4 | **DECIDED: prompt taxonomy** — module skills return *nothing* (how-to guidance); sub-agents + tools return JSON. Skills carved out of the JSON rule (applied to style_guide/checklist/tool_smith 2026-06-21). |
| E10 | Loop constants (`_MAX_ROUNDS`/`_MAX_CORRECTIVE`) — one source of truth | 4 | **DONE 2026-07-03 (round 4.5, PR #4):** single declaration each in config — the user amended the home from `resilience` to a renamed `limits` section (no `resilience` section survives); the dead recovery keys collapsed into `limits.max_recovery_attempts`. |
| E11 | Basic-tier persistence (`session.persistence.backend: postgres` unused; sessions file-based) | 6 | **DECIDED: repoint to `filesystem`** + document file-based as the basic-tier truth; validate `tier`. |
| E12 | Re-route ownership: NLU `contemplate` vs policy `fallback()` | 3 | **DECIDED: both, distinct roles** — policy uses a hard-coded `fallback()` when it knows the fix, else raises a general-fallback signal → Assistant → NLU `contemplate()` (cross-flow). |
| E13 | Scratchpad physical location: keep on `MemoryManager` vs relocate to the World | 2 | **RESOLVED 2026-06-21:** extract to a `SessionScratchpad` component owned by the World; NLU sees it as `nlu.scratchpad` beside `nlu.ambiguity`. Done as part of Step 2. |
| E14 | Low-confidence entity-repair contract | 3 | **DECIDED:** write the value but mark `ver=False` (a prediction); **no blanket gate** — a policy opts into gating only if it uses the signal. |
| E15 | Assistant display name | — | **RESOLVED 2026-06-21:** the assistant is Hugo (the orchestrator setup was promoted to the official `assistants/Hugo/`). `persona.name: "Hugo"` is correct; tool-desc refs `tools.yaml:492,599` are correct as-is. |

---

## Deferred register — "designed, not yet built"

Parked by scope. Each gets a stub + a `# designed-not-built` marker at the exact spot in code, so the spec
stops reading present-tense and a future implementer finds the hook.

- Real parallel **continuous** loops (NLU/PEX/MEM as event-triggered background loops). Today: synchronous
  at the turn points.
- MEM **scratchpad auto-promotion** (salience + `used_count` LLM-judge). `used_count` plumbing stays.
- MEM **proactive push** channel (prefetch + anticipatory scratchpad notes).
- **Multi-active flow concurrency** + the contiguous-Active invariant + N-artifact curation.
- L3 **vector/embedding** retrieval + `agent.md` cold-start ingestion. Today: in-RAM LLM rerank
  (`faq_service.py`).
- `Turn.form` multimodal (speech/image); tool-approval / lethal-trifecta HITL gate; telemetry endpoint;
  responsive block hints.

**From the 2026-07-04 code review (rounds E2-5.1)** — applied immediately: live-stack mirrors for every
`write_state` stack op (the plan-wipe Critical), blocking `_check_nlu` before `contemplate` (belief-writer
ordering), landed-only guard on the stackon-active slot fold (torn-read), `append_to_scratchpad` prompt
name, plan-lifecycle regression test. Parked here as potential plans:

- **One source of truth for the flow stack.** The live `FlowStack` and the file `flow_stack` block have
  different writers reconciled by wholesale overwrites in both directions; the mirror fixes treat the
  symptom. Durable design: route every stack mutation through `write_state` and rehydrate the live stack
  at fixed points, or make the live stack canonical with `write_state` delegating to it.
- **`read_state` blocking scope needs a ruling.** The prompt sends every intent to `read_state` first,
  and its unconditional blocking join serializes most parallel-think turns — the two-speed design only
  pays off if domain turns skip the belief read or the join becomes conditional. Keep-as-is is defensible
  (belief-first correctness) but should be an explicit decision.
- **Smaller parked items:** `execute()` carries 7 params (bundle dax/payload/text as one turn input);
  dead `_llm_quality_check` + placeholder lines in `_validate_artifact`; dead `keep_going` writes in
  draft/revise policies (Batch-2b scope); a test asserting the carrier-A message shape (belief note rides
  the tool-results user message); a forced fallback landing on the loop's final round is not executed
  until next turn; `SessionScratchpad.write_completion` crashes in in-memory mode (unreachable today);
  live eval runs mutate the checked-in content database seeds (sandbox the content DB for eval runs).

---

## Verification strategy

- **Offline gate suites** (no LLM, fast) — keep green after every step:
  `test_artifacts.py`, `unit_tests.py`, `test_nlu_module.py` (baseline 324 passed, 0 failed — no skips).
- **Test cwd gotcha:** run pytest with cwd + `sys.path[0]` set to the `assistants/Hugo` dir, or
  `import backend` may resolve to another assistant's backend. Use the wrapper documented in the test sub-plans.
- **Trace gate** (Step 1 deliverable) — the L2a replay runner gates behavioral steps (esp. Step 3).
- **Parity harness** (`run_parity.py`, 3-axis) — CLI, expensive; re-baseline per E8.
- Each sub-plan ends with its own concrete verify commands.
