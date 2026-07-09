# Round 1.3 — Trace observability for task-completion failures

Status: **draft for alignment**. Owner: evaluation infrastructure. Builds on Round 1.1/1.2 and
the current `utils/evaluation_suite/` layout. This is a diagnostics round, not an agent-behavior
round.

---

## Why this round

The recent E2E sample completed without crashing after the grounding cleanup and
the `clarify` NLU fix, but the aggregate scores still do not explain the failure:

```text
completion=0.25 correctness=0.083 response=0.447 state=0.611 ambiguity=1.0
```

That pattern says Hugo often gets a plausible belief (`state` is better than completion), but
the task does not reliably complete or call the expected domain tools. Evals answer "how bad is
it?"; traces must answer **where the turn broke**: bad NLU belief, no stack/activate call, policy
left Active, tool error, ambiguity surfaced, response fallback, or wrong domain tool sequence.

Today `run_traces.py` prints a useful per-turn line, but it is not enough for debugging:

- default sample is random 8, but there is no `--sample` or `--seed`;
- selected IDs are not printed before the run;
- per-turn output is text only, not structured for later inspection;
- no stable failure taxonomy exists;
- transcript paths are implied but not printed per case;
- it does not record belief / stack / ambiguity snapshots per user turn;
- it still needs to be kept aligned with the new Dialogue State grounding shape.

This round makes traces the primary observability tool for task-completion failures. It does
**not** define a fixed trace set. The default trace run stays a representative sample of 8
conversations; chosen IDs are a debugging override only.

## Scope

In scope:

- Improve `assistants/Hugo/utils/evaluation_suite/_traces/run_traces.py`.
- Add structured trace records under the evaluation report directory.
- Add deterministic sample controls.
- Add per-turn diagnostic snapshots from the current `world.state`, `world.flows`, and
  `world.ambiguity`.
- Add a shared trace-artifact writer that E2E evals can use as diagnostic side output.
- Make `run_suite.py --evals` run traces alongside evals by default.
- Keep traces runnable for a chosen subset when debugging a known failure.

Out of scope:

- Improving task success itself.
- Adding replay/recording of model responses.
- Changing NLU/PEX behavior except for compatibility fixes required to let traces run.
- Re-baselining the full train trace gate.
- Building a UI trace viewer.

## Runner semantics

Direct tier runners remain narrow:

- `utils/evaluation_suite/_evals/run_evals.py` runs **E2E evals only**.
- `utils/evaluation_suite/_traces/run_traces.py` runs **traces only**.

The suite entrypoint composes tiers:

- `utils/evaluation_suite/run_suite.py --sample 8` runs deterministic code tests, then E2E evals
  once, and writes trace JSONL from that same eval pass.
- `run_suite.py --evals` narrows the live run to evals only.
- `run_suite.py --traces` still runs traces alone.
- `run_suite.py --tests nlu` narrows the run to deterministic tests only.

Why: direct runners and live-tier flags are useful for targeted local work, but the default
suite-level command should leave enough observability to debug broken evals without requiring a
second manual run.

## Target command shape

Keep existing commands working:

```bash
python utils/evaluation_suite/_traces/run_traces.py
python utils/evaluation_suite/_traces/run_traces.py --ids B01.C01,B01.C08
python utils/evaluation_suite/_traces/run_traces.py --all
```

Add:

```bash
python utils/evaluation_suite/_traces/run_traces.py --sample 8 --seed 1
python utils/evaluation_suite/_traces/run_traces.py --sample 8 --seed 1 --jsonl
```

Behavior:

- `--ids` wins over `--all`, `--sample`, and `--seed`.
- `--all` runs the full train split and remains the only gated mode.
- No `--ids` and no `--all` uses `sample(args.sample, seed=args.seed)`.
- Default remains sample size **8** with no seed, preserving current behavior.
- The runner prints selected IDs before any live model calls.

## Sample selection

Trace samples should be useful, not fixed. The selection policy is:

1. **Default:** random sample of 8 from `train.jsonl`, using `harness.sample(8)`.
2. **Reproducible debug:** random sample of N with a supplied seed (`--sample N --seed S`).
3. **Known failure drill-down:** explicit `--ids`, supplied by the developer after seeing a bad
   eval or trace run.
4. **Future intelligent sampling:** optional stratified sampler that balances intent/flow,
   ambiguity presence, and prior failure diagnoses. This is allowed only if it remains dynamic and
   transparent by printing the selected IDs and the reason each was selected.

Do **not** bake any recent E2E sample into traces. A previous failed run may be useful as a one-off
debug command via `--ids`, but it is not a default, a baseline, or a standing gate.

## Trace output

Each run should write one JSONL file:

```text
utils/evaluation_suite/report/traces_<timestamp>.jsonl
```

When invoked through the default `run_suite.py` path, the eval pass writes metrics and trace schema
while scoring:

```text
utils/evaluation_suite/report/evals_<timestamp>.json
utils/evaluation_suite/report/evals_trace_<timestamp>.jsonl
```

Direct `run_evals.py` stays eval-only unless a future explicit flag is added.

Each line is one user turn:

```json
{
  "convo_id": "B04.C16",
  "turn_index": 2,
  "user_turn_number": 1,
  "utterance": "Can you tighten this?",
  "expected_actions": ["read_metadata", "revise_content"],
  "actual_domain_tools": ["read_metadata"],
  "all_tools": ["understand", "manage_flows", "read_metadata"],
  "completion_ok": false,
  "completion_reason": "fallback_response",
  "tool_similarity": 0.5,
  "latency_seconds": 14.2,
  "belief_before": {...},
  "belief_after": {...},
  "flow_stack_after": [...],
  "grounding_after": {...},
  "ambiguity_after": {
    "present": false,
    "level": "",
    "metadata": {},
    "observation": ""
  },
  "artifact": {
    "origin": "write",
    "block_types": ["card"],
    "has_content": true
  },
  "message_preview": "I tightened the intro...",
  "transcript_path": "database/sessions/B04.C16/messages.jsonl",
  "diagnosis": "policy_incomplete"
}
```

The JSONL is the artifact for debugging. Console output stays human-readable and short.

## Failure taxonomy

Add a small closed vocabulary for `diagnosis`. This is deliberately coarse; it should route a
developer to the right surface in under a minute.

| Diagnosis | When |
|---|---|
| `completed` | `is_completed` passes |
| `turn_timeout` | `_run_turn` returns the timeout payload |
| `crash_fallback` | assistant returned the top-level crash fallback |
| `loop_fallback` | PEX returned the loop fallback |
| `wrong_belief` | expected single flow exists and `state.pred_flows[0]` differs |
| `ambiguity_pending` | ambiguity is present after the turn |
| `no_domain_tools` | expected actions include domain tools but none were called |
| `tool_mismatch` | domain tools were called, but similarity is below threshold |
| `policy_incomplete` | a flow is Active/Pending and completion failed |
| `empty_artifact` | no artifact, no origin, or artifact has no useful block/thoughts |
| `unknown` | fallback bucket; should be rare |

Recommended threshold for `tool_mismatch`: `tool_similarity < 0.75`.

## Snapshot helpers

Add local helper functions in `run_traces.py` rather than expanding `_snapshot.py` yet:

```python
def _belief_snapshot(agent) -> dict:
    state = agent.world.state
    return {
        "intent": state.pred_intent,
        "pred_flows": state.pred_flows,
        "confidence": state.confidence,
        "pred_slots": state.pred_slots,
    }

def _ambiguity_snapshot(agent) -> dict:
    ambiguity = agent.world.ambiguity
    return {
        "present": ambiguity.present,
        "level": ambiguity.get_level() if ambiguity.present else "",
        "metadata": dict(ambiguity.metadata),
        "observation": ambiguity.observation,
    }

def _artifact_snapshot(result) -> dict:
    artifact = result.get("artifact") or {}
    blocks = artifact.get("blocks") or []
    return {
        "origin": artifact.get("origin", ""),
        "block_types": [block.get("type") for block in blocks],
        "has_content": bool(artifact.get("thoughts") or blocks),
    }
```

Use `agent.world.state`, not `world.current_state()`.

For grounding, preserve the new nested Dialogue State shape:

```python
grounding_after = {
    "choices": list(state.grounding.get("choices", [])),
    "notes": list(state.grounding.get("notes", [])),
    "entities": list(state.grounding.get("entities", [])),
}
```

## Tool logging

Current `_install_tool_logger` records only tool names. Keep that for scoring, but add an optional
full log:

```python
{"name": tool_name, "input": tool_input, "result_success": result.get("_success")}
```

The full log should not dump large result payloads into JSONL; record `result_success`,
`result_error`, and `result_message` only.

## Shared Trace Writer

Move trace-record creation into a small shared helper module, for example:

```text
utils/evaluation_suite/trace_writer.py
```

Responsibilities:

- build `_belief_snapshot`, `_ambiguity_snapshot`, `_artifact_snapshot`, and grounding snapshots;
- build one trace record per user turn;
- write JSONL lines;
- classify the coarse `diagnosis`;
- keep result payloads compact.

`_traces/run_traces.py` and the suite-composed eval path both use this helper. The eval path should
record traces during the same live pass that computes eval scores, not by running the conversations
twice.

## Console output

At run start:

```text
trace ids: B04.C16,B04.C01,B02.C04
trace report: utils/evaluation_suite/report/traces_20260709_143022.jsonl
```

Per turn:

```text
B04.C16 t1: policy_incomplete | complete=no | tools=0.50 | belief=write/0.70 | 14.2s
```

Per conversation:

```text
B04.C16: 1/4 completed in 86s | transcript database/sessions/B04.C16/messages.jsonl
```

Final:

```text
completion_rate=0.25 tool_match_rate=0.083 mean_turn_seconds=17.18
diagnoses: policy_incomplete=5 wrong_belief=2 ambiguity_pending=1
```

## Tests

Add deterministic tests under `utils/evaluation_suite/_tests/` where practical:

1. `sample(n, seed)` is already in `harness.py`; add a trace-runner unit around ID selection
   if helper extraction is needed.
2. `_diagnose_turn(...)` maps:
   - timeout payload → `turn_timeout`
   - crash fallback → `crash_fallback`
   - wrong expected flow → `wrong_belief`
   - ambiguity present → `ambiguity_pending`
   - no domain tools when expected → `no_domain_tools`
3. `_trace_record(...)` serializes with required keys and nested grounding.
4. `run_suite.py --evals` command construction includes traces before evals.
5. Direct `_evals/run_evals.py` does not implicitly run the traces tier.
6. Existing deterministic suite remains green:

```bash
python utils/evaluation_suite/run_suite.py --tests nlu,pex,mem
```

## Manual verification

Default smoke run:

```bash
PYTHONPATH=/Users/derekchen/Documents/repos/personal_assistants \
/opt/miniconda3/envs/env314/bin/python \
assistants/Hugo/utils/evaluation_suite/_traces/run_traces.py \
--sample 8
```

Expected:

- command completes without crashing;
- selected IDs print before live calls and are not hardcoded in the runner;
- report JSONL path prints and exists;
- each user turn has a JSONL record;
- every failed turn has a non-`unknown` diagnosis unless genuinely surprising;
- transcript paths exist under `assistants/Hugo/database/sessions/<convo_id>/messages.jsonl`;
- deterministic suite stays green.

Suite-level eval observability run:

```bash
PYTHONPATH=/Users/derekchen/Documents/repos/personal_assistants \
/opt/miniconda3/envs/env314/bin/python \
assistants/Hugo/utils/evaluation_suite/run_suite.py \
--sample 8
```

Expected:

- deterministic unit tests run before the live pass;
- the sampled conversations are traversed once for eval scoring and trace recording;
- E2E eval scores still print normally;
- an `evals_trace_<timestamp>.jsonl` artifact is written and printed;
- direct `run_evals.py --sample 8` does not run the traces tier implicitly.

For a known failure, a developer may pass explicit IDs from an eval run:

```bash
python utils/evaluation_suite/_traces/run_traces.py --ids B04.C16,B04.C01,B02.C04
```

That command is diagnostic only; it must not become the default sample.

## Acceptance criteria

- A developer can run the default 8-case trace sample, or an explicit debug subset, and answer
  for each failed turn:
  - what NLU believed;
  - what domain tools were expected vs called;
  - whether ambiguity was pending;
  - what flow stack remained;
  - where the full transcript lives;
  - the coarse failure diagnosis.
- `run_traces.py --sample 8 --seed 1` is reproducible.
- `run_traces.py --ids ...` does not grade against the baseline; it is human-read diagnostics.
- Full-train `--all` behavior and baseline gate remain unchanged.
- `run_suite.py --evals` includes traces by default from the same eval pass so broken E2E evals
  have trace artifacts without double-running conversations.
- Direct `run_evals.py` remains eval-only.
