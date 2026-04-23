# Policy Inventory — simplify

**Parent intent:** Revise
**DAX:** {7BD}
**Eval step(s):** 7

## A. Policy (code) understanding

### Flow class
From `backend/components/flow_stack/flows.py` lines 262-273:
- `entity_slot`: source
- `goal`: reduce complexity of a section or note; shorten paragraphs, simplify sentence structure, remove redundancy; image simplification means replacing with a simpler alternative or removing entirely
- `tools`: read_metadata, read_section, revise_content, remove_content, write_text
- Slot schema:
  - source (SourceSlot, 'sec' entity_part, elective) — post and section reference
  - image (ImageSlot, elective) — image to simplify or remove
  - guidance (FreeTextSlot, optional) — prose guidance on how to simplify

### Guard clauses
From `backend/modules/policies/revise.py` lines 155-170 (simplify_policy):
- **Line 156-158:** If both source and image are unfilled, declare 'partial' ambiguity and return empty DisplayFrame(). (Simplify is unusual: it requires at least one of two slots, not a single entity_slot like other revise flows.)
- **Line 160:** Call `_resolve_source_ids` to ground post_id and sec_id from source slot (may return None, None if source is unfilled).
- **Line 161:** Call `llm_execute` to run the skill (tool-using loop).
- **Line 163-164:** If post_id and sec_id and text all exist, call `_persist_section` to save the simplified version directly (unlike rework/polish, simplify persists via the policy helper).
- **Line 166:** Mark flow.status = 'Completed'.
- **Line 167:** Build DisplayFrame with origin='simplify' and thoughts from LLM output.
- **Line 168-169:** If post_id exists, add a card block with post content.

### Staging
No staging used. The flow has no stage field manipulation.

### Stack-on triggers
None. The simplify policy does not call `flow_stack.stackon()` or `fallback()`.

### Persistence calls
**Line 164:** `self._persist_section(post_id, sec_id, text, tools)` is called directly by the policy after llm_execute returns. This is different from rework/polish, which delegate persistence to the skill. Simplify uses the policy-level helper because the skill's output is the complete revised text, ready to persist without further tool loops. The skill calls revise_content internally (per skill prompt line 10) but the policy also calls _persist_section as a safety measure to ensure the LLM output is saved.

### Frame shape
- **Origin:** 'simplify' (line 167)
- **Blocks:** One card block added if post_id is resolved (lines 168-169), containing post_id, title, status, and full content markdown
- **Thoughts:** LLM output text describing the simplify action (line 167)
- **Metadata:** Empty (line 167)
- **Code field:** Not set

### Ambiguity patterns
- **Line 157:** declare('partial', metadata={'missing_slot': 'source_or_image'}) when both source and image are unfilled. This is the only ambiguity point in the policy.

### Eval step + recent track record
**Step 7 from `utils/tests/e2e_agent_evals.py` lines 127-136:**
- Utterance: "The second paragraph of Breakthrough Ideas is too wordy. Cut a sentence or two."
- Expected tools: ['read_section', 'revise_content']
- Rubric:
  - did_action: "Shorter, cleaner paragraph"
  - did_follow_instructions: "Second paragraph reduced in length"

## B. Skill (prompt) understanding

### Skill contract
From `backend/prompts/skills/simplify.md`:
The skill expects `resolved` context to include:
- `post_id` — the target post identifier
- `post_title` — the post title (optional)
- `section_ids` — list mapping section IDs to names (optional)
- `target_section` — the section ID to simplify (when source.sec is filled)

The skill is explicitly told (lines 55-57) to use provided IDs instead of extra read_metadata calls.

### Tool plan
Ordered tools the skill may call:
1. **read_section** (required: loads the target section before editing, per line 7 "Always read first")
2. **revise_content** (required: saves the simplified version)
3. **read_metadata** (optional, for post structure if resolved context is incomplete)

Per-tool guardrails:
- **Never write without reading** (line 7, line 56): Always call read_section on the target section before editing.
- **Scope discipline** (lines 13-16): If the user names a paragraph, edit only that paragraph. Do not touch neighboring paragraphs. If the whole section is named, edit the whole section.
- Preserve meaning (line 9): Do not restructure; if restructuring is needed, rework is the appropriate flow.
- revise_content takes the whole section; the skill must preserve all unchanged paragraphs (lines 34-37 example shows this).
- read_metadata is optional; resolved context should suffice.

### Output shape
JSON with this structure (lines 19-28):
```json
{
  "target": "Breakthrough Ideas — paragraph 2",
  "before": "<the exact prior text of the edited span>",
  "after": "<the simplified text that was saved>",
  "summary": "<one sentence describing what you cut>"
}
```

### Few-shot coverage
Lines 31-47 provide a single positive example:
- User: "The second paragraph of Breakthrough Ideas is too wordy. Cut a sentence or two."
- Tool trajectory: read_section → identify paragraph 2 → revise_content with whole section (paragraph 2 simplified, others unchanged)
- Output: JSON with before/after for paragraph 2 and a summary of edits

The example covers paragraph-level simplification within a section, matching the eval step exactly. Missing coverage:
- Simplifying a whole section (no paragraph specified)
- Image simplification (the image slot is defined as elective in the flow)
- Guidance slot usage (the guidance FreeTextSlot is optional but not exemplified)

### Duplication with policy
The policy checks that at least one of source or image is filled (line 156-158) but then delegates the rest to llm_execute. The skill prompt directs reading before writing and preserving scope discipline. The policy does not pre-parse "paragraph 2" from the user's utterance; the skill must identify the span. Both layers emphasize not over-editing (scope discipline is stated in the policy goal and reinforced in the skill prompt lines 13-16).

## Known gaps

1. **Image slot under-utilized:** The flow slot schema defines `image` (ImageSlot, elective) for image simplification/removal (flows.py line 270), but the skill prompt doesn't cover this case. If the user says "Simplify the hero image", the skill receives no guidance on whether to propose a simpler alternative or remove it. The eval doesn't test this; step 7 is text-only.

2. **Guidance slot not exemplified:** The guidance slot (FreeTextSlot, optional, flows.py line 271) allows the user to specify "make it more casual" or "target a younger audience" to guide simplification. The skill prompt doesn't show how to use this; it only shows the case where the user explicitly names paragraphs and implicitly requests shortening.

3. **Persistence double-call:** The skill prompt (line 10) says the policy will save automatically, and the policy does call `_persist_section` (line 164). However, the skill also calls revise_content in its tool loop. This means the skill's revise_content call persists, and then the policy's _persist_section call persists again — potentially a redundant write or a overwrite. The contract is unclear.

4. **Paragraph identification under-specified:** The eval step says "The second paragraph of Breakthrough Ideas is too wordy." The skill must identify what "paragraph 2" means in the returned section text. Paragraphs are not marked with line numbers or IDs; the skill must count blank-line-separated blocks. No logic in the prompt specifies how to handle ambiguous cases (e.g., if there are only 3 paragraphs and the user asks to edit paragraph 5).
