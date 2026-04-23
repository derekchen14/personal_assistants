# Policy Inventory — audit

**Parent intent:** Revise
**DAX:** {13A}
**Eval step(s):** 11

## A. Policy (code) understanding

### Flow class
From `backend/components/flow_stack/flows.py` lines 249–260:
- `entity_slot`: `source` (SourceSlot, required, scope='post')
- `dax`: `{13A}`
- `goal`: "check that the post is written in the user's voice rather than sounding like AI; compares voice, terminology, formatting conventions, and stylistic patterns against previous posts"
- Slot schema:
  - `source` (SourceSlot, priority='required', entity_part='post') — the post to audit
  - `reference_count` (LevelSlot, priority='optional') — number of reference posts to compare against
  - `threshold` (ProbabilitySlot, priority='optional') — percentage of sections affected that triggers confirmation
- Tools: `['find_posts', 'compare_style', 'editor_review', 'inspect_post']`

### Guard clauses
From `backend/modules/policies/revise.py` lines 92–128 (`audit_policy`):
- **Line 93–95:** Call `_require_source` helper to check if `source` slot is filled. If missing, declare 'specific' ambiguity and return empty frame.
- **Line 98–99:** Default `reference_count` to 5 if not filled.
- **Line 102–103:** Extract `threshold` slot; default to 0.2 if not filled.
- **Line 105:** Call `llm_execute` to run the agentic tool-use loop.
- **Line 106:** Extract `audit_post` tool result (though tool name is not listed in flow class tools).
- **Line 109:** Call `_format_audit_report` to format results into structured text (lines 131–153).
- **Line 111–121:** Threshold check: compute percentage of sections affected. If exceeds threshold:
  - **Line 116–120:** Declare 'confirmation' ambiguity with metadata (pct, threshold).
  - **Line 121:** Return empty frame (no card, await user confirmation).
- **Line 123:** If threshold not exceeded, mark `flow.status = 'Completed'`.
- **Line 124–128:** Build frame with card block containing post content (line 127).

### Staging
No explicit `flow.stage` assignments; policy runs single-pass (but with conditional completion based on threshold).

### Stack-on triggers
None. Audit does not push prerequisite flows; it escalates to the user via confirmation ambiguity if threshold is exceeded.

### Persistence calls
Policy delegates tool calls to `llm_execute` (agentic loop). The LLM calls:
- `find_posts` (to locate reference posts)
- `compare_style` (to compare the target post against references)
- `editor_review` (to check against editorial style guide)
- `inspect_post` (to get structural metrics)

**Key detail:** Unlike find, audit uses `llm_execute`, so the LLM orchestrates the tool calls, not the policy.

### Frame shape
- **Origin:** `'audit'`
- **Blocks:** 
  - If threshold exceeded: None (confirmation ambiguity takes precedence; line 121).
  - If threshold not exceeded: card block with `{post_id, title, content, ...}` from `_read_post_content` (lines 124–128).
- **Thoughts:** Either formatted audit report from `_format_audit_report` or fallback to raw LLM text if no structured results (line 125).

### Ambiguity patterns
- **Line 116–120:** Declare 'confirmation' ambiguity if sections_affected / total_sections > threshold. Metadata includes:
  - `reason: 'audit_threshold_exceeded'`
  - `pct: <percentage>`
  - `threshold: <threshold>`

### Eval step + recent track record
**Step 11** (from `utils/tests/e2e_agent_evals.py` lines 171–179):
- Utterance: `"Check if the multi-modal models post matches my usual writing style"`
- Expected tools: `['find_posts', 'compare_style']`
- Expected block type: Not specified.
- Rubric:
  - `did_action`: "Produces a style consistency report"
  - `did_follow_instructions`: "Compares against existing posts"

**Known quality gap** (from `AGENTS.md` lines 133–134):
- "Step 11 `audit` (L3): response surfaces post content instead of a structured style report; audit policy's card choice."
- This indicates the current implementation returns the full post content as a card block, rather than a structured style report. The policy's choice to add a card block (lines 126–127) is being called out as problematic.

---

## B. Skill (prompt) understanding

### Skill contract
From `backend/prompts/skills/audit.md` lines 1–70:
- **Inputs:** `post_id` from resolved context; optional `reference_count` (default 5) and `threshold` (default 0.2).
- **Assumption:** Policy has already verified `source` is filled and will handle threshold escalation. Skill's job is to compare and report, not decide.

### Tool plan
**Ordered list with guardrails:**
1. **`find_posts(query='', status='published')`** (required)
   - Locate reference posts (published only, line 39).
   - Limit to `reference_count` (line 6).
   - Guardrail: Only published posts are valid references for style consistency.
2. **`compare_style(post_id=..., references=[...])`** (required)
   - Compare target post's style metrics against references.
   - Returns style_score, sections_affected, tone_match.
3. **`editor_review(post_id=...)`** (required)
   - Check post content against editorial style guide.
   - Returns findings and suggestions.
4. **`inspect_post(post_id=...)`** (optional, for structural metrics)
   - Get section count, word count, etc. for context.

### Output shape
**JSON with structured audit report** (lines 14–31):
```json
{
  "post_id": "...",
  "title": "...",
  "style_score": 0.82,
  "tone_match": "mostly consistent",
  "sections_affected": 2,
  "total_sections": 5,
  "findings": [
    "<short finding>",
    "<short finding>"
  ],
  "suggestions": [
    "<actionable suggestion>"
  ]
}
```
- **Key distinction:** Output is **structured JSON with findingsand suggestions**, not prose.
- If threshold exceeded (based on sections_affected / total_sections), the policy returns confirmation ambiguity before the card block is shown.

### Few-shot coverage
Lines 35–60 illustrate:
- 5 reference posts fetched (implied by find_posts call).
- compare_style returns style_score (0.78), sections_affected (2), tone_match.
- editor_review returns specific findings and suggestions.
- All wrapped in JSON output.
- **What's missing:**
  - Edge case: no reference posts available.
  - Edge case: threshold exactly at boundary (pct == threshold).
  - Fallback if compare_style or editor_review fails.
  - How to handle mixed findings (some sections good, others bad).

### Duplication with policy
- **None significant.** Policy does no comparison; skill is responsible for all tool calls and formatting.
- Helper `_format_audit_report` (lines 131–153) is a post-hoc fallback if no structured tool results exist. It does not duplicate skill work.

---

## Known gaps

**Striking gap 1: Card block surfaces post content, not style report (AGENTS.md flagged)**
The policy adds a card block containing the full post content (lines 126–127) via `_read_post_content`. But the skill output is a **JSON style report**, not post content. This mismatch means:
- The card block shows content, not audit findings.
- The user sees full post text in the UI, not a visual audit report.
- **Evidence from code:** Line 125 sets `thoughts=report or text`, so the report goes to `thoughts` (hidden from the card UI). Line 127 adds the card with full post content, drowning out the audit report.
- **Consequence:** Users don't see the audit findings prominently; they see the post content instead. This is the exact gap AGENTS.md calls out.

**Striking gap 2: Threshold confirmation is silent**
When sections_affected / total_sections exceeds threshold, the policy declares 'confirmation' ambiguity (lines 116–120) and returns an empty frame (line 121). This means:
- No audit findings are shown before asking for confirmation.
- The user has to confirm blindly, without seeing what the issues are.
- **Consequence:** Confirmation UX is poor; the user doesn't know what they're confirming.

**Striking gap 3: Reference count default logic**
The policy defaults `reference_count` to 5 (line 99) if not filled. But the skill expects this to come from the slot. If the policy doesn't pass reference_count in resolved context, the skill must infer it from the utterance or slot, risking misalignment. **Consequence:** The skill doesn't have a clear contract on whether reference_count is pre-set or needs to be inferred.

