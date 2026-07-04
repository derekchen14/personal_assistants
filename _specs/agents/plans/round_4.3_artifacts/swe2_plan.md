# SWE2 implementation plan — round 4.3

## Orders echo
1. Implement round_4.3_spec exactly: D1 floor-5 (34 exemplars), D2 read counter max_reads=3, D3 13 NLU contrastive exemplars floor-6.
2. Exemplar rules: no Kitty Hawk, multi-word titles, short 10-40w utterances, no em-dash, agentic shape, match write.md/expert block shapes.
3. Plain language: none of the banned terms.
4. StructuredOutput once, short; work product goes in files.
5. Project rules: simple, surgical, no defensive code, 100-char lines.
6. No branches/PRs/commits.

## Summary
Plan only, edited nothing. Three code sites for the read cap in pex.py: (a) __init__ ~L91 add `self.max_reads = config['limits']['max_reads']`; (b) reset `self._reads = 0` alongside `self._injected` in execute() ~L291 (the real reset home for per-turn flags; functionally identical to the spec's "_orchestrate" label since _run_loop runs once per text turn); (c) _guarded_call ~L440 add a third elif for the cap and increment on successful read-only dispatch. Config: add `max_reads: 3` to limits in shared_defaults.yaml. Exemplars: propose +4→5, six 2-count +3, six 3-count +2 (34) in pex/skills/*.md; 13 contrastive NLU cases across the five experts/*_flows.py to floor-6. Two flags below on naming/reset location.

## Sample exemplar
### Example 2: Loosely-located gap → read outline first

Resolved Details:
- Source: post=7f3a9c21
- User asked: "There's a blank spot somewhere in the permits part of the urban beekeeping post. Give me a few ways to fill it."

Trajectory:
1. `read_metadata(post_id=7f3a9c21, include_outline=True)` → the outline lists a section `permits-and-inspections`.
2. `read_section(post_id=7f3a9c21, sec_id=permits-and-inspections, include_sentence_ids=True)` → an empty bullet sits under the fee schedule, right after the sentence on annual renewal.
3. Generate three drop-in bullets, each from a different angle (cost, timing, paperwork).

Final reply (no write tool — the policy turns these into a selection):
1. "Renewal runs about forty dollars a year, due each spring before the first inspection."
2. "Budget a two-week window between filing and approval, so start well ahead of swarm season."
3. "You will need proof of a water source and neighbor sign-off attached to the application."

## Cap placement
pex.py, three sites. (1) __init__ after L91 `self.max_corrective = ...`: add `self.max_reads = config['limits']['max_reads']`. (2) execute() after L291 `self._injected = False`: add `self._reads = 0  # read-only lookups this turn`. (3) _guarded_call, insert a third branch between L440 and L441:
```
elif tool_use.name in READ_ONLY_DOMAIN_TOOLS and self._reads >= self.max_reads:
    result = {'_success': False, '_error': 'read_cap',
              '_message': f'Already used {self.max_reads} read-only lookups this turn. '
                          'Stack on and activate a flow, or respond to the user.'}
```
Then in the existing else, after dispatch: `if tool_use.name in READ_ONLY_DOMAIN_TOOLS and result['_success']: self._reads += 1`. shared_defaults.yaml: add `max_reads: 3` under limits after L93.

## Risks
Naming: spec pseudo-code says reset in `_orchestrate`, but the real method is `_run_loop` (L336); I place the reset in execute() at L291 beside `_injected`, matching the launch order and the existing per-turn-flag home. Functionally identical (one _run_loop per text turn; click path never reads). Increment reads `result['_success']` before the manage_memory status-normalization line, but read-only domain tools natively return `_success` per the service contract, so this is safe. Count-only-success means a read_cap error does not itself burn budget, and a failed lookup stays retryable — matches D2.
