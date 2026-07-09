# Round 0.1 — DoE adjudication

Divergence class: **minor**. Decision: **apply SWE2's change set as-is** (`swe2_full.diff`).

## Comparison

Both change sets read the spec and the PM plan the same way. Same 37-file footprint, same method
names (recognize / present-returns-level / resolve(explanation) / recover), same tool surface
(declare_ambiguity, ask_clarification_question, recover_from_ambiguity, read_scratchpad,
append_to_scratchpad, read_flow_stack, stackon_flow, fallback_flow; manage_memory and
handle_ambiguity and call_flow_stack fully retired), same A2-A10 cleanups, same test-plan
coverage. Most hunks are byte-identical. There is no fork in interpreting the spec — the
differences are implementation details:

| Point | SWE1 | SWE2 | Better |
|---|---|---|---|
| `NLU.__init__` param order | `(config, ambiguity, engineer, world, memory)` | `(config, ambiguity, engineer, memory, world)` | SWE2 — matches `PEX.__init__`'s order |
| `SessionScratchpad.write` | stamps `writer` by mutating the caller's dict | builds a stamped copy (`{**entry, 'writer': writer}`) | SWE2 — no side effect on the caller's dict (revise.py re-writes the same entry object) |
| `NLU.recover` scratchpad lookup | open scan `read()` + `missing in entry` | `read(keys=[missing])` — the existing filter | SWE2 — reuses the read filter instead of re-implementing it |
| `read_flow_stack` `details` | required | optional, defaults to `'flows'` | tie — spec lists the enum, says nothing about required; the default matches the spec's to_list framing |
| `declare_ambiguity` missing level/metadata | explicit presence guard returning corrective error | direct indexing; a KeyError falls to `_dispatch_tool`'s exception handler, still a corrective error | tie — both return a corrective error to the model; SWE2 has less code |
| recover tests | in-memory scratchpad; MemoryManager built with `business=None` | file-backed scratchpad (the production mode); real BusinessContext | SWE2 — file mode is what runs in production, and `read()` returns a dict (not entries) in in-memory mode, so SWE1's loop never runs in its own tests |
| Extra tests | — | `test_read_scratch_value_reads_flat_entry` (A9 read side + used_count bump round trip) | SWE2 |
| Diff materialization | .md hunks and three test hunks elided in the submission | full 2089-line diff saved to a file, applies cleanly to 070e90b | SWE2 — the only change set that can be applied verbatim |

SWE1 points in its favor, recorded but not merged in:
- `revise._read_scratch_value` filters with `read(keys=['key'])` then indexes `entry['key']`
  directly; SWE2 scans all entries with `entry.get('key')`. SWE1's shape is closer to the
  no-defensive-get rule. Not merged: `.get` is legitimate here — completion records and
  orchestrator appends have no `key` field, so both variants must skip keyless entries, and
  SWE2's applied diff passes the suites unchanged.
- The explicit presence guard in `declare_ambiguity` gives a clearer corrective message than the
  exception fallback. Both shapes satisfy the plan (B2: "return corrective invalid_input").

## What was applied and why

SWE2's diff, unmerged. The deltas above are too small to justify hand-merging two nearly identical
change sets: SWE2 wins or ties on every point, its full diff is the only one on disk, and merging
SWE1 fragments in would mean reconstructing SWE1's elided hunks by hand for no behavior gain.

Verification: `git apply` of `swe2_full.diff` on the clean tree at 070e90b, then the three
deterministic suites from `assistants/Hugo`
(`pex_unit_tests.py nlu_unit_tests.py mem_unit_tests.py`) — result recorded below.

## Suite result

Applied to the real tree at 070e90b and ran from `assistants/Hugo`:
`python -m pytest utils/evaluation_suite/_tests/pex_unit_tests.py
utils/evaluation_suite/_tests/nlu_unit_tests.py utils/evaluation_suite/_tests/mem_unit_tests.py -q`
→ **248 passed, 0 failed, 0 skipped** in 2.61s (baseline 238 + 10 net-new). The plan's acceptance
grep (`handle_ambiguity|manage_memory|call_flow_stack|search_faqs|pop_completed|.peek(|
serialize_session|read_all|find_turn_by_id` over backend + schemas) returns nothing.
