# MEM — Memory Extension Module (the Head)

MEM holds the assistant's **persistent** information — typically uploaded or provided by the user. Its goal
is to **remember facts and retrieve them at the right time** for **pro-active resolution**, so it does **more
reads than writes**.

MEM is a **code-only module** (`backend/modules/mem.py`, class `MemoryExtensionModule`, alias `MEM`), a peer
to [NLU](nlu.md) (the Heart) and [PEX](pex.md) (the Hands) underneath the deterministic Assistant (see
[architecture](../architecture.md)). It has no agent loop — only PEX runs an agent. MEM constructs and owns
its three tier components; the World holds the shared references (`world.context`, `world.prefs`,
`world.knowledge`). The continuous background MEM loop (retrieval running ahead of need, off-turn
compaction) is designed-not-built; today MEM runs synchronously at the end of each turn via `store_turn`.

MEM owns three tiers, a cache hierarchy by scope and durability:

| Tier | Component | Scope | Holds |
|---|---|---|---|
| **L1** | [Context Coordinator](../components/context_coordinator.md) | this session | the append-only event stream of everything that happened |
| **L2** | [User Preferences](../components/user_preferences.md) | per-account | good defaults — conventions, verbosity, style |
| **L3** | [Business Knowledge](../components/business_context.md) | per-client | unstructured uploaded knowledge, retrieved on demand |

## L1 — Context Coordinator

The **append-only event stream** — the durable record of everything that happened this session, the closest
thing the agent has to an objective log. It captures **user** utterances and actions, **agent** utterances
and actions (PEX actions tagged as they fire), and **system** events (some NLU decisions, networking issues,
code errors, anything harness-related). Each turn carries a `turn_id`; flows point at the `turn_id`s they were
active in. A fast-access `recent` window serves prompt context without scanning the full log, and a rolling
summary keeps the window bounded.

## L2 — User Preferences

The closest equivalent to Claude's memory: what the user normally wants — coding conventions, response
verbosity, technical depth. Per-account and persistent, frozen into PEX's system prompt at session start.
Written on onboarding, by explicit configuration, or by promotion of a salient pattern; retrieved by hybrid
embedding / ID lookup. Each
preference is a **typed record** — value plus `endorsed` (user-confirmed vs. agent-guessed), ranked candidate
fallbacks, trigger keywords, and a feedback-updated `confidence` — rendered into the prompt authoritatively when
endorsed and tentatively when guessed; a reserved **caution / risk-tolerance** dial is specified but not yet
wired (see [User Preferences](../components/user_preferences.md)).

## L3 — Business Knowledge

The closest equivalent to RAG: unstructured data the user provides — messages, PDFs, documents — most
commonly used for answering **FAQs**. Per-client, embedded in a shared vector space, and retrieved via an
explicit tool call that pulls ~100 candidates and re-ranks to the top ~10. Cold-start is solved by manual
upload to `agent.md`.

## Skills (one per tier)

MEM exposes one read skill per tier — the tools a PEX sub-agent calls to reach memory. Each takes the params
its store needs:

| Skill | Tier | Signature | Reaches |
|---|---|---|---|
| `recap` | L1 | `recap(n_turns=10, filter=None)` | the Context Coordinator — recent session events |
| `recall` | L2 | `recall(query=None, flow_name=None)` | the User Preferences component — matching preferences for the `query` |
| `retrieve` | L3 | `retrieve(query, top_k=10, documents=[])` | Business Knowledge — candidate retrieval + re-rank (`documents=['faq']` takes the FAQ shortcut) |

Today these are module methods without tool wiring: the orchestrator reaches L1 through
`coordinate_context`, L3 through the `search_documents` tool, and L2 through the frozen prompt snapshot
plus the ambiguity recover path. They get tool surfaces when a flow demonstrably needs them.

## Writing to memory

MEM is **read-mostly**, with three write paths:

- **`store_turn(utterance, prompt_tokens)`** — the end-of-turn store (`take_turn` step 5): record the
  agent turn, bump the turn count, snapshot the stack onto the state and save `state.json` (the record of
  what actually happened — MEM owns the past), then run the compression check.
- **Explicit `store_preference(key, value)`** — writes a preference when the user asks ("remember that I
  prefer X") or onboarding / config seeds one, reached as `world.prefs.store_preference` (PEX has the tool).
  Every write saves to the per-account store `database/memory/<username>.json`, loaded back at construction
  (MEM takes the username in its `__init__`), so L2 survives the session. L3 business knowledge is **not**
  written this way — it arrives by ingestion, manual `agent.md` upload, or promotion.
- **Auto-promotion** — MEM promotes a [Session Scratchpad](../components/session_scratchpad.md) entry to
  L2/L3 via a frequency counter (entry read by ≥N flows, tracked by `used_count`) plus a low-tier LLM-judge
  scoring salience / surprisal, off the turn's critical path. # designed-not-built

MEM never writes the agent's belief: the Dialogue State belongs to [NLU](nlu.md) (code-only; `understand`
writes it), and the `flow_stack` structure belongs to PEX.

## Long-term artifact storage

Each turn produces a [Task Artifact](../components/task_artifact.md). `store_turn` will append it to the
session dir (`artifacts.jsonl`) so the agent's outputs become part of the durable record alongside the
event stream. # designed-not-built

## Pro-active resolution

When the background MEM loop exists (# designed-not-built), retrieval can run ahead of need — surfacing the
right preference or document *before* the user asks. The **push channel** is twofold: MEM **prefetches** likely-needed
entries into its cache so the eventual `recall` / `retrieve` returns instantly, and when it judges an entry
highly relevant it **appends an entry to the [Session Scratchpad](../components/session_scratchpad.md)** — the
existing swarm channel — so PEX sees it without a dedicated pull. There is no separate injection path into
PEX's prompt. The three skills are also how the agent pulls memory on demand:
a sub-agent calls `recap` / `recall` / `retrieve` rather than routing through a separate "Internal" intent
(there is none — see [the intent taxonomy](../components/dialogue_state.md)). Deterministic memory
operations (e.g. a fixed lookup) are plain tools, not flows.
