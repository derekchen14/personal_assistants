# Step 5 — Plan intent / Workflow Planner skill (minimal)

Maps to **Master Plan · Step 5** (build step 4). Effort **M**. Depends on: working flows (PEX, build step 1);
benefits from Steps 2/3. Scope: **minimal**.

**Terminology:** **Plan** is the *intent*; the **Workflow Planner** is the *skill* that serves it.

**Goal:** make the `Plan` intent functional — decompose a multi-step request into ordered sub-flows and let the
PEX orchestrator drive them to the user's goal. **Deliverable:** the **Workflow Planner skill** (`plan.md`,
how-to guidance) + depth 8→16 + Plan-aware chaining. **PEX judges goal completion** (already added to the
orchestrator prompt). There is **no `plan_id`, no scratchpad agenda, and no Plan-flow object** — the stack is
the agenda and PEX owns "done".

Spec: `components/workflow_planner.md` (simplified 2026-06-21). The FlowStack ops
(`stackon`/`fallback`/`pop_completed`, the four-state lifecycle, slot-transfer) are already spec-aligned — this
step adds the thin Plan layer on top.

**Reading the current code.** The pieces this step touches:
- `FlowStack` (`flow_stack/stack.py`): `_max_depth` (`:12`) is already `config...max_flow_depth` (default 8);
  overflow raises `RuntimeError` (`:98-101`). `stackon(flow_name)` (`:17`), `fallback(flow_name)` (`:37`),
  `pop_completed()` (`:74`).
- `PEX._policies` (`pex.py:169-175`) wires the 5 acting intents — **no `Plan` key**, and there is **no**
  `policies/plan.py`. Correct: Plan is decomposed by the Workflow Planner skill, not a flow policy.
- The orchestrator prompt now tells PEX to stage a Plan's flows in order and **judge whether the goal is met**
  after each one (`for_orchestrator.py`, the Plan bullet — added 2026-06-21).
- `plan_id` is a field on `BaseFlow` (`parents.py:14`, serialized `:87`, restored `dialogue_state.py:44`) but
  **inert** — nothing mints or reads it. This step **removes** it (§5.4).
- `state.has_plan` is read by `revise.py:67,227` for a Plan-aware scratchpad write; Step 3.4 left it for this
  step to remove.

---

## Decisions

**Locked (this step implements):**
- **Plan = intent; Workflow Planner = skill.** The Workflow Planner skill (`plan.md`) decomposes the request
  into an ordered list of existing flows; PEX stacks them and runs them. No Plan-flow object, no `plan_id`, no
  scratchpad agenda. (§5.1)
- **The Workflow Planner skill returns nothing — it is guidance.** PEX, following it, issues the `stackon`
  calls itself in its loop; the decomposition is PEX's reasoning + tool calls, not a value the skill returns.
  (per Derek 2026-06-21; §5.1)
- **PEX owns goal completion.** After each sub-flow, the orchestrator judges whether the user's goal is met
  and either runs the next flow or concludes — no completion-assessment flow. Added to the orchestrator prompt
  on 2026-06-21. (§5.2)
- **Plan-aware chaining is behavior, not a flag.** Mid-plan PEX chains to the next flow on the same turn; a
  lone stacked flow exits for review. Removes `state.has_plan`. (§5.4)
- **Remove the inert `plan_id` field** from `BaseFlow` + serialization — the simplified model never uses it.
  (§5.4)
- **Depth 8→16.** A plan stacks several sub-flows, so 8 is too shallow. (§5.3)

**Resolved (confirmed 2026-06-21):**
- **Decomposition vehicle — the Workflow Planner skill** the PEX loop follows on `intent == Plan` (a how-to
  guide, testable as a prompt), not prompt-only orchestrator text and not a flow policy. (§5.1)

**Deferred (stub — designed, not built):**
- Per-step replanning (§S-1); multi-active concurrency + artifact curation (§S-2, shared with Step 4). LATS
  decomposition search is **dropped** — not pursuing it.

---

## 5.1 — The Workflow Planner skill
The **Plan** intent is served by the **Workflow Planner skill** (`plan.md`) — a *how-to* skill, not a flow
policy and not a returning call. Like every module skill it **returns nothing**: it is guidance injected into
the orchestrator's context that tells PEX how to decompose a multi-step request and manipulate the flow stack.
So there is no `plan.py` policy and no `skill_call(...) -> {steps}` round-trip.

**Build:**
1. A `plan.md` skill (the Workflow Planner) whose body tells the orchestrator: map each sub-task to an
   **existing** catalog flow (never invent one), order by dependency, keep it minimal, then `stackon` the
   sub-flows in that order and share a one-line plan with the user.
2. Make that guidance available to the PEX loop when `intent == Plan` (it is the detail behind the
   orchestrator prompt's Plan bullet). PEX, following it, **issues the `stackon` tool calls itself** in its
   normal loop — no separate returning call.

```python
# pex.py — with the Workflow Planner guidance in context, PEX emits stack ops in its own loop:
#   write_state(op='stackon', flow_name='research')   # PEX picks the order, guided by the skill
#   write_state(op='stackon', flow_name='draft')
#   write_state(op='stackon', flow_name='publish')
#   <reply with the one-line plan>
```

Because PEX only stacks **catalog** flows (it reads the flow catalog), it cannot sequence a flow that doesn't
exist. The one-line plan is composed into PEX's reply like any other prose.

## 5.2 — PEX drives the stack to the goal
Once the sub-flows are stacked, PEX runs them through the ordinary lifecycle (Active → Completed →
`pop_completed`) and **judges goal completion itself** — the responsibility now written into the orchestrator
prompt. No `plan_id`, no progress store: the **stack is the agenda** (Pending = remaining, Completed = done),
and PEX reads it with `read_state`.

```text
# for_orchestrator.py — the Plan bullet (added 2026-06-21)
Plan → the request spans multiple steps; decide the order, then stage and run the flows one by one. You own
whether the plan is done: after each flow completes, judge whether the user's goal has been met — stage the
next flow until it is, then conclude and report what was accomplished.
```

If PEX wants a "n of N done" line for the user, it counts the stack's Completed vs. total — no new field, no
helper needed.

## 5.3 — Depth 8→16
`_max_depth` is already config-driven (`stack.py:12` → `session.max_flow_depth`, default 8). A plan stacks
several sub-flows, so 8 is too shallow.

```yaml
# shared_defaults.yaml — session
session:
  max_flow_depth: 16        # was 8 — plans stack several sub-flows
```

Also bump the code default fallback to 16 (`stack.py:12`: `get('max_flow_depth', 16)`). **Keep the hard
`RuntimeError`** (`:98-101`) for now — the spec's note-and-proceed overflow only matters once plans routinely
stack deep; defer it. Coordinate with **Step 6.3** (session-limit enforcement reads the same key).

## 5.4 — Remove the dead Plan state (`has_plan` + `plan_id`)
Two now-unused Plan-tracking fields go away. Plan-aware chaining is rebuilt as **behavior**, not a flag:
**mid-plan** PEX chains to the next sub-flow on the same turn; **outside a plan** a stacked sub-flow exits for
user review (`workflow_planner.md`; cf. [[feedback-keep-going-plans-only]]). PEX already knows it is mid-plan —
it just stacked the sequence following the Workflow Planner skill — so the distinction needs no stored signal.

**`has_plan`** — the two reads in `revise.py:67,227` gate a Plan-aware scratchpad write that is **redundant**
with the completion-record mechanism (every completed flow already appends `{flow, summary, metadata}` to the
scratchpad, which downstream flows read). Remove the gated writes, then remove `has_plan` from
`DialogueState`.

**`plan_id`** — declared `parents.py:14`, serialized `:87`, restored `dialogue_state.py:44`, but never minted
or read. Remove it from `BaseFlow.__init__`, `to_dict`/`serialize`, and the Dialogue State restore.

```python
# revise.py — delete the has_plan-gated branch (completion records already carry the summary)
# (was: if state.has_plan: self.scratchpad.write(flow.name(), {...}))

# dialogue_state.py — remove has_plan from __init__ / serialize / load / from_dict / _BELIEF_FIELDS
# parents.py + dialogue_state.py — remove the plan_id field + its serialize/restore
```

After this the `flags` block has no remaining live entries — finishing the flag-block removal started in
Step 3.4 — and no Plan-tracking field survives on the flow.

---

## Stubs — designed, not built

### S-1 — Per-step replanning
After a sub-flow completes, PEX could re-examine the remaining stack and reorder / add / drop sub-flows instead
of running the agenda verbatim. The minimal model already lets PEX **stack a new flow** the work revealed (its
goal judgment in §5.2), so explicit replanning is just a richer prompted version of that.

```python
# pex.py — replan after a sub-flow completes (designed-not-built)
# the Workflow Planner skill is re-consulted; PEX may reorder remaining Pending, stackon a new sub-flow,
# mark a now-unneeded Pending Invalid, or continue.
```

- **Why deferred:** the minimal goal-judgment loop covers the common case (continue, or stack one more); a
  dedicated reorder/prune step is added only if real plans need it.

### S-2 — Multi-active concurrency + artifact curation  (`workflow_planner.md:284-311`)
Today one flow is Active at a time. The target lets several sub-flows be Active concurrently (preserving the
contiguous-Active invariant), their artifacts curated into one turn artifact (the **Step 4** curation stub).

- **Why deferred:** a large change touching the stack lifecycle, the turn loop, and artifact curation. Mark the
  single-active assumption in `activate_flow` `# designed-not-built`.

---

## Verification
- Offline gate suites green (cwd wrapper). `unit_tests.py` stack tests: update the depth expectation to 16;
  drop any assertion on a serialized `plan_id`.
- **Trace gate:** `07_plan_chain` exercises this — a 3-step request decomposes into 3 ordered `stackon`s and
  PEX runs them to completion on one turn, then concludes. (Its old `plan_id`-linkage tolerance no longer
  applies — match on step ordering, not a shared id.)
- Smoke: a multi-step request stacks the right flows in order; mid-plan PEX chains on the same turn while a
  lone stacked flow exits for review; `state.has_plan` and `flow.plan_id` are gone and nothing reads them.
