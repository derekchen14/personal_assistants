# Policy Inventory — polish

**Parent intent:** Revise
**DAX:** {3BD}
**Eval step(s):** 9 (basic) + 13 (informed, planned; step 13 consumes findings from steps 10-12 inspect/find/audit)

## A. Policy (code) understanding

### Flow class
From `backend/components/flow_stack/flows.py` lines 214-225:
- `entity_slot`: source
- `goal`: editing of a specific paragraph, sentence or phrase; improves word choice, tightens sentences, fixes transitions, and smooths flow without changing meaning or structure. The scope is within a single paragraph or image, not across the whole post
- `tools`: read_metadata, read_section, write_text, find_and_replace, revise_content
- Slot schema:
  - source (SourceSlot, 'sec' entity_part) — post and section reference
  - style_notes (FreeTextSlot, optional) — specific prose guidance (e.g. "punchier", "more formal")
  - image (ImageSlot, optional) — image to polish or improve

### Guard clauses
From `backend/modules/policies/revise.py` lines 47-69 (polish_policy):
- **Line 48-49:** Call `_require_source(flow, state, context)` which checks if entity_slot is filled. If missing, declare 'specific' ambiguity and return empty DisplayFrame().
- **Line 52:** Call `_resolve_source_ids` to ground post_id and sec_id from source slot.
- **Line 53:** Call `llm_execute` to run the skill (tool-using loop).
- **Line 55-56:** If post_id and sec_id and text all exist, call `_persist_section` to save the polished version (same pattern as simplify).
- **Line 59-63:** Check for structural issues via `extract_tool_result(tool_log, 'inspect_post')`. If structural_issues are found, call `fallback('rework')`, set keep_going=True, and return empty DisplayFrame() to escalate to rework. This is the only stack-on/fallback trigger in the polish policy.
- **Line 65:** Mark flow.status = 'Completed'.
- **Line 66:** Build DisplayFrame with origin='polish' and thoughts from LLM output.
- **Line 67-68:** If post_id exists, add a card block with post content.

### Staging
No staging used. The flow has no stage field manipulation.

### Stack-on triggers
**Line 61:** `flow_stack.fallback('rework')` — If the skill detects structural issues (via inspect_post tool result), the policy replaces the current flow with rework and resumes. This is the only condition-based flow replacement in polish.

### Persistence calls
**Line 56:** `self._persist_section(post_id, sec_id, text, tools)` is called directly by the policy after llm_execute returns, similar to simplify. The skill prompt (line 11) confirms the policy saves automatically via revise_content, but the policy also uses the helper as a safety measure.

### Frame shape
- **Origin:** 'polish' (line 66)
- **Blocks:** One card block added if post_id is resolved (lines 67-68), containing post_id, title, status, and full content markdown
- **Thoughts:** LLM output text describing the polish action (line 66)
- **Metadata:** Empty (line 66)
- **Code field:** Not set

### Ambiguity patterns
- **Line 48:** declare('specific', metadata={'missing_slot': flow.entity_slot}) when source is not filled via `_require_source`. This is the only explicit ambiguity declaration in the policy.

### Eval step + recent track record
**Step 9 (basic) from `utils/tests/e2e_agent_evals.py` lines 149-158:**
- Utterance: "Tighten the opening paragraph of the Motivation section — make it punchier"
- Expected tools: ['read_section']
- Rubric:
  - did_action: "Paragraph improved, meaning preserved"
  - did_follow_instructions: "Opening paragraph is shorter and more impactful"

**Step 13 (informed, planned per policy_spec.md):** Not yet in the current e2e_agent_evals.py STEPS list, but per the policy_spec.md line 27 and lines 21-22 (the 14-step table), polish appears again after audit (step 12). Step 13 polish is "Informed pass — uses findings from inspect + find + audit" (steps 10-12).

## A'. Usage Contexts

Polish appears in two distinct contexts:

### Context 1: Basic Polish (Step 9)
The user directly requests prose tightening on a named section/paragraph (e.g., "Tighten the opening paragraph of Motivation — make it punchier"). The policy receives a cold, standalone request:
- No prior tool results; polish runs independently.
- The skill reads the target section, edits in isolation, and calls revise_content.
- The fallback to rework (lines 59-63) checks if the edit exposed structural issues but typically won't trigger on a basic polish request.
- Frame reflects the polished section in a card block.

**Current code path:** Lines 47-69 execute a standard revise-family flow: check source, resolve IDs, llm_execute, persist, complete.

### Context 2: Step 13 polish (after inspect + find + audit)
The user requests polish after the system has collected findings from inspect + find + audit (steps 10-12). Per AD-1 (`policy_spec.md`), these producers write to the **scratchpad** under keys `inspect` / `find` / `audit`, each with `version` / `turn_number` / `used_count` + flow-specific payload.

Per AD-2, there is **no separate "informed" stage** on polish — the skill always reads conversation history + scratchpad and behaves accordingly. When prior findings exist, the skill incorporates them; when they don't, the skill polishes cold.

**Current code path:** Same as basic (lines 47-69). The policy does not differentiate; instead, the polish skill prompt is responsible for looking up relevant scratchpad entries (see `skills/polish.md` § "Using prior findings"). This is intentional and aligns with AD-2.

**Distinction:** The policy is identical in both contexts; the skill differentiates by reading scratchpad. This is the current design and should not be refactored to branch on findings presence in the policy layer.

## B. Skill (prompt) understanding

### Skill contract
From `backend/prompts/skills/polish.md`:
The skill expects `resolved` context to include:
- `post_id` — the target post identifier
- `post_title` — the post title (optional)
- `section_ids` — list mapping section IDs to names (optional)
- `target_section` — the section ID to polish (when source.sec is filled)

Lines 54-59 emphasize using resolved entities instead of calling read_metadata.

For step 13 polish, the skill reads the **scratchpad** (not `resolved`) for findings from prior turns:
- `scratchpad['inspect']` — metrics from inspect_post (word count, section count, read time, etc.)
- `scratchpad['find']` — matching posts from find_posts (related topics)
- `scratchpad['audit']` — tone match, style consistency findings from audit

This is wired via the `## Using prior findings` section in `skills/polish.md` (per AD-1 scratchpad convention).

### Tool plan
Ordered tools the skill may call:
1. **read_section** (required: loads the target section before editing, per line 7 "Find the target section")
2. **find_and_replace** (optional: for targeted word/phrase swaps, line 10)
3. **write_text** (optional: for full sentence rewrites, line 10)
4. **revise_content** (required: saves the polished version, line 11)
5. **read_metadata** (optional fallback, per resolved context guidance)

Per-tool guardrails:
- **Read only the target section** (lines 6-7, 55): Do NOT read other sections. Do NOT read every section first.
- **Match section to section_ids** (line 6): When the user names a section, match it to the resolved section_ids list.
- **Preserve scope** (lines 13-15): If user names opening paragraph, polish only that paragraph. Do not touch neighboring paragraphs.
- **Preserve meaning and structure** (line 9): If restructuring is needed, escalate to rework, not polish.
- **Use find_and_replace for targeted edits** (line 10): Word/phrase swaps; use write_text only for full rewrites.

### Output shape
JSON with this structure (lines 20-28):
```json
{
  "target": "Motivation — opening paragraph",
  "before": "<the exact prior text of the edited span>",
  "after": "<the polished text that was saved>",
  "changes": ["<short description>", "<short description>"]
}
```

### Few-shot coverage
Lines 31-48 provide a single positive example:
- User: "Tighten the opening paragraph of the Motivation section — make it punchier."
- Tool trajectory: read_section → extract first paragraph → revise_content with whole section (paragraph 1 polished, others unchanged)
- Output: JSON with before/after and a list of changes (traded introductory clause for punchy lead; collapsed long phrase into single image)

The example covers paragraph-level prose tightening. Missing coverage:
- Polishing a whole section (no paragraph specified)
- Using style_notes guidance (e.g., "make it more formal")
- Image polish (the image slot is defined as optional but not exemplified)
- Step 13 scenario using prior findings from the scratchpad
- find_and_replace or write_text tool usage (only revise_content shown)

### Duplication with policy
The policy and skill both understand that polish is single-paragraph or sentence scope, with meaning preservation. The policy checks source (line 48) but then delegates scope parsing ("opening paragraph") to the skill. The policy's fallback-to-rework logic (lines 59-63) mirrors the skill's guidance (line 59 of skill prompt: "If the span needs restructuring, use rework instead"), creating alignment that may prevent over-correction. However, no explicit contract governs when the policy inspects tool results vs. when the skill detects structural issues; the fallback check happens after skill completion, which may be late.

## Known gaps

1. **Step 13 scratchpad consumption not yet wired in the skill:** Step 13 in the 14-step eval (policy_spec.md § AD-1 / AD-2) requires polish to consume findings from steps 10-12 (inspect, find, audit) via the scratchpad channel. The skill's `## Using prior findings` section (from Theme 2 execution) handles the consumer side; producers (inspect, find, audit) must write to scratchpad in Theme 3 / Theme 5 work.

2. **Style_notes slot not exemplified:** The style_notes slot (FreeTextSlot, optional, flows.py line 222) allows guidance like "punchier", "more formal", "academic tone". The skill prompt doesn't show how to use this input; the few-shot example doesn't include style guidance.

3. **Image slot not covered:** The flow defines image (ImageSlot, optional, flows.py line 223) for image polish/improvement, but the skill prompt doesn't address this. If the user says "Improve the hero image", the skill has no guidance on whether to propose a better image or describe improvements.

4. **Fallback timing unclear:** The policy checks for structural issues via `inspect_post` tool result (line 59) after the skill finishes. If the skill didn't call inspect_post (unlikely but possible), the fallback won't trigger. The contract between "when the skill should call inspect_post" and "when the policy checks for structural issues" is implicit, not explicit in the code.

5. **Step 9 vs. Step 13 handled at the skill layer, not the policy:** Per AD-2, the policy code is intentionally the same in both contexts. Differentiation happens in the skill via scratchpad reads. The only change needed is on the producer side (inspect/find/audit must write to scratchpad with the AD-1 convention); once that lands, step 13 naturally picks up the findings.
