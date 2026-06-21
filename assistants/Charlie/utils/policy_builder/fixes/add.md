# Fixes — `add` Flow

**Status:** applied (see themes listed below)

## Back-references to Part 1

- Inventory: `inventory/add.md` — § A (Flow class, Guard clauses), § B (Tool plan, Few-shot coverage), § Known gaps #1–#4 (especially Known Gap #1, "Skill prompt mismatch with flow goal")
- Primary SUMMARY.md theme: **Theme 2** (unexemplified slots — `points`, `additions`, `image`). Notes the `add` entry as a "Special case" because the prior few-shot taught the wrong use case entirely.
- Theme feedback: `_theme2_feedback.md` § `add`
- Reference: `ADD_PROMPT` rule 2 in `backend/prompts/nlu/draft_slots.py` — "Adding a wholly new top-level section to a post after the Compose phase is rare — sections should normally be added during the outline phase."
- Part 2: > **Alignment.** Fixes land under [§ 1 Skill-prompt structure](../best_practices.md#1-skill-prompt-structure) — see [Anthropic skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) on concrete input/output examples rather than abstract descriptions (each declared slot `points` / `additions` / `image` now has a matching trajectory) and on consistent terminology (AD-4's `OUTLINE_LEVELS` reused verbatim instead of re-defined in the `add` skill).

## Changes that landed

### 1. Full skill rewrite to match detail-into-existing-section semantics (Theme 2, Special case)

**What changed.** `backend/prompts/skills/add.md` has been rewritten end-to-end. The prior skill had a single few-shot that taught `insert_section` with "after Process" — the **rare** new-top-level-section case. The new skill opens with: "Add more in-depth content into an **existing** section … New top-level sections are rare here; if the user is asking for a wholly new section, that work normally belongs in `outline`."

Three few-shot examples replace the old one, each matching a declared slot:

- **Example 1 — `points` (ChecklistSlot)**: user asks to add three bullet notes into `Methods`. Trajectory: `read_section` → `insert_content` with a list of bullets. `position` defaults to `'end'` when unfilled.
- **Example 2 — `additions` (DictionarySlot)**: user asks for content in two sections. The skill processes them in **post-structure order** (`section_ids` from Resolved entities), not the dict-key order — the prompt is explicit that NLU's dict-key order is just an estimate.
- **Example 3 — `image` (ImageSlot)**: user asks for a diagram in `Architecture`. Trajectory: `read_section` → `insert_media` with `image_type`, `description`, `position='end'`.

The `## Important` block also codifies the 4-level outline scheme (AD-4) for bullet content — ` - bullet` (Level 3) as the default, `   * sub-bullet` (Level 4) for nested detail.

**Why.** Known Gap #1 was the headline: the old few-shot **contradicted the flow goal** (flows.py line 187 — "add more in depth content … to an existing section") and the NLU rule in `ADD_PROMPT`. Theme 2 feedback § `add` (a) quotes the contradiction; (c) drafted the three replacement examples. The rewrite also addresses Known Gaps #2 (no branching for content type) and #3 (resolved context not exploited — each example now uses provided `section_ids` rather than calling `read_metadata`).

**Files touched.** `backend/prompts/skills/add.md`. (The policy `add_policy` in `backend/modules/policies/draft.py` was not modified — per Theme 2 feedback (d.1), "We should trust the NLU to detect flows correctly." No guard redirects new-section requests to `outline`; we rely on upstream routing.)

### 2. Default position = end of section (Theme 2 feedback d.2)

**What changed.** Every example shows `position='end'` when the `position` slot is unfilled. The skill's `## Slots` block states: "Default is end of section when unspecified."

**Why.** Answers Theme 2 feedback d.2 ("By default, it can go to end-of-section"). Keeps `position` as an `optional` slot — the skill infers a safe default rather than forcing NLU to fill it for every utterance.

### 3. New-top-level-section requests belong in `outline` (no policy guard)

**What changed.** The skill's `## Important` block: "New top-level sections: if the user clearly asks for a brand-new section, emit a short note in the JSON output instead of using `insert_section` — the `outline` flow is the right place for that work." No policy-level guard was added.

**Why.** Theme 2 feedback d.1: "We should trust the NLU to detect flows correctly." Per AD-6 this is also not an error or ambiguity — it's a routing question for NLU. The skill's fallback note is belt-and-suspenders for the rare case NLU routes it here anyway.

## Architectural decisions applied

- **AD-4** (4-level outline system): bullets written by `add` follow the canonical scheme — Level 3 ` - ` for top-level notes, Level 4 `   * ` for nested detail. Skill references the `outline` skill for the full reference rather than duplicating the table.
- **AD-5** (terminology): skill language — "emit", "process", not "fire".

## Open follow-ups

- Fuzzy section-name matching (Known Gap #4 — "Best Practices after Process" → `process` sec_id) is left to the tool layer; no skill-level logic was added.
- Image-slot semantics across `add` / `simplify` / `polish` are still flow-specific (insert vs. replace vs. annotate). Theme 2 feedback (Q3) called out the unified-contract question; the user asked us to hold off ("just set some simple default") — that default is now encoded per flow rather than in a shared image contract.
