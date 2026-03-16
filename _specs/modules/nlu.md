# NLU — Natural Language Understanding

Historically, this role was called dialogue state tracking. In this architecture, the tracking is split: NLU owns detection and routing, while the [Dialogue State](../components/dialogue_state.md) component owns storage and belief tracking. NLU routes user requests toward up to 64 flows per domain.

**Module principle**: NLU processes information and produces a new DialogueState per new flow detected (Note: when the detected flow is the same as the previous flow, the existing state can simply be carried over). A new state is created and inserted into World for each new flow; carryover reuses the existing state on continuation.
  - React function: a fast instinctual response without hesitation; used for action turns where the DAX is already known (confidence is strictly greater than 0.95). Skips Steps 1–2 but still runs slot-filling.
  - Think function: a standard response that can handle ambiguity
  - Contemplate function: a slower more deliberate response for thinking deeper; usually gets called when PEX encounters ambiguity, rather than in direct response to a user

**Turn type invariant**: Every turn has an utterance. Utterance turns carry the user's typed message. Action turns (button clicks, menu selections) carry auto-generated text in the form `<action>description of the action</action>`. This preserves a complete, parseable conversation history. Turn type is detected from the `<action>` prefix — there is no separate action parameter. A turn also optionally carries a `dax` (bypasses Steps 1–2) and a `payload` dict (pre-fills slots before any LLM call).

## Think Function

Called on every **user utterance**.

- **Input**: World (provides context coordinator, state history), ambiguity handler, prompt engineer, domain config
- **Output**: Latest `DialogueState` inserted into World — predicted intent, detected flow, confidence scores, and partially filled slots

Ambiguity is not a discrete step — it is an object passed through all steps. Any step can call `declare()` on the ambiguity handler at any time if it detects uncertainty.

### Pre-Hook: `prepare()`

Cheap heuristic checks that run before spending tokens on detection. On failure, notify the Agent (lighter-weight path — no flow stacked, no ambiguity handler), who passes the rejection to RES for a user-facing message.

Specific checks:

1. **Empty input**: Reject
2. **Min length**: 2 characters after whitespace trimming (allows "ok", "no"; rejects single characters)
3. **Max length**: 1024 tokens
4. **Exact repeat**: Reject if identical to the previous user utterance
5. **Known command shortcuts (Tier 0)**: Regex-based rules that bypass NLU entirely — map directly to the target flow with score 1.0. Fast, accurate, but limited in scope. Dev mode (forcing a specific dax) is handled by the frontend, which strips the `/DAX` prefix and sets the `dax` field explicitly — the backend never sees raw slash commands.
6. **System-reserved keywords / special tokens**: Reject to prevent prompt injection
7. **Unsupported language**: Reject via basic heuristic rules

### Step 1 — Intent Prediction

Single call to Claude Sonnet. Predicts one of 6 user-facing intents:

- **2 universal**: Plan, Converse
- **4 domain-specific** (verb forms): Read, Prepare, Transform, Schedule

The **Internal** intent is never predicted by NLU — it is triggered directly by the Agent for system housekeeping.

### Step 2 — Flow Detection (Majority Vote)

Every intent (including Converse and Plan) has flows. Each flow has a standardized name (**dact** — dialog act) and a 3-digit hex ID (**dax**). Dacts and dax codes are defined in domain config (see [Configuration](../utilities/configuration.md)).

**Candidate set**: All flows from the predicted intent, plus configurable **edge flows** from adjacent intents (defined per-intent in domain config, based on historical confusion patterns).

**Prompt context**:

- Conversation history from Context Coordinator (`context.compile_history(turns=5)`)
- Candidate dacts with descriptions
- Active flow state (strong signal to continue current flow)
- Domain context from config

**Multi-model majority vote** (3 escalating rounds). Each model returns a ranked top-N list of dact names. Models within each round run in parallel; if a model fails or times out, skip it and check majority among the rest.

| Round | Models | Agreement needed |
|---|---|---|
| 1 | Claude Sonnet + Gemini Flash | 2/2 agree on top-1 |
| 2 | + Claude Opus + Gemini Pro | 3/4 agree on top-1 |
| 3 | + Claude Opus (extended thinking) | 3/5 agree on top-1 |

If no majority after round 3 → declare **General** ambiguity via the ambiguity handler.

> **Note**: If Gemini API integration exceeds 1 day of Prompt Engineer work, replace Gemini models (Flash, Pro) with ChatGPT equivalents.

#### Flow Deduplication

After flow detection, check whether the detected flow already exists on the stack in a **Pending** or **Active** state. If it does, **carry over** — continue with the existing flow rather than creating a new one. This prevents duplicate flows on the stack and naturally handles multi-turn interactions where the user continues working on the same task.

If the detected flow is not on the stack (or only exists in Completed/Invalid state), create a new flow and push it onto the stack.

### Step 3 — Slot-Filling

Runs only for **domain-specific intents** (Read, Prepare, Transform, Schedule). Converse and Plan skip this step.

Slot-filling is two-phase:

1. **Payload phase**: Pre-filled grounding context from the turn's `payload` dict is mapped directly into the flow's slots before any LLM call. Entity fields (`highlight→note`, `post→post`, `section→sec`, `channel→chl`) are merged into a single SourceSlot entity. The payload is consumed here and never stored on DialogueState.
2. **LLM phase**: If required or elective slots are still unfilled after the payload phase, a single Sonnet call extracts remaining slot values from the conversation history. Skipped entirely if the payload phase already satisfies all required slots.

Ambiguity can be declared at any point if a required slot cannot be resolved.

Plan flows are composed of other selectable flows and enable interactive multi-turn planning (similar to Claude Code's plan mode). Plan flows can technically nest other Plan flows for extra complexity, but this should be avoided.

### Post-Hook: `validate()`

Validates and repairs the mutated dialogue state before returning:

1. Detected flow exists in the domain's dact registry
2. Filled slots match the flow's slot schema
3. No duplicate flows on the stack
4. Confidence scores are well-formed
5. **Entity repair** (domain-specific): Attempt to fix malformed entity references — e.g., case normalization (lower/upper/title), nearest lexical match for misspelled names, column validation with LLM-assisted repair (up to 3 attempts). Specific repair strategies vary by domain.

## Contemplate Function

Re-routes when the initial detection fails. Called by the Agent after a flow encounters a hard failure and the ambiguity handler has been engaged.

- **Input**: Context coordinator, dialogue state (with filled slots from failed flow), ambiguity handler (with declared ambiguity level + metadata), domain config
- **Output**: Mutated dialogue state pointing to a different flow

**Single Claude Opus call** with a narrowed search space:

- **Exclude** the failed flow
- **Restrict** to related flows using the ambiguity metadata
- **Trust region**: The first detected flow acts as a prior. The posterior (re-detected flow) typically does not deviate far — like a trust region in optimization. Having already selected a flow provides information gain that narrows the likely fallback candidates.

## React Function

Unlike user utterances, **user actions** have no uncertainty, so we can act on them with full confidence. We still want to document the intents and flows, so we go through a lightweight version called the 'react' function.

React skips Steps 1–2 (intent prediction and flow detection) since the DAX is already known. It still runs slot-filling (Step 3): the payload typically provides the grounding context, and an LLM slot-fill call runs only if required slots remain unfilled after the payload phase.
