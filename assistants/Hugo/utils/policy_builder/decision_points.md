# Decision Points — policy + prompt authoring

**Purpose.** When writing the prompt + policy for a flow, the template (system prompt shell, skill file shape, starter shell, policy control flow) is already fixed. This file catalogs the **remaining customization decisions** — where the author must fill in flow-specific content — so the policy_builder app can surface them for round-1/round-2 review.

**Scope.** A decision point is a question whose answer is:
- **Not already defined** elsewhere (flow class, slot schema, `FLOW_CATALOG`, `pex._tools`, `sys_prompts.py`)
- **Not computable** from existing definitions
- **Consequential** — different answers produce meaningfully different prompt/policy output

Questions like "what parent intent?" or "which entity?" are NOT decision points — they're already defined on the flow class. Questions like "what's the skill's opening paragraph?" or "what preloads into `<section_content>`?" ARE — the template leaves those blank.

---

## Part A — Universal conventions (for reference, not questions)

These are locked-in across all flows. The app displays them as context; they don't need per-flow answers.

| # | Convention | Source |
|---|---|---|
| UA-1 | System prompt opener: `"You are currently working on {Intent} tasks, which {definition}"` | `sys_prompts.py` |
| UA-2 | System prompt assembly order: persona → intent prompt → universal `## Handling Ambiguity and Errors` → skill body | `for_pex.py::build_skill_system` |
| UA-3 | Per-intent `## Background` content is already locked in `sys_prompts.py` per intent (Draft has outline scheme + ID format; Revise has prose-exclusive note + scope discipline; Research has tool schemas; Publish has channel model). Authoring a new flow doesn't touch this. | `sys_prompts.py` |
| UA-4 | Outline depth scheme: 5 levels (Level 0 `# Title` not editable; 1 `##`; 2 `###`; 3 `-`; 4 `  *`) | `sys_prompts.py::DRAFT` |
| UA-5 | Post ID format: 8-char lowercase hex (first 8 of UUID4) | `post_service.py:169` |
| UA-6 | Section ID format: slug (lowercase, punctuation-stripped, spaces→dashes, ≤80 chars) | `services.py::_slugify` |
| UA-7 | Ambiguity levels (4): `general`, `partial`, `specific`, `confirmation` | `for_pex.py::AMBIGUITY_AND_ERRORS`, AD-6 |
| UA-8 | Violation codes (8): `failed_to_save`, `scope_mismatch`, `missing_reference`, `parse_failure`, `empty_output`, `invalid_input`, `conflict`, `tool_error` | `policy_spec.md § Violation vocabulary` |
| UA-9 | Skill file shape: (optional intro) + `## Process` + (optional `## Error Handling`) + `## Tools` (with `### Task-specific tools` / `### General tools`) + `## Few-shot examples` | `exemplar_prompts.md § Feedback 3` |
| UA-10 | Formatting conventions: em dash `—` separators in tool bullets; Title Case sub-headers consistent within a section; `Resolved Details:` heading (capital D) in few-shot examples | Lessons #2, #3, #5 |
| UA-11 | User-message envelope: `<task>` + content tag + `<resolved_details>` + `<recent_conversation>`. Content tag mirrors the 4 entity parts `{post, sec, snip, chl}`: `<post_content>`, `<section_content>`, `<line_snippet>`, `<channel_content>`. Non-standard XML: closing `<resolved_details>` has no slash (intentional style). | Lessons #1, #9 |
| UA-12 | Embedded outlines in few-shot examples use 2-space indent under the parent list item (never raw `## Heading` mid-example) | Lessons #8 |
| UA-13 | The LLM never sees slot concepts — render values directly in `<resolved_details>`; no mention of "slot", "required", "elective", priority | `exemplar_prompts.md § Feedback 1` |
| UA-14 | Rules that must not be violated live in the system prompt AND are reinforced in the skill template | `exemplar_prompts.md § Feedback 3` |
| UA-15 | Scratchpad key convention: key = `flow_name`; value = dict with `version`, `turn_number`, `used_count`, plus flow payload | AD-1 |
| UA-16 | Persona (from `general.py::build_system`): 3 bullets — response length, visual-block referencing, no-fabrication | `general.py` |
| UA-17 | Persistence ownership: agentic flows (skill has tools) — the skill owns persistence. Deterministic flows — the policy saves inline. | Theme 1 |
| UA-18 | Error channel selection: tool failure → error frame (AD-6); contract violation → error frame (AD-6); ambiguous user intent → `handle_ambiguity`. Never conflate. | AD-6 |
| UA-19 | Prompt caching: `cache_control: {'type':'ephemeral'}` on system block + last tool def; 1-hour TTL | AD-10 |
| UA-20 | `max_response_tokens` default = 4096 (override per-flow when meaningful) | AD-10 |
| UA-21 | `_llm_quality_check` default = off (enable only when prose quality is the flow's whole point) | AD-9 |
| UA-22 | Scenario-setup / user-message alignment: `sec`, `target_section`, `user_text`, `<section_content>` heading, recent conversation, and latest utterance must all agree | Lessons #7 |
| UA-23 | Optional-slot default-with-commit: if a sensible default exists, commit with it; don't declare ambiguity upfront | AD-8 |

---

## Part B — Per-flow decisions (the app's questions)

These are where the template leaves the author to decide. Each decision below has:
- **Decision:** what's actually being chosen
- **Applies to:** *all flows* or *agentic flows only* (see deterministic-flow note below)
- **Why it matters:** what changes in the output
- **Precedents:** how Refine / Compose / Simplify answered it, as concrete reference

The app renders these as form fields per flow. Claude proposes an answer in round 1; user overrides in round 2.

### Answer shape

A DP's `proposal` is usually a **plain string**. For flows with multiple policy modes whose answers diverge cleanly (e.g., outline's `propose` vs. `direct`), `proposal` is a **mode-keyed object** like `{"propose": "...", "direct": "..."}`. The app detects type and renders: string \u2192 one textarea; object \u2192 one textarea per mode. Use the string form when mode-specific content shares significant text \u2014 duplicating across modes is worse than inlining the cross-mode commentary.

### Deterministic flows

Flows whose policy calls a single tool inline without LLM reasoning (`create`, `find`, `inspect`, `explain`, `undo`) have no skill file. For these, the skill-authoring DPs (DP-2 through DP-9, plus DP-18 and DP-19) surface as **`N/A` with rationale**. Do NOT leave the proposal blank \u2014 write a short sentence explaining *why* the DP doesn't apply to this flow, and when a schema-level equivalent exists (e.g., create's DP-1 maps to a CategorySlot invariant rather than a prompt rule), name it. The rationale is what lets future Claude proposals recognize the deterministic shape.

---

### Prompt content

**DP-1: Flow-specific must/never rules**
*Decision:* 0–3 inviolable rules unique to this flow, to be pinned in both the system prompt and the skill template (per UA-14).
*Applies to:* all flows. Agentic flows pin the rules in the skill template; deterministic flows express them as schema-level invariants (e.g., CategorySlot restricts enum values).
*Why it matters:* These surface as "## Constraints" or reinforcement bullets; they catch failures the generic Background doesn't cover.
*Precedents:*
  - Refine: "`generate_section` can only add or edit sections — use `generate_outline` for removal."
  - Compose: "Do NOT invent new terminology — jargon must come from the outline or user."
  - Simplify: "Preserve the meaning. Do NOT expand scope or rewrite paragraphs the user didn't ask you to touch."

**DP-2: Skill intro paragraph**
*Decision:* The one- or two-sentence framing that opens the skill file, explaining what the skill does and where to start.
*Applies to:* agentic flows only (deterministic flows have no skill file).
*Why it matters:* This is the first thing the LLM reads after the system prompt; it anchors the skill's purpose.
*Precedents:*
  - Refine: "This skill describes how to refine outlines. The current outline is provided in the user utterance between the `<post_content>` block. Use it directly as your starting point rather than creating a new one from scratch."
  - Compose: "This skill describes how to convert an outline into prose. The current outline is provided in the user message inside the `<post_content>` block as per-section previews. Use it to plan scope; read the full bullets with `read_section` before converting each section."
  - Simplify: "The skill describes how to simplify a paragraph, sentence, or phrase within a post. The current section is provided in the user utterance between the `<section_content>` block. Use it directly as your starting point for simplification."

**DP-3: Process steps**
*Decision:* The numbered happy-path sequence for `## Process` — what to read, how to interpret, when to call which tool, when to end.
*Applies to:* agentic flows only. Multi-mode flows (e.g., outline's propose/direct) express this as a mode-keyed object.
*Why it matters:* This is the flow's workflow. The LLM follows it literally. Wrong order or missing step → bugs.
*Precedents:*
  - Refine: 5 steps (read guidance → identify scope → adjust → save via generate_section/generate_outline → end turn). Sub-bullets call out renames, bullet-detail, and brainstorming.
  - Compose: 4 steps with a nested per-section 3-step loop (read_section → convert_to_prose → revise_content). Sub-bullets call out scope decision and tone matching.
  - Simplify: 5 steps (read guidance → deep-read → identify target span → shorten → save via the right tool → end turn).

**DP-4: Tool usage hints**
*Decision:* Per task-specific tool, the 1–2 flow-specific usage hints layered onto the registry description (when to reach for this tool in THIS flow, priority vs alternatives, sub-bullets for gotchas).
*Applies to:* agentic flows only.
*Why it matters:* Registry descriptions are flow-agnostic; the skill file is where flow-specific priority lives. Without this, the LLM guesses.
*Precedents:*
  - Refine on `generate_section`: "default saver. Pass the section ID (slug), not the section name. For renames, pass the OLD sec_id — the tool re-slugs from the new title."
  - Refine on `generate_outline`: "use only for sweeping changes or removing sections. If used, it is always the last call."
  - Compose on `read_section`: "required before composing any section. Never write without reading."

---

### Starter content

**DP-5: Task framing sentence**
*Decision:* The imperative sentence inside `<task>` that tells the LLM what this turn's job is, including the termination clause.
*Applies to:* agentic flows only. Multi-mode flows use a mode-keyed object (one task string per mode).
*Why it matters:* The `<task>` block is what the LLM orients on for THIS turn. A vague task produces vague output.
*Precedents:*
  - Refine: `"Refine the outline of \"{title}\". Apply the changes from the user's final utterance to the outline below, then call the appropriate tool to save your revision. End once you have successfully saved all your refinements."`
  - Compose: `"Convert the outline of \"{title}\" into written prose. Compose the post by turning the structured outline into paragraphs. Add transition phrases, introductions, and concluding sentences if needed to weave the story together. Then call the appropriate tool to save the post. End once all sections have been composed."`
  - Simplify: `"Simplify the target span in \"{title}\" — shorten sentences, reduce paragraph length, and remove redundancy without changing the meaning. Respect scope narrowly: if the user named a paragraph, edit only that paragraph; if they named a section, edit every paragraph in it. Then call the appropriate tool to save your revised prose. End once the simplified content has been saved."`

**DP-6: Content tag choice**
*Decision:* Which of `<post_content>`, `<section_content>`, `<line_snippet>`, `<channel_content>` wraps the preloaded data (matching the entity this flow targets).
*Applies to:* agentic flows only.
*Why it matters:* Mis-matched tag vs preload confuses the LLM; the tag is an implicit type signal.
*Precedents:*
  - Refine: `<post_content>` (full outline)
  - Compose: `<post_content>` (per-section previews)
  - Simplify: `<section_content>` (one section's prose)

**DP-7: Preload content**
*Decision:* What goes inside the content tag — full outline? Per-section previews? One section's prose? Nothing (force a `read_section` call)?
*Applies to:* agentic flows only. Multi-mode flows use a mode-keyed object.
*Why it matters:* Preloading saves round-trips but burns context; picking wrong costs tokens or tool calls.
*Precedents:*
  - Refine preloads `current_outline` (full outline, since the flow reads and edits the whole thing)
  - Compose preloads per-section `section_preview` (titles + bullet summaries — the LLM calls `read_section` for each section it processes)
  - Simplify preloads the target section's full prose (since simplify only touches one section and the skill promises no extra `read_section`)

---

### Few-shot examples

**DP-8: Scenario coverage**
*Decision:* Which user-phrasing paths to exemplify (typically 3 per skill).
*Applies to:* agentic flows only.
*Why it matters:* Few-shot examples anchor the LLM's pattern-matching. Wrong coverage → LLM pattern-matches to the wrong example on novel inputs.
*Precedents:*
  - Refine: (a) revising section bullets, (b) appending across multiple sections with retry, (c) reordering + renaming
  - Compose: (a) whole post at standard depth, (b) single section, (c) depth-4 variant
  - Simplify: (a) specific paragraph, (b) whole section, (c) image with unclear operation

**DP-9: Example content (topic + post state)**
*Decision:* The concrete post topic, section names, and content used in the few-shot examples. Must not overlap with the evaluation set.
*Applies to:* agentic flows only.
*Why it matters:* Realistic examples train better than abstract ones, but overlap with eval posts pollutes testing.
*Precedents:*
  - All three exemplars anchor on "User Simulators for training RL agents" with section names like Motivation / Architecture / Evaluation. Post ID format `abcd0123` (realistic 8-char hex).

---

### Error handling

**DP-10: Likely errors and ambiguities encountered**
*Decision:* The realistic set of (violation code × recovery path) and (ambiguity level × trigger) for THIS flow. This is the content of the skill's `## Error Handling` subsection AND the policy's error-frame branches.
*Applies to:* all flows (deterministic flows only populate the policy-side branches).
*Why it matters:* Without enumeration, the skill ends up with generic error handling that doesn't match real failure modes. Per the Part 3 conventions (and UA-18 / AD-6), error routing depends on knowing which channel applies.
*Precedents:*
  - Refine: malformed `<post_content>` → `execution_error('invalid_input', ...)`; user names non-existent section → `handle_ambiguity('specific', metadata={'missing_slot': ...})` or `missing_reference` error frame; `generate_section` tool failure → retry once, then `tool_error`.
  - Compose: `convert_to_prose` fails for a section → retry once, skip on second fail, continue other sections, report skipped via `tool_error` at end; user's request doesn't map to visible sections → `handle_ambiguity('partial' or 'specific')`.
  - Simplify: `<section_content>` malformed → `execution_error('invalid_input', ...)`; user names a paragraph that doesn't exist in the section → `handle_ambiguity('specific')`; image simplification with no verb → `handle_ambiguity('confirmation')`; cross-section edit → `handle_ambiguity('partial')` directing user to Rework flow.

**DP-11: Flow transitions (stack-on and fallback) — MERGED with DP-14**
*Status:* Content moved to DP-14. Historical proposals may still carry a DP-11 entry; new proposals consolidate the answer under DP-14. Structural fallbacks are stack-ons in disguise (both push another flow onto the stack); re-routing fallbacks pop-and-push via `flow_stack('fallback', ...)`. DP-14 now covers all three cases.

**DP-12: Retry strategy per tool**
*Decision:* For each tool in the flow's roster, retry count on transient failure, and what to do after max retries.
*Applies to:* all flows.
*Why it matters:* Over-retrying wastes budget; under-retrying surfaces flaky infrastructure as user-visible errors.
*Precedents:*
  - Refine: `generate_section` / `generate_outline` → retry once, then `execution_error('tool_error')`.
  - Compose: `convert_to_prose` → retry once, then SKIP that section and continue; `revise_content` → retry once, then `execution_error('tool_error')`.
  - Simplify: `generate_section` / `remove_content` → retry once, then `execution_error('tool_error')`.

---

### Policy logic

**DP-13: Optional slot defaults (AD-8)**
*Decision:* For each *optional* slot on this flow, does it have a sensible default that lets the policy commit-without-asking? If so, what's the default?
*Applies to:* all flows. Note: the question applies to `optional` slots only, NOT `elective` slots. Elective slots (exactly-one-of ≥ 2) are definitional to the flow's mode switch (e.g., outline's `topic` / `sections` / `proposals` determine propose vs. direct); they are not defaultable. `flow.is_filled()` already encodes the elective rule.
*Why it matters:* Defaults let the flow run on fewer clarifications. No default → must declare `specific` ambiguity on absence.
*Precedents:*
  - Audit: `reference_count` (optional) defaults to 5.
  - Outline: `depth` (optional) defaults to 1.
  - Refine / Compose / Simplify: `guidance` (optional) has no default; treated as a soft preference when filled, ignored when absent.
  - Create: `topic` (optional) has no default — passed to `create_post` only if filled.

**DP-14: Flow transitions (stack-on and fallback)**
*Decision:* When does this flow hand off to another flow, and through which channel? Two channels: `flow_stack('stackon', <name>)` pushes a prerequisite onto the stack and resumes the current flow after; `flow_stack('fallback', <name>)` pops the current flow and re-routes to a sibling better-matched to the user's actual intent. Also note cases where the flow emits an error frame and stops (no transition).
*Applies to:* all flows. Most flows do not transition; outline may NOT stack on itself (AD-3).
*Why it matters:* Stack-on changes the user's experience (they see the sub-flow's work before returning); fallback replaces this flow entirely. Choosing the wrong channel or triggering on cosmetic state produces confusing UX.
*Precedents:*
  - Compose: `flow_stack('stackon', 'outline')` when `current_outline` is empty. Thoughts: "No outline to compose from, stacking on Outline first."
  - Refine: no proactive stack-on; `flow_stack('stackon', 'outline')` as error-recovery structural fallback when the outline is unparseable.
  - Rework: no stack-on; three fallbacks — `flow_stack('fallback', 'polish')` for word-tightening intent, `flow_stack('fallback', 'simplify')` for trimming intent, `flow_stack('fallback', 'remove')` for span-excise intent.
  - Simplify: no transitions; emits an error frame and stops on unworkable state.

**DP-15: Scratchpad contract (write / read)**
*Decision:* Does this flow write findings for downstream flows? Does it read from upstream producers? What's the payload shape?
*Applies to:* all flows.
*Why it matters:* The scratchpad is the cross-turn findings channel (AD-1). Wrong shape breaks consumers.
*Precedents:*
  - Inspect / Find / Audit: write to `scratchpad[flow_name]` with `{version, turn_number, used_count, payload}`.
  - Polish (informed mode): reads from inspect/find/audit scratchpad entries; increments each `used_count` after consuming.
  - Refine / Compose / Simplify: no scratchpad interaction.

**DP-16: Frame output spec (metadata keys + block types)**
*Decision:* What success-path metadata keys does the `DisplayFrame` carry, what error-path keys, and what block types go in `frame.blocks`?
*Applies to:* all flows. Multi-mode flows use a mode-keyed object when success block types differ per mode (e.g., outline's `selection` block for propose vs. `card` block for direct).
*Why it matters:* RES renders based on block type + metadata. Unknown keys silently drop; missing blocks break the UI.
*Precedents:*
  - Refine: success metadata = `{post_id, post_title, section_ids_touched}`; error metadata = `{violation, failed_tool?}`; block = outline card.
  - Compose: success metadata = `{post_id, sections_composed, sections_skipped}`; block = prose card per section.
  - Simplify: success metadata = `{post_id, sec_id, target_span}`; block = diff card (before/after).

**DP-17: Final reply shape**
*Decision:* The assistant's final text reply format — plain prose (1–2 sentences), structured JSON, or card-only (text reply is empty and RES speaks through the card)?
*Applies to:* all flows. Multi-mode flows use a mode-keyed object if the reply shape differs per mode.
*Why it matters:* Persona says 1–2 sentences; some flows need structured output for downstream consumers. Mismatches break RES templates.
*Precedents:*
  - Refine / Compose: plain prose summary of what was saved.
  - Simplify: structured JSON with `target`, `before`, `after`, `summary` (or `needs_clarification` / `error` variants).
  - Inspect / Find: structured card, text reply is a short summary referencing the card.

---

### Performance overrides

**DP-18: Model tier override**
*Decision:* Does this flow benefit from Opus over the Sonnet default? (Haiku is only for deterministic classification.)
*Applies to:* agentic flows only (deterministic flows make no LLM call).
*Why it matters:* Model tier trades off cost/latency for output quality. Most flows tolerate Sonnet; prose-quality-gated flows don't.
*Precedents:*
  - Sonnet default: Refine, Compose, Simplify, Outline, Add.
  - Opus candidate: Polish, Rework (prose quality is the contract).
  - Haiku: reserved for deterministic classification (none of the 12 eval flows use Haiku today).

**DP-19: `max_response_tokens` override**
*Decision:* Tighten below the 4096 default?
*Applies to:* agentic flows only. Multi-mode flows use a mode-keyed object if different modes have different output-size budgets (e.g., outline propose at 3072, direct at 2048).
*Why it matters:* 4096 is generous; most flows never use it. Lowering saves cost + latency without hurting quality.
*Precedents:*
  - 4096 (default): Compose (prose can be long), Rework.
  - 1024: Inspect (returns short summary), Find (post dedup, short results), Release (status line).
  - 2048: Refine, Simplify.

---

## Summary

**19 per-flow decision points**, grouped into six app field sections:

| Section | DPs | Purpose | Agentic-only |
|---|---|---|---|
| Prompt content | DP-1, DP-2, DP-3, DP-4 | System-prompt rules + skill body content | DP-2, 3, 4 |
| Starter | DP-5, DP-6, DP-7 | `<task>` wording + content tag + preload | all three |
| Few-shot | DP-8, DP-9 | Which scenarios + what post content | all two |
| Error handling | DP-10, DP-12 | Likely errors, retries | none |
| Policy logic | DP-13, DP-14, DP-15, DP-16, DP-17 | Slot defaults, flow transitions, scratchpad, frame, reply | none |
| Performance | DP-18, DP-19 | Model tier, token budget | both |

DP-11 is merged into DP-14 (structural fallbacks are stack-ons; re-routing fallbacks share the same `flow_stack` surface). Totals 18 active DPs; older proposal files may still carry 19.

**Deterministic flows** (create, find, inspect, explain, undo) skip the 10 agentic-only DPs (DP-2\u2013DP-9, DP-18, DP-19). Those entries still appear in the flow's proposal JSON with `N/A` plus a short rationale explaining why the DP doesn't apply \u2014 e.g., create's DP-1 maps to a CategorySlot schema invariant rather than a prompt rule.

**Multi-mode flows** (e.g., outline propose/direct; polish basic/informed) use a mode-keyed object (`{"propose": "...", "direct": "..."}`) in place of a plain string for DPs whose answers diverge cleanly per mode. DPs whose content mixes mode-specific and shared commentary stay as strings.

Each DP is a customization choice, not an architectural lookup. Each has concrete Refine/Compose/Simplify precedents so round-1 proposals can say "this flow's answer looks like Refine's" or "new shape; here's the rationale".

## Next step

Convert DP-1…DP-19 into an app schema:
- One form field per DP per flow; the field shows the question + Claude's proposed answer + an override textbox.
- Precedents from Refine / Compose / Simplify render inline as reference.
- Round 1 = Claude's `proposals/<flow>.json` with all 19 answered; Round 2 = user's `answers/<flow>.json` with overrides.
