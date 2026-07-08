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

**Locked (this step implements):**
- **Intent model = PEX System-1 hint.** Coarse intent is PEX's in-reasoning guess (no model call); NLU
  flow-detection is the authoritative write. Locked in the master plan — the keystone of this step. (§3.1)
- **Keep `_classify_intent` as a callable.** Drop only its unconditional pre-pass call site; retain it for
  round-2 escalation and `contemplate`. (per the user; §3.1.1)
- **Ambiguity resolution is LLM-driven.** The model judges whether the reply answers the open question rather
  than a fixed template; on resolve it fills the slot and clears. (per the user; §3.2.1)
- **Flag cleanup.** Remove the dead `keep_going` / `has_issues` / `natural_birth` writes; **keep `has_plan`**
  for now (Round 5 removes it — Plan-aware chaining becomes behavior, no flag). (§3.4)

**Resolved here — confirm or override:**
- **E14 · low-confidence entity repair.** rec: write the value but set `grounding.ver=False` (a prediction);
  **no blanket PEX gate** — a policy opts into gating only if it uses the signal. (per the user; §3.2.2)
- **E12 · re-route ownership — DECIDED: both, distinct roles.** The policy applies a **hard-coded
  `fallback()`** when it knows the fix (within-policy sibling swap), else raises a **general-fallback signal** →
  the Assistant has NLU run `contemplate()` (cross-flow re-detect). (§3.2.4)
- **E13 · scratchpad location.** Resolved in Round 4 — on the World as `SessionScratchpad`, reached as
  `nlu.scratchpad`; this step adds the entry contract + NLU review on it. (§3.3.2)
- **Scratchpad write path.** rec: writers append through `NLU.append_to_scratchpad(...)` so each append
  triggers NLU review; MemoryManager never writes the pad. (per the user; §3.3.1)

**Deferred (stub — designed, not built):**
- Escalating 3-round ensemble + alignment + abstention (§S-1); scratchpad auto-promotion (§S-2); the
  continuous event-triggered review — the synchronous pass ships now (§S-3).

---

## 3.1 — Intent model rework (the keystone)  ·  N1

**Current:** `predict` always runs a dedicated intent pre-pass — `_classify_intent` (one LLM call) — then
`_detect_flow` narrowed to that intent. The orchestrator prompt *forbids* PEX from classifying
(`for_orchestrator.py:31-35`: "NLU has ALREADY classified… ACT, don't re-classify").

**Target (`nlu.md:108-138`):** coarse intent is **PEX's System-1** in-reasoning guess (no extra model call);
**NLU flow-detection is the authoritative write** — detecting a flow implicitly classifies the intent via
`FLOW_CATALOG[flow]['intent']`. PEX's hint *narrows* detection; it never writes belief.

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
    intents = {FLOW_CATALOG[f['flow_name']]['intent'] for f in detection['pred_flows']}
    return len(intents) > 1 and detection['confidence'] < self.ambiguity.confidence_min
```

`pred_intent` still derives from the detected flow (`_write_belief` `nlu.py:489-500` already sets
`pred_intent = FLOW_CATALOG[flow]['intent']`; `validate` `nlu.py:138-155` re-asserts it). No separate intent
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
    if not hint:                                   # no hint → full catalog (or active flow's intent)
        active = self.flow_stack.get_flow()
        if active:
            return self._intent_candidates(active.intent)
        return list(FLOW_CATALOG)
    return self._intent_candidates(hint)           # hint set → that intent's flows + edge flows

def _intent_candidates(self, intent:str) -> list[str]:
    edges = _get_edge_flows_for_intent(intent)
    return [n for n, cat in FLOW_CATALOG.items() if cat['intent'] == intent or n in edges]
```

PEX passes the hint when it re-invokes detection (e.g. a continuing turn where PEX already has a coarse
sense). The Assistant threads it through `understand(op='think', hint=...)` → `think` → `predict(text, hint)`.

**Sequencing nuance (prove via eval).** NLU's pre-hook `think` runs *before* PEX, so the first-pass detection
has `hint=''` — full-catalog detection, which is the authoritative write. The hint only matters on
**re-detection** (PEX dissatisfied, or a parallel refine). Confirm the pre-hook still produces a usable
authoritative write and the hint only sharpens re-routes: **run all 10 trajectories before/after; require no
trajectory-score regression past threshold.**

---

## 3.2 — Ambiguity behavior  ·  N3 / N4 / N5 / N6

The handler is **LLM-driven**: rather than a fixed template deciding resolution, NLU reasons about whether the
new input answers the open question. The handler stays the closed-vocab record (`general` / `partial` /
`specific` / `confirmation`); the *judgment* of resolved-or-not moves to the model.

### 3.2.1 — Cross-turn binding: the LLM decides whether the reply resolves the ambiguity
**Current:** `agent.py:63-64` unconditionally calls `ambiguity.resolve()` (a blind clear) before any
detection, so every clarification answer is re-detected from scratch — the pending question is forgotten.

**Change:** when `ambiguity.present()` at turn entry, do **not** blind-clear. Hand the reply *and* the open
question to the LLM-driven resolution, which decides one of two outcomes:
- **Resolved** — the reply answers the question: fill the missing slot/entity from the reply, then `resolve()`.
- **Not resolved / abandoned** — the reply changes the subject: leave the ambiguity (or `resolve()` and fall
  through to fresh detection), and run normal `think` detection.

```python
# nlu.py — understand(), entry binding (replaces agent.py's blind resolve)
def understand(self, op, user_text='', dax=None, payload=None, hint=''):
    if op == 'think' and self.ambiguity.present():
        if self._bind_reply_to_question(user_text):     # LLM judges: does this answer the open question?
            return self.validate(self.world.current_state())   # resolved → belief already updated
        # not an answer → fall through to fresh detection (optionally resolve() first)
    ...

def _bind_reply_to_question(self, user_text:str) -> bool:
    """LLM-driven resolution. Given the open ambiguity (level, observation, metadata) and the user's
    reply, decide whether the reply resolves it. On resolve: write the recovered slot/entity into the
    detached flow's belief and call ambiguity.resolve(). Returns True iff resolved."""
    verdict = self.engineer(build_resolve_prompt(self.ambiguity, user_text, ...),
                            'resolve_ambiguity', schema=_resolve_schema())
    if verdict['resolved']:
        self._apply_resolution(verdict)     # fill the slot/entity named in ambiguity.metadata
        self.ambiguity.resolve()
        return True
    return False
```

This needs a small `resolve_ambiguity` prompt + schema (`{resolved: bool, value: str|null}`) and an
`_apply_resolution` that writes the recovered value onto the pending slot. (`nlu.md:237-240`,
`ambiguity_handler.md:46-49`.)

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

### 3.2.3 — Wire `should_escalate`  · N5
`ambiguity_handler.py:65-66` defines `should_escalate` and `counts` increments on every `declare`
(`:36-37`), but nothing calls it. Wire it into PEX's clarification path so that once a level has been
declared `ambiguity_escalation_turns` times (config, default 3) the agent **switches strategy** — offer
explicit options or hand off — instead of re-asking the same question.

```python
# pex.py — at the point PEX is about to surface ambiguity.ask()
if self.ambiguity.should_escalate():
    return self._escalated_clarification(flow)   # offer options / hand off, don't re-ask
question = self.ambiguity.ask(flow.name())
```

`_escalated_clarification` renders a selection block of the top candidates (or a "let's do something else"
hand-off) rather than repeating the question a fourth time.

### 3.2.4 — Wire the idle `contemplate` trigger  · N6
`contemplate` is fully coded (`nlu.py:117-126`, `_check_routing :446-464`) and reachable via
`understand(op='contemplate')` but **never called**. Add a stuck-flow signal in PEX/policy recovery that asks
the Assistant to call `NLU.contemplate(source_flow)`, then feed the re-detection into a `stackon`/`fallback`.

**E12 (re-route ownership) — DECIDED: both, with distinct roles.** The policy classifies the error and either
(a) applies a **hard-coded `fallback()`** it knows for that error (a within-policy swap to a sibling), or
(b) raises a **general-fallback signal** when it can't recover itself. The general-fallback signal alerts the
Assistant, which has NLU run `contemplate()` for a cross-flow re-detect. Wire accordingly:

```python
# policy recovery — a hard-coded fallback when the policy knows the fix; else a general-fallback signal
if has_hardcoded_fallback:
    self.flow_stack.fallback(better_flow_same_intent)   # within-policy swap to a known sibling
else:
    return {'_signal': 'fallback', 'source_flow': flow.name()}   # general fallback → Assistant → contemplate
```

```python
# agent.py — the Assistant, on a general-fallback signal, has NLU re-route
self.nlu.understand(op='contemplate', user_text=last_user_text)   # writes a new detection
# the Workflow Planner then stacks/falls back to the re-detected flow
```

---

## 3.3 — Scratchpad schema & synchronous review  ·  S2 / S3

The scratchpad is the `SessionScratchpad` on the World (Round 4), reached as `nlu.scratchpad`. **MemoryManager
does not write to it.** The common writer is a **sub-agent** (a policy, or the PEX loop) writing its findings
through NLU's exposed write method; NLU reviews the pad after each write.

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

## 3.4 — Vestigial flag cleanup  ·  N "D-state" / Plan-report G8

`dialogue_state.py` still defines a flag block (`:60-63`) and serializes it (`:113-116`, `:129`,
`:247-250`); `dialogue_state.md:105-116` says **no flag block**. Grep results (readers vs. writers):

| Flag | Written by | Read by | Verdict |
|---|---|---|---|
| `keep_going` | `draft.py:168,205`; `revise.py:108,112,216` | **nobody** | **Remove** — dead write. Plan-aware chain rebuilt as behavior in **Round 5 §5.4** (PEX knows it is mid-plan), never as a stored flag. |
| `has_issues` | `_BELIEF_FIELDS` (write_state `update`) | **nobody** | **Remove** — defined + serialized but never read. |
| `natural_birth` | `reset`/`serialize`/`from_dict` only | **nobody** | **Remove** — fully vestigial. |
| `has_plan` | `_BELIEF_FIELDS` (write_state `update`) | `revise.py:67,227` | **Keep for now** — read by Revise's Plan-aware scratchpad writes. **Round 5** removes it (the gated write is redundant with completion records). |

**Do now (3.4):** remove `keep_going`, `has_issues`, `natural_birth` from `__init__`, `reset`, `serialize`,
`serialize_session` flags, `load`, `from_dict`, and `_BELIEF_FIELDS`; delete the dead `state.keep_going = True`
writes in `draft.py`/`revise.py`. Leave `has_plan` (and its two Revise reads) untouched — it is live and
Round 5 owns its removal. After this, the only `flags` block entry persisted is `has_plan`, pending Round 5.

---

## Stubs — designed, not built (full specs)

These are not executed in this step, but they are specified in enough detail to build later without
re-deriving the design.

### S-1 — Escalating 3-round ensemble + alignment multiplier + abstention  (`nlu.md:159-181`)
**Now:** `_detect_flow` runs a **single** round of fixed-weight voters (`_ENSEMBLE_VOTERS` = one
`low`/`med`/`high`), and `_tally_votes` takes a simple weighted top-1 share.

**Target:** rounds escalate until an agreement threshold is met; each voter's weight is scaled by its
**alignment** (demonstrated reliability on this domain's taxonomy, from config); an **abstention**
(`none`/`unsure`) does not enter the agreement denominator.

| Round | Voters added | Agreement on post-weight top-1 |
|---|---|---|
| 1 | 2 × `med` | 2/2 |
| 2 | + 1 × `high`, + 1 alternate `med` | 3/4 |
| 3 | + 1 × `high` (extended thinking) | 3/5 |

```python
# nlu.py — escalating detect (target shape)
def _detect_flow(self, user_text, hint=''):
    votes = []
    for round_voters in self._rounds():                  # config-driven roster per round
        votes += self._run_round(round_voters, user_text, hint)   # parallel; abstainers excluded
        tally = self._tally_votes(votes)                 # alignment-weighted top-1 share
        if tally['top1_share'] >= self._round_threshold(len(votes)):
            return tally
    # no majority after the last round → low-confidence result; caller declares `general`
    return {**self._tally_votes(votes), 'confidence': min(tally['confidence'], self.ambiguity.confidence_min)}
```

- **Alignment multiplier:** `weight = tier_weight * alignment[provider][domain]` (alignment table in config,
  default 1.0). Tune per domain; never hardcode.
- **Abstention:** a voter returning `none` is dropped from `votes` before tally — it pushes toward the next
  round instead of counting as a wrong answer.
- **Plugs into:** 3.1.1's round-2 escalation — the `_intent_split` tie-break is the simplest case of this
  ladder; the full ladder generalizes it across rounds.

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
- Offline gate suites green (cwd wrapper). `test_nlu_module.py` especially — update any row that assumed the
  separate intent pre-pass; add a row asserting `_classify_intent` is still callable (round-2 + contemplate).
- **Trace gate (mandatory):** all 10 approved trajectories pass after each section; the intent rework (3.1)
  and ambiguity binding (3.2.1) are the regression-prone ones — diff trajectory scores before/after.
- Smoke: a clarification answer resolves the pending question (LLM-judged, not a blind re-detect); a
  low-confidence repair leaves `grounding.ver == False` and declares `confirmation`; an entry appended via
  `append_to_scratchpad` carries `version`/`turn_number`/`used_count` and triggers a review pass.
