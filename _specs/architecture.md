# Outline

Assistant - module (code), agent [run] (LLM)
  Natural Language Understanding (NLU)
    Dialogue State [read, write]
      Intent [classify] - Research, Draft, Revise, Publish, Converse, Clarify, Plan, Continue
      Flow [detect] - find, inspect, summarize, compare, outline, compose, refine, brainstorm, rework, write, audit, propose, release, schedule, cite, chat
      Slot [fill] - required, elective, optional
        Entity (used for grounding) - post (post), section (sec), snippet (snip), channel (chl), verified (ver)
    Ambiguity Handler - present, absent
      Level - general, partial, specific, confirmation
      Recognize [declare]
      Recover
      Resolve [ask]
    NLU Agent [react, think, contemplate]
      Ensemble [vote] - confidence
      Tools [call]
      Skills
  Policy Execution (PEX) - policy (code), sub-agent [run] (LLM)
    Workflow Planner
      FlowStack [stackon, fallback, update, pop] - Pending, Active, Completed, Invalid
      Policy [prepare, execute, verify]
        Violation - failed_to_save, scope_mismatch, missing_reference, parse_failure, empty_output, invalid_input, conflict, tool_error
      TaskArtifact [deliver] - Part, Block
    Session Scratchpad
      Entry [amend, append, prune] - conforming, nonconforming
    PEX Agent
      Tools [call]
      Skills
  Memory Extension Module (MEM) - three levels
    Context Coordinator (L1)
      Turn [add] - utterance, action
    User Preferences (L2)
      Record [store] - endorsed, predicted
    Business Knowledge (L3)
      Document [retrieve, rerank]
    MEM Agent
      Pre: []
      Tools [call]
      Skills - recap, recall, retrieve
  World
    Session
Infrastructure
  Utilities
    Prompt Engineer [call, parse, retry]
      Family - Claude, Gemini, GPT, Together
      Tier - low, med, high
    Disk Storage
      state.json [save]
      scratchpad.jsonl
      history.jsonl
    Ontology
      Dact / Dax / Flow
      Edge Flows
    Configuration (config)
  Evaluation Suite - three tiers
    Model Unit Tests (tests)
      Deterministic Tests
      Model Tests
    Observability Traces (traces)
      Trajectory [record, replay] - approved, unapproved
      Tolerance
    E2E Agent Evals (evals)
      Scenario [run] - completed, incomplete, successful, unsuccessful
      Oracle [compare]
      Judge
    Corpus - train, dev, test
  User Interface
    Panels
      Left - dialogue container
      Top - top display container
      Bottom - bottom display container
    Building Blocks [render]
      Type - card, compare, selection, list, grid, checklist, confirmation, toast

# Assistant Architecture

This document is the vocabulary map for the assistant, organized by the Outline above. It names the
modules, the components they own, the objects those components contain (nouns), the actions allowed
on them (verbs), and their statuses (adjectives). Detailed behavior belongs in the linked
component specifications.

Vocabulary is a binding contract. **Always** use an existing noun, verb, or status over a synonym.
**Never** invent new terms or concepts unless explicitly instructed. Needing a new term is a signal
to stop and find the existing rule that covers the scenario, not to coin the term. Verb ownership:
**agents and sub-agents run; policies execute; tools are called.**

## Assistant

The Assistant is the top-level turn owner. Every module pairs deterministic **code** with an LLM
**agent**. A turn is: open the session, insert the User turn, NLU forms belief, PEX acts and
replies, MEM stores the turn, deliver the reply and Task Artifact. The Assistant handles I/O and
failure containment; it never classifies, manages flows, executes policy work, or writes records.

## Natural Language Understanding (NLU)

[NLU](./modules/nlu.md) forms the assistant's structured belief about what the user wants. NLU
exposes no public methods: its work is reached through the two components it owns — the Dialogue
State and the Ambiguity Handler — via the World.

### Dialogue State [read, write]

The [Dialogue State](./components/dialogue_state.md) is the single source of truth for belief.
`read_state` returns the serialized belief; `write_state` is the single writer of `state.json`
(`manage_flows` actions delegate to it; stack actions write through the live FlowStack).

| Object | Meaning |
|---|---|
| **Intent** [classify] | The broad category — the eight options in the Outline. Continue selects the Active flow. |
| **Flow** [detect] | The unit of work — the 16 flows in the Outline (`plan`/`clarify` are placeholders). |
| **Slot** [fill] | A typed value a flow needs or may use. Priority: `required`, `elective`, or `optional`. |
| **Entity** | The domain object in the grounding slot — `post`, `sec`, `snip`, `chl`, `ver`. |

### Ambiguity Handler — present, absent

The [Ambiguity Handler](./components/ambiguity_handler.md) stores unresolved uncertainty. An
ambiguity is not a flow status and does not imply policy failure; a tool failure is a policy
violation, not an ambiguity.

| Object / Action | Meaning |
|---|---|
| **Level** | `general` (intent/flow), `partial` (entity), `specific` (non-entity slot), `confirmation` (approval). |
| **Recognize** [declare] | Store a level, observation, and metadata; repeats merge additively. |
| **Recover** | Attempt internal resolution from preferences and the scratchpad before asking the user. |
| **Resolve** [ask] | Ask the level-specific clarification when recovery fails; clear the uncertainty once answered. |

### NLU Agent [react, think, contemplate]

The NLU Agent is the LLM half of NLU, with three modes: `react` (a known dax and UI payload),
`think` (an utterance — detect the flow, fill its slots, write belief), and `contemplate` (re-route
after a failed flow, excluding it). Detection always precedes slot-filling: when detection matches
the incomplete Active flow, NLU fills that same flow; when it selects a different flow, the
ordinary `stackon` applies.

| Object | Meaning |
|---|---|
| **Ensemble** [vote] | Voters are polled and votes tallied; **confidence** is the agreement score. |
| **Tools** [call] | Bounded operations available to the agent. |
| **Skills** | Instructions the agent follows for a mode's task. |

## Policy Execution (PEX)

[PEX](./modules/pex.md) owns acting: it reads belief, manages flows, executes policies through the
runtime, and composes the reply. The pairing is **policy** (code) and **sub-agent** (LLM): every
flow is agentic, and a sub-agent runs with isolated context and only its flow's tools. Sub-agents
cannot create another nesting level.

### Workflow Planner

The [Workflow Planner](./components/workflow_planner.md) is PEX's activity for selecting, ordering,
and managing flows.

**FlowStack** [stackon, fallback, update, pop] — the bounded, ordered collection of flow entries,
with statuses **Pending, Active, Completed, Invalid**:

| Action | Meaning |
|---|---|
| `stackon` | Place a flow on top; the flow beneath reverts to Pending. `active=false` queues it. |
| `fallback` | Mark the top flow Invalid, place the replacement, run it. |
| `update` | Change slots, stage, or status on any flow by name; `status='Active'` re-runs it. |
| `pop` | Remove Completed and Invalid entries; a Pending flow this promotes to Active is run. |

Stacking and fallback hand matching slot values to the new flow unless an ambiguity is open.
A turn ends with an empty stack or an incomplete Active top — never a Pending top. A Plan is an
ordered use of existing flows (there is no Plan flow or policy): later steps queue with
`stackon(active=false)`, and PEX judges after each result whether the user's goal has been met.

**Policy** [prepare, execute, verify] — the code that performs one flow: prepare the setup before
work, execute the sub-agent with its skill and tools, verify the artifact and persisted effects
after. A policy classifies its failures with the closed **Violation** vocabulary:
`failed_to_save`, `scope_mismatch`, `missing_reference`, `parse_failure`, `empty_output`,
`invalid_input`, `conflict`, `tool_error`. A failed tool call returns a corrective error
(`_success=False` with `_error` and `_message`); violation codes are not lifecycle states.

**TaskArtifact** [deliver] — a policy's structured output; PEX combines the turn's artifacts into
the one artifact the Assistant delivers. A **Part** is an A2A content container holding exactly one
of text, raw, url, or data; a **Block** is a visual unit for the frontend. They are not synonyms.
New attributes and new block types require explicit approval.

### Session Scratchpad

The [Session Scratchpad](./components/session_scratchpad.md) is the session-scoped working ledger
shared by PEX, policies, NLU, and MEM, stored as `scratchpad.jsonl`.

**Entry** [amend, append, prune] — one scratchpad line; every item is an entry. Required fields:
`origin` (the flow or stable topic, stamped by code), `version`, `turn_number`, and `used_count`,
plus the flow-specific payload. A completion entry is an ordinary entry whose payload includes
`summary` and `metadata`. An entry is `conforming` or `nonconforming`; NLU's review repairs or
prunes nonconforming entries at its turn point.

### PEX Agent

The PEX Agent runs the bounded loop for one turn: read belief, commit to one of the eight Intent
options, apply Workflow Planner actions through `manage_flows`, and end the turn with plain text —
the reply. Its **Tools** [call] are the planner surface plus narrow component surfaces (belief
read, scratchpad, preferences, ambiguity ask/recover) and a small read-only domain allowlist;
every domain write goes through a flow. Its **Skills** carry the planner and reply guidance.

## Memory Extension Module (MEM)

[MEM](./modules/mem.md) owns persistent information and retrieval across three Levels. MEM items
are **records**; the Session Scratchpad holds **entries** — the two nouns never mix. L1/L2/L3 name
memory Levels only; Evaluation Suite tiers use names, not these codes.

| Level | Component | Scope | Content |
|---|---|---|---|
| **L1** | Context Coordinator | Session | Turns and checkpoints. |
| **L2** | User Preferences | Account | User defaults and preferences. |
| **L3** | Business Knowledge | Client | Uploaded documents and retrieved knowledge. |

### Context Coordinator (L1)

The [Context Coordinator](./components/context_coordinator.md) is the append-only event stream for
the session and the single source of truth for the conversation. A **Turn** [add] is one event —
`utterance` or `action` — with a `role` (user, agent, system; a **speaker** on an utterance, an
**actor** on an action), a `turn_id`, and a `content` dict that always carries `text`. A
**checkpoint** [save] is a system action (a named marker at a position in the stream), never a
turn type; a *snapshot* is a passive copy of state (`state.json`), and the two never mix. Flows
hold `turn_ids` pointing at their turns.

### User Preferences (L2)

[User Preferences](./components/user_preferences.md) stores typed per-account defaults. A
**Record** [store] is `endorsed` (explicitly confirmed, authoritative) or `predicted` (inferred,
tentative).

### Business Knowledge (L3)

[Business Knowledge](./components/business_context.md) stores per-client unstructured knowledge. A
**Document** [retrieve, rerank] is uploaded knowledge (a PDF, message collection, FAQ); retrieval
gathers candidate passages and reranks the most relevant. New knowledge arrives through ingestion,
never through `store_preference`.

### MEM Agent

The MEM Agent's **Skills** are the three reads — `recap` (L1), `recall` (L2), `retrieve` (L3) —
plus the stores: `store_turn` (record the turn, save state, run the compaction check) and
`store_preference`. Memory work is not an intent; fixed lookups are **Tools** [call].

## World

The **World** is the shared component container: it constructs the components, opens a **Session**,
and exposes the one live instance of each (Dialogue State, FlowStack, Ambiguity Handler, Session
Scratchpad, Context Coordinator, User Preferences, Business Knowledge). Module ownership says who
may change a component; World ownership says where the shared reference lives.

## Infrastructure

Deterministic code and shared services surrounding the assistant.

### Utilities

**Prompt Engineer** [call, parse, retry] — the provider-agnostic model interface used by all
modules. Callers name a **Family** (Claude, Gemini, GPT, Together) and an abstract **Tier** (`low`,
`med`, `high`), never a concrete model id. It owns model selection, prompt caching, retry/backoff,
structured-output parsing, and token-usage logging.

**Disk Storage** — the per-session files: `state.json` (Dialogue State plus the serialized
FlowStack copy), `scratchpad.jsonl` (Session Scratchpad entries), and `history.jsonl` (the
Context Coordinator's turn stream; the model-shaped message list is a projection computed from
it, never stored). The owning component determines who may write each file.

**Ontology** — the structural vocabulary in `ontology.py`: intents, flows, ambiguity levels,
lifecycle values, and the dialogue-act system. A **Dact** is one atom of that system (a verb, noun,
or adjective); a **Dax Code** is the stable hexadecimal id composed from a flow's dacts, digits in
dact positional order (verb → noun → adjective). **Edge Flows** name each flow's likely neighbors
for candidate narrowing.

**Configuration** (config) — tunable runtime settings in YAML, loaded once, validated, and frozen:
it cannot change during the process lifetime, and a validation failure stops the assistant from
starting.

### Evaluation Suite — three tiers

The [Evaluation Suite](./utilities/evaluation_suite.md) sits outside the assistant and proves
behavior through a ladder of three tiers — shorthand **tests**, **traces**, **evals**. The
**Corpus** is the labelled conversations in `train`, `dev`, and `test`. `run_suite.py` is the
entry point; with no flags it runs the deterministic tests plus a sampled eval pass that records
traces during the same live run.

**Model Unit Tests** (tests) — **Deterministic Tests** (contract checks, no model call) and
**Model Tests** (one model decision in isolation: flow detection, slot filling, entity extraction).

**Observability Traces** (traces) — a **Trajectory** [record, replay] is the ordered sequence of
tool calls, key arguments, results, flow statuses, and completion entries; it is `approved` (a
replay baseline) or `unapproved`. **Tolerance** names the approved variation that does not count
as regression.

**E2E Agent Evals** (evals) — a **Scenario** [run] is a full multi-turn task, scored `completed`
or `incomplete` (reached a final answer) and `successful` or `unsuccessful` (achieved the goal).
The **Oracle** [compare] holds the expected end state, grounding, actions, artifact, and reply;
the **Judge** assesses reply quality and faithfulness against a rubric. End-state and grounding
breaks are hard failures; latency is measured but not a gate.

### User Interface

The frontend owns rendering; the assistant never reasons about viewport or device state.

**Panels** — `Left` (the dialogue container), `Top` and `Bottom` (the display containers).

**Building Blocks** [render] — the visual units PEX and policies select data for. The closed
**Type** vocabulary is `card`, `compare`, `selection`, `list`, `grid`, `checklist`,
`confirmation`, and `toast` (toast uses the transient drawer).

## Banned words

Do not turn incidental prose into new object types or control actions. In particular:

- **dispatch** — tools are **called**; agents and flows **run**; policies **execute**;
- **bind** — NLU **fills** slots;
- **stalled** — say **incomplete Active flow**;
- **activate** as a planner action — activation (promoting a flow Pending→Active and kicking off
  its policy) belongs to the runtime alone, never to `manage_flows`;
- **detour**, **staged**, **demote** — a different flow is simply placed with `stackon`, the flow
  beneath reverts to Pending, and the turn-end invariant (never a Pending top at the boundary)
  keeps the stack clean; none of the three needs a name;
- **acting loop**, **belief note** — say the **PEX Agent** and the **belief** it reads;
- **frame** — the object is the **Task Artifact**;
- **record** for a scratchpad item — **records** are MEM's noun; the scratchpad holds **entries**;
- **gate** - when there is branching, describe the actual logic rather than saying it is a gate

## Designed, not built

Future work that reuses this vocabulary when it lands; none of it justifies a new term today:

- background MEM retrieval and prefetch;
- automatic scratchpad promotion to L2/L3, semantic merging, eviction, and cap enforcement;
- a caution/risk-tolerance preference dial;
- long-term `artifacts.jsonl` storage;
- concurrent policy execution (a contiguous block of Active flows); the current runtime executes
  policies sequentially;
- TypeSafe as a non-LLM detection family (registered in the tier table, unwired).
