# NLU — Natural Language Understanding (the Heart)

NLU holds the agent's **ephemeral** beliefs — the information the agent *generates or predicts*, as opposed to
what the user provides. Its goal is to form a **Theory of Mind** about the user from their **words**
(utterances) and their **actions** (interaction with the UI). Because beliefs are updated constantly, NLU does
**more writes than reads**: every turn revises what the agent thinks the user wants.

NLU is a **separate Agent** — one of three continuous LLM-loops, running underneath the deterministic
**Assistant** (L0) alongside [PEX](pex.md) (acting) and [MEM](mem.md) (remembering). The Assistant reaches
NLU at exactly one entry point: **`understand(op=…)`** with `op ∈ {react, think, contemplate}`. `understand`
dispatches to that mode internally — `classify_intent`, `detect_flow`, and `fill_slots` are **NLU-internal**
(not tools, never exposed to PEX or the Assistant).

NLU detects **and** commits in one action: it **writes its prediction — intent, ranked flows, confidence,
and slots (including the entity slot) — into the Dialogue State belief**. The Dialogue State is the
**single source of truth** for those predictions; they are **never duplicated into the scratchpad**. PEX
reads the belief through `read_state`; NLU itself **never touches the flow stack**.

**When the Assistant gates NLU.** The Assistant picks `op` at turn entry: a **click** →
`await understand(op=react)` (the dax is known; react fills required slots from the payload with no LLM
call); an **utterance with no active entity** → `await understand(op=think)` (PEX has no grounding to act
on, so it blocks); an **utterance with an active entity** → `understand(op=think)` started **on a thread,
in parallel with `PEX.execute()`** (PEX proceeds on the standing belief while NLU refines). A **Clarify**
signal from PEX re-runs `understand(op=think)`; `op=contemplate` is the separate failed-flow re-route.

**Commit, or declare ambiguity.** Detection runs against the active flow (a continuing turn) or a fresh
instance. When intent, flow, and grounding are confident, NLU commits the prediction into the Dialogue State
belief; when any is uncertain, it declares ambiguity (below) **instead of** committing a guess. Flow
*stacking* is not NLU's — NLU records the prediction in belief; PEX's
[Workflow Planner](../components/workflow_planner.md) Skill (not NLU, not the Assistant) decides whether to
`stackon` and activate.

NLU works in three modes, all spanning these tools:

- **react** — fast path for action turns (a click) where the dax is already known. A thin **`interaction()`**
  function preprocesses the raw UI payload first — shaping it into the slot contract (e.g. unpacking an
  `outline` proposals array into section slots). This is **semantic normalization, not defensive validation**:
  the frontend payload is a trusted internal contract, so `interaction()` reshapes, it doesn't guard. `react()`
  then fills every **required** slot from the shaped payload **without an LLM call** and returns immediately to
  the main Agent to kick off PEX. Optional slots and housekeeping are handled afterward by the triggered loop
  (below). `interaction()` is just a function in the turn-entry path, not a component or a file.
- **think** — the standard detection path that can surface ambiguity.
- **contemplate** — a slower re-routing pass that takes the **failed source flow** as a parameter and
  re-detects within a narrowed search space (excluding that flow). Triggered only by a **stuck sub-agent**
  via the Workflow Planner (not the Clarify path) — see [Contemplate](#contemplate--re-routing).

### A continuous, event-triggered loop
NLU is an always-running **async loop** (an asyncio task), not a one-shot call. The split that keeps it both
proactive and testable:

- **Awaited or parallel — the Assistant decides at turn entry.** Whether PEX blocks on NLU depends on
  the entry path and whether belief is already grounded:
  - **Click** → `await understand(op=react)` — required slots arrive in the `payload`, so react fills them
    in code (no LLM call) and returns immediately.
  - **Utterance with no active entity** → `await understand(op=think)` — there is no grounded prior to act
    on, so the Assistant blocks until NLU establishes intent, flow, and grounding (committing, or declaring
    ambiguity).
  - **Utterance with an active entity** → `understand(op=think)` **on a parallel thread** — PEX proceeds on
    the standing belief while NLU refines it; the Assistant joins the thread at the turn boundary.

  ```python
  def take_turn(world, turn):
      thread = None
      if turn.is_click:                          # react: required slots are in the payload
          nlu.understand(op='react', …)          # awaited; writes belief
      elif not world.state.grounding['post']:    # no grounded prior — must wait for NLU
          nlu.understand(op='think', …)          # awaited; writes belief
      else:                                      # have a prior — refine in parallel
          thread = Thread(nlu.understand, op='think', …); thread.start()
      artifact = pex.execute()                   # reads belief, decides by intent
      if thread: thread.join()                   # settle at the turn boundary
      return artifact
  ```
- **Three correctness gates** describe *where* understanding can fail: (1) **intent + flow**, (2) **grounding
  entity**, (3) **slot-filling** — an exact mapping to `general` / `partial` / `specific` ambiguity
  (`confirmation` is the 4th, fork case). On an awaited path `think()` returns having either committed all
  three or declared the ambiguity, so PEX never reads a half-formed belief.
- **Eventual consistency (async) for everything else.** NLU is *triggered* by changes to its three
  sub-components — a new [scratchpad](../components/session_scratchpad.md) entry, an
  [ambiguity](../components/ambiguity_handler.md) declaration, or a Dialogue State change — and reacts in the
  background to fill **optional** slots, review the scratchpad, and do housekeeping.

The Assistant **joins** any parallel-thread NLU work at the turn boundary (before persistence), so traces
stay deterministic for the eval harness.

NLU owns three sub-components: the **[Dialogue State](../components/dialogue_state.md)** (structured belief),
the **[Ambiguity Handler](../components/ambiguity_handler.md)** (uncertainty), and the
**[Session Scratchpad](../components/session_scratchpad.md)** (the swarm's working ledger).

---

## 1 — Dialogue State (structured belief)

The [Dialogue State](../components/dialogue_state.md) is NLU's **structured** belief, filled with values from
a pre-defined **ontology**. Because the shape is fixed, it supports direct lookups — find slot-values by
slot-name, read a flag's boolean by name. Each turn NLU:

- **classifies** one of 7 intents (3 universal — Plan, Converse, Clarify — plus 4 domain-specific),
- **detects** one of 32 flows (sub-agents),
- **fills** 16 slot types,
- tracks each flow in one of **4 statuses** — `pending`, `active`, `completed`, `invalid`.

NLU builds understanding up the linguistic stack — **syntax → semantics → pragmatics**. Where the domain
exposes a **semantic layer** (common in data analysis), NLU interacts with it directly; where none exists, NLU
develops one. An insight worth keeping past the session is handed to [MEM](mem.md) for promotion into User
Preferences.

### Coarse intent vs. fine detection
The coarse intent is **PEX's fast first guess, not the decision.** The 7-intent taxonomy sits in PEX's
system prompt, and PEX forms a coarse intent inside its own reasoning — committing it to no belief — only
where the intent maps **1-to-1** onto a flow; under **any** uncertainty it is biased to pick **Plan** or
**Clarify**, which gates execution to wait for NLU. PEX passes that as its **reasoning, a hint — never a
final intent prediction**: PEX's selection set differs from the candidates shown to NLU, so comparing the
two directly would only confuse. The hint narrows `detect_flow`'s candidate set; with no hint, detection
defaults to the active flow's intent, else `Converse`.

**NLU is authoritative.** Its tiered `detect_flow` makes the fine-grained call, and **detecting a flow
implicitly classifies the intent** (every flow belongs to exactly one). **Only NLU commits belief** —
`classify_intent` / `detect_flow` / `fill_slots`; PEX's hint never writes. That is how the `classify_intent`
write tool reconciles with the in-PEX taxonomy: PEX may *propose* the coarse intent, but NLU *records* it.

There is no `Internal` intent — memory work is reached through MEM's `recap` / `recall` / `retrieve`
skills, not detected here. `Clarify` is an **NLU-only classification label**, not a flow-owning intent: it
routes to the [Ambiguity Handler](../components/ambiguity_handler.md) (the gate-1 / no-flow case) — there
are no Clarify policies or flows.

**System 1 vs. System 2.** Read this split as two cognitive speeds playing off each other. PEX's coarse
intent-sense is the **fast, System-1 pass** — it runs inside the orchestrator's own reasoning, needs no separate
model call, and is enough to act on a click or an obvious continuation. NLU's `detect_flow` + slot-fill is the
**deliberate, System-2 pass** — the careful, tiered, ambiguity-aware read of *which* flow and *what* grounding.
The two couple through the active-entity rule: with **no active entity** yet, PEX **awaits** System 2 before
acting (it needs grounding it doesn't yet have); with an entity **already grounded**, System 2 runs
**fire-and-forget** and PEX proceeds on the standing belief while NLU refines it. Two refinements close the
loop: PEX's System-1 sense, when uncertain, leans **Plan/Clarify** — which forces the await path so System
2 decides; and a fire-and-forget pass can be **upgraded to a halt** — if NLU's first ensemble round splits
**across intents** (its voters' flows span different intents), NLU escalates and signals PEX to wait until
it commits, so PEX never closes a turn on an intent NLU is still contesting. An action turn is the
degenerate System-1-only case — the `react` fast path fills the known slots from the payload with no LLM call.

### Input guards
Cheap heuristic checks run before any token is spent — empty input, min length (2 chars), max length,
exact-repeat, reserved-keyword / injection rejection, unsupported language, and Tier-0 command shortcuts
(regex rules mapping straight to a flow at score 1.0). A rejection short-circuits to a direct reply.

### Flow detection — tiered ensemble
Every intent (including Converse and Plan) owns flows. Each flow has a standardized **dact** name and a
3-digit hex **dax** id (defined in domain config — see [Configuration](../utilities/configuration.md)).

**Candidate set:** all flows from the hinted intent, plus configurable **edge flows** from adjacent intents
(per-intent confusion lists in config). **Prompt context:** recent history from the
[Context Coordinator](../components/context_coordinator.md), candidate dacts with descriptions, the
active-flow signal (a strong prior to continue), and domain context.

**Provider-agnostic tiered ensemble** (escalating rounds). Voters are addressed by abstract tier
(`low`/`med`/`high`); the [Prompt Engineer](../components/prompt_engineer.md) resolves them to concrete model
ids via `ACTIVE_FAMILY`. Voters in a round run in parallel; a failed/timed-out voter is skipped and majority
is taken among the rest.

| Round | Voters | Agreement |
|---|---|---|
| 1 | 2 × `med` | 2/2 on top-1 |
| 2 | + 1 × `high`, + 1 alternate `med` | 3/4 on top-1 |
| 3 | + 1 × `high` with extended thinking | 3/5 on top-1 |

No majority after round 3 → the result carries low confidence and close candidates; NLU declares `general`
ambiguity rather than letting PEX activate. Detection always includes at least one `high`-tier voter.

**Fusion — how votes combine.** Agreement is on the **post-weight top-1 share**, not a raw head-count. Each
voter carries its tier weight, and a voter's **alignment** — how reliable that model has been on *this* domain's
flow taxonomy — scales that weight as a multiplier, so a well-aligned cheap voter can outweigh a poorly-aligned
expensive one. Alignment factors are **config, not hardcoded constants** (the principle is "trust a voter in
proportion to its demonstrated alignment"; the numbers are tuned per domain). A voter may also **abstain**
(`none` / `unsure`): an abstention is **not** a vote for any flow and does **not** enter the agreement
denominator — it is a distinct "I don't know" signal that pushes toward the next round rather than counting as a
wrong answer. This keeps a single confident voter from being diluted by peers who simply had no opinion.

> **TODO (future) — full escalation & alignment fusion.** The operational implementation runs a **single round**
> of fixed-weight voters (one `low`/`med`/`high` ensemble, simple weighted majority on top-1) — sufficient for
> now. The escalating rounds in the table above, the alignment-as-multiplier weighting, and the abstention
> denominator are the **target** design, not yet built. Keep the simple ensemble until detection accuracy
> demands the extra rounds; treat the elaboration as the upgrade path, not a present requirement.

**Carryover (detached).** After detection, `detect_flow` reports whether the flow already matches the stacked
one. It does **not** dedupe the live stack — it returns the data and lets PEX decide to continue the existing
flow (carryover) or `stackon` a new one.

### Slot-filling
Runs for domain-specific intents (Converse/Plan typically skip). Two phases:

1. **Payload phase** — grounding context from the turn's `payload` is mapped directly into slots before any
   LLM call. Entity fields (`post`, `sec`, `snip`, `chl`) merge into a single SourceSlot entity. The payload
   is consumed here, never stored.
2. **LLM phase** — if required/elective slots remain unfilled, a single `med`-tier call extracts the rest
   from history. Skipped entirely when the payload already satisfied the required slots.

Filled slots are committed in their exact typed shapes by `fill_slots`: strings for single-value slots, lists
for multi-value ones. They are already validated.

**Entity extraction & repair (the repair ladder).** Entity extraction is a sub-task of slot-filling. A
post-detection repair pass snaps a malformed reference onto a real entity by climbing a **cheap→expensive
ladder**, stopping at the first rung that resolves it:

1. **Exact / case / punctuation** — exact match, then case-insensitive, then alphanumeric-only (ignoring spaces
   and punctuation).
2. **Lexical** — nearest match by edit distance (Levenshtein) above a cutoff, for misspellings.
3. **LLM-assisted** — up to 3 targeted attempts asking the model to pick a valid option or return `none`.

> **TODO (future) — semantic rung.** A nearest-match-by-**embedding** step would slot between *Lexical* and
> *LLM-assisted* to catch paraphrases the lexical rung misses. It is **not** part of the operational ladder and
> is **not** built into Charlie: it adds an embedding dependency we are deliberately deferring to keep the
> agent running on the specs without extra moving parts. Note it, don't build it.

A rung that resolves but with residual doubt declares `confirmation` rather than committing silently. Repair
operates on the detached flow; `fill_slots` writes the grounding as a **prediction** (`ver=False`), and it is
**verified** (`ver=True`) only when PEX confirms it (user-approved or PEX-written).

---

## 2 — Ambiguity Handler (recognize and resolve uncertainty)

The [Ambiguity Handler](../components/ambiguity_handler.md) makes uncertainty a first-class belief. NLU tracks
**four levels** of decreasing uncertainty, and **attempts to resolve internally before asking the user**:

| Level | Gate | What's unclear | Resolve internally by… |
|---|---|---|---|
| **general** | gate 1 (intent/flow) | unclear intent, flows, or scope | forming hypotheses to share, formulating a plan, thinking longer to settle the flow |
| **partial** | gate 2 (grounding) | failing to ground to an entity (which table, which column) | studying the top candidate entities (e.g. peek at the first 100 rows), reading past actions |
| **specific** | gate 3 (slot) | missing information; under-specified request; usually a missing slot-value | considering a reasonable default, reading previous turns, re-routing to a fallback flow |
| **confirmation** | — (fork) | a fork in execution — a hunch worth checking | writing a clear question that thoughtfully presents the distinct options |

Only after internal resolution fails does NLU author a clarification observation; **PEX composes** the
user-facing question from it directly (there is no naturalize tool). Because NLU holds the broadest view of the
user's true intent, it has the best chance at writing the most well-informed observation. A recognized
uncertainty can also flag the **scratchpad line items** it affects, so PEX's sub-agents know which findings are
provisional.

**Cross-turn binding.** When an ambiguity is already open (`present()` is true at turn entry), NLU first
attempts to **`resolve`** it by binding the new input to the pending question — the reply is treated as the
*answer*, not a fresh request. Only when the reply clearly abandons the question does NLU fall back to fresh
detection.

### Contemplate — re-routing
`contemplate(source_flow)` takes the **failed flow** as a required input and re-detects within a narrowed
search space that **excludes** that flow and **restricts** to related flows. A single `high`-tier call; the
first detection acts as a prior, so the re-detected flow rarely deviates far (a trust-region effect).

It is **not** the Clarify path — a Clarify signal has no flow yet to exclude, so Clarify re-runs `op=think`.
Contemplate fires only when a **sub-agent gets stuck**: on an issue the sub-agent (a) retries, (b) follows
its policy's deterministic guardrails (stack-on / fallback / other), or (c) has no clear direction. In case
(c) it signals PEX (per the [Workflow Planner](../components/workflow_planner.md) Skill) → **PEX notifies
the Assistant → the Assistant calls `NLU.contemplate(source_flow)` and notes the request in the
[Context Coordinator](../components/context_coordinator.md) → NLU writes the new detection into the Dialogue
State and tells the Assistant it is done → the Assistant hands it back to PEX → the Workflow Planner
re-plans.** (Batch 2b.)

---

## 3 — Session Scratchpad (the swarm's working ledger)

The [Session Scratchpad](../components/session_scratchpad.md) is the cross-flow channel where the swarm shares
findings within a conversation. Entries are dicts with a **small set of required fields** plus flow-specific
payload — loosely structured next to the ontology-typed Dialogue State, which is the distinction that matters:
the state is what the agent *believes*, the scratchpad is what the swarm is *working on*.

PEX sub-agents write findings into the scratchpad, and because they can run in parallel it is the surface
exposed to **race conditions**. NLU resolves this: it is **triggered to review the scratchpad whenever it is
updated**, and it is the NLU loop's responsibility to keep the scratchpad operating smoothly and uncorrupted —
merging duplicates, reconciling contradictions, and pruning stale notes using its deeper understanding of the
user's true intent.
