# Step 4 — PEX rendering & prompt conformance

Maps to **Master Plan · Step 4**. Effort **M**. Depends on: mostly independent — can run alongside Steps 2/3.

**Goal:** close the style-guide and prompt-assembly gaps so PEX's skill prompts + voice match the spec.
**Deliverable:** the items below; offline suites green; the trace gate still passes.

Spec: `style_guide.md`; `components/prompt_engineer.md`; `modules/pex.md`.

**Reading the current code.** The pieces this step touches:
- `PromptEngineer.skill_call` (`prompt_engineer.py:181-197`) — hardcodes the `'med'` tier at `:190`
  (`model_id = self._resolve_model('med')`); has no `model=` arg.
- `PromptEngineer.tool_call` (`prompt_engineer.py:199-225`) — already accepts `model:str='med'` (`:202`).
- Per-flow call-cap doubling (`prompt_engineer.py:215-217`): `max_num_calls = 8; if flow.name() in
  ['audit','refine','rework','compose']: max_num_calls *= 2`.
- `build_skill_system` (`for_pex.py:49-62`) — assembles `base_system + intent_prompt + AMBIGUITY_AND_ERRORS
  + skill_prompt`; **no closing reminder appended**.
- `SLOT_7_REMINDER` (`general.py:12`) and `JSON_REMINDER` (`general.py:10`) — both defined, **zero call
  sites**. Both are JSON-flavored ("respond with ONLY valid JSON").
- `_MAX_ROUNDS = 8` (`pex.py:21`, read `:332`), `_MAX_CORRECTIVE = 3` (`pex.py:22`, read `:374`); the
  message constants `_FALLBACK_MESSAGE`/`_NUDGE_MESSAGE`/`_WRAP_UP_MESSAGE` (`pex.py:23-27`).
- Config: `resilience.max_recovery_attempts: 2` (`shared_defaults.yaml`, **unused**) and
  `recovery.max_repair_attempts: 2` (**unused, zero call sites**); `compression` is already config-driven
  and read in `agent.py`.

---

## Decisions

**Locked (this step implements):**
- **Inject the slot-7 closing reminder.** Defined but never used; append it last in the assembled skill
  prompt. (§4.2)
- **Delete `JSON_REMINDER`.** Zero call sites and it contradicts the agentic (prose + tools) contract;
  repurpose `SLOT_7_REMINDER` to the agentic reminder text. (§4.2)
- **Per-call skill tier.** `skill_call` takes `model='med'` as a per-call arg (symmetry with `tool_call`), so
  a policy can request `high` for a hard skill. (§4.6)

**Resolved here — confirm or override:**
- **Prompt taxonomy (supersedes the old "8-slot/JSON" framing).** Skills (orchestrator how-to guides) return
  **nothing**; sub-agents (flows) and tools return **JSON**. The per-flow `prompts/pex/skills/*.md` are
  sub-agent prompts. The style guide's "every prompt is multi-slot + JSON" overreaches — skills are carved out
  (applied to style_guide/checklist/tool_smith 2026-06-21). (§4.1)
- **E10 · loop bounds — DECIDED: one source of truth.** Each bound declared in exactly one place (we use
  config under `resilience`, matching `compression`); collapse the two dead recovery keys into one; message
  strings stay code constants. No duplication. (§4.5)
- **Grounding-first ordering.** rec: spec clarification, not a code change — slot-1 "grounding first" targets
  the cacheable system prompt, not the volatile per-turn message. (§4.4)

**Deferred (stub — designed, not built):**
- Multi-sub-agent artifact curation — latent until a turn runs concurrent flows (the Step 5 concurrency stub).

---

## 4.1 — Get the prompt taxonomy right first (skills vs sub-agents vs tools)
Three prompt kinds, three contracts:
- **Module skills** — the orchestrator how-to guides (`plan`, `explain`, `recap` / `recall` / `retrieve`).
  They describe *how* an orchestrator uses a component and **return nothing**; they are guidance injected into
  the orchestrator's context.
- **Sub-agents** (flows) and **tools** — return **JSON** (a result the orchestrator reads).

The style guide (`style_guide.md:127`; also `checklist/phase_8_prompt_writing.md:7`, `tool_smith.md:241`) says
*every* prompt follows the same multi-slot structure and returns JSON. That holds for sub-agent/tool prompts;
it does **not** hold for skills, which return nothing. The per-flow prompt bodies under
`prompts/pex/skills/*.md` are **sub-agent prompts** (each drives a flow that returns a result), despite the
"skills" directory name — the closing reminder + exemplar work below applies to *them*.

**Reconcile the spec — DONE 2026-06-21.** The carve-out is in `style_guide.md`, `checklist/phase_8`, and
`tool_smith.md`: how-to skills return nothing and are exempt from the JSON rule; the multi-slot structure +
JSON applies to sub-agent/tool prompts. (`tool_smith.md` also dropped `scope`/`dispatch`/`output_schema` per
E7 / Step 6.10.)

## 4.2 — Inject the closing reminder
The closing reminder is defined but never used. `build_skill_system` ends with the prompt body; nothing
re-states the output contract at the end (the highest-recency position).

**Change.** Append the reminder as the **final** element of the assembled per-flow (sub-agent) prompt, after
the body/exemplars — it restates that prompt's output contract. Repurpose `SLOT_7_REMINDER` to that text and
**delete** `JSON_REMINDER` (unused; and per 4.1 the how-to skills it implied don't return JSON at all).

```python
# general.py — repurpose the constant (was a JSON instruction)
SLOT_7_REMINDER = ("Finish the turn by EITHER calling a tool OR replying to the user in plain prose. "
                   "Do not wrap your reply in JSON or restate these instructions.")
# delete JSON_REMINDER (no call sites, contradicts the agentic contract)

# for_pex.py — build_skill_system, append the reminder last
parts = [base_system, '\n\n', intent_prompt, '\n\n', AMBIGUITY_AND_ERRORS]
if skill_prompt:
    parts.append(f'\n\n--- {flow.name().capitalize()} Skill Instructions ---\n\n{skill_prompt}')
parts.append(f'\n\n{SLOT_7_REMINDER}')        # NEW: slot-7 closing reminder
return ''.join(parts)
```

Single-shot NLU prompts keep their JSON demand through `_TASK_SUFFIXES` (`prompt_engineer.py:20-37`) — the
carve-out from 4.1.

## 4.3 — Raise exemplar counts toward 7–10  · 8b
Style guide targets 7–10 exemplars per PEX skill (`style_guide.md:124`). **Current counts** (from the `.md`
files under `prompts/pex/skills/`):

| Count | Skills |
|---|---|
| 1 | **propose** (worst) |
| 2 | chat, cite, compose, promote, release, schedule |
| 3 | audit, brainstorm, browse, find, outline, summarize |
| 4 | compare, rework |
| 5 | refine, write |

**Change.** Author exemplars toward 7–10, **priority order: `propose` (1) → the 2-count group → the
3-count group**. Follow the training/test-set rule — **no Kitty Hawk**, multi-word titles, realistic short
utterances ([[feedback-training-vs-test-separation]]). Each exemplar shows the agentic shape (a tool call or
a prose reply), not a JSON blob. Pair with the trace gate / model_tests since exemplars are a behavior
surface — diff detection/trajectory scores after.

## 4.4 — Grounding-first ordering note  · 8d
The starter emits `<task>` before `<resolved_details>` (`for_pex.py:119-122`); `style_guide.md:128` says
grounding-first. Hugo correctly keeps volatile grounding in the **per-turn user message** (out of the cache
prefix).

**Resolution: spec clarification, not a code change.** Note in `style_guide.md` that slot-1 "grounding first"
targets the **cacheable system prompt**, not the per-turn message — where putting volatile grounding first
would churn the cache key every turn. A cheap reorder within the starter is optional and not required.

## 4.5 — Config-promote loop bounds + call-caps (E10)  · 1 / 7b
`_MAX_ROUNDS` / `_MAX_CORRECTIVE` are module constants (`pex.py:21-22`); the per-flow call-cap doubling is
inline (`prompt_engineer.py:215-217`). Two recovery keys exist that nothing reads —
`resilience.max_recovery_attempts` and `recovery.max_repair_attempts`.

**Embedded decision E10 — DECIDED: one source of truth.** Each bound is declared in exactly **one** place. We
use config under `resilience` (matching the already-config-driven `compression`): move
`_MAX_ROUNDS`/`_MAX_CORRECTIVE` + the call-cap list there, and **collapse the two dead recovery keys into one**
so nothing is declared twice. The nudge/wrap-up message **strings** stay code constants. *Where* isn't the
point — no duplication is.

```yaml
# shared_defaults.yaml — resilience (additions)
resilience:
  max_rounds: 8                 # was pex.py _MAX_ROUNDS
  max_corrective: 3             # was pex.py _MAX_CORRECTIVE
  extended_call_flows: [audit, refine, rework, compose]   # was the inline list in prompt_engineer.py
  extended_call_multiplier: 2
  max_recovery_attempts: 2      # keep ONE recovery key; DELETE the orphan `recovery.max_repair_attempts`
```

```python
# pex.py — read config instead of module constants
self._max_rounds = config['resilience'].get('max_rounds', 8)
self._max_corrective = config['resilience'].get('max_corrective', 3)

# prompt_engineer.py — read the call-cap from config
res = config.get('resilience', {})
max_num_calls = 8 if flow.name() not in res.get('extended_call_flows', []) \
    else 8 * res.get('extended_call_multiplier', 2)
```

(Config validation that catches duplicate/dead keys like the two recovery keys lands in **Step 6.1**.)

## 4.6 — Per-call skill tier  · 7d
`skill_call` hardcodes the `'med'` tier (`prompt_engineer.py:190`) while `tool_call` already accepts `model=`
(`:202`). Make the skill tier a per-call arg (default `'med'`), so a policy can request `'high'` for a hard
skill — symmetry with `tool_call`.

```python
# prompt_engineer.py — skill_call signature + resolution
def skill_call(self, flow, convo_history, scratchpad, skill_name=None, skill_prompt=None,
               resolved=None, max_tokens=1024, user_text=None, model:str='med') -> str:
    ...
    model_id = self._resolve_model(model)     # was self._resolve_model('med')
```

---

## Stubs — designed, not built (full specs)

### Multi-sub-agent artifact curation  (`task_artifact.md:43-54`)
**Now:** `activate_flow` runs **one** policy and inserts **one** artifact (`world.insert_artifact`). One flow,
one artifact per turn.

**Target:** when a turn activates **concurrent** flows (the deferred multi-active concurrency from Step 5),
their artifacts are curated into a single turn artifact — blocks merged, deduped, ordered by flow priority —
before the turn ends ("PEX owns ending the turn").

```python
# pex.py — curation step (designed-not-built; build with the concurrency work)
def _curate_artifacts(self, artifacts:list[TaskArtifact]) -> TaskArtifact:
    """Merge the artifacts of concurrently-active flows into one turn artifact: concatenate blocks
    in flow-priority order, drop duplicates by (block_type, data-key)."""
    merged = TaskArtifact()
    seen = set()
    for art in sorted(artifacts, key=lambda a: a.priority):
        for block in art.blocks:
            key = (block.block_type, _block_identity(block))
            if key not in seen:
                seen.add(key)
                merged.add_block(block.to_dict())
    return merged
```

- **Why deferred:** latent until a turn runs concurrent flows, which needs the multi-active concurrency +
  contiguous-Active invariant (Step 5 deferred). Mark the seam in `activate_flow` `# designed-not-built`.

---

## Verification
- Offline gate suites green (cwd wrapper). `test_artifacts.py` parametrizes over skill `.md` files — keep the
  `tools:` frontmatter lints green when adding exemplars; new exemplars must only reference allow-listed tool
  names.
- Trace gate passes (exemplar changes can shift detection — diff scores before/after).
- Grep: `SLOT_7_REMINDER` now has a live call site (`for_pex.py`); `JSON_REMINDER` is gone; no skill body
  claims a JSON return; `_MAX_ROUNDS`/`_MAX_CORRECTIVE` are read from config, not module constants.
