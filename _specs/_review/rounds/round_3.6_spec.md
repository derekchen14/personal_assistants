# Round 3.6 — TypeSafe Flow Detection

Maps to **Master Plan · Round 3 (NLU)**. Priority: second among the NLU upgrades, after the async NLU
round. Proposal spec — nothing here is built yet except the eval-side pieces listed under "What exists".

**Why TypeSafe fits flow detection.** Detection is pick-one-of-N — exactly TypeSafe's **Choice**
question. One fast non-LLM call replaces three medium LLM voters on most turns, there is no JSON to
parse out of a prose reply (the runaway/truncation failure class disappears), and the confidence is
**calibrated** — derived from a real probability distribution over the options. The voter ensemble
exists precisely because LLMs cannot self-report confidence; agreement scoring approximates what
TypeSafe measures directly.

**Relation to async NLU.** Complementary: TypeSafe as detection's round zero shortens the NLU pass
from ~3-5s of parallel LLM calls toward sub-second on confident turns, so the async join points almost
never block. Each round strengthens the other's case.

---

## What exists today

- **`utils/evaluation_suite/_tests/typesafe_helpers.py`** — `predict_flow(convo_history, user_text,
  active_post, ontology, examples) -> (flow_name, confidence)`. One Choice call to
  `https://api.typesafe.ai/v1/systemone` (model `speed_latest`, key from `TYPESAFE_API_KEY`);
  `criteria` = the 18-flow menu with `FLOW_ONTOLOGY` descriptions as rubrics; the `document` carries
  ontology / exemplars / conversation / current turn / active-post title as separate fields.
- **`model_tests.py --provider typesafe`** — the scoring path already imports `predict_flow`, so the
  accuracy measurement (3.6.1) needs zero new code.
- **`prompt_engineer.py:46`** — `FAMILY_TIERS['typesafe'] = ('noul', 'score', 'choice')` is registered,
  but the `match family:` dispatches (`:131`, `:169`, `:197`) have no typesafe branch — the family is a
  placeholder in the production path.
- **Docs gap:** the helper's docstring points at `utils/typesafe/SKILL.md`, which is not on disk.
  Restore it (or repoint) as part of this round.

## 3.6.1 — Measurement gate (do this first, before any wiring)

Run the existing scoring path against the corpus and compare to the LLM baseline:

```
python utils/evaluation_suite/_tests/model_tests.py --module nlu --provider typesafe
```

Baseline to beat: **87.5%** flow-detection accuracy (28/32, single teacher-forced LLM call, recorded in
the eval-system plan). Decision rule:

| Result | Role TypeSafe gets |
|---|---|
| ≥ baseline | **Round zero** of detection (3.6.2) — the headline design |
| within ~5 points below | **Ensemble voter** (3.6.5) — calibration unused, but a cheap fourth opinion |
| far below | Stop; record the number here; keep it as an eval-side comparison only |

Also record per-case confidence from the run: the accept threshold (3.6.2) is picked from this data —
the lowest cutoff where the accepted subset's accuracy is at or above the full ensemble's accuracy.

## 3.6.2 — Round zero in `_detect_flow`

`NLU._detect_flow` (`nlu.py:418`) currently runs the two-round agreement ladder: med trio (or PEX seed
+ 2 off-family meds on Continue turns) → high pair when confidence lands under
`ambiguity_handler.confidence_min`. TypeSafe becomes the round before round one:

```python
# nlu.py — _detect_flow, before building votes
def _detect_flow(self, user_text:str, hint:str=''):
    candidate_names = self._flow_candidate_names(hint)
    accept_min = self.config['thresholds']['typesafe_accept_min']   # 0.0 disables round zero
    if accept_min:
        choice, confidence = self._typesafe_vote(user_text, hint, candidate_names)
        if choice and confidence >= accept_min:
            return {'flow_name': choice, 'confidence': confidence,
                    'pred_flows': [{'flow_name': choice, 'confidence': confidence, 'votes': 1}]}
    ...  # below threshold, call failed, or disabled → today's ladder, unchanged
```

- **Candidate narrowing composes for free.** The Choice `criteria` dict is built from
  `candidate_names`, not the full ontology — so a Continue turn's narrowed menu (active flow + its
  edge flows) and an intent-hint menu both work with no special handling. TypeSafe has no model
  family, so it never collides with PEX's seed-vote family logic; the PEX seed only matters when we
  fall through to the ensemble.
- **Confidence semantics stay coherent.** When round zero accepts, `state.confidence` carries a
  calibrated probability; when the ensemble decides, it carries the agreement score, exactly as
  today. Because `typesafe_accept_min` sits above `confidence_min`, an accepted round zero can never
  trip `needs_clarification` — the two scales never mix below the threshold.
- **Config:** `typesafe_accept_min` under the existing `thresholds` block (start at **0.85**, then
  tune from the 3.6.1 per-case data). `0.0` disables round zero — no new flag, no env var.
- **`pred_flows` depth:** open question 1 below decides whether the ranking has one entry or the
  API's full distribution.

## 3.6.3 — Where the client lives (decision)

The typed-question call does not fit `PromptEngineer.__call__`'s prompt+schema contract, and
flattening the document fields into one prompt string would discard structure the API wants. Two
homes:

- **(a) Recommended — promote the helper to `utils/typesafe/helpers.py`** (next to the restored
  SKILL.md). Backend already imports from `utils` (`utils.helper.dax2flow`), so NLU calls
  `predict_flow` through a thin `_typesafe_vote` wrapper that supplies history, the narrowed
  criteria, and a production timeout; `model_tests.py` re-imports from the new path. One client, two
  callers, no PromptEngineer change — `FAMILY_TIERS['typesafe']` stays a registration for the tier
  table only.
- **(b) A `case 'typesafe':` branch in PromptEngineer** — keeps all model calls behind one component,
  but forces a prompt→document translation layer and gives `__call__` a second contract shape.

Option (a) moves a file and adds one NLU method; option (b) bends the engineer's contract. Confirm (a).

## 3.6.4 — Degradation

A TypeSafe outage degrades to today's behavior, mirroring how `_collect_votes` (`nlu.py:454`) absorbs
a voter outage: timeout, HTTP error, or missing `TYPESAFE_API_KEY` → `log.warning`, return
`('', 0.0)`, fall through to the ensemble. Production timeout ~5s (the helper's current 30s is an
eval-run setting); `speed_latest` should answer well under that. Never crash a turn on TypeSafe
weather; `_raise_if_debug` stays reserved for schema/code bugs.

## 3.6.5 — Fallback role: ensemble voter (only if 3.6.1 lands close-but-below)

TypeSafe joins round one as a vote dict (`{'flow_name': choice, '_model': 'typesafe',
'_tier': 'med'}`). The tally is count-based, so its calibrated confidence is discarded — which wastes
the model's main advantage; this role exists only as the consolation prize. On Continue turns it is a
natural third voter since it can never share a family with PEX.

## Open questions (need Derek / the API docs)

1. **Does the response expose the full distribution?** `answers['flow']` returns `choice` +
   `confidence` today. If per-option probabilities are available, `pred_flows` ranks from them
   (top-3, matching the ensemble's shape and feeding `_intent_split`); if not, round zero returns a
   single-entry ranking.
2. **What are the `noul` and `score` question types for?** `choice` is clearly detection; `score`
   reads like graded judgments (slot repair? completion quality?), `noul` is opaque. One sentence of
   intent decides whether they get follow-up rounds. Restoring `utils/typesafe/SKILL.md` likely
   answers both questions.
3. **Threshold confirmation** — 0.85 as the starting `typesafe_accept_min`, re-picked from the 3.6.1
   per-case data.

## Verification

1. The 3.6.1 accuracy number recorded in this spec next to the 87.5% baseline, with the chosen role.
2. `run_suite.py --tests` green throughout; update existing tests only.
3. Full suite (`run_suite.py`, default 8-sample, seed 212) for a like-for-like read against the
   round-2.12 report: completion at or above, `wrong_belief` count at or below, and a visible latency
   drop on turns where round zero accepts (3 medium LLM calls → 1 TypeSafe call).
