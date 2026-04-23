# Flow-to-Block Classification

**Purpose.** Source of truth for "does this flow update the Display Container
(return a block), or does it narrate in chat only?" Answered by the user during
Part 4 Phase 3 to stop bad guessing.

**Rough split.** ~26 flows update the UI with a block; ~22 narrate in chat only
(of which 7 are Internal sub-agents that never surface to the user at all).

**"No block" does NOT mean "empty screen."** When a flow narrates in chat, the
DisplayContainer simply doesn't change — whatever was already on screen (most
often the active post card) stays visible. The agent reply lands in chat; the
visual surface stays as-is. So chat-only flows are additive to the conversation,
not a screen-clear.

## Updates the UI (return a block)

| Intent | Flow | Block | Why |
|---|---|---|---|
| Draft | create | card | New post — show what was created |
| Draft | outline (propose) | selection | 3 candidate outlines, user picks one |
| Draft | outline (direct) | card | Saved outline — re-render post |
| Draft | refine | card | Post edited — re-render |
| Draft | compose | card | Prose saved — re-render |
| Draft | add | card | New content inserted — re-render |
| Draft | cite | card | Citation attached — re-render |
| Revise | rework | card | Section reworked — re-render |
| Revise | polish | card | Section polished — re-render |
| Revise | tone | card | Tone shifted — re-render |
| Revise | simplify | card | Section simplified — re-render |
| Revise | remove | card | Section removed — re-render |
| Revise | tidy | card | Post formatted — re-render |
| Revise | audit | selection | Findings rendered as options; picking one triggers the corresponding polish / rework / simplify follow-up |
| Research | find | list | Matching posts |
| Research | browse | list | Tagged posts / notes |
| Research | compare | compare | Two posts side-by-side |
| Research | diff | compare | Two code versions side-by-side |
| Publish | preview | card | Rendered preview |
| Publish | promote | card/toast | Post promoted |
| Publish | release | toast | Publication confirmation |
| Publish | syndicate | toast | Channel-by-channel result |
| Publish | schedule | toast | Schedule confirmation |
| Publish | cancel | toast | Cancellation confirmation |
| Plan | blueprint | list | Multi-item orchestration plan |
| Plan | calendar | list | Multi-item content calendar |
| Plan | digest | list | Multi-part series plan |

## Narrates in chat (no block)

### User-facing chat-only flows

| Intent | Flow | Why |
|---|---|---|
| Draft | brainstorm | Ideas delivered as chat text — no UI panel swap |
| Research | check | Status narration |
| Research | inspect | Metrics narration (data also stored in metadata for downstream consumers) |
| Research | summarize | Summary paragraph in chat |
| Publish | survey | Channel status in chat |
| Plan | triage | Narrates revision sequence |
| Plan | scope | Narrates research plan |
| Plan | remember | Narrates what was recalled |
| Converse | chat | Open chat |
| Converse | preference | Confirmation text |
| Converse | suggest | Suggestion text |
| Converse | explain | Explanation text |
| Converse | endorse | Ack text |
| Converse | dismiss | Ack text |
| Converse | undo | Ack text |

### Internal sub-agents (never user-facing)

| Flow | Notes |
|---|---|
| recap, store, recall, retrieve, search, reference, study | System-only; no UI surface. Policy returns DisplayFrame(flow.name()) with no block. |

## How this is enforced in evals

`utils/tests/e2e_agent_evals.py::_check_level3` checks `expected_block_data_keys`
per step. Steps for flows in the "updates UI" table above carry the expected
block type + required data_keys. Steps for flows in the "narrates in chat" table
do NOT set `expected_block_data_keys` — a step that unexpectedly returns a block
would fail L1 (empty_response check) if the block data is empty, but otherwise
the eval accepts text-only output.
