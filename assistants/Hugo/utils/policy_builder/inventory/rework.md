# Policy Inventory — rework

**Parent intent:** Revise
**DAX:** {006}
**Eval step(s):** 6

## A. Policy (code) understanding

### Flow class
From `backend/components/flow_stack/flows.py` lines 200-212:
- `entity_slot`: source
- `goal`: major revision of draft content; restructures arguments, replaces weak sections, addresses reviewer comments. Scope can go across the whole post, or an entire section. For smaller changes, use polish
- `tools`: read_metadata, read_section, revise_content, insert_section, remove_content
- Slot schema:
  - source (SourceSlot, 'sec' entity_part) — post and section reference
  - remove (RemovalSlot, optional) — specific content to cut during rework
  - changes (FreeTextSlot, elective) — prose critique or directive
  - suggestions (ChecklistSlot, elective) — numbered list of specific changes

### Guard clauses
From `backend/modules/policies/revise.py` lines 34-45 (rework_policy):
- **Line 35-36:** Call `_require_source(flow, state, context)` which checks if entity_slot is filled. If missing, declare 'specific' ambiguity and return empty DisplayFrame().
- **Line 39:** Call `_resolve_source_ids` to ground post_id and sec_id from source slot.
- **Line 40:** Call `llm_execute` to run the skill (tool-using loop).
- **Line 41:** Mark flow.status = 'Completed'.
- **Line 42:** Build DisplayFrame with origin='rework' and thoughts from LLM output.
- **Line 43-44:** If post_id exists, add a card block with post content.

### Staging
No staging used. The flow has no stage field manipulation.

### Stack-on triggers
None. The rework policy does not call `flow_stack.stackon()` or `fallback()`.

### Persistence calls
Persistence is delegated to the LLM sub-agent via `llm_execute` (line 40). The skill prompt (`backend/prompts/skills/rework.md` line 9) instructs the sub-agent to call `revise_content` directly to save the expanded version. The policy itself does not call `_persist_section` — that helper is designed for single-step policies; rework's multi-tool loop handles persistence inside the tool-call loop.

### Frame shape
- **Origin:** 'rework' (line 42)
- **Blocks:** One card block added if post_id is resolved (lines 43-44), containing post_id, title, status, and full content markdown
- **Thoughts:** LLM output text describing the rework action (line 42)
- **Metadata:** Empty (line 42)
- **Code field:** Not set

### Ambiguity patterns
- **Lines 35-36:** declare('specific', metadata={'missing_slot': flow.entity_slot}) when source is not filled via `_require_source`. This is the only ambiguity point in the policy.

### Eval step + recent track record
**Step 6 from `utils/tests/e2e_agent_evals.py` lines 113-125:**
- Utterance: "Expand the Motivation section — flesh out the customer story about the screen-reading support agent and why text-only context kept failing"
- Expected tools: ['read_section', 'revise_content']
- Rubric:
  - did_action: "Prose expanded with richer detail"
  - did_follow_instructions: "Expanded content includes the screen-reading agent story and the text-only context limitation"

## B. Skill (prompt) understanding

### Skill contract
From `backend/prompts/skills/rework.md`:
The skill expects `resolved` context to include:
- `post_id` — the target post identifier
- `post_title` — the post title (optional)
- `section_ids` — list mapping section IDs to names (optional; skill can use read_metadata if needed)
- `target_section` — the section ID to rework (when source.sec is filled)

The skill is explicitly told (lines 15-16) to use provided IDs rather than executing extra tool calls.

### Tool plan
Ordered tools the skill may call:
1. **read_metadata** (for post structure; optional, prefer resolved context)
2. **read_section** (required: loads the target section's current content before editing)
3. **revise_content** (required: saves the expanded version back to the section)

Per-tool guardrails:
- Always read before writing — never skip read_section.
- revise_content takes the whole section content; the skill must preserve paragraph breaks and heading structure (line 14).
- read_metadata is a fallback if resolved context lacks section mappings.
- Rework changes substance and depth, not just word choice (line 13).

### Output shape
JSON with this structure (lines 23-32):
```json
{
  "target": "<section name>",
  "before_summary": "<one-line summary of the prior version>",
  "after_summary": "<one-line summary of the expanded version>",
  "added": ["<thing added>", "<thing added>"]
}
```

The actual revised prose is saved via revise_content and shown to the user via the card.

### Few-shot coverage
Lines 37-56 provide a single positive example:
- User: "Expand the Motivation section — flesh out the customer story about the intent classification chatbot."
- Tool trajectory: read_section → revise_content
- Output: JSON with before_summary, after_summary, and a list of what was added

The example covers section-level expansion with a customer story. Missing coverage:
- Removing content during rework (the remove slot is defined but not exemplified)
- Suggestion list processing (suggestions slot from NLU is not shown in few-shot)
- Multi-section rework (scope across whole post)
- Structural changes beyond content addition (arguments replaced, sections reordered)

### Duplication with policy
The policy and skill both understand that rework is about expansion and restructuring at section scope. The policy delegates all tool decisions to the skill via llm_execute. The skill prompt explicitly directs the sub-agent to call read_section before editing, avoiding the mistake of writing without reading. No guard-clause logic in the policy pre-validates content or structure.

## Known gaps

1. **Suggestion slot under-utilized:** The NLU rework_slots.py defines a `suggestions` ChecklistSlot (flows.py line 210) for itemized changes, but the skill prompt's few-shot example doesn't show how to process a list of suggestions. The skill would need to iterate or prioritize them; current guidance is vague.

2. **Remove slot not exemplified:** The `remove` slot (flows.py line 208) is defined as "optional" but the skill's few-shot shows only addition, not removal. If the user says "Expand the section but remove the old customer story", the skill must coordinate read_section, identify and cut the old story, and add new content — no example guides this scenario.

3. **Scope clarity:** The goal says "Scope can go across the whole post, or an entire section" but the source slot's entity_part is 'sec', suggesting section-only. If the user names the whole post (not a section), the policy does not pre-check; the skill must handle it or the request fails ambiguously.

4. **Tool sequencing in step 6 eval:** Expected tools are ['read_section', 'revise_content'] but the skill could call read_metadata if it doesn't trust resolved context. The eval rubric doesn't penalize extra reads, so this slippage is acceptable but not ideal.
