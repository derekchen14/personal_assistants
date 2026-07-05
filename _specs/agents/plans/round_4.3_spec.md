# Round 4.3 Spec — Exemplar raise + cap on repeated read actions

Source: `_specs/_review/step_4_pex.md` §4.3 (8b). Traces to the live-gate failure buckets:
(a) NLU flow-**detection** errors, (b) repeated read-only tool calls sinking `tool_match` and latency.

## Baselines (8-scenario gate: B01.C01, B01.C04, B02.C01, B02.C02, B03.C01, B04.C01, B05.C01, B06.C01)
- completion **0.5152** · tool_match **0.0864** · mean turn **12.4 s**

## New concepts
- **One new config key** `limits.max_reads: 3` — the per-turn cap on the orchestrator's direct
  read-only domain-tool calls. Example added to `shared/shared_defaults.yaml`:
  ```yaml
  limits:
    max_reads: 3   # per-turn cap on direct read-only domain-tool calls (find_posts, read_metadata, ...)
  ```
- **No new classes, files, fields, or terms.** Exemplars are authored into existing `.md`/`.py`
  prompt files. The read counter reuses the existing per-turn instance-flag pattern already in
  PEX (`self._injected`).

---

## Part A — PEX skill exemplar raise (§4.3, priority propose → 2-count → 3-count)

Verified current counts (opening `### Example` blocks per file under `prompts/pex/skills/`):
propose **1**; chat/cite/compose/promote/release/schedule **2**; audit/brainstorm/browse/find/
outline/summarize **3**; compare/rework **4**; refine/write **5**.

House shape (studied from `write.md`, `refine.md`): each exemplar is
`### Example N: <descriptor>` → a `Resolved Details:` block (Source + "User asked:") → a numbered
`Trajectory:` of real tool calls → an optional `Final reply:`. Exemplars span the operation space
of the skill: a direct act, a soft-direction → `handle_ambiguity(level='confirmation')`, an
ambiguity/error fallback, a fallback to a sibling skill via `call_flow_stack(action='fallback')`,
and (where relevant) a scratchpad-informed act. `write.md` demonstrates all five — use it as the
template for what the 5 slots should cover.

### DECISION 1 — target count per skill
**Recommendation: uniform floor of 5** for the 13 priority skills (propose + the six 2-count +
the six 3-count). Leave compare(4)/rework(4)/refine(5)/write(5) untouched this round.

New exemplars to author: propose +4, each 2-count skill +3 (×6 = 18), each 3-count skill +2
(×6 = 12) = **34 exemplars**.

- **Pro:** matches the two best-exemplared skills the team already converged on (write/refine = 5),
  so every skill covers its full operation space (act / confirm / fallback / ambiguity). Bounded
  authoring load that respects the output budget and eval-speed doctrine. Concentrates effort where
  counts are thinnest.
- **Con:** below the style-guide's stated 7–10; a later round may revisit if traces isolate skill
  **trajectory** (not detection) as the limiter.
- **Why stop at 5, not 7–10:** the gate's binding constraints are detection (Part C) and tool
  repeated reads (Part B), not skill-trajectory depth. Pushing 17 skills to 7 is ~70 exemplars of authoring
  against a bottleneck that sits elsewhere — gold-plating. Revisit toward 7–10 when a trace gate
  shows trajectory scores, not detection, capping completion.

**Alternative 1 — push the 13 priority skills to 7** (the guide's low end). Pro: hits the
documented target's floor. Con: ~60 exemplars; churns files whose depth is not the current
bottleneck.
**Alternative 2 — raise only propose (→5), defer the rest.** Pro: smallest diff. Con: leaves the
2-count skills one exemplar above the worst; ignores §4.3's explicit 3-group priority.

### Authoring rules (NON-NEGOTIABLE — apply to every new exemplar)
- No **"Kitty Hawk"** anywhere (held-out manual test topic).
- Multi-word realistic post titles; rotate topics across exemplars (no topic reuse within a skill).
- Short realistic user utterances (10–40 words, implicit, anaphora); **no em-dashes** in utterances.
- Each exemplar shows the **agentic shape** — a tool call or a prose reply — never a JSON blob.
- Match the exact `write.md` block structure (Resolved Details → Trajectory → optional Final reply).

---

## Part B — Cap on repeated read actions (bucket b)

**Problem.** The orchestrator calls `find_posts` 3–9× and `read_metadata`/`read_section` 5–8× in
one turn. The dedupe guard (`pex.py:434`) only blocks **identical consecutive** successful calls,
so varied-args repeats pass. The prompt rule ("at most ONE such lookup per turn",
`for_orchestrator.py:114`) is ignored by the model.

### DECISION 2 — mechanism
**Recommendation: a per-turn counter of read-only domain-tool calls, checked in `_guarded_call`,
converting the (N+1)th into a corrective tool error.** Cap value `N = limits.max_reads = 3`.

The counter reuses the existing per-turn instance-flag pattern (`self._injected`): add
`self._reads = 0`, reset at the top of `_orchestrate` (next to where the turn loop is set up), and
increment/check inside `_guarded_call` — the established home for the two existing guards
(hallucinated name, identical-consecutive). No new params on `_guarded_call`.

Pseudo-code (`pex.py`):
```python
# __init__ — read the cap alongside the other limits
self.max_reads = config['limits']['max_reads']

# _orchestrate — reset the per-turn read counter before the round loop
self._reads = 0
for round_idx in range(self.max_rounds):
    ...

# _guarded_call — third guard, after the invalid-name / duplicate-call guards
elif tool_use.name in READ_ONLY_DOMAIN_TOOLS and self._reads >= self.max_reads:
    result = {'_success': False, '_error': 'read_cap',
              '_message': f'Already used {self.max_reads} read-only lookups this turn. '
                          'Stack on and activate a flow, or respond to the user.'}
else:
    result = self._dispatch_tool(tool_use.name, dict(tool_use.input or {}))
    if tool_use.name in READ_ONLY_DOMAIN_TOOLS and result['_success']:
        self._reads += 1
    if '_success' not in result:
        result['_success'] = result.get('status') == 'success'
```
Count only **successful** read-only calls toward the cap, mirroring the dedupe guard's
"only fires on a prior success" logic — a failed lookup the model legitimately retries should not
burn the budget. Total cap across all read-only tools (not per-tool), because latency is bounded by
the total, and a single knob is simpler.

- **Pro:** directly bounds the repeated reads and the latency it drives; one config knob; the corrective
  error steers the model to stack-and-activate (the intended behavior). Sits with the other guards.
- **Con:** a rare pre-stack flow that legitimately needs 4 distinct lookups gets nudged to stack
  early. Mitigated: within-flow reads happen in the flow's own `tool_call` loop (capped separately
  by `max_tool_calls`/`extended_tool_calls`), NOT the orchestrator loop, so this cap only bounds the
  orchestrator's direct pre-stack peeks — which the prompt already says should be ~1.

**Why N = 3, not 1:** the prompt's "one" is the ideal, but `find_posts` (get an id) → `read_metadata`
(get the outline) is a plausible 2-step before stacking. N = 3 leaves one call of margin and still
kills every observed run of repeated reads (all ≥ 5). Present the strict N = 1 below.

**Alternative 1 — widen the dedupe guard to same-TOOL repeats.** Block the 2nd call to any given
read-only tool regardless of args. Pro: tiniest diff (one condition in `_guarded_call`, no counter,
no config). Con: per-tool not total — `find_posts`+`read_metadata`+`read_section`+`search_notes`
once each = 4 calls still pass; and it blocks a legitimate "read section A, then section B" pair.
**Alternative 2 — prompt-only (strengthen `for_orchestrator.py`).** Pro: zero code. Con: the model
already ignores the existing "at most ONE" rule; no reason a reworded rule binds where the first
did not. Rejected as the primary fix; a one-line prompt tweak may accompany the counter.
**Alternative 3 — strict N = 1.** Pro: matches the prompt's literal rule. Con: breaks the plausible
find→read 2-step; higher risk of a false corrective error mid-legit-lookup.

Cap value lives in the existing `limits` section of `shared/shared_defaults.yaml` (the section PEX
already reads via `config['limits'][...]`).

---

## Part C — DECISION 3: does NLU **detection** need exemplar work? YES — fold it in.

The gate's binding failure bucket (a) is flow **detection** (e.g. detecting `rework` where the
label says `write`). §4.3 as written only covers PEX skill exemplars, which are a **trajectory**
surface, not a detection surface — raising them cannot fix bucket (a). Verified NLU exemplar state:

- **Intent stage** (`for_experts.py` `INTENT_EXAMPLES`): **21** inline exemplars — healthy, no work.
- **Flow-detection stage** (`experts/<intent>_flows.py`, `EXAMPLES`): research **4**, draft **4**,
  revise **4**, publish **3**, converse **2** — one exemplar per flow, no boundary/contrast cases.

The `write`/`rework` pair already has one exemplar each in `revise_flows.py` ("whole post needs
work" → rework; "tighten the phrasing" → write), yet the model still confuses them. The gap is the
**ambiguous middle** — medium-scope edits that could read as either — which no exemplar pins.

**Work item C (in scope this round):** raise flow-detection examples to a **floor of 6 per intent**,
authored as **contrastive boundary cases** on the confusable pairs, not filler. Priority:
- `revise_flows.py` and `draft_flows.py`: add exemplars that pin the `write` (single-section /
  sentence-level) vs `rework` (multi-section / post-level argument) boundary, and the
  `refine`/`compose`/`write` (Draft) boundary, using medium-scope utterances that force the call.
- `publish_flows.py` (3→6) and `converse_flows.py` (2→6): bring to the floor with in-intent + edge
  cases.
- research (4) and draft/revise (4): top up to 6, prioritizing edge flows into adjacent intents.

New exemplars: ~ (6-4)×3 + (6-3) + (6-2) = 6 + 3 + 4 = **13**. Same authoring rules as Part A
(no Kitty Hawk, multi-word titles, short utterances, no em-dashes, rotate topics). Each stays the
existing `<positive_example>` / `<edge_case>` block shape with a `reasoning` + `flow_name` +
`confidence` JSON output.

- **Pro:** attacks the gate's actual binding constraint; contrastive pairs are the highest-leverage
  exemplar type for a boundary the model keeps crossing.
- **Con:** more surface than a pure §4.3 read; but §4.3's PEX-only scope cannot move completion
  while detection is the ceiling, so this is the load-bearing part of the round.
- **Alternative — defer detection to a later round.** Pro: keeps the round to §4.3's literal PEX
  scope. Con: leaves completion pinned by bucket (a); the PEX exemplar raise alone would show
  little gate movement, making the round look inert. **Rejected.**

---

## Verification plan

Every acceptance criterion maps to a named check with an expected result.

### 1. Free suite (fast, deterministic — must stay green)
- `pytest` under `assistants/Hugo` (cwd + `sys.path[0]` = assistant dir per the test-cwd note).
- **AC-1 (prompt integrity):** the slot/flow/skill prompts still build. Expected: all prompt-build
  and NLU schema tests pass; no exemplar introduces an em-dash or the string "Kitty Hawk"
  (grep check over the touched `.md`/`.py` files, expected 0 hits).
- **AC-2 (config):** PEX reads `limits.max_reads`; `config['limits']['max_reads'] == 3`. Expected:
  PEX constructs without KeyError; a unit assertion on the loaded value passes.

### 2. Model tests (relevance)
- **AC-3 (read cap):** a unit test drives `_guarded_call` with 4 successful read-only calls in one
  simulated turn (reset `self._reads = 0`, then call `find_posts`/`read_metadata` with varied args
  ×4). Expected: calls 1–3 dispatch; call 4 returns `{'_success': False, '_error': 'read_cap'}`
  without dispatching. A failed read-only call does **not** increment (retry stays allowed).
- **AC-4 (detection boundary):** a model unit test over the new `write`/`rework` contrastive
  utterances asserts the flow-detection stage returns the labeled flow. Expected: the medium-scope
  boundary utterances resolve to their intended flow. (Detection is a behavior surface — diff
  detection scores before/after per §4.3's "diff detection/trajectory scores after.")

### 3. Live 8-scenario gate (the round's success bar)
Run B01.C01, B01.C04, B02.C01, B02.C02, B03.C01, B04.C01, B05.C01, B06.C01.
- **AC-5 (tool_match up):** the read cap must lift tool_match off **0.0864** and pull mean turn
  under the **12.4 s** baseline (fewer read-only calls per turn). Expected: tool_match rises,
  mean turn drops; neither completion nor correctness regresses.
- **AC-6 (completion up):** the detection exemplars (Part C) must not regress completion **0.5152**
  and should lift it where bucket-(a) mis-detections gated a scenario. Expected: completion ≥ 0.5152,
  trending up on the write/rework scenarios.
- **AC-7 (no regression):** ambiguity, planning, response, and state dimensions hold at or above
  their current values.

Report the before/after delta on completion, tool_match, and mean turn as the round's verdict.

## Simplification / removal opportunities
- The prompt rule "at most ONE such lookup per turn" in `for_orchestrator.py` becomes partly
  enforced by code once the cap lands; keep the prose (it still guides the model) but it no longer
  carries the whole burden — no deletion needed.
- Do **not** touch compare/rework/refine/write skill exemplars this round (already ≥4/5); adding to
  them is churn against a non-bottleneck.
