# Step 5 — Plan / Workflow Planner (minimal)

Maps to **Master Plan · Step 5**. Effort **M**. Depends on: **Step 1** (eval); benefits from Steps 2/3.
Scope: **minimal**.

**Goal:** make the `Plan` intent functional — decompose a multi-step request into ordered sub-flows and track
progress. **Deliverable:** a decomposition vehicle + `plan_id` activation/progress + depth 8→16, with the
agenda tracked via `plan_id` + scratchpad (no Plan-flow object — held).

Spec: `components/workflow_planner.md`. The FlowStack ops themselves (`stackon`/`fallback`/`pop_completed`,
four-state lifecycle, slot-transfer) are already spec-aligned (`stack.py`) — this step adds the Plan layer on
top.

---

## 5.1 — Decomposition vehicle (E2)  · G1
- Today: no `Plan` key in `PEX._policies` (`pex.py:166-172`), no `plan.py`, no `plan.md`; the orchestrator's
  only Plan instruction is one line "stage the flows in order and run them" (`for_orchestrator.py:44,61`) with
  no decomposition behind it. The spec forbids a Plan **policy sub-agent** — Plan is decomposed by the planner
  itself (`workflow_planner.md:319-336`).
- **Embedded decision E2:** rec — a discrete **`plan` skill** invoked inside PEX's loop (testable, reusable
  for later replan/complete) over prompt-only guidance.
- Build: a `plan.md` skill + a PEX branch on `intent == Plan` that runs it to get (a) an ordered list of
  existing flows and (b) a short approval blurb, then issues one `stackon` per sub-flow under a single
  `plan_id`. Do **not** resurrect the deleted `plan.py` as a flow policy.

## 5.2 — `plan_id` activation + progress  · G5
- `plan_id` is fully plumbed but inert: declared (`parents.py:14`), serialized (`parents.py:87`), accepted by
  `stackon` (`stack.py:17,27,108`), threaded through `write_state` (`pex.py:548`, `dialogue_state.py:208`),
  in the tool schema (`pex.py:895`) — but **no caller sets it and nothing reads it**.
- Have 5.1's decomposition **mint** a `plan_id` and pass it on each `stackon`. Add `FlowStack` helpers:
  progress count by `plan_id` ("2 of 4 done") and cascade-Invalidate by `plan_id` (plan abandonment).
- The agenda **is** the Pending sub-flows sharing the `plan_id` (`workflow_planner.md:338-342`) — no new
  store needed.

## 5.3 — Depth 8→16 (moved from Step 0)  · G2
- `stack.py:12` `_max_depth=8`; overflow raises `RuntimeError` (`stack.py:98-101`). Bump the default to 16
  (or wire `session.max_flow_depth: 16` from config — coordinate with Step 6's session-limit enforcement).
- Keep the hard raise for now (safer than silent note-and-proceed); the spec's "note-and-proceed" fallback is
  only meaningful once Plans stack many flows — defer it.

## 5.4 — `keep_going` Plan-aware behavior  · G8
- Rebuild the spec's loop-control distinction as **behavior**, not a stored flag (the stored `keep_going` is
  removed in Step 3.4): **inside a Plan**, PEX chains to the next sub-flow on the same turn;
  **outside a Plan**, a stacked sub-flow exits for user review (`workflow_planner.md:391`; cf. the
  `keep_going`-only-during-Plans memory rule). Express via the Plan branch from 5.1 + the `plan_id` check.

---

## Held / deferred

- **Plan-flow sentinel (held).** The spec puts a Plan flow at the stack bottom to own completion
  assessment (`workflow_planner.md:338-342,354-358`). Minimal Plan **omits** it — completion assessment is
  deferred (below), so the sentinel isn't needed yet. **When completion assessment is taken up, revisit this
  with Derek** (it's a new flow class).
- **Deferred — stubs + markers:** per-step **replanning** (Continue/Reorder/Expand/Prune,
  `:344-352`), **completion assessment** (`:354-358`), **multi-active concurrency** + contiguous-Active
  invariant + N-artifact curation (`:284-311`), **LATS** (`:379-385`, spec marks optional). Mark each seam
  `# designed-not-built`.

## Verification
- Offline gate suites green (cwd wrapper). `unit_tests.py` has stack tests (depth at `:1624`) — update the
  depth expectation.
- **Trace gate:** `07_plan_chain` exercises this — it must pass, and its `plan_id`-linkage tolerance TODO
  (Step 1 §1.6 / decision) must be resolved consistently with how 5.2 mints `plan_id`.
- Smoke: a 3-step request decomposes into 3 `stackon`s under one `plan_id`; progress reports "n of N"; mid-Plan
  chains on the same turn while a lone stacked sub-flow exits for review.
