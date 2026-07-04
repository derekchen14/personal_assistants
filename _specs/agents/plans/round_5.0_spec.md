# Round 5.0 — PEX hook points + Plan awaits NLU

**AMENDMENT (the user 2026-07-03, post-build):** only Plan and Clarify are REQUIRED to wait on NLU
(their `read_state` blocks). The other five intents never block: flow execution's settle is
non-blocking (`_settle_nlu(wait=False)`) — it picks up a landed detection and otherwise proceeds
on standing belief. When the predicted flow matches the active flow nothing changes; that is the
speed-up. The DoE's third join site (the stackon-active fold) stays, but non-blocking.

Status: SHIPPED 2026-07-03 (branch round/5.0-pex-hooks). Free suite 132+86/0 skips. Live gate
(standard 8): completion 0.52 -> 0.5455, tool_match 0.0613, mean turn 14.0s, wall 465s. Dominant
remaining failure: the loop CONTINUES last turn's still-Active flow instead of reacting to a
mismatching fresh detection (11 of 15 failed turns show a stale origin like find/compose/outline
carried across turns). That reaction — pred vs active differs => reconsider (fallback/stackon) —
is the spec's hook severity model, not yet built; candidate for round 5.1 alongside the Workflow
Planner. Opens Master Plan Step 5 (`step_5_plan.md`); the Workflow Planner
skill itself is the NEXT round (5.1). the user's directive (2026-07-03): PEX follows the existing
6-hook framework (`_specs/modules/pex.md` § hook points — pre-flow, pre-tool, post-tool,
tool-retry, post-flow, verification; no new hooks), and when the orchestrator picks the Plan
intent on the parallel-NLU path, the pre-flow or pre-tool hook waits on NLU before proceeding.

## The problem this solves

On active-post turns NLU `think` runs on a thread in parallel with `pex.execute` (`agent.py:74-77`),
so this turn's detection is invisible to the acting loop — the documented remaining eval failure
(stale/misdetected flow origins; fix_1 ticket). Full serialization would fix it but give up the
two-speed design. The hooks let ONLY the turns that need detection pay the wait.

## The hook points (the 6-hook framework, mapped to today's code)

The framework is already specified in `_specs/modules/pex.md` § hook points; this round follows
it — no new hooks, no hook registry. The four hooks this round touches, and where they live:

| Hook (spec name) | Where it fires | Exists today as |
| --- | --- | --- |
| pre-tool (②/④) | before each tool dispatch (`_guarded_call`, `pex.py:390`) | name/dedupe guards — **gains the NLU join** |
| post-tool (③) | after each dispatch (`pex.py:366-371`) | error counter + log line |
| pre-flow (①) | inside `activate_flow`, before `policy.execute` (`pex.py:618`) | `_security_check` + `_stage_flow` — **gains the NLU join** |
| post-flow (⑤+⑥) | after the policy returns (`pex.py:626-649`) | `_validate_artifact` + completion record + stack sync |

The work at `execute()` entry and the end-of-turn checkpoint is ordinary turn lifecycle, not a
hook (the user 2026-07-03).

## The Plan-awaits-NLU mechanism

`Agent._orchestrate` hands the think thread to PEX: `pex.execute(..., nlu_thread=thread)`. PEX
keeps it for the turn and exposes one internal `_settle_nlu()` — join once, then clear. Two hooks
call it:

- **pre-tool, on `read_state`**: `read_state` returns the whole state document including belief,
  so a belief read IS the "wait on NLU flow detection" the Plan bullet promises. The prompt already
  tells a Plan turn to read belief before deciding — the join makes that read return THIS turn's
  detection instead of last turn's.
- **pre-flow, on any flow run** (`activate_flow`, `write_state stackon active:true` routes there):
  the backstop — no flow ever activates against stale belief, whatever intent the model picked.

Turn shape after the change (active-post turn):

```
Agent._orchestrate
  ├── NLU.think ─────────── thread ───────────────────────┐
  └── PEX.execute(nlu_thread=thread)                      │
        reset, seed message                               │
        loop:                                             │
          LLM round → commits to an intent                │
            Plan  → read_state ── pre-tool: join ─────────┤  fresh belief lands here
            other → domain lookup (pre-tool: no join)     │
          write_state stackon active:true                 │
            └─ pre-flow: join (no-op if settled) ─────────┘
               security check → policy.execute → post-flow validate
        end-of-turn checkpoint
  └── thread.join()   ← turn-boundary settle stays; usually a no-op now
```

Non-Plan turns that answer from a lookup or plain reply never touch belief or a flow, so they keep
full parallelism. The wait cost lands exactly where the user scoped it: Plan turns (and any flow
activation).

## New concepts

One: **the NLU thread handle passed into PEX** (`nlu_thread` parameter + `_settle_nlu()`).
Example: `self.pex.execute(state, ..., nlu_thread=thread)`; inside PEX,
`if self._nlu_thread: self._nlu_thread.join(); self._nlu_thread = None`. The hooks themselves are
the spec's existing 6-hook framework, not new machinery.

## Big decisions

**1. How PEX knows the intent is Plan — behavioral proxy (recommended) vs explicit declaration.**
- (A, recommended) Behavioral: joining on `read_state` + flow activation. Picking Plan already
  means "read belief first" per the prompt, so the join point IS the intent signal. Pros: zero new
  tools, zero extra calls, covers every path that consumes detection. Cons: the intent commitment
  stays in the model's prose, not machine-readable — a Plan turn that skips `read_state` only joins
  at activation.
- (B) Explicit: a `declare_intent` tool or an `intent` param the model must send first. Pros:
  machine-readable intent per turn (evals could score it directly). Cons: one more required call
  per turn — the opposite of the single-call-staging direction — and a new tool concept.

**2. Hook shape — named methods (recommended) vs hook registry.**
- (A, recommended) Six named methods called at fixed points. Pros: greppable, no indirection,
  matches the existing post-hooks-validate pattern. Cons: adding a seventh consumer someday means
  editing PEX.
- (B) Registry of callables. Pros: pluggable. Cons: an abstraction with exactly one implementation
  per hook — the yagni pattern the project rules prohibit.

## Alternatives considered

- **Serialize NLU on all active-post turns** (join before the loop): simplest, and prestage would
  apply everywhere — but every turn pays the detection latency and the two-speed design dies.
- **Do nothing; rely on round 4.3 exemplars**: better detection accuracy doesn't fix staleness —
  the loop would still act on LAST turn's belief.

## Build list (small)

1. `agent.py`: pass `nlu_thread=thread` into `pex.execute`; keep the boundary join.
2. `pex.py`: store the handle per turn; `_settle_nlu()`; call it from pre-tool (`read_state`) and
   pre-flow (`activate_flow`). No renaming beyond that — the 6-hook framework names the existing
   pre/post hooks; do not add PEX start/end hooks.
3. `for_orchestrator.py`: one line under the Plan bullet — "`read_state` always reflects this
   turn's detection; read it before staging when you picked Plan."
4. Unit tests: a fake slow thread proves `read_state` returns post-join belief; a no-thread turn
   (awaited path) is unchanged.

## Verification

Free suite green; the 8-scenario live gate rerun — expected movement on the active-post
stale-origin failures (B04.C01 class). Latency check: non-Plan turns show no added wall time.
