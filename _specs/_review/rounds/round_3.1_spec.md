# Round 3.1 — Intent model rework (the keystone)

Status: **signed off 2026-07-08** — Derek picked D1-A, D2-A, D3-A (the recommendations). Implements
§3.1 (3.1.1 / 3.1.2 / 3.1.3) of `round_3_nlu.md`. Base commit: `a2445f6` (all line numbers below
refer to it). Shipped in `942bb79`.

**Amendments (2026-07-08, after ship):**
1. **D3-A superseded — the hint now has a real caller, and it is deterministic code.** PEX/NLU
   coordination is the Assistant's job, so the hint is never a tool argument: on an NLU consult,
   `_dispatch_understand` reads the flow PEX committed to the stack top — a domain intent
   (Research / Draft / Revise / Publish) becomes NLU's candidate-narrowing hint; Plan / Clarify /
   Converse (or an empty stack) carry no real signal, so the hint stays blank and NLU detects over
   the full ontology. The hint threads `understand(..., hint='') → think(..., hint='') →
   _detect_flow(text, hint)`. The orchestrator prompt carries no hint instructions.
2. **`predict()` folded into `think()`** (Derek): the detect-first + tie-break logic lives directly
   in `think`; there is no separate `predict` method. Tests renamed `TestPredictDispatch` →
   `TestThinkDispatch` and drive `think()` with the fill/repair steps stubbed.
3. **Orchestrator tool surface converged to two hot-path tools** (Derek): `understand(op = read |
   think | contemplate)` is the one belief tool (`read` returns the serialized belief and joins the
   NLU thread — Plan/Clarify wait there; `read_state` retired), and `manage_flows(op = update |
   stackon | fallback | activate | pop)` is the one flow tool (replaces `write_state` +
   `activate_flow`; `update` = the old update_flow, `pop` = the old pop_completed — Completed and
   Invalid flows removed all at once; the old belief-fields update op is gone — PEX cannot
   manipulate the belief, that is NLU's job).

Scope is **only §3.1**. Ambiguity binding (§3.2), the scratchpad contract (§3.3), and the flag
cleanup (§3.4) are separate sub-rounds and are not touched here.

---

## The change in one paragraph

Today `NLU.predict` always makes a dedicated intent call (`_classify_intent`, one LLM call), then
runs `_detect_flow` narrowed to that intent. The round makes **flow detection the authoritative
write**: detection runs first, and the detected flow implicitly sets the intent via
`FLOW_CATALOG[flow]['intent']`. The intent call survives as a **tie-break only** — it runs when the
ranked flows are low-confidence and span more than one intent. The orchestrator prompt stops saying
"NLU already classified; do not re-classify" and instead tells PEX to form a cheap intent sense in
its own reasoning and lean Plan/Clarify when unsure. `_detect_flow`'s `intent` parameter is renamed
to `hint` to signal it is a candidate-narrowing string, not an authoritative intent.

## New concepts

- **No new components, classes, config keys, or state fields.**
- One new private method: `NLU._intent_split(detection)` — a boolean tie-break test. It reads
  existing data (`detection['pred_flows']`, `FLOW_CATALOG`, `ambiguity.confidence_min`).
- One renamed parameter: `_detect_flow(..., intent=None)` → `_detect_flow(..., hint='')`, and the
  same rename on `_flow_candidate_names` and `predict`.
- Under Decision D1-A only: one new module-level prompt constant `GENERIC_FLOW_PROMPT` in
  `backend/prompts/experts/__init__.py`, plus an `intent=''` branch in `build_flow_prompt`. This is
  new prompt text, not a new concept — surfaced for sign-off in D1.

## What §3.1 already has in the code (verified, not missing)

Check these before treating anything as unbuilt:

1. **Belief is already flow-derived.** `_write_belief` (nlu.py:496-507) sets
   `state.pred_intent = FLOW_CATALOG[flow_name]['intent']`, and `validate` (nlu.py:139-156)
   re-asserts it. The plan's claim "no separate intent write remains on the default path" is
   already true for the *write*. The only thing still running the pre-pass is the call site inside
   `predict` (nlu.py:262). So 3.1.1 is a **one-line deletion plus a tie-break guard**, not a rewrite
   of the belief path.
2. **`_flow_candidate_names(intent)` already exists** (nlu.py:362-366) and already returns "that
   intent's flows + edge flows". The plan's proposed `_intent_candidates` helper duplicates it —
   see Simplifications.
3. **`_get_edge_flows_for_intent` already exists** (nlu.py:22-28). No new edge-flow helper needed.
4. **The eval `state` dimension already scores exactly this.** `run_evals.py:113-116` checks
   `pred_flows[0]['flow_name'] == expected_flow`. The authoritative-write acceptance criterion maps
   straight onto it — no new eval harness.

## What is actually missing or contradicted

1. **`predict` still runs the unconditional pre-pass** (nlu.py:262). This is the core removal.
2. **The orchestrator prompt contradicts the target.** `INTENT_TAXONOMY` (for_orchestrator.py:32-36)
   says "NLU runs before you and has ALREADY classified the intent … Your job is to ACT on that
   detection, not to re-classify it". `TOOL_POLICY` (for_orchestrator.py:52-54) repeats it. §3.1.2
   rewrites both.
3. **`get_prompt('')` would crash.** `build_flow_prompt` (for_experts.py:375-397) calls
   `get_prompt(intent)` → `PROMPTS[intent]` (experts/__init__.py:30-31). An empty intent raises
   `KeyError`. So the target "first pass runs `_detect_flow(text, hint='')`" cannot work until the
   prompt path handles an empty hint. This forces **Decision D1**.
4. **No production caller passes a non-empty `hint`.** The pre-hook `think` always runs with hint=''.
   PEX's only mid-turn NLU re-consult is `understand(op='contemplate')` (pex.py:395, 720), which has
   its own routing and does not go through `predict`. So the plan's `understand(..., hint='')`
   threading has no caller this round. This forces **Decision D3**.
5. **Stale references in the plan.** `round_3_nlu.md` cites line numbers from an older base
   (predict at 260-267, `_detect_flow` at 322-359, etc.); current lines are predict 261,
   `_detect_flow` 323, `_flow_candidate_names` 362, `_classify_intent` 312. The verification section
   names `test_nlu_module.py`, which does not exist — the NLU tests live in
   `utils/evaluation_suite/_tests/nlu_unit_tests.py` and `model_tests.py`. Target those.

---

## 3.1.1 — Stop the automatic pre-pass; keep `_classify_intent` as a tie-break

**Why.** Today every turn pays for a classify LLM call whose only job is to narrow the flow
candidate list. When detection ranges over the whole catalog (D1-A), that narrowing call is no
longer needed to reach the answer — the detected flow already fixes the intent. Removing the call on
the common path is one fewer LLM round per turn. We keep `_classify_intent` for the rare low-signal
turn where detection cannot separate two intents on its own, because a coarse intent read is the
cheapest way to break that specific tie.

**Current (nlu.py:261-268).**

```python
def predict(self, user_text:str) -> dict:
    intent = self._classify_intent(user_text)           # always classifies first
    detection = self._detect_flow(user_text, intent)
    return {
        'flow_name': detection['flow_name'],
        'confidence': detection['confidence'],
        'pred_flows': detection.get('pred_flows', []),
    }
```

**Proposed.** Detect first; classify only to break a low-confidence cross-intent tie. `pred_intent`
keeps deriving from the detected flow inside `_write_belief` (nlu.py:502), so no belief change is
needed here.

```python
# nlu.py — predict(), rewritten
def predict(self, user_text:str, hint:str='') -> dict:
    detection = self._detect_flow(user_text, hint)      # hint='' on the pre-hook first pass
    if self._intent_split(detection):                   # low-confidence AND spans >1 intent
        intent = self._classify_intent(user_text)       # the retained tie-break call
        detection = self._detect_flow(user_text, hint=intent)
    return {'flow_name': detection['flow_name'],
            'confidence': detection['confidence'],
            'pred_flows': detection.get('pred_flows', [])}

def _intent_split(self, detection:dict) -> bool:
    """True when the ranked flows span more than one intent AND top-1 is under the confidence
    floor — the only case where a coarse-intent tie-break is worth a call. At most one extra
    classify + one extra detect per turn."""
    intents = {FLOW_CATALOG[f['flow_name']]['intent'] for f in detection['pred_flows']}
    return len(intents) > 1 and detection['confidence'] < self.ambiguity.confidence_min
```

**Keep** `_classify_intent` (nlu.py:312-321), `build_intent_prompt`, `_intent_schema`. Only the
*unconditional call site in `predict`* is removed. `_classify_intent` still serves the tie-break here
and `contemplate`'s routing.

`think` (nlu.py:101-116) calls `self.predict(user_text)` at line 102 — under Decision D3-A this stays
as-is (no hint threaded), and detection still runs on the first pass with hint=''.

## 3.1.2 — PEX System-1 bias as prompt guidance

**Why.** The prompt currently tells PEX that NLU already made a separate classification and that
PEX must not re-classify. After 3.1.1 there is no separate classification step to defer to on the
default path — the intent comes out of flow detection. Left unchanged, the prompt would describe a
pipeline that no longer exists and could push PEX to trust a "classified intent" that was never
independently computed. The rewrite tells PEX to form its own cheap intent sense while reasoning,
never write it to belief, and lean Plan or Clarify when unsure — Plan and Clarify are the two paths
that wait for NLU's authoritative detection instead of guessing a flow.

**Current (for_orchestrator.py:26-27, the header comment).**

```python
# NLU classifies the coarse intent and detects the flow before the loop runs; the orchestrator
# reads that detection from belief and acts on it.
```

**Current (for_orchestrator.py:32-36, inside `INTENT_TAXONOMY`).**

```python
'before you and has ALREADY classified the intent and detected the flow for this turn — read '
'them from belief with `read_state` (user_beliefs.intent, pred_flows, pred_slots). Your job '
'is to ACT on that detection, not to re-classify it; treat your own read of the intent as '
'internal reasoning, and bias toward Plan or Clarify only when the detection looks uncertain '
'or the request spans several steps:\n'
```

**Proposed.** Replace the header comment and the "ALREADY classified … ACT, don't re-classify"
sentence with guidance that PEX forms a cheap intent sense in its own reasoning, never writes
belief, and leans Plan/Clarify when unsure. Draft replacement for the sentence beginning "NLU runs
before you and has ALREADY classified …":

```text
Flows group under one of seven intents. You form a quick sense of the intent as you reason — but
you do NOT classify on the record. NLU owns the authoritative intent: it is written when NLU
detects a flow, and you read it from belief with read_state (user_beliefs.intent, pred_flows,
pred_slots). Use your own sense only to pick which flow to activate when the mapping is obvious (a
click or a clear continuation). When you are unsure — the request is multi-step, vague, or spans
intents — bias toward Plan or Clarify, which wait for NLU rather than guessing. Never assert a
final intent yourself.
```

**Current (for_orchestrator.py:52-54, inside `TOOL_POLICY`).**

```python
'**Understanding a user turn.** NLU runs before you and writes the detection to belief: the '
'classified `intent`, ranked candidate flows (`pred_flows`), and filled slot values '
'(`pred_slots`). Call `read_state` to read it — do not re-derive the flow yourself.\n'
```

**Proposed.** The sentence stays accurate (NLU still writes an intent to belief, now flow-derived) —
leave the belief-read instruction, but drop wording that implies NLU makes a *separate*
classification. Minimal edit: change "the classified `intent`" to "the detected `intent`" so the
prompt matches the flow-first model. **Why:** the word "classified" is the last remaining hint that
a standalone intent call ran; "detected" is the plain, accurate description after 3.1.1. No other
`TOOL_POLICY` change.

Prose-only change. No code, no new tool, no belief write from PEX.

## 3.1.3 — `_detect_flow(text, hint='')` and candidate narrowing

**Why the rename.** The parameter is no longer an authoritative intent that detection must obey — it
is an optional narrowing string that may be empty on the first pass and only set on the tie-break
re-detect. Naming it `hint` (and defaulting it to `''` instead of `None`) states that contract in
the signature, and it matches the vocabulary the round plan uses. It also makes the empty case a
plain falsy string check (`if not hint`) rather than an `is None` check.

**Current (nlu.py:323, 362-366).**

```python
def _detect_flow(self, user_text:str, intent:str|None=None) -> dict:
    ...

def _flow_candidate_names(self, intent:str|None) -> list[str]:
    if intent is None:
        return list(FLOW_CATALOG)
    edges = _get_edge_flows_for_intent(intent)
    return [name for name, cat in FLOW_CATALOG.items() if cat['intent'] == intent or name in edges]
```

**Proposed — rename the parameter** on three methods from `intent`/`intent=None` to `hint=''`:

```python
# nlu.py — signatures after rename
def predict(self, user_text:str, hint:str='') -> dict: ...
def _detect_flow(self, user_text:str, hint:str='') -> dict: ...
def _flow_candidate_names(self, hint:str='') -> list[str]: ...
def _detect_flow_prompt(self, user_text:str, hint:str, convo_history:str) -> str: ...
```

`_detect_flow` (nlu.py:323-360) passes `hint` where it passes `intent` today (into
`_detect_flow_prompt`, `_flow_candidate_names`, `_flow_detection_schema`). No body logic changes
beyond the rename and the D1 candidate/prompt behavior below.

**`_flow_candidate_names` behavior when `hint=''`** is Decision **D1**. The two live options:

```python
# D1-A (recommended): empty hint → full catalog, so detection can switch intents in one pass
def _flow_candidate_names(self, hint:str='') -> list[str]:
    if not hint:
        return list(FLOW_CATALOG)
    edges = _get_edge_flows_for_intent(hint)
    return [n for n, cat in FLOW_CATALOG.items() if cat['intent'] == hint or n in edges]
```

The `hint`-set branch is byte-identical to today's `_flow_candidate_names` body (nlu.py:362-366) —
only the empty-hint branch changes.

**Do NOT add `_intent_candidates`** (the plan's proposed helper). Its body equals the `hint`-set
branch above; splitting a 3-line branch into a separate method that has one caller adds indirection
for no reuse (project rule: extract a helper only at 3+ call sites). See Simplifications.

**Decision D3** governs whether `hint` is threaded through `understand`/`think`. Recommended (D3-A):
it is not — `understand` (nlu.py:85-97) and `think` (nlu.py:101-116) keep today's signatures, and
`predict` supplies `hint=''` on the first pass and `hint=<classified intent>` only on the internal
tie-break re-detect.

**Sequencing (prove via eval, not by inspection).** The pre-hook `think` runs before PEX, so the
first pass is always hint='' — a full-catalog authoritative write under D1-A. The check is the eval
`state` and `correctness` dimensions across the sampled scenarios, before vs after, with no
regression past threshold (Acceptance §7).

---

## Decisions for sign-off

### D1 — First-pass detection when there is no intent hint (candidate scope + prompt content)

**The decision.** On the pre-hook first pass `hint=''`. What flows does detection range over, and
what prompt does it use? The problem is real: `build_flow_prompt` looks up per-intent prompt text by
intent name, and an empty intent has no entry, so it raises.

**Current (for_experts.py:375-377).**

```python
def build_flow_prompt(user_text:str, intent:str, convo_history:str,
                       candidate_catalog:str, active_post:dict=None) -> str:
    prompt_fields = get_prompt(intent)          # intent='' → KeyError below
```

**Current (experts/__init__.py:30-31).**

```python
def get_prompt(intent:str) -> dict[str, str]:
    return PROMPTS[intent]                       # PROMPTS[''] raises KeyError
```

Note: `_flow_candidate_names` (nlu.py:362-366) *already* returns `list(FLOW_CATALOG)` when the
argument is falsy — that full-catalog branch exists today but is dead, because `predict` never
passed `None` (it always classified first). D1-A revives that existing branch; the only new
code is the prompt path below.

**D1-A (recommended) — full catalog + a generic (intent-agnostic) flow prompt.**
`_flow_candidate_names('')` returns `list(FLOW_CATALOG)` (all 18 flows). `build_flow_prompt` gains an
`intent:str=''` path that uses a shared generic instruction/rules/examples block instead of
`get_prompt(intent)`. Concrete draft added to `backend/prompts/experts/__init__.py`:

```python
GENERIC_FLOW_PROMPT = {
    'instructions': ('Choose the single flow that best matches what the user wants across ALL '
                     'intents. The candidate list spans every flow; the detected flow fixes the '
                     'intent, so do not pre-commit to one intent family.'),
    'rules': PRECEDENCE_NOTE,          # reuse the shared precedence note
    'examples': GENERIC_FLOW_EXAMPLES, # 5-6 cross-intent <positive_example> blocks, one per intent
}
def get_prompt(intent:str) -> dict[str, str]:
    return PROMPTS[intent] if intent else GENERIC_FLOW_PROMPT
```

- **Pro:** realizes the keystone — flow detection is authoritative and can switch intent in one
  pass (a Draft-active turn saying "publish it" surfaces `release` directly). Zero classify calls on
  the default path. This is the exact "pred vs active differs" failure class round 2.7 flagged.
- **Con:** new generic-prompt content; an 18-way choice can lose accuracy versus the per-intent
  4-5-way choice. Must be checked on the sampled scenarios (Acceptance §7).

**D1-B — keep the classify pre-pass (status quo narrowing).** Leave `predict` classifying first;
detection stays per-intent. `hint=''` never reaches `_detect_flow` because `predict` always passes a
classified intent.
- **Pro:** no new prompt; per-intent examples preserved; still switches intent (classify is fresh
  each turn).
- **Con:** keeps the unconditional call the locked decision says to drop — this is *not doing the
  round*. Rejected unless D1-A regresses on evals.

**D1-C — narrow by the active flow's intent when `hint=''`.** `_flow_candidate_names('')` returns
the active flow's intent's flows+edges (full catalog only on a cold open with no active flow), and
`build_flow_prompt` uses `get_prompt(active.intent)`.
- **Pro:** cheapest; reuses per-intent prompts; no classify call on active-post turns.
- **Con:** **cannot detect a cross-intent switch on an active post.** With `outline` active
  (edges `compose`/`refine`/`brainstorm`, all Draft), "publish it now" has no `release` candidate,
  so detection can't switch to Publish — it re-breaks the round-2.7 failure. Rejected.

**Recommendation: D1-A.** It is the only option that both removes the pre-pass and keeps
cross-intent switching, which is the point of the keystone. Ship it and check the sampled scenarios;
fall back to D1-B only if the sampled `state`/`correctness` scores regress past threshold.

### D2 — The `_intent_split` tie-break condition

**The decision.** When does `predict` spend the extra classify + re-detect? The plan gives
`len(intents) > 1 and confidence < confidence_min`. Under D1-A the voters range over all flows, so
`len(intents) > 1` is almost always true, which makes the confidence clause the real trigger.

**D2-A (recommended) — ship the plan's condition verbatim.**
`return len(intents) > 1 and detection['confidence'] < self.ambiguity.confidence_min`.
- **Pro:** matches the plan; simplest; a low-confidence detection escalates to classify+narrow — the
  System-2 fallback.
- **Con:** the `len(intents) > 1` clause is near-always true under D1-A, so in practice the trigger
  is `confidence < confidence_min`. Slightly misleading to read, but harmless.

**D2-B — escalate on `confidence < confidence_min` only.** Drop the intent-span clause.
- **Pro:** one honest condition; no near-dead clause.
- **Con:** escalates even when the top-2 are same-intent siblings (e.g. `outline` vs `compose`),
  where a coarse classify cannot disambiguate — a wasted pair of calls.

**D2-C — escalate on a small top-2 confidence gap across differing intents.**
`top2 differ in intent AND (conf[0] - conf[1]) < margin`, independent of absolute confidence.
- **Pro:** targets the real two-intent tie that classify actually resolves.
- **Con:** needs a new `margin` threshold in config; more logic for a round meant to be small.

**Recommendation: D2-A.** Keep the round small and match the plan. If telemetry later shows
escalation firing on same-intent ties, revisit with D2-C. Note in code that the span clause is
usually true under D1-A.

### D3 — Threading the `hint` parameter through `understand` / `think`

**The decision.** The plan's target signature is `understand(op, ..., hint='')` →
`think(text, payload, hint='')` → `predict(text, hint)`. But no caller passes a non-empty `hint`
this round: the pre-hook first pass is always hint='', and PEX's System-1 sense (§3.1.2) is prose
only — it is not fed back into NLU as a code value, and `contemplate` does not go through `predict`.

**D3-A (recommended) — add `hint` only where it is used now.**
`predict`, `_detect_flow`, `_flow_candidate_names`, `_detect_flow_prompt` gain `hint`. `understand`
and `think` keep today's signatures. `predict` sets `hint` internally on the tie-break re-detect.
- **Pro:** no speculative plumbing (project YAGNI rule); smallest diff; every added parameter has a
  live caller.
- **Con:** deviates from the plan's literal `understand(..., hint='')` signature; a future round that
  wires a PEX→`think` re-detection adds the `understand`/`think` param then.

**D3-B — thread `hint` fully now, per the plan's signature.** Add `hint=''` to `understand` and
`think` even though nothing passes it.
- **Pro:** matches the plan's stated end-state; ready for the re-detection caller.
- **Con:** a parameter nothing passes — dead plumbing this round, which the repo rules prohibit.

**D3-C — thread `hint` AND wire a real caller.** Have PEX re-invoke
`understand(op='think', hint=<coarse sense>)` on a continuing turn so the hint does work now.
- **Pro:** the hint narrows a real re-detection.
- **Con:** out of §3.1 scope — that is a PEX behavior change (Round 5 / Workflow Planner territory),
  risks the parallel-think design, and was not asked for.

**Recommendation: D3-A.** Add the parameter only on the internal detection methods that consume it.
Flag the deviation from the plan's literal signature for sign-off.

---

## Simplifications and removals called out

1. **Do not add `_intent_candidates`** (plan 3.1.3). It duplicates the existing
   `_flow_candidate_names` per-intent branch (nlu.py:362-366). Keep one method, `_flow_candidate_names(hint='')`.
2. **No belief-path rewrite.** `_write_belief`/`validate` already derive `pred_intent` from the
   detected flow. 3.1.1 is a one-line deletion (the pre-pass call) plus the `_intent_split` guard —
   not a new belief write.
3. **No new edge helper.** Reuse `_get_edge_flows_for_intent` (nlu.py:22-28).
4. **Net effect on the default path: one fewer LLM call per turn** (the classify pre-pass), traded
   for a wider candidate list (D1-A). The tie-break adds calls back only on low-confidence
   cross-intent turns.
5. **`understand`/`think` untouched** under D3-A — smaller diff than the plan implies.

---

## Test plan

Offline model unit tests run with no live LLM (the free tier), cwd = `assistants/Hugo`. Live evals
run only in the trace and eval checks the orchestrator runs after the build (feedback: builders run
no live evals).

### Model unit tests — `utils/evaluation_suite/_tests/nlu_unit_tests.py`

The existing detection tests at nlu_unit_tests.py:71-112 call `_detect_flow('hello', intent='...')`.
Rename those keyword args to `hint='...'` (mechanical). New tests below (add near `TestEnsembleVoting`):

| Test name | Setup | Expected result |
|---|---|---|
| `test_predict_skips_classify_on_confident_detection` | Spy/patch `_classify_intent`; mock `_detect_flow` to return a single-intent, high-confidence detection (conf ≥ confidence_min). Call `predict('draft me an outline')`. | `_classify_intent` **not called**; returned `flow_name` matches the mocked detection. |
| `test_predict_escalates_on_low_conf_cross_intent` | Mock `_detect_flow` first call → low-conf detection whose `pred_flows` span 2 intents; patch `_classify_intent` → `'Draft'`; second `_detect_flow` call → a Draft detection. Call `predict(...)`. | `_classify_intent` **called once**; `_detect_flow` called **twice** (second with `hint='Draft'`); result is the second detection. |
| `test_intent_split_true_when_flows_span_intents_and_low_conf` | Build `detection` with `pred_flows` from `outline` (Draft) + `find` (Research), `confidence=0.4`. | `_intent_split(detection) is True`. |
| `test_intent_split_false_when_confident` | Same cross-intent `pred_flows`, `confidence=0.9`. | `_intent_split(detection) is False`. |
| `test_intent_split_false_when_single_intent` | `pred_flows` all Draft flows, `confidence=0.4`. | `_intent_split(detection) is False`. |
| `test_classify_intent_still_callable` | Mock engineer to return `{'reasoning':..., 'intent':'Revise'}`. Call `_classify_intent('polish the intro')`. | returns `'Revise'` — the callable survives for tie-break + contemplate. |
| `test_candidate_names_empty_hint_is_full_catalog` (D1-A) | `_flow_candidate_names('')`. | equals `list(FLOW_CATALOG)` (18 flows). |
| `test_candidate_names_hint_narrows_to_intent` | `_flow_candidate_names('Draft')`. | contains `outline`,`compose`,`refine`,`brainstorm` + edge flows; excludes `release`. |

Under D1-A add one prompt test (in `nlu_unit_tests.py` or the prompt test group):

| `test_generic_flow_prompt_used_when_no_hint` | `build_flow_prompt('publish it', '', history, catalog)` runs without raising; the prompt string contains the generic instruction text and does not require a per-intent key. | no `KeyError`; the rendered prompt is non-empty. |

### Trace check — `utils/evaluation_suite/_traces/run_traces.py`

`python utils/evaluation_suite/_traces/run_traces.py --ids B01.C01,B03.C05,B01.C08` before and after
the change. Expected: turns complete; no crash from an empty-hint prompt path; mean turn seconds
within baseline +20% (the trace latency check). Detection cost should not rise materially despite the
wider candidate list (one classify call removed offsets the larger prompt).

### E2E eval check — `utils/evaluation_suite/_evals/run_evals.py`

Sampled from the existing 96-convo corpus (`datasets/train.jsonl`) — not invented. The `state`
dimension (run_evals.py:113-116) scores `pred_flows[0]['flow_name'] == expected_flow`, which is the
authoritative-write check for §3.1; `correctness` scores tool match.

| Scenario id | Why it is in the sample | Scored dimension → expected |
|---|---|---|
| `B01.C01` | find → outline → compose → release: three intents in one session, each turn a clean single-flow switch | `state` per-turn detects the right flow at each intent boundary; no regression vs pre-change |
| `B03.C05` | Draft/Publish/Research/Revise all present — the hardest cross-intent switching | `state` holds; `correctness` holds |
| `B02.C15` | Publish/Research/Revise switching mid-session | `state` holds |
| `B01.C08` | multi-flow **plan** turn (stack length > 1) + Converse/Revise/Publish | `planning` (criterion 7) holds; `completion` holds |
| `B03.C11` | second plan scenario | `planning` holds |
| `B01.C10` | carries an `ambiguity` turn → low-confidence path that may trip `_intent_split` | `ambiguity` (criterion 6) still declared; `completion` not worse |
| `B02.C06` | second ambiguity scenario | `ambiguity` holds |
| `B01.C14` | Draft/Research/Revise continuation on an active post (same-intent turns must NOT regress) | `state`/`correctness` no regression |

Rule: run these 8 before and after; the mean `state` and `correctness` must not drop past the suite
threshold, and `completion` must not regress. This is the round plan's "10 approved trajectories"
mapped onto the suite's 8-scenario check (the corpus has no separate 10-trajectory set; the feedback
doctrine is ~8 scenarios per round).

---

## Acceptance criteria

Every criterion maps to a named test above with an expected result.

1. **Pre-pass removed.** `predict` makes no `_classify_intent` call on a confident single-intent
   detection → `test_predict_skips_classify_on_confident_detection`.
2. **Tie-break retained.** A low-confidence cross-intent detection escalates to classify + narrowed
   re-detect → `test_predict_escalates_on_low_conf_cross_intent`; the split logic is correct across
   the three `test_intent_split_*` cases.
3. **`_classify_intent` still callable** → `test_classify_intent_still_callable`.
4. **Empty-hint detection works** (no `get_prompt('')` crash) → `test_candidate_names_empty_hint_is_full_catalog`
   + `test_generic_flow_prompt_used_when_no_hint` (D1-A).
5. **Hint narrows** → `test_candidate_names_hint_narrows_to_intent`.
6. **Prompt guidance rewritten.** `INTENT_TAXONOMY` no longer contains "ALREADY classified" /
   "don't re-classify"; it contains the Plan/Clarify bias language →
   grep `for_orchestrator.py` returns nothing for `ALREADY classified` and finds the new bias text.
7. **No detection regression** on the 8 sampled scenarios: mean `state` and `correctness` do not
   drop past threshold, `completion` no worse → E2E eval check before/after.
8. **Free suite green, zero skips** from `assistants/Hugo` cwd: `nlu_unit_tests.py`,
   `model_tests.py`, `pex_unit_tests.py`, `mem_unit_tests.py`.
9. **Net simplification on the default path:** one fewer LLM call per turn (the classify pre-pass),
   and no `_intent_candidates` helper added.

## Out of scope (do not build here)

§3.2 ambiguity binding, §3.3 scratchpad contract, §3.4 flag cleanup, and the S-1 escalating
ensemble. The `_intent_split` tie-break is the single-round base case of S-1; the full ladder is a
later round.
