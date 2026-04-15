# PEX Output Validation and Recovery Loop

## Goal

Implement the `recover()` method in PEX so that when a policy produces a bad frame (empty content, tool errors, malformed output), PEX automatically retries with escalating strategies before the user ever sees the failure. The user should only see the final, passing result — or a clear clarification question if all recovery attempts fail.

## Current State

Today, `PEX.execute()` calls `policy.execute()` once and returns whatever frame it produces. There is no validation of frame quality after the policy runs, and no retry. If the LLM generates an empty outline, a broken draft, or a response that ignores the user's request, it goes straight through RES to the user.

The spec defines a 4-step recovery cascade in `PEX § Recover Function`:
1. Retry skill (1 retry with same inputs)
2. Gather more context (push Internal flow for supporting info)
3. Re-route via `contemplate()` (fallback flow or plan decomposition)
4. Escalate to user (clarification via RES)

Steps 2 and 3 involve the Agent orchestrator and flow stack manipulation. This plan implements **steps 1 and 4 entirely**, and **prepares the interface** for steps 2 and 3 so they can be added later without refactoring.

## Architecture

### Where recovery lives

Recovery logic goes in `PEX`, not in individual policies. Policies produce frames; PEX validates them and retries if needed. This keeps policies focused on their domain logic (slot checking, tool calling, frame building) while PEX owns the quality gate.

### The validation → retry flow

```
policy.execute()
       │
       ▼
  validate_frame()  ──pass──▶  return frame to Agent
       │
      fail
       │
       ▼
  recover()
    ├── Tier 1: retry skill (re-invoke policy.execute with error context)
    ├── Tier 2: gather context (return RecoveryAction.GATHER_CONTEXT) ← future
    ├── Tier 3: re-route (return RecoveryAction.REROUTE) ← future
    └── Tier 4: escalate to user (declare ambiguity, return clarification frame)
```

## Files to Modify

### 1. `backend/modules/pex.py` — Main changes

**Add `recover()` method and `_validate_frame()` method. Modify `execute()` to call them.**

#### a. Frame validation

Add `_validate_frame()` that checks whether a frame is good enough to show to the user. Returns a `FrameCheck` result with pass/fail and a reason string.

```python
# Add at top of pex.py
from dataclasses import dataclass
from enum import Enum

class RecoveryAction(Enum):
  """What the Agent should do after recover() returns."""
  RETRY = 'retry'              # PEX handles internally
  GATHER_CONTEXT = 'gather'    # Agent pushes Internal flow (future)
  REROUTE = 'reroute'          # Agent calls NLU contemplate() (future)
  ESCALATE = 'escalate'        # Agent goes to RES for clarification

@dataclass
class FrameCheck:
  passed: bool
  reason: str = ''

# Constants
_MAX_REPAIR_ATTEMPTS = 2  # 1 original + 1 retry = 2 total attempts
```

The `_validate_frame()` method runs structural checks first, then an optional LLM quality check for flows that warrant it:

```python
def _validate_frame(self, frame: DisplayFrame, flow, state: DialogueState) -> FrameCheck:
  """Validate that a frame is good enough to show to the user.

  Checks are ordered cheapest-first. Returns on first failure.
  """
  # 1. Frame exists and has content
  if not frame or not frame.has_content():
    # Exception: ambiguity frames (where the policy already declared ambiguity
    # and returned a clarification prompt) should pass through — the ambiguity
    # handler is already handling this case.
    if self.ambiguity.present():
      return FrameCheck(passed=True)
    return FrameCheck(passed=False, reason='Frame has no content')

  content = frame.data.get('content', '')

  # 2. Content is not empty or trivially short
  if isinstance(content, str) and len(content.strip()) < 20:
    # Allow short content for specific block types that don't need prose
    if frame.block_type not in ('confirmation', 'toast', 'form'):
      return FrameCheck(passed=False, reason=f'Content too short ({len(content.strip())} chars)')

  # 3. Tool errors in frame data
  error_msg = frame.data.get('error') or frame.data.get('message', '')
  if 'error' in frame.data and frame.data.get('status') == 'error':
    return FrameCheck(passed=False, reason=f'Tool error in frame: {error_msg}')

  # 4. Content echoes the user's message verbatim (parrot check)
  #    This catches the common LLM failure mode of restating the request.
  last_user = self._get_last_user_utterance()
  if last_user and isinstance(content, str) and content.strip() == last_user.strip():
    return FrameCheck(passed=False, reason='Content is a verbatim echo of user input')

  # 5. (Optional) LLM quality check for creative/complex flows
  #    Only runs for flows flagged in config. Costs 1 extra Haiku call.
  if self._should_llm_validate(flow):
    quality = self._llm_quality_check(content, flow, state)
    if not quality.passed:
      return quality

  return FrameCheck(passed=True)
```

The `_should_llm_validate()` method checks domain config for which flows warrant the extra cost:

```python
def _should_llm_validate(self, flow) -> bool:
  """Check if this flow is flagged for LLM quality validation in config."""
  llm_validate_flows = self.config.get('recovery', {}).get('llm_validate_flows', [])
  return flow.name() in llm_validate_flows
```

The `_llm_quality_check()` method uses a fast model (Haiku) to verify the output addresses the request:

```python
def _llm_quality_check(self, content: str, flow, state: DialogueState) -> FrameCheck:
  """Quick LLM check: does the output actually address the user's request?"""
  last_user = self._get_last_user_utterance()
  if not last_user:
    return FrameCheck(passed=True)

  system = (
    'You are a quality checker. The user asked for something and the agent produced a response. '
    'Does the response actually address what the user asked? '
    'Reply with ONLY "pass" or "fail: <one-sentence reason>".'
  )
  prompt = f'User request: {last_user}\n\nAgent output:\n{content[:2000]}'
  try:
    result = self.engineer.call(prompt, system=system, task='quality_check', model='haiku', max_tokens=100)
    result = result.strip().lower()
    if result.startswith('pass'):
      return FrameCheck(passed=True)
    reason = result.removeprefix('fail:').strip() or 'LLM quality check failed'
    return FrameCheck(passed=False, reason=reason)
  except Exception:
    # If the quality check itself fails, let the frame through
    return FrameCheck(passed=True)
```

Helper to get the last user utterance:

```python
def _get_last_user_utterance(self) -> str | None:
  """Get the most recent user utterance from context."""
  recent = self.world.context.compile_history(look_back=1)
  if isinstance(recent, str):
    return recent.strip() or None
  if isinstance(recent, list):
    for turn in reversed(recent):
      role = turn.get('role', '') if isinstance(turn, dict) else ''
      if role.lower() == 'user':
        return turn.get('content', '').strip() or None
  return None
```

#### b. The recover() method

```python
def recover(self, frame: DisplayFrame, check: FrameCheck,
            flow, state: DialogueState,
            context: 'ContextCoordinator') -> tuple[DisplayFrame, RecoveryAction]:
  """Attempt to recover from a failed frame validation.

  Tries strategies in escalating order. Returns the best frame
  achievable and an action for the Agent.

  Args:
    frame: The frame that failed validation.
    check: The FrameCheck result explaining why it failed.
    flow: The active flow.
    state: Current dialogue state.
    context: Conversation context.

  Returns:
    (recovered_frame, action) — the frame to use and what the Agent should do next.
  """
  log.warning('recover: %s (flow=%s)', check.reason, flow.name())

  # ── Tier 1: Retry skill with error feedback ──────────────────────
  #
  # Re-invoke the policy with the validation error injected into context.
  # The skill sees what went wrong and gets one chance to fix it.
  # This is the "silent retry" — the user never sees the failed attempt.

  repair_context = (
    f'[Recovery] Your previous output was rejected: {check.reason}. '
    f'Please try again, addressing this issue. '
    f'The user\'s request has not changed.'
  )
  self.memory.write_scratchpad(f'[repair] Previous attempt rejected: {check.reason}')

  policy = self._policies.get(flow.intent)
  if policy:
    # Inject the repair context into conversation history
    context.add_turn('System', repair_context, turn_type='system')
    retry_frame = policy.execute(flow, state, context, self._dispatch_tool)

    retry_check = self._validate_frame(retry_frame, flow, state)
    if retry_check.passed:
      log.info('recover: tier-1 retry succeeded')
      return retry_frame, RecoveryAction.RETRY

    log.warning('recover: tier-1 retry failed: %s', retry_check.reason)

  # ── Tier 2: Gather more context (future) ─────────────────────────
  #
  # Would push an Internal flow to collect supporting info (peek at DB,
  # check memory/FAQs, look at related posts). Not implemented yet.
  # When implemented, return:
  #   return frame, RecoveryAction.GATHER_CONTEXT
  # The Agent would push the Internal flow, set keep_going, and re-enter
  # execute() for this flow after the Internal flow completes.

  # ── Tier 3: Re-route via contemplate (future) ────────────────────
  #
  # Would send to NLU contemplate() for a fallback flow or plan
  # decomposition. Not implemented yet.
  # When implemented, return:
  #   return frame, RecoveryAction.REROUTE

  # ── Tier 4: Escalate to user ─────────────────────────────────────
  #
  # All automated recovery failed. Ask the user for help.
  # Declare ambiguity so RES generates an appropriate clarification.

  log.info('recover: escalating to user')
  self.ambiguity.declare(
    'partial',
    metadata={'flow': flow.name(), 'failure_reason': check.reason},
    observation=(
      f'I had trouble completing this — {check.reason}. '
      f'Could you provide more details or try a different approach?'
    ),
  )
  escalation_frame = DisplayFrame(self.config)
  escalation_frame.set_frame('default', {'content': self.ambiguity.ask()})
  return escalation_frame, RecoveryAction.ESCALATE
```

#### c. Modify `execute()` to use validation and recovery

Replace the current execute method body (lines 73–109 of pex.py) with:

```python
def execute(self, state: DialogueState,
            context: 'ContextCoordinator') -> tuple[DisplayFrame, bool]:
  active_flow = self.flow_stack.get_active_flow()
  if not active_flow:
    frame = DisplayFrame(self.config)
    return frame, False

  flow_name = active_flow.name()

  check_result = self._security_check(active_flow)
  if check_result:
    return check_result, False

  if flow_name in _UNSUPPORTED:
    self.flow_stack.mark_complete(result={'unsupported': True})
    frame = self.world.latest_frame() or DisplayFrame(self.config)
    return frame, False

  # ── Execute policy ──────────────────────────────────────────────
  policy = self._policies.get(active_flow.intent)
  if policy:
    frame = policy.execute(active_flow, state, context, self._dispatch_tool)
  else:
    frame = DisplayFrame(self.config)

  # ── Validate output ─────────────────────────────────────────────
  check = self._validate_frame(frame, active_flow, state)
  if not check.passed:
    frame, action = self.recover(frame, check, active_flow, state, context)
    # For ESCALATE, don't mark flow complete — leave it Active so the
    # user can provide clarification and we re-enter execute().
    if action == RecoveryAction.ESCALATE:
      state.has_issues = True
      self.world.insert_frame(frame)
      self._verify()
      return frame, False
    # For GATHER_CONTEXT and REROUTE (future), the Agent handles routing.
    # For RETRY, we continue with the recovered frame below.

  # ── Flow completion ─────────────────────────────────────────────
  if active_flow.intent != Intent.PLAN:
    self.flow_stack.mark_complete(result={'flow_name': flow_name})
  self.world.insert_frame(frame)

  if active_flow.intent in _POST_INTENTS:
    self._update_active_post(active_flow)

  self._verify()

  keep_going = state.keep_going
  return frame, keep_going
```

### 2. `shared/shared_defaults.yaml` — Add recovery config

Add a `recovery` section to the shared defaults:

```yaml
recovery:
  max_repair_attempts: 2          # 1 original + 1 retry
  min_content_length: 20          # chars below which content is considered empty
  llm_validate_flows: []          # flows that get LLM quality check (domain overrides this)
  llm_validate_model: haiku       # cheap model for quality checks
```

### 3. `schemas/blogger.yaml` — Add domain-specific recovery config

Add to the Hugo domain config:

```yaml
recovery:
  llm_validate_flows:
    - outline
    - expand
    - compose
    - revise_content
    - brainstorm
```

These are the creative/generative flows where the LLM is most likely to produce low-quality output. Deterministic flows (create, browse, check, view) rely on structural validation only — no extra LLM call needed.

### 4. `backend/components/memory_manager.py` — Ensure `write_scratchpad` exists

Verify that `MemoryManager` has a `write_scratchpad(text)` method. The recovery loop uses it to record repair attempts so subsequent retries have context about what was already tried. If the method doesn't exist, add:

```python
def write_scratchpad(self, text: str):
  """Append a snippet to the session scratchpad."""
  self._scratchpad.append(text)
```

### 5. `backend/components/context_coordinator.py` — Support system turns

The recovery loop injects a `System` turn with the repair context. Verify that `add_turn('System', text, turn_type='system')` works. The system turn should be included in `compile_history()` output so the skill sees the repair instruction.

### 6. No changes to individual policies

Individual policy files (`draft.py`, `research.py`, `revise.py`, etc.) do **not** need modification. The validation and retry happen in PEX around the `policy.execute()` call. Policies continue to produce frames exactly as they do today — they are unaware of the recovery loop.

The one exception: policies that already declare ambiguity (e.g., `outline_policy` declaring `specific` ambiguity for missing topic slot) will have their ambiguity frames passed through by `_validate_frame()` without triggering recovery, because the ambiguity handler check runs first.

## Testing

### Unit tests to add to `tests/unit_tests.py`

1. **`test_validate_frame_empty`** — empty frame fails validation with reason "Frame has no content"
2. **`test_validate_frame_short_content`** — frame with <20 chars of content fails (except for confirmation/toast/form block types)
3. **`test_validate_frame_tool_error`** — frame with `{'status': 'error', 'error': '...'}` in data fails
4. **`test_validate_frame_parrot`** — frame whose content matches the last user utterance fails
5. **`test_validate_frame_passes`** — frame with substantive content passes
6. **`test_validate_frame_ambiguity_passthrough`** — when ambiguity is already declared, even an empty frame passes (the ambiguity handler owns the response)
7. **`test_recover_tier1_succeeds`** — mock policy returns bad frame first, good frame second → recover returns good frame with RETRY action
8. **`test_recover_tier4_escalates`** — mock policy returns bad frame both times → recover declares ambiguity and returns ESCALATE action
9. **`test_execute_with_recovery`** — end-to-end: policy produces bad frame → PEX retries → user sees the recovered frame

### E2E tests to add to `tests/e2e_agent_evals.py`

Add a new test class `TestRecovery` with LLM-backed tests:

1. **`test_outline_retry_on_empty`** — ask for an outline on a vague topic → verify the response has actual outline content (not empty or parrot)
2. **`test_draft_retry_on_parrot`** — provide a topic and immediately ask to compose → verify the response doesn't just echo the topic

## Sequence of Implementation

1. Add `FrameCheck`, `RecoveryAction` dataclasses and constants to `pex.py`
2. Add `_validate_frame()` with structural checks only (no LLM check yet)
3. Add `_get_last_user_utterance()` helper
4. Add `recover()` with Tier 1 (retry) and Tier 4 (escalate) only
5. Modify `execute()` to call `_validate_frame()` and `recover()`
6. Add `recovery` config section to `shared_defaults.yaml` and `blogger.yaml`
7. Write unit tests for validation and recovery
8. Add `_should_llm_validate()` and `_llm_quality_check()` (the LLM-based quality gate)
9. Write e2e tests
10. Verify all existing tests still pass — the recovery loop should be invisible to passing cases