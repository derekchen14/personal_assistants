# Policy Inventory — compose

**Parent intent:** Draft
**DAX:** {003}
**Eval step(s):** 5

## A. Policy (code) understanding

### Flow class
From `backend/components/flow_stack/flows.py` (lines 169–180):
- entity_slot: `source`
- goal: write a section from scratch based on instructions or an outline. If only given a topic, generate an outline first; for editing existing content, use rework
- tools: `['read_metadata', 'read_section', 'convert_to_prose', 'write_text', 'revise_content']`
- slot schema:
  - `source` (SourceSlot(1), required)
  - `steps` (ChecklistSlot, elective) — ordered process-level actions to follow
  - `guidance` (FreeTextSlot, elective) — qualitative writing direction (tone, length, angle)

### Guard clauses
From `backend/modules/policies/draft.py:compose_policy` (lines 143–167):

1. **Guard: entity slot (source)** (lines 144–147). If `flow.slots[flow.entity_slot]` not filled:
   - declare('specific', metadata={'missing_slot': flow.entity_slot}) (line 146)
   - Return DisplayFrame() (line 147)

2. **Main path: check for outline, possibly stack-on** (lines 149–156):
   - Resolve source to post_id (line 150)
   - If post_id exists:
     - Call `tools('read_metadata', {'post_id': post_id})` to check if post has section structure (line 152)
     - If post has NO `section_ids` (line 153):
       - Stack-on outline flow: `flow_stack.stackon('outline')` (line 154)
       - Set `state.keep_going = True` (line 155)
       - Return empty DisplayFrame() (line 156)

3. **Compose path: execute or persist** (lines 158–167):
   - Call `llm_execute(flow, state, context, tools)` to compose prose (line 158)
   - If post_id exists and text returned:
     - Resolve source section again (line 160) — get post_id and sec_id
     - Call `_persist_section(post_id, sec_id, text, tools)` to save composed text (line 162)
   - Mark flow complete: `flow.status = 'Completed'` (line 163)
   - Return DisplayFrame(origin='compose', thoughts=text) with card block if post_id exists (lines 164–166)

### Staging
No `flow.stage` assignments in compose_policy. Single path: check outline → compose → save.

### Stack-on triggers

**Outline stack-on** (lines 149–156):
- Condition: Source resolved to a post, but post has no section structure (no section_ids)
- Action: `flow_stack.stackon('outline')` + `state.keep_going = True` + return empty DisplayFrame
- Rationale: Cannot compose a section without outline structure; must generate outline first

### Persistence calls

**Delegated to LLM sub-agent via llm_execute:**
- Skill may call `convert_to_prose(content: str)` to draft prose from outline (line 158)
- Skill may call `write_text(...)` to refine prose (line 158)
- Skill may call `revise_content(post_id, sec_id, content)` to save prose to section (line 158)

**Direct tool calls by policy:**
- `tools('read_metadata', {'post_id': post_id})` (line 152) — check if post has sections
- `_resolve_source_ids(flow, state, tools)` (lines 150, 160) — resolves source slot to (post_id, sec_id)
- `_persist_section(post_id, sec_id, text, tools)` (line 162) — saves composed text to section (calls `revise_content` internally, base.py line 123)

**Helpers called:**
- `_read_post_content(post_id, tools)` (line 166) — loads post for card block
- `_build_resolved_context(flow, state, tools)` — prefills post/section context for LLM

### Frame shape

**Success with post_id (lines 164–166):**
- origin: `'compose'`
- thoughts: LLM text summary (or empty per skill file)
- blocks: 1 card block with post content (title, status, all sections)

**Success without post_id (lines 164–166, post_id falsy):**
- origin: `'compose'`
- thoughts: LLM text
- blocks: none

**Stack-on deflection (line 156):**
- origin: not set (empty DisplayFrame)
- blocks: none
- thoughts: none

**Early guard return (line 147):**
- origin: not set (empty DisplayFrame)
- blocks: none
- thoughts: none

### Ambiguity patterns

- **'specific'** (line 146) — source slot not filled. Metadata: `{'missing_slot': 'source'}`. User needs to specify which post and section.

### Eval step + recent track record

**Step 5** (`utils/tests/e2e_agent_evals.py` lines 101–111):
- Utterance: "Convert the entire outline into prose"
- Expected tools: `['convert_to_prose']`
- Rubric:
  - did_action: "Outline bullets converted to prose paragraphs across all sections"
  - did_follow_instructions: "All sections now have prose content, not just bullets"

Policy resolves source (post from state.active_post, no specific section). Checks outline exists (has section_ids from step 2–4). Calls `llm_execute`. Skill iterates all sections, calls `convert_to_prose` for each, then `revise_content` to save. Policy checks for `convert_to_prose` in tool log, then calls `_persist_section` to save final text. Returns card.

---

## B. Skill (prompt) understanding

### Skill contract

From `backend/prompts/skills/compose.md` (lines 1–40):

**Inputs from resolved context:**
- `post_id` (string): The post to compose into
- `post_title` (string): Title of the post
- `section_ids` (list): IDs of existing sections (user can pick which to compose into, or compose all)

**Slots consumed:**
- `source` (required): The post and section to compose (e.g., source.post + source.sec)
- `steps` (elective): Ordered process-level actions to follow ("start with a hook", "end with a takeaway")
- `guidance` (elective): Qualitative writing direction (tone, length, angle, audience)

### Tool plan

**Ordered tools (lines 5–10, exemplified in lines 27–34):**

1. `read_metadata(post_id: str, include_outline: true)` — Get post structure (line 6, implied from context availability)
2. `read_section(post_id: str, sec_id: str)` — Load a section's outline content (outline in bullets) (line 7)
3. `convert_to_prose(content: str)` — Get initial prose draft from bullets (line 8)
4. `write_text(...)` — Refine prose if needed (line 9)
5. `revise_content(post_id: str, sec_id: str, content: str)` — Save final prose to section (line 10)

**Guardrails:**
- Match the tone and style of existing sections in the post (line 11)
- Use resolved post title and surrounding sections for style consistency (line 11)
- Use provided IDs from resolved context rather than extra tool calls (line 16)
- Do NOT call extra tool calls to resolve post IDs; context is pre-resolved (line 16)
- Process one section at a time if composing multiple sections (line 30, "one section at a time")

### Output shape

**Plain text (lines 23–24):**

The composed prose, saved via `revise_content`. Do not wrap in JSON — the prose is the output. Final reply is typically a short summary (lines 36–40):

```
Converted all 4 sections from bullets to prose. Motivation, Process, Breakthrough Ideas, and Takeaways now read as paragraphs.
```

Not the prose itself (that's shown via the card block), but a brief summary of what was done.

### Few-shot coverage

One example provided (lines 26–40):

- User: "Convert the entire outline into prose"
- Correct tool trajectory (one section at a time):
  1. `read_section(post_id=..., sec_id='motivation')` — returns the bullets
  2. `convert_to_prose(content=<bullets>)` — returns prose draft
  3. `revise_content(post_id=..., sec_id='motivation', content=<prose>)` — saves
  4. Repeat for each remaining section (Process, Breakthrough Ideas, Takeaways)
- Correct final reply: Short summary ("Converted all 4 sections from bullets to prose...")

**What's covered:**
- Multiple sections: loop over section_ids, compose each (implied by step 5 expecting "entire outline")
- Tool order: read → convert → revise (or read → convert → write → revise if refinement needed)
- Output: summary text, not the prose itself

**What's missing:**
- How to select which sections to compose (if `steps` or `guidance` specifies only some sections)
- What to do if `convert_to_prose` outputs poor quality prose (retry? call `write_text`?)
- Tone/style matching: skill says to use surrounding sections (line 11), but doesn't show how to access/read them
- Error handling: what if `revise_content` fails?

### Duplication with policy

**Policy handles stack-on and section iteration start; skill handles tool loop:**
- Policy checks outline exists before invoking skill (line 152). Skill assumes outline/sections exist.
- Policy stacks-on outline if missing (lines 153–156). Skill has no fallback.
- Policy calls `_persist_section` at the end (line 162) — but skill also calls `revise_content` inside `llm_execute`. Double persistence?
  - Actually, `_persist_section` (base.py line 123) also calls `revise_content`, so there's potential for duplication if skill also calls it. The policy's `_persist_section` call (line 162) may overwrite the skill's individual revisions, or be redundant if skill has already called `revise_content` for each section.

**Overlap on context:** Policy calls `_build_resolved_context` to prefill post/section info (line 158 via `llm_execute`). Skill also consumes post_id, section_ids from resolved (lines 13–15). Both layers trust resolved context — good alignment.

---

## Known gaps

1. **Double persistence ambiguity:** Policy calls `_persist_section(post_id, sec_id, text, tools)` at line 162, which calls `revise_content` internally. But the skill also calls `revise_content` inside the tool loop (per the few-shot example). If both run, the final text from `_persist_section` (which may be just the last section's text, or an aggregate) could overwrite the skill's section-by-section saves. The contract is unclear.

2. **Section iteration responsibility:** The skill says to compose "one section at a time" (line 30), implying the skill loops over sections and calls `revise_content` for each. But the policy's `_persist_section` (line 162) takes a single sec_id. If the skill composes multiple sections but `_persist_section` is called once, only one section's output persists. The policy and skill don't agree on who loops.

3. **Outlined but not yet sectioned:** The policy checks if post has `section_ids` (line 153). But after step 2–4, the post has an outline (bullets stored) but may not have created section_ids for each heading. The contract between outline data structure and section_ids is unclear.

4. **Tone matching not shown:** Skill says "Match the tone and style of existing sections in the post" (line 11), but doesn't show how. Does the skill `read_section` for all other sections to learn their style? No example shows this. It's aspirational guidance without implementation example.

5. **steps slot not used in example:** The slot schema includes `steps` (elective, "ordered process-level actions"), but the example utterance is generic ("Convert the entire outline into prose"), and no example shows how to use `steps` to selectively compose only some sections or in a specific order.

6. **Skill file title mismatch:** The file is `compose.md` but step 5 description is "Convert the entire outline into prose". The skill handles composing outline → prose, but it could also handle composing free-form text → prose (e.g., rewriting notes into prose). The skill name and examples are narrow.
