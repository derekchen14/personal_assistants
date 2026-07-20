# Evaluation Suite

How Hugo is measured, and how to read what happened when a run looks wrong. Full design lives in
`_specs/utilities/evaluation_suite.md`; this file is the practical entry point. The complete package
is called the "evaluation suite", with three tiers inside it: (1) tests (2) traces (3) evals.

## Default: run the suite

When we say "run the suite", use the standard entry point with no tier-selection flags:

```bash
python utils/evaluation_suite/run_suite.py
```

By default this does three things:

1. Runs the deterministic code/unit tests.
2. Samples 8 conversations from the eval corpus.
3. Runs one E2E eval pass over that sample and records trace JSONL during the same pass.

The sampled conversations are traversed once. The eval metrics and trace records come from that same
run; do not run traces and evals as two separate passes unless you are deliberately debugging one
tier in isolation.

For a smaller smoke run:

```bash
python utils/evaluation_suite/run_suite.py --sample 4
```

## The three tiers

Run everything through the one entry point (`run_suite.py`). Tier flags narrow the run to that tier
only; the default command above is the normal full-suite path.

| Tier | Flag | What it checks |
| --- | --- | --- |
| **Model Unit Tests** | `--tests [nlu,pex,mem]` | deterministic component behavior, no model calls |
| (probabilistic half) | `--model [nlu,pex,mem]` | single-prompt component accuracy, live |
| **Observability Traces** | `--traces` | per-turn trajectory: did the turn complete, did tools match |
| **E2E Agent Evaluations** | `--evals` | whole-conversation, 7 criteria (completion, correctness, ...) |

```bash
python utils/evaluation_suite/run_suite.py                         # tests + 8 sampled evals + traces
python utils/evaluation_suite/run_suite.py --sample 4              # smaller full-suite smoke run
python utils/evaluation_suite/run_suite.py --tests nlu             # tests only
python utils/evaluation_suite/run_suite.py --model nlu             # model tests only
python utils/evaluation_suite/run_suite.py --traces --ids B04.C01  # traces only, chosen subset
python utils/evaluation_suite/run_suite.py --evals --ids B01.C01   # evals only, chosen subset
```

The corpus is `datasets/train.jsonl` and `datasets/dev.jsonl`, one JSON object per line.
A run with no `--ids` takes a fresh random sample of 8.

## Reading traces (how to diagnose a bad run)

Every scenario run writes the **full turn record** to disk — this is the observability trace. You
do not re-run the agent to see what happened; you read the files.

```
database/sessions/<convo_id>/history.jsonl      # every turn: user/agent/system, tool calls + results
database/sessions/<convo_id>/subagents.jsonl    # one line per policy sub-agent run: its tool
                                                # trajectory ({tool, input, _success, _error}) +
                                                # the flow, end status, and terminal thoughts
database/sessions/<convo_id>/scratchpad.jsonl   # the session scratchpad (NLU announcements,
                                                # completion entries, contemplate requests)
```

A run names its session after the scenario (e.g. `database/sessions/B04.C01/`), so the transcript is
findable per case. In history.jsonl, agent action turns carry `tool_uses` + `tool_results` — a
`_success: false` on `manage_flows` is a failed policy run; the matching subagents.jsonl line shows
what the sub-agent actually did (or failed to do) inside that run.

Read three or four turns in order and the break point is visible: a wrong flow in the `[nlu]` note,
a `_success: false` on `manage_flows`, or a sub-agent that never called its save tool.

The suite also writes structured trace records under:

```text
utils/evaluation_suite/report/evals_<timestamp>.json
utils/evaluation_suite/report/evals_trace_<timestamp>.jsonl
utils/evaluation_suite/report/traces_<timestamp>.jsonl
```

Default suite runs produce `evals_*.json` for eval metrics and `evals_trace_*.jsonl` for turn-level
traces from the same pass. Direct trace-tier runs produce `traces_*.jsonl`. `run_suite.py` keeps
only the most recent 128 trace JSONL files by default; tune that with `--keep-traces N`.

Sessions are gitignored and pruned to the most recent N, so copy a transcript out if you need to keep
it past the next run.

## Shortcut

The canonical command is short enough to use directly for now:

```bash
python utils/evaluation_suite/run_suite.py
```

If this becomes frequent enough to need muscle memory, prefer a repo-local shortcut that still calls
that command unchanged, for example a future Make target like `make hugo-suite`. Avoid making a
shortcut that adds tier flags; that would stop being the standard suite run.

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

## Corpus curation

`curate_corpus.py` denoises and filters the train split in review rounds. Its audit and selection
commands write reports only; corpus changes require a resolved round manifest or final selection.

```bash
python utils/evaluation_suite/curate_corpus.py audit
python utils/evaluation_suite/curate_corpus.py judge --tier high --resume  # only when needed
python utils/evaluation_suite/curate_corpus.py round --round 1 --limit 12
python utils/evaluation_suite/review_app/server.py
python utils/evaluation_suite/curate_corpus.py apply-round --dry-run
python utils/evaluation_suite/curate_corpus.py apply-round
python utils/evaluation_suite/curate_corpus.py select --target 128
python utils/evaluation_suite/curate_corpus.py finalize --target 128 --dry-run
```

The review ledger has a hard budget of 32 review events. Re-reviewing one conversation in a later
round consumes another event. An open round must be fully resolved before it can be applied, and an
open round blocks finalization.
