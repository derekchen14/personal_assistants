# Fixes — `rework` Flow

**Status:** applied (see themes listed below)

## Back-references to Part 1

- Inventory: `inventory/rework.md` — § A (Flow class, Guard clauses, Persistence calls), § B (Skill contract, Tool plan, Few-shot coverage), § Known gaps #1–#3
- Primary SUMMARY.md themes: **Theme 2** (unexemplified slots — `remove`, `suggestions`), **Theme 7** (tool-log extraction)
- Theme feedback: `_theme2_feedback.md` § `rework`, `_theme7_feedback.md` § Helper 2 (`tool_succeeded`)
- Part 2: > **Alignment.** Fixes land under [§ 1 Skill-prompt structure](../best_practices.md#1-skill-prompt-structure) — see [Anthropic skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) on concrete input/output examples over abstract descriptions (every declared slot — `suggestions`, `remove`, `changes` — now has a matching few-shot) and on direct commands replacing "might consider" (the `done: [...]` array contract).

## Changes that landed

### 1. Skill gained three concrete few-shot examples (Theme 2)

**What changed.** `backend/prompts/skills/rework.md` now carries three few-shot scenarios instead of the single Motivation-expansion example captured in the inventory (lines 37–56 of the prior version):

- **Example 1** — prose-guided expansion using `changes` (the original customer-story case, rewritten around a notetaking chatbot exemplar to stay out of the Kitty Hawk test set).
- **Example 2** — an itemized `suggestions` ChecklistSlot being processed; the reply's `done: [...]` array names each suggestion it addressed.
- **Example 3** — mixed `remove` + `changes`: the "read once, output twice" pattern. The skill issues ONE `read_section`, then TWO `revise_content` calls — first to excise, then to add new material on top of the trimmed version.

**Why.** The inventory's Known Gaps #1 and #2 flagged that `suggestions` and `remove` were declared on `ReworkFlow` (flows.py lines 208–210) but not exemplified, so NLU-filled values were silently dropped. Theme 2 feedback (§ `rework` (c)) laid out the two additional exemplars verbatim; the remove+changes read-once/output-twice combinator is an extra on top.

**Files touched.** `backend/prompts/skills/rework.md`.

### 2. Whole-post scope now triggers a per-section loop (Known Gap #3)

**What changed.** `rework_policy` in `backend/modules/policies/revise.py` (lines 41–54) splits on whether `sec_id` was resolved. When the user names the whole post (no section), the policy reads metadata, walks `section_ids`, and calls `llm_execute` once per section, passing `extra_resolved={'target_section': sid, 'rework_scope': 'whole_post'}`. Section-scoped requests still run a single skill pass.

**Why.** The flow goal ("Scope can go across the whole post, or an entire section") contradicted the `source` slot's `entity_part='sec'`; Known Gap #3 called out the silent failure. The skill prompt's `## Important` bullet on `rework_scope: whole_post` tells the sub-agent to treat `target_section` as "the section for THIS invocation" so it does not try to reach across sections.

### 3. `_mark_suggestions_done` helper (Theme 2 consumer side)

**What changed.** New module helper `_mark_suggestions_done(flow, tool_log, text)` parses the JSON reply for either a top-level `done: [...]` array or a legacy `suggestions: {name: "done"}` dict, then calls `sug_slot.mark_as_complete(step_name)` on each match. Invoked after every `llm_execute` return (single-section and per-section loop).

**Why.** Once Example 2 taught the skill to emit `done`, the policy needed a consumer so ChecklistSlot items actually get ticked off between turns.

### 4. `self.engineer.tool_succeeded(tool_log, 'revise_content')` (Theme 7)

**What changed.** `_mark_suggestions_done` gates its JSON-parse work behind `self.engineer.tool_succeeded(tool_log, 'revise_content')`. The helper returns `(bool, dict)`; the helper is on `PromptEngineer` per the Theme 7 scoped-down decision (spec § AD Progress index row 7).

**Why.** Matches the one helper the user accepted from the Theme 7 proposal. The rejected helpers (`guard_slot`, `complete_with_card`, `stack_on`) do not appear here.

## Architectural decisions applied

- **AD-5** (terminology): "per-section loop" / "stack on" — no "fires" language.
- **AD-6**: vague `remove` targets are a `specific`-level **ambiguity**, not an error frame — the skill signals via `needs_clarification` (see skill § Important) and the policy surfaces it through `AmbiguityHandler`.

## Open follow-ups

- Multi-section rework with `additions`-style scoping (dict of section → directive) is not exemplified; today the whole-post loop is an all-or-one lever.
- `_mark_suggestions_done` accepts two JSON shapes for backwards compatibility — consolidate to the `done: [...]` array once no skill variants emit the legacy dict.
