# Policy Inventory — create

**Parent intent:** Draft
**DAX:** {05A}
**Eval step(s):** 1

## A. Policy (code) understanding

### Flow class
From `backend/components/flow_stack/flows.py` (lines 114–126):
- entity_slot: `title`
- goal: start a new post from scratch; initializes a post record with title, type, and empty sections
- tools: `['create_post']`
- slot schema:
  - `title` (ExactSlot, required)
  - `type` (CategorySlot(['draft', 'note']), required)
  - `topic` (ExactSlot, optional)

### Guard clauses
From `backend/modules/policies/draft.py:create_policy` (lines 183–221):

1. **Guard: slot completeness** (lines 184–191). If `flow.is_filled()` returns false:
   - If `title` slot not filled → declare('specific', metadata={'missing_slot': 'title'}) → return DisplayFrame('error')
   - Else if `type` slot not filled → declare('specific', metadata={'missing_slot': 'type'}) → return DisplayFrame('error')
   - Else → declare('partial') → return DisplayFrame('error')
   
2. **Main path: direct tool call** (lines 193–221). If all required slots filled:
   - Extract slot values dict (title, type, optionally topic) (lines 193–196)
   - Call `tools('create_post', create_params)` directly — **no LLM** (line 197)
   - If result['_success'] (line 199):
     - Set `new_id = result['post_id']`
     - Sync state: `state.active_post = new_id` (line 201)
     - Mark flow complete: `flow.status = 'Completed'` (line 202)
     - Return DisplayFrame(origin='create') with card block containing post_id, title, status (lines 203–205)
   - Else if result['_error'] == 'duplicate' (line 207):
     - Declare confirmation ambiguity: `declare('confirmation', metadata={'reason': 'duplicate_file'})` (line 208)
     - Return DisplayFrame with confirmation block asking user to confirm/cancel (lines 209–217)
   - Else (other tool error) (line 218):
     - Return DisplayFrame(origin='create', thoughts=error_message) (lines 219–220)

### Staging
No `flow.stage` assignments in create_policy. Flow is single-stage: slots → direct tool call → done.

### Stack-on triggers
None. Create does not stack on other flows.

### Persistence calls
**Direct tool call (no LLM delegation):**
- `tools('create_post', {'title': str, 'type': str, [optional 'topic': str]})` — line 197

No delegation to llm_execute. The policy owns the create_post call entirely.

### Frame shape

**Success path (lines 203–205):**
- origin: `'create'`
- blocks: 1 card block with shape `{'post_id': str, 'title': str, 'status': str}`
- thoughts: none (frame.thoughts not set)

**Duplicate confirmation path (lines 209–217):**
- origin: `'create'`
- metadata: `{'duplicate_title': str}`
- blocks: 1 confirmation block with shape `{'prompt': str, 'confirm_label': str, 'cancel_label': str}`
- thoughts: none

**Error path (lines 219–220):**
- origin: `'create'`
- metadata: none
- blocks: none
- thoughts: error message string

**Early return (error, line 191):**
- origin: `'error'`
- blocks: none
- thoughts: none

### Ambiguity patterns

- **'specific'** (lines 186–188) — missing required slot (title or type). Metadata: `{'missing_slot': 'title'|'type'}`.
- **'partial'** (line 190) — missing optional topic (no metadata). Declared when title+type present but topic not filled.
- **'confirmation'** (line 208) — title already exists (duplicate file). Metadata: `{'reason': 'duplicate_file'}`. User chooses confirm or cancel.

### Eval step + recent track record

**Step 1** (`utils/tests/e2e_agent_evals.py` lines 40–50):
- Utterance: "Create a new post about Using Multi-modal Models to Improve AI Agents"
- Expected tools: `['create_post']`
- Rubric:
  - did_action: "Post created with title containing multi-modal models / AI agents"
  - did_follow_instructions: "Post type is draft, title matches request"

NLU slot-fills title and type (NLU responsibility, not policy). Policy then validates both are present and calls `create_post` once. No LLM involved in the policy layer.

---

## B. Skill (prompt) understanding

### Skill contract

From `backend/prompts/skills/create.md` (lines 1–29):

**Inputs from resolved context:**
- Not specified in the skill file. Policy does NOT call `llm_execute` for create — resolved context is unused.

**Slots consumed:**
- `title` (required): post title
- `type` (required): "draft" or "note"
- `topic` (optional): topic description for initial outline

### Tool plan

**Ordered tools the skill may call:**

1. `create_post(title, type)` → returns `{post_id, ...}`. Single call, mandatory once.

**Guardrails:**
- Title should be in Proper Case (not lowercase, not verbatim user input) — line 7.
- Type must respect user intent — if user asked for note, pass "note", not default to "draft" — line 9.
- Do NOT invent a topic if not provided — only generate initial outline if topic slot is actually filled — line 10.

**Per-tool observations:**
- `create_post` is called exactly once per successful flow (no retries, no conditionals on create result).
- No other tools are mentioned in the skill file; skill does not call `read_metadata`, `find_posts`, etc.

### Output shape

**JSON final output** (lines 20–29):

```json
{
  "post_id": "...",
  "title": "...",
  "type": "draft" | "note",
  "next_steps": ["outline", "brainstorm", "compose"]
}
```

Not free-text; structured JSON with required fields. The skill returns this as the final turn text.

### Few-shot coverage

Two examples provided (lines 31–61):

1. Synthetic Data Generation example — basic case: title + type (draft) → `create_post` → JSON response with next_steps.
2. Birds of the Amazon example — same pattern: title + type (draft) → `create_post` → JSON response.

**What's covered:**
- Happy path: title + type → single tool call → JSON output.
- Type variation: draft vs. note (both examples use draft, but type slot is shown as variable).

**What's missing:**
- How to handle title already in Proper Case vs. user's lowercase/mixed input (implied but not exemplified).
- Topic provided case (skill says generate initial outline if topic is present, but no example shows `create_post` with topic parameter or outline generation).
- Error case: what if `create_post` returns `_success: false` or `_error: 'duplicate'`? (Skill file silent; policy handles in draft.py:207–217).

### Duplication with policy

**Policy re-does work the skill describes:**

The policy (draft.py:183–221) owns the entire create_post call and slot validation. The skill file (create.md) documents the same behavior:
- Slot requirements (title, type) — both layers describe them.
- Proper Case formatting of title — skill file line 7 describes it, but the policy does NOT enforce it; the LLM never runs, so no enforcement.
- Type slot respect — skill line 9 says "do NOT default to draft if user asked for note", policy line 194 passes `'type': slots['type']` without transformation.

**Grounding duplication:** The policy validates slots and calls `create_post`. The skill file redundantly documents what the policy already ensures, since the skill is never actually invoked (no llm_execute call). The skill is documentation-only for the create flow.

---

## Known gaps

1. **Skill execution mismatch:** The skill file describes LLM behavior (title formatting, initial outline generation), but the policy never calls `llm_execute`. The skill is dead code or purely aspirational documentation. If create is ever meant to run the skill (for future enhancement to generate title suggestions, for example), the policy will need to be rewritten to call `llm_execute` instead of direct tool call.

2. **Topic handling undefined:** The slot schema includes `topic` (optional), and the skill file says "If topic is provided, generate a brief initial outline" (line 10), but the policy passes topic to `create_post` (line 196) with no follow-up to actually generate that outline. The `create_post` tool signature doesn't mention outline generation, so the contract is unclear.

3. **Duplicate title ambiguity relies on tool error:** The policy catches `'_error': 'duplicate'` from the tool result (line 207), but the skill file never mentions how to handle this. If the skill were invoked, it would have no guidance on whether to retry, propose an alternative title, or escalate.

4. **Template output mismatch:** `modules/templates/draft.py` line 6 renders create as `"I've created a new draft called '{title}'"`, but the skill file outputs JSON. The template and skill are not aligned on output format.

5. **No validation of type enum:** The slot schema restricts type to `['draft', 'note']`, but the policy does not validate against this list before calling `create_post`. If NLU filled type with an invalid value, the policy would pass it through.
