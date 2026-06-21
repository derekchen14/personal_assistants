# Step 3 — NLU belief, ambiguity & the intent rework (the Heart)

Maps to **Master Plan · Step 3**. Effort **L**. Depends on: **Step 1** (eval gate — required for the intent
rework) and **Step 2** (scratchpad/MEM ownership). The highest-risk step; gate every sub-item on the trace
runner.

**Goal:** bring NLU belief + ambiguity behavior to spec and adopt the PEX System-1 intent hint.
**Deliverable:** the items below, each green on the offline suites *and* the 10 approved trajectories.

Spec: `modules/nlu.md`; `components/{dialogue_state,ambiguity_handler,session_scratchpad}.md`.

---

## 3.1 — Intent model rework (the keystone)  ·  N1

Current: NLU's `think` (`nlu.py:99`) calls a dedicated `_classify_intent` (`nlu.py:259`, def `:309-318`),
then detects a flow. The orchestrator prompt *forbids* PEX from classifying ("NLU has ALREADY classified the
intent… ACT, don't re-classify", `for_orchestrator.py:31-35`).

Target (spec, `nlu.md:108-138`): coarse intent is **PEX's System-1** in-reasoning guess (no extra model
call); **NLU flow-detection is the authoritative write** — detecting a flow implicitly classifies intent via
`FLOW_CATALOG[flow]['intent']`. PEX's hint narrows `detect_flow(text, intent=None)`
(`dialogue_state.md:96-99`).

### 3.1.1 — Drop NLU's dedicated intent pre-pass
- Remove the `_classify_intent` call (`nlu.py:259`) and let `pred_intent` derive from the detected flow
  (`FLOW_CATALOG[detected]['intent']`). Keep `_classify_intent`/`build_intent_prompt` only if PEX needs a
  callable detect-with-hint path (3.A3); otherwise delete.

### 3.1.2 — PEX System-1 bias as prompt guidance
- Rewrite `for_orchestrator.py:31-35`: instead of "don't classify," instruct PEX to form a cheap coarse-intent
  sense in its own reasoning and lean **Plan/Clarify under uncertainty** (architecture.md:98). No extra LLM
  call — it's reasoning inside the existing loop.

### 3.1.3 — Hint into detect_flow (sequencing nuance — validate via eval)
- `detect_flow` already accepts `intent=None`; thread PEX's hint through when PEX re-invokes detection
  (e.g. contemplate / dissatisfied with the pre-hook detection).
- **Open nuance:** NLU's pre-hook `think` runs *before* PEX, so the first-pass detection has no PEX hint;
  the hint matters on re-detection. Confirm the pre-hook still produces a usable authoritative write and the
  hint only sharpens re-routes. **This is exactly what Step 1's gate must prove** — run all 10 trajectories
  before/after and require no trajectory-score regression past threshold.

---

## 3.2 — Ambiguity behavior  ·  N3 / N4 / N5 / N6

### 3.2.1 — Cross-turn ambiguity binding (treat the reply as the *answer*)  · N4 · M
- Today `agent.py:62-64` unconditionally calls `ambiguity.resolve()` (clear) before any detection — every
  clarification answer is re-detected blind.
- Add a binding step in `think`/`understand`: if `ambiguity.present()` at entry, route the utterance to the
  **pending question** (fill the missing slot/entity from `ambiguity` metadata) instead of wipe-then-detect.
  Fall back to fresh detection only if the reply abandons the question. (`nlu.md:237-240`,
  `ambiguity_handler.md:46-49`.)

### 3.2.2 — Gate low-confidence entity repairs  · N3 · S
- `nlu.py:185-211`: the lexical (`get_close_matches`) and LLM rungs assign `slot.value = matches[0]` **and**
  declare `confirmation` — committing a guessed value. Exact/case rungs commit clean (correct, no doubt).
- **Embedded decision E14 (repair contract):** rec — a doubtful repair writes the value only as a **prediction
  (`ver=False`)** and PEX won't act until verification flips `ver=True`; it must not present as committed.
  Apply to the lexical/LLM rungs.

### 3.2.3 — Wire `should_escalate` (moved from Step 0)  · N5 · S
- `ambiguity_handler.py:65-66` is defined and `counts` increments (`:36-37`), but nothing calls it.
- Wire into PEX's clarification path (`pex.py:219`, `:598`) so that once `counts ≥ ambiguity_escalation_turns`
  (config, default 3) the agent switches strategy (offer options / hand off) instead of re-asking.

### 3.2.4 — Wire the idle `contemplate` trigger  · N6 · M
- `contemplate` is fully coded (`nlu.py:116-125`, `:444-474`) and reachable via `understand(op='contemplate')`
  (`:91-92`) but **never called**. Add a stuck-flow signal in PEX/policy recovery that calls it and feeds the
  re-detection into a `stackon`/`fallback`.
- **Embedded decision E12 (re-route ownership):** Hugo's own docs conflict on `contemplate` (NLU re-route)
  vs the policy `fallback()` tool. Rec — `contemplate` owns **cross-flow** re-routing (wrong flow chosen),
  `fallback()` owns **within-policy** recovery (right flow, bad slot/tool). Wire accordingly.

---

## 3.3 — Scratchpad schema & synchronous review  ·  S2 / S3

### 3.3.1 — Minimal entry schema  · S3 · M
- `memory_manager.py:34` stores free dicts; only `writer` is stamped. Stamp the spec's required fields on
  append — `version:int`, `turn_number:int`, `used_count:int` — and key by **flow name**
  (`session_scratchpad.md:34-64`). (Corrects the stale audit: `used_count` is **not** currently written.)
- Reconcile `write_completion` (`memory_manager.py:58-64`, keyed by `writer`) with the entry schema — this is
  the `c6` completion-vehicle item deferred from Step 2.

### 3.3.2 — Synchronous NLU review + `update_scratchpad`  · S2 · M
- Spec: appending triggers NLU to review the pad (merge dups, reconcile contradictions, prune stale)
  via an **NLU-only `update_scratchpad`** (`session_scratchpad.md:22,78-89`; `nlu.md:258-269`).
- Core now: run the review **at the turn points** NLU already executes — not on every append. Add the
  `update_scratchpad` mutation + a `_review_scratchpad` routine NLU calls in `think`. Mark the
  **continuous/event-triggered** version `# designed-not-built`.
- **Embedded decision E13 (location) — RESOLVED in Step 2:** the scratchpad now lives on the World as a
  `SessionScratchpad` component, reached as `nlu.scratchpad` beside `nlu.ambiguity`. This section adds the
  entry schema + NLU review on that component (not `MemoryManager`).

---

## 3.4 — Vestigial flag block cleanup  ·  N "D-state" / Plan-report G8

- `dialogue_state.py:60-63,91-94,105-111,240-243` still defines/serializes `keep_going`/`has_issues`/
  `has_plan`/`natural_birth`; `dialogue_state.md:105-116` says **no flag block**. `keep_going` is *written*
  by Draft/Revise (`draft.py:168,205`; `revise.py:108,112,216`) but **never read** in the orchestrator path.
- **Verify-then-remove:** grep each flag for live readers in Hugo; remove the dead writes + serialization
  once confirmed orphaned. (The Plan-aware `keep_going` *behavior* — chain vs exit-for-review — is rebuilt in
  Step 5, not restored as a stored flag.)

---

## Deferred here (stubs)
3-round escalating ensemble + alignment-multiplier + abstention (`nlu.md:177-181` — spec marks these future);
scratchpad auto-promotion; continuous review trigger.

## Verification
- Offline gate suites green (cwd wrapper). `test_nlu_module.py` especially — update any row that assumed the
  separate intent pre-pass.
- **Trace gate (mandatory):** all 10 approved trajectories pass after each section; the intent rework (3.1) and
  ambiguity binding (3.2.1) are the regression-prone ones — diff trajectory scores before/after.
- Smoke: a clarification answer fills the pending slot (not a blind re-detect); a low-confidence repair leaves
  `ver=False`.
