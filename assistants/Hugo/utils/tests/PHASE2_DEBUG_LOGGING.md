# Phase-2 Debug Logging — Teardown Manifest

**Purpose.** Part 4 Phase 2 added temporary instrumentation to surface the CLI↔UI gap (frame serialization, dispatch routing). When Phase 2 wraps, every line listed below should come out so the codebase doesn't carry diagnostic weight forever.

**Convention used.** Every temporary block has a `# Phase-2 logging:` (Python) or `// Phase-2 logging:` (TypeScript) comment header, so a one-line grep finds them all:

```
grep -rn "Phase-2 logging" backend frontend
```

## Backend (Python) — temporary

| File | Lines | What | Tear-down action |
|---|---|---|---|
| `backend/agent.py` | top of file: `import json`, `import os` | New imports for `AGENT-FRAME-FULL` dump | Remove if no other code in the file needs them post-teardown. |
| `backend/agent.py` | inside `_take_turn` after the existing `log.info(f'AGENT: {agent_utt[:256]}')` | `block_summary = [...]` + `log.info(f'AGENT-FRAME: …')` + the `HUGO_DEBUG_FRAMES` opt-in `AGENT-FRAME-FULL` dump | Delete the block. The original `log.info(f'AGENT: ...')` line stays. |
| `backend/modules/pex.py` | inside `execute()`, immediately after `frame = policy.execute(...)` | `log.info(f'PEX-POST-POLICY: …')` block | Delete the block. |
| `backend/routers/chat_service.py` | inside the WS handler, immediately after `frame = result.get('frame') or {}` | `print('WS-HANDOFF: …', flush=True)` block | Delete the block. |

## Frontend (TypeScript) — temporary

| File | Lines | What | Tear-down action |
|---|---|---|---|
| `frontend/src/lib/stores/conversation.ts` | inside `onMessage`, the enriched `[frame] received` log | Block-summary formatting + `console.log('[frame] received', …)` and the matching `[frame] none` branch | Restore the original one-line `console.log('[frame] received:', { origin, panel, blocks })`. The pre-Phase-2 version is preserved in git history for the file. |
| `frontend/src/lib/stores/display.ts` | inside `setFrame`, after `const panel = frame.panel \|\| 'bottom';` | `console.log('[setFrame] dispatch', …)` block | Delete the block. |

## NOT temporary (keep these)

- `utils/tests/playwright_evals/conftest.py` — the new `console_log` fixture is permanent test infrastructure. Future Playwright tests can use it.
- `utils/tests/playwright_evals/test_phase2_console_capture.py` — frame-roundtrip and pageerror tests are permanent regression coverage.
- `utils/tests/ws_smoke.py` — diagnostic helper. Useful for ad-hoc backend probing; keep around.
- `HUGO_DEBUG_FRAMES` env var support — the env-var gate itself can stay (it's opt-in and silent by default), but the body of the `if os.environ.get('HUGO_DEBUG_FRAMES'):` branch ships the full frame dump and should be deleted along with the rest of the AGENT-FRAME block. Reword: delete the env-var check too unless we explicitly want to keep a documented debug toggle.

## Teardown verification

After deleting:

```
# 0 hits expected
grep -rn "Phase-2 logging" backend frontend

# 0 hits expected
grep -rn "AGENT-FRAME\|PEX-POST-POLICY\|WS-HANDOFF\|HUGO_DEBUG_FRAMES" backend
grep -rn "\[setFrame\] dispatch" frontend

# Existing baseline log lines should still be present
grep -rn "AGENT:" backend/agent.py     # the original log.info(f'AGENT: ...') stays
grep -rn "\\[frame\\] received" frontend/src/lib/stores/conversation.ts   # original one-liner stays
```
