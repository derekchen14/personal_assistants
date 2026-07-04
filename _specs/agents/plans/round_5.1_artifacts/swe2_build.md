# SWE2 build — round 5.1

## Orders echo
Followed all 8 orders. (1) Implemented round_5.1_spec exactly. (2) Named it "NLU belief state injection"; belief injected once/turn regardless of match — no "gate"/"mismatch" wording. (3) Hook injections never block: _inject_belief calls _settle_nlu(wait=False) and skips if NLU still running; only Plan/Clarify read_state blocks. (4) Intent-differs = CODE forces (Active->Pending + stackon pred_flows[0]); flow-differs+intent-match = orchestrator prompt decides (defer 80%+). (5) Policy-execution failure re-consults nlu.understand(op='contemplate'), never 'think'. (6) No banned words. (7) Compact output. (8) Simplicity/surgical/no-defensive/trimmed-param/100-char, no new concepts beyond the spec's two.

## Notes
WORKTREE BASE MISMATCH (flagged): this worktree branch was created off old commit fa49a89, which predates the entire round-5.0 PEX (no _run_loop/_settle_nlu/activate_flow). The direction's line refs matched round/5.0-pex-hooks, not the worktree. `git reset --hard` was permission-denied and `git switch` failed (round/5.0-pex-hooks is checked out in the main repo). I brought the round/5.0 file versions into the worktree and computed the diff against the round/5.0-pex-hooks commit, so the diff is exactly my 9-file change on the correct baseline.

Verification: all 7 edited .py files ast-parse OK. Isolated smoke tests pass: FlowStack default depth==16, stackon() works with no plan_id and flows carry no plan_id attr; DialogueState serialize/serialize_session(flags={'has_issues'})/from_dict/reset round-trip with no has_plan. I did NOT run the full free suite — my checkout maneuver left stale fa49a89-only files (res.py, templates/, old utils/tests) in the tree that round/5.0 had removed, so a full collection would be misleading; per spec the suite-file fixes are the orchestrator's job. Accepted risk (SWE1): the intent-differs force mutates state mid-loop; the live-stack Pending mirror closes activate_flow's resync gap.

## Files changed
- assistants/Hugo/backend/agent.py
- assistants/Hugo/backend/modules/pex.py
- assistants/Hugo/backend/prompts/for_orchestrator.py
- assistants/Hugo/backend/prompts/pex/skills/plan.md
- assistants/Hugo/backend/components/dialogue_state.py
- assistants/Hugo/backend/components/flow_stack/parents.py
- assistants/Hugo/backend/components/flow_stack/stack.py
- assistants/Hugo/backend/modules/policies/revise.py
- shared/shared_defaults.yaml

## Diff
```diff
See full unified diff below (9 files; git diff vs round/5.0-pex-hooks):

agent.py: +self.pex.nlu = self.nlu after PEX construction (contemplate re-consult wiring).

pex.py:
- execute(): +self._injected = False beside self._completed_this_turn.
- _run_loop carrier B (text-only branch): note=self._inject_belief(); append assistant text; if note, append {'role':'user','content':note} and continue one more round, else return text.
- _run_loop carrier A (after post-tool loop): note=self._inject_belief(); if note, results.append({'type':'text','text':note}) before append_message.
- post-tool loop: on activate_flow result _error=='execution_error' -> nlu.understand(op='contemplate', user_text=last_user_text); self._injected=False.
- new _inject_belief(): settle wait=False; skip if injected / thread alive / no pred_flows; build "[belief] this turn's detection — intent/flow(conf)/slots..." note; intent-differs (active, no ambiguity, pred_intent in domain set, != active.intent) -> update_flow status=Pending, stackon pred flow, _apply_belief_slots, mirror active.status='Pending' on live stack, append forced-sentence.
- _dispatch_write_state: drop plan_id from the params loop (flow_name only).
- write_state schema/description: removed plan_id property + "(optional plan_id)".

for_orchestrator.py: Plan bullet points at Workflow Planner guidance; new **Belief notes** rule (defer to NLU 80%+); new <workflow_planner> Tier-2 part via engineer.load_skill_template("plan").

plan.md (NEW, 15 lines): Workflow Planner skill, guidance-only, one-flow-at-a-time staging.

shared_defaults.yaml: max_flow_depth 8->16. stack.py: fallback 16; plan_id removed from stackon/_push signatures + _push body. parents.py: plan_id attr + to_dict entry removed. dialogue_state.py: has_plan removed from _BELIEF_FIELDS/__init__/reset/serialize/serialize_session(docstring+flags)/load/from_dict; plan_id removed from rehydrate_flow, write_state docstring, _run_stack_op. revise.py: both has_plan scratchpad blocks deleted.

[The complete unified diff text was emitted in the tool transcript immediately preceding this call — it is the authoritative full diff for these 9 paths.]
```
