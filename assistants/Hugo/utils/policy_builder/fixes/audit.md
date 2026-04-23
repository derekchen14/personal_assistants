# Fixes — `audit` Flow

**Status:** applied (see themes listed below)

## Back-references to Part 1

- Inventory: `inventory/audit.md`
- Relevant sections: § Guard clauses, § Frame shape, § Ambiguity patterns, § Known gaps
- Known gap (per AGENTS.md): step 11 surfaced post content instead of structured style report
- Primary SUMMARY.md themes: **T3 (output-shape drift)**, **T4 (error-path gaps)**, **T5 (cross-turn findings channel)**
- Theme feedbacks: `inventory/_theme3_feedback.md § audit`, `inventory/_theme4_feedback.md § audit`, `inventory/_theme5_feedback.md § audit`

## Changes that landed

### Structured `report` block — findings are visible, post content is not the frame

- **What changed:** `audit_policy` (in `backend/modules/policies/revise.py` lines ~144-214) now parses the skill JSON via `self.engineer.apply_guardrails(text, format='json')`. On success it builds a single `card` block whose `data` carries **nested `report` data**:
  ```python
  block_data = {
      'post_id': post_id,
      'post_title': parsed.get('title', ''),
      'report': {
          'style_score': parsed.get('style_score'),
          'tone_match': parsed.get('tone_match'),
          'findings': findings,     # list of {aspect, expected, observed, severity, snippet?}
          'suggestions': suggestions,
      },
  }
  ```
  No more full-post-content card. The AGENTS.md § Known e2e quality gaps entry for step 11 is resolved.
- **Why:** `_theme3_feedback.md § audit` resolved "reuse card with nested report" (Option B). Per-finding severity (`low|medium|high`) replaces a separate severity-threshold slot, per the user's "no need to overcomplicate with a severity threshold slot" note.
- **Theme:** Theme 3 (output-shape drift).
- **Files touched:**
  - `backend/modules/policies/revise.py` — `audit_policy` lines ~144-214
  - `backend/prompts/skills/audit.md` — output schema tightened to include per-finding severity
  - `backend/modules/templates/revise.py` — `_format_audit_message` produces the spoken line from the nested report

### Threshold breach → `confirmation` ambiguity with findings preview

- **What changed:** When `sections_affected / total_sections > threshold` (default 0.2), the policy declares `ambiguity.declare('confirmation', metadata={'reason': 'audit_threshold_exceeded', 'pct': round(pct, 2), 'threshold': threshold, 'findings_preview': findings[:3]})` and returns `DisplayFrame()`. The preview carries the top-3 findings so the spoken confirmation question can reference what triggered the escalation ("I found a few issues during the audit, would you like me to go ahead and polish section X?").
- **Why:** `_theme4_feedback.md § audit` confirmed this path stays in `AmbiguityHandler` per AD-6 Section 3 (genuine ambiguous user intent — user must decide whether to apply changes).
- **Theme:** Theme 4 (error-path gaps) refinement.
- **Files touched:**
  - `backend/modules/policies/revise.py` — `audit_policy` lines ~178-185

### Parse-failure path → `origin='error'` (AD-6 contract violation)

- **What changed:** If `apply_guardrails` cannot return a dict with a `findings` key, the policy returns
  ```python
  DisplayFrame(
      origin='error',
      metadata={'contract_violation': 'audit_findings_missing'},
      code=text or 'Audit produced no structured findings.',
  )
  ```
  The raw offending skill text goes into `code` (per AD-6: `code` holds error text just as it holds successful code). This replaces the old silent fallback to `thoughts=raw_text`.
- **Why:** AD-6 Section 2 (contract violation) — tighten prompt, require JSON, `apply_guardrails`, and when that still fails, surface via `origin='error'` rather than routing through `AmbiguityHandler`.
- **Theme:** Theme 4 (error-path gaps) — AD-6 reshape of what had been proposed as a `parse_error=True` metadata flag on an `origin='audit'` frame.
- **Files touched:**
  - `backend/modules/policies/revise.py` — `audit_policy` lines ~161-169

### Scratchpad write under AD-1 convention

- **What changed:** After the successful parse + threshold check, the policy writes to scratchpad under key `'audit'` with the required fields `version: '1'`, `turn_number: context.turn_id`, `used_count: 0`, plus `summary`, `style_score`, `tone_match`, `findings`, `suggestions`, and `evidence_posts` (list of `post_id` strings per `_theme5_feedback.md § audit`).
- **Why:** Theme 5 / AD-1. Step 13 polish consumes `findings` + `evidence_posts`; when polish cites an `evidence_post`, it can cross-reference the `'find'` scratchpad for full metadata.
- **Theme:** Theme 5 (cross-turn findings channel).
- **Files touched:**
  - `backend/modules/policies/revise.py` — `audit_policy` lines ~189-199

## Architectural decisions applied

- **AD-1** (scratchpad channel) — producer write under key `'audit'`, convention-compliant.
- **AD-5** (terminology) — policy "declares ambiguity" on threshold breach, "returns an error frame" on contract violation; no "fires" language.
- **AD-6** (three failure modes):
  - Parse/contract failure → `DisplayFrame(origin='error', metadata={'contract_violation': ...}, code=raw_text)`. Not ambiguity.
  - Threshold breach → `AmbiguityHandler` `confirmation` level (legitimate user-intent ambiguity).
  - Tool-call failure is not yet explicitly scanned (the `editor_review` / `compare_style` calls could fail); treated as skill output contract violation today.

> **Part 2 alignment.** This fix aligns with [§ 3 Error recovery](../best_practices.md#3-error-recovery) and [§ 9 Cross-turn state / findings channel](../best_practices.md#9-cross-turn-state--findings-channel). See [Error Recovery and Graceful Degradation — notes.muthu.co](https://notes.muthu.co/2026/02/error-recovery-and-graceful-degradation-in-ai-agents/) on distinct channels for contract violations (parse failure → `origin='error'`) vs. user-intent ambiguity (threshold breach → `AmbiguityHandler.declare('confirmation')`) and [State of AI Agent Memory 2026 — mem0.ai](https://mem0.ai/blog/state-of-ai-agent-memory-2026) on structured findings that downstream consumers can index by intent (polish reads `findings` + `evidence_posts`).

## Open follow-ups

- Tool-call failure for `editor_review` / `compare_style` / `find_posts` inside `llm_execute` is not separately classified; a platform outage today will bubble up as a contract violation (no `findings` key). If we want AD-6 tool-error conformance here, add a `tool_log` scan similar to `release_policy`.
- The audit confirmation modal is faked in the spoken response (`"I found a few issues... [Yes/No]"`) pending frontend chat-container confirmation UI. User explicitly deferred the UI work to a later task.
- Part 4 cross-flow integration test should assert `memory.read_scratchpad()['audit']['findings']` is a non-empty list after step 12.
