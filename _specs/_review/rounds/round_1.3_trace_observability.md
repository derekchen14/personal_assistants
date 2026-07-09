# Round 1.3 — Trace observability for task-completion failures

Status: **draft for alignment**. Owner: evaluation infrastructure. Builds on Round 1.1/1.2 and
the current `utils/evaluation_suite/` layout. This is a diagnostics round, not an agent-behavior
round.

---

## Why this round

The latest 3-conversation E2E sample completed without crashing after the grounding cleanup and
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

This round makes traces the primary observability tool for task-completion failures.

## Scope

In scope:

- Improve `assistants/Hugo/utils/evaluation_suite/_traces/run_traces.py`.
- Add structured trace records under the evaluation report directory.
- Add deterministic sample controls.
- Add per-turn diagnostic snapshots from the current `world.state`, `world.flows`, and
  `world.ambiguity`.
- Keep traces runnable for a chosen 3-case subset.

Out of scope:

- Improving task success itself.
- Adding replay/recording of model responses.
- Changing NLU/PEX behavior except for compatibility fixes required to let traces run.
- Re-baselining the full train trace gate.
- Building a UI trace viewer.

## Target command shape

Keep existing commands working:

```bash
python utils/evaluation_suite/_traces/run_traces.py
python utils/evaluation_suite/_traces/run_traces.py --ids B04.C16,B04.C01,B02.C04
python utils/evaluation_suite/_traces/run_traces.py --all
```

Add:

```bash
python utils/evaluation_suite/_traces/run_traces.py --sample 3 --seed 1
python utils/evaluation_suite/_traces/run_traces.py --sample 3 --seed 1 --jsonl
```

Behavior:

- `--ids` wins over `--all`, `--sample`, and `--seed`.
- `--all` runs the full train split and remains the only gated mode.
- No `--ids` and no `--all` uses `sample(args.sample, seed=args.seed)`.
- Default remains sample size 8 with no seed, preserving current behavior.
- The runner prints selected IDs before any live model calls.

## Trace output

Each run should write one JSONL file:

```text
utils/evaluation_suite/report/traces_<timestamp>.jsonl
```

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
4. Existing deterministic suite remains green:

```bash
python utils/evaluation_suite/run_suite.py --tests nlu,pex,mem
```

## Manual verification

Use the three IDs from the latest completed E2E sample:

```bash
PYTHONPATH=/Users/derekchen/Documents/repos/personal_assistants \
/opt/miniconda3/envs/env314/bin/python \
assistants/Hugo/utils/evaluation_suite/_traces/run_traces.py \
--ids B04.C16,B04.C01,B02.C04
```

Expected:

- command completes without crashing;
- selected IDs print before live calls;
- report JSONL path prints and exists;
- each user turn has a JSONL record;
- every failed turn has a non-`unknown` diagnosis unless genuinely surprising;
- transcript paths exist under `assistants/Hugo/database/sessions/<convo_id>/messages.jsonl`;
- deterministic suite stays green.

## Acceptance criteria

- A developer can run a 3-case trace subset and answer, for each failed turn:
  - what NLU believed;
  - what domain tools were expected vs called;
  - whether ambiguity was pending;
  - what flow stack remained;
  - where the full transcript lives;
  - the coarse failure diagnosis.
- `run_traces.py --sample 3 --seed 1` is reproducible.
- `run_traces.py --ids ...` does not grade against the baseline; it is human-read diagnostics.
- Full-train `--all` behavior and baseline gate remain unchanged.
