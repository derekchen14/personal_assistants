# Policy Inventory — inspect

**Parent intent:** Research
**DAX:** {1BD}
**Eval step(s):** 10

## A. Policy (code) understanding

### Flow class
From `backend/components/flow_stack/flows.py` lines 44–56:
- `entity_slot`: `source` (SourceSlot, required)
- `dax`: `{1BD}`
- `goal`: "report numeric content metrics; word count, section count, reading time, image count, post size (MB); optionally filtered to a single metric"
- Slot schema:
  - `source` (SourceSlot, priority='required') — the post to inspect
  - `aspect` (CategorySlot, priority='optional') — single metric filter: word_count, num_sections, time_to_read, image_count, num_links, post_size
  - `threshold` (ScoreSlot, priority='optional') — reference value for comparison
- Tools: `['read_metadata', 'read_section', 'inspect_post', 'check_readability', 'check_links']`

### Guard clauses
From `backend/modules/policies/research.py` lines 123–135 (`inspect_policy`):
- **Line 124–127:** Check if `source` slot is filled. If not, declare 'specific' ambiguity with missing_slot metadata and return empty frame.
- **Line 129:** If filled, delegate to `llm_execute` (agentic tool-use loop).
- **Line 130:** Extract `inspect_post` tool result.
- **Line 133:** Call helper `_format_inspect_metrics` to format results.
- **Line 135:** Return DisplayFrame with `origin='inspect'` and formatted metrics as `thoughts`.
- **Line 59:** Mark `flow.status = 'Completed'` after policy completes.

### Staging
No explicit `flow.stage` assignments; policy runs single-pass.

### Stack-on triggers
None. Inspect does not push prerequisite flows.

### Persistence calls
Policy delegates all tool calls to `llm_execute` (agentic loop). The LLM calls:
- `inspect_post` (always, to gather metrics)
- `check_readability` (optional, if user asks about readability)
- `check_links` (optional, if user asks about links/images)
- `read_section` (optional, only if LLM needs raw content)

**Key detail:** `_format_inspect_metrics` (lines 138–156) is a post-processing helper that extracts structured fields from the tool result dict and formats them into readable text. This runs deterministically after the LLM step, not as part of the agentic loop.

### Frame shape
- **Origin:** `'inspect'`
- **Blocks:** None — metrics are returned as `thoughts` text, not as a card/list block.
- **Thoughts:** Either formatted metrics from `_format_inspect_metrics` or fallback to raw LLM text if metrics extraction fails.

### Ambiguity patterns
- **Line 126:** Declare 'specific' if `source` slot missing, with `metadata={'missing_slot': 'source'}`.

### Eval step + recent track record
**Step 10** (from `utils/tests/e2e_agent_evals.py` lines 160–168):
- Utterance: `"What are the metrics on the multi-modal models post?"`
- Expected tools: `['inspect_post']`
- Expected block type: Not specified (defaults to no explicit block).
- Rubric:
  - `did_action`: "Reports word count, section count, read time"
  - `did_follow_instructions`: "Metrics are for the multi-modal models post"

---

## B. Skill (prompt) understanding

### Skill contract
From `backend/prompts/skills/inspect.md` lines 1–62:
- **Inputs:** `post_id` and section IDs from resolved context; optional `aspect` slot to filter to a single metric.
- **Assumption:** Policy has already verified `source` is filled and resolved the post_id deterministically. Skill should NOT re-ground or call `read_metadata` for post lookup.

### Tool plan
**Ordered list with guardrails:**
1. **`inspect_post(post_id=<resolved_id>)`** (required)
   - Compute word count, read time, section count, readability.
   - Guardrail: Always call this as the primary metric source.
2. **`check_readability`** (optional, conditional)
   - Only if user explicitly asked about readability.
   - Guardrail: Do not call if `aspect` is filled with a different metric.
3. **`check_links`** (optional, conditional)
   - Only if user asked about links or images.
4. **`read_section`** (discouraged, fall-through only)
   - Only if LLM needs raw content to answer a complex question about section structure.
   - Guardrail: `Resolved entities` gives you post_id — use it instead of extra `read_metadata` calls (line 61).

### Output shape
**JSON with structured metrics** (lines 13–27):
```json
{
  "post_id": "...",
  "title": "...",
  "metrics": {
    "word_count": 1234,
    "section_count": 5,
    "read_time_minutes": 6,
    "image_count": 2,
    "link_count": 8
  },
  "notes": "<one-sentence summary>"
}
```
- If `aspect` is filled, include only that metric key under `metrics`.
- **Key distinction:** Output is **JSON, not Markdown or prose** — this is a data-focused skill expecting structured output.

### Few-shot coverage
Lines 34–52 illustrate:
- Single call to `inspect_post`.
- JSON output with all five metrics.
- One-sentence summary note.
- **What's missing:**
  - Edge case: aspect='word_count' only (subset output).
  - Edge case: no results or empty post.
  - Fallback behavior if `inspect_post` fails.

### Duplication with policy
- **None significant.** Policy does no metric computation; skill is fully responsible for tool calls and formatting.
- Helper `_format_inspect_metrics` (in policy) is a post-hoc formatting step, not duplication with the skill.

---

## Known gaps

**Striking gap 1: Output shape mismatch**
The skill prompt specifies **JSON output** (lines 13–27), but the policy returns raw LLM text as `thoughts` to the frame. The eval rubric (step 10) does not check for JSON structure — it only checks that metrics are reported. This means the skill's JSON contract is not enforced; the policy happily accepts plain text. **Consequence:** The downstream informed-polish step (step 13) cannot reliably parse inspect's output if the LLM ignores the JSON instruction.

**Striking gap 2: No card block** 
Unlike `find` and `audit`, which return a card block with post metadata, `inspect` returns only `thoughts` text with no block. This makes the output less usable for downstream steps that might want to reference the post. **Consequence:** Downstream steps cannot click to view the full post in context; they only see the metrics text.

**Striking gap 3: Aspect filter edge case**
The policy does not pass the `aspect` slot value to the skill context. If `aspect='word_count'`, the skill must infer from the LLM turn that it should filter output to a single metric. **Consequence:** The skill relies on the LLM to read the slot from conversation history, risking misalignment if the LLM misses it.

