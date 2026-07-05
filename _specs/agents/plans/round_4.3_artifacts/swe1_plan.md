# SWE1 implementation plan — round 4.3

## Orders echo
1. PM spec authoritative: implement D1 floor-5/34 exemplars, D2 read counter max_reads=3 read_cap, D3 13 contrastive detection exemplars.
2. Exemplars: no Kitty Hawk, multi-word titles, short anaphoric utterances, no em-dashes, agentic shape, rotate topics, match house shape.
3. Plain language: none of the banned words used.
4. StructuredOutput once, short; work product to files; fields under 150 words.
5. Simplicity, surgical, no defensive code, 100-char lines.
6. No branches/PRs/commits; plan only, edited nothing.

## Summary
Plan only; edited nothing. Three-part change matching the spec.

Part A: raise 13 PEX skill exemplars in backend/prompts/pex/skills/*.md to a floor of 5 (propose +4; six 2-count +3; six 3-count +2 = 34). Each new block copies write.md shape (Resolved Details -> Trajectory -> optional Final reply) and spans the skill's real tool space.

Part B: cap on repeated read actions. Add limits.max_reads: 3 to shared_defaults.yaml; read it in pex __init__; reset self._reads=0 beside self._injected in __init__ and execute(); add a third guard in _guarded_call turning the 4th successful read-only call into a read_cap corrective error, counting only successes.

Part C: raise experts/*_flows.py detection EXAMPLES to floor 6 per intent (13 new contrastive boundary cases on write/rework and refine/compose/write), keeping the positive_example/edge_case JSON block shape.

Verification: pytest, config assertion, read-cap unit test, detection boundary test, 8-scenario gate.

## Sample exemplar
### Example 2: Loosely-located gap (read the outline first)

Resolved Details:
- Source: post=bee14f02, section described loosely
- User asked: "There's a blank spot near the end of the placement section. Give me a few ways to finish it."

Trajectory:
1. `read_metadata(post_id=bee14f02, include_outline=True)` → the outline lists "Hive Placement Basics" as sec_id=hive-placement-basics.
2. `read_section(post_id=bee14f02, sec_id=hive-placement-basics, include_sentence_ids=True)` → an empty bullet sits right after a line about afternoon shade.
3. Generate three drop-in alternatives, each finishing the shade thought from a different angle (morning warmth, forager traffic, inspection access).

Final reply (no write tool — the policy turns these into a selection):
1. "Face the entrance east so the first warmth of morning pushes foragers out early."
2. "Leave a clear flight path in front; a hedge set too close forces bees up over foot traffic."
3. "Keep a working arm's width behind the hive so an inspection never means moving it."

## Cap placement
shared_defaults.yaml: add `max_reads: 3` in the limits block (after line 95). pex.py __init__ (~line 91, beside max_corrective): `self.max_reads = config['limits']['max_reads']`. Add `self._reads = 0` beside `self._injected` in both __init__ (~line 151) and execute() (~line 291); execute() is the load-bearing per-turn reset. In _guarded_call, insert a third branch before the final `else` (line 441):
```python
elif tool_use.name in READ_ONLY_DOMAIN_TOOLS and self._reads >= self.max_reads:
    result = {'_success': False, '_error': 'read_cap',
              '_message': f'Already used {self.max_reads} read-only lookups this turn. '
                          'Stack on and activate a flow, or respond to the user.'}
```
In the existing `else`, AFTER the `_success` normalization (line 444), add: `if tool_use.name in READ_ONLY_DOMAIN_TOOLS and result['_success']: self._reads += 1`.

## Risks
Spec pseudo-code names `_orchestrate` and "reset before the round loop"; no such method exists — the loop is `_run_loop` and the per-turn reset home is `execute()` (line 291). Placed there. Spec increments before `_success` normalization; I moved it after to avoid a KeyError on any read-only tool lacking `_success` (services return it, so low risk, but safer). read_cap sets `_success: False`, so it increments the `errors` counter (line 395); three back-to-back could trip max_corrective early wrap-up, but a successful stack/activate resets errors — matches intended steering. Task-brief NLU path `nlu/experts/*_flows.py` is wrong; real path is `backend/prompts/experts/*_flows.py`.
