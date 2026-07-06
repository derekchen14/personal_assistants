# Evaluation Suite

How Hugo is measured, and how to read what happened when a run looks wrong. Full design lives in
`_specs/utilities/evaluation_suite.md`; this file is the practical entry point. The complete package
is called the 'evalaution suite', with three tiers inside of it: (1) tests (2) traces (3) evals.

## The three tiers

Run everything through the one entry point (`run_suite.py`). By default only the free deterministic
tests run — every tier is opt-in and paid.

| Tier | Flag | What it checks |
| --- | --- | --- |
| **Model Unit Tests** | `--tests [nlu,pex,mem]` | deterministic component behavior, no model calls |
| (probabilistic half) | `--model [nlu,pex,mem]` | single-prompt component accuracy, live |
| **Observability Traces** | `--traces` | per-turn trajectory: did the turn complete, did tools match |
| **E2E Agent Evaluations** | `--evals` | whole-conversation, 7 criteria (completion, correctness, ...) |

```
python utils/evaluation_suite/run_suite.py                # free tests, all modules
python utils/evaluation_suite/run_suite.py --traces       # per-turn trajectory (paid)
python utils/evaluation_suite/_traces/run_traces.py --ids B04.C01,B05.C01   # a chosen subset
python utils/evaluation_suite/_evals/run_evals.py --ids B01.C01             # conversation scoring
```

The corpus is `datasets/train.jsonl` and `datasets/dev.jsonl`, one JSON object per line.
A run with no `--ids` takes a fresh random sample of 8.

## Reading traces (how to diagnose a bad run)

Every scenario run writes the **full orchestrator transcript** to disk — this is the observability
trace. You do not re-run the agent to see what happened; you read the file.

```
database/sessions/<convo_id>/messages.jsonl
```

A run names its session after the scenario (e.g. `database/sessions/B04.C01/`), so the transcript is
findable per case. Each line is one API-shaped message in order:

- `read_state` result + a `[belief]` line — NLU's detection for the turn (intent, flow, confidence,
  slots). This is where you see what the agent *thought* the user wanted.
- `write_state` / `activate_flow` calls — what PEX actually dispatched, and the result (or the error).
- the final assistant text — the reply the user saw.

Read three or four turns in order and the break point is visible: a wrong flow at `[belief]`, a
`_success: false` on `activate_flow`, or a flow that finishes without ever grounding a post.

Sessions are gitignored and pruned to the most recent N, so copy a transcript out if you need to keep
it past the next run.

## Seed library (the standing posts)

Scenario openers reference draft posts that must already exist. Those posts are **real committed blog
drafts**, not a dataset file — that is why they are not under `datasets/`:

```
database/content/drafts/*.md   +   database/content/metadata.json
```

32 drafts (16 topics x 2), tags carrying query keywords so `find_posts` (a plain substring match)
resolves the openers. They were generated once and committed (a2445f6); the generators are archived
in `utils/trash_suite/` (`library_spec.py`, `library_prose.py`, `seed_library.py`). To regenerate,
restore those and run `seed_library.py`.

## Eval hygiene

Live runs mutate `database/content` (create/edit/publish posts). **Commit before running**, then
restore after:

```
git restore assistants/Hugo/database/content
git clean -fd assistants/Hugo/database/content
```
