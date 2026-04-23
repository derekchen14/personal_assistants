# Policy Builder — Consolidated Lessons (Parts 1-5)

**This file consolidates every lesson, decision, convention, anti-pattern, and rule that emerged from the Hugo policy refactor (Parts 1-5).** Organized hierarchically by theme. Every lesson traces back to a source: architectural decisions (AD-x), universal annotations (UA-x), policy-writing conventions (#x), decision points (DP-x), themes (Tx), or specific inventory/fix documents.

Target: ~100+ lessons organized into 11 chapters for scannability. Use this as a reference when writing or reviewing policies, prompts, and flows.

---

## 1. Architectural Decisions

These seven decisions resolve the biggest open questions and shape every subsequent part. Prefix: AD-x.

### AD-1 — Cross-turn findings channel = scratchpad with key convention

**Rule.** Use scratchpad (MemoryManager, L1, turn-surviving) as the standard cross-policy findings channel. Never add a new `DialogueState` or `DisplayFrame` attribute.

**Why.** Findings from step 10 (inspect) must reach step 13 (polish). Scratchpad already survives turns; adding attributes requires component-level changes that violate the stability rule.

**Convention.** Key = `flow_name` (e.g., `'inspect'`, `'audit'`). Value = dict with required fields: `version`, `turn_number`, `used_count`, plus flow-specific payload. Type: `dict[str, dict]` (serializable). Producers write at entry; consumers walk or filter-by-key.

**Reference implementations:**
- Write: `memory.write_scratchpad(flow.name(), {'version': 1, 'turn_number': context.turn_id, 'used_count': 0, 'findings': [...]})`
- Read: `scratchpad = state.scratchpad; findings = scratchpad.get('inspect', {}).get('findings', [])` (Sources: `policy_spec.md § AD-1`, `best_practices.md § 9`, `inventory/audit.md`, `inventory/polish.md`)

### AD-3 — Outline recursion is already safe (document, don't refactor)

**Rule.** `outline_policy` only self-recurses after draining `proposals` into `sections`. Since the recursive call hits the sections-filled branch (non-recursive), infinite loops are impossible.

**Why.** A non-recursive outline doesn't exist; outline recursion is inherent to the "propose 3 candidates, user picks one, refine if needed" pattern. Over-engineering a fix introduces bugs.

**How.** Document the safety in a comment at the recursion call-site. Do NOT rewrite to iterative, do NOT extract `_execute_direct_outline`, do NOT add depth guards — all mask a non-existent bug.

**Anti-pattern:** Treating outline recursion as dangerous. (Source: `policy_spec.md § AD-3`)

### AD-6 — Three failure modes, three distinct channels

**Rule.** Classify failures into three channels; never conflate under `AmbiguityHandler`:

1. **Tool-call failure** (network, API down, permission denied) → `DisplayFrame(flow.name(), metadata={'violation': 'tool_error'}, code=<raw error>)`. Use `code` attribute for payloads.
2. **Contract violation** (skill output shape mismatch, invalid JSON) → `apply_guardrails(text, format='json')` first; if still malformed, `DisplayFrame(origin='error', metadata={'violation': 'parse_failure'}, code=<offending output>)`.
3. **Ambiguous user intent** (missing or unclear slot) → `self.ambiguity.declare(level, observation=..., metadata=...)` with one of four levels (general/partial/specific/confirmation).

**Why.** Tool failures are infrastructure issues (signal to user, no retry needed). Contract violations are prompt/output-shape bugs (may benefit from retry with repair scratchpad). Ambiguity is a user-facing clarification need (deserves a question, not an error). Conflating hides the root cause.

**Anti-patterns:**
- Declaring ambiguity for tool failures. Tool down is not a question for the user.
- Using `origin='error'` as a sentinel. Errorness lives in metadata; `origin` is always `flow.name()`.
- Inventing new violation codes outside the 8-item vocabulary. (Source: `policy_spec.md § AD-6`, `skill_tool_subagent.md § 3.2-3.3`)

### AD-7 — YAML frontmatter on skill files

**Rule.** Every skill file in `backend/prompts/pex/skills/*.md` starts with YAML frontmatter:

```yaml
---
name: <flow_name>               # matches flow.name()
description: <1-sentence purpose>
version: 1
stages:                         # optional, only if multi-stage
  - propose
  - direct
tools:                          # optional, explicit allowlist
  - find_posts
  - generate_outline
---
```

**Why.** Anthropic's 2026 convention. `description` becomes a routing key for future registries. `tools` field asserts against `flow.tools` to catch skill-registry mismatches at load time.

**How.** `PromptEngineer.load_skill_template` parses frontmatter and strips it from the body. Existing loaders keep working. Companion `load_skill_meta(name)` returns the parsed dict.

**Reference:** All deployed skills have frontmatter as of Part 2 Phase 1. (Source: `policy_spec.md § AD-7`, `decision_points.md UA-7`)

### AD-8 — EVPI default-with-commit for optional slots

**Rule.** Optional slots with a sensible default commit with the default and let downstream decide whether to clarify. Do NOT declare ambiguity upfront on optional-slot absence.

**Why.** Expected value of perfect information may be negative. If `reference_count` defaults to 5 and the user can adjust it downstream, asking upfront wastes a turn.

**When to apply:** Only for optional slots where a default makes sense. Required and elective slots never get defaults; AD-8 applies to optional only.

**Example:** `audit_policy` fills `reference_count=5` inline without asking. If the user later wants 3, they revise in the next turn.

**Anti-pattern:** Declaring ambiguity for every missing optional slot. (Source: `policy_spec.md § AD-8`, `best_practices.md § 5`, `decision_points.md UA-23`)

### AD-9 — `_validate_frame` tightens; `_llm_quality_check` is off by default

**Rule.** `_validate_frame` checks that expected values are present on frame blocks (e.g., card blocks have required `post_id`, `title`, `content` keys), not just that `.blocks` is non-empty. `_llm_quality_check` (LLM-as-judge secondary check) defaults off; enable only for flows where prose quality is the whole contract (e.g., `polish`, `rework`).

**Why.** Deterministic value-checks are cheaper and more reliable than LLM re-verification. Prose-quality evals are expensive; most flows tolerate Sonnet output without a secondary check.

**How.** Per-flow `BaseFlow.llm_quality_check` flag (default False). Override True only when the flow's contract is "prose quality matters." (Source: `policy_spec.md § AD-9`, `fixes/_shared.md § AD-9`)

### AD-10 — Token-budgeting easy wins

**Rule.** Two additive changes, no conflict:

1. **Prompt caching** on skill system prompt + tool definitions. Add `cache_control={'type': 'ephemeral'}` markers to the system-prompt tail and tool-def array in `PromptEngineer._call_claude`. 1-hour TTL, automatic cache hit. Pure cost + latency win.
2. **Per-flow `max_response_tokens` override.** Add `BaseFlow.max_response_tokens` attribute (default 4096). Most flows (inspect, find, release) never use more than 1024. Tighten per-flow to save cost without capping prose-heavy flows.

**Why.** Infrastructure wins. Caching saves ~90% on repeated system/tool segments. Token limits prevent over-budgeting deterministic or short-output flows.

**How.** Add markers at `_call_claude` lines; no behavior change. Add `max_response_tokens` override on flows where meaningful (e.g., `find.max_response_tokens = 1024`). (Source: `policy_spec.md § AD-10`, `fixes/_shared.md § AD-10`)

---

## 2. Policy-Writing Conventions

Twelve rules distilled while writing exemplar policies. Apply to every Part 3+ policy. Prefix: Convention #x or just the rule name.

### Convention 1 — Don't defend deterministic code

**Rule.** Service-layer tools have known contracts. Access keys directly.

**Example:** `flow_metadata['outline']`, not `flow_metadata.get('outline', '')`. If a key is missing or `_success=False`, that's a bug to surface, not a branch to guard.

**Why.** Default-hiding masks upstream mistakes. Let tests catch it. (Source: `policy_spec.md § Policy-writing conventions § 1`, `skill_tool_subagent.md § 3.2 convention 1`)

### Convention 2 — No defaults that hide errors

**Rule.** Never use `text or ''`, `parsed or {}`, `isinstance(parsed, dict)` patterns.

**Why.** These mask mistakes. `apply_guardrails` returns a dict; trust it. Crashes surface bugs faster than silent degradation. (Source: `policy_spec.md § Convention 2`)

### Convention 3 — Slot priorities are definitional, not advisory

**Rule.** Required slots MUST be filled. Elective slots need exactly one of ≥2 options. Optional slots are nice-to-have. `flow.is_filled()` already encodes both required and elective rules.

**How.** Use `if not flow.is_filled(): declare_ambiguity(...)` at the top. No re-checking of individual electives.

**Why.** Slot priorities route the policy's branching. Treating them as advisory invites silent bugs. (Source: `policy_spec.md § Convention 3`, `skill_tool_subagent.md § 3.1`)

### Convention 4 — Build `frame_meta` and `thoughts` first, then the frame

**Rule.** Assemble metadata dict and thoughts text on separate lines, then instantiate `DisplayFrame` in a single line. Keep short dicts collapsed (one line).

**Example:**
```python
thoughts = 'Outline shrunk from 5 bullets to 3 without explicit removal directive.'
frame = DisplayFrame(flow.name(), metadata={'violation': 'failed_to_save'}, thoughts=thoughts)
```

**Why.** Readable, diff-friendly, easy to refactor. Multi-line `DisplayFrame(...)` constructions scatter intent. (Source: `policy_spec.md § Convention 4`)

### Convention 5 — `code` holds actual code; `thoughts` holds descriptive text

**Rule.** `code` is for payloads you'd copy-paste: raw tool response, failing JSON, error stack. Descriptive prose goes in `thoughts`.

**Example:** `code=result['_message']` (the error the tool returned). `thoughts='Outline is malformed — no ## headings detected.'` (human explanation).

**Why.** `code` is machine-consumable; `thoughts` is user-readable. RES renders thoughts differently than code. (Source: `policy_spec.md § Convention 5`)

### Convention 6 — Keep metadata sparse

**Rule.** Metadata is for classification (violation category, missing-slot name). Flow identity lives in `origin`, not metadata. Specifics go in `thoughts` (natural free-form text), not nested tokens.

**Anti-pattern:** `metadata={'violation': 'parse_failure', 'field': 'title', 'error_token': 'missing_key'}`. Instead, put the field/token info in `thoughts`.

**Why.** Natural text can be rendered to users or fed to future summarizers. Mangled keys cannot. (Source: `policy_spec.md § Convention 6`)

### Convention 7 — `ambiguity.declare` uses `observation`, not metadata keys

**Rule.** `declare(level, observation=<human_text>, metadata=<classification>)`. Use `observation` for the readable description; metadata for classification only.

**Example:**
```python
self.ambiguity.declare('partial',
    observation='Simplify needs either a section or an image to target.',
    metadata={'missing_entity': 'section_or_image'})
```

**Why.** Separates the question the user sees from the routing classification. (Source: `policy_spec.md § Convention 7`)

### Convention 8 — Never invent new keys without approval

**Rule.** Hard rule. Whether in `metadata`, `extra_resolved`, `frame.blocks` data, or anywhere else — don't introduce a new key name without explicit approval.

**Why.** Downstream components (skill templates, RES templates, tool schemas) depend on known keys. Inventing a key breaks consumers.

**How.** Use existing keys or surface a design question. (Source: `policy_spec.md § Convention 8`)

### Convention 9 — Standard variable names

**Rule.** Use consistent names:
- `flow_metadata` for `tools('read_metadata', ...)`
- `text, tool_log` for `llm_execute`
- `parsed` for `apply_guardrails`
- `saved, _` (or `saved_any`, `content_saved` when disambiguating) for `tool_succeeded`

**Why.** Code reviewers instantly recognize the pattern. Reduces context switching. (Source: `policy_spec.md § Convention 9`, `skill_tool_subagent.md § 3.2 convention 8`)

### Convention 10 — No em-dashes in `frame.thoughts`

**Rule.** Thoughts are user-facing. Write like a person: commas, periods, short sentences. No em-dashes.

**Example:** `'Outline shrunk from 5 bullets to 3. No explicit removal directive.'` (not `'Outline shrunk…no directive — scope mismatch.'`)

**Why.** Em-dashes are hard to parse on small screens; commas and periods are friendlier to rendering. (Source: `policy_spec.md § Convention 10`)

### Convention 11 — Single return at end; early returns only for major errors

**Rule.** `partial` and `general` ambiguity use early returns. Everything else — `specific` ambiguity, `confirmation`, stack-on, fallback, success, error frames — assigns to `frame` and falls through to a single `return frame` at the end.

**Example:**
```python
def example_policy(self, flow, state, context, tools):
    if not flow.slots[flow.entity_slot].check_if_filled():
        self.ambiguity.declare('partial', metadata={'missing_entity': 'post'})
        return DisplayFrame(flow.name())  # Early return OK — top-level grounding failure

    if <specific ambiguity condition>:
        self.ambiguity.declare('specific', metadata={'missing_slot': '<name>'})
        frame = DisplayFrame(flow.name())  # Falls through
    else:
        frame = DisplayFrame(flow.name(), thoughts='Success')  # Falls through
    
    return frame  # Single exit
```

**Why.** Makes the overall success/error path legible. Rare early returns stand out. (Source: `policy_spec.md § Convention 11`, `skill_tool_subagent.md § 3.1`)

### Convention 12 — `origin` is always `flow.name()`

**Rule.** Every `DisplayFrame` a policy builds sets `origin` to `flow.name()` — guards, stack-on, fallback, error, and success frames alike. Error-ness lives in metadata (`'violation' in frame.metadata`), not `origin`.

**Example:**
```python
return DisplayFrame(flow.name())                                              # guard
frame = DisplayFrame(flow.name(), thoughts='No sections yet, outlining first.')  # stack-on
frame = DisplayFrame(flow.name(), metadata={'violation': 'failed_to_save'})   # error
frame = DisplayFrame(flow.name(), thoughts=text)                             # success
```

**Why.** RES keys per-flow templates off `origin`. `_validate_frame` detects errors via metadata. Single-meaning field prevents routing confusion. (Source: `policy_spec.md § Convention 12`)

---

## 3. Violation Vocabulary

Eight failure categories for `metadata['violation']`. Keep this set closed; specifics go in `thoughts`. Prefix: violation-<code>.

| Code | Fires when | Example |
|---|---|---|
| `failed_to_save` | A persistence tool ran but produced no effect | Tool returned `_success=False`; post not written to disk. |
| `scope_mismatch` | The flow ran at the wrong granularity | User asked to edit "the Motivation section" but the policy read the whole post. |
| `missing_reference` | An entity in a slot doesn't exist | Skill referenced `sec_id='unknown-section'` which is not on the post. |
| `parse_failure` | Skill output couldn't be parsed into expected shape | Skill returned `{title: 'X'}` when the contract requires `{post_id, sections, title}`. |
| `empty_output` | Skill returned nothing when prose was expected | `compose` returned an empty string instead of paragraphs. |
| `invalid_input` | A tool rejected the arguments given | Tool signature requires `snip_id` to be int or tuple, but the skill passed a string. |
| `conflict` | Two slot values contradict | User specified both `remove` and `guidance` (incompatible intents). |
| `tool_error` | A deterministic tool returned `_success=False` | `create_post` failed with a duplicate-title error. |

**Reference:** `policy_spec.md § Violation vocabulary`, `exemplar_prompts.md § Feedback`, `decision_points.md UA-8`

---

## 4. Skill-Prompt Structure

Three-layer architecture for agentic flows (deterministic flows skip). Prefix: UA-x (universal annotation).

### UA-1 through UA-6 — System prompt universals

**Rule.** System prompt contains:

1. **Persona (universal).** *"You are Hugo, an AI writing assistant that helps users create, revise, and publish blog content."* + 3 rules (terse replies, reference visual blocks, never fabricate).
2. **Post/Section ID schema.** Post IDs are 8-char lowercase hex. Section IDs are slugified. Proper-case natural-language titles.
3. **Outline depth scheme.** Level 0 = `# Title` (not editable); 1 = `##`; 2 = `###`; 3 = `-`; 4 = `  *`. Most outlines have Level 1 + Level 3.
4. **`## Handling Ambiguity and Errors` block.** Full 4-row ambiguity-level table + 8-row violation-code table. Required in every system prompt.
5. **Intent-woven persona sentence.** *"You are currently working on {Intent} tasks, which encompasses..."* (Draft/Revise/Research/Publish/Converse/Plan/Internal).
6. **`## Background` block.** Intent-scoped. Draft/Revise share the outline scheme; Research/Publish need their own framing.

**Reference:** `exemplar_prompts.md`, `decision_points.md UA-1 through UA-6`

### UA-7 through UA-14 — Per-flow starter and skill

**Rule.** User message = task framing + content tag + resolved details. Skill file = Process + Error Handling + Tools + Few-shot.

- **Task framing (DP-5).** *"Refine the outline of \"{title}\". Apply the changes from the user's final utterance to the outline below, then call the appropriate tool to save your revision. End once you have successfully saved all your refinements."*
- **Content tag (DP-6).** One of `<post_content>`, `<section_content>`, `<line_snippet>`, `<channel_content>`.
- **Preload content (DP-7).** Full outline for refine; per-section previews for compose; single section for simplify.
- **Resolved details block.** XML-wrapped with semantic labels (`Source:`, `Feedback:`, `Guidance:`, `Steps:`, `Image:`, `Channel:`, etc.).
- **Skill structure (DP-2 through DP-4).** Intro paragraph + `## Process` (numbered happy-path steps) + `## Error Handling` (failure modes) + `## Tools` (task-specific + general) + `## Few-shot examples` (3 scenarios per flow).

**Anti-pattern:** Skill file with `## Slots`, `## Background`, `## Important`, `## Output` sections. These live in system prompt or user message, not the skill.

**Reference:** `decision_points.md DP-5 through DP-9`, `exemplar_prompts.md`

### UA-15 — Scratchpad key convention (AD-1)

**Rule.** Key = `flow_name`; value = `{version, turn_number, used_count, payload}`. Producers write at entry; consumers filter-by-key.

**Reference:** `policy_spec.md § AD-1`, `decision_points.md UA-15`

---

## 5. Tool Registry & Branching

One canonical tool per CRUD operation per entity. Prefix: tool-<entity>-<op>.

### The CRUD-Entity Grid

| Entity | Create | Read | Update | Delete |
|---|---|---|---|---|
| metadata | `create_post` | `read_metadata` | `update_post` | `delete_post` |
| post outline | `generate_outline` | `read_metadata(include_outline=True)` | `generate_outline` | N/A |
| section outline | `insert_section` + `generate_section` | `read_section` | `generate_section` | `remove_content` |
| section prose | `insert_section` + `revise_content` | `read_section` | `revise_content` | `remove_content` |
| snippet | `revise_content(snip_id=int)` | `read_section(snip_id=...)` | `revise_content(snip_id=...)` | `remove_content(snip_id=...)` |
| channel | N/A | `channel_status` | `release_post` / `promote_post` / `cancel_release` | N/A |

### Snippet Semantics (snip_id)

**Rule.** Section content is an ordered list of sentences. Every snippet tool accepts:
- `snip_id=None` — whole section
- `snip_id=<int>` — single sentence at that index (0-based; `-1` is last)
- `snip_id=(start, end)` — slice of sentences, Python-style (end-exclusive)

**For `revise_content`:** `snip_id=<int>` inserts at that index; `-1` appends. `snip_id=(start, end)` replaces.
**For `remove_content`:** `snip_id=<int>` deletes one. `snip_id=(start, end)` deletes a slice.

**Range rule:** Both endpoints must be non-negative integers in `0 ≤ start ≤ end ≤ sentence_count`. `-1` never appears in a range; to reach the end, use the concrete `sentence_count`.

**Anti-pattern:** Passing `-1` as a range endpoint. That's only valid for single-int `snip_id`.

**Reference:** `tool_branching.md § Snippet identification`, `decision_points.md DP-18`

### Tool Persistence Ownership

**Rule.** Agentic flows (skill has tools) — the skill owns persistence via `revise_content`, `generate_section`, `generate_outline`. Deterministic flows (no skill) — the policy saves inline via `tools(tool_name, params)`.

**Anti-pattern:** Both policy and skill writing to disk for the same operation. Double-persistence risks silent overwrites or lost edits. (Source: `inventory/SUMMARY.md § Theme 1`, `decision_points.md UA-17`)

---

## 6. Error Handling (AD-6 Model)

Three failure channels, never conflated. Established by AD-6.

### Tool-Call Failure Path

**Trigger.** Network down, API failure, permission denied, platform unavailable.

**Response.** `DisplayFrame(flow.name(), metadata={'violation': 'tool_error'}, code=<raw error text>)`. Do NOT declare ambiguity.

**Why.** Infrastructure failure is not a question for the user; it's a signal that Hugo encountered a platform issue.

**Retry.** If the error is transient (timeout, lock), retry once at the policy layer via `BasePolicy.retry_tool`. If non-retryable or retry fails, return the error frame. (Source: `policy_spec.md § AD-6`, `best_practices.md § 3`)

### Contract Violation Path

**Trigger.** Skill output shape mismatch, invalid JSON, missing required fields, truncated result.

**Response:** 
1. First try `engineer.apply_guardrails(text, format='json')` to parse-and-fail-closed.
2. If still malformed, `DisplayFrame(flow.name(), metadata={'violation': 'parse_failure'}, code=<offending output>)`.

**Why.** Output contract violations are bugs in the skill or tool. The policy can retry with repair-scratchpad context, but eventually must fail-closed to surface the bug.

**Anti-pattern:** Declaring ambiguity for bad JSON. The skill is broken, not the user's intent. (Source: `policy_spec.md § AD-6`, `skill_tool_subagent.md § 3.2`)

### Ambiguous User Intent Path

**Trigger.** Missing or unclear slot (entity unresolved, required slot unfilled, elective slot missing, candidate needing sign-off).

**Response:** `self.ambiguity.declare(level, observation=<question>, metadata=<classification>)` with one of four levels:
- `general` — intent itself is unclear
- `partial` — intent known, key entity unresolved (which post? which section?)
- `specific` — intent + entity known, a slot value missing or invalid
- `confirmation` — candidate value exists needing sign-off (e.g., duplicate title detected)

**Why.** This is the only channel that should produce a clarification question back to the user. RES renders the question and waits for user input before resuming the flow.

**Anti-pattern:** Declaring ambiguity for tool failures. Use the tool-error channel instead. (Source: `policy_spec.md § AD-6`, `exemplar_prompts.md`)

---

## 7. Slot Architecture

Core slot rules: required (must fill), elective (exactly one of ≥2), optional (nice-to-have). Prefix: slot-<priority>.

### Required Slots

**Rule.** Must be filled before policy execution. If unfilled, declare `specific` ambiguity with `metadata={'missing_slot': '<name>'}`.

**Check.** Use `if not flow.is_filled()` which already checks required slots and electives. Inside the guard branch, identify which slot is missing.

**Example:** `flow.slots['title'].check_if_filled()` → False means title is missing.

**Reference:** `skill_tool_subagent.md § 3.1`, `decision_points.md DP-13`

### Elective Slots

**Rule.** Exactly one of ≥2 must be filled. Defined as `priority='elective'` on the flow class. `flow.is_filled()` checks the at-least-one rule; the policy identifies which one is present to route branching.

**Anti-pattern:** Single elective. That's not a choice; convert to required or optional.

**Example:** `outline` has `proposals` (propose mode) and `sections` (direct mode) as electives. The policy checks which one is filled to branch.

**Reference:** `inventory/outline.md`, `skill_tool_subagent.md § 3.1`

### Optional Slots

**Rule.** Nice-to-have but not a blocker. If a sensible default exists, commit it inline (AD-8) without asking. Otherwise, treat absence as OK; the skill proceeds without it.

**Example:** `audit`'s `reference_count` defaults to 5. `refine`'s `guidance` has no default, so absence is OK.

**Anti-pattern:** Declaring ambiguity for every missing optional slot. That's not EVPI-aware.

**Reference:** `policy_spec.md § AD-8`, `decision_points.md DP-13`, `best_practices.md § 5`

### Entity Slots

**Rule.** Must be a SourceSlot (post, section, channel, etc.) or ExactSlot (title for create). Guards go first in the policy; missing entity triggers `partial` ambiguity.

**Example:**
```python
post_id, sec_id = self._resolve_source_ids(flow, state, tools)
if not post_id:
    self.ambiguity.declare('partial', metadata={'missing_entity': 'post'})
    return DisplayFrame(flow.name())
```

**Why.** Entity resolution is grounding; without it, the flow can't proceed.

**Reference:** `skill_tool_subagent.md § 3.1`

---

## 8. Flow Stack & Cross-Turn State

Stack-on and fallback semantics. Prefix: transition-<type>.

### Stack-On Semantics

**Rule.** `self.flow_stack.stackon('<name>')` pushes a prerequisite flow onto the stack and resumes the current flow after the prerequisite completes.

**Pattern.** Three lines, no helper:
```python
self.flow_stack.stackon('outline')
state.keep_going = True
frame = DisplayFrame(flow.name(), thoughts='No outline exists, outlining first.')
```

**Why.** Stack-on is for prerequisite setup; the user sees the sub-flow's work before returning. Inlining the pattern keeps one source of truth in the policy.

**Allowed recursion:** Outline may NOT stack-on itself (AD-3). Other flows can stack-on any other flow.

**Reference:** `policy_spec.md § Theme 6`, `inventory/compose.md`

### Fallback Semantics

**Rule.** `self.flow_stack.fallback('<name>')` pops the current flow and re-routes to a sibling better-matched to the user's actual intent.

**Example:** User says "shorten the intro" but simplify flow is designed for prose-to-shorter. Fallback to polish (word-level tightening) instead.

**Pattern:** Same as stack-on but signals different UX (user sees the sibling flow, not the original).

**When NOT to use:** Don't fallback on skill errors (use error frames instead). Use only when the user's intent genuinely maps to a different flow. (Source: `decision_points.md DP-14`)

### Scratchpad Cross-Turn

**Rule.** Key = flow name; value = dict with `version`, `turn_number`, `used_count`, plus flow payload. Producers write; consumers read-and-increment `used_count`.

**Pattern:**
```python
# In audit_policy (producer)
memory.write_scratchpad('audit', {
    'version': 1,
    'turn_number': context.turn_id,
    'used_count': 0,
    'findings': [...]
})

# In polish_policy (consumer)
scratchpad = state.scratchpad
audit_findings = scratchpad.get('audit', {}).get('findings', [])
if audit_findings:
    scratchpad['audit']['used_count'] += 1
```

**Reference:** `policy_spec.md § AD-1`, `inventory/polish.md`

---

## 9. NLU Contract Assumptions

What NLU guarantees so policies don't re-derive. Prefix: nlu-<guarantee>.

### Pre-Grounded Context

**Rule.** NLU slot-fills before any policy runs. The policy receives `DialogueState` with resolved `post_id`, `sec_id`, etc. from slot resolution. Do NOT call `read_metadata` or `find_posts` to re-ground; use what NLU already provided.

**Why.** Re-grounding wastes rounds and tokens. "Deterministic core, agentic shell" means discovery is pre-done; the skill interprets, not discovers.

**Pattern.** Check `flow.slots[slot].value` or use `_resolve_source_ids(flow, state, tools)` to fetch resolved context. Never call discovery tools in the policy layer.

**Anti-pattern:** Skill calling `read_metadata` to load the outline when `_build_resolved_context` already fetched it.

**Reference:** `best_practices.md § 4`, `inventory/SUMMARY.md § Theme 1`

### Slot-Filling Correctness

**Rule.** If `flow.is_filled()` returns True, all required slots and at least one elective (if any) are filled. The policy trusts this check; it doesn't re-validate slots.

**Why.** `is_filled()` encodes the flow's slot contract. If the contract is wrong, fix the flow definition, not the policy.

**Reference:** `skill_tool_subagent.md § 3.1`

---

## 10. DisplayFrame / RES Contract

Frame attributes and block types. Prefix: frame-<part>.

### Frame Origin

**Rule.** `origin = flow.name()` always. Error-ness lives in metadata, not origin. RES keys per-flow templates off origin.

**Example:**
```python
DisplayFrame('refine', metadata={'violation': 'failed_to_save'})  # error refine frame
DisplayFrame('refine', thoughts='Saved!')                         # success refine frame
```

**Why.** Single-meaning field. RES knows how to render refine frames regardless of success/error.

**Reference:** `policy_spec.md § Convention 12`, `exemplar_prompts.md`

### Required Metadata Keys

**Rule.** Every error frame carries `metadata['violation']` set to one of the 8-item vocabulary (failed_to_save, parse_failure, etc.). Success frames may carry contextual metadata (`post_id`, `sections_touched`, etc.) but not `violation`.

**Anti-pattern:** `metadata={'error': 'failed_to_save'}` or `metadata={'status': 'error'}`. Use the standardized `violation` key.

**Reference:** `policy_spec.md § Violation vocabulary`

### Block Types and Shapes

**Rule.** Return the block type expected by the flow's RES template:
- `card` — updates the post card (create, refine, compose, rework, polish, simplify, etc.)
- `selection` — presents 3 candidate options (outline propose mode, audit findings)
- `list` — search results (find, browse)
- `compare` — side-by-side comparison (compare flows)
- `toast` — lightweight notification (release, promote, schedule)
- (empty) — chat-only flows (inspect, chat, explain, undo)

**Required data per block type.**
- `card` → `{type, data: {post_id, title, sections, ...}}`
- `selection` → `{type, data: {options: [{label, id}, ...]}}`

**Anti-pattern:** Returning wrong block type. `compose` returns `card`, not a prose blob.

**Reference:** `block_classification.md`, `decision_points.md DP-16`

---

## 11. Testing & Evals

Three-tier eval scaffold and anti-patterns. Prefix: eval-<tier>.

### Tier 1 — Policy in isolation

**Scope.** `utils/tests/policy_evals/` — run a single policy against pre-seeded state + frozen tool mocks.

**Runs in:** ~5 seconds per policy. No network, no side-effects.

**Assertions.** Tool-call sequence, frame shape, metadata keys, block types.

**What NOT to test:** Message formatting, prose quality, user-facing copy (those are Tier 2+).

**Reference:** `eval_design.md § Phase 0`, `policy_spec.md § Part 4`

### Tier 2 — E2E CLI

**Scope.** `utils/tests/e2e_agent_evals.py` — full 14-step lifecycle with three scenarios.

**Runs in:** ~20 min for all scenarios. Real LLM calls, persistent disk state.

**Assertions.** Step-by-step flow execution, inter-flow state propagation, scratchpad writes, frame→block serialization.

**Purpose.** Close the CLI↔UI gap. CLI evals pass but the UI app breaks → evals don't model user experience.

**Anti-pattern:** Mocking the LLM or the content service. Mock early failures so downstream can run, but not tools that are the focus of the eval.

**Reference:** `eval_design.md § Phase 1-2`, `census.md`

### Tier 3 — Playwright UI

**Scope.** `utils/tests/playwright_evals/` — run the full 14-step lifecycle in the browser.

**Purpose.** Validate RES → UI rendering, frame→block display, user interaction.

**Install gate:** `uv pip install pytest-playwright && playwright install chromium`

**Reference:** `eval_design.md § Phase 0`

### Failure Dumps

**Rule.** On eval failure, write `utils/policy_builder/failures/<run_id>/step_<N>.md` with:
- Utterance, expected tools, actual tools
- Expected frame origin/metadata, actual frame origin/metadata
- Scratchpad state (if relevant)
- Tool call trajectory with responses

**Why.** Machine-readable error output lets a fresh Claude instance debug without re-running the eval.

**Reference:** `eval_design.md § Phase 0`

### Anti-Patterns in Test Design

**Common mistake 1:** Testing prose quality with assertions like `assert 'motivation' in response['thoughts']`. Prose is subjective; use LLM-as-judge only as a last resort, and only for genuinely subjective quality (not for shape/structure).

**Common mistake 2:** Mocking databases to avoid setup. Real failures are in the data layer; mocks hide them. Mock only where the tool itself is irrelevant to the test.

**Common mistake 3:** Testing deterministic and agentic flows the same way. Deterministic flows have a single tool call and a closed set of outcomes. Agentic flows have multiple possible tool trajectories — test for valid outcomes, not exact tool sequences.

**Reference:** `policy_spec.md § Part 4`, `eval_design.md`

---

## 12. Anti-Patterns to Flag Explicitly

Common pitfalls and what to avoid. Prefix: anti-<pattern>.

### Error-Masking Defaults

**Pattern:** `text or ''`, `parsed or {}`, `dict.get('known_key', '')`

**Problem:** Silently converts errors to empty values. Tests pass; prod breaks.

**Fix:** Let the code crash. Use `apply_guardrails(text, format='json')` to parse-and-fail-closed if parsing is expected. (Source: Convention 2)

### Conflating Failure Channels

**Pattern:** Declaring ambiguity for tool failures. `tool.failed() → ambiguity.declare('partial')`

**Problem:** Tool failure is infrastructure (signal to user, no clarification needed). Intent ambiguity is a question. Conflating hides the root cause.

**Fix:** Use AD-6's three channels: tool failure → error frame; intent ambiguity → ambiguity.declare. (Source: AD-6)

### Em-Dashes in User-Facing Text

**Pattern:** `frame.thoughts = 'Outline shrunk from 5 bullets to 3 — scope mismatch detected.'`

**Problem:** Em-dashes are hard to parse on small screens.

**Fix:** Use periods or commas. `'Outline shrunk from 5 bullets to 3. Scope mismatch detected.'` (Source: Convention 10)

### Inventing New Metadata Keys

**Pattern:** `metadata={'error_type': '...', 'flow_id': '...', 'custom_flag': True}`

**Problem:** Downstream components (RES, tools) don't know about custom keys. They silently drop unrecognized metadata.

**Fix:** Use standardized keys only (`violation`, `missing_slot`, `missing_entity`, `failed_tool`, etc.). If you need to pass something new, surface a design question. (Source: Convention 8)

### Defensive Checks for Guaranteed Values

**Pattern:** `if post_id and post_id != '': ...` when NLU already resolved post_id.

**Problem:** If NLU guarantees a value, the policy should trust it. Defensive checks hide missing contracts.

**Fix:** Use the value directly. If it's None, that's a guard case at the top (missing_entity ambiguity). (Source: Convention 1, best_practices.md § 4)

### Hallucinated APIs

**Pattern:** `engineer.tools`, `flow.resolved`, `Block` class that doesn't exist.

**Problem:** Code crashes at runtime. Test coverage is incomplete.

**Fix:** Check imports. Use real APIs: `tools(name, params)`, `state`, `DisplayFrame`. (Source: CLAUDE.md § Module Contracts)

### Double-Persistence

**Pattern:** Both policy and skill writing to disk for the same operation.

**Problem:** Overwrites, lost edits, silent regression (skill shrinks outline; policy writes stale version).

**Fix:** Clear ownership per flow. Agentic flows: skill owns persistence. Deterministic flows: policy saves. (Source: Theme 1, tool_branching.md)

### Backwards-Compat Shims

**Pattern:** `if _legacy_flag: ... else: ...` to support old and new behavior.

**Problem:** Doubles code paths, makes testing twice as complex, leads to divergent behavior over time.

**Fix:** Remove old paths cleanly. Part 3 is consolidation, not migration. (Source: CLAUDE.md § Coding conventions)

### Mode-as-Flag

**Pattern:** `stage = 'error'` instead of error frames. `stage = 'informed'` instead of scratchpad reading.

**Problem:** Stages should reflect genuine control-flow divergence, not cosmetic labels. Conflating them hides which branch the policy actually took.

**Fix:** Stages only where the policy's structure genuinely branches (outline propose vs. direct). For "did we get findings?" use the scratchpad, not a flag. (Source: best_practices.md § 6, AD-2/AD-5 moved to AGENTS.md)

---

## 13. User-Collaboration Meta-Lessons

Patterns from feedback loops. Prefix: feedback-<topic>.

### Communication Preference

**Pattern.** User feedback consistently requests explanations of tradeoffs before new concepts are introduced.

**Example:** AD-1 needed scratchpad instead of new attributes. User wanted to understand why adding attributes was problematic before accepting scratchpad as the alternative.

**Lesson.** Surface design questions with tradeoff analysis. Don't just propose a solution; explain why the alternative was rejected. (Source: feedback_no_overdefending.md, feedback_hook_philosophy.md in memory/)

### No Concepts Without Approval

**Pattern.** Proposed `STACK_ON_REASONS` dict, `BasePolicy.guard_slot` helper, `flow.deterministic` flag — all rejected.

**Lesson.** New concepts (new dicts, new helpers, new attributes) require explicit approval. Patterns are useful; concepts must be vetted first. (Source: fixes/_shared.md § Proposed but rejected)

### Hallucination and Precision

**Pattern.** When reading complex code to propose changes, Claude sometimes hallucinates APIs that don't exist or misread method signatures.

**Lesson.** Verify assumptions with git log / grep before proposing changes. Read actual call-sites, not mental models.

### Batch Discipline

**Pattern.** Part 3 changes landed smoothly because Themes 1-7 had already consolidated patterns. Part 5 batching works because each batch validates against Part 4 evals.

**Lesson.** Large refactors need waypoints. Don't ship 48 policy rewrites at once; land by theme, then by batch, with validation gates.

---

## 14. Quick Reference: When to Use Each Concept

| Question | Answer | Reference |
|---|---|---|
| User's post is missing — how do I signal? | `partial` ambiguity with `missing_entity='post'` | AD-6, Convention 3 |
| Skill returned bad JSON — how do I respond? | Try `apply_guardrails(format='json')` first, then `parse_failure` error frame | AD-6, Convention 5 |
| Tool failed (network down) — how do I respond? | `tool_error` error frame, not ambiguity | AD-6 |
| Optional slot is missing — ask or default? | If sensible default exists, commit it (AD-8). Otherwise, OK to proceed without it | AD-8, Convention 3 |
| Which tool saves an outline section? | `generate_section` for outline content; `revise_content` for prose. Use `insert_section` first for new section shell. | tool_branching.md |
| How do I pass findings from step 10 to step 13? | Scratchpad with key=flow_name. Include `version`, `turn_number`, `used_count`. | AD-1 |
| Should I call `read_metadata` to load context? | No — NLU already resolved it. Use `_resolve_source_ids` or `extra_resolved`. | Convention 1, best_practices.md § 4 |
| How do I create a new DisplayFrame with metadata? | Build metadata dict and thoughts first, then one-line instantiation. | Convention 4 |
| What's the outline depth scheme? | Level 0: `# Title` (not editable); 1: `##`; 2: `###`; 3: `-`; 4: `  *` | UA-4, tool_branching.md |
| Should I add a new attribute to DialogueState? | No. Use scratchpad for findings; per-turn payload in frame.metadata. | AD-1, Convention 8 |

---

## Final Notes

**This document is a reference, not a rigid checklist.** Every policy should follow the 12 conventions and use the 8-item violation vocabulary. Deviations need an inline comment citing which convention justifies the deviation. The goal is consolidation (removing variance that hides bugs), not uniformity for its own sake.

**Update cadence.** After each Part 5 batch, review the lessons and add new ones discovered during implementation. If a new lesson contradicts an existing one, flag it for discussion — don't silently override.

**For reviewers.** Use this document to frame feedback. "This violates Convention 6 (keep metadata sparse)" is clearer than "metadata is too complex." Link to the specific lesson.

---

**Generated:** 2026-04-23 (Parts 1-5 consolidated)
**Source documents:** policy_spec.md, best_practices.md, decision_points.md, skill_tool_subagent.md, exemplar_prompts.md, census.md, tool_branching.md, block_classification.md, eval_design.md, inventory/*, fixes/*, memory/*.md

