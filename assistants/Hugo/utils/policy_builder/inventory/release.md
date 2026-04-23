# Policy Inventory — release

**Parent intent:** Publish
**DAX:** {04A}
**Eval step(s):** 14

## A. Policy (code) understanding

### Flow class
From `backend/components/flow_stack/flows.py` lines 303–313:
- `entity_slot`: `source` (SourceSlot, required)
- `dax`: `{04A}`
- `goal`: "publish the post to the primary blog; makes the post live immediately on the main channel. Use syndicate to cross-post, promote to amplify reach after publishing"
- Slot schema:
  - `source` (SourceSlot, required) — the post to publish
  - `channel` (ChannelSlot, required) — the target channel
- Tools: `['read_metadata', 'channel_status', 'release_post', 'update_post']`

### Guard clauses
From `backend/modules/policies/publish.py` lines 45–60 (`release_policy`):
- **Line 46–49:** Check if `source` slot is filled. If not:
  - Declare 'specific' ambiguity with missing_slot metadata (line 48).
  - Call `_clarify_with_steps` helper (lines 34–43) to show a multi-step form.
  - Return the clarification frame (line 49).
- **Line 50–51:** If channel slot not filled, default it to 'mt1t' (the primary blog).
- **Line 53:** Resolve source to post_id via `_resolve_source_ids`.
- **Line 54:** Call `llm_execute` for agentic tool-use loop.
- **Line 55–56:** Update post status to 'published' if post_id resolved (direct tool call, not via LLM).
- **Line 57:** Mark `flow.status = 'Completed'`.
- **Line 58–60:** Build frame with toast block containing the LLM response text.

### Staging
No explicit `flow.stage` assignments; policy runs single-pass.

### Stack-on triggers
None. Release does not push prerequisite flows.

### Persistence calls
Policy makes direct tool calls:
- `llm_execute` (line 54) — for publication orchestration via LLM.
- `update_post` (line 56) — direct call to flip status to 'published'.

**Key detail:** Unlike inspect/find/audit which are pure-read flows, release modifies state via `update_post`.

### Frame shape
- **Origin:** `'release'`
- **Blocks:** 
  - If source missing: toast block from `_clarify_with_steps` (lines 34–43).
  - If source present: toast block with the LLM response text (line 59).
- **Thoughts:** LLM text from llm_execute (line 54), stored as `text` variable.

### Ambiguity patterns
- **Line 48:** Declare 'specific' if `source` slot missing, with `metadata={'missing_slot': 'source'}`.
- **Expected ambiguity:** `{'channel_unavailable'}` per eval spec (line 210 in e2e_agent_evals.py).

### Eval step + recent track record
**Step 14** (from `utils/tests/e2e_agent_evals.py` lines 204–215):
- Utterance: `"Publish the multi-modal models post to Substack"`
- Expected tools: `['channel_status']`
- Expected block type: Not specified.
- **Expected errors:** `{'channel_status', 'release_post'}`
- **Expected ambiguity:** `{'channel_unavailable'}`
- Rubric:
  - `did_action`: "Attempts publication (errors from platform tools are expected)"
  - `did_follow_instructions`: "Targets the multi-modal models post and Substack channel"

**Known quality gap:** The eval explicitly expects platform tool errors and channel_unavailable ambiguity. This is documented as known-flaky behavior.

---

## B. Skill (prompt) understanding

### Skill contract
From `backend/prompts/skills/release.md` lines 1–52:
- **Inputs:** `post_id` and `channel` from resolved context.
- **Assumption:** Policy has already verified `source` and `channel` are filled and resolved. Skill's job is to publish and report, not validate slots.

### Tool plan
**Ordered list with guardrails:**
1. **`channel_status(channel=<channel>)`** (required)
   - Verify the channel is connected and ready.
   - Guardrail: Must succeed before attempting release.
2. **`release_post(post_id=..., channel=<channel>)`** (required)
   - Publish the post to the specified channel.
   - Guardrail: If fails, surface the error; do not retry unless user explicitly asks (line 52).

### Output shape
**JSON with publication result** (lines 12–23):
```json
{
  "post_id": "...",
  "title": "...",
  "channel": "...",
  "status": "published" | "failed",
  "url": "https://...",
  "notes": "<one-sentence summary or error message>"
}
```
- If publication succeeds: status='published', url set.
- If publication fails: status='failed', notes explain the failure.

### Few-shot coverage
Lines 27–43 illustrate:
- channel_status call succeeds (ok=true).
- release_post call succeeds, returns URL.
- JSON output with published status and URL.
- **What's missing:**
  - Edge case: channel_status fails.
  - Edge case: release_post fails (the eval explicitly expects this as channel_unavailable).
  - Behavior when channel is unavailable (expected ambiguity per eval).
  - How to handle multiple channels (the slot can be a list per line 6).

### Duplication with policy
- **None significant.** Policy does no publication logic; skill orchestrates the tool calls.
- Policy's `update_post` call (line 56) is deterministic post-processing, not duplication with skill.

---

## Known gaps

**Striking gap 1: Channel unavailability is expected but not surfaced**
The eval explicitly expects ambiguity='channel_unavailable' (line 210 in e2e_agent_evals.py), suggesting that channel_status can fail. But the policy does not catch this failure or declare the expected ambiguity. The policy calls `llm_execute`, which may encounter tool errors, but the policy doesn't route those to the 'channel_unavailable' ambiguity declaration. **Consequence:** When a channel is unavailable, the user doesn't get a clarifying prompt to choose a different channel; they get a generic error message.

**Striking gap 2: Multi-channel support unclear**
The skill prompt says "For each channel in the list" (lines 5–10), implying the skill should handle multiple channels. But the policy defaults channel to a single value 'mt1t' (line 51) and does not loop over multiple channels. **Consequence:** If the user says "publish to Substack and LinkedIn", the policy only publishes to mt1t, not the requested channels.

**Striking gap 3: Status update is unconditional**
The policy calls `update_post` to flip status to 'published' (line 56) regardless of whether `release_post` succeeded. If release_post fails (expected per eval), the post status is still flipped to published on disk, creating a stale state. **Consequence:** The post is marked published locally but not actually live on the platform.

**Striking gap 4: Toast block doesn't differentiate success/failure**
The policy returns the same toast block structure whether publication succeeded or failed (line 59). The toast type is always 'toast' with 'data: {message: text}'. There's no 'level' field to mark it as an error vs. success. **Consequence:** Users don't immediately see whether publication succeeded; they must parse the text.

