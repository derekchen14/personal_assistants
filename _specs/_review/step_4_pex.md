# Step 4 — PEX rendering & prompt conformance

Maps to **Master Plan · Step 4**. Effort **M**. Depends on: mostly independent — can run alongside Steps 2/3.

**Goal:** close the style-guide and prompt-assembly gaps so PEX's skill prompts + voice match the spec.
**Deliverable:** the items below; offline suites green; the trace gate still passes.

Spec: `style_guide.md`; `components/prompt_engineer.md`; `modules/pex.md`.

---

## 4.1 — Resolve the agentic-skill format exemption (E9) — decide first
- Style guide (`style_guide.md:113-137`) wants an 8-slot format + a JSON return for "all prompts". Hugo's
  PEX skills are agentic: prose final reply + tool calls (`save_findings`/`execution_error`), not a JSON blob.
- **Embedded decision E9:** rec — **exempt agentic skill bodies** from the 8-slot/JSON rule; keep that rule
  for single-shot classification/extraction prompts (NLU). This unblocks 4.2 and avoids forcing JSON onto
  tool-using skills. Record the carve-out as a one-line note in `style_guide.md`.

## 4.2 — Inject the closing reminder (slot 7)  · 7c
- `SLOT_7_REMINDER` is defined (`general.py:12`) but **never injected** — grep shows zero call sites;
  `JSON_REMINDER` (`general.py:10`) is likewise unused.
- Append the closing reminder as the final element of the assembled skill prompt, after the skill body /
  exemplars (`for_pex.py:49-62` `build_skill_system`). Per 4.1, the reminder must reinforce **each skill's
  actual** output contract (prose + tools), **not** a literal "respond with JSON". Drop or repurpose
  `JSON_REMINDER` accordingly.

## 4.3 — Raise exemplar counts toward 7–10  · 8b
- Style guide targets 7–10 per PEX skill (`style_guide.md:124`). Current counts: refine 7; compare/rework/
  write 6; chat/outline/summarize 5; audit/brainstorm/browse 4; cite/compose/promote/release/schedule 3;
  **propose 2**.
- Author exemplars for the under-target skills (priority: `propose`, then the 3-count cluster). Follow the
  training/test-set rule — no Kitty Hawk; multi-word titles; realistic short utterances. Pair with the trace
  gate / model_tests since exemplars are a behavior surface.

## 4.4 — Grounding-first ordering note  · 8d
- Starters emit `<task>` before `<resolved_details>` (`for_pex.py:119-122`). `style_guide.md:128` says
  grounding-first. Hugo correctly keeps volatile grounding in the **per-turn user message** (out of the
  cache prefix).
- **Resolution:** spec clarification, not a code change — note that slot-1 "grounding first" targets the
  cacheable **system prompt**, not the per-turn message. (If desired, a cheap reorder within the starter is
  optional.)

## 4.5 — Config-promote loop bounds + call-caps (E10)  · 1 / 7b
- `_MAX_ROUNDS=8` / `_MAX_CORRECTIVE=3` are module constants (`pex.py:22-23`); the per-flow call-cap doubling
  for `['audit','refine','rework','compose']` is inline (`prompt_engineer.py:216-218`).
- **Embedded decision E10:** rec — promote both to config (under `resilience`), matching how `compression` is
  already config-driven. Keep the nudge/wrap-up message *strings* as code constants (not user-tunable).
- Reconcile the two overlapping recovery keys that nothing reads today —
  `resilience.max_recovery_attempts` vs `recovery.max_repair_attempts` — into one. (Config validation that
  catches such dupes lands in Step 6.)

## 4.6 — Minor tier param  · 7d
- `skill_call` hardcodes the `'med'` tier (`prompt_engineer.py:191`) while `tool_call` accepts `model=`
  (`:203`). Make the skill tier a per-call arg (default `'med'`). Small.

---

## Deferred here (stubs)
**Multi-sub-agent artifact curation** (`task_artifact.md:43-54`; `pex.py` `activate_flow` runs one policy →
one `world.insert_artifact`). Latent until a turn activates concurrent flows — which needs the deferred
multi-active concurrency. Mark the curation seam `# designed-not-built`; build with the concurrency work.

## Verification
- Offline gate suites green (cwd wrapper). `test_artifacts.py` parametrizes over skill `.md` files — keep the
  `tools:` frontmatter lints green when adding exemplars; new exemplars must only reference allow-listed tool
  names.
- Trace gate passes (exemplar changes can shift detection — diff scores).
- Grep: `SLOT_7_REMINDER` now has a live call site; no skill body claims a JSON return.
