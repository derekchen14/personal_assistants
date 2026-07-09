# DoE plan review — round 0.1

Reviewed against `round_0.1_spec.md`, the PM build plan, and the current code
(`session_scratchpad.py`, `revise.py`, `pex.py`, `nlu.py`, `memory_manager.py`,
`user_preferences.py`, `ambiguity_handler.py`, the nlu unit tests).

## SWE1 — APPROVED

The plan follows the PM staging (steps 1-13, each ending green), covers every work item, and adds
no concepts beyond the spec. Two things it does beyond the PM plan are correct and required:

1. The A9 read side. `RevisePolicy._read_scratch_value` (`revise.py:32-35`) reads the old nested
   entry shape (`read(keys=[key])` then `entries[-1][key]`). After A9 flattens writes to
   `{'key': <name>, ...}`, that filter matches nothing. I verified both live callers
   (`revise.py:202` used-count bump, `revise.py:297` propose read-back) break without SWE1's
   rewrite. The PM plan missed this; SWE1's fix is in scope because A9 forces it.
2. The B1 test-fixture change (the `nlu` fixture must build a `MemoryManager` and wire
   `ambiguity.nlu`). Verified: `MemoryManager.__init__` just stores its three components, so
   passing `None` for business context is fine — `recall` only touches preferences.

Decision D-A (define `read_scratchpad` once in `_component_tool_definitions`, dispatch through a
`_dispatch_tool` branch instead of adding it to `_orchestrator_toolset`) deviates from the PM's
literal wording but lands the same menus and the same dispatch behavior — `_dispatch_tool` already
falls through to `_orchestrator_toolset` (`pex.py:488`), so one branch serves both callers, and the
composition tests still assert the PM's exact orchestrator name set. One def object beats two
copies. Accepted.

Minor notes (fix during build, no plan change needed):
- Step 13's `handle_ambiguity` list drops `browse.md:94` (the PM plan includes it). The acceptance
  grep catches it; just do the edit.
- `NLU.recover`'s scratchpad scan iterates `read()` raw; in in-memory mode that yields string keys
  and `missing in entry` becomes a substring check. Unreachable in production (file mode) and in
  the planned tests (prefs hit first / empty pad), and SWE1 flags it. Fine as planned.

## SWE2 — RETURNED

One concrete defect plus two PM deviations:

1. **Misses the A9 read-side work item.** A9 changes the scratchpad entry shape, and
   `RevisePolicy._read_scratch_value` (`revise.py:32-35`) still reads the old nested shape. With
   the flat write, `read(keys=['propose'])` returns nothing: the propose pick phase
   (`revise.py:297`) always declares "options lost", and the used-count bump (`revise.py:202`)
   silently stops working. The plan's own normative flag 3 states "grep confirms no such reader
   exists today" — that is wrong; `_read_scratch_value` is exactly that reader, with two live
   callers. The plan ships a change that breaks a working flow and no test in its plan catches it.
2. **`NLU.recover` writes the recovery entry only on success.** The PM plan (B1) appends a
   recovery entry to the scratchpad and then resolves if a value was found — the failed attempt is
   recorded too. SWE2's code skips the write when nothing is found.
3. **A9 in-memory write drops the writer stamp.** The PM plan says in-memory mode appends the
   stamped entry; SWE2's code stamps only in file mode. The rewritten test asserting the stamp
   happens to run on the file-backed fixture, so the gap would land unnoticed.

Also fix on revision: the plan puts a `read_scratchpad` def in both `_orchestrator_tool_definitions`
(via its 7-item `_HOT_PATH_TOOLS`) and `_component_tool_definitions` — two copies of the same def.
The PM plan says the sub-agent menu shares B5's def; keep one def object.

## Out-of-scope observation (no action this round)

`utils/evaluation_suite/_traces/tolerance_rules.md` names `handle_ambiguity`, `manage_memory`, and
`pop_completed`. Traces are outside this round's suites and the acceptance grep (backend/schemas
only); the trace round should refresh those rules after the renames land.
