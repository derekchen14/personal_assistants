# Fixes — `release` Flow

**Status:** applied (see themes listed below)

## Back-references to Part 1

- Inventory: `inventory/release.md`
- Relevant sections: § Guard clauses, § Persistence calls, § Ambiguity patterns, § Known gaps
- Known gap: unconditional `update_post(status='published')` after `llm_execute` → stale disk state when platform fails. Eval step 14 explicitly expects tool failures.
- Primary SUMMARY.md themes: **T4 (error-path gaps)** — HIGHEST PRIORITY
- Theme feedback: `inventory/_theme4_feedback.md § release`

## Changes that landed

### `update_post(status='published')` is gated on tool success (AD-6 error frame)

- **What changed:** `release_policy` in `backend/modules/policies/publish.py` (lines ~45-91) now scans `tool_log` after `llm_execute` for `channel_status` and `release_post` entries, checking each call's `result['_success']`. On any failure, the policy short-circuits:
  ```python
  return DisplayFrame(
      origin='error',
      metadata={
          'tool_error': failed_tool,       # 'channel_status' or 'release_post'
          'channel': channel_val,
          'post_id': post_id or '',
          'reason': reason,                # '_error' code, or 'channel_unavailable' / 'platform_unreachable'
      },
      code=err_msg,                         # result['_message'] or result['_error'] or '<tool> failed'
  )
  ```
  `update_post` is **not** called and `flow.status` is **not** marked `Completed` — the user can retry without the disk state being out of sync with the platform.
- **Why:** Inventory § Known gaps #3 and `_theme4_feedback.md § release` both flagged this as disk-state corruption — step 14 of the eval explicitly expects `channel_status` / `release_post` to fail. Per AD-6 Section 1, tool-call failure is **not** ambiguity; it is an error frame with `metadata.tool_error` and the error text in `code`.
- **Theme:** Theme 4 (error-path gaps) — HIGH priority.
- **Files touched:**
  - `backend/modules/policies/publish.py` — `release_policy` lines ~56-84

### Success path writes `level='success'` toast

- **What changed:** On the happy path (both `channel_status` and `release_post` succeed), the policy calls `update_post(status='published')`, marks `flow.status = 'Completed'`, and builds a toast block with `data={'message': text, 'level': 'success'}`. The toast now carries a `level` field so the UI can distinguish success from the earlier generic toast.
- **Why:** Inventory § Known gaps #4 ("toast block doesn't differentiate success/failure"). The failure path now exits via error origin before ever reaching this branch, so the success toast is unambiguous.
- **Files touched:**
  - `backend/modules/policies/publish.py` — `release_policy` lines ~86-91

### Eval rubric aligned with AD-6 error frame

- **What changed:** The eval spec for step 14 (`utils/tests/e2e_agent_evals.py`) dropped `expected_ambiguity={'channel_unavailable'}` and added:
  - `expected_frame_origin='error'`
  - `expected_tool_error={'channel_status', 'release_post'}`
  `_check_level1` now reads `frame.origin` and `frame.metadata.get('tool_error')` and asserts both. A short-circuit was added so error-origin frames don't fail the "empty response" check (their payload is in `metadata` / `code`, not in blocks).
- **Why:** The test was previously expecting ambiguity; AD-6 changed that channel. Keeping the rubric wrong would mask the very regression we just fixed.
- **Theme:** Theme 4 (error-path gaps) harness alignment.
- **Files touched:**
  - `utils/tests/e2e_agent_evals.py` — step 14 rubric + `_check_level1` generic AD-6 assertions

## Architectural decisions applied

- **AD-5** (terminology) — policy "scans the tool_log", "returns an error frame"; no "fires" / "triggers" language introduced.
- **AD-6** (three failure modes, three distinct channels):
  - **Tool-call failure** → `DisplayFrame(origin='error', metadata={tool_error, channel, post_id, reason}, code=err_msg)`. Not ambiguity.
  - **Contract violation** — skill output shape is not explicitly validated here (release is short and the `llm_execute` text is only used as the toast message); the tool-error scan is the primary contract surface.
  - **Ambiguous user intent** — the missing-source guard at the top of the policy still uses `ambiguity.declare('specific', metadata={'missing_slot': 'source'})` + `_clarify_with_steps`. This is legitimate user-intent ambiguity (which post to publish) and stays with `AmbiguityHandler`.

> **Part 2 alignment.** This fix aligns with [§ 3 Error recovery](../best_practices.md#3-error-recovery). See [When Agents Fail — Mindra](https://mindra.co/blog/fault-tolerant-ai-agents-failure-handling-retry-fallback-patterns) on per-tool circuit breakers — scanning `tool_log` for each `channel_status` / `release_post` `_success` and short-circuiting before `update_post` is exactly the "don't persist past a failed dependency" pattern — and [Your ReAct Agent Is Wasting 90% of Its Retries — TDS](https://towardsdatascience.com/your-react-agent-is-wasting-90-of-its-retries-heres-how-to-stop-it/) on classifying platform-unreachable failures as tool errors (error frame with `metadata.tool_error`) rather than rerouting through ambiguity.

## Open follow-ups

- Retry-with-exponential-backoff on transient failures (30s / 1min / 2min per user's feedback in `_theme4_feedback.md § release (d)`) is not yet implemented. Ship as a follow-up; the current path surfaces the error after the first failure.
- Multi-channel publication (loop `channel_status` + `release_post` per channel in the slot's list) is also deferred per the same feedback.
- The user-facing error message does not differentiate between `channel_status` failing vs. `release_post` failing beyond the `reason` field (`channel_unavailable` vs. `platform_unreachable`). Frontend can surface different copy if desired.
