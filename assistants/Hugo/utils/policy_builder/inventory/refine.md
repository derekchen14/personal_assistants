# Policy Inventory — refine

**Parent intent:** Draft
**DAX:** {02B}
**Eval step(s):** 3, 4

## A. Policy (code) understanding

### Flow class
From `backend/components/flow_stack/flows.py` (lines 143–154):
- entity_slot: `source`
- goal: refine the bullet points in the outline; adjust headings, reorder points, add or remove subsections, and incorporate feedback
- tools: `['find_posts', 'read_metadata', 'read_section', 'generate_outline', 'write_text']`
- slot schema:
  - `source` (SourceSlot(1), required)
  - `steps` (ChecklistSlot, elective) — structured list of specific changes requested by user
  - `feedback` (FreeTextSlot, elective) — open-ended guidance on how to improve

### Guard clauses
From `backend/modules/policies/draft.py:refine_policy` (lines 98–130):

1. **Guard: flow completeness** (lines 99–104). If NOT `flow.is_filled()`:
   - If `source` slot not filled:
     - declare('partial', metadata={'missing_ground': 'source slot empty'}) (line 101)
   - Else if `feedback` AND `steps` both not filled:
     - declare('specific', metadata={'missing_slot': 'details on how to refine the outline are incomplete'}) (line 103)
   - Return DisplayFrame() (empty) (line 104)

2. **Guard: source resolution** (lines 106–109). Resolve source to post_id:
   - Call `_resolve_source_ids(flow, state, tools)` (line 106)
   - If post_id could not be resolved:
     - declare('specific', metadata={'missing_ground': 'could not resolve source to a post'}) (line 108)
     - Return DisplayFrame() (line 109)

3. **Guard: outline existence** (lines 110–130). Check if post has an outline with bullet points:
   - Call `tools('read_metadata', {'post_id': post_id, 'include_outline': True})` (line 110)
   - Call `_has_bullets(content)` helper (line 113) to check for `- `, `* `, or `1. ` prefixes
   - If outline has bullets (line 113):
     - Call `llm_execute(flow, state, context, tools)` to refine (line 114)
     - Check if `generate_outline` was called and succeeded (lines 115–116)
     - If LLM failed: return DisplayFrame(origin='refine', metadata={'error': 'LLM failed to refine outline bulletpoints'}) (lines 118–119)
     - Else (success):
       - Set `flow.status = 'Completed'` (line 121)
       - Return DisplayFrame(origin='refine', thoughts=text) with card block of post (lines 122–123)
   - Else (no bullets, outline is missing):
     - Stack-on outline flow (line 126): `self.flow_stack.stackon('outline')`
     - Set `state.keep_going = True` (line 127) so UI doesn't wait for user input
     - Return empty DisplayFrame() (line 128)

### Staging
No `flow.stage` assignments in refine_policy. Single path: validate → refine or stack-on.

### Stack-on triggers

**Outline stack-on** (lines 125–128):
- Condition: Source resolved OK, but outline has no bullet points (missing outline)
- Action: `flow_stack.stackon('outline')` + `state.keep_going = True` + return empty DisplayFrame
- Rationale: User cannot refine a non-existent outline; must generate first

### Persistence calls

**Delegated to LLM sub-agent via llm_execute:**
- Skill may call `generate_outline(post_id, outline_content)` to save refined outline (line 115)

**Direct tool calls by policy:**
- `tools('read_metadata', {'post_id': post_id, 'include_outline': True})` (line 110) — load current outline to check if it exists
- `_resolve_source_ids(flow, state, tools)` → calls `resolve_post_id` which may call `find_posts`, `read_metadata` (line 106)

**Helpers called:**
- `_has_bullets(content)` (line 113) — regex check, not a tool call
- `_read_post_content(post_id, tools)` (line 123) — loads post for card block

### Frame shape

**Success (lines 122–123):**
- origin: `'refine'`
- thoughts: LLM text output (summary of refinement)
- blocks: 1 card block with post content (title, status, all sections)

**Error (LLM failure, lines 118–119):**
- origin: `'refine'`
- metadata: `{'error': 'LLM failed to refine outline bulletpoints'}`
- blocks: none
- thoughts: none

**Stack-on deflection (line 128):**
- origin: not set (empty DisplayFrame)
- blocks: none
- thoughts: none

**Early guard returns (lines 104, 109):**
- origin: not set (empty DisplayFrame)
- blocks: none
- thoughts: none

### Ambiguity patterns

- **'partial'** (line 101) — source slot not filled. Metadata: `{'missing_ground': 'source slot empty'}`. User needs to specify which post.
- **'specific'** (line 103) — both feedback and steps are empty. Metadata: `{'missing_slot': 'details on how to refine the outline are incomplete'}`. User needs to give instructions.
- **'specific'** (line 108) — source title did not resolve to a known post. Metadata: `{'missing_ground': 'could not resolve source to a post'}`.

### Eval step + recent track record

**Step 3** (`utils/tests/e2e_agent_evals.py` lines 69–85):
- Utterance: "Add bullets to the outline. Under Process, add: pick a vision encoder, wire it to the planner, fine-tune on UI traces, evaluate on held-out workflows, and ship behind a flag. Under Ideas, add: using video for temporal grounding, treating screenshots as a tool the agent can call, and falling back to text-only when latency budget is tight."
- Expected tools: `['read_metadata', 'generate_outline']`
- Rubric:
  - did_action: "Process and Ideas sections each have the requested bullets appended to (not replacing) any existing bullets"
  - did_follow_instructions: "All 5 new Process bullets and all 3 new Ideas bullets are present; prior bullets are preserved"

Policy validates source, checks outline has bullets, calls `llm_execute`. Skill reads current outline via context, appends new bullets, calls `generate_outline` to save. Policy returns card.

**Step 4** (`utils/tests/e2e_agent_evals.py` lines 86–100):
- Utterance: "Reorder the outline: move Ideas before Process, and rename it to Breakthrough Ideas. The final order should be Motivation, Breakthrough Ideas, Process, Takeaways."
- Expected tools: `['read_metadata', 'generate_outline']`
- Rubric:
  - did_action: "Sections reordered and Ideas renamed to Breakthrough Ideas"
  - did_follow_instructions: "Order is Motivation, Breakthrough Ideas, Process, Takeaways"

Policy same flow. Skill renames section, reorders, saves via `generate_outline`. Policy returns card.

**Known eval gap (from AGENTS.md line 133):**
- "Step 3 `refine_bullets` (L3): `generate_outline` overwrites instead of appending; investigate skill prompt or tool semantics."
- Suggests the refine skill or tool may be re-generating the entire outline from scratch (overwrite) rather than merging user changes with existing bullets (append).

---

## B. Skill (prompt) understanding

### Skill contract

From `backend/prompts/skills/refine.md` (lines 1–48):

**Inputs from resolved context:**
- `post_id` (string): The post whose outline to refine
- `post_title` (string): Title of the post
- `section_ids` (list): Existing section IDs for reference
- `target_section` (string, optional): If user is editing a specific section

**Slots consumed:**
- `source` (required): The post whose outline to refine
- `steps` (optional): A structured list of specific changes requested by user
- `feedback` (optional): Open-ended guidance on how to improve the outline

### Tool plan

**Ordered tools (lines 5–10):**

1. `read_metadata(post_id: str, include_outline: true)` — Load current outline to see structure (line 6)
2. `read_section(post_id: str, sec_id: str)` — If you need to see content of specific sections (line 7)
3. `write_text(...)` — If you need to generate new bullet points or descriptions (line 8)
4. `generate_outline(post_id: str, content: str)` — Save the revised outline (implied by policy, not explicit in skill)

**Guardrails:**
- When user specifies exact bullet points, use those verbatim; do not add or remove beyond what was requested (line 15)
- Rephrase bullets only if user explicitly asks to improve them or to fix grammatical errors (line 16)
- Use provided post/section IDs from resolved context rather than extra tool calls (line 17)
- Do NOT call extra tool calls to resolve post IDs; context is pre-resolved (line 17)

### Output shape

**Markdown text (lines 24–25):**

The refined outline saved via `generate_outline`. Format as `## Heading` per section with `- bullet` lines underneath. Example (lines 35–47):

```
## Motivation
- (existing bullets preserved)

## Process
- (existing bullets preserved)
- design scenarios
- assign labels
- generate conversations

## (other sections preserved)
```

Final reply is typically this markdown (TXT, not JSON). The policy persists it automatically (line 13: "The policy saves the result automatically — just output the revised outline as markdown").

### Few-shot coverage

One example provided (lines 27–47):

- User: "Add bullets to the outline. Under Process, add: design scenarios, assign labels, generate conversations."
- Correct tool trajectory:
  1. `read_metadata(post_id=..., include_outline=True)` — returns existing outline
  2. `generate_outline(post_id=..., content=<full outline with new bullets appended under Process>)`
- Correct final reply: Markdown outline with new bullets appended under Process, all other bullets preserved

**What's covered:**
- Appending bullets to a section (not replacing)
- Preserving existing bullets in all sections
- Tool order: read first, then save

**What's missing:**
- Reordering sections (step 4 test case uses reordering, but no example shows this)
- Renaming sections
- Removing bullets
- Removing sections entirely
- What to do if outline is malformed or missing

### Duplication with policy

**Policy handles guard conditions; skill outputs refinement:**
- Policy checks source resolves (lines 106–109 in draft.py). Skill expects resolved context (line 17).
- Policy checks outline exists and has bullets (lines 110–113). Skill assumes it exists (lines 1–3: "Refine an existing outline").
- Policy stacks-on outline if missing (lines 125–128). Skill has no fallback.
- Policy calls `read_metadata` as guard check (line 110). Skill also calls it to load outline (line 6). Redundant if policy's guard check could be used.

**Minor overlap:** Both policy and skill use `read_metadata` to load the outline. The policy uses it for existence check; the skill uses it for content. Could be unified.

---

## Known gaps

1. **KNOWN EVAL GAP: generate_outline overwrites not appends** (from AGENTS.md line 133). Step 3 expects bullets to be appended to existing Process/Ideas sections, but the tool may be re-generating from scratch (overwrite). No example in skill shows how to handle this, and the skill's "append not replace" rule (line 15) may not be honored by the tool.

2. **Reorder/rename operations not exemplified:** Step 4 requires renaming "Ideas" → "Breakthrough Ideas" and reordering sections. The skill file has one example (append bullets); it doesn't show how to reorder or rename. Skill must infer from the instruction alone.

3. **Missing section handling:** Skill says "Do not add or remove bullets beyond what was requested" (line 15), but what if user asks to remove a section entirely? The skill has no guidance on how to signal that to `generate_outline`.

4. **Fallback if read_metadata fails:** Skill assumes `read_metadata` succeeds (line 6). If it returns `_success: false`, the skill has no recovery path. Policy also doesn't handle this; it checks `check_if_filled()` but not tool success.

5. **Slot redundancy:** Both `steps` (structured list) and `feedback` (open-ended) are optional and elective. If user provides neither, the policy declares 'specific' ambiguity (line 103), but the skill still receives a tool call. Skill should handle the case where both are missing, but doesn't.

6. **Policy/skill contract on output:** Skill line 13 says "policy saves the result automatically", but policy only calls `generate_outline` if skill outputs call it. If skill outputs only markdown text without calling `generate_outline`, the policy will catch the missing tool call and error (line 118). The expectation is unclear.
