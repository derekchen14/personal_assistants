# DoE adjudication — round 5.2 (one flow stack)

## Winner: SWE1, with one file swapped from SWE2 (backend/modules/policies/base.py)

Divergence: Six production files are identical between builds (same blobs). Three differences:
(1) base.py — SWE2 matches the spec 5.2.9 block exactly (docstring rewrap, split
write_completion call); SWE1 kept old wrapping, leaving a 102-char line. Swapped in SWE2's.
(2) pex_unit_tests hypothesis header — spec 5.2.11.4 gives the exact rewrite; SWE1 matches it,
SWE2 kept an extra @reproduce_failure sentence the spec dropped. Kept SWE1's.
(3) mem_unit_tests _session_state fixture (shared out-of-spec fix, both flagged) — SWE1's entry
matches the real BaseFlow.to_dict shape (dax, intent, full source parts); SWE2 omits dax/intent.
Kept SWE1's. Remaining test differences are line-wrap only.

Compliance: Plain language — grep of added lines for all banned words returns nothing; sweeps of
5.2.10 applied. Net deletion: 145 insertions / 231 deletions (−86), meeting criterion 6. Spec
conformance verified hunk by hunk against 5.2.2-5.2.11; both builds implement all sections and
amendments A1-A7. Both made one flagged out-of-spec fix (mem fixture) that the spec's
open_session change forces — rehydrate_flow reads flow_name/flow_id/status/stage/turn_ids/slots,
which the old fixture lacked. Both report 224 passed, 0 skips. No branches, no commits.

## Ponytail review

- Deletes three indirection layers (_run_stack_op, _rehydrate_stack, _stack_flow), the mirror
  block, and prestack; replaces them with one stack= param — the lowest rung that works.
- No new class, method, or attribute; saved-copy refresh is one line at each of three spec'd
  points.
- stack=None default is a real default (op 'update' has no stack), not a guard; bad calls crash
  loudly.
- Tests shed paired direct-mutation lines; hypothesis machine now drives one stack through
  write_state only.
- Mild residue: three separate refresh points (write_state, read_state, agent post-hook) could
  drift, but each is one line and spec-mandated.
- Net score: 9/10 — a deletion round done as a deletion round.

## Ship

Apply-check: git apply --check exit 0 from the repo root; stat 10 files, +145/−231. Orchestrator
must: (1) re-run the free suite (the composed diff mixes the builders' test files), (2) run the
live 8-scenario gate, (3) commit. Pre-existing unused rehydrate_flow imports in nlu/mem tests
stay per builder notes; the lone DeprecationWarning is pre-existing (google-genai).
