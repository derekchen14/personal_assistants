# Ambiguity Handler

The reliability of AI agents is the number one blocker to mass adoption. The best way around this is curated training data, but another method is to make ambiguity handling a first-class citizen — the agent explicitly recognizes when it is unsure, classifies the uncertainty, and decides how to respond. This is likely the most unique core component that differentiates our agent.

## Levels of Ambiguity

Based on levels of grounding uncertainty (Horvitz & Paek, [Grounding Criterion](https://erichorvitz.com/ftp/grounding.pdf)):
1. Uncertainty at conversation
2. Uncertainty at intention
3. Uncertainty at signal
4. Uncertainty at channel

The handler maps these into four actionable levels, forming a gradient of decreasing uncertainty:

| Level | What's unknown | Example |
|---|---|---|
| **General** | Intent is unclear; unknown dialog act or general error | User utterance is too vague to match any flow |
| **Partial** | Intent is known, but the key entity is unresolved | Data analysis: table / row / column / metric; Coding: folder / file / function / line number |
| **Specific** | Intent and entities are known, but a slot value is missing or invalid | "Total ARR in a year" — an operation is not possible on this metric; agent knows we want to fill the "country" slot but doesn't have a value |
| **Confirmation** | A candidate value exists and needs user sign-off | Agent guesses the title should be "Dancing with Wolves"; agent guesses the country should be "France" |

"Key entity" is domain-specific — it grounds the conversation to a specific tangible thing (a table, file, blog post, recipe, etc.). What counts as a key entity is defined in domain config.

## Lifecycle

1. **Recognize** — A component detects uncertainty. Two main entry points: NLU during `think()` (before the flow is stacked — cheap to re-route) or PEX during policy execution (flow already active). This is the hardest step — naive models are over-confident.
2. **Declare** — The component calls `declare()` to record the uncertainty level, set generation flags, and store metadata.
3. **Respond** — Based on the level, the handler determines the response strategy: ask a clarification question, present multiple plausible options, or provide UI for gathering feedback.
4. **Resolve** — Uncertainty is cleared when the user provides clarification, the Agent re-routes successfully, or the flow completes. Calls `resolve()` to clear stored values.

## State

### Uncertainty

Integer counts per level (general, partial, specific, confirmation). Each `declare()` call increments the count — this can represent distinct ambiguities (e.g. two missing slots) or repeated failures on the same issue (retries). Higher count signals greater severity.

- **general** — no clue what is going on, high uncertainty in intent or dialog act
- **partial** — know the dialog act, but not the grounding details (e.g. tables, columns, metrics)
- **specific** — the flow has a missing slot to fill (e.g. target, metric, category)
- **confirmation** — have a candidate slot value (e.g. removal column), but want to confirm

### Observation

Option to specify the clarification question at the point the issue arises.

### Metadata

Supporting details stored for generating the question. Key-value pairs cleared at the end of every turn. Not touched directly by the developer — accessed through methods. The active flow and slot are already in dialogue state; metadata is for other supporting context.

### Generation

Boolean flags specifying whether an extra LLM call is needed. Three modes:

- **[Lexicalize](https://en.wikipedia.org/wiki/Deep_structure_and_surface_structure)** — translate a template with variables into a surface form
    - Suppose the conversation so far

    > User: How many active users do we have in Mexico?
    Agent: Do you mean daily, weekly, or monthly?
    User: Daily

    - Also, we have a template stored as an observation: `There are <metric count> <metric name> in <dimension>.`
    - We also have the following metadata: `{'DAU': 236, 'MAU': 1835}`
    - Then, the LLM should return something like: "There are 236 daily active users from Mexico."

- **Naturalize** — rewrite an utterance to sound natural given conversation history
    - Suppose the conversation so far

    > User: What's the conversion rate according to our Mixpanel import?
    Agent: The conversion rate for the Thanksgiving Sale campaign is 17.6%
    User: What about for the Black Friday Deals campaign?

    - Given the observation: "There are 23.6% conversion rate in Black Friday Deals"
    - We would like to return something like: "The conversion rate for the Black Friday campaign is 23.6%"

- **Compile** — summarize the metadata context along with any observation into a better response
    - Often used when there has been re-routing and session scratchpad
    - Suppose the conversation so far

    > User: How many leads did we get last week?
    Agent: We generated 1,757 sales leads last week.
    User: That's a big increase, any idea why that happened?

    - Given the metadata:

    > The mix shift changed from Google Ads to TikTok in May
    The most popular advertising platform is still Subscriber Referrals
    Subscriber Referrals went from to 833 leads to 859 leads
    Google Ads went from 574 leads to 561 leads
    Tiktok when from 180 leads to 334 leads

    - We would like to return something like: "Tiktok provided a major boost where it almost doubled, going from 180 to 334 leads."

## Core Functions

- **Declare** — fills uncertainty level, generation flags, and basic metadata
- **Ask** — triggers generation of the clarification based on latest information; dispatches by level: `general_ask`, `partial_ask`, `specific_ask`, `confirmation_ask`
- **Generate** — triggered if any generation flags are true; executes LLM call(s) via [Prompt Engineer](./prompt_engineer.md)
- **Resolve** — clears stored values in metadata and uncertainty

## Component Interactions

- **NLU `think()`**: NLU holds a confidence distribution over flows within each intent (~7 intents × ~9 flows each). The first round of slot-filling happens inside `think()`, which gives NLU a chance to detect Partial or Specific ambiguity and declare it *before* the flow is stacked. This is good timing — the flow hasn't been committed to yet, so re-routing is cheap. Low overall confidence → General ambiguity. Entity grounding uncertainty → Partial.
- **NLU `contemplate()`**: When re-routing after a failed flow, the ambiguity handler is an input — `contemplate` uses the declared ambiguity level and metadata to inform re-prediction.
- **PEX**: Policies declare ambiguity when execution or recovery fails (see [Flow Stack § Failure Recovery](./flow_stack.md)). Typically Specific or Confirmation level, since the flow is already active and partially executed.
- **RES**: When the Agent escalates, RES renders the clarification question or options to the user.
- **Prompt Engineer**: Generation modes (lexicalize, naturalize, compile) execute LLM calls via the [Prompt Engineer](./prompt_engineer.md)'s generic prompt interface.
- **Dialogue State**: Stores top-N confidence scores for logging and debugging. Does not automatically trigger the handler — NLU owns that decision based on the confidence distribution.
