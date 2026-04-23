# Policy Inventory — outline

**Parent intent:** Draft
**DAX:** {002}
**Eval step(s):** 2 (propose via 02a), 3 (direct via 02b); steps 2, 02a, 02b

## A. Policy (code) understanding

### Flow class
From `backend/components/flow_stack/flows.py` (lines 128–141):
- entity_slot: not set (inherits parent default)
- goal: generate an outline including section headings, key bullet points, estimated word counts, and suggested reading order
- tools: `['find_posts', 'brainstorm_ideas', 'generate_outline']`
- slot schema:
  - `source` (SourceSlot(1), required)
  - `sections` (ChecklistSlot, elective)
  - `topic` (ExactSlot, elective)
  - `depth` (LevelSlot, optional, threshold=1)
  - `proposals` (ProposalSlot, optional) — used internally, filled by policy during propose → direct flow

### Guard clauses
From `backend/modules/policies/draft.py:outline_policy` (lines 31–78):

1. **Guard: source slot** (lines 32–34). If `source` slot not filled:
   - declare('partial') → return DisplayFrame()

2. **Branch A: Direct mode** (lines 36–51). If `sections` slot is filled:
   - Set `flow.stage = 'direct'` (line 37)
   - Get `post_id` from `state.active_post` (line 38)
   - Call `llm_execute(flow, state, context, tools)` to refine sections (line 40)
   - Check if `generate_outline` tool was called and succeeded (lines 41–42)
   - If LLM failed or tool not called: return DisplayFrame(origin='outline', metadata={'error': 'LLM failed to generate outline'}) (lines 44–45)
   - Else (success):
     - Mark each section in `flow.slots['sections'].steps` as complete (lines 47–48)
     - Set `flow.status = 'Completed'` (line 49)
     - Return DisplayFrame(origin='outline', thoughts=text) with card block of post content (lines 50–51)

3. **Branch B: Propose mode via topic** (lines 53–62). If `topic` slot is filled AND sections not filled:
   - Check if `proposals` slot already filled (lines 56): — user already chose an option in a sub-turn
     - Extract chosen outline from proposals (line 57)
     - Add each section to `flow.slots['sections']` (lines 58–59)
     - Recurse to outline_policy to execute direct mode (line 60)
   - Else:
     - Call `_propose_outline` helper (line 62) to generate 3 options without saving

4. **Branch C: Topic extraction** (lines 64–77). If topic NOT filled:
   - Compile conversation history (line 65)
   - Call LLM to extract topic from conversation (lines 66–68)
   - If topic extracted successfully: set `flow.stage = 'propose'` and call `_propose_outline` (lines 70–72)
   - Else: set `flow.stage = 'error'`, declare('specific', metadata={'missing_slot': 'topic'}) → return DisplayFrame('error') (lines 74–76)

### _propose_outline helper (lines 80–96)
Pre-execution checks and frame composition for propose mode:

1. Get `post_id` from `state.active_post` (line 81)
2. Call `llm_execute` (line 82) — skill must output 3 options as markdown text
3. Initialize DisplayFrame(origin='outline') (line 83)
4. Check if LLM ignored propose-mode rules and called `generate_outline` (line 86):
   - If it did: treat as direct mode, set `flow.stage = 'direct'` + `flow.status = 'Completed'`, add card block (lines 87–90)
   - Else (correct propose behavior): parse LLM markdown output as candidate options (line 92), store in `flow.slots['proposals'].options` (line 93), add selection block (lines 94–95)
5. Return frame (line 96)

### Staging

Two stages used:

- **'propose'** (lines 37, 54, 71) — LLM generates 3 outline options; policy does NOT call `generate_outline`; UI renders selection block for user to pick.
- **'direct'** (line 37, 87) — User provided `sections` slot directly OR chose an option from propose; policy calls `generate_outline` and marks flow complete.
- **'error'** (line 74) — Topic could not be extracted from conversation.

**Recursion invariant (AD-3):** After sections are filled from proposals, the
recursive call takes the sections-filled branch, which does NOT self-recurse.
Max recursion depth = 1. Outline may NOT `stackon('outline')`.

### Stack-on triggers

None. Outline does not stack on other flows as a prerequisite.

### Persistence calls

**Delegated to LLM sub-agent via llm_execute:**
- In direct mode: skill may call `generate_outline(post_id, outline_content)` (line 41)
- In propose mode: skill MUST NOT call `generate_outline` (skill constraint, line 45 in outline.md)

**Helper functions called by policy:**
- `_read_post_content(post_id, tools)` (line 51) — loads post content for card block
- (Indirectly via skill resolution) `_build_resolved_context(flow, state, tools)` provides post_id + section_ids to the skill

### Frame shape

**Direct mode success (lines 50–51):**
- origin: `'outline'`
- thoughts: LLM text output (outline explanation or summary)
- blocks: 1 card block with post content (title, status, all section prose)

**Direct mode error (lines 44–45):**
- origin: `'outline'`
- metadata: `{'error': 'LLM failed to generate outline'}`
- blocks: none
- thoughts: none

**Propose mode success (lines 94–95):**
- origin: `'outline'`
- blocks: 1 selection block with candidates (list of 3 option outlines)
- thoughts: none
- metadata: none

**Propose mode deflection (lines 87–90):** If LLM called `generate_outline` anyway:
- origin: `'outline'`
- blocks: 1 card block with post content (as if direct mode)
- thoughts: none

**Error (line 76):**
- origin: `'error'`
- blocks: none

**Early guard return (line 34):**
- origin: not set (empty DisplayFrame)
- blocks: none

### Ambiguity patterns

- **'partial'** (line 33) — source slot not filled. No metadata. User needs to specify which post.
- **'specific'** (line 75) — topic could not be extracted from conversation. Metadata: `{'missing_slot': 'topic'}`.

### Eval step + recent track record

**Step 2 (outline direct mode)** (`utils/tests/e2e_agent_evals.py` lines 51–68):
- Utterance: "Make an outline with 4 sections: Motivation, Process, Ideas, and Takeaways. Under Motivation, add bullets about..."
- Expected tools: `['generate_outline']`
- Expected block type: `'card'`
- Rubric:
  - did_action: "4 sections saved to disk with bullet points under Motivation"
  - did_follow_instructions: "Sections are Motivation, Process, Ideas, Takeaways in that order"

In step 2, the `sections` slot is pre-filled via NLU (user specified section names), so the policy enters direct mode immediately. LLM executes, calls `generate_outline`, policy marks complete and returns card.

**Substep 02a (outline propose mode)** (`OUTLINE_SUBSTEPS` lines 223–239):
- Utterance: "Make an outline — propose a few options I can pick from"
- Expected tools: `['read_metadata']`
- Expected block type: `'selection'`
- Rubric:
  - did_action: "Generated multiple outline options without saving to disk"
  - did_follow_instructions: "Offered options for the user to pick between"

Policy enters propose mode (topic filled but sections not). LLM generates 3 markdown options. Policy parses them, stores in proposals, returns selection block.

**Substep 02b (outline selection follow-up)** (`OUTLINE_SUBSTEPS` lines 241–251):
- Utterance: "Let's go with Option 2"
- Expected tools: `['generate_outline']`
- Expected block type: `'card'`
- Rubric:
  - did_action: "Persisted the selected option's sections to disk"
  - did_follow_instructions: "Saved Option 2's sections, not Option 1 or Option 3"

User picks an option (NLU fills `proposals` slot with chosen candidate). Policy recurses into outline_policy, now with `proposals` filled. Executes direct mode, calls `generate_outline`, returns card.

---

## A'. Usage contexts

### Propose mode (steps 02a, topic filled, sections empty)

**Code path:** Lines 53–62 → `_propose_outline` (lines 80–96)

**Conditions:** `flow.slots['sections'].check_if_filled()` returns false AND `flow.slots['topic'].check_if_filled()` returns true

**What distinguishes it:**
- Policy does NOT call any tool directly; delegates to LLM via `llm_execute`
- Skill must output exactly 3 outline options as markdown text (no JSON, no tool calls)
- UI renders a `selection` block listing the 3 options for the user to click
- Policy stores parsed options in `flow.slots['proposals'].options` for the next turn
- Flow does NOT move to 'Completed'; user must pick first

**LLM constraints (skill file lines 39–50):**
- May call `find_posts` AT MOST ONCE to research existing posts on topic
- MUST NOT call `generate_outline` (user hasn't chosen yet)
- MUST NOT call `read_metadata` (post context pre-resolved)
- Final output MUST be text (three markdown options), not tool calls

**Frame on success:** `selection` block with candidates

### Direct mode (steps 02b, sections filled OR proposals filled)

**Code path:** Lines 36–51

**Conditions:** `flow.slots['sections'].check_if_filled()` returns true OR (topic filled AND `proposals` filled, then recurse)

**What distinguishes it:**
- Policy MUST call `generate_outline` to save the outline to disk
- Skill receives resolved post context (post_id, section_ids) via `_build_resolved_context`
- User has already chosen sections (either directly in step 2, or picked an option in 02b)
- Flow moves to 'Completed' after successful `generate_outline` call
- Policy returns card block showing the final saved post

**LLM constraints (skill file lines 5–11):**
- MUST call `generate_outline` exactly once with the markdown outline
- May call `find_posts` to research existing posts
- May call `read_metadata` (though context is pre-resolved)
- Output MUST be saved via `generate_outline`; final text is typically a summary (or empty per skill line 63)

**Frame on success:** `card` block with full post content

---

## B. Skill (prompt) understanding

### Skill contract

From `backend/prompts/skills/outline.md` (lines 1–64):

**Inputs from resolved context:**
- `post_id` (string): The post to outline
- `post_title` (string): Title of the post
- `section_ids` (list): Existing section identifiers (may be empty for new post)

**Slots consumed:**
- `topic` (elective): The blog post topic
- `sections` (elective): User-provided section headings
- `depth` (optional): Number of heading levels to generate
- `proposals` (optional): Internal-use only; filled by policy during propose→direct transition

### Tool plan

**Propose mode tools (lines 41–49):**

1. `find_posts(query: str)` — AT MOST ONCE. May call once to scan for existing posts on topic to vary angles. Line 44.
2. MUST NOT call `generate_outline` (line 45)
3. MUST NOT call `read_metadata` (line 46)

**Direct mode tools (lines 5–11):**

1. `generate_outline(post_id: str, outline_content: str)` — MUST call once to save (line 11)
2. `find_posts(query: str)` — May call to research (implied in direct, explicit in propose)
3. (Implied) `read_section(post_id, sec_id)` for reading existing section content

**Guardrails per tool:**
- `generate_outline` only in direct mode; save in markdown `## Section Title` format with bullet points (line 25)
- `find_posts` at most once in propose; do not call repeatedly (line 44)
- Do not call tools in propose beyond `find_posts`; stop and emit options as text instead (line 49)
- Use resolved post context rather than making extra tool calls (line 46)

### Output shape

**Propose mode final output (lines 15–37):**

Markdown text with three options, strict format:

```
### Option 1
## First section title
One or two sentences describing what this section covers.

## Second section title
...

### Option 2
...

### Option 3
...
```

Rules (lines 39–47):
- Each option uses `### Option N` header (N = 1, 2, 3), no trailing text
- Each section uses `## <title>` header followed by 1-2 sentence description
- Each option has 4-7 sections
- Vary the angles across options (listicle vs. narrative vs. how-to vs. teardown)
- NO trailing commentary after Option 3

**Direct mode final output (lines 12–13):**

Markdown text: the refined outline saved via `generate_outline`, formatted as `## Heading` per section with `- bullet` lines underneath.

### Few-shot coverage

No explicit few-shot examples in outline.md, but structure is fully specified in the Behavior section.

**What's covered:**
- Direct mode: Section titles as headings, bullet points underneath (lines 8–11)
- Propose mode: Three distinct outline angles with different structures (lines 15–37)
- Vary angles: listicle, narrative, how-to, teardown patterns implied (line 44)
- Tool constraints: at-most-once `find_posts` in propose (line 44)

**What's missing:**
- Example of three real outline options for a concrete topic (no worked example)
- How to handle `depth` parameter (slot is defined but not used in instructions)
- What "one or two sentences describing what section covers" should include — level of detail, formality, length
- How to react if `find_posts` returns nothing (fallback to generic angles?)
- Error handling if `generate_outline` fails in direct mode

### Duplication with policy

**Policy orchestrates; skill executes:**
- Policy decides propose vs. direct (lines 31–78 in draft.py). Skill does not.
- Policy handles recursion when user picks option (lines 56–60). Skill is stateless.
- Policy checks for LLM's rule-breaking (`generate_outline` called in propose, line 86). Skill should not, but policy has a fallback.
- Policy marks flow.stage, flow.status. Skill outputs only text/frames.

**No duplication in logic:** Policy and skill do not re-do each other's work. Policy is orchestration; skill is content generation.

---

## Known gaps

1. **Propose-mode rule enforcement via detection:** Policy checks if LLM violated propose-mode rules (called `generate_outline` when it shouldn't, line 86) and treats it as direct mode anyway. Graceful degradation, but the skill file's "MUST NOT" constraints (line 45) rely on LLM compliance — there is no deterministic enforcement in code.

2. **Depth parameter unused:** The slot schema includes `depth` (line 54), but the skill instructions do not mention how to use it. If user specifies depth=2, the skill has no guidance on what that means (number of `#` levels? number of sub-sections?).

3. **Selection block parsing implicit:** The policy (line 92) calls `apply_guardrails` to parse LLM markdown output as candidates, but the guardrails format and error handling are not documented in the inventory. What happens if the LLM outputs 2 options instead of 3? Does parsing fail silently?

4. **Recursion risk:** When user picks an option (lines 56–60), the policy recurses by calling outline_policy again. If there are bugs in the recursion (e.g., infinite loop if proposals stays filled), they are hard to trace.

5. **_propose_outline name mismatch:** Helper method is `_propose_outline` but it's also called when user picks an option and proposals is already filled. The name is misleading — it should be `_propose_or_execute_outline` or the logic should be split.

6. **Missing context in propose mode:** The skill says "The post title has been resolved for you within Resolved entities" (line 52), but in propose mode (before user has chosen sections), the post may not yet exist. The resolved context contract is unclear for propose mode on a brand-new post.
