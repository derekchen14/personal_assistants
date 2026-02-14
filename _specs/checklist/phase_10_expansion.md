# Phase 10 — Expansion

Enable remaining flows, tune prompts, and iterate based on evaluation. This phase brings the agent from 16 working flows to the full 32.

## Context

With the frontend deployed and evaluation pipeline running, this phase enables the 16 Batch 2 flows that were templated but stubbed during Phase 7. Each flow is enabled one by one, tested end-to-end, and tuned based on evaluation results. Batch 3 flows (16 unsupported) are evaluated for potential promotion.

**Prerequisites**: Phase 9 complete — working frontend, evaluation pipeline, production configuration.

**Outputs**: 32 fully working flows, expanded NLU exemplars, tuned prompts, evaluation baselines.

**Spec references**: [pex.md § Policies and Tools](../modules/pex.md), [evaluation.md](../utilities/evaluation.md), [tool_smith.md § Skill Templates](../utilities/tool_smith.md)

---

## Steps

### Step 1 — Audit Batch 2 Skill Templates

Review all 16 Batch 2 skill templates in `backend/prompts/skills/`. Verify each has:

- Flow description and behavior section
- Slot-to-parameter mapping (if tools are used)
- Expected tool sequence
- Output format specification

Fix any incomplete templates before enabling.

### Step 2 — Enable Batch 2 Flows

For each of the 16 Batch 2 flows, update the policy file to wire the flow through to LLM execution instead of returning "coming soon":

1. Remove the flow name from `_BATCH_2` set in the policy file
2. Add it to `_BATCH_1` (or remove the set check entirely)
3. Add a `_do_<flow>` handler if the flow needs custom logic beyond `_llm_execute`
4. Test the flow end-to-end via WebSocket

**Batch 2 flows by intent**:

| Intent | Flows |
|---|---|
| Converse | preference, endorse |
| Explore | review_lessons, summarize, inspect |
| Provide | teach, revise |
| Design | revise_flow, suggest_flow, refine |
| Deliver | confirm_export, preview, ontology |
| Plan | research, expand |
| Internal | read_spec |

### Step 3 — Expand NLU Exemplars

With 32 working flows, the NLU classifier needs more exemplars to distinguish between them:

- Start with 10 sample utterances per flow (from Phase 7 artifacts)
- Add exemplars for commonly confused flow pairs
- Target ~32 exemplars in `for_experts.py` for intent prediction
- Target ~32 exemplars for flow prediction
- Add ~16 exemplars for `for_contemplate.py` re-routing decisions

### Step 4 — End-to-End Flow Testing

Test each newly enabled flow through the full pipeline:

- Send a representative utterance via the frontend
- Verify NLU classifies to the correct flow
- Verify PEX executes the correct tools
- Verify RES produces a natural response with appropriate block type
- Check that the display frame renders correctly in the frontend

### Step 5 — Evaluate Batch 3 Promotions

Review the 16 Batch 3 (unsupported) flows and decide which, if any, should be promoted:

- Flows that users frequently attempt → promote to Batch 2 (template + stub)
- Flows that are genuinely unnecessary → keep unsupported or remove from ontology
- Flows that overlap with existing flows → merge into the covering flow

### Step 6 — Prompt Tuning

Based on evaluation results from Phase 9:

- Identify flows with low NLU accuracy → add exemplars targeting failing cases
- Identify flows with poor trajectory scores → refine skill templates
- Identify flows with low Final Output scores → adjust RES templates or naturalization prompts
- Version all prompt changes: `{template_id}.v{N+1}`

### Step 7 — Establish Evaluation Baselines

With all 32 flows working:

- Run the full offline evaluation suite
- Record baseline scores for all three pillars (workflow prediction, trajectory, final output)
- Set regression thresholds based on baselines
- Create test cases for each flow (JSON conversation format)

### Step 8 — Flow Confusion Analysis

Identify flow pairs that the NLU frequently confuses:

- Run confusion matrix on all 32 flows
- For pairs with >10% confusion rate: add distinguishing exemplars, refine flow descriptions, or merge flows
- Update edge flow definitions in ontology if needed
- Re-run evaluation to confirm improvement

### Step 9 — User Feedback

**Explicit**: thumbs up/down (`bool`), correction (`{expected, actual}`), rating (`int` 1–5).

**Implicit**:

| Signal | Interpretation |
|---|---|
| Re-ask | Prior response insufficient |
| Abandonment | User gave up (non-empty stack at session end) |
| Correction follow-up | Agent was wrong |
| Continued engagement | Positive signal |
| Escalation to ambiguity | Agent couldn't handle it |

---

## Files to Modify/Create

| Action | File | Description |
|---|---|---|
| Modify | `<domain>/backend/modules/policies/*.py` | Enable Batch 2 flows (move from _BATCH_2 to _BATCH_1) |
| Modify | `<domain>/backend/prompts/skills/*.md` | Refine skill templates based on evaluation |
| Modify | `<domain>/backend/prompts/for_experts.py` | Expand NLU exemplars to ~32 per classification |
| Modify | `<domain>/backend/prompts/for_contemplate.py` | Add ~16 re-routing exemplars |
| Modify | `<domain>/backend/prompts/for_res.py` | Tune naturalization prompts |
| Modify | `<domain>/schemas/ontology.py` | Update edge flows based on confusion analysis |
| Create | `<domain>/tests/test_flows/{dax}_{flow}.py` | Integration tests for Batch 2 flows |
| Create | `<domain>/tests/eval_cases/*.json` | Offline evaluation test cases |

---

## Verification

- [ ] All 16 Batch 2 flows enabled and returning real responses (not "coming soon")
- [ ] Each Batch 2 flow passes end-to-end testing via WebSocket
- [ ] NLU exemplars expanded: ~32 for intent prediction, ~32 for flow prediction
- [ ] `for_contemplate.py` has ~16 re-routing exemplars
- [ ] No two flows have >10% confusion rate
- [ ] Offline evaluation baseline scores recorded for all three pillars
- [ ] Regression thresholds set based on baselines
- [ ] Prompt versions incremented for all tuned prompts
- [ ] Batch 3 flows reviewed: promotions, merges, or removals decided
- [ ] Agent handles: simple query, multi-turn, Plan decomposition, ambiguity resolution
- [ ] 320 total sample utterances (10 per flow × 32 flows) documented
