# Engineering Team — Pipeline

A five-role sub-agent team that takes **one [Master Plan](../_review/master_plan.md) step at a time**
from spec to a commit on master. Each role runs as an isolated sub-agent; the only thing that crosses
between them is a named **handoff artifact**, so every boundary is inspectable and context stays
compressed.

**Git workflow (Derek 2026-07-04 — no PRs):** (1) develop the plan with the PM, (2) SWEs/DoE/QA write
the code, (3) make a commit, (4) after a few commits, push to master. Derek reviews in the loop after
steps 1, 2, and 3 — the review happens live, not on a pull request, so PRs are not part of the
workflow (too much overhead for a one-person team; may change later).

Roles: [PM](./pm.md) · [SWE1](./swe1.md) · [SWE2](./swe2.md) · [DoE](./doe.md) · [QA](./qa.md)

## Handoff artifacts

| Artifact | Produced by | Consumed by | Contents |
|---|---|---|---|
| **Decision Options** | PM | User | At least 3 open decisions shown as 2-3 fleshed alternatives with pros/cons |
| **Spec sheet** | PM | SWE1, SWE2, QA | Feature definition, user stories, pseudo-code, and the test plan (unit / traces / evals) with expected results; every open decision shown as 2-3 fleshed alternatives with pros/cons |
| **Implementation plan** | each SWE | DoE | Detailed plan of action, for pre-approval before any code |
| **Change set** | each SWE | DoE, QA | The diff plus a self-review (what changed, why, scope adherence, tests satisfied) |
| **Verdict** | QA | DoE | Pass/fail per acceptance criterion, with cited evidence |
| **Commit** | DoE | human | Final commit (reviewed live by Derek; pushed to master after a few accumulate) |

Artifacts pass agent-to-agent — the orchestrator hands each as the next role's input. Every round,
persist all of them under `plans/round_<id>_artifacts/` (the SWE plans, the DoE approval and
adjudication, the QA verdict) so the back-and-forth is readable after the fact, and relay the DoE's
approval notes and adjudication summary to Derek during the round, not only the final report.

## Presenting a plan (required in every plan, PM or orchestrator)

Every plan presented for sign-off — a PM Spec sheet or a plan the orchestrator writes directly — must
state, up front:

1. **New concepts** — anything the change adds that did not exist before: a class, component, config
   key, field, file kind, or term. For each, show a concrete example of what is actually added. When
   there are none, say "no new concepts" explicitly.
2. **Big decisions** — each one with its pros and cons spelled out.
3. **Alternatives** — for each big decision, 1-2 alternatives we could have taken, with their own pros
   and cons.

A plan missing these three call-outs is not ready for sign-off. Small rounds still state them — often
the answer is one line ("no new concepts; no big decisions"), and that line is the point.

## Pipeline

1. **Spec** — PM reads the Master Plan step and code to develop decision options to iterate on
   with the user. This should produce a signed-off **Spec sheet**. This is displayed in Plan Mode.
   Execution does not begin until the user approves.
2. **Plan** — SWE1 and SWE2 each read the Spec sheet → an **Implementation plan**. DoE approves each (or
   returns it) before any code is written.
3. **Build** — each SWE implements its approved plan → a **Change set**.
4. **Adjudicate** — DoE compares the two Change sets and picks or merges via the divergence ladder below.
5. **Verify** — QA checks the chosen Change set against the Spec's test plan → a **Verdict**. Any fail
   returns to the SWEs to repeat steps 2 to 4; all-pass continues.
6. **Ship** — DoE turns the passing Change set into a **Commit**; Derek reviews it live. After a few
   commits accumulate, push to master — no branches or PRs.

## Two SWEs, divergent mandates

SWE1 and SWE2 run in parallel on the **same** Spec sheet but optimize for **different** ends, so any
difference between them is a signal about a real tradeoff — not noise to average away:

- **SWE1 — minimal diff / maximal reuse:** smallest change, reuse existing APIs, zero new concepts.
- **SWE2 — normative / clean design:** implement from the ideal end-state, flag where the minimal path
  accrues debt.

DoE adjudicates the result:

| Divergence | Reading | DoE action |
|---|---|---|
| Converge (≈ identical) | Even the simplest and the cleanest approach agreed — the design is forced | Keep it |
| Minor | Two viable shadings of one approach | DoE decides which way |
| Major | A genuine fork — the spec admits different interpretations | Surface both to the user to decide |
