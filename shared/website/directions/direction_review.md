# Review of `potential_directions.md`

## Top-line Verdict

**~80% agreement.** The doc's three pillars (Ambiguity Handler, Three-tier
Memory, Synthetic Data) survive scrutiny, but two of the three need to be
**reframed**, not just kept. The doc's biggest weakness is conflating "what is
genuinely differentiated" with "what wins the marketing pitch" — those are not
the same audience, and the top 3 should serve both.

The doc also under-weights two things the user explicitly named:

1. **The agent's "own world view."** This is what answers sycophancy. The
   doc treats slot-flow lifecycle as plumbing, but slot-flow + dialogue-state
   IS the agent's world view in operational form. Demote at your own risk.
2. **The "non-coding domain" problem.** None of the three pillars is named
   for this, even though it's user-stated problem #1. The doc's #3 (synthetic
   data) is the *mechanism* for non-coding domains, but that's not how the doc
   frames it. Reframe #3 as **"spec-to-agent pipeline"** and the connection
   becomes obvious.

The recommended top 3 below are the doc's three with sharper framing and an
explicit map to the user-stated problems.

---

## Where the Doc is Right (Don't Re-Litigate)

These calls are correct and shouldn't be reopened:

- **Absorb POMDP framing into Ambiguity Handler.** They are one idea wearing
  two hats. The doc's ranking surfaces this honestly.
- **Drop the compositional dax grammar as a *headline* idea.** Keep the codes
  as internal IDs, but stop trying to make them semantically meaningful. The
  16-primitive teaching cost is real and the differentiation value is near-zero.
- **Park the universal dialogue-state protocol.** Research artifact. Belongs
  in the interview-prep folder until cross-agent interop is a paying customer.
- **Borrow per-flow PEX verify/recover from LangGraph / MS Agent Framework.**
  Custom-build only the verify/recover paths that are genuinely AF-specific
  (i.e., ambiguity recovery).
- **Borrow the Claude Agent SDK subagent dispatch pattern for Internal flows.**
  Don't rebuild the orchestration; the unique parts are the *flows*, not the
  swarm machinery.
- **The compounding loop story.** Ambiguity → Memory → Synthetic Data →
  back to Ambiguity is genuinely a virtuous loop, and removing any one of the
  three breaks it. This is the doc's strongest argument.

---

## Where to Push Back

### Push-back 1 — Synthetic Data is the right #3, but the doc oversells it

The doc rates synthetic data **5/5 ML-friendly, 4/5 robustness, 2/5
productivity** and counts it as a top-3 differentiator. The "2/5 productivity"
is honest — synthetic data is *not user-facing*. Users will never say "wow, AF
has a great synthetic data pipeline." So the doc is implicitly mixing two
audiences:

- **End users / customers** — feel #1 (no false confidence) and #2 (knows my
  business). Don't feel #3.
- **AF the company / domain builders** — feel all three, especially #3,
  because #3 is what lets AF ship Hugo, Dana, Kalli, Blogger, Recruiter,
  Scheduler without an army of annotators.

The fix is **reframing #3 as "spec-to-agent pipeline"**, not "synthetic data
augmentation." The synthetic data piece is the *mechanism*; the *product* is
"write a spec, get a working agent in a week." This reframe:

- Maps directly onto user-stated problem #1 (over-fitting to coding) — the
  factory works for non-coding domains because the pipeline is domain-agnostic.
- Is the only one of the three pillars that explicitly addresses the
  Bitter Lesson criterion.
- Aligns with the product name. AF is literally a *factory*. The factory's
  output is agents. The pipeline is the assembly line.
- Honest to the dual audience: builders feel it directly, end users feel it
  indirectly via faster domain coverage and more reliable behavior.

Synthetic data alone is becoming commoditized — every research group does
this. The novel asset is the **coupling of the pipeline to AF's ontology
format**: spec changes auto-regenerate slots, exemplars, and eval scenarios.
Lead with the coupling, not the data generation.

### Push-back 2 — "Vetted/unvetted memory" is thinly defended

The doc's case for three-tier memory is good on productivity (5/5) but the
*differentiated* part — the trust gradient between vetted and unvetted — is
defended in two paragraphs and a hand-wave. Concrete pressure tests:

- **Letta is 6–12 months from this.** Their three-tier architecture is older
  and more polished; adding a trust marker is one PR.
- **Zep already has temporal validity** (`valid-from` / `valid-until`),
  which is a related-but-different trust signal. A user asking "why AF over
  Zep?" needs a sharper answer than what the doc provides.
- **The "automated vetting" claim is aspirational.** Today the trust grade
  is hand-curated. The ML path (corrections → labels) is plausible but
  unbuilt. The doc presents this as a virtue ("trainable once corrections log");
  it's also a risk ("we don't know if calibration will actually work").

This is still the right #2, but the headline should be sharper. Suggested
phrasing: **"Memory with calibrated trust, not just retrieval."** The memory
manager doesn't just return facts; it returns facts with a confidence label
that the Ambiguity Handler can read. That's the integration story Letta and
Zep don't have.

### Push-back 3 — Slot-flow lifecycle is undersold

The doc demotes slot-flow lifecycle coupling to "infrastructure, not an idea."
This is a defensible call but worth poking at, because the user explicitly
named **sycophancy** as a problem and slot-flow is the most direct mechanism
against it.

- A sycophantic agent says "yes, done!" when it isn't done.
- A slot-flow agent **cannot** terminate a flow with unfilled required slots.
- The lifecycle is the agent's *own definition* of what "done" means,
  independent of the user's last assertion. That's the world-view property.

That said: slot-flow is hard to *market* on its own. "Predictable termination"
is a developer-facing property, not a user-facing one. Users don't shop for
agents on this axis even though they should.

**Resolution:** keep the doc's call (slot-flow stays as infrastructure), but
elevate it in the *technical* pitch. When someone asks "how does AF avoid
sycophancy?" the answer is two parts: (a) Ambiguity Handler asks when unsure,
(b) Slot-flow lifecycle won't let the agent fake completion. Cite both.

### Push-back 4 — The doc doesn't map ideas to user-stated problems

The user named three problems. The doc presents three pillars. But the doc
never draws the lines between them. Here's the mapping that should be in the
doc:

| User problem | Primary AF answer | Secondary support |
|---|---|---|
| Over-fitting to coding | **Spec-to-agent pipeline (#3)** — domain-agnostic | Ontology + slot-flow let any vertical describe itself |
| Over-confident hallucination | **Ambiguity Handler (#1)** — knows when unsure | Memory's vetted/unvetted prevents asserting from raw retrieval |
| Sycophancy | **Ambiguity Handler (#1) + slot-flow** — won't agree it's done | Memory grounds in reality, not user's latest assertion |

Notice that **Ambiguity Handler hits two of the three user problems**, which
is why it's correctly locked in. The other two pillars each cleanly own one
problem.

### Push-back 5 — The compounding loop argument has a hole

The doc claims: "Without synthetic data, we can't iterate without
expert-authored data." This is true at *bootstrap* but becomes less true once
real users start logging corrections. Real corrections are higher-quality
calibration signal than synthetic ones.

This doesn't change the verdict (synthetic data is still right for #3 because
of the bootstrap problem) but it does change the framing. **Synthetic data
matters most in the first 6 months of a new domain; less afterward.** That's
fine — bootstrapping new domains *is* the factory's job.

---

## Recommended Top 3 (Final)

Same three pillars as the doc, with sharper framing:

### 1. Ambiguity Handler — *robustness pillar* (lock-in)

Uncertainty as first-class content, declared and resolved at four levels.
Pitch: "the agent knows when it's confused and clarifies before acting."

Owns: hallucination problem, sycophancy problem (in part).

### 2. Memory with Calibrated Trust — *productivity pillar*

Three-tier memory (scratchpad / preferences / business context) with a trust
gradient on every retrieved fact. Pitch: "the agent doesn't confidently assert
what it merely searched for."

Owns: long-horizon productivity. Differentiates from Letta on the trust
gradient and from Zep on the integration with Ambiguity Handler.

### 3. Spec-to-Agent Pipeline — *Bitter-Lesson pillar*

Synthetic data + ontology + slot-flow + skill templates, packaged as a
pipeline that turns a domain spec into a working agent. Pitch: "write a spec,
get a working domain agent in a week, not three months."

Owns: non-coding domain coverage, Bitter Lesson axis, "factory" identity.

---

## Buy / Build / Borrow

The doc gestures at this; here's an explicit table.

### Build (the moat)

| Capability | Why build |
|---|---|
| Ambiguity Handler (4 levels) | No SDK has this. Productizes academic work. |
| Memory trust gradient | Letta/Zep don't have it. Integration with Ambiguity is unique. |
| Spec-to-agent pipeline | No L1/L2 framework expects you to bring a spec; most expect data. |
| Slot-flow lifecycle | Voiceflow/Botpress have entities + flows but no formal lifecycle. |

### Borrow (adopt patterns, not implementations)

| Capability | Source | Notes |
|---|---|---|
| Hooks at lifecycle points | Claude Agent SDK | Widen our pre/post-hooks to 25-ish points. |
| Subagent dispatch (Internal flows) | Claude Agent SDK | The pattern, not their runtime. |
| Workflow primitives (Sequential / Parallel / Loop) | Google ADK | For Plan flow's sub-flow orchestration. |
| Durable execution / checkpointing | LangGraph + MS Agent Framework | Closes our snapshot/rollback gap. |
| Three-tier memory architecture | Letta | Adopt the architecture, add the trust gradient. |
| Temporal validity on facts | Zep | Bolt onto business context tier. |
| Tiered guardrails (input / output / per-tool) | OpenAI Agents SDK | Vocabulary for our pre/post-hooks. |
| Skill metadata pattern | Claude Agent SDK | Replace `prompts/skills/` markdown files with metadata-first skills. |

### Buy (consume off-the-shelf)

| Capability | Source |
|---|---|
| LLM providers + native tool-calling | Anthropic, OpenAI, Google APIs |
| MCP servers / tool registries | Composio, Arcade, Smithery |
| Voice (if/when on roadmap) | Vapi, Retell |
| Observability + traces | Langfuse (default), Braintrust as alt |
| OAuth / credential storage | Standard libraries |
| Vector DB | Off-the-shelf (Chroma, pgvector, Pinecone) |

### Drop or radically simplify

| Capability | Why |
|---|---|
| Compositional dax grammar | Hand-engineering. Keep dax codes as opaque IDs; drop the 16-primitive grammar. |
| Universal dialogue-state protocol | Research vision. Park. |
| Per-flow PEX hand-engineering for verify/recover | Borrow LangGraph nodes for the generic case; custom-build only ambiguity recovery. |

---

## Rough Roadmap

Three phases, each ~2 quarters. The roadmap respects "narrow scope" — each
phase delivers one pillar to a shippable state before opening the next.

### Phase A (Q3–Q4 2026): Ambiguity + Slot-Flow Foundation

The robustness pillar lands first because it gates everything else. If the
agent can't recognize confusion, the rest of the system can't compensate.

- Ship Ambiguity Handler at all four levels (general / partial / specific /
  confirmation) integrated into NLU, PEX, RES.
- Slot-flow lifecycle hardened: predictable termination, required-slot
  enforcement, snapshot/rollback. This is *infrastructure for #1*; doesn't
  need a marketing story but does need to work.
- Borrow durable execution from LangGraph or MS Agent Framework — closes the
  snapshot/rollback gap.
- Borrow Claude SDK hooks pattern at NLU/PEX/RES boundaries.
- **Structured trace exporter to Langfuse.** Belief-state, slot-fill, and
  ambiguity-flag transitions emitted as structured spans. Makes pillar #1
  demoable; without this the Ambiguity Handler is invisible.
- One reference domain (Hugo) running end-to-end with Ambiguity actually
  changing behavior, not just decorating logs.
- **Drop**: dax grammar simplification (mechanical refactor, schedule mid-phase).

### Phase B (Q1–Q2 2027): Memory with Calibrated Trust

Once the agent recognizes uncertainty, give it grounded knowledge to reduce
*how often* it has to ask. This is the productivity payoff.

- Three-tier memory shipped (scratchpad / preferences / business context).
  Borrow Letta's three-tier architecture; bolt on Zep-style temporal validity
  on business context.
- Trust gradient labels on every retrieved fact. Initially hand-curated; ship
  the *vocabulary* and the *integration path* with Ambiguity Handler.
- Memory ↔ Ambiguity integration: low-trust retrievals automatically raise
  ambiguity flags. This is the cross-pillar win nobody else has.
- One reference domain demonstrates session-to-session memory continuity
  ("the agent that knows your business").
- Synthetic data pipeline starts being used internally to populate vetted
  business-context tier for new domains. Not yet a product story.

### Phase C (Q3–Q4 2027): Spec-to-Agent Pipeline (Public)

The Bitter-Lesson pillar goes public. Until now synthetic data has been an
internal tool; now it becomes the factory's marketing surface.

- Spec format stabilized (YAML + ontology + slot definitions + skill stubs).
- Pipeline: spec → synthetic utterances → eval scenarios → trained slot
  filler / classifier → working agent. Hugo, Dana, Kalli were built by hand;
  Blogger / Scheduler / Recruiter are built by the pipeline.
- Public-facing claim: "ship a domain agent in a week." Time-to-first-agent
  becomes the headline metric.
- Calibration loop: real user corrections feed back into the labels for
  Ambiguity Handler thresholds and Memory trust grades. This is when the
  compounding loop starts compounding for real.
- **Drop**: any remaining hand-engineering for Slot-flow lifecycle that the
  pipeline can subsume.

### Phase D (2028+): Open questions

- Universal dialogue-state protocol — revisit *only if* a customer asks for
  cross-agent interop. Otherwise leave it parked.
- Plan flow with replanning — by now ADK/MSAF workflow primitives may be
  good enough. Audit and possibly delete our custom replanning logic.
- The Strands experiment: rebuild Hugo as a 100-line Strands agent. If it
  matches AF on multi-turn ambiguity, the moat is in the wrong place.

---

## On Observability / Evals / Monitoring / Red-Teaming

Mid-2026 hot trend. Worth a separate section because the question is sharper
than "should we care?" — it's "should this be a 4th pillar?" The intuition
that dialogue state enables dramatically richer transparency is correct: a
Strands trace shows "agent said X, called tool Y"; an AF trace shows "agent
believed user wanted A with confidence 0.6, Ambiguity Handler raised a partial
flag, NLU re-routed, belief updated to B, PEX executed." That's a real asset.

**It is not a 4th pillar.** Four reasons:

1. **It's a consequence of pillar #1, not a separate commitment.** The
   dialogue state already exists. Emitting structured traces is a few hooks
   away. The differentiated thing is *having explicit beliefs*, which is
   pillar #1. Don't double-count the same idea under two banners.
2. **L3 infrastructure is not our layer.** Langfuse, Braintrust, LangSmith,
   Arize, and Helicone are mature, well-funded, and shipping faster than AF
   could match. Building our own observability backend is the same trap as
   rebuilding tool-calling JSON parsing.
3. **"Hot trend" is also a smell.** If every framework is sprouting an
   observability story, the trace pipeline isn't a moat. Our moat is *what
   we put into the trace*, not the pipe itself.
4. **The narrow-to-3 constraint is real.** Adding a 4th idea is exactly the
   failure mode the doc was written to avoid.

Per-category breakdown:

| Category | Treatment | Why |
|---|---|---|
| **Observability / traces** | **Derived asset of pillar #1.** Ship a thin structured-trace exporter to Langfuse. Marketing line: "see what your agent believed, not just what it said." | Pillar #1 produces the belief data; Langfuse stores and visualizes. |
| **Agent evals** | **Already inside pillar #3.** The spec-to-agent pipeline produces eval scenarios as part of its output. | Don't double-count. The pipeline emits eval suites. |
| **Monitoring** | **Buy.** Standard ops infrastructure. | Not our specialty. |
| **Red-teaming** | **Small research bet, not a pillar.** Adversarial testing of the Ambiguity Handler (probing for sycophancy / over-confidence) is a tractable research project that strengthens pillar #1. | Genuinely novel angle (state-aware adversarial probes), but small enough to fit inside pillar #1's calibration work. |

**Roadmap impact:** the structured trace exporter is added to Phase A as part
of the Ambiguity Handler ship. Without it, pillar #1 is *invisible* to
enterprise buyers — "show me a trace" is the demo question, and our trace
needs to look meaningfully different from a Strands trace. With it, pillar #1
is demoable in 30 seconds.

**Net change to the top 3:** none. Pillars stay the same. What changes is
that pillar #1's *pitch* should explicitly cite the observability angle, and
the roadmap gains one concrete deliverable in Phase A.

---

## What This Roadmap Implicitly Says No To

To make the "narrow scope" commitment real, here's what's *not* on the
roadmap, even though some are tempting:

- **Plan flow with replanning** as a marketed differentiator. Keep the
  feature, don't elevate it. Borrow ADK's Sequential/Parallel/Loop primitives.
- **Per-flow PEX policies** as a marketed differentiator. Infrastructure.
  Borrow what we can.
- **Internal flow swarm** as a marketed differentiator. Borrow Claude SDK
  subagent dispatch.
- **Voice infrastructure**. Buy when needed.
- **Multi-agent interop / dialogue-state protocol**. Park.
- **Compositional dax grammar**. Reduce to opaque IDs; stop teaching it.
- **Building our own observability stack**. Use Langfuse.
- **Building our own tool registry**. Use MCP + Composio.

If any of these crawl back into the roadmap as differentiators, treat that
as a smell that scope is expanding again.

---

## Architectural Questions

Two structural questions surfaced after the pillars were locked: what should
DialogueState actually *be*, and do we still need three pipeline modules?
Both are answered through the lens of the three differentiators — not "what
makes clean code" but "what serves the pillars."

### Question 1 — DialogueState's shape and role

**Diagnosis: state is anemic because the actual beliefs live elsewhere, and
that's mostly fine.** The fix is not to *enrich* state, it's to *redefine*
it. Right now the spec promises a sufficient-statistic belief tracker; the
code delivers a thin flag-and-prediction holder. Bridge the gap by changing
the spec, not the code.

Where information actually flows today (Hugo's `revise.py` is the case study):

| Information | Lives in | Evidence |
|---|---|---|
| Slot values per flow | `flow.slots[<name>]` | `flow.slots['category'].value` |
| Sub-flow stage | `flow.stage` | `audit_policy` `'discovery'` → `'delegation'`; `chat_policy` plan adds `'pre_dispatch'` → `'post_dispatch'` |
| Cross-flow handoffs | Session scratchpad | `self.memory.write_scratchpad('audit', {...})`, read on second pass |
| Ephemeral picks | `state.slices['choices']` | frontend payload only |
| Active content context | `state.active_post` | one of the few real fields |
| Snapshots / undo | Content service | `self.record_snapshot(self.content, ...)` — not state |
| Ambiguity flags | `self.ambiguity` (handler) | `self.ambiguity.declare(...)` — separate object |
| Conversation history | Context Coordinator | `context.compile_history()` |

The state object holds: flags (`keep_going`, `has_plan`, `has_issues`,
`natural_birth`), predicted intent/flow strings, the predicted-but-not-yet-
distributed slot dict, plus a couple of ephemeral fields. Everything the
spec promised beyond that — diffs, full snapshots, rollback, belief tracking
— either moved elsewhere or never landed.

**This is not a bug; it's a working separation of concerns.** Beliefs that
*belong to a flow* live on the flow. Beliefs that *cross flows* live in the
scratchpad. Beliefs about *content* live in the content service. State
holds the residual: **flags, predictions, and turn-scoped ephemera.**

The redesign is to commit to this honestly:

1. **State is a thin coordinator, not a storage layer.** Stop pretending it
   will eventually hold full belief snapshots. Storage is distributed across
   Flow Stack, Scratchpad, and services. State is the index.
2. **Promote `flow.stage` into the formal model.** The `stage` attribute is
   already in code (`audit_policy`, the new `chat_policy` plan) but absent
   from `_specs/components/dialogue_state.md`. Document it as a first-class
   flow lifecycle field alongside `status`. This is what the master_plan
   relies on.
3. **Drop snapshot/diff/rollback from DialogueState's spec.** It never
   landed and it shouldn't. Undo is content-side; that's correct.
4. **Add a `belief()` accessor that composes the trace view.** Aggregate
   active flow + stage + slot-fill states + ambiguity flags + scratchpad
   keys + intent confidence into a single read-only structured snapshot.
   State *composes* the belief view; it does not *own* the belief data.

**Why this serves the pillars:**

- **Pillar #1 (Ambiguity).** The structured-trace exporter (Phase A) needs
  one query — "what did the agent believe at this turn?" — to emit a
  meaningful Langfuse span. Without `state.belief()`, the trace is scattered
  across three components and impossible to render coherently. The belief
  view IS the demo surface for pillar #1.
- **Pillar #3 (Spec-to-agent).** A thin state schema is easy for the
  pipeline to generate against. Every additional field is a generation
  target with degrees of freedom that produce hallucinated wiring.

State stays small. That's the feature.

### Question 2 — Do we still need three pipeline modules?

**Recommendation: Hybrid (option 3). Keep NLU and PEX as modules. Demote
RES to a helper component.**

Argument by elimination.

**Option 1 (keep all 3) is wrong** because RES is doing very little distinct
work in the current code. Policies already produce
`text, tool_log = self.llm_execute(...)` and assign `frame.thoughts = text`
— the frame's thoughts ARE the user-facing text in most flows. RES's
`naturalize()` is largely pass-through. Symmetry is not a reason to keep a
module.

**Option 2 (drop all modules) is also wrong** for two reasons:

1. **You still need a centralized classifier.** Calling it "NLU" or "router"
   or "dispatcher" is naming, not structure. Whoever picks which policy to
   run is the NLU module. Eliminating the name doesn't eliminate the role.
2. **Ambiguity handling becomes scattered.** Pillar #1 attaches at the
   *boundaries* between intent-detection and action. If every policy does
   its own classification (Strands-style), the ambiguity gate becomes an
   implicit per-policy concern instead of a centrally enforced one. That's
   exactly the moat erosion we don't want.

**Option 3 (hybrid) is right.** Specifically:

- **Keep NLU as a module.** Single source of truth for intent / flow / slot
  prediction. Pre-hook is where pillar #1's first ambiguity gate fires.
  Without this, every policy reinvents classification.
- **Keep PEX as a module.** Policy orchestrator. Post-hook is where
  pillar #1's verify gate fires. Failure cascade lives here.
- **Demote RES to `ResponseHelper`** — a component, not a pipeline stage.
  Policies call its functions inline (`naturalize_text`, `merge_thoughts`,
  `route_to_display`). Multi-flow merge moves to the Agent's `keep_going`
  loop, which is its natural home.

Shape after the change:

```
Agent orchestrator
├── NLU (module)         — classify, slot-fill, pre-hook ambiguity gate
├── PEX (module)         — execute policy, verify, recover
│   └── policies call:
│       ├── ResponseHelper (component)   — naturalize, format
│       ├── Memory Manager (component)
│       ├── Ambiguity Handler (component)
│       └── Prompt Engineer (component)
└── keep_going loop      — multi-flow merge happens here
```

**Why this serves the pillars:**

- **Pillar #1 (Ambiguity).** NLU pre-hook + PEX post-hook = two centrally
  enforced gates. RES had a third gate (`finish()`) but most of what it did
  was naturalization, which doesn't need a gate. Two gates are sufficient
  and cleaner than three.
- **Pillar #2 (Memory).** Orthogonal to module count. No change.
- **Pillar #3 (Spec-to-agent).** Smaller pipeline = smaller spec surface.
  The pipeline describes NLU schemas and PEX policies; it doesn't have to
  describe RES templates. One fewer thing to generate, debug, and
  calibrate.

Migration cost is bounded — RES's current jobs re-home cleanly:

| Today's RES job | New home |
|---|---|
| `naturalize()` from frame thoughts | `ResponseHelper.naturalize()` — called only when a policy returns code/data needing prose |
| `display()` block routing | `ResponseHelper.route()` — pure function, no ceremony |
| `clarify()` for ambiguity | Ambiguity Handler emits question text directly when declaring |
| Multi-flow merge across `keep_going` | Agent orchestrator (where the loop already lives) |
| `finish()` self-checks | Genuinely useful checks fold into PEX `verify()`; drop the rest |

**Honest connection to the Strands hypothesis:** dropping RES is a *partial*
adoption of Strands' bet. Strands argues frontier LLMs don't need a separate
response stage because they already produce well-formed responses. We're
not adopting that bet wholesale — NLU and PEX stay because pillar #1 needs
the boundaries to attach gates to. But RES is the part of our stack where
Strands' bet actually holds. Drop it for that reason, not for tidiness.

### How both answers reinforce each other

These two redesigns aren't independent. The hybrid module shape *requires*
the slim DialogueState redesign:

- If RES becomes a helper, *something* has to expose "what the agent
  believes" for the trace exporter. That something is `state.belief()`.
- If state is a thin façade, the response helper can read directly from
  flows / scratchpad / ambiguity without going through a fat state object.
- `flow.stage` being formalized matters for both: the trace needs it; the
  helper reads it; PEX dispatches on it.

Net effect: one fewer module, one redefined component, and a coherent
belief surface that the structured-trace exporter (Phase A) can render in
~30 lines of code.

---

## Open Decisions for the User

Before this becomes the actual plan:

1. **Synthetic data as #3, or "spec-to-agent pipeline" as #3?** Same
   substance, different framing. I think the latter is sharper but it's a
   judgment call.
2. **Phase A vs Phase B ordering.** I've put Ambiguity first because it gates
   the rest, but you could argue Memory should come first if the immediate
   demo problem is "agents don't remember anything." Phase B-then-A is
   defensible if memory continuity is the bigger near-term customer pain.
3. **How aggressively to drop the dax grammar.** Mechanical refactor that
   touches every domain. If the cost is real, push to Phase C or later.
4. **The Strands experiment.** Worth running in Phase A as a steel-man, even
   though it's listed in Phase D. A quick rebuild now answers the moat
   question before we invest more in scaffolding.
5. **Red-teaming as a small research bet.** Should we fund a 1-engineer
   research thread on state-aware adversarial probes (sycophancy, false
   confidence, slot-coercion)? It's a high-leverage way to validate pillar #1
   and produces publishable artifacts that align with the user's research
   network. Not a pillar; a side bet.
6. **DialogueState redesign.** Commit to "thin coordinator + `belief()`
   accessor" or push back. The risk is that `belief()` becomes the new fat
   state by accumulation; we'd need a discipline to keep it composed-only,
   not stored.
7. **Drop RES as a pipeline module.** Adopt the hybrid (NLU + PEX modules,
   ResponseHelper component) or keep all three. The migration touches every
   domain's policies and tests, so the cost is real even if bounded.

If those seven are settled, the rest of this is implementation.
