# Master Plan — Transfer the spec → Hugo

The roadmap for bringing the **Hugo** implementation up to the master spec (`_specs/`). Hugo already has
working code, so each step is a *transfer/refactor* against current state, not a from-scratch build.

**We build in demo order, not component order.** Start with the end in mind: every step leaves Hugo able to
do something you can *show*. What sequences the work is "which demo does this unlock?" — not the module
dependency graph alone.

- **Master Plan** (this file) = the major rounds in priority order. Each leads with the demo it unlocks, then
  its goal and deliverable.
- **Round plans** = `round_<N>_<slug>.md` = the minor steps of each major round, with file:line detail,
  new-concept shapes, per-step verification, and embedded decisions. **`<N>` IS the priority order
  (re-prioritized 2026-07-07):** 1 evals · 2 PEX · 3 NLU · 4 MEM · 5 Plan · 6 infra.
- **Sub-rounds** = `rounds/round_<N.M>_*.md` = one executed team round each (spec + artifacts), where `<N>`
  names the owning round. Every shipped sub-round is in the ledger below; former `fix_*` tickets and the
  old `round_4.x`/`round_5.x`/`E1` ids are merged into the same `N.M` scheme.

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
  approved concept's shape is described in its round plan before any code. There is **no Plan-flow object** — the
  Plan is a skill that stacks existing flows, and PEX judges goal completion.
- **Intent model = adopt the spec's PEX System-1 hint.** PEX emits a coarse-intent hint inside its own
  reasoning; NLU drops its separate `_classify_intent` call (`nlu.py:259,309`) and flow-detection becomes the
  authoritative intent write. Highest-regression-risk change → gated behind the trace eval (Round 1).
- **Plan lifecycle = minimal.** The Workflow Planner skill guides PEX to stack ordered flows; depth 8→16;
  **PEX judges goal completion** (no `plan_id`, no Plan-flow object). Defer replanning and multi-active
  concurrency; LATS dropped.

---

## The end in mind

The whole point of Hugo: **a user collaborates across a multi-turn session to research, draft, revise, and
publish a blog post** — Hugo remembers their style preferences, pulls in business context, asks a clarifying
question when a request is ambiguous, and handles multi-step requests by planning and showing progress.

Working backward, each milestone is the smallest slice that adds **one visible capability** on top of the
last. Build in round order:

| Round | Demo you can show once the round is done | Plan |
|---|---|---|
| 1 | **Hugo is measurable.** Free suite in seconds; an ~8-scenario live gate in ≤10 min scores the 7 E2E criteria. | `round_1_evals.md` |
| 2 | **Hugo replies.** A single-flow request ("draft an intro about X") returns a well-formed reply + an artifact the UI renders; the voice matches the style guide. | `round_2_pex.md` |
| 3 | **Hugo clarifies.** An ambiguous request gets a targeted question; next turn the answer binds correctly; intent routing is right. | `round_3_nlu.md` |
| 4 | **Hugo remembers.** "I prefer short paragraphs" changes the next draft; a business-context question is answered from L3; session recap works. | `round_4_mem.md` |
| 5 | **Hugo plans.** A multi-step request decomposes into ordered flows and Hugo runs them to the goal, reporting what got done. | `round_5_plan.md` |
| 6 | **Hugo ships.** Progress streams to the UI mid-turn; session limits are enforced; config is validated on load. | `round_6_infra.md` |

**Why evals then PEX lead.** The eval suite is the measurement every later round is judged with, and the turn
loop is the substrate of *every* demo: until a user message produces a well-formed reply + artifact, there is
nothing to show for ambiguity, memory, or planning. Both are now largely shipped (see the ledger).

**NLU before MEM (the 2026-07-07 re-prioritization).** The old order put MEM first because NLU's scratchpad
lives there; that dependency is already satisfied — `SessionScratchpad` landed early on the World
(`backend/components/session_scratchpad.py`, E13). Routing/ambiguity quality is the dominant live-gate
failure mode, so NLU outranks the rest of MEM.

---

## The major rounds (priority order)

Effort key: S ≈ <½ day, M ≈ 1–2 days, L ≈ 3+ days. "Gated" = waits on a listed decision (above) or an
embedded decision (below). Sub-round file names in `rounds/` carry the owning round's number.

> **Step 0 (Identity & dead-config cleanup) — DONE 2026-06-21.** Recorded under "Already done"; its sub-plan
> file is retired. The one open thread it surfaced (`persona.name`) lives on as decision **E15**.

### Round 1 · Hugo is measurable — the evaluation suite · `round_1_evals.md`
- **Shipped:** **1.1** fast evals (was E1 — seeding + timing + the ~8-scenario gate; record/replay built,
  proven, removed by the user's call) · **1.2** suite consolidation (was fix_4 — everything under
  `utils/evaluation_suite/`, dead taxonomy deleted, all 7 E2E criteria scored).
- **Remaining:** trace replay (approved trajectories + cached votes); the two approval TODOs in
  `tolerance_rules.md` (06 ambiguity-ask shape; 07 plan-chain step ordering — `plan_id` is gone);
  parity-oracle re-baseline (E8). The gate keeps running beside every later round.

### Round 2 · Hugo replies — PEX turn & prompt conformance · `round_2_pex.md`
- **Demo unlocked:** talk to Hugo and get a well-formed reply + a rendered artifact for a single flow — the
  voice matches the style guide and the flow behaves.
- **Shipped:** **2.2** closing reminder · **2.3** exemplar raise + read cap · **2.5** `limits` config (E10) ·
  **2.6** per-call model tier · **2.7** PEX hook points + NLU joins (was 5.0) · **2.8** one flow stack
  (was 5.2) · **2.9** flow prompt consolidation (was 5.3) · **2.10** orchestrator activation (was fix_1;
  its create-on-missing finale was replaced 2026-07-06 by the `understand(op='contemplate')` re-route).
- **Remaining:** multi-artifact curation stays deferred (needs concurrency); §2.4 grounding-first ordering
  note is prompt-only follow-through.

### Round 3 · Hugo clarifies — NLU belief, ambiguity & the intent rework, the Heart · **L** · `round_3_nlu.md`
- **Demo unlocked:** an ambiguous request gets a targeted clarifying question; next turn the answer binds as
  the *answer* (not re-detected); intent routing is right under the PEX-hint model.
- **Shipped:** **3.5** propose slot-fill prompt (was fix_2) · **3.6** fill_slots retry guardrail (was fix_3a)
  · **3.7** slot-fill repair (was fix_3b) — done 2026-07-08: `_parse_json` fallback is outermost-greedy
  (never a nested fragment) and the retry loop catches the parse-failure ValueError.
- **Goal:** bring NLU belief + ambiguity behavior to spec and execute the intent-model change (PEX System-1
  hint) — sub-steps §3.1–§3.4.
- **Deliverable:** PEX-hint intent model (remove `_classify_intent`); minimal-schema scratchpad entries
  (`version`/`turn_number`/`used_count`) + synchronous NLU review at turn points; cross-turn ambiguity
  binding; gate low-confidence entity repairs (`ver=False`) instead of committing silently; halt-on-intent
  -split; wire the idle `contemplate` trigger (partially landed 2026-07-06 as the `understand` dispatch
  tool); wire the unused `should_escalate` escalation; cap `pred_flows` to top-3 (`dialogue_state.md:131`).
- **Depends on:** the eval gate (Round 1, running) for the intent rework. The old MEM dependency is
  satisfied — `SessionScratchpad` already lives on the World. Riskiest change on the board.
- **Gated:** continuous scratchpad review is the deferred (stub) variant.

### Round 4 · Hugo remembers — MEM, the Head · **L** · `round_4_mem.md`
- **Demo unlocked:** "I prefer short paragraphs" changes the next draft (preference recall); a
  business-context question is answered from L3 (`retrieve`); session recap works.
- **Goal:** stand up memory as a real module — three tiers + the skill surface (synchronous facade; the
  continuous loop is deferred).
- **Deliverable:** `MemoryManager` as the facade owning L1 (Context Coordinator) / L2 (`user_preferences`) /
  L3 (`business_context`); `recap`/`recall`/`retrieve` as the public skill surface; a typed `Preference`
  record with endorsed-vs-guessed rendering + the caution dial (shape only). Auto-promotion, proactive push,
  and vector retrieval land as designed-not-built stubs. §4.4 (`SessionScratchpad`) already landed.
- **Depends on:** the component shapes approved above (confirm in the round plan).

### Round 5 · Hugo plans — Plan / Workflow Planner (minimal) · **M** · `round_5_plan.md`
- **Demo unlocked:** a multi-step request ("research competitors, outline, then write the intro") decomposes
  into ordered flows and Hugo runs them to the goal, reporting what got done.
- **Shipped:** **5.1** Workflow Planner skill + NLU belief state injection (implements §5.1–§5.4: the skill,
  stack-all-at-once plans, depth handling, dead Plan-state removal).
- **Remaining:** replanning + multi-active concurrency stay deferred; LATS dropped. Judge with the
  plan-arc eval scenarios.

### Round 6 · Hugo ships — Config / Server / Blocks infra · **M–L** · `round_6_infra.md`
- **Demo unlocked:** progress streams to the UI mid-turn; session limits are enforced
  (`max_turns`/`max_flow_depth`); config is validated on load; blocks render via the agreed model.
- **Goal:** conform the remaining infrastructure surfaces.
- **Deliverable:** a validating config loader + ontology merge (`config.flows`); remove
  `content_validation` + `response_constraints` (E4); enforce session limits; WS mid-turn progress streaming;
  reconcile the blocks rendering model (E3); delete the RES test tombstones; re-baseline the parity oracle;
  consistent designed-not-built markers across config.
- **Depends on:** the eval gate (parity-oracle convergence, E8).

## Sub-round ledger (shipped work, one naming scheme)

| Sub-round | Was | What shipped |
|---|---|---|
| 1.1 | round E1 | fast eval mode: seeding all 96, timing reports, `--ids` gate subset; replay removed by design |
| 1.2 | fix_4 | suite consolidated under `utils/evaluation_suite/`; dead trace/eval taxonomy deleted |
| 2.2 | round 4.2 | closing reminder (slot 7) injected into every flow sub-agent prompt |
| 2.3 | round 4.3 | exemplar raise (34 PEX + 13 detection) + per-turn read cap (`limits.max_reads`) |
| 2.5 | round 4.5 | loop bounds + call caps promoted to the `limits` config section (E10) |
| 2.6 | round 4.6 | per-call model tier on the flow sub-agent call |
| 2.7 | round 5.0 | PEX hook points; only Plan/Clarify block on NLU |
| 2.8 | round 5.2 | one flow stack — `write_state` mutates the live `FlowStack`; saved copy on serialize |
| 2.9 | round 5.3 | flow prompts to `pex/flows/`; starters render parameters only; `flow_reply`/`flow_execute` |
| 2.10 | fix_1 | orchestrator activation; finale superseded by `understand(op='contemplate')` (169419e) |
| 3.5 | fix_2 | `propose` NLU slot-fill prompt |
| 3.6 | fix_3a | fill_slots one-retry guardrail |
| 3.7 | fix_3b | fill_slots retry (Decision B) + outermost-greedy `_parse_json` fallback (Decision A) |
| 5.1 | round 5.1 | Workflow Planner skill + belief injection + stack-at-once plans + dead Plan-state removal |

---

## Sequencing

```
  1. evals  ───►  2. PEX  ───►  3. NLU  ───►  4. MEM  ───►  5. Plan  ───►  6. infra
 (measurable)   (replies)    (clarifies)   (remembers)     (plans)        (ships)
   ~done          ~done        ◄ NEXT      (5.1 shipped)
```

Build in round order. **Evals first** — every later round is judged with the gate, which keeps running
alongside. **PEX second** — nothing is showable without a turn. Rounds 1 and 2 are largely shipped (see the
ledger), so **the current front is Round 3 (NLU)** — its old MEM dependency is satisfied because
`SessionScratchpad` already lives on the World. **Plan** needs working flows and reads better with clarify in
place (5.1 already shipped the Workflow Planner). **Infra** hardens what the earlier demos rely on.

---

## Embedded decisions (resolve in the relevant round plan; recommendations given)

These don't reshape the roadmap, so they're tracked here and decided in-flight, not up front. (The **Round**
column names the owning round, which is also its priority position.)

| # | Decision | Round | Recommendation |
|---|---|---|---|
| E1 | Memory tools: alias `recap/recall/retrieve` over existing impls vs. rename outright | 4 | Add the 3 as the public surface over `compile_history`/`manage_memory`/`search_faqs`; don't rename. |
| E2 | Decomposition vehicle: discrete skill vs. prompt-only orchestrator guidance | 5 | **DECIDED: the Workflow Planner skill** (how-to guidance PEX follows; returns nothing — not a flow policy, not a returning call). |
| E3 | Blocks rendering model (spec self-conflict) | 6 | **DECIDED: one `panel` ∈ {top, bottom, left}** — `left` = chat container (old `inline` → `panel:'left'`); spec rewritten + small code change to accept `'left'`. |
| E4 | `content_validation` + `response_constraints` | 6 | **DECIDED: remove both** (half-wired — quality-check call commented out, response_constraints unread; quality lives in prompts/exemplars). |
| E5 | Compaction summary placement | 6 | **DECIDED:** summary = in-stream **`user`-message** handoff (`SUMMARY_PREFIX`, the vehicle); compaction **diagnostic = `system` turn**, treated differently (excluded from user-facing history). |
| E6 | Post/note CRUD: direct router handlers vs. route through NLU `react()` | 6 | **DECIDED: keep direct** + record a user-action turn in the ContextCoordinator; wire vocab `dax`+`payload`. |
| E7 | Tool manifest `scope`/`dispatch`/`output_schema` fields | 6 | **DECIDED: don't back-fill** — code is the single source; document code-side routing; drop the fields from the required manifest. |
| E8 | Parity oracle provenance (captured from deleted legacy pipeline) | 1/6 | Re-baseline from an approved orchestrator run; converge with the recorded-trace model. |
| E9 | Prompt taxonomy: does the 8-slot/JSON rule apply to skills? | 2 | **DECIDED: prompt taxonomy** — module skills return *nothing* (how-to guidance); sub-agents + tools return JSON. Skills carved out of the JSON rule (applied to style_guide/checklist/tool_smith 2026-06-21). |
| E10 | Loop constants (`_MAX_ROUNDS`/`_MAX_CORRECTIVE`) — one source of truth | 2 | **DONE 2026-07-03 (round 2.5, PR #4):** single declaration each in config — the user amended the home from `resilience` to a renamed `limits` section (no `resilience` section survives); the dead recovery keys collapsed into `limits.max_recovery_attempts`. |
| E11 | Basic-tier persistence (`session.persistence.backend: postgres` unused; sessions file-based) | 6 | **DECIDED: repoint to `filesystem`** + document file-based as the basic-tier truth; validate `tier`. |
| E12 | Re-route ownership: NLU `contemplate` vs policy `fallback()` | 3 | **DECIDED: both, distinct roles** — policy uses a hard-coded `fallback()` when it knows the fix, else raises a general-fallback signal → Assistant → NLU `contemplate()` (cross-flow). |
| E13 | Scratchpad physical location: keep on `MemoryManager` vs relocate to the World | 4 | **RESOLVED 2026-06-21:** extract to a `SessionScratchpad` component owned by the World; NLU sees it as `nlu.scratchpad` beside `nlu.ambiguity`. Landed (`backend/components/session_scratchpad.py`). |
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

- ~~**One source of truth for the flow stack.**~~ **DONE as round 2.8** — the live `FlowStack` is canonical;
  `write_state` mutates it directly and the state file holds a saved copy refreshed on serialize.
- ~~**`read_state` blocking scope needs a ruling.**~~ **RULED in round 2.7's amendment** — only Plan and
  Clarify block on NLU; the other five intents proceed on standing belief with a non-blocking settle.
- **Flow-internal bounding of repeated read actions (round 2.3 gate forensics, 2026-07-04):** the orchestrator
  `limits.max_reads` cap never fires live because the observed repeated reads (find_posts ×5-7,
  read_metadata ×5-8) run inside flow policies' own tool loops, under `max_tool_calls`. The cap
  that would actually move tool_match and latency is a per-flow read budget inside `llm_execute`
  (or flow-prompt discipline for the read-heavy flows: browse, audit, find). Partially addressed in
  round 2.9: audit now gets the full post prose preloaded, and audit/compose carry no-re-read rules.
- **Smaller parked items:** `execute()` carries 7 params (bundle dax/payload/text as one turn input);
  dead `_llm_quality_check` + placeholder lines in `_validate_artifact`; dead `keep_going` writes in
  draft/revise policies (Batch-2b scope); a test asserting the carrier-A message shape (belief note rides
  the tool-results user message); a forced fallback landing on the loop's final round is not executed
  until next turn; `SessionScratchpad.write_completion` crashes in in-memory mode (unreachable today);
  live eval runs mutate the checked-in content database seeds (sandbox the content DB for eval runs).

---

## Verification strategy

- **Offline gate suites** (no LLM, fast) — keep green with zero skips after every round:
  `utils/evaluation_suite/_tests/{pex,nlu,mem,model}_unit_tests.py`.
- **Test cwd gotcha:** run pytest with cwd + `sys.path[0]` set to the `assistants/Hugo` dir, or
  `import backend` may resolve to another assistant's backend. Use the wrapper documented in the test round plans.
- **Trace gate** (Round 1 deliverable) — the trace-replay runner gates the behavioral rounds (esp. Round 3).
- **Live gate** — a fresh ~8-scenario sample via `utils/evaluation_suite/_evals/run_evals.py --ids …`,
  ≤10 min; commit first, `git restore database/content` after (live runs mutate the seeds).
- The old parity harness (`run_parity.py`) was deleted in round 1.2; the E8 re-baseline is Round 1 work.
- Each round plan ends with its own concrete verify commands.
