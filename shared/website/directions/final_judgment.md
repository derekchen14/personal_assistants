# Final Judgment — The Three Differentiators

This document is the consolidated, final call after three prior attempts
(`potential_directions.md`, `alternate_directions.md`, `direction_review.md`)
and a fresh web pass to validate or refute the core claims. The job here is
not to deliberate further. It is to pick three and commit.

## Top-line Verdict

The three differentiators for Assistant Factory are:

1. **Ambiguity Handler** — uncertainty as first-class content, declared and
   resolved at four levels.
2. **POMDP-Grounded Worldview** — Dialogue State + Flow Stack as one idea: an
   explicit, evaluable belief state the agent can defend or revise.
3. **Trust-Graded Memory** — three-tier memory (scratchpad / user preferences
   / business context) with a *vetted vs unvetted* axis on every retrieved fact.

Synthetic Data / Spec-to-Agent Pipeline is **demoted to internal capability**
(see § Why Not Spec-to-Agent below). The Bitter Lesson concern stays as a
*constraint on how we build*, not a customer-facing pillar.

This breaks with `potential_directions.md` and `direction_review.md` (both of
which kept synthetic data as #3) and lands with `alternate_directions.md`'s
choice of "POMDP-Grounded Worldview" as #2 — refined and defended below
against the fresh web evidence.

---

## Mapping User Problems → Differentiators

The user named three failure modes. Every pillar earns its slot only by
naming the problem it owns.

| User problem | Primary answer | Secondary support |
|---|---|---|
| Over-confident hallucination | **Ambiguity Handler (#1)** — knows when unsure, asks before asserting | Trust-Graded Memory prevents asserting from raw retrieval |
| Sycophancy / no worldview | **POMDP-Grounded Worldview (#2)** — has predictions to defend, not just chat to please | Slot-flow lifecycle won't let the agent fake "done" |
| Brittleness in real workflows | **Trust-Graded Memory (#3) + #1 + #2** — grounded knowledge, calibrated retrieval, recoverable state | All three compound |

The "over-fitting to coding" framing the user opened with is *enabled by*
all three pillars working together — the architecture is domain-agnostic
because state, ambiguity, and memory are domain-agnostic. It is not its own
pillar; it's the property the pillars produce.

---

## The Three Differentiators

### 1. Ambiguity Handler — Robustness Pillar (locked)

**What it is.** A dedicated component that *declares*, *tracks*, and
*resolves* uncertainty at four levels (general, partial, specific,
confirmation). NLU, PEX, and RES all surface confidence into a shared
object that drives clarification, re-routing, or escalation. Not a vibe;
a measurable property tied to dialogue state.

**Why it's a moat (web-validated).**

- Search confirms **no L1 SDK has a confidence-driven clarification
  primitive.** Voiceflow and Botpress have entity-confidence reprompts;
  Anthropic's Claude Agent SDK, OpenAI Agents SDK, AWS Strands, Google ADK,
  MS Agent Framework all leave it to the LLM to "ask if confused."
- AWS itself shipped Strands Evals in 2026 specifically because model-driven
  agents are "difficult to evaluate systematically" on multi-turn — i.e.,
  they don't reliably know when they're confused. That is exactly the gap
  AF's Ambiguity Handler fills.
- 2026 sycophancy research (Giskard, MIT's "Delusional Spiraling" paper,
  CONSENSAGENT) treats uncertainty/disagreement as the structural counter to
  sycophancy. AF's four-level taxonomy is the productized form of that
  research direction.

**Customer value.** The agent stops sounding confidently wrong. Users notice
within the first session.

**ML path.** Confidence is a calibratable signal. Each user correction is a
labeled training example. The four-level taxonomy is structured enough to
learn, unstructured enough to generalize.

---

### 2. POMDP-Grounded Worldview — Sycophancy Pillar

**What it is.** Every turn updates an explicit `DialogueState`: predicted
intent, predicted flow, slot beliefs, a stack of flows in flight, and a
small set of control flags. The flow stack has a real lifecycle (Pending →
Active → Completed) and supports stacking, popping, mid-plan replanning.
Slots have validation tied to the flow that owns them. Treat
`DialogueState` and `FlowStack` as **one differentiated idea**: the agent's
own worldview in operational form.

**Why it's a moat (web-validated).**

- Search returns **almost nothing post-2013** on production POMDP-based
  dialogue state tracking. The line is academic-only. Young et al. 2013
  and the MultiWOZ / SGD lineage stayed in research; nobody productized it.
- Strands' explicit philosophy is "the LLM has the state in its head" —
  state is just context + tool results. Claude Agent SDK and OpenAI Agents
  SDK ship sessions but no structured belief state. LangGraph gives you a
  graph but you draw it yourself; no opinion on what state means.
- Anthropic's April 2026 Planner/Generator/Evaluator engineering note
  *gestures* at this (separating planning state from execution) but doesn't
  ship a belief schema. AF can be the productized form.
- 2026 sycophancy research (Batista & Griffiths, "Rational Analysis of
  Sycophantic AI") shows that without a *prior belief* to defend, a Bayesian
  agent given hypothesis-confirming data drifts toward overconfidence. A
  worldview is the prior. Without one, an agent has nothing to disagree with
  the user about.

**Customer value.** The agent doesn't drift. Multi-step tasks complete.
When the user contradicts themselves on turn 5, the agent notices because
the state model says it should. The agent has its own definition of "done"
(unfilled required slots → not done, period) that the user can't bully it
out of.

**Why this is one idea, not two.** `direction_review.md` correctly noted
that Dialogue State and Flow Stack interlock. Slots without lifecycle are
just variables; lifecycle without slots is just routing. Together they
*are* the agent's worldview. Splitting them into two pillars would break the
narrow-scope rule for no benefit.

**ML path.** The schema is structured but slot values are LLM-filled and
many are open-text — the same hybrid approach as
`interview_prep/dialogue_state_research.md` (typed primitives where
structure suffices, NL+embedding where it doesn't). The shape is the
discipline; the content is learned. Maps cleanly onto RL-style training
when we get there.

**Transparency dividend (the eval / observability / red-team payoff).**
A structured `DialogueState` is a qualitatively richer trace target than
"LLM context + tool results." This pillar's downstream payoff is what
2026's hot trends (observability, agent evals, monitoring, red-teaming)
demand and what unstructured competitors can't deliver:

- **Observability** — we trace belief-diffs, slot-fill events,
  ambiguity-raise events, and flow lifecycle transitions. LangSmith /
  Langfuse / Arize can ingest these via OpenTelemetry / OpenInference; the
  *content* of the trace is what makes our agent debuggable, not the
  vendor.
- **Evals** — reproducible against belief state, not just final output.
  Slot-fill correctness, flow-termination correctness, and
  ambiguity-trigger precision/recall become first-class metrics.
  Strands explicitly struggles here (AWS shipped Strands Evals in 2026 to
  paper over it); structured state makes the same evals cheap for us.
- **Monitoring** — a slot at confidence < threshold while the agent
  asserts is a measurable production failure, not a vibes check. Cleaner
  signal than the cross-model-disagreement heuristics commodity tools rely
  on.
- **Red-teaming** — structured state means structured attack surface
  (memory poisoning at the trust-grade level, ambiguity-trigger
  manipulation, slot injection). Aligns with OWASP ASI 2026, NIST CAISI
  (launched Feb 2026), and EU AI Act Article 55 obligations (high-risk
  obligations land Aug 2026). Structured state turns those compliance
  requirements from a cost into a capability.

**Why this isn't a fourth pillar.** Observability/evals/monitoring/
red-teaming are 2026's hottest trends, but the *platforms* are
commoditizing fast — six production-grade observability platforms
consolidated by April 2026; Langfuse was acquired by ClickHouse in
January. Building any of them would be reinvention. The differentiator is
*what we put into the trace*, which is precisely what pillar #2 produces.
Promote, don't proliferate.

---

### 3. Trust-Graded Memory — Productivity Pillar

**What it is.** Three-tier memory (Session Scratchpad → User Preferences →
Business Context) with one twist nobody else has: every fact carries a
**trust grade**. *Vetted* facts (confirmed by the user, derived from an
authoritative source) override *unvetted* facts (inferred, scraped,
mid-conversation guesses). Retrieval surfaces the grade alongside the fact,
so the Ambiguity Handler can read it and policies can choose to confirm or
proceed.

**Why it's a moat (web-validated).**

- Letta has three tiers (Core / Recall / Archival) and self-editing core
  memory but, per multiple 2026 comparison surveys, **does not separate
  vetted from unvetted facts.** Every recalled fact is treated as
  equivalent. Confirmed by web search.
- Zep has temporal validity (valid-from / valid-until) on facts in its
  Graphiti knowledge graph — *complementary*, not a substitute. Temporal
  validity says *when* a fact was true; trust grading says *whether to bet
  on it.* Both axes belong; Zep ships one, AF ships both.
- The cross-pillar integration is the part nobody can copy quickly:
  low-trust retrievals automatically raise ambiguity flags. Memory and
  Ambiguity Handler share a vocabulary because they were designed together.
  Letta+Zep stitched together externally would not produce this.

**Customer value.** The agent remembers what users actually told it without
blurring it into what it guessed. This is the central failure mode in
productivity domains (Recruiter, Scheduler), where "the agent thinks it
knows but it's wrong" is worse than "the agent doesn't know."

**ML path.** Hybrid retrieval is well-studied. The novel part — automated
vetting from logged corrections — is exactly the kind of label that becomes
trainable once corrections start logging. Treat current hand-curation as
the bootstrap, not the steady state.

**What gets borrowed.** Letta's three-tier architecture and self-editing
core memory primitive; Zep/Graphiti's temporal validity bolted onto the
business-context tier. The synthesis (trust grades on top of tiers, wired
to Ambiguity) is ours.

---

## Why Not Spec-to-Agent (Synthetic Data)?

`potential_directions.md` named synthetic data as #3 (5/5 ML-friendly, 4/5
robustness, 2/5 productivity). `direction_review.md` reframed it as
"spec-to-agent pipeline" to make it customer-facing. Both arguments are
internally coherent. Both lose to fresh evidence:

1. **Synthetic data is commoditizing.** NVIDIA NeMo Synthetic Data
   Generation, Tonic.ai, and a growing "synthetic data tools" category
   (Gartner: 75% of businesses by 2026) make domain-bootstrap pipelines
   widely available. The unique asset is *coupling to AF's ontology* — but
   coupling is not a category-defining moat.
2. **Spec-to-agent has competitors.** Oracle's Open Agent Spec (2025–2026)
   is an explicit declarative language for defining agents. The category
   "agents-as-code" is forming around us; we'd be entering a fight, not
   pioneering. The web search surfaced "POLARIS" (governed orchestration as
   typed plan synthesis) and several similar 2026 efforts.
3. **Customer-facing weakness.** Even after reframing as "ship a domain
   agent in a week," the customer's lived experience of synthetic data is
   indirect. Pillars #1 and #2 are felt within the first session;
   spec-to-agent is felt only by *builders*, who are not our day-one
   customer set.
4. **Internal capability ≠ identity.** AF should still build a synthetic
   pipeline — it's how Hugo, Dana, Kalli get bootstrapped efficiently. But
   the pipeline is the assembly line, not the product. The product is the
   agent the assembly line outputs.

**Net.** Keep building synthetic data. Stop selling it. Reassess after the
first three queued domains (Blogger, Scheduler, Recruiter) ship; if
time-to-domain becomes our externally measurable advantage, promote it
then.

---

## Buy / Build / Borrow

### Build (the moat)

| Capability | Why build |
|---|---|
| **Ambiguity Handler at four levels** | No SDK has it. Productizes academic work on uncertainty as content. |
| **POMDP-grounded Dialogue State + Flow Stack** | No production framework ships an explicit belief-state worldview. POMDP-DST line went quiet post-2013; we revive it. |
| **Memory trust gradient (vetted / unvetted)** | Letta has tiers, Zep has temporal validity; nobody has trust grading. Integration with Ambiguity Handler is the unique surface. |

### Borrow (adopt patterns, not implementations)

| Capability | Source | Notes |
|---|---|---|
| Hooks at lifecycle points | Claude Agent SDK | Widen NLU/PEX/RES pre/post-hooks to ~25 points (PreToolUse, PostToolUse, OnFlowPush, OnFlowPop, etc.). |
| Subagent dispatch | Claude Agent SDK | For Internal flows (recap / recall / retrieve). Borrow the pattern, not their runtime. |
| Workflow primitives (Sequential / Parallel / Loop) | Google ADK | For Plan-flow sub-flow orchestration. |
| Durable execution / checkpointing | LangGraph (or MS Agent Framework) | Closes the snapshot/rollback gap. LangGraph's per-step Postgres checkpointing is the cleanest model. |
| Three-tier memory architecture | Letta | Adopt Core / Recall / Archival shape; layer trust grades on top. |
| Temporal validity on facts | Zep / Graphiti | valid-from / valid-until under our trust axis on the business-context tier. |
| Tiered guardrails (input / output / per-tool) | OpenAI Agents SDK | Vocabulary import for our pre/post-hooks. |
| Skill metadata pattern | Claude Agent SDK | Replace `prompts/skills/` markdown with metadata-first lazy-loaded skills. |
| Planner / Generator / Evaluator pattern | Anthropic April 2026 engineering blog | Validates AF's structural separation; light pattern-import for plan flows. |

### Buy (consume off-the-shelf)

| Capability | Source |
|---|---|
| LLM providers + native tool-calling JSON | Anthropic / OpenAI / Google APIs — never re-parse |
| Tool registries (MCP servers) | Composio, Arcade, Smithery |
| Voice (when on roadmap) | Vapi, Retell |
| Observability + traces | Langfuse (default), Braintrust as alt — emit OpenTelemetry/OpenInference; *what* we trace is the moat, not the platform |
| Agent eval platform | Braintrust (CI-gated PR pattern) or LangSmith — feed DialogueState diffs in; eval *content* lives in our repo |
| Production monitoring (drift, hallucination, policy) | Datadog LLM Observability, Galileo, or Maxim — commodity layer; configure to read our ambiguity-flag signal |
| Red-teaming primitives | Promptfoo + DeepTeam (open source) — wrap with our state-aware probes when EU AI Act / NIST CAISI obligations bind in late 2026 |
| OAuth / credential storage | Standard libraries |
| Vector DB | Off-the-shelf (Chroma, pgvector, Pinecone) |
| Synthetic data primitives | NVIDIA NeMo SDG, Tonic, or similar — we ship the *coupling*, not the generator |

### Drop or radically simplify

| Capability | Why drop |
|---|---|
| Compositional dax grammar (16-primitive) | Hand-engineering. Keep dax codes as opaque IDs; drop the symbolic grammar. Teaching cost > differentiation value. |
| Universal dialogue-state protocol | Research vision. Park in `interview_prep/`. Revisit only if cross-agent interop becomes a paying-customer requirement. |
| Per-flow PEX hand-engineering for verify/recover | Borrow LangGraph node patterns for the generic case; custom-build only the recovery paths that are specifically *ambiguity recovery*. |
| Custom provider abstraction layer | Use the L1 SDK; stop maintaining our own. |
| Hand-rolled tool schemas in `schemas/` | Move to MCP. |

---

## How the Three Compound

The pillars aren't independent — they reinforce each other. This is the
loop that keeps AF improving without expert authoring on every iteration:

```
   [Ambiguity Handler]
         │
         │ confidence flags on retrieved memories
         ▼
   [Trust-Graded Memory]
         │
         │ low-trust retrievals → auto-raise ambiguity
         ▼
   [POMDP Worldview]
         │
         │ slots/flow-state ground both Ambiguity AND Memory
         ▼
   [back to Ambiguity Handler] — confidence model now anchored in beliefs
```

- **#1 declares uncertainty.** Without it, no signal.
- **#2 anchors the agent's beliefs.** Without it, nothing to be uncertain
  *about* — ambiguity becomes vibes.
- **#3 grounds external knowledge.** Without it, the agent over-asks (no
  memory) or hallucinates (untrusted memory).

Cut any one and the loop breaks. This passes
`potential_directions.md`'s compounding-loop test, with worldview replacing
synthetic data as the third leg — and the loop is *stronger* this way,
because all three pillars are customer-felt.

---

## Anti-Sycophancy Story (the user's named gap)

The user named sycophancy as a problem and observed that the answer is to
give the agent its own worldview. Here is the explicit sycophancy
defense that emerges from the three pillars:

1. **The agent has *predictions* before the user speaks.** NLU outputs an
   intent and flow with confidence, slots have priors. (Pillar #2)
2. **The agent has its own definition of "done."** A flow with unfilled
   required slots cannot terminate. The user saying "we're done" doesn't
   override the slot contract. (Pillar #2)
3. **The agent registers its own confusion.** When a user assertion
   conflicts with state, ambiguity is raised; the agent asks rather than
   capitulates. (Pillar #1)
4. **The agent distinguishes what users *told* it from what it *guessed*.**
   On contradiction, vetted facts win over unvetted. (Pillar #3)

This is the operational form of "the agent has its own worldview." None of
the three pillars on their own delivers it; the integration does.

---

## Sanity Checks (kept from `alternate_directions.md`)

- **The Strands experiment.** Run a ~100-line Strands agent on Scheduler.
  If it matches AF on multi-turn ambiguous dialogue, the moat is in the
  wrong place. The 2026 web data already suggests Strands struggles here
  (AWS shipped Strands Evals to expose exactly this), but a head-to-head on
  a real AF domain settles it.
- **No-fourth-pillar rule.** If a feature isn't one of the three
  differentiators, it doesn't get a top-level component or its own README
  section. It lives inside the existing structure or it waits.
- **Practical-over-novel test.** Before adding any concept, ask: "Does this
  make Scheduler ship faster or work better for a real user this week?"
  If no, defer.
- **Bitter-Lesson kill criterion.** If by the third domain (Blogger) we
  still need significant hand-engineered prompts or per-domain glue, scope
  narrows or we pivot toward more learned components. Don't invest more in
  scaffolding for its own sake.

---

## The Pitch (three sentences)

When someone asks "why Assistant Factory and not Strands / Letta / OpenAI
Agents SDK?":

> First, our agent treats uncertainty as content, not a failure mode — it
> knows when it's confused and clarifies before acting. Second, it has its
> own worldview: an explicit belief state with a flow lifecycle that won't
> let the agent fake completion or sycophantically agree to a wrong framing.
> Third, its memory has a trust gradient — vetted business knowledge is
> separated from raw retrieval, so the agent doesn't confidently assert what
> it merely searched for.

That's the story. Three sentences. Everything else is implementation.

---

## What This Judgment Implicitly Says No To

To make the narrow-scope commitment real, the following are *not*
differentiators, even when tempting:

- **Synthetic data / spec-to-agent** as a marketed pillar. Build it, use it
  internally, don't sell on it.
- **Compositional dax grammar.** Reduce to opaque IDs.
- **Plan flow with replanning** as a differentiator. Useful feature, not a
  pillar; borrow ADK's Sequential/Parallel/Loop primitives.
- **Per-flow PEX policies** as a differentiator. Infrastructure.
- **Internal flow swarm** as a differentiator. Borrow Claude SDK subagent
  pattern; uniqueness is the *flows*, not the orchestration.
- **Voice infrastructure**. Buy when needed.
- **Multi-agent dialogue-state protocol**. Park in research notes.
- **Bespoke observability stack**. Use Langfuse.
- **Custom tool registry**. Use MCP + Composio.
- **Bespoke eval platform.** Use Braintrust or LangSmith; ship eval *content*, not infrastructure.
- **Bespoke red-team framework.** Wrap Promptfoo / DeepTeam with state-aware probes only when compliance demands it.

If any of these creep back into the roadmap as differentiators, treat that
as a smell that scope is expanding again.

---

## Resolved Open Question — Observability / Evals / Monitoring / Red-Teaming as a Fourth Pillar?

**No.** Web data confirms all four are commoditizing rapidly:

- Six observability platforms consolidated by April 2026 (LangSmith,
  Langfuse, Arize Phoenix, Helicone, Datadog, Honeycomb); OpenTelemetry +
  OpenInference are the de facto trace standard.
- Eval platforms (Braintrust, LangSmith, Galileo, Comet Opik, DeepEval,
  Promptfoo, Latitude) all ship the same primitives — the *content* of
  evals is where the value lives.
- Monitoring is a Datadog/Galileo/Levo/MLflow line item by mid-2026.
- Red-teaming has open-source tools (Garak, Promptfoo, PyRIT, DeepTeam)
  and a regulatory forcing function (OWASP ASI 2026, NIST CAISI, EU AI
  Act Article 55) — but the value is what state we expose to the
  red-teamer, not the runner.

The user's intuition is correct that DialogueState gives radical
transparency. That intuition gets cashed in by **promoting transparency
as the headline downstream payoff of pillar #2**, not by spinning a
fourth pillar. See § 2 above for the explicit transparency dividend.

The pitch-line update: when someone says "but how do you actually know
your agent is doing the right thing?" the answer is *because we have an
explicit belief state to evaluate against.* The structured state IS the
evaluability story.

---

## Resolved Open Questions from `direction_review.md`

The review left four open decisions; the final calls:

1. **Synthetic data as #3, or "spec-to-agent" as #3?** Neither. POMDP
   Worldview takes the slot; synthetic data is internal capability.
2. **Phase A vs Phase B ordering.** Ambiguity Handler ships first because
   it gates the rest. POMDP Worldview hardens in parallel since it is the
   substrate Ambiguity reads. Memory comes after.
3. **Drop the dax grammar?** Yes. Mechanical refactor; opportunistic, not
   blocking.
4. **Strands experiment?** Run early — within the first phase, not at the
   end. Cheapest way to test the moat hypothesis on a real domain.

---

# Addendum — Architecture Questions

Two follow-up architecture decisions surfaced by the locked pillars: what
should DialogueState actually be, and do the three NLU/PEX/RES modules
still earn their keep? Both are tested against the three pillars; nothing
survives unless it carries pillar weight.

## Q1 — Shape and Role of Dialogue State

### Diagnosis

DialogueState today is a thin control-flag bus (`has_plan`, `keep_going`,
`has_issues`, `natural_birth`, `slices`, `active_post`) plus a top-N
confidence cache. The actual worldview content lives elsewhere:

| What | Where it actually lives today |
|---|---|
| Slot beliefs | `flow.slots[name]` on each flow (`flow_stack/flows.py`) |
| Flow lifecycle status | `flow.status` on each flow |
| Flow-internal stage | `flow.stage` (audit at `revise.py:228`; soon chat per `master_plan.md`) — ad-hoc, undocumented |
| Cross-flow handoff | Memory Manager L1 scratchpad (`revise.py:51-54`, `175-180`) |
| Snapshots / rollback | Per-domain content service (`policies/revise.py:40,102,125,140,317,346,368`) |
| Ambiguity declarations | AmbiguityHandler component, no diff log |

This is fine for getting work done but **fatal for pillar #2 if left
alone.** A worldview we cannot trace, diff, or evaluate against is just
bookkeeping with extra steps. The "transparency dividend"
(observability / evals / red-team) demands a single canonical container,
not state scattered across five components.

### Recommendation: DialogueState becomes the canonical worldview container

Five concrete moves, ordered by leverage:

1. **Scratchpad moves into DialogueState, not Memory Manager.** L1 is
   *session-scoped and turn-mutable* — that is the definition of dialogue
   state. Memory Manager keeps L2 (user prefs) and L3 (business context).
   The current placement was a design artifact, not load-bearing.
   Concretely: `state.scratchpad.write(key, value)` /
   `state.scratchpad.read(key)`, with diffs captured automatically.
2. **Snapshots / rollback move into DialogueState.** The spec already
   declares this (`_specs/components/dialogue_state.md:91-93`); the code
   has drifted. Per-domain content services should not own undo —
   rollback IS state-rewind. Single owner: DS.
3. **Flow `stage` formalized as a DS-level field.** `audit_policy` and
   the upcoming `chat_policy` both need a sub-stage marker. Today it's a
   freeform attribute on the flow object. Promote to
   `state.get_flow_stage(name)` / `state.set_flow_stage(name, value)`,
   logged through the diff stream so traces capture stage transitions for
   free.
4. **Slot beliefs stay on flow objects, accessed via DS.** Don't flatten
   — slot classes have rich behavior (`fill_slot_values`,
   `check_if_filled`, `is_verified`, `mark_as_complete`) tied to the flow
   class hierarchy. But add a uniform read API:
   `state.get_slot(flow_name, slot_name)`, `state.iter_filled_slots()`.
   Internal ownership unchanged; external surface consolidated.
5. **Ambiguity declarations get logged into DS.** AmbiguityHandler stays
   the resolver, but DS records the per-turn declaration history. Diff
   stream now answers "when did the agent first become uncertain about
   this?" — gold for evals and red-team replay.

### What this buys

- One trace target → emit DS diffs as OpenTelemetry / OpenInference events
  and the observability story is mechanical, not aspirational.
- One eval target → eval scenarios assert on DS shape, not output text.
  This is what makes pillar #2's evaluability claim cash out.
- One snapshot target → undo, time-travel debugging, durable execution
  resume points all read from the same place.
- One red-team target → structured attack surface (slot injection,
  ambiguity-trigger manipulation, scratchpad poisoning) is enumerable.

### What stays unchanged

Internal storage and behavior of flows, slots, and policies.
Slot-filling logic, flow lifecycle transitions, `keep_going` semantics
all unchanged. This is an *aggregation/API* refactor, not a
re-architecture. Roughly 1–2 weeks: move snapshot logic out of content
services, move scratchpad ownership from Memory to DS, add read-through
accessors, register `flow.stage` through DS.

---

## Q2 — Do We Need NLU / PEX / RES as Modules?

### Per-pillar load test

Modules earn their keep only if they uniquely carry pillar weight.

| Pillar | NLU | PEX | RES |
|---|---|---|---|
| **#1 Ambiguity Handler** | Load-bearing — `general` / `partial` levels live here; `prepare()` / `validate()` are natural pre/post-hook anchors | Load-bearing — `specific` / `confirmation` levels declared from policies; `verify()` / `recover()` is the Tier 1 repair loop | Light — RES surfaces ambiguity to the user, but the *decision to ask* is made upstream |
| **#2 POMDP Worldview** | Load-bearing — single canonical writer of `state.intent`, `state.flow`, `state.slots[*]` | Load-bearing — single canonical executor against beliefs, single Tier 1 repair surface | Light — RES reads DS, doesn't write it |
| **#3 Trust-Graded Memory** | Neutral — calls Memory but doesn't own access protocol | Neutral — primary consumer; trust-grade enforcement at policy boundary | Neutral — naturalization could use prefs, not where the moat lives |

**NLU and PEX are load-bearing for two pillars each. RES is light across all three.**

### Alt 1 — Keep all three modules

| Pros | Cons |
|---|---|
| Maps cleanly to the 4-level ambiguity taxonomy (NLU general/partial, PEX specific, RES confirmation) | Triplicates pre/post-hook ceremony; RES post-hooks duplicate work the agent loop already does |
| NLU as canonical state writer enforces the worldview pillar | RES `naturalize()` overlaps with what skill-driven LLM calls already produce — second LLM pass is largely redundant |
| Three pipeline stages = three places to instrument for the transparency dividend | Forces a "RES turn" even when the policy already produced perfectly usable text |
| Familiar to anyone reading the spec | Symmetry is the wrong reason to keep a layer; the cost is a module that doesn't earn its keep on pillar value |

**Weight: 6/10.** Symmetry is real but symmetry alone doesn't justify a module.

### Alt 2 — Drop the modules entirely (NLU / RES → components, PEX → policy registry)

| Pros | Cons |
|---|---|
| Matches L1 SDK pattern (Strands, Claude Agent SDK, OpenAI Agents SDK) — fewer concepts to teach | **Breaks pillar #2.** No canonical writer for DS → policies re-implement intent classification ad-hoc, exactly the failure mode the user already cited ("policies taking on NLU's job") |
| Each policy becomes a self-contained subagent — Markovian, scalable | Breaks pillar #1's natural anchors. The 4 ambiguity levels lose their pre/post-hook homes |
| Less code on paper | Two-tier failure recovery (PEX inline repair → Agent cascade) loses its outer structure |
| | The user's stated goal — "stateless policies, Markovian behavior based on state" — *requires* a single component to set the state. That component IS NLU. Removing it pushes the work into policies, defeating the goal |
| | "Most frameworks don't have these modules" reflects coding-agent positioning. Voiceflow and Botpress (our actual peers in sustained dialogue) keep an NLU stage. Our market, not theirs |

**Weight: 3/10.** Looks lean; quietly breaks pillars #1 and #2. The
user's own observation that policies "take on NLU's job when slots are
wrong" is the symptom of *insufficient* NLU, not too much of it. Fix is
to strengthen `contemplate()`, not to delete the module.

### Alt 3 — Hybrid: keep NLU + PEX as modules; demote RES to a component (RECOMMENDED)

| Pros | Cons |
|---|---|
| NLU stays as canonical state-writer → pillar #2 protected | One-time refactor cost: redistribute RES responsibilities |
| PEX stays as canonical state-executor + Tier 1 repair → pillar #1 protected | Stack cleanup and multi-flow merge move to the agent loop — slightly thicker orchestrator |
| RES `naturalize()` folds into policies — they already write the response text via skills (`revise.py:41,142,194,234,318,347,379`); the second LLM pass was redundant | Loses RES as a single style/tone enforcement point — must rely on policy skills sharing a base prompt, or a thin opt-in `naturalize_helper()` |
| RES post-hooks (`start()`, `finish()`) move to the agent loop, where they belong — orchestration concerns, not response-rendering concerns | Need to keep some RES-shaped concerns: multi-flow merge when `keep_going` accumulates frames, display-frame → block routing |
| Display Frame stays a component (already consistent with how policies use it) | Architecture diverges from the spec — `_specs/architecture.md` will need an update |
| The 2-module result stays opinionated (vs. SDK lean) but the opinion is *justified by pillar value*, not by symmetry | |

**Weight: 9/10.** Removes the layer that doesn't earn its keep, keeps
the two that do, and matches the user's diagnosis.

### What "RES becomes a component" means concretely

- **Goes away from RES.** `respond()` as a separate LLM-pass for
  naturalization. Policies already emit final response text through their
  skills (`text, tool_log = self.llm_execute(...)` at `revise.py:41` and
  six other sites in `revise.py` alone).
- **Moves to the agent loop.** Stack cleanup (popping completed flows),
  `keep_going` continuation, multi-flow merge, post-hook validations.
  Most of these are already orchestrator-shaped; the move is honest.
- **Stays as a component.** Display-frame block routing and a thin
  `naturalize_helper()` policies *can* call when they want consistency.
  Optional, not mandatory.
- **Reframed.** Ambiguity surfacing to the user. When ambiguity is
  present, today RES picks a clarification template; make it a small
  `AmbiguityHandler.surface()` method on the existing component instead.

### Are we innovative or outdated?

The 3-module shape is a 1990s spoken-dialogue-system inheritance
(`_specs/architecture.md` even cites the POMDP-DST lineage). Innovation
isn't in keeping all three out of nostalgia — it's in keeping the two
that *uniquely* carry our pillars (NLU writes the worldview, PEX is the
Tier 1 ambiguity surface) and dropping the one that doesn't. That puts
us roughly where Voiceflow sits architecturally (NLU + policies + thin
response layer) but with pillar-aligned justification rather than
design-tool inheritance.

The truly outdated move would be keeping RES because the diagram has
three boxes. The truly innovative move is also not "delete everything,
trust the LLM" — that's Strands, and 2026 web evidence shows Strands
struggles on the multi-turn ambiguity axis we own. The hybrid is the
honest middle.

### Final Answer

Three modules → **two modules + a richer agent loop.** Keep NLU and PEX
as they directly carry pillars #1 and #2. Demote RES because its only
load-bearing responsibilities (orchestration, post-hooks) belong in the
agent loop, and its non-load-bearing one (naturalization) is what
skill-driven LLM calls already do for free.

### Implementation Note

This is *not* a Phase A blocker. NLU and PEX are pillar-load-bearing and
already in good shape; the RES demotion is opportunistic. Sequence:

- Q1 (DialogueState consolidation) goes first — it's the substrate. ~1–2
  weeks. Pillar #2 doesn't fully cash out without it.
- Q2 (RES demotion) waits until Q1 is stable. Naturalize-in-policy and
  agent-loop post-hooks are easy mechanical refactors once DS owns its
  diffs. ~1 week per domain.
- The `_specs/architecture.md` rewrite happens after both ship, not
  before.

---

## Q3 — DialogueState Lifetime and Persistence

The user's framing is correct: per-turn was the right scope when surviving
NLU/PEX/RES was the hard problem, but that problem is solved. The hard
problem now is multi-flow coordination via `keep_going`, mid-plan
replanning, and cross-flow handoffs. State scope must follow the problem.

### What the rest of the industry actually does (mid-2026)

| Framework | Lifetime | Backing | Persistence |
|---|---|---|---|
| **LangGraph** | Thread-scoped (≈ session) | In-process per turn | `SqliteSaver` (dev) / `PostgresSaver` (prod). Snapshot per step. |
| **OpenAI Agents SDK** | `Session` | In-process per turn | SQLite default; SQLAlchemy / Redis / Dapr / MongoDB backends; MongoDBSession added v0.14.2 (Apr 2026) |
| **Microsoft Agent Framework** | Workflow-scoped | In-process | Durable Task Scheduler (DTS) checkpoints |
| **Letta** | Session-scoped tiers | In-process Core / Recall | Postgres + vector store for Archival |
| **Strands** | None as a structured object | LLM context only | None (this is the bet that doesn't pay off on multi-turn) |
| **ESAA (arxiv 2602.23193, 2026)** | Per agent run | Materialized view in-process | Append-only `activity.jsonl` event log with hash-verified replay |

The consensus is decisive: **session-scoped, in-process for the hot loop,
durable per-session backend, optional event log for replay.** Per-turn is
nowhere; per-flow is nowhere. Strands' "no structured state" is the
outlier — and the outlier we already chose not to be.

### Final recommendation

**(a) Lifetime: per session.**

- Per-turn is an artifact of when "surviving the pipeline" was hard.
  It's solved. Per-turn state today drops cross-flow context every
  `keep_going` continuation, which is exactly when we need it.
- Per-flow is wrong because flows compose. `audit_policy` stacks sub-flows
  whose state must coordinate; Plan flows replan mid-execution; the chat
  dispatch in `master_plan.md` reads scratchpad written by sub-flows.
  State that ends with the flow erases pillar #2's worldview between
  flows.
- Per-session is what pillar #2 actually needs: a single object that
  answers "what does the agent believe right now?" across the entire
  conversation, with the worldview surviving every `keep_going` boundary.
- Aligns with every credible 2026 framework (LangGraph threads, OpenAI
  Sessions, Letta, MS Agent Framework).

**(b) Backing: in-process Python object + JSONL append-only log + SQLite
checkpoint. No Redis yet.**

- **Hot loop (within a turn)**: a single in-process `DialogueState` object.
  Policies read and write it directly. No serialization on the hot path.
- **End of turn**: append one JSONL line to `activity.jsonl` per session
  (ESAA pattern; web-validated 2026 architecture). One line = the diff +
  the projected belief view. Grep-able, replay-able, hash-verifiable.
  This is the observability story for pillar #2 *as a side effect* of
  the persistence design — no separate dashboard, no separate
  instrumentation, just the log.
- **Resume-session**: SQLite checkpointer keyed by `session_id`. Latest
  full belief view + pointer to the JSONL log offset. Matches LangGraph's
  `SqliteSaver` and OpenAI's default. ~0 ops cost on a developer
  laptop; trivial to ship.
- **Redis: not yet.** Industry uses Redis only for sub-millisecond
  cross-process coordination (multi-worker shared state, real-time agent
  swarms). We're single-worker per session, user-paced. Adding Redis now
  is premature optimization; revisit only when we hit either (i)
  multi-worker contention, or (ii) sub-50ms state-read deadlines we can't
  meet from in-process + SQLite.

**(c) Shape: current beliefs only. History lives in the JSONL log, not
in active state.**

- The 2026 named failure mode is *context bloat* (xMemory, OpenClaw,
  Cloudflare Agent Memory). Per-session state must NOT mean
  "accumulate everything across turns."
- State at any moment = sufficient statistic for the next move (the MDP
  property). Past intents, past tool calls, past frames — all in the log,
  reconstructable on demand by replay, but not in `state`.
- Diffs are computed at end-of-turn for the log; they're not retained
  across turns in memory.

### Signs we've gone too far (breaking points)

If any of these light up, scope crept and the design is leaking:

| Signal | What it means | Fix |
|---|---|---|
| Serialized state >10KB per typical session | State is storing the conversation, not the beliefs | Move accumulated history to the JSONL log; keep state to current-only |
| Belief diff replay >50ms | State grew with history instead of staying current | Same as above; replay is for the log, not for active state |
| Field preserved "just in case" across turns | State is leaking into archive responsibility | Move to log; only keep if a stateless policy *needs* it next turn |
| Two homes for the same data (e.g., slot value on `flow.slots[*]` AND mirrored to `state.slot_cache[*]`) | Sufficient-statistic contract broken; sync drift inevitable | Single owner; surface via accessor (`state.get_slot(...)`) not mirror |
| Need to grep state to debug | The log isn't capturing what the state contains | Fix the diff emitter, not the state shape |
| Policies reach into `memory.scratchpad` for *inputs* (not outputs) | Side-channel coordination; pillar #2 contract broken | Move belief data to state; scratchpad is for working notes only |
| State load on session resume >100ms | Checkpoint is replaying too much history | Snapshot the latest belief view, not the full log; the log is for replay-on-demand |
| Multi-worker contention forces locking | We've outgrown single-worker per session | *Then* introduce Redis for hot state; SQLite for archival |

### What this means concretely (the contract)

A new policy can be added that takes only `(state, context, tools)` and
acts correctly without touching `memory.scratchpad`, `flow.stage`,
`content_service`, or any other side channel. If that's true, pillar #2
holds. If a new policy needs a fourth argument, the design has failed.

The kill criterion (sharper than `alternate_directions.md` had it):
**if we ever introduce a new "where does belief data live" axis — a
third home for slot data, a second home for ambiguity — pillar #2 has
failed and we drop it.** Pillar #2 lives in a single object or it
doesn't exist.

### Why this is "right trend," not over-engineering

The over-engineering question is the right one to ask, and the answer is
no for three reasons:

1. **The industry already converged here.** LangGraph, OpenAI, MS Agent
   Framework, Letta all ship session-scoped state with durable per-thread
   backends. It's not exotic; it's the floor. Going below the floor
   (per-turn) is what would now look outdated.
2. **The cost is a SQLite file and a JSONL appender.** Both are
   stdlib-or-near-stdlib. The complexity is in the discipline (current
   beliefs only, single owner per fact, log for history) — not in the
   infrastructure.
3. **The transparency dividend is mechanical, not aspirational.** Pillar
   #2's eval / observability / red-team payoff requires a single canonical
   belief object with diffable history. JSONL is *exactly* that with a
   2026-published research backing (ESAA). We're not inventing; we're
   adopting a pattern already validated.

The over-engineering risk lives elsewhere: in *what we put inside the
state*, not *how long it lives*. Lifetime is the cheap call. Shape
discipline is the expensive one — and the breaking-points table above
is how we hold the line.

### Sequence

1. **Q1 first (DS consolidation).** Move scratchpad, snapshots, stage
   into DS as proposed above.
2. **Q3 immediately after (persistence).** SQLite checkpointer + JSONL
   appender. ~3-5 days of work; both are libraries.
3. **Q2 last (RES demotion).** Wait until DS owns its diffs; then RES
   demotion is mechanical.
4. **Gate before any new domain (Recruiter):** the contract test —
   "a new policy can be added reading only `state, context, tools`" —
   must pass on Hugo. Otherwise we ship the leak twice.

---

## Corrections to Q1 / Q2 After Q3 and Reviewer Comparison

Recording corrections rather than silently rewriting, because the
*reasoning* matters as much as the conclusion. Three to Q1, one to Q2.

### Q1 corrections

**(1) Walk back: "scratchpad moves into DS wholesale."**

`alternate_directions.md` has the sharper test: **scratchpad = working
notes; state = beliefs.** Hugo's `audit_policy` writing findings to
`memory.scratchpad['audit']` for cross-flow consumption is a pillar #2
violation — but the fix is to move *those specific findings* into state
because they are beliefs, not to relocate the entire scratchpad. Genuine
working notes (a policy's intermediate considerations before picking an
option) stay in scratchpad. The original blanket move would have
polluted the belief object with deliberation noise.

Revised rule: **belief data passed cross-flow goes to DS; working notes
stay in scratchpad.** The test that decides borderline cases: if a
downstream policy depends on it to act correctly, it's belief data.

**(2) Walk back: "snapshots / rollback move into DS."**

`alternate_directions.md` makes the cleaner cut, and `direction_review.md`
reaches the same answer: **belief diffs ≠ content snapshots.**

| Concern | Lives in | Purpose |
|---|---|---|
| Belief diffs (slot, stage, ambiguity changes) | DS at end-of-turn → JSONL log | Replay, observability, eval |
| Content snapshots (the actual post text) | Per-domain content service (Hugo: `_snap_root` reached via `record_snapshot()` in `revise.py`) | Content rollback (`{08F}`) |

Hugo's `record_snapshot()` calls capture post content, not beliefs.
They stay where they are. The original move would have entangled two
cleanly separated concerns and created a maintenance burden in DS for
content the agent doesn't reason about.

**(3) Sharpen: "ambiguity declarations get logged into DS" → projection only.**

`alternate_directions.md` self-corrected on exactly this: pulling the
AmbiguityHandler's state into DS would *demote* it from a first-class
component (with agency: declare, ask, resolve, present) to a struct
attribute. That weakens pillar #1 to strengthen pillar #2 — wrong trade.

Revised: **AmbiguityHandler stays a first-class component. DS holds a
read-only projection** (`level`, `metadata`, `declared_at_turn`) so any
reader can see uncertainty without depending on the handler. The handler
*owns* uncertainty; DS *exposes* it. Same destination for the trace
exporter; cleaner separation of agency from belief.

**(4) Add (from Q3): belief diffs are logged, not retained.**

The ESAA pattern shows replay-from-log is how prior beliefs get
reconstructed. Active DS holds *current beliefs only*; diffs are
emitted to the JSONL log at end-of-turn and dropped from memory. This
collapses two earlier ambiguities — "where do diffs live?" and "how do
we keep state from bloating?" — into one answer: log for history,
state for now.

### Revised Q1 recommendation (consolidated)

DialogueState is a **thin coordinator + sufficient statistic** for
current beliefs. Concretely:

| Move | Status |
|---|---|
| `flow.stage` formalized as canonical DS field | ✅ Unchanged |
| Slot beliefs stay on flows, uniform read API on DS | ✅ Unchanged |
| Cross-flow *belief* data (findings, decisions) moves from scratchpad to DS | ✅ Refined from "scratchpad into DS" |
| Working notes stay in `MemoryManager` scratchpad | ✅ New (corrects original) |
| Belief diffs computed end-of-turn, emitted to JSONL log | ✅ New (from Q3) |
| Content snapshots stay in per-domain content service | ✅ Reverses original |
| AmbiguityHandler stays first-class; DS holds projection only | ✅ Sharpened from original |
| Active state size: <10KB serialized; current beliefs only | ✅ From Q3 breaking points |

### Q2 corrections

**(1) Refinement: slim NLU and PEX *implementations* too, not just demote RES.**

`alternate_directions.md` makes the point: the spec ships heavy
sub-method taxonomies (`understand` / `react` / `contemplate`; `execute`
/ `recover`; `generate` / `clarify` / `display`) and most of the
ceremony hasn't earned its keep on Hugo. PEX is a dispatcher with a
small repair loop; NLU's sub-methods overlap in practice. Keep the
*module boundaries* (pillar #1 attaches gates to them) and the
*lifecycle phases* (pre-hook / dispatch / post-hook), drop the
sub-method ceremony that doesn't pull weight.

The test from `alternate_directions.md`: if a method can be moved
between modules without breaking anything, the boundary is bookkeeping,
not a contract. Slot recovery in policies is *not* bookkeeping (the
policy knows what it still needs); RES's `naturalize()` *is* (skill
output already serves).

**(2) Walk back: "PEX should add hooks at lifecycle points."**

PEX already has them — `_security_check` (pre-hook,
`pex.py:171`), `_validate_frame` (post-hook, `pex.py:212`), `_verify`
(`pex.py:632`). They do real work today. The right framing is
"**widen what gets run at each existing hook** (pre-tool, post-tool,
on-flow-push, on-flow-pop) as extension points," not "introduce hooks."
Borrow item should be read as opening the existing hook surface, not
adding a new primitive.

### Revised Q2 recommendation (consolidated)

Hybrid stands. Two modules + thicker agent loop, with implementations
slimmed:

| Module | Keep | Slim |
|---|---|---|
| **NLU** | Module boundary + pre/post-hook gates (pillar #1) | Drop sub-method ceremony where overlap is real; keep `prepare()` / `validate()` / `contemplate()` only as named entry points, not separate algorithms |
| **PEX** | Module boundary + dispatch + repair loop (pillar #1, pillar #2) | Open existing hooks as extension points; drop sub-method taxonomy that doesn't earn its keep |
| **RES** | Demoted to `ResponseHelper` component | `naturalize()` opt-in helper; multi-flow merge → agent loop; `clarify()` → AmbiguityHandler method; `finish()` → fold useful checks into PEX `verify()` |

### Why these corrections matter

The corrections all share a pattern: **don't merge components to make
the doc tidy.** Pillar #1 (Ambiguity Handler) and pillar #2 (Worldview)
are stronger as collaborating components than as a fused state object.
The reviewers caught me leaning toward consolidation when separation
was the right answer. Q3's web data reinforces this — the industry
keeps state thin and pushes archival concerns out (to checkpointers,
to event logs), rather than fattening state to "own everything."

**Net effect on the three pillars:** unchanged. The pillars are right.
The corrections are about *where the data lives* and *what owns
agency*, not about which differentiators we're betting on.

---

## Q4 — JSONL Log vs Session Scratchpad: Where to Draw the Line

The Q3 corrections produced an overlap: both DialogueState (logged to
JSONL) and the dict-based scratchpad (Memory Manager L1) hold
session-scoped data. Hugo's actual usage shows they're not as cleanly
separated as the spec implies — `audit_policy` writes findings to
scratchpad that downstream policies depend on. Three competing models;
the recommendation is Model B.

### Model A — Strict separation: DS logged, scratchpad private

| Pros | Cons |
|---|---|
| Cleanest conceptual boundary | Audit findings are belief-relevant — drive sub-flow execution; if log can't capture them, pillar #2's transparency dividend is half-baked |
| Smallest log size | Eval/replay can't reconstruct *why* audit dispatched to polish vs rework — that reasoning lives in unlogged scratchpad |
| Scratchpad "private to the policy" | Red-team can't probe scratchpad-mediated attacks (L1 memory poisoning is invisible) |

**Weight: 4/10.** Tidy on paper; gap in observability.

### Model B — Both logged, separate lanes (RECOMMENDED)

DS holds beliefs (in-process). Scratchpad holds cross-flow + working
data (in-process, stays a Memory L1 tier). JSONL line per turn carries
**both** as separate fields: `belief_diff` + `scratchpad_diff`.

| Pros | Cons |
|---|---|
| Pillar #3 stays intact — scratchpad remains the L1 memory tier per spec | One extra schema field in the JSONL line |
| Pillar #2's transparency dividend covers cross-flow data — eval can grep findings, red-team can probe scratchpad poisoning | Working notes (deliberation) also get logged; minor bloat, but cheap and grep-friendly |
| No judgment call at every scratchpad write — write where it naturally belongs | Replay logic merges two diff streams to reconstruct |
| Matches ESAA pattern (append-only log over multiple materialized views) | |
| Migration cost is a logging layer; existing Hugo code unchanged | |

**Weight: 9/10.** Both kinds of data captured; both pillars preserved.

### Model C — Move all cross-flow data into DS; scratchpad shrinks to true working notes only

| Pros | Cons |
|---|---|
| One canonical "session memory" object | Hollows out pillar #3's L1 tier — Hugo's scratchpad would be nearly empty |
| Strongest pillar #2 surface | Forces a judgment call at every cross-flow write |
| | Bloats DS with data that isn't current beliefs (audit findings persist after audit completes — violates Q3 "current beliefs only" rule) |
| | Migration cost: every scratchpad-using policy needs rewriting |

**Weight: 5/10.** Strengthens pillar #2 by weakening pillar #3. Net negative.

### The line — role-based, not lifetime-based

| What | Where it lives | Logged in |
|---|---|---|
| Predicted intent / flow / slot beliefs | DS (in-process) | `belief_diff` |
| Flow stack lifecycle + `stage` | DS | `belief_diff` |
| Ambiguity projection (handler stays first-class) | DS | `belief_diff` |
| Control flags | DS | `belief_diff` |
| Cross-flow handoff data (audit findings, delegate summaries) | **Scratchpad** | `scratchpad_diff` |
| Working / intermediate notes (used-count, version markers, skill-internal scratch) | Scratchpad | `scratchpad_diff` |

**Test for borderline cases:** is this what a policy reads to decide its
*current action* (belief → DS), or what a policy produced or coordinated
*during execution* (handoff → scratchpad)?

### Hugo example — applied

Concrete cuts in `revise.py`:

| Data | Cut | Why |
|---|---|---|
| `audit.delegates` slot tracking completed sub-flows | **DS** | `audit_policy:214` reads `is_verified()` to decide it's done — pure belief |
| `scratchpad['audit'] = {'findings': [...], 'summary': '...'}` | **Scratchpad** | Working data; converted to slot values when sub-flows are stacked at `revise.py:286-289` |
| `scratchpad['polish'] = {'version', 'turn_number', 'used_count', 'summary'}` | **Scratchpad** | Cross-flow handoff to audit's read loop; consumed via `read_scratchpad('polish')['summary']` at `revise.py:217` |
| `flow.slots['suggestions']` filled from audit findings | **DS** (via flow) | The slot is what the policy acts on; the scratchpad entry was the *recipe* |

The JSONL line for an audit-dispatch turn carries both the
`audit.delegates` bump (in `belief_diff`) and the `audit` findings write
(in `scratchpad_diff`). Replay reconstructs the full picture without
either lane being silent.

### Why Model B over A or C

1. **Pillar #2's transparency dividend needs scratchpad in the log.**
   Cross-flow handoffs drive downstream behavior; a trace that can't
   show them is half a trace. Pillar #2 logs what the agent
   *coordinated*, not just what it *believed*.
2. **Pillar #3 needs scratchpad as a real L1 tier.** Spec already places
   it there; Model C empties it. Don't hollow out one pillar to
   strengthen another.
3. **Matches the validated event-sourcing pattern.** ESAA's
   `activity.jsonl` projects multiple materialized views from one log.
   Model B is the same shape — append-only log, two materialized views
   (DS, scratchpad), reconstructable on demand.
4. **No new concepts introduced.** CLAUDE.md forbids it. Model B keeps
   existing components (DS, scratchpad, log) and just wires the log to
   both.
5. **Migration cost is bounded.** Add a logging layer that emits
   `scratchpad_diff` alongside `belief_diff`. Hugo's policies need no
   changes; the diff captures what they already write.

### Implementation note

Both DS and scratchpad live in-process during a turn. Both get
checkpointed to SQLite for session-resume (LangGraph's standard
pattern — the `thread_id` checkpoint includes the full session state,
not just beliefs). Both emit diffs to JSONL at end-of-turn. Three
materialized views, one event log.

The Q3 breaking-points table extends to scratchpad too: if scratchpad
size grows unbounded across turns (entries that should have been
consumed and dropped), or if the diff stream becomes mostly
`scratchpad_diff`, the cut is being applied wrong — likely beliefs are
ending up in scratchpad. Audit and review.
