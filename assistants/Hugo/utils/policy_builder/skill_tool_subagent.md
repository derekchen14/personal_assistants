# Part 3 — Implementation Plan: Standardize & Harden the Policy Layer

**Audience:** user review before any Part 3 code changes land.
**Scope:** **all 48 flows** across the seven intents (Draft 7, Revise 8, Publish 7, Research 6, Converse 7, Plan 6, Internal 7). Six exemplars ratify the patterns: `RefineFlow`, `ComposeFlow`, `SimplifyFlow`, `CreateFlow`, `AddFlow`, `BrowseFlow`. Phases 4a–4c apply them to the remaining 42 flows.
**Non-scope:** new component surfaces, new flow attributes, new helpers beyond those already signed off in `fixes/_shared.md`, skill deletions for non-deterministic flows, rewrites of component classes.

---

## 1. Executive summary

Part 3 takes the 7 locked architectural decisions (AD-1, AD-3, AD-6, AD-7, AD-8, AD-9, AD-10 — AD-2/4/5 were conventions moved to `AGENTS.md`) and Themes 1-7 that already landed, and applies them uniformly so that every flow composes the same way. The work is not additive — it is consolidating. We shrink variance across **four pillars**:

1. **Interface** — how a policy talks to its collaborators, and how PEX signals state back to RES/user. Outside the policy layer the contracts are already clear: NLU↔PEX through `DialogueState`, PEX↔RES through `DisplayFrame`. Part 3 fixes the policy-side interface: the policy reaches the skill and tools through `BasePolicy.llm_execute` / `PromptEngineer.tool_call` / direct `tools(name, params)`; it declares ambiguity via `self.ambiguity.declare(level, observation=..., metadata=...)`; it pushes prerequisites via `flow_stack.stackon(...)` or re-routes via `flow_stack.fallback(...)`; it writes findings via `memory.write_scratchpad(flow.name(), {...})`; and it signals errors to RES via `DisplayFrame(flow.name(), metadata={'violation': ...}, thoughts=...)` per AD-6.
2. **Structure** — one method shape per policy (§ 3.1) and one three-layer shape per prompt (§ 3.5). Deviations cite a specific convention.
3. **Policy** — Python code that executes the flow. Deterministic flows (create, find, inspect, explain, undo) call tools inline and have no skill file. Agentic flows route through `llm_execute`. The template covers both shapes.
4. **Prompt** — for agentic flows only: system prompt (persona + flow preamble + skill body + suffix + current state) + starter prompt (recent conversation + latest utterance + task framing) + skill file (frontmatter + Behavior + Important + Slots + Output + Few-shot). Each sub-component has a single job; Theme 8 tightens the assembly.

Three things change in the repo:

- **Policy methods** gain a single, uniform shape: entity-slot guard → optional-slot defaults (AD-8) → `_resolve_source_ids` → dispatch (deterministic inline tool call, or `self.llm_execute`) → success check via `self.engineer.tool_succeeded` → error-frame branch per AD-6 → completion + card.
- **Skill files** align to a uniform section layout (YAML frontmatter → `## Behavior` → `## Important` → `## Slots` → `## Output` → `## Few-shot examples`), with Option C trajectory examples already required by Phase 3's pytest (`test_skill_tool_alignment.py`).
- **Error recovery** stops living in two fighting systems. `_validate_frame` dispatches error frames by inspecting `metadata['violation']` and `tool_log` — the same information the policy already produced. Per `error_recovery_proposal.md § 5.3` (updated to drop the parallel `error_class` taxonomy), Tiers 2 and 3 are revived (not deleted) per DP-8. Retry lives at three layers — skill inner loop, `BasePolicy.retry_tool`, and `pex.recover` Tier 1 — each addressing a different failure class (§ 6 below). App-crash handling (unhandled exceptions) is out of scope for 4RE — handled by try-catch at `Agent.take_turn`.

The six exemplars in § 4 cover the patterns the other 42 flows reduce to:

- **Refine** — entity-first nested guards + single-branch (outline-present vs not) + contract backstop on silent-shrink.
- **Compose** — elective "at least one of" guard + stack-on when prerequisite missing.
- **Simplify** — disjunction via if/elif/else (source vs image) + scope-mismatch fallback to a sibling flow + missing-reference check for image.
- **Create** — deterministic flow, no `llm_execute`; entity slot is an ExactSlot (title) not a SourceSlot; duplicate-detection as `confirmation` ambiguity; forward-chain to `outline`.
- **Add** — three-way "at least one of" elective + multi-tool success contract.
- **Browse** — non-post entity (tags); required CategorySlot drives the success contract.

Once these six lock in, the remaining 9 flows in the 14-step eval (Phase 4a) + 33 non-eval flows (Phases 4b–4c) receive the same treatment.

**Template philosophy — principles, not fill-in-the-blank.** The § 3 standardization rules describe best practices grounded in the 10 ADs, the 12 conventions, and the 8-item violation vocabulary. They are not a rigid template to mechanically apply. Every policy shares the method-shape contract (§ 3.1) and AD-6 error channels (§ 3.2), but deviations are allowed when a flow has a genuinely different shape — they just need an inline comment citing which convention justifies the deviation. The goal is **consolidation** (removing variance that hides bugs), not uniformity for its own sake.

**Themes 1-7 — partial landing, Phase 1/4 completes the sweep.** Themes 1-7 landed across the 12 exemplar flows (`policy_spec.md § Theme execution status`). Across the remaining 36 flows, coverage is partial: most have AD-6 error frames only where Theme 4 forced them (release); AD-1 scratchpad only where Theme 5 consumers exist (polish); standardized `missing_entity` / `missing_slot` metadata only where Theme 7 call-sites were touched. Phase 1 normalizes metadata to the 8-item `violation` vocabulary uniformly; Phases 4a–4c complete the Theme 1-7 sweep (entity-slot guard first, tool_succeeded backstops, optional-slot defaults) across every flow.

**Part 5 relationship — first-draft here, tuning there.** Part 3 writes the first-draft policy + prompt for every flow following the template. **Things work after Part 3 lands** — the 14-step eval passes at the current level (or better), and the 36 non-eval flows at least import, construct, and execute a happy path. Part 5 then makes targeted improvements to specific flows based on Part 4 eval results (failing rubrics) and human feedback (Part 5a HITL app). Part 5 is iterative quality work; Part 3 is the foundation. If the template itself needs revision because a specific flow surfaces a genuine design gap, we come back to Part 3, not the other way around.

Part 3 does **not** introduce new concepts, new helpers beyond what `fixes/_shared.md` proposes under AD-7…AD-10, new `DialogueState` or `DisplayFrame` attributes, new `flow.deterministic` flags, or any `BasePolicy.direct_tool_call` helper. Those are rejected (see `fixes/_shared.md § Proposed but rejected`).

---

## 2. What is already locked

### Architectural decisions (cite `policy_spec.md § Architectural decisions (locked)`)

- **AD-1** — scratchpad `dict[str, dict]` with `{version, turn_number, used_count, ...}` convention. Producers: `inspect_policy`, `find_policy`, `audit_policy` (`backend/modules/policies/revise.py:189-199`). Consumer: `polish_policy` (`revise.py:102-108`).
- **AD-3** — outline recursion is safe; documented as a comment at `draft.py:94-97`; `OutlineFlow` may not `stackon('outline')` itself.
- **AD-6** — three failure channels, all routed through `DisplayFrame(flow.name(), metadata={'violation': <class>}, thoughts=...)` where `<class>` is one of the 8-item violation vocabulary (§ 3.3). User-intent ambiguity uses `self.ambiguity.declare(level, observation=..., metadata=...)`. Distinct, never conflated.
- **AD-7** — YAML frontmatter on every skill (`policy_spec.md § Theme execution status`). Phase 1 landed; loader parses + strips frontmatter.
- **AD-8** — optional slots with a sensible default commit with the default (`audit_policy`'s `reference_count=5` at `revise.py:150-151`).
- **AD-9** — `_validate_frame` checks value correctness per block type; `_llm_quality_check` off by default, per-flow opt-in.
- **AD-10** — prompt caching on system+tool segments; `BaseFlow.max_response_tokens` per-flow override.

Gaps (no AD-2/4/5) are deliberate — those were conventions (terminology, `OUTLINE_LEVELS` reference, polish-stages design note). Moved to `AGENTS.md` so they're visible to coding agents without bloating the code-shaping decision set.

### Themes 1-7 outcomes (cite `policy_spec.md § Theme execution status`)

- **T1** (skill/policy contract) — `create`/`find`/`inspect` skills deleted; `simplify`/`compose`/`rework` skills own persistence; `merge_outline` tool split for refine.
- **T2** (unexemplified slots) — every declared slot has at least one few-shot.
- **T3** (output-shape drift) — `audit` emits structured report; scratchpad writes standardized.
- **T4** (error-path gaps) — AD-6 landed in `release_policy`, `refine_policy`, `outline_policy` propose-mode.
- **T5** (scratchpad convention) — producers/consumers wired end-to-end using `context.turn_id`.
- **T6** (stack-on opacity) — inline `flow_stack.stackon(...) + state.keep_going = True + frame.thoughts=<reason>` (`draft.py:197-200`, `draft.py:226-228`).
- **T7** (repeated guard patterns) — only `PromptEngineer.tool_succeeded` extracted; `guard_slot`/`complete_with_card`/`stack_on` rejected.

### Part 2 Phases 1-4

- **Phase 1** — YAML frontmatter on all skills; loader in `backend/components/prompt_engineer.py::load_skill_template`.
- **Phase 2** — deterministic migration for `explain` + `undo` complete (inline `tools(name, params)` calls; no helper, no flag).
- **Phase 3** — Option C enforced by pytest (`utils/tests/test_skill_tool_alignment.py`).
- **Phase 4** — `handle_ambiguity` / `coordinate_context` descriptions tightened in `PEX._component_tool_definitions` (`pex.py:426-505`).

Test baseline: 121 pass / 37 skip.

---

## 3. Standardization rules — the post-Part-3 house style

Every policy method MUST follow the rules below. Deviations require an inline comment citing the specific convention.

### 3.1 Method-shape contract

**Key idea — slots route the flow.** Most flows have if-then-else branching based on the state of the slots. Slots serve three jobs, in order of importance: (1) **routing** — which branch of the policy does this invocation take; (2) **grounding** — what entity is the flow acting on; (3) **parameters** — what values go into tool calls. The third job is a bonus; the first two are why slots exist. A policy's first act is to interpret which slots are filled and branch accordingly.

**Slot priorities — canonical definitions** (from `utils/flow_recipe.md § 1` and `_specs/components/flow_stack.md § Elective Rule`):

- **`required`** — must be filled before execution.
- **`elective`** — exactly one must be filled; flows with electives must have ≥2 elective options (choice among alternatives). A single elective is invalid — convert it to `required` or `optional`.
- **`optional`** — nice to have but not a blocker.

`flow.is_filled()` returns True when all required slots are filled **and** at least one elective (if any) is filled. That means `if not flow.is_filled(): ...` at the top of a policy already captures both the required-slot rule and the at-least-one-elective rule. No need to re-check each elective separately — inside the guard branch, just identify which specific slot is missing to pick the right ambiguity level and metadata.

**Ambiguity levels by missing slot type** (inside `if not flow.is_filled():`):

- Missing **entity** slot → `partial` ambiguity (the grounding itself is incomplete).
- Missing **other required** slot → `specific` ambiguity with `missing_slot` naming it.
- All electives empty → `specific` ambiguity with `missing_slot` listing the alternatives (e.g., `steps_or_guidance`).

When writing a policy, still ask: *does the skill have enough to produce the right output given what `is_filled()` accepts?* If the answer is no, the flow's slot priorities are wrong — flag for review (promote an elective to required, add a new slot, or assign an AD-8 default). Don't paper over with ad-hoc defaults in the policy.

**Single return at end; early returns only for major errors.** Major errors (`partial` and `general` ambiguity — top-level grounding failures that block the whole turn) use early returns. Every other outcome — `specific` ambiguity, `confirmation`, stack-on, fallback, success, and AD-6 error frames — assigns to a `frame` variable and falls through to a single `return frame` at the end. The main policy body ends up as one nested if/elif/else that decides what `frame` contains.

**No universal slot-guard helper.** Each flow's guard depends on its slot semantics — which slots are required, whether there's a disjunction (e.g. simplify's `source OR image`), whether NLU can sometimes infer a missing slot from context. Hand-write the guard per flow. Do NOT introduce a `BasePolicy._require_source` / `guard_slot` helper — variance in slot contracts makes the abstraction wrong more often than right.

General shape (not a rigid template — most sections expand or contract per flow):

```python
def <flow>_policy(self, flow, state, context, tools):
    # 1. Guard the entity slot — early return only for partial/general ambiguity.
    post_id, sec_id = self._resolve_source_ids(flow, state, tools)
    if not flow.slots[flow.entity_slot].check_if_filled() or not post_id:
        self.ambiguity.declare('partial', metadata={'missing_entity': 'post'})
        return DisplayFrame(flow.name())

    # 2. Branch on slot state. Most flows spend their lines here.
    if <specific ambiguity condition>:
        self.ambiguity.declare('specific', metadata={'missing_slot': '<name>'})
        frame = DisplayFrame(flow.name())
    elif <prerequisite missing>:
        self.flow_stack.stackon('<prereq>')
        state.keep_going = True
        frame = DisplayFrame(flow.name(), thoughts='<reason>')
    else:
        # 3. Dispatch. Deterministic → inline tools(name, params). Agentic → llm_execute.
        text, tool_log = self.llm_execute(flow, state, context, tools)
        saved, _ = self.engineer.tool_succeeded(tool_log, '<tool_name>')
        if not saved:
            thoughts = '<what the skill did wrong>'
            frame = DisplayFrame(flow.name(), metadata={'violation': 'failed_to_save'}, thoughts=thoughts)
        else:
            flow.status = 'Completed'
            frame = DisplayFrame(flow.name(), thoughts=text)
            frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})

    return frame
```

**Default-commit for optional slots (AD-8) is rare.** When a slot has a sensible default (`audit`'s `reference_count=5`), commit it inline at entry with `flow.fill_slot_values({'X': <default>})` and cite AD-8. Not part of the standard template — most flows don't have a defaultable optional slot.

### 3.2 Conventions

Rules that apply to every Hugo policy. Each was distilled from a specific feedback moment.

**1. Don't defend deterministic code.** Service-layer tools like `read_metadata` have known contracts. Access keys directly — `flow_metadata['outline']`, not `flow_metadata.get('outline', '')`. If a key is missing or `_success=False`, that's a bug to surface, not a branch to guard. Same for `_message`: always populated when relevant.

**2. No defaults that hide errors.** `text or ''`, `parsed or {}`, `isinstance(parsed, dict)` — these mask upstream mistakes. Let the code crash on unexpected state so tests catch it. `apply_guardrails` returns a dict; trust that.

**3. Build `frame_meta` and `thoughts` first, then the frame.** Avoid multi-line `DisplayFrame(...)` constructions. Assemble the dict and thoughts on their own lines, then instantiate in a single line. Keep short dicts collapsed — one line is readable and diff-friendly. When metadata has one key with no computed values, inline it directly.

```python
thoughts = 'Outline shrunk from 5 bullets to 3 without an explicit removal directive.'
frame = DisplayFrame(flow.name(), metadata={'violation': 'failed_to_save'}, thoughts=thoughts)
```

`DisplayFrame` accepts `origin` positionally. Empty guard frames shorten to `DisplayFrame(flow.name())`.

**4. `code` holds actual code; `thoughts` holds descriptive text.** `code` is for payloads a human would copy-paste: raw tool response, failing JSON blob, erroring SQL, unparseable LLM output. Descriptive prose belongs in `thoughts`. Many error frames have no `code` at all, and that's fine.

**5. Keep metadata sparse.** Metadata is for classification (violation category, missing-slot name, duplicate-title sentinel, etc.). Flow identity is not in metadata — it lives in `origin` (see convention #12). Specifics go in `thoughts` (natural free-form text), not nested-underscore tokens. Natural text can be rendered to the user or fed to a future summarizer; mangled keys can't.

**6. `ambiguity.declare` uses `observation`, not metadata keys.** `AmbiguityHandler.declare(level, observation=..., metadata=...)` takes `observation` for the human-readable description of what's unclear. Don't stuff `question` / `reason` / `prompt` into metadata.

```python
self.ambiguity.declare('partial',
    observation='Simplify needs either a section or an image to target.',
    metadata={'missing_entity': 'section_or_image'})
```

Corollary: if every slot is filled correctly, the skill should not be raising clarification questions. "Intent unclear despite all slots filled" usually means a slot is missing from the flow design.

**7. Never invent new keys without approval.** Hard rule. Whether in `metadata`, `extra_resolved`, `frame.blocks` data, or anywhere else — **don't introduce a new key name** without explicit approval. Use the keys the downstream consumer (skill template, RES template, tool schema) already knows about. If what you want to pass doesn't fit an existing key, surface that as a design question before adding it.

**8. Standard variable names.**

| Concept | Name |
|---|---|
| result of `tools('read_metadata', ...)` | `flow_metadata` |
| result of `llm_execute` | `text, tool_log` |
| result of `apply_guardrails` | `parsed` |
| result of `tool_succeeded` | `saved, _` (or `saved_any`, `content_saved`, etc. when distinguishing) |

**9. No em-dashes in `frame.thoughts`.** Thoughts are user-facing. Write like a person: commas, periods, or short sentences.

**10. Single return at end; early returns only for major errors.** See § 3.1 — covered by the method-shape contract. Avoid inline `return DisplayFrame(origin=..., metadata=..., code=...)` constructions anywhere. Assemble `frame_meta` and `thoughts` on their own lines first, then build the frame in a single line (see convention #3).

**11. Strip template comments from real code.** Exemplars use comments to explain *why* non-obvious decisions are made. When you port these shapes into real `backend/modules/policies/*.py` code, **drop the step-by-step template comments**. Keep comments only where something is genuinely tricky — a cross-flow invariant, a bug workaround, a subtle contract. A reader of the policy should be able to follow the code from the structure itself.

**12. `origin` is always `flow.name()`.** Every `DisplayFrame` a policy builds sets `origin` to `flow.name()` — guards, stack-on, fallback, error, and success frames alike. The old pattern `origin='error'` is gone; error-ness lives in metadata (`'violation' in frame.metadata`). And `flow` is not a metadata key — it lives in `origin` only. Single-meaning field: "which flow produced this frame."

```python
return DisplayFrame(flow.name())                                                 # guard (empty)
frame = DisplayFrame(flow.name(), thoughts='No sections yet, outlining first.')  # stack-on / fallback
frame = DisplayFrame(flow.name(), metadata={'violation': 'failed_to_save'},      # error
                    thoughts=thoughts)
frame = DisplayFrame(flow.name(), thoughts=text)                                 # success
```

Consumers: RES keys per-flow templates off `frame.origin`; `_validate_frame` detects error frames via `'violation' in metadata`. Frames built outside the policy layer (e.g., an `Agent.take_turn` try-catch for app crashes) are the one exception — those can use a literal like `'system'`.

### 3.3 Violation vocabulary

`metadata['violation']` names what kind of failure occurred. Keep the set small (8 categories). Specifics go in `thoughts` (natural language).

| violation | fires when |
|---|---|
| `failed_to_save` | A persistence tool didn't run or produced no effect |
| `scope_mismatch` | The flow ran at the wrong granularity |
| `missing_reference` | An entity referenced in a slot doesn't exist on the post |
| `parse_failure` | Skill output couldn't be parsed into the expected shape |
| `empty_output` | Skill returned nothing when prose was expected |
| `invalid_input` | A tool rejected the arguments given |
| `conflict` | Two slot values contradict |
| `tool_error` | A deterministic tool returned `_success=False` |

**Why only `violation` (and not `error_class`).** An earlier draft carried a second key `error_class` (from `error_recovery_proposal.md § 5.3`) to route PEX recovery — `transient_tool` → retry, `permanent_tool` → short-circuit, `semantic_violation` → gather-context, etc. The two taxonomies overlap (`parse_failure` and `invalid_input` appear in both lists), and everything PEX needs to route recovery is derivable from `violation` plus the `tool_log` it already has:

- `parse_failure` / `empty_output` / `invalid_input` → Tier 2 gather-context → Tier 1 rephrase
- `failed_to_save` with empty `tool_log` → short-circuit (nothing to retry)
- `failed_to_save` with tool calls but semantic drift → Tier 2 → Tier 1 (context may help re-plan)
- `tool_error` with a retryable `_error` code → retry at the policy layer (opt-in per flow) before a frame even comes back
- `tool_error` with a non-retryable code → short-circuit
- `scope_mismatch` / `missing_reference` / `conflict` → never reach PEX recovery (the policy resolves these via fallback, ambiguity, or confirmation)

`error_class` is dropped. `_validate_frame` inspects `violation` and `tool_log` to decide the recovery tier. This matches the codebase's "inspect what you already have" pattern and keeps metadata sparse. `error_recovery_proposal.md § 5.3` needs an aligned update — flag for follow-up.

### 3.4 Rules by what NOT to do

- **Do NOT** invent a `BasePolicy.direct_tool_call(...)` helper. Inline `tools(name, params)`.
- **Do NOT** invent a `BasePolicy._require_source(...)` / `guard_slot(...)` helper. Slot guards are flow-specific — hand-write per policy. `OutlineFlow` / `CreateFlow` / `RefineFlow` are reference shapes.
- **Do NOT** add `flow.deterministic` or any flow-class flag that encodes deterministic-vs-agentic routing. The policy code is the source of truth.
- **Do NOT** add attributes to `DialogueState` or `DisplayFrame`. Findings go in scratchpad; transient per-turn payload goes in `frame.metadata`.
- **Do NOT** raise ambiguity for tool-call failures or contract violations.
- **Do NOT** delete skill files for non-deterministic flows (Phase 2 is complete).
- **Do NOT** rewrite component files (AmbiguityHandler, DialogueState, ContextCoordinator).
- **Do NOT** invent a parallel `error_class` metadata key. Use `violation` + `tool_log` inspection.
- **Do NOT** use `origin='error'`. `origin` is always `flow.name()` — error-ness is `'violation' in metadata`.

### 3.5 Prompt template — system + starter + skill

Agentic flows only (deterministic flows skip this section; they have no prompt). Three layers, each owned by a different location:

- **System prompt** = persona (`backend/prompts/general.py::build_system`) + per-intent block (`backend/prompts/pex/sys_prompts.py::PROMPTS[intent]`) + skill body (`backend/prompts/pex/skills/<flow>.md`). Assembled by `backend/prompts/for_pex.py::build_skill_system`.
- **User message** = filled per-flow starter (`backend/prompts/pex/starters/<flow>.py::build`) + `<recent_conversation>`. Assembled by `build_skill_messages`. XML-tagged throughout.
- **Skill file** carries `## Process` + `## Error Handling` + `## Tools` + `## Few-shot examples`. No `## Slots`, no `## Background`, no `## Important`, no `## Output` (unless the flow genuinely needs a flow-specific JSON output shape, e.g. `simplify`).

Theme 8 restructured the old single-file flow into the three layers above. The Execution Rules suffix is gone (dropped; its two bullets were redundant with intent/skill content). The per-turn `## Latest utterance` block is gone (the tail of `<recent_conversation>` suffices).

Concrete rendered text for Refine, Compose, and Simplify is in § 4.7.

#### Layer 1 — System prompt (universal + intent-scoped)

**Universal static — copied verbatim across ALL flows.** Lift into shared constants:

- Persona opener — *"You are Hugo, an AI writing assistant that helps users create, revise, and publish blog content."*
- Persona rules — 3 bullets (terse reply / reference visual blocks / never fabricate). The *"ask for missing information"* bullet is OUT — it contradicts AD-6 (the policy declares ambiguity, not the LLM).
- Post-ID / Section-ID schema paragraph — 8-char hex post IDs, slugified section IDs, proper-case natural-language titles.
- `## Handling Ambiguity and Errors` — full block including the 4-row ambiguity-level table and the 8-row violation-code table. Required in every system prompt.
- `--- Skill Instructions ---` divider between intent prompt and skill body.
- Skill's `### General tools` list — `execution_error`, `handle_ambiguity`, `manage_memory`, `read_flow_stack`.

**Intent-scoped static — 7 blocks total.** One per intent (Draft / Revise / Research / Publish / Converse / Plan / Internal). `get_intent_prompt(intent)` returns one of these:

- Intent-woven persona sentence — *"You are currently working on {Intent} tasks, which encompasses {intent description}."* Woven into the persona paragraph; NO separate `##` heading.
- `## Background` — domain schema + depth scheme + mixing rule. Draft and Revise share a 5-level outline scheme. Research / Publish / Converse / Plan / Internal need their own Background framings. Converse probably skips the post/section schema entirely.

#### Layer 2 — User message (per-flow starter)

`backend/prompts/pex/starters/<flow>.py` is a Python module with a `TEMPLATE` string and a `build(flow, resolved, user_text)` function. The starter assembles the task-framing sentence, preloaded content, and resolved details for this turn.

**Fill-in-the-blank template slots** — these are what vary per flow:

- `{post_title}` — always quoted in the opening sentence.
- `{flow_verb} {target}` — "Refine the outline of" / "Compose prose for sections of" / "Simplify the named target in".
- `{tool_sequence}` — one-line happy-path imperative naming the required tool order.
- `{end_condition}` — optional explicit stop ("End once you have saved…").
- `{post_content_block}` — XML-wrapped preloaded data. Shape varies:
  - `<post_content>` for whole-outline work (refine, whole-post compose).
  - `<section_content>` when operating on a single section (simplify, most Revise-intent flows).
  - `<line_content>` when operating on a single snippet or bullet span.
  - Absent when scope varies per turn — skill reads at runtime.
- `{resolved_details_block}` — `<resolved_details>` with semantic-label lines (`Source:`, `Feedback:`, `Guidance:`, `Steps:`, `Image:`, `Channel:`, …) drawn from filled slots.

**Canonical user-message shape:**

```xml
<task>
{flow_verb} {target} of "{post_title}". {tool_sequence}. {optional end_condition}.
</task>

<post_content>  [or <section_content>, <line_content>]
{preloaded content — omit block entirely if nothing to preload}
</post_content>

<resolved_details>
Feedback: …
Guidance: …
</resolved_details>

<recent_conversation>
{compiled convo history — tail is the latest utterance, no separate block}
</recent_conversation>
```

**Slot-serialization helpers** live in `for_pex.py`: `render_source`, `render_freetext`, `render_checklist`, `render_section_preview`. They strip empty fields, drop internal flags (`ver`), and collapse list wrappers. Aim for 3–5 helpers total across the 12 flows, not one per slot.

#### Layer 3 — Skill file (per-flow static behavior)

`backend/prompts/pex/skills/<flow>.md`. Canonical structure:

```
---
name: <flow>
description: …
version: N
tools: [...]
---

[one-line intro — "This skill describes how to X."]

## Process

1. …numbered steps, with lettered sub-steps for nuance…

## Error Handling

[invalid_input branch + handle_ambiguity branch]

## Tools

### Task-specific tools
- `tool_name(params)` — description.

### General tools
- `execution_error(violation, message)`
- `handle_ambiguity(**params)`
- `manage_memory(**params)`
- `read_flow_stack(**params)`

## Few-shot examples

### Example 1: <scenario name>
Resolved Details:
- …

Trajectory:
1. …

Final reply:
…
```

Dropped vs. the old skill shape: `## Slots` (slots aren't the LLM's concern — grounding is done before the skill runs), `## Background` (moved to the intent prompt), `## Important` (hard rules fold into Process steps with a *why*), `## Output` (unless the flow genuinely emits flow-specific JSON), the `# Skill: <name>` top-level header, and the separate `### Branching` sub-section (branch details now inline in Process steps).

#### Tactical / editorial rules

Copy-editing conventions surfaced during hand-written review. Apply consistently or the template diverges:

1. **XML tag names are scope-dependent.** `<section_content>` for single-section work (Simplify, Rework, Polish, most Revise); `<post_content>` for whole-outline work (Refine, whole-post Compose); `<line_content>` for snippet-level work.
2. **Few-shot heading is `Resolved Details:` — capital D.** Never `Starter parameters:` or `Resolved details:` (lowercase).
3. **Tool-description separator is em dash `—`, never hyphen `-`.** Applies to every bullet in `### Task-specific tools` and `### General tools`.
4. **Sub-section headers (`###`) use Title Case consistently within a section.** No mixing `### Intent Sampler` with `### intent sampler`.
5. **Scenario setup must agree with the rendered user message.** `sec`, `target_section`, `user_text` must match XML blocks and recent-conversation text. Mismatch silently breaks the example.
6. **Indent example outlines with 2 spaces under a list item**, never as raw top-level `## Heading` lines mid-example — raw headings risk being parsed as new prompt sections.

#### Per-flow decision-point checklist

Answer these 19 questions before writing any new flow's prompt. Each resolves a fill-in-the-blank slot or a branch in the skill body.

*Task framing (starter opening sentence):*
1. Flow verb + target — what action, on what (outline / section / paragraph / whole post / channel / image / snippet)?
2. `{post_title}` relevance — does the task reference post title, a different entity, or nothing?
3. Tool-sequence imperative — one-line happy-path summary of tool order.
4. Explicit end condition — needed ("End once you have saved…"), or implicit from tool completion?

*Preloaded context (`<post_content>` shape):*
5. What to preload — full outline, per-section previews, just target section, target paragraph/line, or nothing?
6. XML tag name — `<post_content>` / `<section_content>` / `<line_content>`.
7. What runtime reads remain — even with preloading, does the skill still need `read_section` for a nested target?

*Resolved details (`<resolved_details>`):*
8. Which slots become lines — walk the flow's slot dict, drop the entity slot, pick the rest.
9. Semantic label per slot — `Source` / `Feedback` / `Guidance` / `Steps` / `Image` / `Channel` / `Schedule` / `Tone` / `Topic`.
10. Render helper needed? — scalars default-serialize; nested dicts/lists need a helper in `for_pex.py`.

*Error handling:*
11. Likely ambiguity levels — which of the 4 (confirmation / specific / partial / general) apply?
12. Likely violations — which of the 8 codes apply?
13. Flow-specific must/never rules — any hard-stops with a *why* to reinforce in system + skill?

*Tools:*
14. Task-specific tool list — signatures registered and implemented? Any missing?
15. General tools — confirm the standard 4 are available.

*End behavior + examples:*
16. Summarize or stay silent? — refine/compose/simplify stay silent; publish/research will often summarize.
17. How many few-shot scenarios — minimum 2 (normal + edge).
18. Which variations to cover — exercise different tool paths, not just different content.

*Background:*
19. Needs the post/section schema? — Converse probably skips; all others include.

**Caching implication.** The system prompt's universal + intent-scoped blocks are stable across all flows in an intent and heavily cacheable. Per-flow variance is confined to the skill body (stable within a flow) and the per-turn starter (small, uncacheable). Put stable content first in assembly order; never interleave per-turn tokens inside cacheable prefixes.

### 3.6 Interface reference — what talks to what

The policy sits at the center of four interfaces. All of them use existing hooks; Part 3 tightens the call-sites rather than adding new ones.

- **Policy → Skill / Tools** (`backend/modules/policies/base.py::llm_execute` or inline `tools(name, params)`). Deterministic flows call tools directly. Agentic flows package the system + starter + skill per § 3.5 and dispatch through `engineer.tool_call`, getting back `(text, tool_log)`. The success check is `engineer.tool_succeeded(tool_log, name)` — the one shared helper Theme 7 kept.
- **Policy → AmbiguityHandler** (`self.ambiguity.declare(level, observation=..., metadata=...)`). Four levels (general / partial / specific / confirmation). `metadata` keys are standardized: `'missing_entity': <entity_name>`, `'missing_slot': <slot_name>`, `'missing_reference': <ref_kind>`, `'duplicate_title': <title>`. Per convention #6, human-readable text goes in `observation`, not metadata.
- **Policy → FlowStack** (`self.flow_stack.stackon('<name>')` for prerequisites, `self.flow_stack.fallback('<name>')` for re-routes). Inline reason goes in `frame.thoughts` so RES can surface the transition. No helper — Theme 6.
- **Policy → MemoryManager** (`self.memory.write_scratchpad(flow.name(), payload)`). Key is the bare flow name; payload has `version`, `turn_number: context.turn_id`, `used_count`, plus flow-specific fields. AD-1 is the authoritative convention.
- **PEX → RES → user** (via `DisplayFrame`). Error-signaling uses `DisplayFrame(flow.name(), metadata={'violation': <class>}, thoughts=<description>)` per convention #12. RES templates key off `frame.origin` (the flow name) and detect error frames via `'violation' in metadata`.
- **PEX → policy (recovery)** — four-tier ladder dispatched by `_validate_frame` inspecting `metadata['violation']` + `tool_log`. **Tier 1** (rephrase-with-feedback) remains live. **Tiers 2 and 3 are revived** in Phase 2 with tightened triggers (§ 6). **Tier 4** (escalate via `ambiguity.declare('partial', ...)`) remains as the terminal rung. **App-crash handling is outside this ladder** — try-catch at `Agent.take_turn` renders a standard system message (see `error_recovery_proposal.md § 5.9`).

---

## 4. Six exemplar flows — concrete code shapes

The goal is **not** to write exemplar policies. It is to distill the generalized rules of how to write **every** policy in Hugo by working through concrete cases. Each exemplar surfaces a different pattern. The conventions in § 3.2 are where the real content lives; the exemplars below demonstrate the rules on real code.

### 4.1 RefineFlow

**Slots** (`flow_stack/flows.py:157-168`): `source` (SourceSlot, entity, required), `steps` (ChecklistSlot, elective), `feedback` (FreeTextSlot, elective). At least one of `steps` / `feedback` must be filled.

**Pattern surfaced:** entity-first nested guards + single-branch (outline-present vs not) + contract backstop on silent-shrink.

```python
def refine_policy(self, flow, state, context, tools):
    post_id, _ = self._resolve_source_ids(flow, state, tools)
    if not flow.slots['source'].check_if_filled() or not post_id:
        self.ambiguity.declare('partial', metadata={'missing_entity': 'post'})
        return DisplayFrame(flow.name())

    if (not flow.slots['feedback'].check_if_filled()
            and not flow.slots['steps'].check_if_filled()):
        self.ambiguity.declare('specific', metadata={'missing_slot': 'refine_details'})
        frame = DisplayFrame(flow.name())
    else:
        flow_metadata = tools('read_metadata', {'post_id': post_id, 'include_outline': True})
        content = flow_metadata['outline']

        if not self._has_bullets(content):
            self.flow_stack.stackon('outline')
            state.keep_going = True
            frame = DisplayFrame(flow.name(), thoughts='No bullets in the outline yet, generating one first.')
        else:
            text, tool_log = self.llm_execute(flow, state, context, tools,
                extra_resolved={'current_outline': content})
            saved, _ = self.engineer.tool_succeeded(tool_log, 'merge_outline')

            if not text or not saved:
                thoughts = 'The refine skill did not call merge_outline, or produced empty output.'
                frame = DisplayFrame(flow.name(), metadata={'violation': 'failed_to_save'}, thoughts=thoughts)
            else:
                # Silent-shrink backstop: merge_outline should not lose bullets without a removal directive.
                new_metadata = tools('read_metadata', {'post_id': post_id, 'include_outline': True})
                prior_bullets = self._count_bullets(content)
                new_bullets = self._count_bullets(new_metadata['outline'])

                if new_bullets < prior_bullets and not _has_removal_intent(flow):
                    thoughts = f'Outline shrunk from {prior_bullets} bullets to {new_bullets} without an explicit removal directive.'
                    frame = DisplayFrame(flow.name(), metadata={'violation': 'failed_to_save'}, thoughts=thoughts)
                else:
                    flow.status = 'Completed'
                    frame = DisplayFrame(flow.name(), thoughts=text)
                    frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})

    return frame
```

---

### 4.2 ComposeFlow

**Slots** (`flow_stack/flows.py:183-194`): `source` (SourceSlot, entity, required), `steps` (ChecklistSlot, elective), `guidance` (FreeTextSlot, elective). At least one of `steps` / `guidance` must be filled for the policy to have something actionable.

**Pattern surfaced:** elective-slot "at least one of" guard. No branching on which is filled — the skill reads filled slots directly from its resolved context. Policy just verifies the precondition.

```python
def compose_policy(self, flow, state, context, tools):
    post_id, sec_id = self._resolve_source_ids(flow, state, tools)
    if not flow.slots['source'].check_if_filled() or not post_id:
        self.ambiguity.declare('partial', metadata={'missing_entity': 'post'})
        return DisplayFrame(flow.name())

    if (not flow.slots['steps'].check_if_filled()
            and not flow.slots['guidance'].check_if_filled()):
        self.ambiguity.declare('specific',
            observation='Compose needs either a list of sections to write, or guidance on what to compose.',
            metadata={'missing_slot': 'steps_or_guidance'})
        frame = DisplayFrame(flow.name())
    else:
        flow_metadata = tools('read_metadata', {'post_id': post_id})
        if not flow_metadata['section_ids']:
            self.flow_stack.stackon('outline')
            state.keep_going = True
            frame = DisplayFrame(flow.name(), thoughts='No sections yet, outlining first.')
        else:
            text, tool_log = self.llm_execute(flow, state, context, tools, include_preview=True)
            saved_any, _ = self.engineer.tool_succeeded(tool_log, 'revise_content')
            if saved_any:
                flow.status = 'Completed'
                frame = DisplayFrame(flow.name(), thoughts=text)
                frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
            else:
                thoughts = 'The compose skill produced no revise_content calls.'
                frame = DisplayFrame(flow.name(), metadata={'violation': 'failed_to_save'}, thoughts=thoughts)

    return frame
```

**Lessons:**

- The policy does not invent `extra_resolved` keys to carry slot values. The skill's resolved context already exposes filled slots through the standard assembly.
- Only the `partial` guard at the top uses early return. The "both electives empty" case is `specific`, so it builds an empty frame and falls through. Same for the stack-on case and the success/failure branches — all assign to `frame` and reach the single `return frame` at the end.

---

### 4.3 SimplifyFlow

**Slots** (`flow_stack/flows.py:276-287`): `source` (SourceSlot, section-scoped, elective), `image` (ImageSlot, elective), `guidance` (FreeTextSlot, required). Entity is the disjunction `source OR image`.

**Pattern surfaced:** disjunction via `if / elif / else` (no upfront disjunction guard), scope-mismatch fallback to a sibling flow, and missing-reference verification for image.

#### Open question — flag before implementation

Image operation (replace / remove / simplify-in-place) is not captured in slots today. When `image` is filled alone, the skill emits `needs_clarification` — which violates convention #6 (*if every slot is filled, no clarification should be needed*). Proposal: add an `operation` CategorySlot. Pseudocode below assumes the slot exists and omits the `needs_clarification` path.

```python
def simplify_policy(self, flow, state, context, tools):
    if (not flow.slots['source'].check_if_filled()
            and not flow.slots['image'].check_if_filled()):
        self.ambiguity.declare('partial',
            observation='Simplify needs either a section or an image to target.',
            metadata={'missing_entity': 'section_or_image'})
        return DisplayFrame(flow.name())

    if flow.slots['source'].check_if_filled():
        post_id, sec_id = self._resolve_source_ids(flow, state, tools)
        if not sec_id:
            self.flow_stack.fallback('rework')
            state.keep_going = True
            frame = DisplayFrame(flow.name(), thoughts='Simplifying a whole post belongs to rework. Switching flows.')
        else:
            text, tool_log = self.llm_execute(flow, state, context, tools)
            parsed = self.engineer.apply_guardrails(text)
            if 'error' in parsed:
                frame = DisplayFrame(flow.name(), metadata={'violation': 'failed_to_save'}, thoughts=parsed['error'])
            else:
                already_saved, _ = self.engineer.tool_succeeded(tool_log, 'revise_content')
                if not already_saved:
                    self._persist_section(post_id, sec_id, parsed['prose'], tools)
                    already_saved, _ = self.engineer.tool_succeeded(tool_log, 'revise_content')
                if already_saved:
                    flow.status = 'Completed'
                    frame = DisplayFrame(flow.name(), thoughts=parsed['prose'])
                    frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
                else:
                    thoughts = 'The simplify skill produced prose but revise_content did not persist.'
                    frame = DisplayFrame(flow.name(), metadata={'violation': 'failed_to_save'}, thoughts=thoughts)
    else:
        post_id = flow.slots['image'].post_id
        flow_metadata = tools('read_metadata', {'post_id': post_id})
        if flow.slots['image'].ref not in flow_metadata['images']:
            self.ambiguity.declare('specific',
                observation='The referenced image is not on this post.',
                metadata={'missing_reference': 'image'})
            frame = DisplayFrame(flow.name())
        else:
            text, tool_log = self.llm_execute(flow, state, context, tools)
            parsed = self.engineer.apply_guardrails(text)
            if 'error' in parsed:
                frame = DisplayFrame(flow.name(), metadata={'violation': 'failed_to_save'}, thoughts=parsed['error'])
            else:
                flow.status = 'Completed'
                frame = DisplayFrame(flow.name(), thoughts=parsed['prose'])
                frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})

    return frame
```

---

### 4.4 CreateFlow

**Slots** (`flow_stack/flows.py:128-140`): `title` (ExactSlot, **entity**, required), `type` (CategorySlot `['draft', 'note']`, required), `topic` (ExactSlot, optional).

**Patterns surfaced:** entity slot that is **not** a SourceSlot (title is just a string); deterministic flow (no `llm_execute`); duplicate-detection surfaces as `confirmation` ambiguity; successful create chains forward to `outline` when `topic` is provided.

```python
def create_policy(self, flow, state, context, tools):
    if not flow.slots['title'].check_if_filled():
        self.ambiguity.declare('partial', metadata={'missing_entity': 'title'})
        return DisplayFrame(flow.name())

    if not flow.slots['type'].check_if_filled():
        self.ambiguity.declare('specific', metadata={'missing_slot': 'type'})
        frame = DisplayFrame(flow.name())
    else:
        slots = flow.slot_values_dict()
        params = {'title': slots['title'], 'type': slots['type']}
        if 'topic' in slots:
            params['topic'] = slots['topic']

        result = tools('create_post', params)

        if result['_success']:
            new_id = result['post_id']
            state.active_post = new_id
            flow.status = 'Completed'
            block_data = {'post_id': new_id, 'title': result['title'], 'status': result['status']}
            frame = DisplayFrame(flow.name())
            frame.add_block({'type': 'card', 'data': block_data})

            # Chain forward: if the user gave a topic, outline next with grounding pre-filled.
            if 'topic' in slots:
                frame.thoughts = 'Created the post, moving on to outline.'
                self.flow_stack.stackon('outline')
                state.keep_going = True
                outline_flow = self.flow_stack.get_flow()
                outline_flow.slots['source'].add_one(post=new_id)
                outline_flow.slots['topic'].add_one(slots['topic'])

        elif result['_error'] == 'duplicate':
            self.ambiguity.declare('confirmation',
                observation=f'A post titled "{slots["title"]}" already exists. Overwrite it, or pick a different title?',
                metadata={'duplicate_title': slots['title']})
            frame = DisplayFrame(flow.name())

        else:
            thoughts = f'Could not create the {slots["type"]}: {result["_message"]}'
            frame = DisplayFrame(flow.name(), metadata={'violation': 'tool_error'}, thoughts=thoughts)

    return frame
```

**Lessons:**

- Entity slot is `title` — an ExactSlot, not a SourceSlot. No `_resolve_source_ids` needed. Missing entity still maps to `partial` per convention #6.
- Deterministic flow: direct `tools('create_post', ...)` call, no skill dispatch. `flow.is_filled()` guards the required set (title + type), not the optional `topic`.
- Duplicate detection is `confirmation` (candidate awaiting sign-off), not `specific`. `observation` carries the human-readable question; metadata carries the classification (`duplicate_title`).
- Forward chain uses `flow_stack.stackon('outline')` plus `state.keep_going = True` plus direct slot-filling on the newly pushed flow. The `thoughts` string tells RES to surface the transition.

---

### 4.5 AddFlow

**Slots** (`flow_stack/flows.py:196-210`): `source` (SourceSlot, entity, required), `points` (ChecklistSlot, elective), `additions` (DictionarySlot, elective), `image` (ImageSlot, elective), `position` (PositionSlot, optional). At least one of `points` / `additions` / `image` must be filled for the flow to have content to insert.

**Patterns surfaced:** three-way "at least one" elective guard (broader than compose's two-way); multi-tool success contract (insert_content OR insert_media OR revise_content).

```python
def add_policy(self, flow, state, context, tools):
    post_id, sec_id = self._resolve_source_ids(flow, state, tools)
    if not flow.slots['source'].check_if_filled() or not post_id:
        self.ambiguity.declare('partial', metadata={'missing_entity': 'post'})
        return DisplayFrame(flow.name())

    any_content = (flow.slots['points'].check_if_filled()
                   or flow.slots['additions'].check_if_filled()
                   or flow.slots['image'].check_if_filled())
    if not any_content:
        self.ambiguity.declare('specific',
            observation='Add needs something to insert: bullet points, a section addition, or an image.',
            metadata={'missing_slot': 'points_additions_or_image'})
        frame = DisplayFrame(flow.name())
    else:
        text, tool_log = self.llm_execute(flow, state, context, tools)

        content_saved, _ = self.engineer.tool_succeeded(tool_log, 'insert_content')
        media_saved, _ = self.engineer.tool_succeeded(tool_log, 'insert_media')
        revise_saved, _ = self.engineer.tool_succeeded(tool_log, 'revise_content')

        if content_saved or media_saved or revise_saved:
            flow.status = 'Completed'
            frame = DisplayFrame(flow.name(), thoughts=text)
            frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        else:
            thoughts = 'The add skill produced no insert_content, insert_media, or revise_content calls.'
            frame = DisplayFrame(flow.name(), metadata={'violation': 'failed_to_save'}, thoughts=thoughts)

    return frame
```

**Lessons:**

- "At least one of three" is a straightforward extension of "at least one of two" — same `or`-chain pattern, same `specific` ambiguity when the precondition fails. The `missing_slot` value lists the options with underscores only because it's a classification token; the user-facing text goes in `observation`.
- Multi-tool contract: three separate `tool_succeeded` checks, joined with `or` in the success branch. No ceremony; each tool check is one line.
- `position` (optional slot) isn't guarded — it truly is optional, defaulting to whatever the skill decides. If a sensible default existed (e.g., "end of section"), AD-8 default-commit would apply, but today the policy doesn't set one.

---

### 4.6 BrowseFlow

**Slots** (`flow_stack/flows.py:19-31`): `tags` (FreeTextSlot, **entity**, required), `target` (CategorySlot `['tag', 'note', 'both']`, required).

**Patterns surfaced:** entity slot that is a FreeTextSlot (tags — no post_id unpacking); required CategorySlot whose value determines the success contract.

```python
def browse_policy(self, flow, state, context, tools):
    if not flow.slots['tags'].check_if_filled():
        self.ambiguity.declare('partial', metadata={'missing_entity': 'tags'})
        return DisplayFrame(flow.name())

    if not flow.slots['target'].check_if_filled():
        self.ambiguity.declare('specific', metadata={'missing_slot': 'target'})
        frame = DisplayFrame(flow.name())
    else:
        text, tool_log = self.llm_execute(flow, state, context, tools)

        # Contract varies by target: tag uses find_posts, note uses search_notes, both uses either.
        target = flow.slots['target'].value
        if target == 'tag':
            saved, _ = self.engineer.tool_succeeded(tool_log, 'find_posts')
        elif target == 'note':
            saved, _ = self.engineer.tool_succeeded(tool_log, 'search_notes')
        else:
            posts_saved, _ = self.engineer.tool_succeeded(tool_log, 'find_posts')
            notes_saved, _ = self.engineer.tool_succeeded(tool_log, 'search_notes')
            saved = posts_saved or notes_saved

        if saved:
            flow.status = 'Completed'
            frame = DisplayFrame(flow.name(), thoughts=text)
        else:
            thoughts = f'The browse skill produced no results for target "{target}".'
            frame = DisplayFrame(flow.name(), metadata={'violation': 'empty_output'}, thoughts=thoughts)

    return frame
```

**Lessons:**

- Not every entity slot maps to a post. Browse's entity is a FreeTextSlot of tags — no `_resolve_source_ids`, no `post_id`. The policy skips the ID-unpack step entirely.
- A required CategorySlot can drive a policy-side branch **after** dispatch. Here, the success contract depends on `target`'s value: tag-scope verifies `find_posts`, note-scope verifies `search_notes`, `both` accepts either. This branch is about *verifying* the skill did the right thing given the target; the skill itself also reads `target` from its resolved context and picks which tool to call.
- The success frame has no `card` block because browse doesn't act on a single post — its output is a search result the skill narrates in `text`. Different flows emit different block types (or none); not every success needs a card.
- Violation class here is `empty_output` rather than `failed_to_save`. The flow doesn't persist anything; its contract is "produce search results." Pick the violation label that actually matches what went wrong.

---

### 4.7 Rendered prompts — three exemplar flows

Concrete text for `refine`, `compose`, `simplify` — the three agentic flows where the 3-layer architecture was hand-tuned. Use these as reference templates when writing the other 25 agentic flows.

#### 4.7.1 Shared system-prompt prefix (universal + Draft / Revise intent)

Every Hugo sub-agent sees the same persona opener, the same post-id/section-id schema, the same ambiguity + violation tables, and an intent-specific Background. Only the intent block (and the skill body at the end) change per flow.

**Persona + rules** (universal):

```
You are Hugo, an AI writing assistant that helps users create, revise, and publish blog content. You are currently working on {Intent} tasks, which encompasses {intent description}. Your tone is {tone} and your response style is {response_style}:
- Keep responses to 1–2 sentences. Only elaborate when the user asks for detail
- Reference visual blocks when present ("as shown on the right")
- Never fabricate post content — use find_posts/read_metadata to verify
```

**Draft intent description** — *"generating outlines, refining them, and composing prose from those outlines in order to create a draft of new blog posts."*

**Revise intent description** — *"polishing existing content by crafting new sentences, reworking the structure, auditing for style, or simplifying wording in order to develop an improved revision of the blog post."*

**`## Background` — Draft / Revise share the 5-level outline scheme:**

```
A post outline contains a title, a status (draft / note / published), and an ordered list of sections. Each section has a subtitle and content — either outline bullets or prose paragraphs.

Outlines follow markdown down to depth of four levels:
- Level 0: `# Post Title`  (not editable)
- Level 1: `## Section Subtitle`
- Level 2: `### Sub-section`
- Level 3: `- bullet point`
- Level 4: `  * sub-bullet`

Most outlines have Level 1 + Level 3. Add Level 2 only when the section needs explicit sub-structure; use Level 4 only when a bullet genuinely needs supporting detail underneath.

Outline sections follow the depth scheme above. Prose sections replace levels 2-4 with standard paragraphs separated by blank lines. Both are markdown — the only difference is bullet-structured content vs. paragraph-structured content! Never mix prose and bullets inside the same section unless the skill explicitly asks you to.

Post IDs take the form of 8-character lowercase hex strings. They are the first 8 characters of a UUID4. Section IDs take the form of slugs. We convert a section name to a slug by lowercasing, stripping punctuation, collapsing spaces/underscores to dashes, and truncating to 80 chars. In contrast, both post names and section names are proper case natural language text.
```

**Revise variant** adds a closing line: *"Since you are dealing with revising posts, you will be dealing exclusively with prose rather than outlines."*

**`## Handling Ambiguity and Errors`** — identical in every flow:

```
If you encounter issues during execution, there are a few ways to manage them. You can retry calling a tool if there is a transient network issue. If you face uncertainty in the user's request because there are multiple possible interpretations, you should ask for clarification instead of making assumptions.

| ambiguity level | description |
|---|---|
| confirmation | Confusion among a small set of options; often just a decision on whether or not to proceed with a potentially risky action |
| specific | A specific piece of information or user preference is missing |
| partial | Unclear which post, note, or section is being discussed; indicates a lack of grounding |
| general | the user's request is gibberish; highly unlikely to encounter at this point in the process |

In contrast to semantic mis-understanding, there may also be systemic errors caused by syntactical or technical issues. Such errors are categorized into 8 possible violations:

| violation code | description |
|---|---|
| `failed_to_save` | A persistence tool didn't run or produced no effect |
| `scope_mismatch` | The flow ran at the wrong granularity |
| `missing_reference` | An entity referenced in a slot doesn't exist on the post |
| `parse_failure` | Skill output couldn't be parsed into the expected shape |
| `empty_output` | Skill returned nothing when prose was expected |
| `invalid_input` | A tool would reject or has rejected the arguments given |
| `conflict` | Two slot values contradict |
| `tool_error` | A deterministic tool returned `_success=False` |

Use the `handle_ambiguity()` or `execution_error()` tools to signal such issues only after considering all other paths to resolution.
```

Then the divider — `--- {Flow_name} Skill Instructions ---` — followed by the skill body.

#### 4.7.2 RefineFlow — skill body + user message

**Skill body** (`backend/prompts/pex/skills/refine.md` post-frontmatter):

```
This skill describes how to refine outlines. The current outline is provided in the user utterance between the `<post_content>` block. Use it directly as your starting point rather than creating a new one from scratch.

## Process

1. Read the user's guidance from the `<resolved_details>` block to decide what to do. Refer to the `<recent_conversation>` block for the original context.
   a. Only focus on the user's last utterance in the conversation history. Prior turns are context only.
   b. Requests from previous turns have already been addressed, so NEVER act on them.
2. Identify which sections or bullets the user wants changed within the `<post_content>`.
   a. Scope your changes to the specific sections or sub-sections named.
   b. Do NOT try to do more than the user asked.
3. Adjust headings, bullet points, and section order per the user's request. Follow the outline depth scheme from the Draft intent. Insert sub-sections or sub-bullets when appropriate, but do not add unwarranted complexity.
   a. Consider the subject matter of the post when deciding how much depth to add.
   b. If the user asks for new bullet wording but gave only a topic, call `write_text` to brainstorm candidate bullets before saving.
4. Save your changes:
   a. **Targeted edit (default):** call `generate_section(post_id, sec_id, content)` once per changed section. If the section id is new, the content is appended at the tail. If the section id exists, the content replaces that section. To rename, pass the old `sec_id` — the tool re-slugs from the new `## Heading`.
   b. **Full-outline replace (removals only):** call `generate_outline(post_id, content)` once with the complete revised outline. Use this ONLY when removing sections — `generate_section` cannot delete.
5. When done, simply close the loop. No summary needed.

## Error Handling

If the `<post_content>` looks malformed (missing `##` headings, bullets outside a section), do your best to fix visible structure while honoring the request. If truly unworkable, call `execution_error(violation='invalid_input', message=<short explanation>)` and do NOT save.

If the user's request does not make sense given the actual outline content, call `handle_ambiguity(level=<partial|specific|confirmation>, ...)` with the supporting detail so Hugo can resolve it on the next turn.

## Tools

### Task-specific tools

- `generate_section(post_id, sec_id, content)` — save a revised section. Append when `sec_id` is new; replace when it matches. Pass the old slug for rename; the tool rederives the slug from the incoming `## Heading`.
- `generate_outline(post_id, content)` — replace the ENTIRE outline. Only call this when removing one or more sections; `generate_section` cannot delete. Exactly one call per turn.
- `read_section(post_id, sec_id)` — read the prose of a specific section. Rare in refine; only when the preloaded outline truncated the content you need.
- `write_text(prompt)` — brainstorm candidate bullets or descriptions via an LLM. Use sparingly.

### General tools

- `execution_error(violation, message)`
- `handle_ambiguity(**params)`
- `manage_memory(**params)`
- `read_flow_stack(**params)`

## Few-shot examples

### Example 1: Appending bullets

Resolved Details:
- Feedback: "Add under Process: design scenarios, assign labels, generate conversations."

Trajectory:
1. `generate_section(post_id=abcd0123, sec_id=process, content="## Process\n  - design scenarios\n  - assign labels\n  - generate conversations\n  - evaluate")` → `_success=True`. End turn.

### Example 2: Reordering and renaming sections

Resolved Details:
- Feedback: "Rename Ideas to Breakthrough Ideas and tighten its bullets."

Trajectory:
1. `generate_section(post_id=abcd0123, sec_id=ideas, content="## Breakthrough Ideas\n  - bullet A tightened\n  - bullet B tightened")` → `_success=True, renamed=True`. End turn.

### Example 3: Removing a section

Resolved Details:
- Feedback: "Drop the Takeaways section."

Trajectory:
1. `generate_outline(post_id=abcd0123, content=<full outline with Takeaways omitted>)` → `_success=True`. End turn.
```

**User message** rendered by `pex/starters/refine.py::build`:

```
<task>
Refine the outline of "{post_title}". Apply the changes from the user's final utterance to the outline below. Call `generate_section` for each targeted edit, or `generate_outline` when removing sections. End once you have successfully saved all your refinements.
</task>

<post_content>
{current_outline — preloaded by policy via extra_resolved}
</post_content>

<resolved_details>
Feedback: {render_freetext(flow.slots['feedback'])}
Specific changes: {render_checklist(flow.slots['steps'])}
</resolved_details>

<recent_conversation>
{compiled convo history}
</recent_conversation>
```

#### 4.7.3 ComposeFlow — skill body + user message

**Skill body** (same shape as refine; flow-specific variations):

```
This skill describes how to convert an outline into prose. The current outline is provided in the user utterance between the `<post_content>` block. Use it directly as your starting point for composition.

## Process

1. Read the user's guidance from the `<resolved_details>` block; refer to `<recent_conversation>` for original context. Only act on the latest utterance.
2. Gain a deep understanding of the semantics AND themes of the post by reading `<post_content>`.
   a. Note load-bearing text that should transfer verbatim, as opposed to bullet points which convey rough ideas.
   b. Level-4 content is likely verbatim-quality detail — preserve word-for-word.
   c. Consider the right tone / writing style for this content.
3. Convert into complete paragraphs using `convert_to_prose(content)`.
   a. Proceed one section at a time across the whole post by default.
   b. Stop at one section only if the user explicitly requested it.
   c. No bullets should remain in a converted section.
   d. Polish the output — `convert_to_prose` is blunt; flow and hooks need tuning.
   e. Do NOT invent new terminology. Jargon comes from the outline or user.
4. Save with `generate_section(post_id, sec_id, content)` per section. End the turn.

## Error Handling

Malformed `<post_content>` → best-effort fix + `execution_error('invalid_input', …)` if unworkable.

User request doesn't make sense → `handle_ambiguity(…)`.

If `convert_to_prose` fails, retry ONCE. If it fails again, skip that section and continue — do NOT abort the whole flow. After all other sections save, note the failure with `execution_error('tool_error', …)`.

## Tools

### Task-specific tools

- `convert_to_prose(content)` — removes bullets and indentation from outline text. Rough output; polish before saving.
- `generate_section(post_id, sec_id, content)` — save polished prose. You MUST run this for changes to persist.
- `read_section(post_id, sec_id)` — rare; only if `<post_content>` was truncated.

### General tools — same as refine.

## Few-shot examples

### Example 1: Standard whole-post compose
[see backend/prompts/pex/skills/compose.md for full trajectory]

### Example 2: Composing a single named section
[user restricts scope to Motivation; skip others]

### Example 3: Composing at depth 4 (verbatim sub-bullets)
[preserve `*` sub-bullet content word-for-word in the prose output]
```

**User message**:

```
<task>
Compose prose for sections of "{post_title}". For each in-scope section, call `read_section`, `convert_to_prose`, then `revise_content`. Decide scope from the parameters and the user's latest utterance.
</task>

<post_content>
{section_previews — per-section title + preview, preloaded via include_preview=True}
</post_content>

<resolved_details>
Source: {render_source(flow.slots['source'])}
Steps: {render_checklist(flow.slots['steps'])}
Guidance: {render_freetext(flow.slots['guidance'])}
</resolved_details>

<recent_conversation>
{compiled convo history}
</recent_conversation>
```

#### 4.7.4 SimplifyFlow — skill body + user message

Uses the **Revise intent** block (scope discipline + "you deal exclusively with prose" variant of Background).

**Skill body:**

```
This skill describes how to simplify a paragraph, sentence, or phrase within a post. The current section is provided in the user utterance between the `<section_content>` block. Use it directly as your starting point for simplification.

## Process

1. If the starter includes a `<section_content>` block, use it directly (preloaded by policy). Otherwise (image path, or load failure) call `read_section` first.
2. Read user guidance from `<resolved_details>`; refer to `<recent_conversation>`. Only act on the latest utterance.
3. Identify the exact target span — a paragraph, a section, or an image.
   a. Narrow scope: paragraph named → edit only that paragraph. Section named (no paragraph) → edit the whole section. Otherwise prefer the narrowest interpretation that works.
   b. The user may highlight a target via the UI — `<section_content>` may be a span, not the full section. Call `read_section` to see the whole section if needed.
4. Shorten sentences, reduce paragraph length, remove redundancy. **Preserve meaning.**
   a. Do NOT expand scope, invent terminology, or rewrite paragraphs the user didn't touch.
   b. If the user asks to REMOVE an element ("remove that image"), treat as removal, not simplification.
5. Save your changes:
   a. In-place span edit → `replace_text(post_id, sec_id, content)` with just the new text for the span.
   b. Larger rewrite → `generate_section(post_id, sec_id, content)` with the FULL section (paragraphs you didn't touch must be included verbatim; call `read_section` first to confirm you have the whole section).
   c. Image removal → `remove_content(post_id, sec_id, target)`.
   d. End the turn.

## Error Handling

Malformed `<section_content>` → best-effort simplify + `execution_error('invalid_input', …)` if unworkable.

Save tool fails → retry ONCE; then `execution_error('tool_error', …)`.

User names a non-existent target (e.g., "second paragraph" in a one-paragraph section) → `handle_ambiguity(level='specific' or 'partial', …)`.

User wants edits across sections → this is the Rework flow, not Simplify. Declare `handle_ambiguity(level='partial', metadata={'wrong_flow': 'rework'})`.

## Tools

### Task-specific tools

- `replace_text(post_id, sec_id, content)` — most common. Replaces just the provided span.
- `generate_section(post_id, sec_id, content)` — replace the entire section. Requires full section content (verbatim for paragraphs you didn't touch).
- `read_section(post_id, sec_id)` — fallback when no `<section_content>` block was preloaded, or when the span is a partial view.
- `remove_content(post_id, sec_id, target)` — remove an image or explicit span.

### General tools — same as refine.

## Few-shot examples

### Example 1: Simplifying a specific paragraph
[target: paragraph 2 of Evaluation; keep paragraphs 1 and 3 untouched]

### Example 2: Simplifying a whole section
[target: Architecture; apply conversational-tone guidance; preserve core claims]

### Example 3: Image, operation unclear
[image slot filled but no verb; call `handle_ambiguity('confirmation', …)` with replace/remove options; no save tool]
```

**User message** (simplify has two template variants depending on whether policy preloaded the target section):

```
<task>
Simplify the named target in "{post_title}" — shorten sentences, reduce paragraph length, remove redundancy. Rewrite the content below, then call `revise_content` to save.
</task>

<section_content>
{target section content — preloaded by policy when source+sec_id are known}
</section_content>

<resolved_details>
Source: {render_source(flow.slots['source'])}
Image: {render_image(flow.slots['image'])}
Guidance: {render_freetext(flow.slots['guidance'])}
</resolved_details>

<recent_conversation>
{compiled convo history}
</recent_conversation>
```

When `<section_content>` is absent (image path, or preload failed), the task line changes to *"Always `read_section` before editing. Always call `revise_content` to save."*

---

### 4.8 Generalized lessons from the six exemplars

The six exemplars above surface composable building blocks. When writing any non-exemplar policy, do **not** force the flow to the closest exemplar's template. Instead, pick the subset of lessons below that fit the flow's actual slot shape, tool list, and contract. Every policy method reads like it was written by the same author, from the same menu.

#### Lesson 1 — Method-shape contract (convention #11)

```python
def <flow>_policy(self, flow, state, context, tools):
    # --- guards ---
    # partial / general ambiguity → early return (exception to single-return rule)
    # specific / confirmation → assign empty frame, fall through

    # --- resolve / preload ---
    # post_id, sec_id, preloaded content via extra_resolved

    # --- dispatch ---
    # agentic: text, tool_log = self.llm_execute(...)
    # deterministic: result = tools('<name>', params)

    # --- verify / classify ---
    # saved, _ = self.engineer.tool_succeeded(tool_log, '<name>')
    # branch: success / error / fallback / stack-on

    # --- build frame ---
    frame = DisplayFrame(flow.name(), ...) or self.error_frame(...)
    # add blocks, set flow.status

    return frame  # one exit
```

Early returns are allowed ONLY for `partial` / `general` ambiguity (entity-missing, gibberish). Everything else — `specific`, `confirmation`, stack-on, fallback, success, error — assigns to `frame` and flows to the final `return frame`.

#### Lesson 2 — Guard composition (pick what applies)

- **Entity guard** — `partial` ambiguity + early return when the entity slot can't be resolved. Every agentic flow.
- **Slot precondition guard** — `specific` ambiguity for missing required / elective slots. Assigns empty frame, falls through.
- **Disjunction entity** — if/elif/else when the flow has two entity axes (source vs. image, tag vs. note). From Simplify / Browse.
- **Elective "at-least-one-of"** — `specific` when all N electives are empty (two-way from Compose, three-way from Add, generalizable to N).
- **Confirmation** — `confirmation` with `observation=...` + metadata for candidate-awaiting-signoff cases (duplicate title, overwrite). From Create.
- **Prerequisite stack-on** — if a precondition needs a sibling flow, `stackon('<name>') + state.keep_going = True + frame.thoughts = <reason>`. From Compose / Refine.
- **Forward stack-on** — after a successful deterministic operation, chain the next flow with slot pre-population. From Create.
- **Scope-mismatch fallback** — `flow_stack.fallback('<sibling>')` when the request is at the wrong granularity. From Simplify.

#### Lesson 3 — Dispatch (one path, pick the variant)

- **Agentic** — `text, tool_log = self.llm_execute(flow, state, context, tools, extra_resolved=..., include_preview=..., exclude_tools=...)`. Use for any flow with 2+ tools or LLM-reasoned args.
- **Deterministic** — direct `tools('<name>', params)` inline; no skill file, no `llm_execute`. Use for create / find / inspect / explain / undo patterns.
- **Preload** — pass content into `extra_resolved` (`current_outline`, `section_content`, `section_preview`, `items`) to avoid redundant skill-side tool calls.
- **Exclude tools when semantically required** — `exclude_tools=('generate_section', 'generate_outline')` for outline propose-mode. Hard constraint beyond prompt text.

#### Lesson 4 — Verification / success contract

- **Single-tool contract** — `saved, _ = self.engineer.tool_succeeded(tool_log, '<name>')`. One assertion.
- **Multi-tool "any succeeded" contract** — multiple `tool_succeeded` calls OR'd together. From Add / Browse.
- **Multi-tool "all required" contract** — AND'd checks when every tool must have fired. Rare.
- **Slot-driven contract** — branch the `tool_succeeded` call on a CategorySlot value (target=tag → `find_posts`; target=note → `search_notes`). From Browse.
- **Contract backstop** — post-dispatch invariant check (bullet count, section count, content hash). If violated, emit `failed_to_save` even when the tool reported success. From Refine's silent-shrink check.
- **Fallback persistence** — if the skill produced prose but didn't call the save tool, policy calls `_persist_section` as a backup. From Simplify.

#### Lesson 5 — Error-frame construction (universal)

- Use `self.error_frame(flow, violation, thoughts, code, **extra_metadata)`.
- `origin=flow.name()` always (convention #12). Never `'error'`; never bare strings.
- `metadata['violation']` in the 8-item vocab: `failed_to_save`, `scope_mismatch`, `missing_reference`, `parse_failure`, `empty_output`, `invalid_input`, `conflict`, `tool_error`.
- Keep `metadata` sparse (convention #6). Prose goes in `thoughts`; raw payloads go in `code`.

#### Lesson 6 — Success-frame construction

- `frame = DisplayFrame(flow.name(), thoughts=text)` — minimal shape.
- Add a block only when there's UI data to render: `card` for post edits, `list` / `selection` for search results, `toast` for publishes, `compare` for diffs.
- Set `flow.status = 'Completed'` before returning.

#### Lesson 7 — Scratchpad writes (AD-1)

- Producers write `self.memory.write_scratchpad(flow.name(), {'version': '1', 'turn_number': context.turn_id, 'used_count': 0, <payload>})`.
- Consumers increment `used_count` on entries they actually referenced.
- Key on `flow.name()`; no ad-hoc keys.

#### Lesson 8 — `BasePolicy` helpers

`llm_execute`, `_resolve_source_ids`, `_build_resolved_context`, `_read_post_content`, `resolve_post_id`, `_persist_section`, `_persist_outline`, `error_frame`, `retry_tool`, `engineer.tool_succeeded`.

#### Lesson 9 — Universal conventions (all 12)

1. Don't defend deterministic code (direct dict access, not `.get()` with defaults).
2. No defaults that hide errors (`text or ''`, `parsed or {}` are banned).
3. Slot priorities are definitional — trust `flow.is_filled()`.
4. Build `thoughts` / `metadata` first, then one-line `DisplayFrame(...)`.
5. `code` holds payloads; `thoughts` holds prose.
6. Metadata is classification-only; no detailed explanations.
7. `ambiguity.declare` uses `observation=` for human text; metadata is classification.
8. Never invent new keys without approval.
9. Standard variable names (`flow_metadata`, `text, tool_log`, `parsed`, `saved`).
10. No em-dashes in `frame.thoughts` (user-facing).
11. Single return at end; early returns only for `partial` / `general`.
12. `origin` is always `flow.name()`.

#### Lesson 10 — Violation vocabulary (8 items)

| violation | fires when |
|---|---|
| `failed_to_save` | A persistence tool didn't run or produced no effect |
| `scope_mismatch` | The flow ran at the wrong granularity |
| `missing_reference` | An entity referenced in a slot doesn't exist on the post |
| `parse_failure` | Skill output couldn't be parsed into the expected shape |
| `empty_output` | Skill returned nothing when prose was expected |
| `invalid_input` | A tool rejected or would reject the arguments given |
| `conflict` | Two slot values contradict |
| `tool_error` | A deterministic tool returned `_success=False` |

---

## 5. Generalization to the remaining 42 flows

When writing any non-exemplar policy, do **not** force the flow to the closest exemplar's template. Instead, consult `§ 4.8 Generalized lessons from the six exemplars` and pick the subset of lessons that fit the flow's slot shape, tool list, and contract. The per-intent tables below are a rough starting point; the lesson menu is the source of truth.

### 5.1 Phase 4a — remaining 9 flows in the 14-step eval intents

These share the exemplar patterns from § 4. Each row: flow → dominant pattern → flow-specific caveat.

| Flow | Intent | Dominant pattern | Caveat |
|---|---|---|---|
| `outline` | Draft | Refine pattern; keep `propose`/`direct` stages — genuine behavioral divergence (proposals need grounding; direct has stated depth); add `read_metadata` failure guard with `violation='tool_error'` | Recursion safety is AD-3 comment only. No rewrite. |
| `rework` | Revise | Compose pattern: add `revise_content` backstop (`_mark_suggestions_done` already reads the log); `violation='failed_to_save'` on skip | Whole-post scope iterates sections; the backstop checks at least one section's `revise_content` succeeded per-iteration. |
| `polish` | Revise | Simplify pattern: unchanged for the scratchpad consumption (AD-1/T5 landed); normalize error metadata to `violation` | `fallback('rework')` on structural issues stays as re-route. Keep as-is. |
| `inspect` | Research | Deterministic flow — already inline tool call | Normalize error metadata to `violation='tool_error'` on `inspect_post` failure. |
| `find` | Research | Deterministic flow — add tool-failure branch (currently happy-path-only per `error_recovery_proposal.md § 7`) | `violation='tool_error'` for `find_posts` transient failures. No retry loop — just surface. |
| `audit` | Revise | Already AD-6 on parse failure (`violation='parse_failure'`); already AD-8 default-commit on `reference_count` | Normalize `origin='error'` → `flow.name()`; ensure `violation` key is set per § 3.3. |
| `release` | Publish | AD-6 already landed for tool failures; DP-4 retry helper opt-in in Phase 5 — `BasePolicy.retry_tool` wraps `channel_status` + `release_post` | Slot/channel-level fallback chains dropped (DP-5 B). Flow-level fallback via `flow_stack.fallback(...)` available if a scope-mismatch is ever detected, but `release` has no natural alternate flow today. |

Plus the `simplify → rework` flow-level Re-route codification, which is part of the simplify exemplar but worth stating separately: `simplify_policy` calls `flow_stack.fallback('rework')` when scope is detected as whole-post rather than a sentence/section. Existing `FlowStack.fallback` API — no new structure.

### 5.2 Phase 4b — remaining Draft / Revise / Publish / Research flows (16 flows)

Flows in these four intents that are not in the 14-step eval. Most have thin or first-draft policies today; Phase 4b brings them to template conformance.

| Intent | Non-eval flows | Template application |
|---|---|---|
| **Draft** (3 of 7) | `brainstorm`, `cite`, `draft-specific TBD` per `flow_stack/flows.py` | Entity-slot guard if flow has one; AD-6 on any deterministic tool call; skill file if agentic (frontmatter + six sections + Option C few-shots). |
| **Revise** (3 of 8) | `tone`, `simplify`, others per `flow_stack/flows.py` (exclude rework/polish/add/audit already in 4a) | `revise_content` persistence contract; AD-6 backstop with `violation='failed_to_save'` where skill owns persistence. |
| **Publish** (6 of 7) | `schedule`, `preview`, `promote`, `syndicate`, `survey`, plus one more per `flow_stack/flows.py` (exclude release in 4a) | AD-6 with `violation='tool_error'` for any deterministic publish-side tool call (Substack/Medium/etc.). |
| **Research** (4 of 6) | `browse`, `summarize`, `compare`, plus one more (exclude inspect/find in 4a) | Scratchpad writes per AD-1 convention for any flow whose output is consumed by a downstream flow (polish-style); deterministic-vs-agentic classification per Phase 2 rules. |

Exact flow lists come from `backend/components/flow_stack/flows.py` at phase-execution time — the counts above match the 7+8+7+6 totals; the specific names are the ones declared in `flow_classes`. Phase 4b confirms the list against the file rather than pre-committing to one here (avoids drift if the flow set has shifted).

### 5.3 Phase 4c — Converse / Plan / Internal (20 flows)

These three intents share a trait: flows are slot-light or orchestration-heavy, and several are cross-domain mandatory (recap, recall, retrieve, search, outline-plan per `MEMORY.md`).

| Intent | Flows | Template-application notes |
|---|---|---|
| **Converse** (7) | per `flow_stack/flows.py` Converse set (endorse, confirm, dismiss, etc.) | Often 0-slot; entity-slot guard may be absent by design — a 0-slot Converse flow is legitimate. Template still applies: skill file with § 3.4 structure if agentic; inline tool call if deterministic; AD-6 on any failure path. |
| **Plan** (6) | `triage`, `blueprint`, `calendar`, `scope`, `digest`, `remember` (per `MEMORY.md`) | Orchestration-heavy; these call other flows via `flow_stack.stackon(...)`. Template still applies at the outer policy layer; the inner orchestration uses existing `FlowStack` APIs. Re-plan mechanism (4RE) lives here — but out-of-scope for Part 3's code changes; Part 4 evals don't exercise Plan flows. |
| **Internal** (7) | `recap`, `recall`, `retrieve`, `search`, `calculate`, `peek`, plus one more (per domain) | Cross-domain mandatory (MEMORY.md). Typically deterministic — Python logic + one-or-two tool calls. Phase 4c applies the inline-tool-call pattern uniformly; AD-6 on any `_success=False` with `violation='tool_error'`; no skill file for deterministic flows (Phase 2). `retrieve` specifically gets re-checked since Tier 2 revival (§ 6) depends on it. |

### 5.4 Scope contract for Phase 4

Every flow after Phase 4 must satisfy:

- **Structural**: imports + constructs cleanly; `flow_classes[name]()` doesn't raise.
- **Contract**: policy returns a `DisplayFrame` (never `None`, never a raw dict) on every code path, per MEMORY.md module-contracts rule.
- **AD-6**: every tool call result check emits an error frame with `origin=flow.name()` + `metadata['violation']` from the 8-item vocab. No bare `frame.thoughts = err_msg` anywhere. No `origin='error'` sentinel.
- **AD-1**: any scratchpad write uses the `{version, turn_number: context.turn_id, used_count, …}` shape, keyed by bare flow name.
- **Skill file** (if agentic): frontmatter + six sections + Option C trajectories; `test_skill_frontmatter.py` + `test_skill_tool_alignment.py` pass.

Per the template philosophy (§ 1): deviations are allowed with an inline comment. A 0-slot Converse flow that skips the entity-slot guard doesn't need a ceremonial check — it needs a comment saying "0-slot flow; no entity to guard."

---

## 6. Error recovery integration — what lands in Part 3

Resolution of `error_recovery_proposal.md` decision points, translated to Part 3 deliverables. Note: `error_recovery_proposal.md § 5.3` needs an aligned update to drop the parallel `error_class` taxonomy — PEX dispatches on `violation` + `tool_log` only.

| DP | Recommendation | Status | Part 3 action |
|---|---|---|---|
| **DP-1** (`RecoveryAction` enum) | Option B: remove entirely | landed | Phase 2 |
| **DP-2** (`classify_error` location) | Option A: `PromptEngineer.classify_error` | dropped | `classify_error` is not needed — `_validate_frame` inspects `violation` + `tool_log` directly |
| **DP-3** (`_validate_frame` dispatch) | Dispatch by `violation` + `tool_log`: short-circuit for `tool_error` with empty log; Tier 2 for `parse_failure`/`empty_output`/`invalid_input`; Tier 2→1 for `failed_to_save` with tool calls | landed | Phase 2 |
| **DP-4** (retry helper placement) | Option A: `BasePolicy.retry_tool`, called from inside policy | landed | Phase 5 (release only) |
| **DP-5** (fallback) | Option B: flow-level via existing `FlowStack.fallback`; slot-level chains dropped | landed | Part 3 codifies usage (simplify/rework scope-mismatch); no new structure |
| **DP-6** (user-facing copy) | Option A: RES templates | landed | RES keys per-flow templates off `frame.origin`; detects error frames via `'violation' in metadata`. `backend/modules/templates/errors.py` is follow-up. |
| **DP-7** (auto-dump) | Option C: env-gated | landed | Not in Part 3; revisit when `database/telemetry/` exists |
| **DP-8** (commented Tier 2/3) | Option C: **revive with tightened triggers** | landed | Phase 2 un-comments both tiers; gates them on `violation` vocabulary |

**R-R-R-R-E mechanism implementations after Part 3 lands:**

- **Retry (three layers)** —
  - Skill inner loop: `PromptEngineer.tool_call` with skill-narrated "retry ONCE" (existing).
  - `BasePolicy.retry_tool(name, args, tools)`: called *from inside a policy body*; `release_policy` is the only Part 3 opt-in.
  - `pex.recover` Tier 1 rephrase: re-runs policy with scratchpad feedback; fires for malformed frames and (after Tier 2) for `{invalid_input, parse_failure, empty_output}`.
- **Rephrase (two variants)** — Tier 1 (feedback retry, existing) + Tier 2 (context-aided retry: `retrieve` + `search` then Tier 1, revived). Tier 2 fires for `{invalid_input, parse_failure, empty_output}` and for `failed_to_save` with non-empty `tool_log` (semantic drift).
- **Re-route (two variants)** —
  - Policy-directed: `FlowStack.fallback('<name>')` (e.g. `polish→rework` existing; `simplify→rework` newly codified). `FlowStack.stackon(...)` for prerequisites (refine/compose → outline, existing).
  - NLU-directed: `pex.recover` Tier 3 calls `NLU.contemplate()` (revived). Fires as follow-on to failed Tier 1 on flow-mis-selection-shaped malformations, or when `_validate_frame` detects a `missing_reference` that's really a wrong-flow signal.
- **Re-plan** — Plan-family flows, out of scope for Part 3.
- **Escalate (two variants)** — error `DisplayFrame(flow.name(), metadata={'violation': ...}, thoughts=...)` (AD-6 terminal) + `pex.recover` Tier 4 `ambiguity.declare('partial', ...)` (existing). **Note: app-crash handling is beyond 4RE** — try-catch at `Agent.take_turn` + standard system message; engineering concern, not a recovery mechanism (see `error_recovery_proposal.md § 5.9`).

**Dispatch summary (inside `_validate_frame`):**

```
if 'violation' not in frame.metadata:               # non-error frame
    run full Tier 1 ladder on malformed output
elif violation == 'tool_error' and not tool_log:    # short-circuit
    return frame as-is
elif violation in {'parse_failure', 'empty_output', 'invalid_input'}:
    Tier 2 gather-context → Tier 1 rephrase
elif violation == 'failed_to_save' and tool_log:    # semantic drift
    Tier 2 → Tier 1
elif violation in {'scope_mismatch', 'missing_reference', 'conflict'}:
    short-circuit (policy resolved or should have resolved)
else:
    Tier 4 escalate
```

All DPs resolved; no pending questions before Phase 1 begins.

---

## 7. Implementation order & migration plan

Seven phases (5 was, 7 is — Phase 4 split into 4a/4b/4c for the all-48-flows scope). Each independently shippable. Tests that must stay green are listed per phase.

**Phase 0 — Theme 8 prompt restructure (landed; ✅).** The three-layer assembly per § 3.5 is live: `backend/prompts/pex/sys_prompts.py` holds 7 intent blocks, `backend/prompts/pex/starters/<flow>.py` holds per-flow templates (refine/compose/simplify implemented; the 25 other agentic flows still use legacy scaffolding), and `backend/prompts/pex/skills/<flow>.md` holds skill bodies with the new structure. `build_skill_system` / `build_skill_messages` in `for_pex.py` assemble the layers; `SKILL_SYSTEM_SUFFIX` is gone; `## Latest utterance` tail block is gone; slot-render helpers (`render_source` / `render_freetext` / `render_checklist` / `render_section_preview`) live in `for_pex.py`. The four Theme 8 roughness follow-ups are closed (drop latest-utterance block, XML-tag starters, preload simplify target section, replace `merge_outline` with `generate_section`). Phase 4 sweeps the remaining agentic flows into this shape.

**Phase 0b — `generate_section` tool migration (landed; ✅).** New tool in `ContentService.generate_section(post_id, sec_id, content)` — appends when `sec_id` is new, replaces when it matches (with rename detection). Registered in `schemas/tools.yaml` and `pex.py` tool registry. `RefineFlow.tools` now lists `generate_section` + `generate_outline` instead of `merge_outline`. `refine_policy` checks both tools' `tool_succeeded` (either counts as saved). `merge_outline` stays registered as legacy; the policy no longer requires it. **Test migration pending:** `utils/tests/policy_evals/test_refine_policy.py`, `utils/tests/unit_tests.py`, and `utils/tests/e2e_agent_evals.py` assert on `merge_outline` — those fixtures need updating to `generate_section` before Phase 3 finishes.

**Phase 1 — uniform AD-6 metadata sweep (~60 LOC across `draft.py`, `revise.py`, `publish.py`, `research.py`).** For every error `DisplayFrame` site in the 12 exemplar flows: (a) move the flow name from `metadata['flow']` (if present) or from `origin='error'` to `origin=flow.name()`; (b) ensure `metadata['violation']` is one of the 8-item vocabulary; (c) normalize `'missing_ground'` → `'missing_entity'`. No `classify_error` helper — `_validate_frame` inspects `violation` + `tool_log` directly. Greens: `test_*_policy.py` (update assertions to the new keys); `test_skill_tool_alignment.py`, `test_skill_frontmatter.py`.

**Phase 2 — `pex.py` rework per `error_recovery_proposal.md` (~60 LOC net, mix of additions + removals).** `_validate_frame` dispatches via `violation` + `tool_log` per the § 6 dispatch summary. Delete `RecoveryAction` enum (DP-1 B). **Revive** Tier 2 (gather-context via `retrieve` + `search`) and Tier 3 (NLU `contemplate` re-route) — both gated on the `violation` vocabulary (DP-8 C). Drop the invalid `ambiguity.declare('reroute', ...)` call in Tier 3; replace with direct flow-swap + re-execute. Delete legacy `block_data.status == 'error'` branch in `_merge_block_data` (Open Q 2, confirmed legacy). Greens: `e2e_agent_evals.py` step 14; new unit tests for Tier 2 and Tier 3 trigger conditions.

**Phase 3 — six exemplar policy + skill edits (~160 LOC across `draft.py`, `revise.py`, `publish.py`, `research.py`, skill files for refine/compose/simplify/add/browse).** Lands § 4.1–4.6. Greens: `test_refine_policy.py`, `test_compose_policy.py`, `test_simplify_policy.py`, `test_create_policy.py`, `test_add_policy.py`, `test_browse_policy.py` with new fixture rows; `e2e_agent_evals.py` steps exercising these six.

**Phase 4a — remaining 9 flows in the 14-step eval (~150 LOC across `draft.py`, `revise.py`, `publish.py`, `research.py`, 6 skill files).** Applies § 5.1 patterns. Greens: all 12 tier-1 policy evals; full `e2e_agent_evals.py` run.

**Phase 4b — non-eval flows in Draft / Revise / Publish / Research (~16 flows, estimated ~250 LOC across the same four policy files + ~12 skill files).** Applies § 5.2 patterns. Where a flow currently has no policy body (stub), Phase 4b writes a first-draft following the method-shape contract (§ 3.1). Greens: `import + construct` smoke test for every flow (new `test_all_flows_construct.py`); no-new-regressions on existing tier-1 policy evals.

**Phase 4c — Converse / Plan / Internal (20 flows, ~300 LOC across `converse.py`, `plan.py` + Internal wiring, plus skill files for agentic flows).** Applies § 5.3 patterns. Per-intent caveats: 0-slot Converse flows skip the entity-slot guard with an inline comment; Plan flows use `flow_stack.stackon(...)` for orchestration; Internal flows are typically deterministic (no skill file per Phase 2 rules). `retrieve` gets re-verified since Tier 2 revival depends on it. Greens: construction smoke test + any existing Internal/Converse unit tests.

**Phase 5 — `release_policy` retry helper (~30 LOC: `BasePolicy.retry_tool` + 2 call-sites in `publish.py`).** DP-4 option A. Greens: `test_release_policy.py` with a transient-failure fixture row; `e2e_agent_evals.py` step 14.

Optional follow-up tasks (not gated on this plan):

- AD-10 prompt caching in `PromptEngineer._call_claude` (pure additive win).
- AD-9 `flow.llm_quality_check` opt-in.
- `BasePolicy.error_frame(...)` helper — only if ≥5 call-sites want identical construction; track post-Phase-4c.
- `backend/modules/templates/errors.py` (DP-6 follow-up) — `violation` → user-facing copy map in RES.
- App-crash try-catch at `Agent.take_turn` (engineering scope per § 5.9 of the proposal).
- Align `error_recovery_proposal.md § 5.3` with the `error_class`-dropped dispatch.

Rough total surface: ~1,000 LOC changed across ~10 policy/component files + ~25 skill files (out of 48 total — deterministic flows have no skill). Most of the growth from the 280 LOC earlier estimate is Phases 4b + 4c (scope expansion to all 48 flows). No new component surfaces.

---

## 8. Risk register

1. **`_validate_frame` dispatch-by-violation changes PEX behavior for existing error frames.** The old `_validate_frame` flagged AD-6 error frames as "no data" (`pex.py:184-185`) and triggered `recover` Tier 1 unconditionally. Post-fix, behavior splits by `violation` + `tool_log`. Any policy today that relies on Tier 1 auto-retry masking a tool failure will break — exactly the kind of silent failure this phase is meant to surface. Mitigation: run full `e2e_agent_evals.py` before and after Phase 2; investigate any step that changed from pass to fail.

2. **Metadata-key reclassification** (`missing_ground` → `missing_entity`; `origin='error'` → `origin=flow.name()`; drop `metadata['flow']` and `metadata['error_class']`). Downstream RES templates may key on the old metadata shapes. Mitigation: `grep` RES templates for `missing_ground` / `origin == 'error'` / `metadata['flow']` / `error_class` usages before Phase 1; update in lockstep.

3. **Simplify `needs_clarification` hoist double-handles the signal.** Today the skill's JSON reaches the user via `frame.thoughts`; the new policy parse declares `confirmation` *and* returns an empty frame. If the RES template still reads `frame.thoughts` for simplify, the user loses the clarifying question. Mitigation: verify the RES simplify path uses `ambiguity.ask()` (likely — that's the 4-level handler contract); add an `e2e` assertion.

4. **Compose `failed_to_save` backstop false-positives.** If the user says "no sections are worth composing, explain why", the skill should return text without any `revise_content` calls, and the new backstop will error. Mitigation: fold the "explain why and call no tools" path into the skill `## Important` bullet — the skill's summary text is fine; the error is only raised when at least one section was in scope.

5. **`read_metadata` failure branches change flow semantics.** Today refine/compose silently continue. Adding explicit error frames makes previously-hidden failures visible — some E2E runs that were quietly passing may now report errors. Mitigation: this is the correct behavior; treat any regression as a real bug and fix the tool or the test setup, not the policy.

6. **Reclassifying `create`'s duplicate-title to `confirmation`.** `fixes/_interfaces.md` currently says duplicate-title is `specific`. User has confirmed revert to `confirmation`. Mitigation: Phase 3 updates `draft.py:287` and the interface doc in lockstep so future readers don't re-reclassify.

7. **RecoveryAction removal** (DP-1 B) touches 6 call-sites in `pex.py`. If `world.insert_frame` or downstream telemetry expects the enum for logging, removal changes the log shape. Mitigation: grep for `RecoveryAction.` outside `pex.py`; none expected, but confirm.

8. **Eval fixtures assume old error metadata shapes.** `test_*_policy.py` files may assert on `metadata['missing_ground']`, `origin='error'`, or `metadata['error_class']`. Mitigation: Phase 1 updates fixtures in the same phase.

9. **Tier 2/3 revival re-introduces code that was commented out.** The old `retrieve`-based context-gather and `contemplate()` re-route were untested (commented out since before Themes 1-7). Reviving them risks exposing latent bugs — e.g. the `retrieve` flow may need a dedicated prompt, `contemplate()` API may have drifted. Mitigation: Phase 2 adds dedicated unit tests for each tier's trigger condition; run `e2e_agent_evals.py` to verify no step regresses. If a tier's implementation is too stale to revive cleanly, gate it behind an env flag and ship the short-circuit + classifier first.

10. **App-crash try-catch at `Agent.take_turn` is NOT in Part 3.** 4RE covers failures the agent observes; app-crash handling is engineering scope (separate commit, likely in Part 4 when telemetry wiring lands). If a production turn crashes during Part 3 rollout, we still get a Python traceback with no user message — mitigated today by the frontend showing "something went wrong" generically. Flag for follow-up, not a Part 3 blocker.

11. **Scope expansion to all 48 flows (Phases 4b + 4c) touches code the 14-step eval doesn't exercise.** Non-eval flows may have latent bugs that template application surfaces (e.g. a Converse flow that silently swallowed tool failures will now return an error frame — correct behavior, but newly visible). Mitigation: Phase 4b/4c add an `import + construct` smoke test for every flow; regressions in non-eval flows are treated as new bugs, not rollback triggers for the template work. Part 5 tunes any flow whose first-draft policy needs refinement based on Part 4 evals + Part 5a HITL feedback.

12. **Plan flows' orchestration semantics unclear without Part 4 eval coverage.** Phase 4c applies the template to Plan flows (`triage`, `blueprint`, etc.) but the 14-step eval doesn't exercise them. First-draft policies may be structurally correct but semantically under-tested. Mitigation: Part 5 picks up Plan flows once Part 4 adds Plan-specific eval coverage; Phase 4c ships the template application and flags the eval gap.

---

## 9. Open questions & feedback

All decision points are resolved. `create`'s duplicate-title uses `'confirmation'` (answered by user — Phase 3 reclassifies from current `'specific'`). `error_class` dropped in favor of `violation` + `tool_log` inspection (answered by user — `error_recovery_proposal.md § 5.3` needs aligned update). No questions block Phase 1.

### Dependencies to clear before Phase 4 sweep

- **6 intent-prompt blocks still to write.** `backend/prompts/pex/sys_prompts.py::PROMPTS` currently contains Draft + Revise. Research, Publish, Converse, Plan, Internal need their own intent-woven persona sentences and `## Background` blocks. Draft/Revise templates in § 4.7.1 serve as reference. Converse probably skips the post/section schema entirely; Internal needs its own framing.
- **25 more starter templates to write.** `backend/prompts/pex/starters/` has refine/compose/simplify. The other 25 agentic flows (all non-Internal, non-deterministic flows) need one Python module each. Decision-point checklist in § 3.5 walks 19 questions per flow; budget ~1 afternoon for 4-5 starters once the pattern is internalized.
- **25 skill files to move + reshape.** Old skills at `backend/prompts/skills/<flow>.md` need the frontmatter preserved and body restructured per § 4.7 (`## Process` + `## Error Handling` + `## Tools` split). Moved to `backend/prompts/pex/skills/<flow>.md`. `PromptEngineer._SKILL_DIRS` already falls back to the old location, so partial migration is safe.
- **Test fixtures referencing `merge_outline`.** `test_refine_policy.py`, `unit_tests.py`, `e2e_agent_evals.py` need updating to the new `generate_section`/`generate_outline` success contract. Migrate in Phase 3 alongside the other refine changes.
- **`_propose_outline` exclude_tools list.** `draft.py:128` excludes `generate_outline` and `merge_outline`. Since the refine skill no longer lists `merge_outline`, this is harmless vestigial code — clean up when convenient, not gating.

### Resolved (Theme 8 follow-ups)

- **`{end_condition}` placeholder?** ✅ Hardcode in the TEMPLATE string per flow — varies too much to standardize in `build()`.
- **`write_text` rename?** ✅ Approved; Part 5 tools review will choose the new name and verify every skill-referenced tool actually exists (no placeholder functions). Track as a Part 5 deliverable.
- **`merge_outline` deletion?** ✅ Deleted from `content_service.py`, `pex.py`, `schemas/tools.yaml`, `draft.py::_propose_outline`'s `exclude_tools`, and the outline skill's "do not call" list. Test fixtures still referencing it are Phase 3 cleanup.

### Standardization rules (§ 3)

### Exemplar flows — six patterns (§ 4)

### Generalization across all 48 flows (§ 5)

### Error recovery placement (§ 6)

### Migration order — 7 phases (§ 7)
