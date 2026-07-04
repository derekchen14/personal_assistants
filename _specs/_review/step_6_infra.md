# Step 6 — Config / Server / Blocks / Tool-manifest infra

Maps to **Master Plan · Step 6**. Effort **M–L**. Depends on: nothing structural (the eval items moved to
Step 1). The catch-all conformance step; several items are spec-fixes or designed-not-built markers rather
than code.

**Goal:** conform the remaining infrastructure surfaces. **Deliverable:** the items below; offline suites
green.

Spec: `utilities/{configuration,blocks,server_setup,tool_smith}.md`.
**Evaluation moved out:** the eval system (parity oracle re-baseline E8, the test pyramid, robustness) is now
owned by **`step_1_evals.md`**. Step 6 keeps only the non-eval infra (config / server / blocks / manifest)
plus deleting the two RES-era test tombstones (6.11).

**Reading the current code.** The pieces this step touches:
- `schemas/config.py`: `load_config` (`:56-64`) → `_validate` (`:41-54`) checks sections present +
  `persona.{name,tone,response_style}` + `models.default`. `_REQUIRED_SECTIONS` (`:14-18`) does **not**
  include `compression` or `content_validation` (both are read elsewhere but unvalidated). `_deep_freeze`
  (`:21-26`). `config.flows` is **never** populated from `ontology.FLOW_CATALOG`.
- `schemas/tools.yaml`: `content_validation` (`:62-65`) = `[compose, rework, write]` (a flow allowlist),
  consumed at `pex.py:236` (the `_llm_quality_check` is commented at `pex.py:240`). `response_constraints`
  (`shared_defaults.yaml:140-149`) is required by config but has **no consumer**.
- Session limits (`shared_defaults.yaml:52-60`): `max_flow_depth` is **enforced** (`stack.py:12,98-101`);
  `max_turns` (256) and `idle_timeout_ms` are **defined but not enforced**; `session.persistence.backend:
  postgres` is **unhonored** (Hugo persists to the filesystem via `world.py`); `max_sessions` is consumed
  (`world.py:87`).
- `task_artifact.py`: `VALID_BLOCK_TYPES` (`:3`) = `(card, checklist, confirmation, toast, default,
  selection, list, compare)` — **no `grid`, no `form`**; `_TOP_BLOCK_TYPES` (`:4`) **does** include `grid`;
  `chat_service.py` emits `type='grid'` (`:52,168,334`) → a **latent validation bug**. `BuildingBlock`
  (`:8-17`) implements the **panel-zone** model (`panel='top'|'bottom'` + `expand`).
- `chat_service.py`: one `result` dict per turn (`{message, actions, artifact}` via `agent.py:144`); WS input
  fields `text`/`currentMessage`/`dax`/`payload` (`:314-316`); `send_json` (`:275`); **no progress stream**.
- `health_service.py` (`:6-8`) returns `{'status':'ok'}`; `webserver.py:37` uses the deprecated
  `@app.on_event('startup')`.
- Tool manifest entries carry `tool_id/name/description/input_schema/idempotent/timeout_ms/capabilities` —
  **no** `scope`/`dispatch`/`output_schema`.

---

## Decisions

**Locked (this step implements):**
- **Validating config loader + ontology merge.** Refuse to start on bad config (warn in dev, fail in prod);
  add `compression` / `content_validation` to the required sections; populate `config.flows` from
  `FLOW_CATALOG`. (§6.1)
- **Enforce `max_turns`.** A cheap backend runaway guard at turn entry; `max_flow_depth` is Step 5.3;
  `idle_timeout_ms` is noted and deferred. (§6.3)
- **Block-type registry sync.** Add `grid` to `VALID_BLOCK_TYPES` — emitted but unlisted, a latent bug. (§6.5)
- **WS mid-turn streaming.** Stream `text` / `feedback` live; blocks deliver once at turn end. (§6.7)
- **Delete the RES test tombstones.** `test_res_module.py` + `test_res_tool_llm.py`. (§6.11)

**Resolved here — confirm or override:**
- **E3 · blocks rendering — DECIDED: one `panel` ∈ {top, bottom, left}.** `left` = the chat container (the old
  `inline` → `panel:'left'`). Spec rewritten; small code change to accept `'left'`. (§6.6)
- **E4 · content_validation + response_constraints — REMOVE both (decided).** Both are half-wired (the
  quality-check call is commented out; `response_constraints` has no consumer). Delete them; output quality
  lives in skill prompts + exemplars. (§6.2)
- **E6 · post/note CRUD routing — keep direct (decided).** Deterministic CRUD stays in the WS router (no LLM
  hop); standardize on `dax` + `payload`. **New:** each handler records a user-action turn in the
  ContextCoordinator so history reflects the edit. (§6.8)
- **E7 · tool-manifest fields — don't back-fill (decided).** `dispatch` + `output_schema` (and `scope`) stay
  in code only; one source is enough. Document the code-side routing in `tool_smith.md`; drop those fields
  from the spec's required manifest. (§6.10)
- **E11 · persistence — DECIDED: repoint to filesystem.** Hugo persists to disk; change
  `persistence.backend: postgres` → `filesystem` and validate `tier ∈ {basic,pro,advanced}`. (§6.4)

**Resolved (confirmed 2026-06-21):**
- **`form` block type — not added.** Grepped the frontend: nothing emits a `form` block. Only `grid` joins
  `VALID_BLOCK_TYPES`. (§6.5)

**Deferred / out of scope:**
- Out of scope (basic tier — do not build): JWT/OAuth, credentials table, rate-limiting. Stubs: tool-approval
  HITL gate (§S-1), telemetry endpoint (§S-2), responsive block hints (§S-3), cost budgeting + proactive flag
  (§S-4).

---

## 6.1 — Validating config loader + ontology merge  · A5
`_validate` (`config.py:41-54`) checks ~3 things. The spec (`configuration.md:468-486`) wants per-section
checks (provider enum, temperature range, allocation sums, **flow integrity + dax-code conflicts**,
policy-path resolution) and a `config.flows` populated from `ontology.py` (step 4 of the spec's load) —
which Hugo never merges.

**Change.** Expand `_validate` into a real validating loader that **refuses to start on bad config**, staged
by `environment` (warn in dev, fail in prod — `configuration.md:428`). Add `compression` to
`_REQUIRED_SECTIONS` (read but unvalidated) and **drop** `response_constraints` from it (removed in §6.2).
Merge the ontology into `config.flows`.

```python
# config.py — _validate, expanded
_REQUIRED_SECTIONS = frozenset({..., 'compression'})   # +compression; content_validation + response_constraints removed (§6.2)

def _validate(config:dict):
    errors = []
    errors += _missing_sections(config, _REQUIRED_SECTIONS)
    errors += _check_persona(config)                 # existing: name/tone/response_style
    errors += _check_models(config)                  # existing: models.default
    errors += _check_provider_enum(config['models']) # provider ∈ {anthropic, openai, google, qwen, deepseek}
    errors += _check_temperature(config['models'])   # 0.0 ≤ temperature ≤ 2.0
    errors += _check_flow_integrity(config)          # every dax unique + ascending digits; policy paths resolve
    _stage(errors, config['environment'])            # dev → log.warning; prod → raise ValueError

def _merge_ontology(config:dict) -> dict:
    from schemas.ontology import FLOW_CATALOG
    return {**config, 'flows': dict(FLOW_CATALOG)}    # the step-4 merge Hugo currently skips

# load_config: merge ontology, validate, then freeze (order matters — validate the merged shape)
merged = _merge_ontology(_merge_configs(shared, domain))
_validate(merged)
return _deep_freeze(merged)
```

`_check_flow_integrity` is where dax-code conflicts (two flows sharing a dax) and dead policy paths surface —
exactly the duplicate-key class that left `resilience.max_recovery_attempts` vs `recovery.max_repair_attempts`
both unread (Step 4.5).

## 6.2 — Remove `content_validation` + `response_constraints` (E4)  · A3
Both are half-wired and **removed** (decided 2026-06-21).
- `content_validation` (`tools.yaml:62-65`, the flow allowlist `[compose, rework, write]`) gated an LLM
  quality pass at `pex.py:236`, but the call (`pex.py:240`) is commented out — it gates nothing. Delete the
  `tools.yaml` block, the `pex.py:236-240` check, and `_llm_quality_check` (`pex.py:252+`).
- `response_constraints` (config, satisfied via shared default) has **no consumer**. Delete it from config +
  `_REQUIRED_SECTIONS` (§6.1).

Output quality is carried by the skill prompts + exemplars, not a runtime gate.

## 6.3 — Session limits  · A6
`session.{max_turns, idle_timeout_ms}` are unconsumed; `max_flow_depth` is already enforced (`stack.py`).
Enforce the runaway guard `max_turns` (backend-only, cheap); `max_flow_depth` is handled by Step 5.3.

```python
# agent.py — _orchestrate, at turn entry (after add_turn)
if state.turn_count >= self.config['session']['max_turns']:
    return self._fallback_response("This session has reached its turn limit — start a new one.")
```

`idle_timeout_ms` is a frontend/session-store concern; note it, defer enforcement. The
`human_in_the_loop.tool_approval` gate is **deferred** (stub S-1) — the `capabilities` metadata is captured
per tool, but the gate that consumes it needs a frontend round-trip.

## 6.4 — `tier` + persistence truth-up (E11)  · A4 / D4
Add the spec-mandated `tier in {basic, pro, advanced}` validation (Hugo is `basic` by inheritance — correct).

**Embedded decision E11 — DECIDED: repoint to filesystem.** `session.persistence.backend: postgres` (shared
default) is **unhonored** — Hugo persists sessions to the filesystem (`world.py`). Repoint the config key so it
stops lying and document file-based as the **basic-tier truth**:

```yaml
# shared_defaults.yaml — session.persistence
session:
  persistence:
    backend: filesystem      # was postgres; basic tier persists to database/sessions/<id>/
    max_sessions: 20         # already consumed by world.close()
```

## 6.5 — Block-type registry sync  · C2
`VALID_BLOCK_TYPES` (`task_artifact.py:3`) omits `grid` though `_TOP_BLOCK_TYPES` lists it and
`chat_service.py` emits `type='grid'` — a block that renders but fails validation if validation ever runs on
it. Hugo's block set otherwise **exceeds** the spec (no gap).

```python
# task_artifact.py — add the emitted-but-unlisted type
VALID_BLOCK_TYPES = frozenset((
    'card', 'checklist', 'confirmation', 'toast', 'default', 'selection', 'list', 'compare', 'grid'))
# 'form' is NOT emitted anywhere (grepped 2026-06-21) — do not add it; only 'grid' was missing.
```

Add `compare`/`selection`/`grid` to the spec's documented block palette (`blocks.md`) so they aren't later
"fixed" as non-canonical.

## 6.6 — Reconcile the blocks rendering model (E3)  · C1
`blocks.md` had **two competing models**: an `inline` attribute (`:18-54`) vs `top`/`bottom` panel zones
(`:82-98`). Hugo implements the panel-zone model (`task_artifact.py:8-17`, `BlockRenderer.svelte`), today with
`panel ∈ {top, bottom}`.

**Decided 2026-06-21:** converge to a **single `panel` attribute with three values — `top`, `bottom`, `left`**
— where `left` is the dialogue/chat container (the old `inline` becomes `panel: 'left'`). `blocks.md` is
rewritten to this model and the `inline` attribute is deleted. **Small code change:** extend Hugo's `panel` to
accept `'left'` (`task_artifact.py` `BuildingBlock`) and render `left` in the dialogue panel (`display.ts` /
`BlockRenderer.svelte`).

## 6.7 — WS mid-turn progress streaming  · D1
`chat_service.py` sends a single `result` dict per turn (`agent.py:144`); no typed multi-message stream, no
live `toast`/progress. Orchestrator turns run up to `max_rounds` (8) / minutes → a real UX gap.

**Change.** Per `server_setup.md:107-119`, stream **only** `text` + feedback live; **blocks deliver once at
turn end** ("PEX owns ending the turn"). Emit typed messages from the loop; reconcile the frontend.

```python
# chat_service.py — typed stream (bounded scope)
async def stream_turn(ws, agent, user_text, dax, payload):
    async for msg in agent.take_turn_streamed(user_text, dax, payload):
        await ws.send_json(msg)            # {type: 'text'|'feedback'|'result', ...}
    # 'text'/'feedback' arrive live during the loop; the single 'result' (blocks+artifact) lands last
```

PEX emits `text`/`feedback` events as the loop runs; the final `result` (blocks, artifact) is sent once at
turn end. Bounded — no change to how blocks are computed.

## 6.8 — Post/note CRUD routing + WS field names (E6)  · D2
Post/note CRUD from UI buttons (`create_post` / `update_post` / `delete_post` / `create_note` / `update_note` /
`delete_note`) is dispatched by the WS router (`chat_service.py:300-312`) to dedicated handlers that **bypass
the agent** (no NLU/PEX) and `continue`. Wire naming has minor drift (`dax` vs `dialogueAct`, `payload` vs
`lastAction`, `chat_service.py:314-316`).

**Decided 2026-06-21:** keep the direct handlers (deterministic CRUD shouldn't pay an LLM hop), standardize the
wire vocabulary on **`dax` + `payload`**, add a one-line spec note — **but** each handler must **record a
user-action turn in the ContextCoordinator** so history reflects the out-of-band edit (today they `continue`
silently, leaving the next agent turn blind to the change).

```python
# chat_service.py — after a direct CRUD handler runs, record it in L1 (ContextCoordinator)
agent.world.context.add_turn(speaker='user', text=f'{api_category}: {payload_summary}', turn_type='action')
# add_turn(speaker, text, turn_type) — context_coordinator.py:80
```

The next agent turn then sees the create/delete in `compile_history`, so a follow-up like "now publish it"
resolves against the just-created post.

## 6.9 — Health + lifespan  · D3
`health_service.py:6-8` returns `{'status':'ok'}` only — add a config-loaded assertion
(`server_setup.md:74-80`). Migrate `webserver.py:37`'s deprecated `@app.on_event('startup')` to a FastAPI
lifespan handler (minor, unrelated to spec).

```python
# health_service.py
@health_router.get('/health')
def health_check():
    ok = bool(load_config())                       # config loads + validates
    return {'status': 'ok' if ok else 'degraded', 'config_loaded': ok}

# webserver.py — lifespan instead of on_event
from contextlib import asynccontextmanager
@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(bind=engine)          # was the on_event('startup') body
    yield
app = FastAPI(lifespan=lifespan)
```

## 6.10 — Tool manifest Core Fields (E7)  · Flows-report divergence #1
Manifest entries (`tools.yaml`) carry `tool_id/name/description/input_schema/idempotent/timeout_ms/
capabilities` but omit the spec's `scope`/`dispatch`/`output_schema` Core Fields (`tool_smith.md:497-512`).
Hugo routes via each flow's `self.tools` + a code-side dispatch table instead.

**Decided 2026-06-21:** do **not** back-fill the manifest. `dispatch` (service vs internal) and `output_schema`
stay **in code only** — one source is enough (same for `scope`). Document Hugo's code-side routing in
`tool_smith.md` (one sentence) and drop `scope`/`dispatch`/`output_schema` from the spec's required manifest
fields so the manifest stops claiming them.

## 6.11 — Delete the RES-era test tombstones
`utils/tests/test_res_module.py` and `utils/tests/test_res_tool_llm.py` are now stub files whose bodies say
"Removed in the RES-removal refactor". Delete the files outright (the RES module is gone; PEX composes the
reply directly). Confirm no importer references them.

---

## Out of scope (basic tier)  · D5
JWT/OAuth, a credentials table, and rate-limiting are pro/advanced (`configuration.md:437-447`). Hugo's
username-only WS auth + permissive localhost CORS match the basic tier. **Do not build** — recorded so
they're not mistaken for gaps.

## Stubs — designed, not built (full specs)

### S-1 — Tool-approval / lethal-trifecta HITL gate  (`human_in_the_loop.tool_approval`)
Each tool entry already carries a `capabilities` block (`accesses_private_data`, `receives_untrusted_input`,
`communicates_externally`). The gate fires when a single turn touches all three legs of the trifecta and the
tool isn't on the approved list — pausing for a frontend approval round-trip.

```python
# pex.py — before dispatching a flagged tool (designed-not-built; needs a FE round-trip)
def _needs_approval(self, tool_name:str) -> bool:
    cap = self.config['flows']... # tool capabilities from the manifest
    mode = self.config['human_in_the_loop']['tool_approval']['mode']    # off | trifecta | explicit_list
    if mode == 'off':
        return False
    trifecta = cap['accesses_private_data'] and cap['receives_untrusted_input'] \
        and cap['communicates_externally']
    return trifecta or tool_name in self.config['human_in_the_loop']['tool_approval']['explicit_list']
# on True: emit an approval request to the FE and suspend the tool until the user approves/denies
```

- **Why deferred:** the consume side needs a frontend approval UI + a suspend/resume turn path. The
  capabilities metadata is captured now so the gate has its inputs when built. Mark the dispatch seam.

### S-2 — Telemetry endpoint  (`/api/v1/telemetry`)
A POST endpoint that records per-turn metrics (latency, rounds, tokens, flow, ambiguity level) to a sink for
dashboards. Hugo already tracks `last_prompt_tokens` and the round count internally.

```python
# designed-not-built — telemetry sink
@telemetry_router.post('/api/v1/telemetry')
def record(event:dict):
    _SINK.append({**event, 'conversation_id': ..., 'turn': ...})   # later: Langfuse (Step 1 seam)
```

- **Why deferred:** observability is the Langfuse seam owned by the eval plan (Step 1); a local sink is the
  interim.

### S-3 — Responsive block hints
Block payloads gain optional layout hints (`width`, `priority`, `collapsible`) so the frontend can reflow on
small screens. `BuildingBlock` already has `panel` + `expand`; this adds presentation hints.

- **Why deferred:** purely presentational; no behavior change. Note the field on `BuildingBlock`.

### S-4 — `models.cost` budgeting + `feature_flags.proactive_issue_detection`
A per-session token/cost budget that degrades tiers (or refuses) when exceeded, and a feature flag that turns
on MEM's proactive issue detection (the proactive-push channel, itself deferred in Step 2).

- **Why deferred:** budgeting needs the telemetry sink (S-2); proactive detection needs the real background
  MEM loop. Both are config keys with no consumer yet — note them, don't wire.

---

## Verification
- Offline gate suites green (cwd wrapper); the new config validator must **not** reject the current valid
  config (run `load_config()` in a test).
- Smoke: a bad config (provider typo) fails startup in **prod** mode, warns in **dev**; `/health` reports
  `config_loaded`; a `grid` block passes validation; a long orchestrator turn streams `text` before the
  final blocks.
- `tools.yaml:611` template-registry comment — already handled in former Step 0; confirm gone.
- Grep: `test_res_module.py` / `test_res_tool_llm.py` are deleted; nothing imports them.
