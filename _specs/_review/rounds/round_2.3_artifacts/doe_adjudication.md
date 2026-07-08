# DoE adjudication — round 4.3

## Orders echo
1) Spec round_4.3_spec.md authoritative: D1 floor-5 for 13 priority PEX skills (34 exemplars); D2 per-turn read counter, limits.max_reads:3, read_cap corrective error in _guarded_call, count successes only; D3 13 contrastive detection exemplars, floor 6 per intent, write/rework priority. 2) No Kitty Hawk, multi-word titles, 10-40 word utterances, no em-dashes in utterances, agentic shape, rotate topics, house block shapes. 3) Plain language, banned word list. 4) StructuredOutput once, short, work product in files. 5) Repo CLAUDE.md rules. 6) No branches/PRs/commits.

## Winner
SWE2 (base), with targeted swaps from SWE1

## Divergence
pex.py and yaml changes are the same except comment wording and one alignment space (SWE2 misaligned). Real divergence is exemplar content. Decisive defect: the flow-detection JSON schema enum is intent flows + edge_flows; SWE1 authored two exemplars with flow_names outside the enum (Converse->summarize, Publish->promote; promote is a PEX-agent skill, not a flow) — they teach outputs the schema rejects. SWE1's chat.md also used the flagged tic "earns its place" and an undocumented 'recall' scratchpad key; its converse/revise contrast cases were otherwise sharper. SWE2 was fully schema-valid but its 4 converse additions were all chat (no adjacent-intent contrast the spec asked for), its propose Ex5 invented a coordinate_context signature, and draft covered refine/compose but not write.

## Order compliance
Order 1: pass both on D1 (34 exemplars, all 13 skills at 5) and D2 (identical cap code at the direction's exact placements); D3 counts pass both (13, floor 6) but SWE1 fails schema validity on 2 exemplars — fixed in merge. Order 2: no Kitty Hawk, no utterance em-dashes in either; SWE1 has several sub-10-word utterances; both match house shapes. Order 3: SWE1 fails once ("earns its place"); SWE2 clean; merge clean. Order 4: both wrote diffs to files. Order 5: pass. Order 6: pass (worktree only, no commits). Merged diff: lints 4/4 pass, all detection flow_names in-enum, yaml max_reads=3 loads.

## Ponytail (line-item)
- + Read cap reuses the existing per-turn flag pattern and guard chain; one config knob, no new params, no new concepts.
- + read_cap error reuses the guard result dict shape; increment after _success normalization avoids a KeyError guard.
- + Exemplar work is pure prompt content; zero code surface added beyond the 9-line cap.
- + Merge dropped SWE1's 2 schema-invalid detection exemplars (dead weight that trains rejected outputs) and SWE2's 3 contrast-free chat exemplars, replacing with 3 reused + 1 authored contrastive case.
- + One-line fixes over wholesale swaps: propose coordinate_context signature, yaml comment alignment.
- - Nothing further to delete; no speculative abstractions found in either build.
- Net: +5 / -0 — ship.

## Apply check
git apply --check passed (exit 0) from /Users/derekchen/Documents/repos/personal_assistants against master 8875217; 20 files, 613 insertions, 5 deletions.

## Notes
MUST-FLAG (out of my scope, orchestrator owns utils/): two test fixtures hardcode a limits override without max_reads, so PEX.__init__ raises KeyError — add 'max_reads': 3 at conftest.py:109-111 and pex_unit_tests.py:518-520. The direction's AC-3 read-cap unit test and AC-4 detection check are also unwritten (both SWEs were barred from utils/). Adopted deviation (both builds, per direction): counter increments after _success normalization. I authored one new converse detection exemplar (find edge case) because neither build supplied a valid adjacent-intent case; it follows all authoring rules. Merged files taken from SWE1: converse (2 blocks), draft write edge, revise pair. Everything else SWE2. Verified: lints 4/4, floor counts, enum validity, banned-word and em-dash greps clean.
