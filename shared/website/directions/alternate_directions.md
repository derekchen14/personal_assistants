# Alternate Directions — The Three Things That Matter

Assistant Factory has been trying to ship too many ideas. This doc commits to **three** customer-visible
differentiators and explicitly defers everything else. Power comes from depth on a narrow set of bets,
not breadth across many.

## The problems we exist to solve

Three failure modes in today's agents, ranked by how much they hurt real users:

1. **Overconfidence under uncertainty.** The agent guesses, then doubles down. Users notice the
   *second* wrong answer more than the first.
2. **Sycophancy / no worldview.** The agent has no model of what *the task* is — only what the user
   just said. So it agrees with whatever framing comes in, even when the framing is wrong.
3. **Brittleness in real workflows.** Real users are lazy, contradict themselves, paste in messy
   context. Demoware breaks; products survive.

These are three faces of the same underlying gap: **the agent has no internal beliefs that persist
across turns.** Everything we build should reinforce that the agent has its own grounded view of
what's going on.

A fourth concern — the Bitter Lesson — is a *constraint* on how we build, not a customer-visible
differentiator. Any time we hand-engineer something, we owe a story for how it gets learned later.

## Build — the three differentiators

### 1. Ambiguity Handler (locked)

**What it is.** Confidence is measured, not assumed. Uncertainty is declared at four levels
(general, partial, specific, confirmation) and the agent has explicit branches for each: ask,
narrow, confirm, or proceed.

**Why it's a moat.** No L1 SDK has this. Voiceflow and Botpress have entity-confidence reprompts;
AF goes layered. Academic work treats uncertainty as content — closed-world over uncertainty *types*,
not over values (see `interview_prep/dialogue_state_research.md`). We're the only product shipping
that thesis.

**Customer value.** The agent stops sounding confidently wrong. Users notice within the first session.

### 2. POMDP-Grounded Worldview — Dialogue State + Flow Stack

**What it is.** Every turn updates an explicit `DialogueState`: predicted intent, predicted flow,
slot beliefs, a stack of flows in flight, and a small set of control flags. The flow stack has a
real lifecycle (Pending → Active → Completed) and supports stacking, popping, mid-plan replanning.
Slots have validation tied to the flow that owns them.

**Why it's a moat.** Strands bets the LLM is smart enough to keep track. Claude Agent SDK and
OpenAI Agents SDK ship sessions but no structured belief state. LangGraph gives you the graph but
you draw it yourself. AF ships an *opinionated* state shape that:

- Makes evals reproducible — you can diff belief state across runs.
- Anchors the agent against sycophancy — it has predictions to defend or revise, not just a chat
  to please.
- Provides the natural attach point for the Ambiguity Handler — confidence is a property of beliefs,
  and beliefs only exist if you have a belief schema.

**Customer value.** The agent doesn't drift. Multi-step tasks complete. When the user contradicts
themselves on turn 5, the agent notices because the state model says it should.

**Bitter Lesson hedge.** The schema is structured but slot values are LLM-filled and many are open
text — the same hybrid approach as the dialogue-state research doc (typed primitives where structure
is enough, NL+embedding where it isn't). The shape is the discipline; the content is learned.

### 3. Trust-Graded Memory — Vetted vs Unvetted

**What it is.** Three-tier memory (session scratchpad → user preferences → business context) with
one twist nobody else has: every fact carries a trust grade. **Vetted** facts (confirmed by the
user, derived from an authoritative source) override **unvetted** facts (inferred, scraped, mid-
conversation guesses). Retrieval surfaces the grade alongside the fact so policies can choose to
confirm or proceed.

**Why it's a moat.** Letta has tiers but no trust gradient. Zep has temporal validity (valid-from /
valid-until) but doesn't separate vetted from unvetted — temporal validity says *when* a fact was
true, trust grading says *whether to bet on it*. They're complementary; adopt Zep's temporal axis
underneath our trust axis.

**Customer value.** The agent remembers what users actually told it without blurring it into what
it guessed. This is the central failure mode in productivity domains (Recruiter, Scheduler), where
"the agent thinks it knows but it's wrong" is worse than "the agent doesn't know."

## Buy — outsource cleanly

| Capability | Source | Why |
|---|---|---|
| Tool-calling JSON + provider abstraction | Claude Agent SDK or OpenAI Agents SDK | One quirk per provider × every API change is a maintenance sink |
| Tool registration & ecosystem | MCP | Protocol value > hand-rolling schemas |
| Voice transcription / TTS | Vapi (if voice ships) | Not our specialty |
| Observability & traces | Langfuse | Self-hosted, MIT, safe default |
| Vector retrieval for business tier | Standard vector DB | No reason to invent |

## Borrow — adopt patterns, not whole frameworks

- **Skills pattern (Claude SDK)** — replace hand-curated `prompts/` files with metadata-first
  lazy-loaded skill bundles.
- **Hooks at lifecycle boundaries (Claude SDK)** — widen our NLU/PEX/RES pre/post hooks to
  pre-tool / post-tool / on-flow-push / on-flow-pop. Cheap, big payoff.
- **Workflow primitives Sequential/Parallel/Loop (Google ADK)** — the natural shape for Plan flows.
- **Durable execution / checkpointing (LangGraph or MS Agent Framework)** — closes the
  snapshot/rollback gap in Future Work.
- **Self-editing core memory (Letta)** — agent has tools to edit its own L1 scratchpad; maps onto
  `recap` / `recall`.
- **Temporal validity on facts (Zep)** — valid-from / valid-until layered under our vetted/unvetted
  axis.

## Defer — promising but not in the top three

These stay in the roadmap; they do not get sold as differentiators today.

- **Synthetic data augmentation pipeline.** Still the right answer to the Bitter Lesson, but the
  customer doesn't see "synthetic data" — they see "the agent works in my domain." Treat as an
  *internal capability* that powers fast domain spin-up, not a marketing pillar. Re-evaluate after
  the first three domains ship.
- **Compositional dax grammar.** Real semantic discipline for flow definition. Keep using it
  internally; don't sell it externally — nobody outside the team cares about a flow naming
  convention.
- **Per-flow PEX policies with verify/recover.** Useful structure, but Voiceflow and Botpress have
  neighbors. Build it, treat it as table stakes, not moat.
- **Visual editor for the flow stack.** Don't build until two of the three queued domains are
  live. If we ever do, copy Voiceflow's vocabulary, not LangGraph's graph metaphor.

## Drop — stop investing

- **Custom provider abstraction layer.** Use the L1 SDK; stop maintaining our own.
- **Hand-rolled tool schemas in `schemas/`.** Move to MCP.
- **Bespoke observability dashboards.** Langfuse handles it; don't build in-app.
- **Per-domain shared base classes.** Already gone per the README; keep it that way.

## Roadmap

The arc, written in terms of when each differentiator stops being aspirational.

**Now → next 4 weeks (Phase 4–6 of the build checklist).**
Ship the three differentiators end-to-end on one domain — Scheduler, because it has the narrowest
surface and cleanest slot definitions.
- Ambiguity Handler at four levels with measurable confidence.
- Dialogue State + Flow Stack with the lifecycle states actually exercised in evals.
- Memory tiers wired up; trust grading present even if simple (boolean vetted/unvetted, no learned
  grading yet).

**Weeks 4–10 (Phase 7–8).**
Add Recruiter as a second domain. The point is to prove the architecture transfers, not to add
features. Anything that needed hand-tweaking only for Scheduler is a bug.
- Adopt Skills, Hooks, MCP. Drop the custom prompt loader and tool schema files.
- Evaluation harness measures ambiguity-handler accuracy and flow-completion rate per domain.

**Weeks 10–16 (Phase 9–10).**
- Blogger as the third domain — long-form generative, the hardest fit for slot-flow framing. This
  is the architecture's stress test.
- Durable execution / checkpointing imported from LangGraph or MS Agent Framework.
- Begin synthetic data work *only if* eval signals from the first three domains show concrete
  failure modes that data could fix.

**The kill criterion.** If by the third domain we still need significant hand-engineered prompts or
per-domain glue, the Bitter Lesson is winning. At that point we either narrow scope further or
pivot toward more learned components — not invest more in scaffolding.

## Sanity checks

- **Strands experiment.** Run a ~100-line Strands agent on Scheduler. If it matches AF on multi-turn
  ambiguous dialogue, the moat is in the wrong place. If it doesn't (likely), the scaffolding has
  evidence.
- **No-fourth-pillar rule.** If a feature isn't one of the three differentiators, it doesn't get a
  top-level component or its own README section. It lives inside the existing structure or it
  waits.
- **Practical-over-novel test.** Before adding any concept, ask: "Does this make Scheduler ship
  faster or work better for a real user this week?" If no, defer.

---

# Addendum — State as Sufficient Statistic (2026-05-09)

Architectural review prompted by three questions: shape and role of Dialogue State, whether the
NLU/PEX/RES pipeline earns its keep, and where state should live. Two of my earlier suggestions were
wrong on inspection; I'm recording the corrections alongside the revised position so the *reasoning*
is visible, not just the conclusions.

## Self-corrections

**Wrong: "Pull AmbiguityHandler state INTO dialogue state."**
That move would relegate ambiguity from a first-class component to a struct attribute, hiding the
agency that makes Pillar #1 a moat. The Handler has to *do things* (declare, ask, resolve, present);
those behaviors are visible, evaluable, and inspectable precisely because they live in their own
component. State can hold a *projection* of what's currently declared (`level`, `metadata`,
`declared_at_turn`) so any reader can see the uncertainty without depending on the Handler — but the
Handler itself stays put. Pillar #1 and Pillar #2 reinforce each other; they don't merge.

**Wrong: "Add hooks to PEX."**
PEX already has them — `_security_check` (pre-hook, `pex.py:171`), `_validate_frame` (post-hook,
`pex.py:212`), `_verify` (post-post-hook, `pex.py:632`). They do real work today (lethal-trifecta
guard, frame validation, active-post check). The right framing isn't "add hooks" — it's "the surface
is already there; the open question is whether to widen what gets run at each hook (e.g., pre-tool,
on-flow-push) as extension points." That's a refinement, not a missing primitive. The Borrow item in
the main doc should be read as "open the hook surface to extension," not "introduce hooks."

## The forest before the trees: what is state for?

The MDP slice of POMDP says state must be a **sufficient statistic** — given state alone, any policy
can act correctly without replaying history. That's the load-bearing property, and it's the property
today's `DialogueState` does not yet hold.

When state is sufficient, every policy is *stateless*: read state, decide, write back. Policies do
not talk to each other through side channels (flow attributes, scratchpad keys, content-service
files); they talk through state. That is what makes new policies cheap to add and existing policies
safe to recompose. It is also what makes the agent inspectable — a single object answers "what does
the agent believe right now?"

When state is *not* sufficient, you see exactly the symptoms Hugo has today:

- Lifecycle stage lives on `flow.stage` (audit's `discovery → delegation`, planned chat's
  `pre_dispatch → post_dispatch`) — opaque to evals, opaque to other policies.
- Routing decisions live in `memory.scratchpad['audit']` — readable only by something that knows to
  look there.
- Snapshots for Undo live in `content_service._snap_root` — readable as content backup, not as
  belief replay.
- Slot values live on `flow.slots[...]` — fine for the active flow, but a sibling policy can't see
  another flow's slots without walking the stack.

Each individual leak is defensible in isolation. The aggregate is that Pillar #2 fails to deliver:
there is no single object you can read to answer the worldview question.

So the right question is not "what new field should state have?" It is: **what is the minimum a
stateless policy needs to act correctly?** Working that backward gives the contract:

| Belief category | Concrete content |
|---|---|
| Who is being addressed | session_id, user_id, persona |
| What the user wants | predicted intent + flow with top-N confidence |
| What is known about the request | slot values per flow on the stack, filled / missing / invalidated |
| What is in flight | flow stack with lifecycle stage per entry |
| What is uncertain | projection of current ambiguity (level + metadata + declared_at_turn) |
| What just happened | last frame origin + violation, last tool calls (compact), last user text |
| Agent disposition | flags (keep_going, has_plan, has_issues, natural_birth) |
| What can be reversed | diff against prior turn + snapshot pointer when the stack closes |

This is not a wishlist; it is the contract that lets policies stay stateless. If a policy reads only
`state` and can act, the contract holds. If a policy reaches into `flow.stage`, `memory.scratchpad`,
or `content_service` to know what to do, the contract is broken and we're paying a moat tax for
nothing.

Corollary: **scratchpad is for working notes, not beliefs.** A policy's intermediate considerations
("I evaluated three options before picking this one") belong in scratchpad. The chosen option, if a
downstream policy depends on it, belongs in state. This is the test that decides every borderline
case.

## Revised positions on the three questions

### Q1 — What state should hold

Promote state to the sufficient statistic above. Two specific moves are load-bearing for Pillar #2:

1. **Lifecycle stage moves into state.** `state.flow_stack[i].stage` becomes the canonical reading;
   the flow class can still expose helpers. This is what makes the planned `chat_policy`
   `pre_dispatch → post_dispatch` transition and `audit_policy`'s `discovery → delegation` visible
   to evals and observability — without it, those transitions are invisible to anything outside the
   policy that wrote them.
2. **Diffs are implemented in state.** Belief diffs (slot changes, stage changes, ambiguity
   declarations) are state-level and feed Undo (`{08F}`). Content snapshots in `content_service`
   stay where they are — they're a different concern (content rollback, not belief replay).
   Conflating the two was what made state look thin.

What does *not* change:

- Scratchpad stays in `MemoryManager` — it's working notes, not beliefs.
- Slots stay on flows; state surfaces a read-only projection (`state.active_slots`) so policies
  don't have to walk the stack to read the active flow's slots.
- The AmbiguityHandler stays a first-class component. State holds a projection of *what's
  currently declared*, not the handler itself.

### Q2 — Modules: keep the contract, drop the ceremony

The spec had heavy NLU/PEX/RES classes with their own internal taxonomies (`understand`/`react`/
`contemplate`; `execute`/`recover`; `generate`/`clarify`/`display`). Most of that ceremony hasn't
earned its keep — Hugo's PEX is a dispatcher with a small repair loop, RES is a thin pass-through,
and NLU's sub-methods overlap in practice.

But the *contract* — three lifecycle phases with stable boundaries — is exactly what Pillar #2
needs. Without phase boundaries, eval can't ask "what did NLU predict?" because NLU isn't a thing.
That's the path to becoming Strands.

So: keep the boundaries, slim the implementations. PEX already shows the pattern (pre-hook, dispatch,
post-hook); apply the same shape to NLU and RES. Phases are contracts, not class hierarchies.

The right test for whether a boundary is real: if a method can be moved between modules without
breaking anything, the boundary is bookkeeping, not a contract. Slot recovery happens inside
policies today — that's correct, because slot recovery is a policy responsibility (the policy knows
what it still needs). NLU's job is "what does the user want?"; the policy's job is "given that, what
do I still need to act?" Both are legitimate; the line is just blurry on paper, sharp in practice.

### Q3 — Where state lives

Per-session scope, in-process for the hot loop, JSONL on disk for everything else.

Per-session is right because state is the sufficient statistic across flows (multi-flow plans) and
across turns (`keep_going`, mid-plan replanning). Per-turn was sized for a problem we no longer
have. Signs we've gone too far: serialized state >>10KB per typical session, diff replay >50ms,
fields preserved "just in case." Kill those — state holds *current beliefs*, not history.

The JSONL question — what to store — falls out of the sufficient-statistic framing. One line per
turn:

```
{
  "session_id": "...", "turn_id": 12, "timestamp": "...",
  "user_text": "...", "agent_text": "...",
  "intent_pred": [{"intent": "Revise", "conf": 0.82}, ...],
  "flow_pred":   [{"flow":   "polish", "conf": 0.71}, ...],
  "flow_stack":  [{"name": "audit", "stage": "delegation", "slots_filled": [...]}, ...],
  "active_flow": "polish",
  "ambiguity":   {"level": "specific", "metadata": {...}} | null,
  "flags":       {"keep_going": true, "has_plan": true, "has_issues": false},
  "frame":       {"origin": "polish", "block_types": ["card"], "violation": null},
  "tool_calls":  [{"tool": "revise_content", "ok": true}, ...],
  "diff":        {"slots_changed": [...], "stage_changed": [...], "ambiguity_changed": ...}
}
```

`grep "specific"` shows every specific-level ambiguity ever declared. `grep "violation"` shows every
error frame. `jq 'select(.flow_stack[].stage == "delegation")'` returns every audit dispatch. This
is the observability story for Pillar #2 — not a separate dashboard, just the state log. It also
reframes the earlier observability/eval discussion: we don't need a fourth pillar because Pillar #2
done correctly *is* the observability surface.

The "grep across policies within PEX" use case the question raised is actually two cases that look
similar: (a) within a single turn, all policies see the same in-process `state` object — no disk
needed; (b) across sessions or for debugging, the JSONL log is the substrate. In-process for the
hot loop, SQLite `jsonb` for resume-session, JSONL for archive/replay/eval. Redis only once we have
multi-worker contention, which we don't.

## Implications for Pillar #2

Pillar #2 ("POMDP-Grounded Worldview") is currently aspirational. The fix is mechanical, not
conceptual: make state the sufficient statistic the spec already calls for, then prove it by ripping
out side channels one at a time. The pillar holds if and only if a new policy can be added that
reads only state and acts correctly.

The kill criterion is sharper than I originally had it: **if we ever need to introduce a new "where
does this information live" axis (a third home for slot data, a second home for ambiguity), the
pillar has failed and we should drop it.** Pillar #2 lives in a single object or it doesn't exist.

Pillar #1 (Ambiguity Handler as its own component) and Pillar #3 (Trust-Graded Memory) are unchanged
by this review. Their separateness from state is in fact load-bearing: Pillar #1 because uncertainty
needs agency, not just a flag; Pillar #3 because memory has its own retrieval and trust semantics
that don't belong in per-turn beliefs.

## What this means for the roadmap

The Scheduler-first plan in the main doc still stands, but with one explicit gate before any new
domain work: **state must be the sufficient statistic before Recruiter starts.** Otherwise we'll
ship the leak, not the contract, twice. Concretely, the gate is:

- `flow.stage` reads route through state.
- Belief diffs land in state every turn and feed Undo.
- JSONL turn log writes one line per turn with the schema above.
- A new policy can be added that only takes `state, context, tools` and acts correctly without
  touching `memory.scratchpad` for inputs. (Outputs to scratchpad remain fine — scratchpad is the
  working-notes channel.)

If that gate slips, Recruiter slips with it. The pillar is worth more than a one-week delay.
