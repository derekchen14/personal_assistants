# Agent Landscape (May 2026)

A survey of agent-building platforms to answer one strategic question:

> Is Assistant Factory inventing genuinely new primitives, or are we
> reinventing wheels that already exist in Claude Agent SDK, OpenAI Agents
> SDK, AWS Strands, and the rest? If we're reinventing some wheels, which
> ones should we drop? If we're inventing new ones, which are the moat?

The doc is structured as: framing and criteria, a layered map of where every
framework fits, the categorized landscape, deep dives on the 10 most relevant
frameworks (with an explicit *ambiguity handling* axis), and a candid answer
to the wheel-reinvention question.

---

## Selection Criteria

Three criteria, narrower than the prior cut:

1. **Ambiguity / uncertainty handling.** Does it have a first-class concept of
   "the user was unclear, ask for clarification before acting"? This is AF's
   core differentiator. Almost nothing has this.
2. **Architectural similarity to AF.** Does it make the same commitments —
   explicit dialogue control, persistent state, conversational focus, slot or
   slot-equivalent concepts?
3. **Popular enough that we should know about it.** Either widely adopted, or
   from a major lab (Anthropic, OpenAI, Google, Amazon, Microsoft, Nvidia).

These three filters reduce a 60+ option landscape to the 10 frameworks worth
deep-diving, plus a handful of coding-adjacent and infrastructure entries.

---

## How to Read the Deep Dives

Each entry is scored on the same 9 axes so we can compare apples to apples:

1. **Positioning** — who is this for, what's the canonical use case?
2. **State model** — how is dialogue/task state represented across turns?
3. **Control flow** — how is "what to do next" decided?
4. **Memory** — short-term and long-term.
5. **Tools** — schema source, registration, execution, auth model.
6. **Ambiguity / clarification** — first-class concept or LLM-honor-system?
7. **Evaluation surface** — what's measurable?
8. **Tradeoff** — what does this give up to get its strength?
9. **AF takeaway** — concrete idea (or anti-pattern) to adopt or avoid.

The *ambiguity* axis is the one that will repeatedly say "none" and that is
the point — AF's approach to confidence-driven clarification is rare in
productized frameworks and only just emerging in the academic literature.

---

## The Layered Map

Where every framework sits in the agent-tooling stack. AF needs to know which
layer it's in and which layers it should consume rather than rebuild.

```
L0 — Models                Claude, GPT, Gemini, Llama, DeepSeek, Qwen, Gemma
                           (provider APIs, native tool calling, reasoning)

L1 — Agent SDKs            Claude Agent SDK, OpenAI Agents SDK, Google ADK,
                           AWS Strands, Pydantic AI
                           (thin abstraction over L0 models, tool-call loops,
                           handoffs, sessions, basic memory)

L2 — Orchestration         LangGraph, Microsoft Agent Framework, CrewAI,
   frameworks              LlamaIndex Workflows, Smolagents, AutoGen/AG2
                           (multi-agent graphs, role crews, durable execution
                           — operate on top of L1)

L3 — Meta-frameworks       Nvidia AgentIQ / NeMo Agent Toolkit
                           (operate ALONGSIDE L2 frameworks; framework-agnostic
                           plugin systems, observability, performance primitives)

L4 — Conversational        Botpress, Voiceflow, Lindy, Relevance AI, Dify,
   platforms               Langflow, Flowise, Coze, MindStudio
                           (visual builders for dialogue agents — opinionated
                           for sustained conversation, often with GUIs)

L5 — Stateful agent        Letta (formerly MemGPT)
   platforms               (opinionated for memory tiering; deployable as
                           service)

L6 — Domain-specific       MOSTLY EMPTY. This is where AF lives. There is no
   conversational          mainstream "build a healthcare agent" or "build a
   frameworks              writing agent" framework. Vertical AI products
                           exist (L7) but not frameworks.

L7 — Vertical AI           Sierra (customer service), Harvey (legal), Glean
   products                (enterprise search), Lyrebird (healthcare), Manus
                           (autonomous), Pi (Inflection consumer chatbot)
                           (end products, not buildable)


Side-car infrastructure (consumed by any layer above):

  Memory infra             Mem0, Zep, Cognee, Supermemory
  Tool registries          Composio, Arcade, Smithery, Nango
  Observability + eval     Langfuse, Braintrust, LangSmith, Arize, Helicone
  Voice infra              Vapi, Retell, Bland, Pipecat
  Multi-agent runners      GasTown, claude-flow, Aeon, vibe-kanban, cmux
  Agent persistence        Beads (task-graph memory for coding agents)
```

The strategic read of this map:

- AF is **L6**, the layer that barely exists outside vertical products
- AF should consume L0, L1, L2, and the side-car infrastructure
- AF should NOT rebuild L0, L1, or L2 primitives unless there's a real reason
- AF should NOT compete with L4 platforms head-on — those are general-purpose
  conversational builders with broad surface area; AF is opinionated about
  POMDP framing, dax codes, and ambiguity handling

---

## Categorization

### (a) Frameworks — directly compete with how we build agents

#### For coding (different surface, similar primitives)

- **Claude Code / Claude Agent SDK** (Anthropic) — Skills, Hooks, Subagents
- **AWS Kiro** — Strands-based; AWS's coding agent
- **Pi** (badlogic) — minimal primitives, RPC mode, npm extensions
- **Goose** (Block / Linux Foundation AAIF) — Recipes, MCP-first
- **Codex CLI** (OpenAI) — cloud-container execution
- **Cursor** — IDE-integrated harness with Agent Tabs

Long tail: Aider, OpenCode, OpenHands, Cline, Gemini CLI, oh-my-pi.

Coding-adjacent infrastructure worth knowing:
- **Beads** (Steve Yegge) — Dolt-powered git-backed issue tracker as agent
  memory; gives long-horizon coding agents a stable task graph
- **GasTown** — Go orchestrator running 20-30 Claude Code instances in
  parallel; Mayor / Crew / Daemon / Beads architecture

#### For specific non-coding domains

**The category is mostly empty.** Vertical AI products exist (Sierra, Harvey,
Glean, Lyrebird) but they are products, not build-your-own frameworks.
Voiceflow leans customer service and Lindy leans ops, but both are general
builders pointed at a vertical. **This is the gap AF is positioned to fill.**

#### General-purpose

The real comparison set. Ranked by relevance under the three criteria:

1. **Voiceflow** — conversational design platform with entity confidence and
   reprompts (rare ambiguity primitive), strong AF similarity
2. **Botpress** — visual flow builder with confidence-threshold fallback nodes
   (rare ambiguity primitive), strong AF similarity
3. **Letta** (formerly MemGPT) — three-tier memory, self-editing, LLM-as-OS
4. **LangGraph** — state graphs with durable execution
5. **Microsoft Agent Framework 1.0** — graph workflows, checkpointing, pause/resume
6. **Google ADK 2.0** — Sequential / Parallel / Loop workflow agents
7. **OpenAI Agents SDK** — handoffs as tools, tiered guardrails, sessions
8. **AWS Strands** — model-driven (drop the flow scaffolding entirely)
9. **Nvidia AgentIQ / NeMo Agent Toolkit** — framework-agnostic meta-toolkit
10. **Claude Agent SDK** — Skills, Hooks, Subagents, Plugins

Long tail (mostly L4 recycles): Dify, Langflow, Flowise, Stack AI, MindStudio,
Coze, Lindy, Mastra, LlamaIndex Workflows, Smolagents, DSPy, CrewAI, Pydantic
AI, Relevance AI, AutoGen / AG2 (effectively dead).

### (b) Tools / services we'd use INSIDE Assistant Factory

#### Voice
- **Vapi** — provider-swappable voice runtime (only if voice is on roadmap)

#### Memory
- **Zep** — temporal knowledge graph, valid-from / valid-until on facts
- **Mem0** — managed cloud memory API, fastest path to ship
- **Letta** — also runs as memory-as-a-service (three-tier OSS)

#### Observability / eval / traces
- **Langfuse** — OSS, MIT, self-hostable; safe default
- **Braintrust** — observability + eval as one workflow

#### Other infrastructure
- **Composio** — pre-built tool connectors with execution runtime
- **Arcade** — user-identity-bound tool calls (act as user, not as agent)
- **Smithery** — MCP server registry, "Docker Hub for MCP"
- **Beads** — task-graph persistence (interesting for Plan-intent memory)

### (c) Other — doesn't fit either bucket

- **Manus, Inflection's Pi (chatbot)** — consumer products, not buildable
- **Sierra, Harvey, Glean, Lyrebird** — vertical AI competitors at the agent
  layer (L7), not the framework layer (L6)
- **AutoGen / AG2** — superseded by Microsoft Agent Framework
- **GasTown** — multi-agent runner for coding only; not for AF

---

## Deep Dive: Top 10 Frameworks

The headline pattern, visible at a glance: only Voiceflow and Botpress have
any first-class ambiguity primitive. Everything else relies on the LLM to
notice it's confused. This is a real moat for AF if we keep investing in it.

| # | Framework | Ambiguity primitive | Closest AF analog |
|---|---|---|---|
| 1 | Voiceflow | entity confidence + no-match handlers | NLU + AmbiguityHandler |
| 2 | Botpress | intent confidence + fallback nodes | NLU + AmbiguityHandler |
| 3 | Letta | none built in | Memory Manager |
| 4 | LangGraph | DIY via nodes | flow_stack (graph form) |
| 5 | MS Agent Framework | pause/resume + HITL | snapshot + ambiguity |
| 6 | Google ADK | none built in | Workflow agents |
| 7 | OpenAI Agents SDK | guardrails (different concern) | flow_stack + verify |
| 8 | AWS Strands | none — opposite philosophy | (anti-pattern study) |
| 9 | Nvidia AgentIQ | none — framework-agnostic | (sits orthogonal) |
| 10 | Claude Agent SDK | none built in | Skills + Hooks |

### 1. Voiceflow

- **Positioning** — conversation design platform, voice-first roots, now
  multimodal. Strong in customer service and IVR.
- **State model** — variables and entities (their term for slots), persisted
  across the conversation. Concrete and visible.
- **Control flow** — visual canvas of intents, blocks, prompts. Step types
  include capture-with-entity, choice, condition, API call, LLM block.
- **Memory** — per-user variables, knowledge-base integrations.
- **Tools** — REST/API blocks; LLM blocks for prompted reasoning inside flows.
- **Ambiguity** — *yes, productized*. Entity-confidence-driven reprompts;
  explicit "no match" and "no input" handlers. Closest commercial peer to
  AF's AmbiguityHandler.
- **Evaluation** — built-in analytics; conversation testing.
- **Tradeoff** — designer-first, less programmable than Botpress. Strong
  publishing model (Alexa, Google Assistant, web from one canvas).
- **AF takeaway** — Voiceflow's vocabulary is almost identical to ours
  (intents, entities = slots, prompts). Their no-match / no-input handlers
  generalize our recovery pattern. **If AF ships a visual editor, copy the
  Voiceflow conventions, not LangGraph's.**

### 2. Botpress

- **Positioning** — production-grade conversational platform. 1M+ agents
  built. Closest UX competitor to AF.
- **State model** — variables (per-conversation), workflow context, user
  profile. Concrete and visible.
- **Control flow** — visual flow builder with nodes (capture input, call API,
  branch, transition). *Flows* is the primary primitive — same word AF uses,
  similar concept.
- **Memory** — persistent per-user; multichannel (web, SMS, WhatsApp, voice).
- **Tools** — native API/tool calling per node; custom code via JS hooks.
- **Ambiguity** — *yes, productized*. Confidence-thresholded intent matching
  with fallback nodes. More mature than most because Botpress predates LLMs
  and inherited intent-classification discipline.
- **Evaluation** — analytics dashboards, A/B testing, conversation review.
- **Tradeoff** — opinionated, conversational-first, has a real GUI. Cost is
  proprietary platform lock-in (OSS edition exists but lighter).
- **AF takeaway** — Botpress is where AF naturally ends up if we built a
  visual editor for our flow stack. They have already solved the
  intent + slots + flows + ambiguity-fallback UX. **Study their workflow
  editor before designing our own.**

### 3. Letta (formerly MemGPT)

- **Positioning** — only mainstream framework that takes statefulness as the
  primary axis. Closest spiritual sibling to AF's Memory Manager.
- **State model** — three-tier: Core (in-context, agent self-edits), Recall
  (searchable history outside context), Archival (long-term, queried via tool
  calls).
- **Control flow** — V1 (2026) drops `request_heartbeat` and `send_message`;
  uses native reasoning. Agent terminates naturally.
- **Memory** — *the product*. Self-editing memory: agent has tools to modify
  its own Core block. This is what `recap` and `recall` flows in AF gesture at.
- **Tools** — generic; any tool-calling LLM works.
- **Ambiguity** — none.
- **Evaluation** — basic; team has its own benchmarks.
- **Tradeoff** — strong opinion on memory, almost none on dialogue control.
  Excellent if memory is your bottleneck; thin if conversational flow is.
- **AF takeaway** — three-tier memory maps cleanly onto our Memory Manager
  spec. **Adopt their self-editing core memory primitive inside `recap` and
  `recall`.** Do not adopt their lack of dialogue control — that's our moat.

### 4. LangGraph

- **Positioning** — LangChain's stateful graph framework. Current market leader
  for production multi-agent Python work.
- **State model** — explicit state graph. Nodes are functions, edges are
  conditional routing. State is a pydantic-typed object flowing through edges.
- **Control flow** — *you* draw the graph. Branches, loops, human-intervention
  nodes are explicit. No LLM-driven control unless you put one in a node.
- **Memory** — checkpointers persist state per thread; long-term is BYO.
- **Tools** — generic; works with any tool-calling LLM.
- **Ambiguity** — DIY. You can put an "ask user" node in the graph but the
  decision logic is yours. No built-in confidence framework.
- **Evaluation** — LangSmith integrates deeply (node-by-node state diffs,
  full graph replay against new model versions).
- **Tradeoff** — extreme flexibility at the cost of zero opinions. Powerful
  for production but slow to start. **Durable Execution** is the standout:
  agents resume from the last breakpoint after crashes.
- **AF takeaway** — durable execution is the answer to our snapshot/rollback
  gap. **The graph metaphor is *not* the right metaphor for AF** — our flow
  stack is more constrained on purpose. But the persistence pattern is.

### 5. Microsoft Agent Framework 1.0 (April 2026)

- **Positioning** — production unification of AutoGen + Semantic Kernel.
  Aimed at .NET and Python enterprise.
- **State model** — Semantic Kernel's session-based state, type-safe, with
  middleware and telemetry. Workflow engine layered on top.
- **Control flow** — graph-based workflows with explicit edges. Six
  orchestration patterns: sequential, concurrent, handoff, group chat,
  Magentic-One. All support streaming, checkpointing, pause/resume,
  human-in-the-loop approvals.
- **Memory** — session state per agent; long-term via plugins.
- **Tools** — Semantic Kernel connectors; MCP support.
- **Ambiguity** — pause/resume + HITL is the closest thing — workflow can
  pause for an approval. Different from model-driven uncertainty but
  philosophically adjacent.
- **Evaluation** — telemetry / filters built in.
- **Tradeoff** — most enterprise-feature-complete framework on the list. Cost
  is verbosity and Microsoft-flavored ecosystem assumptions.
- **AF takeaway** — *checkpointing + pause/resume* directly addresses our
  Future Work § snapshot/rollback. **Magentic-One pattern (planner +
  workers) is worth comparing to AF's Plan intent.**

### 6. Google ADK 2.0

- **Positioning** — code-first toolkit optimized for Gemini but model-agnostic.
  Cloud Run / Vertex deployment.
- **State model** — Sessions hold conversational state, memory holds
  cross-session knowledge, artifacts hold large blobs (lazy-loaded). ADK
  manages context like source code.
- **Control flow** — three agent types: LLM agents, Workflow agents
  (Sequential, Parallel, Loop), Custom agents. ADK 2.0 adds graph-based
  workflows.
- **Memory** — sessions, memory, artifacts. Framework auto-filters events,
  summarizes older turns.
- **Tools** — large pre-built ecosystem; A2A protocol for cross-framework
  agent communication.
- **Ambiguity** — none.
- **Evaluation** — OpenTelemetry built in; integrates with Langfuse, Arize,
  Google Cloud Observability natively.
- **Tradeoff** — heavy framework with lots of primitives. Big out-of-the-box
  payoff, non-trivial learning curve, Google-Cloud-flavored deployment.
- **AF takeaway** — *Sequential, Parallel, Loop* as workflow primitives is
  exactly what we want for Plan-intent flows. **The
  artifact / session / memory split mirrors our DialogueState /
  ContextCoordinator / MemoryManager split — same problem, different names.**

### 7. OpenAI Agents SDK

- **Positioning** — OpenAI's official, code-first agent framework.
  Lightweight, not opinionated about workflow shape.
- **State model** — Sessions as a working-context container per run. No
  graph, no flow stack — event-driven loop.
- **Control flow** — Agents call tools, including handoff tools. A handoff is
  literally a tool named `transfer_to_<agent>` that passes control. Optional
  context filtering on handoff.
- **Memory** — Sessions for in-run state. Cross-session memory is BYO.
- **Tools** — function tools, agent-as-tool, handoff tools. Three layers of
  guardrails: input (before run), output (after final), per-tool (every
  custom function call).
- **Ambiguity** — none. Guardrails are about safety/validation, not
  uncertainty.
- **Evaluation** — OpenAI evals integrate but not as part of the SDK proper.
- **Tradeoff** — minimal abstraction at the cost of having no built-in answer
  for long-running, multi-turn, ambiguous dialogue. Composable, not
  opinionated.
- **AF takeaway** — handoffs-as-tools is a clean parallel to flow_stack.push.
  **Three-tier guardrails (input / output / per-tool) generalize our NLU.prepare
  / RES.finish / PEX.verify post-hooks. Adopt the vocabulary.**

### 8. AWS Strands

- **Positioning** — Amazon's open-source agent SDK (Apache-2.0). Used in
  production by Kiro, Amazon Q, AWS Glue. Anthropic and Meta are contributors.
- **State model** — *minimal*. Just LLM context + tool results. The agent has
  no externally-managed dialogue state.
- **Control flow** — **the antithesis of AF**. Strands is "model-driven":
  three components — LLM, system prompt, tools. The LLM does all planning,
  decides which tools to use, when. No flow scaffolding, no slots, no
  intents, no state machine.
- **Memory** — BYO; SDK doesn't impose a model.
- **Tools** — function tools; deep AWS integration (VPC, IAM, KMS).
- **Ambiguity** — none. The bet is that frontier LLMs know when to ask.
- **Evaluation** — rich observability, especially in AWS environments.
- **Tradeoff** — bets the entire architecture on "models are smart enough
  now." When the bet pays off (Claude 4.7, GPT-5.5), the developer writes 5
  lines of code instead of 500 and the agent works. When it doesn't, there's
  no scaffolding to fall back on.
- **AF takeaway** — **Strands is the explicit hypothesis we should test
  against.** It's the steel-man for "throw out the flows and let the LLM
  drive." If a Strands agent matches AF's quality on Hugo / Dana / Kalli
  with 1/100th the code, the moat is in the wrong place. If it doesn't
  (which is likely on multi-turn ambiguous dialogue), AF's hand-crafted
  scaffolding is justified. *Run this experiment.*

### 9. Nvidia AgentIQ / NeMo Agent Toolkit

- **Positioning** — meta-framework. Sits **alongside** L2 frameworks
  (LangChain, LlamaIndex, CrewAI, Semantic Kernel), not replacing them.
- **State model** — none of its own; defers to the underlying framework.
- **Control flow** — treats agents, tools, and workflows as composable
  function calls. Plugin system with entry points and decorators.
- **Memory** — defers.
- **Tools** — MCP client and server runtime; framework-agnostic tool
  registration.
- **Ambiguity** — none — wrong layer for it.
- **Evaluation** — plugin-based observability; event-driven tracing exports
  to Phoenix, Langfuse, Weave, OpenTelemetry.
- **Tradeoff** — orthogonal to most other frameworks. Adds value when you
  have multiple frameworks to integrate; adds nothing if you're greenfield
  on a single framework. The Agent Performance Primitives (parallel
  execution, speculative branching, node-level priority routing) are
  genuinely interesting at scale.
- **AF takeaway** — **AgentIQ is not a competitor — it's an integration
  surface.** If AF ever exposes itself as one framework among many in an
  enterprise stack, AgentIQ is how that integration would happen. Until then,
  ignore. Performance primitives might inform our async Internal-flow design.

### 10. Claude Agent SDK

- **Positioning** — Anthropic's own primitives, exposed as an SDK after
  Claude Code validated them.
- **State model** — single LLM context with `CLAUDE.md` injected every turn.
  Cross-session state lives in the filesystem.
- **Control flow** — native tool-calling loop. Subagents dispatched as a tool
  call; their work happens in isolated context, returns a summary.
- **Memory** — `CLAUDE.md` as core memory; subagent memory directories;
  Skills as on-demand instruction loading via progressive disclosure.
- **Tools** — MCP servers are first-class. Tools registered by mounting an
  MCP server.
- **Ambiguity** — none. Model asks if it feels like asking. No programmatic
  "confidence below threshold, clarify" primitive.
- **Evaluation** — manual. Hooks at 25 lifecycle points let you attach
  validators, but you write them.
- **Tradeoff** — gives up multi-turn dialogue scaffolding (slot-filling, flow
  lifecycles, ambiguity gating) for being model-native and minimal.
  Brilliant for one-shot agentic tasks; thin for sustained dialogue.
- **AF takeaway** — Skills, Hooks, Subagents, MCP are not just for coding.
  **Adopt all four as primitives inside our existing architecture.**

---

## The Reinventing-the-Wheel Question

The user's central question, plainly stated:

> What do the SDKs offer that we couldn't build ourselves? Is AF building
> primitives that already exist elsewhere — are we reinventing the wheel
> for nothing? Or are we inventing the wheel, and that's fine because
> there's no standard wheel shape yet?

### What AF could rebuild — but probably shouldn't

These are L1 / L2 primitives. AF could build them, but every SDK already has
them battle-tested at scale, and they ship updates the day a new model lands.

| AF subsystem | Already standard in | Why we shouldn't rebuild |
|---|---|---|
| Native tool-calling JSON parsing | All L1 SDKs | Provider-specific quirks, breaks on every API change |
| Provider abstraction | OpenAI SDK, ADK, Strands, Pydantic AI | Five providers × N quirks = maintenance sink |
| MCP client/server | Claude SDK, Goose, AgentIQ, Strands | It's a protocol, the value is the ecosystem |
| Workflow primitives (Sequential/Parallel/Loop) | ADK, MS Agent Framework | Generic, well-tested elsewhere |
| Subagent dispatch with isolated context | Claude SDK | Solid pattern, easy to adopt |
| Hooks at lifecycle points | Claude SDK (25 points) | Trivial to adopt, big payoff |
| Durable execution / checkpointing | LangGraph, MS Agent Framework | Hard to get right at the edges |
| Sessions / per-run context | OpenAI SDK, ADK | Standard pattern |
| Tool guardrails (input / output / per-tool) | OpenAI SDK | Vocabulary worth importing |
| Observability / tracing | Langfuse, Braintrust, OpenTelemetry | Outsourced infrastructure category |

If AF reimplements any of these from scratch, that's wasted engineering. The
right move is to consume them from L1 SDKs and L3 meta-frameworks.

### What AF is actually inventing (the moat)

These are genuinely new wheels. Either the standard wheel doesn't exist, or
existing wheels are immature.

| AF subsystem | State of the art elsewhere | Why we should keep building |
|---|---|---|
| **Confidence-driven clarification** | Botpress / Voiceflow have entity-confidence reprompts. Academic work uses EVPI and structured uncertainty separation. **No SDK has it.** | This is the moat. Multi-turn assistants live or die on this. |
| **AmbiguityHandler at four levels** | Closest peer: Voiceflow's no-match / no-input. Ours is more layered. | Productizes what's currently academic. |
| **POMDP framing of dialogue state** | Pure research; no productized framework treats it this way. | Makes signals measurable, evals reproducible. |
| **Slot-filling tied to flow lifecycle** | Botpress / Voiceflow have entities + flows but no formal lifecycle on flow termination. | Predictable termination is a real production property. |
| **Per-flow PEX policies with verify/recover** | LangGraph nodes can do this, but you write everything. AF gives a structure. | Domain-specific guardrails as first-class concept. |
| **Three-tier memory with vetted/unvetted split** | Letta has tiers but no vetted-vs-unvetted distinction. | Trust gradient on retrieved facts is novel. |
| **Compositional dax grammar** | Nothing comparable anywhere. | Forces semantic discipline on flow definition. |
| **Synthetic data augmentation pipeline** | Most frameworks expect you to bring your own data. | Ships a path from spec to trained system. |

### So — are we reinventing the wheel?

**Partially yes, partially no.** The honest split:

- **Yes**: tool-calling, MCP, hooks, sessions, durable execution, workflow
  primitives, observability. These are L1/L2 wheels that already exist. Every
  hour AF spends rebuilding them is a wasted hour.

- **No**: confidence-driven clarification, POMDP framing, slot-flow lifecycle
  coupling, dax composition, ambiguity at four levels. These are genuinely
  not standard. AF is shaping wheels that don't have a standard shape yet.

**The market context matters.** It's May 2026. The L1 SDKs (Claude, OpenAI,
ADK, Strands) all launched within the last 18 months. They're stabilizing now
but the standards are far from settled. Building on top of them is
defensible; building parallel to them is reinvention.

**The strategic answer:** AF should be **L6 — a domain-specific framework for
sustained, ambiguity-aware conversational agents — built on L1 SDKs and L3
meta-tooling.** That's a quadrant nobody is occupying. Strands is the test
case: if a 100-line Strands agent matches AF on Hugo / Dana / Kalli, our moat
is in the wrong place. If it doesn't (likely on multi-turn ambiguity), our
hand-crafted scaffolding is justified — but only the parts that aren't
already standard.

---

## Obvious Wins to Carry Over

Concrete imports from the SDK ecosystem into AF, in priority order:

1. **Skills as the prompt mechanism.** Our `prompts/skills/` already gestures
   at this. Adopt the Claude SDK pattern: metadata-first, lazy-load
   instructions on demand. Replaces hand-curated prompt files.
2. **MCP for tool registration.** Replace hand-rolled `schemas/` with MCP
   servers. Free integration with the broader ecosystem; Composio / Arcade /
   Smithery become available.
3. **Native tool-calling APIs.** `prompt_engineer.py` should not parse text
   for tool calls. Use the provider's native JSON. Cuts a class of bugs.
4. **Subagent dispatch for Internal flows.** Spec says Internal flows can run
   async. Claude SDK's subagent pattern is the implementation; copy it.
5. **Hooks at lifecycle boundaries.** We have NLU/PEX/RES post-hooks. Widen
   to pre-tool / post-tool / pre-LLM / post-LLM / on-flow-push / on-flow-pop.
6. **Durable execution / checkpointing.** LangGraph + MS Agent Framework both
   solve this. Pick a model, port it. Closes our snapshot/rollback gap.
7. **Letta-style self-editing core memory.** Agent has tools to modify its
   own L1 scratchpad. Aligns with `recap`'s intent.
8. **Zep-style temporal validity on memory facts.** valid-from / valid-until
   on entries. Solves staleness in business-context tier.
9. **Arcade-style user-identity-bound tool calls.** Tool actions act *as*
   the user, not as the agent. Maps to our auth/middleware design.
10. **Workflow primitives (Sequential / Parallel / Loop) for Plan flows.**
    ADK already has these. Useful shape for `outline`-driven multi-step plans.

---

## The Moat — What to Keep

Things to keep building because they don't exist anywhere else, or exist only
in research:

- **POMDP framing with confidence thresholds** — measurable, evaluatable,
  unique among productized frameworks
- **AmbiguityHandler at four levels** — closest peers (Voiceflow, Botpress)
  do entity-confidence reprompts only; AF goes further
- **Flow stack with explicit lifecycle** — predictable termination is a
  production property, not a feature
- **Slot-filling with validation tied to flows** — programmatic, not
  LLM-honor-system; prevents the SDK failure mode of "agent wandered off"
- **Per-flow policies in PEX** — domain-specific guardrails as first-class
- **Three-tier memory with vetted-vs-unvetted distinction** — Letta has
  tiers, only AF has the trust gradient
- **Compositional dax grammar** — forces semantic discipline; no peer
- **Synthetic data augmentation pipeline** — most frameworks assume you
  bring data; AF ships a path

Strategic positioning if these moats hold up: **AF becomes the framework for
sustained-dialogue agents that mortals don't want to build from scratch,
sitting at L6 on top of L1 SDKs, with the moat squarely in ambiguity
handling, slot-flow lifecycle coupling, and trust-graded memory.** That
quadrant is unoccupied today. The risk is that frontier LLMs (especially
through Strands' "model-driven" bet) make some of these moats redundant
within 18 months. The Strands experiment on a real AF domain is the cheapest
way to find out.
