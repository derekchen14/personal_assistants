# Step 6 — Config / Eval / Server / Blocks infra

Maps to **Master Plan · Step 6**. Effort **M–L**. Depends on: **Step 1** (parity oracle convergence). The
catch-all conformance step; several items are spec-fixes or designed-not-built markers rather than code.

**Goal:** conform the remaining infrastructure surfaces. **Deliverable:** the items below; offline suites
green; the trace + parity gates current.

Spec: `utilities/{configuration,evaluation,blocks,server_setup}.md`.

---

## A. Config

### 6.A1 — Validating loader + ontology merge  · A5 · M/L
- `config.py:41-53` validates ~3 things (sections present, `persona.{name,tone,response_style}`,
  `models.default`). Spec (`configuration.md` ~L468-486) wants per-section checks (provider enum, temperature
  range, allocation sums, **flow integrity + dax-code conflicts**, policy-path resolution) and a
  `config.flows` populated from `ontology.py` (~L458 step 4) — which Hugo never merges.
- Build a validating loader that freezes (Hugo already `_deep_freeze`s) and **refuses to start on bad
  config**, staged by `environment` (warn in dev, fail in prod, `configuration.md:428`). Add `compression` +
  `content_validation` to `_REQUIRED_SECTIONS` (they're read but unvalidated, `config.py:14-18`).

### 6.A2 — `content_validation` ↔ `response_constraints` (E4)  · A3
- `content_validation` (`tools.yaml:64`, a **flow allowlist**, consumed `pex.py:233`) ≠ `response_constraints`
  (required by `config.py:17`, satisfied via shared default, **no consumer**). Verify the flow names in the
  list against `ontology.py` (`compose`/`write` may be stale).
- **Embedded decision E4:** rec — keep `content_validation`; have spec §12 absorb it; wire
  `response_constraints` length-bounds/self-check only if that behavior is actually wanted (else mark it
  designed-not-built and stop requiring it).

### 6.A3 — Session limits  · A6 · M
- `session.{max_turns,max_flow_depth,idle_timeout_ms}` are unconsumed. Enforce the runaway guards
  (`max_turns`, `max_flow_depth`) — backend-only, cheap. `max_flow_depth` feeds Step 5's depth bump.
- **Deferred:** `human_in_the_loop.tool_approval` (lethal-trifecta gate) — the `capabilities` metadata
  is captured per tool but the gate that consumes it needs a frontend round-trip; stub + marker.

### 6.A4 — `tier` + persistence truth-up (E11)  · A4 / D4
- Add the spec-mandated `tier in {basic,pro,advanced}` validation; Hugo is `basic` by inheritance (correct).
- **Embedded decision E11:** `session.persistence.backend: postgres` (shared default) is **unhonored** —
  Hugo persists sessions to the filesystem (`world.py:47-63`). Rec — document file-based as the basic-tier
  truth and fix/repoint the config key so it stops lying.

---

## B. Evaluation

### 6.B1 — Parity oracle re-baseline (E8)  · B2
- `comparator.py`'s oracle was captured from the **deleted** legacy pipeline (`capture_oracle.py`) and can't
  be regenerated. **Embedded decision E8:** rec — re-baseline from an approved orchestrator run, converging
  L3a parity with Step 1's approved-trace model so parity stays a live gate.

### 6.B2 — Pyramid organization + gate thresholds  · B3
- Organize the existing suites into the spec's ladder (L1a unit/property, L1b component-isolation, L2a trace
  replay [Step 1], L2b robustness, L3a parity) and add the regression-gate thresholds table
  (`evaluation.md:124-135`).
- **Orphan cleanup:** `test_res_module.py` / `test_res_tool_llm.py` are near-empty RES-era stubs — remove.

### 6.B3 — L2b robustness probes  · B4 · M (optional, lower priority)
- A focused suite for injection / reserved-keyword / length guards + the corrective-loop cap. Depends on the
  (deferred) tool-approval gate for the trifecta probe — keep minimal.

---

## C. Blocks

### 6.C1 — Reconcile the rendering model (E3)  · C1
- `blocks.md` contains **two competing models**: the `inline` attribute (`:18-54`) vs `top`/`bottom` panel
  zones (`:82-98`). Hugo faithfully implements the panel-zone model (`task_artifact.py:8-17`,
  `BlockRenderer.svelte`). **Embedded decision E3:** rec — converge the **spec** to Hugo's panel model;
  do **not** add `inline` to Hugo. (Spec fix, not a code change.)

### 6.C2 — Block-type registry sync  · C2
- `VALID_BLOCK_TYPES` (`task_artifact.py:3`) omits `grid` and `form` though those Svelte components exist and
  `chat_service.py` emits `type='grid'` — a latent validation bug. Add `grid` (decide on `form`). Hugo's
  block set otherwise **exceeds** the spec (no gap). Add `compare`/`selection` to Hugo's documented block
  palette in the spec so they aren't later "fixed" as non-canonical.

### 6.C3 — Stale comment  · C3
- `tools.yaml:611` template-registry comment — already handled in Step 0; verify gone.

---

## D. Server

### 6.D1 — WS mid-turn progress streaming  · D1 · M
- `chat_service.py` sends a single `result` dict per turn (`agent.py:139-140`, `:275`); no typed multi-message
  stream, no live `toast`/progress. Orchestrator turns run up to 8 rounds / minutes → a real UX gap.
- Per `server_setup.md:107-119`, stream **only** `text` + feedback live; blocks deliver once at turn end ("PEX
  owns ending the turn"). Emit typed messages from the loop; reconcile the frontend. Bounded scope.

### 6.D2 — WS field names + panel CRUD (E6)  · D2
- Minor naming drift: `dax` vs `dialogueAct`, `payload` vs `lastAction` (`chat_service.py:314-316`).
- **Embedded decision E6:** Hugo handles panel create/update/delete directly in the router; the spec routes
  panel interactions through NLU `react()`. Rec — keep the direct handlers (faster); add a spec note rather
  than refactor.

### 6.D3 — Health + lifespan  · D3
- `health_service.py:7-8` returns `{'status':'ok'}` only — add a config-loaded assertion
  (`server_setup.md:74-80`). Note: `webserver.py:37` uses the deprecated `@app.on_event('startup')` — migrate
  to FastAPI lifespan (minor, unrelated to spec).

### 6.D4 — Out of scope (basic tier)  · D5
- JWT/OAuth/Credential table/rate-limiting are pro/advanced (`configuration.md:437-447`). Hugo's
  username-only WS auth + permissive localhost CORS match basic tier. **Do not build** — recorded so they're
  not mistaken for gaps.

---

## E. Tool manifest (E7)  · Flows-report divergence #1
- Manifest entries (`tools.yaml`) carry `tool_id/name/description/input_schema/idempotent/timeout_ms/
  capabilities` but omit the spec's `scope`/`dispatch`/`output_schema` Core Fields (`tool_smith.md:497-512`).
  Hugo routes via each flow's `self.tools` + a code-side dispatch table instead.
- **Embedded decision E7:** rec — **document the code-side routing** (one sentence in `tool_smith.md`); don't
  back-fill the manifest fields.

## Deferred here (stubs)
Tool-approval / lethal-trifecta HITL gate; telemetry endpoint (`/api/v1/telemetry`); responsive block hints;
`models.cost` budgeting; `feature_flags.proactive_issue_detection`.

## Verification
- Offline gate suites green (cwd wrapper); the new config validator must not reject the current valid config.
- Parity harness re-baselined and passing post-E8; trace gate current.
- Smoke: bad config (e.g. provider typo) fails startup in prod mode, warns in dev; `/health` reports
  config-loaded; a long orchestrator turn streams progress before the final blocks.
