# Policy Inventory — find

**Parent intent:** Research
**DAX:** {001}
**Eval step(s):** 13

## A. Policy (code) understanding

### Flow class
From `backend/components/flow_stack/flows.py` lines 58–70:
- `entity_slot`: `query` (ExactSlot, required)
- `dax`: `{001}`
- `goal`: "search previous posts by keyword or topic; returns matching titles, excerpts, and publication dates sorted by relevance"
- Slot schema:
  - `query` (ExactSlot, priority='required') — the search keyword/phrase
  - `count` (LevelSlot, priority='optional') — cap on result count
- Tools: `['find_posts']` (single tool)

### Guard clauses
From `backend/modules/policies/research.py` lines 158–222 (`find_policy`):
- **Line 159–160:** Extract `query` slot value. If not filled, default to empty string (not an error).
- **Line 162–168:** Extract optional `count` slot and convert to integer limit.
- **Line 170–183:** Main search loop:
  - **Line 173:** Call `_expand_query` to generate semantically similar search terms (LLM-based expansion, lines 224–239).
  - **Line 174–178:** For each expanded term, call `find_posts` and deduplicate by post_id.
  - **Line 182–183:** Apply limit if count is set.
- **Line 185–191:** Build summary text with hit count and first 10 title snippets.
- **Line 195:** Mark `flow.status = 'Completed'`.
- **Line 198–212:** Conditional frame-building:
  - If 0 results: return DisplayFrame with `thoughts=text` (no block).
  - If 1 result: fetch full metadata and return card block with post content.
  - If 2+ results: return list block with optional expanded_ids if n <= 8 (lines 219–220).

### Staging
No explicit `flow.stage` assignments; policy runs single-pass.

### Stack-on triggers
None. Find does not push prerequisite flows.

### Persistence calls
Policy directly calls:
- `find_posts` (lines 174, 180) — via tool dispatcher, not llm_execute.
- `read_metadata` (line 203) — optional, only if exactly 1 result found.

**Key detail:** Unlike inspect and audit, find does NOT use `llm_execute`. It is deterministic, calling only domain tools directly.

### Frame shape
- **Origin:** `'find'`
- **Blocks:** 
  - If 0 results: None.
  - If 1 result: card block with `{post_id, title, status, content}` (line 206–212).
  - If 2+ results: list block with `{items, page, expanded_ids}` (line 218–221).
- **Thoughts:** Always set to `text` (the summary). For multi-result case, thoughts + list block together form the response.

### Ambiguity patterns
None. Find does not declare ambiguity; it accepts an empty query and returns all posts (line 180).

### Eval step + recent track record
**Step 13** (from `utils/tests/e2e_agent_evals.py` lines 193–201):
- Utterance: `"Search for posts about data augmentation"`
- Expected tools: `['find_posts']`
- Expected block type: Not specified.
- Rubric:
  - `did_action`: "Returns search results"
  - `did_follow_instructions`: "Results relate to data augmentation"

---

## B. Skill (prompt) understanding

### Skill contract
From `backend/prompts/skills/find.md` lines 1–53:
- **Inputs:** `query` from the user (required, resolved by policy); optional `count` to limit results.
- **Assumption:** Policy has already called `find_posts` and returned results. Skill is **NOT responsible for calling find_posts itself** — it receives the results via frame context and formats them.
- **Critical distinction:** This is **not an LLM-only skill** — the policy does the tool calling, not the skill.

### Tool plan
**Ordered list with guardrails:**
1. **`find_posts(query=<query>)`** (required, called by POLICY, not skill)
   - Policy expands query semantically (line 224–239 in policy).
   - Skill should assume results are pre-fetched.
2. **Deduplication logic** (deterministic, in policy)
   - Policy dedupes by post_id across multiple expanded terms.
   - Skill does not repeat this work.

**Skill's role:** Format and contextualize results, not fetch them.

### Output shape
**JSON with result metadata** (lines 12–24):
```json
{
  "query": "...",
  "count": 3,
  "results": [
    {"post_id": "...", "title": "...", "status": "draft|published|note", "relevance": "<one-line note>"}
  ]
}
```
- If no results: `results: []` with a `notes` field explaining no matches.
- **Key distinction:** Output is **JSON with relevance notes per item**, not a simple list.

### Few-shot coverage
Lines 28–44 illustrate:
- Query expansion (2 expanded terms yielding 3 unique results).
- JSON output with relevance notes for each post.
- Status field populated (draft, published).
- **What's missing:**
  - Edge case: empty query (all posts).
  - Behavior when count limit is hit.
  - How to handle mixed statuses (drafts + published in same result set).

### Duplication with policy
- **Moderate duplication:** Policy does query expansion via `_expand_query` (lines 224–239). The skill prompt also mentions expanding query with synonyms (lines 6–7). However:
  - Policy expansion uses LLM (`self.engineer(prompt, ...)`).
  - Skill is expected to expand via its own reasoning if needed.
  - **This is a gap:** The policy already expanded; the skill shouldn't re-expand and re-call find_posts. The skill should just format the policy's results.

---

## Known gaps

**Striking gap 1: Skill-policy contract mismatch**
The skill prompt says "Expand the user's query with synonyms... Run at most 3 queries" (lines 6–7), but the **policy already does this expansion** (lines 224–239). The skill is supposed to receive pre-fetched results, not re-fetch them. This creates confusion: does the skill call find_posts or not? **Consequence:** The skill might redundantly re-expand and re-query, wasting compute and potentially returning duplicates the policy didn't deduplicate.

**Striking gap 2: List block metadata**
When find returns a list block for 2+ results, the block contains only `items`, `page`, and `expanded_ids` (line 221). But the items themselves carry minimal metadata from the `find_posts` response (post_id, title, preview_snippet). Downstream audit step (step 12) will need to compare style against these posts, but the list block doesn't include a `status` field or full content preview. **Consequence:** Downstream audit must re-fetch post details, defeating the "carry results forward" intent.

**Striking gap 3: Query expansion + LLM overhead**
The `_expand_query` helper (lines 224–239) calls `self.engineer(prompt, ...)` for every find query. This LLM call happens inside the policy, not the skill. For a typical find invocation (e.g., "search for data augmentation"), this adds one extra LLM call before any tool calls. **Consequence:** Slower initial response; the query expansion could be cached or skipped for single-word queries.

