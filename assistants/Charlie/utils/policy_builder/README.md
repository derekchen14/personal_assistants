# Policy Builder

Human-in-the-loop tool for iteratively refining the 9 eval-covered policies + skills that aren't already hand-written. See [`policy_spec.md`](policy_spec.md) for the full 5-part plan and [`decision_points.md`](decision_points.md) for the per-flow decision catalog.

Scope note: `refine`, `compose`, and `simplify` are the three hand-written exemplars whose current skill files at `backend/prompts/pex/skills/{refine,compose,simplify}.md` *define* the DP precedents. They are not routed through the app.

## Layout

```
policy_spec.md             running spec; updated as each part completes
decision_points.md         Part 5a \u2014 per-flow decision catalog (23 universal + 19 per-flow DPs)
inventory/                 Part 1 \u2014 filled templates per flow + SUMMARY
best_practices.md          Part 2 \u2014 latest-2026 research
census.md                  Part 3 supporting \u2014 repeated-pattern tally
fixes/                     Part 3 \u2014 per-flow changelog + _shared + _interfaces
eval_design.md             Part 4 \u2014 CLI + Playwright harness architecture
server.py / index.html / app.js / data/   Part 5a \u2014 HITL app (port 8022)
LESSONS.md                 Part 5b \u2014 end-of-project synthesis
failures/                  Part 4 runtime dumps (git-ignored once real)
```

## Data layout

```
data/
  proposals/<flow>.json    Claude's round-1 answers for each of the 19 DPs
  answers/<flow>.json      User-exported accept/override + transferable rationale
  drafts/<flow>.json       Claude's round-2 final draft (batch-end output)
  feedback/<flow>.json     User's round-2 feedback (optional)
```

Each `proposals/<flow>.json` has shape:

```json
{
  "flow": "refine",
  "parent_intent": "Draft",
  "batch": 1,
  "round": 1,
  "decision_points": {
    "DP-1": {
      "section": "Prompt content",
      "title": "...",
      "question": "...",
      "proposal": "...",        // string, OR {"propose": "...", "direct": "..."} for multi-mode flows
      "reasoning": "..."
    }
  }
}
```

`answers/<flow>.json` has shape:

```json
{
  "flow": "refine",
  "batch": 1,
  "round": 1,
  "decision_points": {
    "DP-1": {
      "accepted": true,
      "override": null,
      "rationale": "transferable cross-flow reasoning"
    }
  }
}
```

## Running the app

From the `assistants/Hugo/` directory:

```bash
python utils/policy_builder/server.py
```

Then open `http://localhost:8022`. The header shows the current batch, a dropdown switcher across the 3 flows, and a save button. Section tabs (Prompt content / Starter / Few-shot / Error handling / Policy logic / Performance) filter the DPs displayed.

Each DP card renders: title, question, the read-only proposal + collapsible reasoning, an Accept/Override radio, an override textarea (or per-mode textareas for multi-mode flows), and a rationale textarea for transferable cross-flow reasoning.

Changing the batch is currently a constant in `server.py` (`CURRENT_BATCH = 1`).

## Playwright UI tier (Part 4, Phase 3)

Tier 3 of the eval stack \u2014 drives the real browser against `http://localhost:5174`. Gated on the `--ui` pytest flag so CI default-skips it.

Install:

```bash
uv pip install pytest-playwright
playwright install chromium
```

Run:

```bash
python -m pytest utils/tests/playwright_evals/ --ui
```

When the `--ui` flag is absent the whole directory skips. The conftest starts backend (port 8001) and frontend (port 5174) only if they are not already running, and tears down only what it started.

Failure dumps land in `utils/policy_builder/failures/<run_id>/`, where `<run_id>` is `YYYYMMDD_HHMMSS`. Schema is fixed by `eval_design.md \u00a7 Failure-dump format`. The same writer (`utils/tests/playwright_evals/dump.py`) is called by both CLI and Playwright tiers \u2014 it has no Playwright import dependency.
