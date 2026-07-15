# Phase 6 — Staging

Verify the agent works end-to-end with hard-coded test flows before investing in policies and prompts. This phase catches integration bugs early and proves the full turn (the main Agent driving PEX, which consults NLU and MEM) is functional.

## Context

After Phase 5, the agent has all 9 components and 3 module-loops implemented, but nothing has been tested as a system. Staging exercises the full turn with canned responses, confirming that the server boots, WebSocket connects, and the agent responds to messages. This is the cheapest point to find and fix integration issues.

**Prerequisites**: Phase 5 complete — all components, modules, and Agent orchestrator are implemented.

**Outputs**: Bootable server, WebSocket smoke tests passing, canned responses for core flows.

**Spec references**: [server_setup.md](../utilities/server_setup.md), [configuration.md](../utilities/configuration.md)

---

## Steps

### Step 1 — Verify Server Boots

Ensure the server starts without errors:

```bash
cd <domain> && ./init_backend.sh   # tab 1
cd <domain> && ./init_frontend.sh  # tab 2
curl localhost:<port>/api/v1/health   # → {"status": "ok"}
```

Fix any import errors, missing `__init__.py` files, or configuration issues that prevent startup.

### Step 2 — Lazy LLM Client

The server must boot even without an API key. Use a lazy property pattern:

```python
@property
def client(self) -> anthropic.Anthropic:
    if self._client is None:
        if not self._api_key:
            raise RuntimeError('ANTHROPIC_API_KEY not set.')
        self._client = anthropic.Anthropic(api_key=self._api_key)
    return self._client
```

The client is only instantiated when an LLM call is actually made.

### Step 3 — Unsupported Flow Handling

Unsupported flows (those without real policy implementations yet) are handled inside PEX:
- **PEX**: Detects unsupported flows from the `_UNSUPPORTED` set, completes the flow via `complete_flow` with `{'unsupported': True}`, and carries over the previous artifact. PEX composes the user-facing message ("That feature isn't supported yet…") directly over the TaskArtifact via its voice Skill, which the main Agent delivers.

No `_CANNED` dict — all flows either execute real policies or go through the unsupported path.

### Step 4 — Environment and Keys

- Shared API keys live in `shared/.keys` (not committed to git)
- `init_backend.sh` sources `shared/.keys` before `.env`
- `.gitignore` includes `.keys`, `.env`
- Each domain runs on its own port (starting at 8000, incrementing by 1)

### Step 5 — WebSocket Smoke Test

Test the full round-trip: WebSocket connect → send username → receive greeting → send messages → receive responses.

```
1. WS /api/v1/ws → connect (no auth required)
2. Send {"username": "testuser"} → receive greeting
3. Send {"text": "Hello"}      → receive canned chat response
4. Send {"text": "status"}     → receive canned status response
5. Send {"text": "what next?"} → receive canned next response
```

All 3 messages must receive non-error responses.

### Step 6 — Config Validation

Verify the config loader successfully:
1. Finds and loads `shared/shared_defaults.yaml`
2. Finds and loads `schemas/<domain>.yaml`
3. Merges with section-level override
4. Validates all required sections present
5. Returns a deeply frozen `MappingProxyType`

---

## File Changes Summary

| Action | File | Description |
|---|---|---|
| Modify | `<domain>/backend/modules/pex.py` | Add `_UNSUPPORTED` set for unimplemented flows |
| Modify | `<domain>/backend/components/prompt_engineer.py` | Lazy client property |
| Modify | `<domain>/init_backend.sh` | Source `shared/.keys` before `.env` |
| Create | `<domain>/schemas/__init__.py` | Package init (if missing) |

---

## Logging Conventions

Every turn logs structured diagnostics to `stdout` via the `logging` module.

### After NLU

```
flow_name {dax}  confidence=0.XX  slots={...}
```

`flow_name {dax}` is the canonical format for dialogue state — the recognized flow and its dialogue act.

### After Each PEX Round

```
  pex round=N
```

Indented to nest under the NLU line. Logs after every round of the PEX loop.

### After PEX Loop (Tools + Artifact)

```
  tools=[tool1, tool2]
  artifact=card  source=sql
```

Only logged when present — no empty lines for turns without tools or artifacts.

### Level

All turn diagnostics use `INFO`. Reserve `WARNING` for recoverable issues (self-check failures, fallbacks) and `ERROR` for unrecoverable failures.

---

## Verification

- [ ] Server boots on assigned port without errors
- [ ] `GET /health` returns `{"status": "ok"}`
- [ ] Server boots without `ANTHROPIC_API_KEY` set
- [ ] Config loads and validates successfully
- [ ] WebSocket connects without auth
- [ ] Username greeting is received after sending username
- [ ] Unsupported flows return "not supported yet" message (PEX artifact, delivered by the main Agent)
- [ ] Supported flows execute real policies and return TaskArtifacts
- [ ] `.keys` file is not tracked by git
- [ ] Main Agent's turn runs PEX (consulting NLU + MEM) end-to-end
- [ ] PEX chains multiple flows in one turn
- [ ] Self-check gate catches intent drift and empty responses
