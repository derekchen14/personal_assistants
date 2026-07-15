# Round 3 — NLU belief, ambiguity & the intent rework (the Heart)

Maps to **Master Plan · Round 3**. Effort **L**. Depends on: **Round 1** (eval gate — required for the intent
rework) and **Round 4** (the scratchpad now lives on the World as `SessionScratchpad`). The highest-risk step;
gate every sub-item on the trace runner.

**Goal:** bring NLU belief + ambiguity behavior to spec and adopt the PEX System-1 intent hint.
**Deliverable:** the items below, each green on the offline suites *and* the 10 approved trajectories.

Spec: `modules/nlu.md`; `components/{dialogue_state,ambiguity_handler,session_scratchpad}.md`.

**Reading the current code.** The pieces this step touches:
- `NLU.understand(op)` (`nlu.py:84-96`) → `think` / `react` / `contemplate`.
- `think` (`nlu.py:100-115`) → `predict` (`nlu.py:260-267`) → `_classify_intent` (`nlu.py:311-320`) +
  `_detect_flow` (`nlu.py:322-359`).
- `_repair_entities` (`nlu.py:159-216`) — the entity-repair ladder.
- `contemplate` (`nlu.py:117-126`) → `_check_routing` (`nlu.py:446-464`).
- `DialogueState` flags (`dialogue_state.py:60-63`) + `grounding` (`dialogue_state.py:75`, the `ver` bool).
- `AmbiguityHandler` (`ambiguity_handler.py`) — `declare/present/ask/resolve`, `needs_clarification`,
  `should_escalate`, the per-level `counts`.

---

## Decisions

**Locked — and where they stand (2026-07-10):**
- **Intent model = PEX System-1 hint.** SHIPPED — coarse intent is PEX's in-reasoning guess; NLU
  flow-detection is the authoritative write. (§3.1)
- **Keep `_classify_intent` as a callable.** SHIPPED — the `_intent_split` tie-break calls it. (§3.1.1)
- **Cross-turn clarification binding — SUPERSEDED.** The bind concept was removed: detection always runs
  first; when detection matches the stalled Active flow, `nlu.think()` fills that flow in place. See
  `rounds/round_3.3_spec.md` and `rounds/round_2.12_spec.md`. (was §3.2.1)
- **Flag cleanup.** DONE 2026-07-10 — see §3.4 for the record.

**Resolved here — confirm or override:**
- **E14 · low-confidence entity repair.** rec: write the value but set `grounding.ver=False` (a prediction);
  **no blanket PEX gate** — a policy opts into gating only if it uses the signal. (per the user; §3.2.2)
- **E12 · re-route ownership — DECIDED: both, distinct roles.** The policy applies a **hard-coded
  `fallback()`** when it knows the fix (within-policy sibling swap), else raises a **general-fallback signal** →
  the Assistant has NLU run `contemplate()` (cross-flow re-detect). (§3.2.4)
- **E13 · scratchpad location.** Resolved in Round 4 — on the World as `SessionScratchpad`, reached as
  `nlu.scratchpad`; the entry contract + conservative NLU review have since shipped. (§3.3)

**Deferred (stub — designed, not built):**
- Scratchpad auto-promotion (§S-2); the continuous event-triggered review — the synchronous pass
  shipped (§S-3).

**Follow-on round:** TypeSafe flow detection (a non-LLM Choice model as detection's round zero) is
spec'd separately at `rounds/round_3.6_spec.md`.

---

## 3.1 — Intent model rework (the keystone)  ·  N1  ·  **SHIPPED**

**Shipped** across rounds 0.3–2.12: detection runs first with the `_intent_split` tie-break;
`_classify_intent` survives only as that tie-break callable; the hint is PEX's intent OR the active
flow's name (the round-2.12 Continue intent — PEX's active-flow selection also seeds the vote list).
Further upgrades still wanted: detection near-miss exemplars (`rounds/round_2.13_spec.md` §2.13.3) and
TypeSafe as detection's round zero (`rounds/round_3.6_spec.md`). The rest of this section is the
design record as written before implementation.

**Was current then:** `predict` always ran a dedicated intent pre-pass — `_classify_intent` (one LLM
call) — then `_detect_flow` narrowed to that intent. The orchestrator prompt *forbade* PEX from
classifying ("NLU has ALREADY classified… ACT, don't re-classify").

**Target (`nlu.md:108-138`):** coarse intent is **PEX's System-1** in-reasoning guess (no extra model call);
**NLU flow-detection is the authoritative write** — detecting a flow implicitly classifies the intent via
`FLOW_ONTOLOGY[flow]['intent']`. PEX's hint *narrows* detection; it never writes belief.

### 3.1.1 — Stop the automatic pre-pass; keep `classify_intent` as a callable
The pre-pass is dropped from the **default** path, but `_classify_intent` is **not deleted** — it stays a
callable that NLU invokes in two situations:

1. **Round-2 escalation.** When round-1 flow detection is unconvincing (low top-1 share, or the voters' flows
   span **different intents**), NLU calls `_classify_intent` to settle a coarse intent, then re-runs
   `_detect_flow` narrowed to that intent's candidates. (This is the System-2 fallback the single-round
   ensemble can escalate into — see the escalating-ensemble stub.)
2. **`contemplate`.** Re-routing after a failed flow can call `_classify_intent` to anchor the narrowed
   re-detection (today `contemplate` routes purely off edge flows; the intent anchor sharpens it).

So `predict` changes from "always classify, then detect" to "detect first; classify only to break a tie":

```python
# nlu.py — predict(), rewritten
def predict(self, user_text:str, hint:str='') -> dict:
    detection = self._detect_flow(user_text, hint)          # hint='' on the first pass (pre-hook)
    if self._intent_split(detection):                       # voters disagree ACROSS intents → escalate
        intent = self._classify_intent(user_text)           # the retained coarse-intent call
        detection = self._detect_flow(user_text, hint=intent)
    return {'flow_name': detection['flow_name'],
            'confidence': detection['confidence'],
            'pred_flows': detection.get('pred_flows', [])}

def _intent_split(self, detection:dict) -> bool:
    """True when the ranked flows in pred_flows belong to more than one intent — the signal that a
    coarse-intent tie-break is worth a call. Single-round, fixed cost: at most one extra call."""
    intents = {FLOW_ONTOLOGY[f['flow_name']]['intent'] for f in detection['pred_flows']}
    return len(intents) > 1 and detection['confidence'] < self.ambiguity.confidence_min
```

`pred_intent` still derives from the detected flow (`_write_belief` `nlu.py:489-500` already sets
`pred_intent = FLOW_ONTOLOGY[flow]['intent']`; `validate` `nlu.py:138-155` re-asserts it). No separate intent
write remains on the default path.

**Keep** `_classify_intent` (`nlu.py:311-320`), `build_intent_prompt`, and `_intent_schema`. Only the
*unconditional call site inside `predict`* is removed.

### 3.1.2 — PEX System-1 bias as prompt guidance
Rewrite `for_orchestrator.py:31-35`. Instead of "don't classify," instruct PEX to form a cheap coarse-intent
sense **inside its own reasoning** (no LLM call, no belief write) and, under any uncertainty, lean
**Plan/Clarify** (`architecture.md:98`) — which forces the await path so NLU's System-2 decides. The prompt
must make clear the hint is *reasoning*, never a committed intent.

```text
# for_orchestrator.py — replacement guidance (prose in the system prompt)
You form a quick sense of the user's intent as you reason — but you do NOT classify on the record.
NLU owns the authoritative intent (it is written when a flow is detected). Use your sense only to pick
which flow to activate when the mapping is obvious (e.g. a click or a clear continuation). When you are
unsure — the request is multi-step, vague, or spans intents — bias toward Plan or Clarify, which waits
for NLU rather than guessing. Never assert a final intent yourself.
```

### 3.1.3 — `detect_flow(text, hint='')`
Rename `_detect_flow`'s parameter from `intent=None` to **`hint=''`** and thread PEX's coarse-intent hint
into it. The hint is a *candidate-narrowing* string, not an authoritative intent.

```python
# nlu.py — signatures
def _detect_flow(self, user_text:str, hint:str='') -> dict:
    candidate_names = self._flow_candidate_names(hint)
    ...

def _flow_candidate_names(self, hint:str='') -> list[str]:
    if not hint:                                   # no hint → full ontology (or active flow's intent)
        active = self.flow_stack.get_flow()
        if active:
            return self._intent_candidates(active.intent)
        return list(FLOW_ONTOLOGY)
    return self._intent_candidates(hint)           # hint set → that intent's flows + edge flows

def _intent_candidates(self, intent:str) -> list[str]:
    edges = _get_edge_flows_for_intent(intent)
    return [n for n, cat in FLOW_ONTOLOGY.items() if cat['intent'] == intent or n in edges]
```

PEX passes the hint when it re-invokes detection (e.g. a continuing turn where PEX already has a coarse
sense). The Assistant threads it through `understand(op='think', hint=...)` → `think` → `predict(text, hint)`.

**Sequencing nuance (prove via eval).** NLU's pre-hook `think` runs *before* PEX, so the first-pass detection
has `hint=''` — full-ontology detection, which is the authoritative write. The hint only matters on
**re-detection** (PEX dissatisfied, or a parallel refine). Confirm the pre-hook still produces a usable
authoritative write and the hint only sharpens re-routes: **run all 10 trajectories before/after; require no
trajectory-score regression past threshold.**

---

## 3.2 — Ambiguity behavior  ·  N3 / N4 / N5 / N6

The handler stays the closed-vocab record (`general` / `partial` / `specific` / `confirmation`);
whether a reply resolves an open ambiguity is decided by flow detection itself — see the note below.

### 3.2.1 — REMOVED (superseded)
This section prescribed a `_bind_reply_to_question` LLM pass that judged whether a reply answered the
open question. The bind concept was thrown away: detection always runs first, and when it lands on the
stalled Active flow, `nlu.think()` fills that flow in place — resolving the ambiguity as a side effect
of a normal slot-fill. Shipped in round 2.12; design record in `rounds/round_3.3_spec.md`.

### 3.2.2 — Mark low-confidence entity repairs as unverified (no blanket gate)
**Current:** `_repair_entities` (`nlu.py:159-216`) — the exact/case rungs (`:181-185`) commit a clean value;
the lexical (`:188-199`) and LLM (`:201-213`) rungs set `slot.value = <guess>` **and** already declare
`confirmation`.

**Change (E14, revised):** a doubtful repair (lexical / LLM rung) writes the value **and leaves
`grounding.ver = False`** — the value is present but marked *unverified* (a prediction). It keeps declaring
`confirmation` exactly as today.

**Do not add a blanket PEX gate.** PEX is *not* globally blocked on `ver`. A policy that wants to gate on
verification reads `grounding.ver` itself; policies that don't care proceed on the predicted value. Only the
declared `confirmation` ambiguity (already surfaced) reaches the user.

```python
# nlu.py — _repair_entities, lexical/LLM rung (doubtful resolve)
if matches:
    slot.value = matches[0]
    self.world.current_state().grounding['ver'] = False     # predicted, not verified
    self.ambiguity.declare('confirmation', metadata={
        'missing': slot_name, 'candidate': matches[0],
        'question': f'Did you mean "{matches[0]}" for {slot_name}?'})
```

```python
# example — a policy that DOES opt into the gate (most do not)
if flow.needs_verified_entity and not state.grounding['ver']:
    self.ambiguity.declare('confirmation', observation=..., metadata={...})
    return TaskArtifact(flow.name())     # this policy chose to wait; PEX did not force it
```

Verification flips `ver=True` only when PEX confirms (user-approved or PEX-written), per `nlu.md:213-215`.

### 3.2.3 — Wire `should_escalate`  · N5  ·  **lower priority**
`AmbiguityHandler.should_escalate` (sum of `counts` ≥ `max_turns`) exists and `counts` increments on
every `recognize`, but nothing calls it. The intent stands: after repeated clarification attempts the
agent should **switch strategy** — offer explicit options or hand off — instead of re-asking.

Two things changed since this was written, so the wiring needs a rethink before it lands:
1. `assistant.py` now zeroes `counts` at every turn start (the reset that lets counts show *concurrent*
   ambiguities within a turn, planner spec scenario 21). As written, `should_escalate` can therefore
   only see same-turn declares — it can never count "asked three turns in a row". A cross-turn signal
   is needed (e.g. reset counts on `resolve()` instead of at turn start, or track asks per open
   ambiguity), and that interacts with scenario 21's within-turn semantics.
2. The surface point moved: clarification questions now go out through the
   `ask_clarification_question` tool (`PolicyExecutor._ask_clarification`), which is where the
   escalation check would live.

Park until the higher-priority rounds land (2.13 grounding/hygiene, 3.6 TypeSafe, async NLU).

### 3.2.4 — Wire `understand(op='contemplate')` through the Dialogue State  · N6
`contemplate` is fully coded (`NLU.contemplate` → `_check_routing`) and `NLU.understand` dispatches
`op='contemplate'` correctly. The setup, clarified:

- **The common caller is the flow's policy** — when slot-filling or the sub-agent hits an issue mid-flow.
  That is why we generally say "PEX does not call contemplate": the *orchestrator agent* rarely needs it.
- **It is still possible from the agent.** The PEX agent has the tool `understand(op='contemplate')`.
  Today `PolicyExecutor._understand_user` ignores `op` and always returns the state document — the
  wiring gap this item closes.
- **The PEX module (the code portion) executes the tool by calling `self.world.state.contemplate()`** —
  a component call, which keeps the doctrine intact: PEX never invokes the NLU *module*.
- **Prerequisite refactor: `react` / `think` / `contemplate` move under the `DialogueState` class.**
  The Assistant reaches them as `self.nlu.state.think(...)`; NLU keeps owning the state object and the
  prompt/ensemble machinery those methods use.

**E12 (re-route ownership) — DECIDED: both, with distinct roles.** The policy classifies the error and either
(a) applies a **hard-coded `fallback()`** it knows for that error (a within-policy swap to a sibling), or
(b) raises a **general-fallback signal** when it can't recover itself. The general-fallback signal alerts the
Assistant, which runs `contemplate()` for a cross-flow re-detect. Wire accordingly:

```python
# policy recovery — a hard-coded fallback when the policy knows the fix; else a general-fallback signal
if has_hardcoded_fallback:
    self.flow_stack.fallback(better_flow_same_intent)   # within-policy swap to a known sibling
else:
    return {'_signal': 'fallback', 'source_flow': flow.name()}   # general fallback → Assistant → contemplate
```

```python
# assistant.py — the Assistant, on a general-fallback signal, re-routes through the state component
self.nlu.state.contemplate(last_user_text)   # writes a new detection
# the Workflow Planner then stacks/falls back to the re-detected flow
```

---

## 3.3 — Scratchpad schema & synchronous review  ·  S2 / S3  ·  **MOSTLY SHIPPED**

The scratchpad is the `SessionScratchpad` on the World (Round 4). **MemoryManager does not write to it.**

**Status (2026-07-10):** the entry contract shipped — producers write `version` / `turn_number` /
`used_count` themselves (`research.py find_policy`, `NLU.attempt_recovery`), and the write policy bumps
`used_count` when it consumes an entry. `NLU.review_scratchpad` exists as the synchronous turn-point
review, conservative for now: it repairs entries missing the contract fields via `amend_entry`; semantic
review (merge, prune, contradiction checks) stays designed-not-built (§S-3 is its continuous form).
**Not shipped:** the write path was NOT re-pointed through `NLU.append_to_scratchpad` — writers call
`scratchpad.append_entry` directly, and the orchestrator writes through the PEX `append_to_scratchpad`
tool. Decide whether the NLU-routed write path is still wanted, or whether the tool path plus NLU's
turn-point review supersedes it. The subsections below are the original design record.

### 3.3.1 — Required entry fields + the `append_to_scratchpad` write path
**Entry shape.** Entries are keyed by **flow name** (one entry per flow). Every entry includes three
required fields, plus whatever flow-specific payload the producer needs:

| Field | Type | Meaning |
|---|---|---|
| `version` | `int` | payload schema version; bump when the payload shape changes |
| `turn_number` | `int` | the turn the entry was written (`= context.turn_id`) |
| `used_count` | `int` | how many downstream flows have read this entry (maintained by NLU, 3.3.2) |

The producer writes these fields itself when it appends; nothing is added behind its back. (Corrects the
stale audit: `used_count` is **not** currently written — this step adds it.)

**Write path.** A sub-agent appends through **`NLU.append_to_scratchpad(writer, entry)`** — the exposed API.
routing the write through NLU is what lets NLU review the pad on each append. NLU exposes three
methods (mirroring `session_scratchpad.md`), delegating to the shared `SessionScratchpad` instance:

```python
# nlu.py — the exposed scratchpad API (NLU maintains nlu.scratchpad == world.scratchpad)
def append_to_scratchpad(self, writer:str, entry:dict):
    """Any sub-agent / the PEX loop appends here. `writer` is recorded in code so authorship can't be
    forged. The append triggers NLU's review (3.3.2)."""
    self.scratchpad.write(entry, writer=writer)
    self._review_scratchpad()                       # synchronous review at this turn point

def read_from_scratchpad(self, key=None, writer=None, keys=None):
    return self.scratchpad.read(key=key, writer=writer, keys=keys)   # read-only

def update_scratchpad(self, key:str, entry:dict):    # NLU-only: revise/correct a prior entry
    self.scratchpad.write(key, entry)
```

```python
# producer (a research-style policy) — write findings at policy entry
nlu.append_to_scratchpad(flow.name(), {
    'version': 1, 'turn_number': context.turn_id, 'used_count': 0,
    'findings': [...],
})
# consumer — read by key, read-only
entry = nlu.read_from_scratchpad('audit')
```

**Wiring note.** Round 4 wired policies/PEX to call `self.scratchpad.write(...)` directly (the interim path).
This step re-points those writers to `NLU.append_to_scratchpad(...)` so the append triggers review. PEX and
the policies get the NLU handle the same way they get other shared components (passed in `components` /
constructor); the scratchpad **instance** stays on the World, so this is an access-path change, not a second
store.

**Completion records.** `SessionScratchpad.write_completion` (Round 4) appends `{flow, summary, metadata}`.
Bring it under the same contract — include `version`/`turn_number`/`used_count` — so completion entries read
back through the same filters. (This is the `c6` completion-vehicle item deferred from Round 4.)

### 3.3.2 — Synchronous NLU review + `update_scratchpad`  · S2
**Spec:** appending triggers NLU to review the pad — merge duplicate entries, reconcile contradictions, prune
stale notes, and maintain `used_count` — via the **NLU-only** `update_scratchpad`
(`session_scratchpad.md:22,78-89`; `nlu.md:258-269`).

**Core now:** run the review **at the turn points NLU already executes** (synchronously inside
`append_to_scratchpad` and at the end of `think`), **not** as a background trigger on every append. Add a
`_review_scratchpad` routine:

```python
# nlu.py — _review_scratchpad (synchronous review pass)
def _review_scratchpad(self):
    entries = self.scratchpad.read()                 # whole pad
    # 1. merge entries that share a flow-name key (keep newest, union payload)
    # 2. drop entries contradicted by the current Dialogue State belief
    # 3. bump used_count for entries referenced by the active flow this turn
    for key, merged in self._reconcile(entries).items():
        self.update_scratchpad(key, merged)
```

Mark the **continuous / event-triggered** version (below) `# designed-not-built`.

**E13 — RESOLVED in Round 4:** the scratchpad lives on the World as a `SessionScratchpad` component, reached
as `nlu.scratchpad`. This section adds the entry-field contract + NLU review on that component (not
`MemoryManager`).

---

## 3.4 — Vestigial flag cleanup  ·  N "D-state" / Plan-report G8  ·  **DONE 2026-07-10**

All three dead flags were written by policies and read by nobody; `has_plan` (the one live flag when
this was drafted) had already disappeared in earlier rounds, so the whole flag block went with them.

What was removed:
- `keep_going`, `has_issues`, `natural_birth` from `DialogueState` — `reset`, `serialize`, `load`,
  and `_BELIEF_FIELDS`.
- The `flags` block from the `read_state()` document — state.json is now four blocks
  (`session`, `user_beliefs`, `grounding`, `flow_stack`).
- The five dead `state.keep_going = True` writes (`draft.py` ×2, `revise.py` ×3).
- The three flag fields from the trace snapshot projection (`_snapshot.py _project_state_obj`).
- The three document-shape test assertions updated (`nlu_unit_tests.py` ×2, `pex_unit_tests.py` ×1).

Suites green after the cleanup: 244 passed. Plan-aware chaining stays behavior (PEX knows it is
mid-plan), never a stored flag.

---

## Stubs — designed, not built (full specs)

These are not executed in this step, but they are specified in enough detail to build later without
re-deriving the design.

*(S-1 — the escalating 3-round ensemble with alignment multipliers and abstention — was removed:
the shipped two-round agreement-scored ladder in `_detect_flow` is the better design.)*

### S-2 — Scratchpad auto-promotion  (`session_scratchpad.md:92-105`)
A background MEM task (off the turn's critical path) promotes a salient scratchpad entry to L2/L3.

```python
# mem-side (background) — auto-promotion
for key, entry in scratchpad.read().items():
    if entry['used_count'] >= PROMOTE_MIN_READS:                 # frequency criterion
        score = engineer(build_salience_prompt(entry), 'low')   # LOW-tier judge: generalizable? surprising?
        if score.promote:
            memory.preferences.store_preference(key, entry)     # L2, or business_context for L3
```

- **Triggers:** `used_count ≥ N` **or** a LOW-tier salience/surprisal judge passes **or** explicit user save
  (`store_preference`).
- **Keep the `used_count` plumbing** (3.3) so this has its frequency signal when built.
- **Why deferred:** needs the real background MEM loop; the synchronous facade (Round 4) has no loop yet.

### S-3 — Continuous, event-triggered scratchpad review
The synchronous `_review_scratchpad` (3.3.2) runs at turn points. The target is an **always-running asyncio
task** triggered by each append, settling by the turn boundary.

```python
# nlu.py — event-triggered review (target)
async def _review_loop(self):
    while True:
        await self._scratchpad_dirty.wait()      # set by append_to_scratchpad
        self._scratchpad_dirty.clear()
        self._review_scratchpad()                # debounced; must settle before the turn boundary join
```

- **Why deferred:** the three loops (NLU/PEX/MEM) run synchronously at turn points in this release; the
  continuous-loop machinery is a later structural change. The synchronous review is behaviorally equivalent
  for a single turn.

---

## Verification
For the remaining open items (3.2.2, 3.2.3, 3.2.4, the 3.3 write-path decision):
- Offline gate suites green (`run_suite.py --tests`); update existing tests only.
- Full suite (`run_suite.py`, default 8-sample) before/after each item — no completion-rate regression.
- Smoke: a clarification answer resolves the pending question through detection landing on the stalled
  flow (no bind pass); a low-confidence repair leaves `grounding.ver == False` and recognizes
  `confirmation`; `understand(op='contemplate')` from the orchestrator reaches
  `self.world.state.contemplate()` and writes a re-detection.
