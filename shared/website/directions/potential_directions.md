# Potential Directions for Assistant Factory

The agent landscape doc (`agent_landscape.md`) answered "what's already out there." This
doc answers the harder follow-up: **of everything Assistant Factory does differently,
which 3 are worth keeping as our identity, and which should we drop, delegate, or
absorb from the ecosystem?**

Soleda's recurring failure mode is doing too much. Every additional "big idea" is a
multi-quarter commitment, more surface to maintain, more concepts to teach. We need
exactly three. Not five. Not "three plus one or two more." Three.

Features are different from ideas. A feature is roughly one flow / dialogue act / sub-
agent / skill — those are cheap now, since each new feature follows a template. An
*idea* is a big-picture commitment about how we build agents at all. Ideas are
expensive: they shape architecture, hiring, evals, and roadmap.

---

## Ranking Criteria

Three axes, with an explicit tradeoff between the first two and the third:

1. **Real-world robustness.** Users are lazy, vague, contradictory, and frequently
   change their minds. The agent must keep functioning when reality doesn't match
   the toy-demo conditions of a research paper.
2. **Productivity utility.** Users adopt agents that help them get *real work* done
   over weeks and months, not agents that win one-shot demos. This requires
   resilience to complexity: state, history, constraints, and recovery.
3. **Minimal hand-engineering (the Bitter Lesson axis).** Anything that requires
   expert authoring should have a clear path to learning from data. Hand-tuned
   pipelines lose to scaled compute every time, given enough time.

Criteria 1 and 2 trade off against criterion 3. Hand-crafted scaffolding makes
agents more robust *today* but blocks our long-term scaling story. The "practical"
choice balances both — power enough to ship now, learnable enough to keep up later.

---

## Inventory of Differentiators

Every concept in AF that meaningfully distinguishes us from the L1/L2 SDK pack.
Brief description, then a score against the three criteria.

### 1. Ambiguity Handler (uncertainty as a first-class component)

What it is: a dedicated component that declares, tracks, and resolves uncertainty
at four levels (general, partial, specific, confirmation). The NLU/PEX/RES modules
all surface confidence into a shared object that drives clarification, re-routing,
or escalation. Botpress and Voiceflow have entity-confidence reprompts; nothing
else productized comes close.

- Robustness: 5/5. This is the central robustness story. The whole reason the
  agent doesn't go off the rails on vague utterances.
- Productivity: 4/5. Confidence-aware behavior compounds across long sessions —
  the agent doesn't accumulate small wrong commits.
- ML-friendly: 3/5. Confidence is a learnable signal. EVPI is a structured framing.
  Today the resolution policy is hand-tuned; with logged conversation data we can
  learn calibrated thresholds and which clarification to ask.

### 2. Three-tier Memory with the vetted / unvetted distinction

What it is: Session Scratchpad (L1, in-context) / User Preferences (L2, per-user)
/ Business Context (L3, vector-retrieved). Each tier carries a *trust grade*:
`lookup` and `search` return vetted/curated content, `query` and `retrieve` return
unvetted raw context. This trust gradient is what no other memory framework has —
Letta has tiers but treats every recalled fact as equivalent.

- Robustness: 4/5. The vetted/unvetted split prevents the agent from confidently
  asserting something it merely retrieved from a stale doc.
- Productivity: 5/5. This is the "knows your business" property. Real productivity
  gains come from the agent remembering preferences across sessions and grounding
  in your actual business context.
- ML-friendly: 3/5. Hybrid retrieval is well-studied. The trust-grade marker
  itself is currently hand-curated but is exactly the kind of label that becomes
  trainable once we have enough corrections.

### 3. Synthetic Data Augmentation pipeline

What it is: a pipeline that takes an ontology spec (intents, flows, dax codes,
slots) and generates training data — utterances per flow, exemplars for slot
filling, evaluation scenarios. The pipeline itself is the leverage: it trades
domain expert time for compute.

- Robustness: 4/5. Synthetic data covers rare events (errors, edge cases,
  contradictions) that real logs rarely contain in the early lifecycle of a new
  domain agent.
- Productivity: 2/5. Indirect. Helps the agent get good faster but doesn't
  directly help the user.
- ML-friendly: 5/5. This is *the* anti-Bitter-Lesson move. The whole point is to
  let new domains be brought up by writing a spec, not by hand-labeling 10k
  utterances.

### 4. POMDP framing of dialogue state

What it is: the agent's beliefs are explicitly tracked as a probability-weighted
state, where the user's intent is the hidden variable and the utterance is the
observation. The DialogueState component is the sufficient statistic.

- Robustness: 3/5. The substrate that makes ambiguity measurable. Without it,
  ambiguity becomes vibes.
- Productivity: 2/5. Foundational, not user-facing.
- ML-friendly: 4/5. POMDPs are the canonical formalism for sequential decisions
  under uncertainty. Maps cleanly onto RL-style training when we get there.

Note: this is largely *inseparable from* idea #1. The Ambiguity Handler is the
operational manifestation of the POMDP framing. Treating them as one idea is
honest; treating them as two is double-counting.

### 5. Slot-filling tied to flow lifecycle (predictable termination)

What it is: every flow declares the slots it needs. A flow can't terminate until
its required slots are filled. This is what prevents the SDK failure mode of
"agent decided it was done halfway through."

- Robustness: 5/5. Predictable termination is a hard production property. The
  difference between "the agent might finish" and "the agent will finish."
- Productivity: 3/5. Forces the right info-gathering before action.
- ML-friendly: 2/5. Slots are hand-defined per flow today. Path to learning slot
  schemas from data exists (schema-guided dialogue work) but is not on our
  current roadmap.

### 6. Per-flow PEX policies with verify / recover

What it is: each flow has its own policy in PEX, with explicit `verify` (is the
output valid?) and `recover` (try repair if not) hooks. Two-tier failure
handling: PEX repair loop inside the flow, Agent-level cascade above it.

- Robustness: 4/5. Real safety net for tool errors and bad LLM outputs.
- Productivity: 2/5. Infrastructure, not user-facing.
- ML-friendly: 1/5. Policies are heavily hand-engineered today. The closest peer
  (LangGraph nodes) is similarly hand-engineered. ML path is unclear.

This is also the area where "borrow from L1/L2 SDKs" matters most. LangGraph and
MS Agent Framework give us most of this for free. Building it ourselves is
defensible only if our specific verify/recover patterns turn out to be unique.

### 7. Plan flow with mid-plan replanning

What it is: a Plan flow can stack sub-flows, then between each sub-flow the
Agent reassesses whether the remaining plan still makes sense given what was
discovered. Adaptive replanning, not fixed scripts.

- Robustness: 3/5. Handles partial failures gracefully (skip and continue).
- Productivity: 4/5. Multi-step real-world tasks need this — outline + execute
  + adjust is the natural shape of complex work.
- ML-friendly: 2/5. Replanning logic is currently rule-based.

### 8. Internal flows as a lightweight async swarm

What it is: Internal flows (recap, recall, retrieve, calculate, search, peek)
run alongside the user-facing flow with focused context, minimal tool access,
and a shared scratchpad. Conceptually similar to Claude SDK subagents but
specialized for in-conversation memory and grounding tasks.

- Robustness: 3/5. Recap/recall before action prevents context-loss errors.
- Productivity: 3/5. Latency benefit when parallelized correctly.
- ML-friendly: 2/5. Orchestration is hand-engineered.

### 9. Compositional dax grammar

What it is: every dialogue act has a 2-3 hex code composed of dact primitives
(16 verbs/nouns/adjectives). The code semantically reflects the composition
(`fill = {5BD}` = insert + row + multiple).

- Robustness: 1/5. Semantic discipline at the spec level; doesn't directly
  affect runtime robustness.
- Productivity: 1/5. Developer-side organization, not user-facing.
- ML-friendly: 0/5. Pure hand-engineering. *Actively hurts* criterion 3.

### 10. Universal dialogue-state protocol (research vision)

What it is: from `dialogue_state_research.md` — a standard JSON schema for
inter-agent belief-state transmission, with closed-world over uncertainty types
but open-world over content. Currently a research direction, not productized.

- Robustness: 2/5. Doesn't address current production needs.
- Productivity: 1/5. Multi-agent interop is a future concern.
- ML-friendly: 5/5. The protocol is *designed* to enable cross-agent learning.

---

## Scoring Summary

| Idea | Robust | Prod | ML | Total | Verdict |
|---|---|---|---|---|---|
| 1. Ambiguity Handler | 5 | 4 | 3 | 12 | **Top 3** |
| 2. Three-tier Memory (vetted/unvetted) | 4 | 5 | 3 | 12 | **Top 3** |
| 3. Synthetic Data Augmentation | 4 | 2 | 5 | 11 | **Top 3** |
| 4. POMDP framing | 3 | 2 | 4 | 9 | Absorb into #1 |
| 5. Slot-flow lifecycle | 5 | 3 | 2 | 10 | Keep, but as infrastructure |
| 6. Per-flow PEX verify/recover | 4 | 2 | 1 | 7 | Borrow from LangGraph/MSAF |
| 7. Plan flow with replanning | 3 | 4 | 2 | 9 | Keep as feature, not idea |
| 8. Internal flow swarm | 3 | 3 | 2 | 8 | Borrow Claude SDK subagent pattern |
| 9. Dax grammar | 1 | 1 | 0 | 2 | Drop or radically simplify |
| 10. Dialogue-state protocol | 2 | 1 | 5 | 8 | Park for research, not product |

The numerical totals are noisy — the "Verdict" column is the actual call.

---

## The Recommended Top 3

### 1. Ambiguity Handler — *robustness pillar*

The user already has this locked in. Confirming why it survives the cut:

- **It's the only idea that hits criterion 1 head-on.** Every other framework
  treats ambiguity as either an LLM problem ("the model will ask if it doesn't
  know") or a low-level entity-confidence reprompt. Neither addresses the
  real-world case where the user *thinks* they were clear.
- **Strong ML path.** Confidence is a calibratable signal. Each user correction
  is a labeled training example. The four-level taxonomy is structured enough
  to be learned, unstructured enough to generalize.
- **Compounds with #2 and #3.** Ambiguity-aware retrieval (memory) and
  ambiguity-aware data synthesis are downstream wins.

What it absorbs: the POMDP framing (idea #4) is the formal substrate for this.
Treat them as one idea labeled "Uncertainty as First-Class Content."

### 2. Three-tier Memory with vetted / unvetted distinction — *productivity pillar*

The user's central productivity story is "the agent that knows your preferences
and your business." Three-tier memory is how you get there. The vetted/unvetted
distinction is the part nobody else has.

- **It's what makes long-horizon agents trustworthy.** Without trust grades,
  every retrieved fact is suspect, and the agent is forced into endless
  clarification — defeating the productivity goal.
- **The trust grade is the new label.** Vetted = curated semantic layer.
  Unvetted = raw retrieval. This is the conceptual move that turns memory from
  "search results" into "calibrated knowledge."
- **Compounds with #1.** Uncertain memory items can be flagged via the same
  ambiguity primitives. The Memory Manager and Ambiguity Handler share a
  vocabulary.
- **ML path: hybrid retrieval is well-studied.** The novel part — automated
  vetting — is exactly the kind of label that becomes trainable once corrections
  start logging.

What gets borrowed: Letta's three-tier architecture and self-editing core
memory; Zep's temporal validity (valid-from / valid-until). The *synthesis* —
trust grades on top of tiers — is ours.

### 3. Synthetic Data Augmentation — *Bitter-Lesson pillar*

This is the only idea on the list that directly addresses criterion 3. Without
it, every new domain agent requires expert authoring of slot definitions, flow
exemplars, and eval scenarios, and AF stays in the hand-engineering bucket
forever.

- **It's the bridge from spec to trained system.** A domain expert writes the
  ontology; the pipeline produces training data, eval scenarios, and synthetic
  conversations.
- **Generalizes to new domains.** Today's pipeline is the generic frame; tomorrow's
  is fine-tuned per-domain. The same compute that improves Hugo improves Dana.
- **Necessary for #1 and #2 to scale.** Calibrating ambiguity confidence and
  populating vetted memory both need lots of labeled examples. Synthetic data is
  the cheapest path.
- **Almost no comparable framework has this.** Most expect you to bring your own
  data. The Schema-Guided Dialogue work is the closest research peer; nothing
  productized.

What gets borrowed: prompt-based data generation patterns (well-trodden), eval
scenario templates from `_specs/hidden/confidence_experiment.md`. The unique
asset is the *coupling* of the pipeline to our ontology format — spec changes
auto-regenerate the data.

---

## Why Not the Others

### Things to keep building, but as infrastructure (not "ideas")

- **Slot-flow lifecycle coupling.** Real production property, but it doesn't
  carry a story by itself. It's the plumbing that lets #1 and #2 work. Keep
  building, don't market.
- **Per-flow PEX verify/recover.** Necessary, but LangGraph and MS Agent
  Framework have similar primitives. Borrow what we can, custom-build only the
  flow types where verify/recover is genuinely AF-specific (e.g., ambiguity
  recovery).
- **Plan flow.** A feature, not an idea. The Plan intent is a flow like any
  other; it inherits replanning behavior from the agent loop. Don't elevate.
- **Internal flow swarm.** Borrow the Claude Agent SDK subagent dispatch
  pattern. The unique parts (recap / recall / retrieve / search / lookup) are
  *flows*, not orchestration architecture.

### Things to drop or radically simplify

- **Compositional dax grammar.** Hand-engineering taken to its logical extreme.
  The semantic discipline it forces is real but the cost is teaching every
  contributor a 16-primitive symbolic system. Either simplify to a flat enum
  with human-readable names, or accept that dax codes are an *internal*
  identifier and stop trying to make them semantically meaningful. Rolling them
  into a flow's metadata as a stable ID would lose nothing.
- **Universal dialogue-state protocol.** Research vision, not product. Park in
  the interview-prep / research notes. Revisit if cross-agent interop becomes a
  business requirement (it isn't today).

### Things to outsource (buy / borrow from L1/L2 SDKs)

These are listed in `agent_landscape.md` but worth restating: tool-calling JSON
parsing, MCP servers, native streaming, sessions, durable execution, workflow
primitives (Sequential / Parallel / Loop), observability/tracing, voice
infrastructure, OAuth / credential storage. Every hour spent rebuilding any of
these is a wasted hour against the top-3 ideas above.

---

## How These 3 Compound

The pillars aren't independent — they reinforce each other.

```
   [Ambiguity Handler]
         |
         | confidence flags on retrieved memories
         v
   [Three-tier Memory]
         |
         | structured corrections become labels
         v
   [Synthetic Data]
         |
         | populates calibration sets and eval scenarios
         v
   [back to Ambiguity Handler] — confidence model gets better
```

This is the loop that makes AF improve over time without expert authoring on
every iteration. Idea #1 declares uncertainty, idea #2 surfaces what to be
uncertain about, idea #3 produces the data to calibrate idea #1. Each loop
through this cycle reduces the hand-engineering tax on new domains.

If we cut any one of the three, the loop breaks:
- Without #1, we have no signal worth labeling.
- Without #2, we have nothing to calibrate against.
- Without #3, we can't iterate without expert-authored data.

---

## What Goes Into the Marketing / Pitch

When someone asks "why Assistant Factory and not [Strands / Letta / OpenAI Agents
SDK]?":

> Three reasons. First, we treat uncertainty as content, not a failure mode —
> the agent knows when it's confused and clarifies before acting. Second, our
> memory has a trust gradient: vetted business knowledge is separated from raw
> retrieval, so the agent doesn't confidently assert what it merely searched
> for. Third, new domains are bootstrapped from a spec, not from hand-labeled
> data — the pipeline does the labeling.

That's the story. Three sentences. Everything else is implementation.

---

## Decision Checkpoint

Before adopting this, the open question is whether the user agrees that:

1. POMDP framing should be absorbed into Ambiguity Handler (one idea, not two).
2. The dax grammar is over-engineered and a candidate to simplify or drop.
3. Plan flow, slot-flow lifecycle, and per-flow PEX are infrastructure, not
   ideas — important to keep building, but not part of the headline pitch.

If those three calls hold, the top 3 above are the recommended commitments and
everything else moves to "future work" or "borrow from the ecosystem."
