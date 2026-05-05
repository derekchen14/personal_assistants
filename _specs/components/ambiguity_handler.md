# Ambiguity Handler

The reliability of AI agents is the number one blocker to mass adoption. The best way around this is curated training data, but another method is to make ambiguity handling a first-class citizen — the agent explicitly recognizes when it is unsure, classifies the uncertainty, and decides how to respond. This is likely the most unique core component that differentiates our agent.

## Levels of Ambiguity

Based on levels of grounding uncertainty (Horvitz & Paek, [Grounding Criterion](https://erichorvitz.com/ftp/grounding.pdf)):
1. Uncertainty at conversation
2. Uncertainty at intention
3. Uncertainty at signal
4. Uncertainty at channel

The handler maps these into a **closed set of four levels**, forming a gradient of decreasing uncertainty. The vocabulary is locked — `declare()` rejects any other level. Cite by name; never extend without explicit approval.

| Level | What's unknown | Example | Frame shape |
|---|---|---|---|
| **`general`** | Intent itself is unclear; gibberish; rare in PEX/policy phase | User utterance is too vague to match any flow | empty; RES asks "what are we doing?" |
| **`partial`** | Intent is known, but the key entity is unresolved | "show me the table" with no table grounded; "edit that section" with no post grounded | empty; RES asks "which post / which section?" |
| **`specific`** | Intent and entities are known, but a required slot value is missing or invalid | "Total ARR in a year" with no `country` slot filled | RES asks for the specific value |
| **`confirmation`** | A candidate value exists and needs user sign-off | Agent guesses the post title is "Dancing with Wolves"; agent proposes a 5-bullet outline | optional confirmation block |

"Key entity" is domain-specific — it grounds the conversation to a tangible thing (a table, file, blog post, recipe, etc.). What counts as a key entity is defined in domain config.

## Picking the Level

| When the policy discovers... | Declare | Metadata |
|---|---|---|
| No entity slot filled, no candidate in scratchpad | `general` | none |
| Entity is post/section but `post_id` unresolvable | `partial` | `{missing_entity: 'post'}` |
| Required value slot missing | `specific` | `{missing_slot: <name>}` |
| All electives empty | `specific` | `{missing_slot: <alt1>_or_<alt2>}` |
| Candidate exists needing sign-off | `confirmation` | `{candidate: <value>}` or `{reason: <code>}` |

## Lifecycle

1. **Recognize** — A component detects uncertainty. Two main entry points: NLU during `think()` (before the flow is stacked — cheap to re-route) or PEX during policy execution (flow already active). This is the hardest step — naive models are over-confident.
2. **Declare** — The component calls `declare(level, observation=..., metadata=...)` to record the uncertainty. One clarification per turn — return immediately after declare.
3. **Respond** — Based on the level, the handler determines the response strategy: ask a clarification question, present multiple plausible options, or render UI for gathering feedback.
4. **Resolve** — Uncertainty is cleared when the user provides clarification, the Agent re-routes successfully, or the flow completes. Calls `resolve()` to clear stored values.

## Declare Signature

```python
self.ambiguity.declare(level, observation=<human_text>, metadata=<classification>)
```

- **`level`** — one of the four closed values.
- **`observation`** — natural-language text describing what is uncertain. This is the question the user will be asked, in the policy's own voice. RES naturalizes it for delivery.
- **`metadata`** — classification keys only (`missing_entity`, `missing_slot`, `candidate`, `reason`). Don't stuff `question` / `prompt` / arbitrary prose into metadata — that's what `observation` is for.

```python
# specific — value slot missing
self.ambiguity.declare('specific',
    observation='Which tone should I use, formal or casual?',
    metadata={'missing_slot': 'tone'})

# partial — entity unresolved across alternatives
self.ambiguity.declare('partial',
    observation='Simplify needs either a section or an image to target.',
    metadata={'missing_entity': 'section_or_image'})
```

## State

### Uncertainty Counts

Integer counts per level (general, partial, specific, confirmation). Each `declare()` call increments the count — this can represent distinct ambiguities (e.g. two missing slots) or repeated failures on the same issue (retries). Higher count signals greater severity.

### Public Attributes

After `declare()`, the handler exposes `level`, `metadata`, and `observation` as plain attributes for downstream readers (PEX retry logic, RES `ask()`, debugging tools). These auto-clear at the end of every turn.

## Core Functions

- **`declare(level, observation=, metadata=)`** — record uncertainty (closed-vocab level, free-text observation, classification metadata).
- **`ask()`** — generate the clarification text for delivery; dispatches by level (`general_ask`, `partial_ask`, `specific_ask`, `confirmation_ask`). Each variant naturalizes `observation` against conversation context via the [Prompt Engineer](./prompt_engineer.md).
- **`present()`** — RES helper; returns a renderable description of the unresolved ambiguity (text + optional confirmation block).
- **`needs_clarification()` / `should_escalate()`** — predicates the Agent uses to decide whether to escalate to the user or attempt recovery first.
- **`resolve()`** — clears stored level, observation, metadata.

## Component Interactions

- **NLU `think()`**: Holds confidence over flows within each intent. The first round of slot-filling happens inside `think()`, giving NLU a chance to detect Partial or Specific ambiguity and declare it *before* the flow is stacked. This is good timing — re-routing is cheap. Low overall confidence → General. Entity grounding uncertainty → Partial.
- **NLU `contemplate()`**: When re-routing after a failed flow, the declared ambiguity level + metadata inform re-prediction.
- **PEX**: Policies declare ambiguity when slot review or skill execution surfaces unresolved user intent. Typically Specific or Confirmation, since the flow is already active.
- **RES**: When the Agent escalates, RES calls `present()` / `ask()` and renders the clarification to the user.
- **Prompt Engineer**: Naturalization of `observation` into the final user-facing question runs through the engineer's `skill_call` path.
- **Dialogue State**: Stores top-N confidence scores for logging and debugging. Does not automatically trigger the handler — NLU and policies own that decision.
