# Policy Inventory — add

**Parent intent:** Draft
**DAX:** {005}
**Eval step(s):** 8

## A. Policy (code) understanding

### Flow class
From `backend/components/flow_stack/flows.py` lines 182-196:
- `entity_slot`: source
- `goal`: add more in depth content, such as sub-sections or an image to an existing section; inserted at a specific position
- `tools`: read_metadata, read_section, insert_section, insert_content, insert_media
- Slot schema:
  - source (SourceSlot, elective) — post reference
  - points (ChecklistSlot, elective) — bulletpoint list to add to a section
  - additions (DictionarySlot, elective) — dict mapping section names to content
  - image (ImageSlot, elective) — image to insert
  - position (PositionSlot, optional) — insertion index

### Guard clauses
From `backend/modules/policies/draft.py` lines 169-181 (add_policy):
- **Line 170-173:** If entity_slot (source) is not filled, declare 'specific' ambiguity with missing_slot metadata and return empty DisplayFrame('error').
- **Line 175:** Call `_resolve_source_ids` to ground post_id from source slot.
- **Line 176:** Call `llm_execute` to run the skill (tool-using loop).
- **Line 177:** Mark flow.status = 'Completed'.
- **Line 178:** Build DisplayFrame with origin='add' and thoughts from LLM output.
- **Line 179-180:** If post_id exists, add a card block with post content.

### Staging
No staging used. The flow has no stage field manipulation.

### Stack-on triggers
None. The add policy does not call `flow_stack.stackon()` or `fallback()`.

### Persistence calls
Persistence is delegated to the LLM sub-agent via `llm_execute` (line 176). The skill prompt (`backend/prompts/skills/add.md`) instructs the sub-agent to call `insert_section` or `insert_content`/`insert_media` tools directly. The policy itself does not call `_persist_section` or `_persist_outline` — those are reserved for rework/simplify/polish which modify existing sections; add creates new content elements.

### Frame shape
- **Origin:** 'add' (line 178)
- **Blocks:** One card block added if post_id is resolved (lines 179-180), containing post_id, title, status, and full content markdown
- **Thoughts:** LLM output text describing the add action (line 178)
- **Metadata:** Empty (line 178)
- **Code field:** Not set

### Ambiguity patterns
- **Line 172:** declare('specific', metadata={'missing_slot': flow.entity_slot}) when source is not filled. This is the only ambiguity point in the policy.

### Eval step + recent track record
**Step 8 from `utils/tests/e2e_agent_evals.py` lines 138-146:**
- Utterance: "Add a new section called Best Practices after Process"
- Expected tools: ['insert_section']
- Rubric:
  - did_action: "New section added to the post"
  - did_follow_instructions: "Section titled Best Practices inserted after Process"

## B. Skill (prompt) understanding

### Skill contract
From `backend/prompts/skills/add.md`:
The skill expects `resolved` context to include:
- `post_id` — the target post identifier
- `post_title` — the post title (optional but available)
- `section_ids` — list of current section IDs mapped to section names

The skill is explicitly told (line 12) to use these provided resolved entities instead of calling `read_metadata` repeatedly.

### Tool plan
Ordered tools the skill may call:
1. **read_metadata** (optional, for post structure verification if resolved context is incomplete)
2. **insert_section** (primary: adds a new top-level section with a heading and empty body)
3. **insert_content** (for adding notes or paragraphs into existing sections)
4. **insert_media** (for image insertion)

Per-tool guardrails:
- Prefer using resolved section_ids rather than calling read_metadata for post structure.
- insert_section is the authoritative tool for creating a new section; position is resolved from the user's utterance ("after Process") into a 0-based index or anchor string.
- insert_content is for adding bullet points or paragraphs within an existing section.
- insert_media is used only when the image slot is filled.

### Output shape
JSON with this structure (lines 19-31):
```json
{
  "post_id": "...",
  "new_section": {
    "title": "...",
    "sec_id": "...",
    "position": <integer index>
  },
  "ordering_after": ["<sec_id>", "<sec_id>", "..."]
}
```

### Few-shot coverage
Lines 34-50 provide a single positive example:
- User: "Add a new section called Best Practices after Process"
- Tool trajectory: insert_section with post_id, title='Best Practices', position='after:process'
- Output: JSON reflecting the new section and its position in the list

The example covers the common case of adding a section at a relative position. Missing coverage:
- Adding content (points) into an existing section rather than a new top-level section
- Adding to multiple sections in one utterance (additions dict case)
- Image addition scenarios
- Positional variants (beginning, end, numeric index)

### Duplication with policy
The skill independently constructs the position index ("after Process" → index 3 in the example), but the policy doesn't pre-resolve this. The skill also independently decides which tool to call based on the content type (insert_section vs insert_content) — the policy delegates this entirely to llm_execute without guard-clause logic to split them.

## Known gaps

1. **Skill prompt mismatch with flow goal:** The skill's first paragraph (lines 5-10) and few-shot example focus exclusively on adding a **new top-level section**. However, the flow goal (flows.py line 187) and the policy_spec.md (line 22) explicitly state that add is for "drilling down into more depth within a section, NOT a new top-level section." The NLU ADD_PROMPT rule 2 (draft_slots.py line 1200) says "Adding a wholly new top-level section to a post after the Compose phase is rare — sections should normally be added during the outline phase." The skill prompt contradicts this guidance.

2. **Missing branching for content type:** The policy branches on entity_slot but the skill doesn't differentiate between the three content cases (points for same-section bullets, additions for multi-section dict, image for media). The skill's few-shot shows only insert_section; no example for insert_content or insert_media.

3. **Resolved context not exploited:** Lines 12-13 of the skill prompt mention using resolved entities but the few-shot example doesn't demonstrate this; it doesn't show the resolved section_ids list being used to avoid a read_metadata call.

4. **Ambiguity on section references:** When the user mentions "Best Practices after Process", the skill must fuzzy-match section names (e.g. "process" in the user's speech → 'process' sec_id). The skill prompt doesn't specify this logic; it relies on the tool's internal behavior.
