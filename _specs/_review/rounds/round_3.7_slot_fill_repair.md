# Round 3.7 (was fix 3b) — Repair/retry a slot-fill response that is missing the `slots` key

Status: **done (2026-07-08).** Decision B shipped earlier as a plain one-retry loop (no
corrective-nudge line, which is fine). Decision A shipped 2026-07-08: `_parse_json`'s fallback regex is
now outermost-greedy (`r'\{.*\}'`), so it can only recover the full object (prose-wrapped JSON) and
returns None on truncation — never a nested fragment. The `_fill_slots` retry loop catches the
resulting ValueError from the engineer's schema path as one more retry-once case. Tests:
`TestParseJson` (pex) + two `_fill_slots` retry tests (nlu).
Discovered by the 2026-07-03 evaluation-suite run.
Owner module: **NLU** (`_fill_slots`) + **PromptEngineer** (JSON parse fallback). See also [[round_3_nlu.md]],
[[round_2.10_orchestrator_activation.md]].

---

## What is being changed

When the slot-fill LLM call returns an object with no top-level `slots` key, NLU currently logs a warning
and **returns with every slot unfilled** (`backend/modules/nlu.py:392-397`). This silent give-up leaves
the flow with nothing to act on. The change: **do not silently drop the fill** — re-issue the call once
with a corrective instruction, and fix the underlying parser footgun that produces the malformed object in
the first place.

## Background and motivation

### The symptom

```
[fill_slots] schema violation flow=outline payload={'post': 'The Case for Sleepers Over Hotels'}
[fill_slots] convo_history=
  User: Pull up my posts about sleeper trains, please.
  Agent: Found three: 'The Case for Sleepers Over Hotels', ...
  User: sketch a structure from the draft, lead with comfort then cost
[fill_slots] filled-state: {'source': False, 'sections': False, 'topic': False, 'depth': False, 'proposals': False}
```
The returned object was `{'post': 'The Case for Sleepers Over Hotels'}` — no `slots`, no `reasoning`. NLU
hit the guard at `nlu.py:393` and returned, so the `outline` flow ran with **all five slots empty**.

### Root cause (two layers)

The schema is strict — `_fill_slots_schema` requires `reasoning` + `slots` at the top level with
`additionalProperties: False` (`nlu.py:62-72`). So a *conforming* response cannot look like
`{'post': ...}`. The malformed object comes from the **parser fallback**, not the model:

- `engineer(prompt, 'fill_slots', schema=...)` calls `apply_guardrails(text, format='json')` →
  `_parse_json` (`backend/components/prompt_engineer.py:166`, `627-638`).
- `_parse_json` first tries `json.loads(text)`. If that raises (truncated or otherwise malformed text —
  `fill_slots` runs at `max_tokens=2048` and a long `reasoning` can get cut off mid-string), it falls back
  to a regex: `re.search(r'\{[^{}]*\}', text, re.DOTALL)` and returns the first **innermost, brace-free**
  object it finds (`prompt_engineer.py:632-635`).
- In `{"reasoning": "...", "slots": {"source": {"post": "The Case..."}}}`, the first brace-free `{...}` is
  the deepest one: `{"post": "The Case..."}`. So on any parse failure the fallback silently returns a
  **nested fragment** — exactly the `{'post': ...}` we saw, which of course lacks `slots`.

So: a truncated/garbled structured response → `json.loads` fails → the regex grabs a deep fragment → the
fragment has no `slots` → NLU gives up → the flow gets no slots. This feeds directly into Fix 1's
"terminal tool never fires": a Draft/Revise flow with empty slots has nothing to generate from.

### Why it matters

- Slot-filling is the join between NLU detection and PEX action. When it silently yields nothing, the
  detected flow is hollow — the user asked to "sketch a structure" and the outline flow received no source,
  no sections, no depth.
- The failure is **silent** (a log line, then normal control flow), which is exactly the kind of ghost the
  repo's philosophy warns against (`CLAUDE.md` — loud failures over silent fallbacks).

## Connected files

| File | Role |
|---|---|
| `backend/modules/nlu.py:388-399` | `_fill_slots` Phase 3 — the call, the `'slots' not in pred_slots` guard, the silent return |
| `backend/modules/nlu.py:59-72` | `_fill_slots_schema` — the strict shape the response should obey |
| `backend/components/prompt_engineer.py:148-171` | `__call__` — schema-constrained path, `apply_guardrails` |
| `backend/components/prompt_engineer.py:627-638` | `_parse_json` — the regex fallback that grabs a nested fragment |
| `backend/components/prompt_engineer.py:610-617` | `_strip_nulls` — applied to `pred_slots['slots']` after the guard |

## Decision A — fix the parser footgun (do this regardless)

The regex fallback `\{[^{}]*\}` returning a **deep fragment** is wrong for schema-constrained calls: a
partial/garbled JSON should fail loudly (so we retry), not resolve to a random inner object that happens to
parse. Options:

1. **Make the fallback outermost-greedy, not innermost.** Match the whole `{...}` span
   (`r'\{.*\}'`, DOTALL) so a fragment is only ever the full object, never a nested slice. On genuine
   truncation this still fails to parse → returns `None` → caller can retry. Smallest change.
2. **Drop the regex fallback for schema calls entirely.** When a `schema` was supplied, `__call__` should
   trust `json.loads` and return `None` on failure (the schema exists precisely to guarantee shape). Keep
   the lenient regex only for schemaless `format='json'` callers. Cleanest separation.

- **Recommendation:** Option 2 for the schema path (a schema-constrained response that won't `json.loads`
  is a real failure, not something to salvage by fragment-grabbing), with Option 1 as the fallback for
  legacy schemaless callers. Either way, `_parse_json` must never return a *nested* fragment.
- **Pros:** removes the silent-wrong-data path at the source; benefits every schema-constrained call, not
  just `fill_slots`. **Cons:** a schemaless caller that today accidentally relies on fragment extraction
  could change behavior — grep callers of `apply_guardrails(format='json')` first; there are few.

## Decision B — what `_fill_slots` does on a bad/empty response

Even with A, a call can still legitimately fail (overloaded model, real truncation). Today NLU returns
silently. Choices:

1. **Retry once with a corrective nudge (recommended).** Re-issue the same call, appending one line to the
   prompt: "Return a single JSON object with a top-level `slots` key holding every slot; do not nest slot
   values at the top level." Reuses the existing `self.engineer(...)` call — no new mechanism, just a
   second invocation guarded by a boolean so it runs at most once.
   ```python
   pred_slots = self.engineer(prompt, 'fill_slots', max_tokens=2048, schema=_fill_slots_schema(flow))
   if 'slots' not in pred_slots:
       pred_slots = self.engineer(prompt + '\n\n' + _SLOTS_KEY_REMINDER, 'fill_slots',
                                  max_tokens=2048, schema=_fill_slots_schema(flow))
   if 'slots' not in pred_slots:
       log.warning(...); return           # keep the existing give-up as the FINAL resort only
   ```
   - Pros: recovers the common transient case; leaves detected flows filled; minimal code. Cons: one extra
     paid call on the failure path (rare); bump `max_tokens` (e.g. 3072) if truncation is the cause.
2. **Repair the fragment in place.** If the returned object's keys are all slot names or entity parts, wrap
   it as `{'slots': {...}}`. Rejected: fragile and guessy — the observed `{'post': ...}` is a *piece* of the
   `source` value, not a slot map, so wrapping it produces wrong data. Repair can't reconstruct what
   truncation destroyed.
3. **Raise instead of returning.** Loud, matches repo philosophy, but crashes the whole turn for a
   recoverable hiccup — worse UX than a bounded retry. Keep raising only if the retry ALSO fails and you
   decide a hollow flow is worse than a fallback message (team call; default is the current soft return).

- **Recommendation:** B1 (retry once) layered on A. The retry handles transient failures; A stops the
  parser from manufacturing the failure in the first place. Keep the existing log+return as the final
  resort after the retry.

### Alternatives considered

- **Raise `max_tokens` only.** If truncation is the dominant cause, a bigger budget alone reduces the
  failure — but it doesn't fix the parser returning a nested fragment when truncation *does* happen, so it
  is a mitigation, not the fix. Do it alongside A+B1, not instead.
- **Validate the parsed object against the schema in `__call__`** (jsonschema). Heavier dependency and
  broader blast radius than this bug needs; the `'slots' not in pred_slots` check is a sufficient, targeted
  guard. Revisit only if malformed structured output turns out to be widespread across tasks.

## New concepts introduced

**None.** A is a bug fix to an existing parser. B1 is a second call through the existing
`self.engineer(...)` entry, gated by a boolean — no retry framework, no new component, no new state. The
`_SLOTS_KEY_REMINDER` is a module-level string constant beside the existing prompt constants.

## How to verify

1. **Unit test the parser (deterministic, free)** in `pex_unit_tests.py` (PromptEngineer is PEX-owned):
   - `_parse_json('{"reasoning": "x", "slots": {"source": {"post": "T"}}}')` returns the FULL object
     (`'slots' in result`), never the nested `{"post": "T"}`.
   - A truncated string (`'{"reasoning": "aaaa...'` cut mid-value) returns `None`, not a fragment.
2. **Unit test the guard (deterministic, free)** in `nlu_unit_tests.py`: stub the engineer to return
   `{'post': 'T'}` once then a well-formed `{'reasoning': .., 'slots': {..}}`; assert `_fill_slots` retries
   and the flow ends up filled. A stub that returns the bad shape twice → the flow stays unfilled and the
   warning is logged (final-resort path intact). No live calls.
3. **Live, bounded:** rerun the outline scenario that failed —
   `python utils/evals/run_evals.py --ids B01.C01` — and confirm no `[fill_slots] schema violation` line,
   and the outline turn's `source`/`sections` come back filled (visible in the flow's slot state / the
   `generate_outline` firing with real inputs).
4. **Model tier:** `python utils/tests/model_tests.py --module nlu` on the standard 8 shows no
   `schema violation` warnings.
5. Regression: `python utils/evals/run_evaluation_suite.py --tests` stays green (208).
