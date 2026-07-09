# Round 0.1 build plan — component interface taxonomy (staged)

Source of truth: `_specs/_review/rounds/round_0.1_spec.md` (signed off). This plan compiles the
code-ready parts of that spec into work items for SWE1/SWE2, with file:line refs, a deterministic
test plan, and a build order that keeps the three suites green between steps.

All paths below are under `assistants/Hugo/` unless absolute. Style: plain language, lines to 100
chars, no defensive guards beyond the existing LLM-input guardrails, match existing style, no new
concepts beyond the spec.

---

## 1. Stage boundaries (in scope vs deferred)

IN scope (built this round):
- Ambiguity Handler redesign: `declare`→`recognize`, single-shape `present()`, `resolve(explanation)`,
  new `recover()` that delegates to an NLU method (deterministic routing; reasoning lives in NLU).
- Scoped tool-surface changes T1-T6 as amended:
  - split the orchestrator `scratchpad(op)` tool into `read_scratchpad` / `append_to_scratchpad`;
  - replace sub-agent `call_flow_stack(action,details)` with `read_flow_stack` / `stackon_flow` /
    `fallback_flow`;
  - retire `manage_memory` (both surfaces);
  - rename `search_faqs` → `search_documents` (rename in place; no new menu placement);
  - new tools `declare_ambiguity` (sub-agents), `ask_clarification_question` (orchestrator),
    `recover_from_ambiguity` (orchestrator); `handle_ambiguity` fully retired.
- Component-method cleanups C1-C10.
- The flow-prompt `.md` edits the tool renames force, plus the two prompt builders.
- Test updates for every change above.

DEFERRED (not built this round — owning round named):
- NLU review + `scratchpad.update()` + `update_scratchpad` tool — round 3.3.
- MEM-agent tools (`get_dialog_state`), end-of-turn stack snapshot N1, `FlowStack.load()`, and the
  divergence-1 stack-persistence move off `write_state` — the MEM module round (round 4).
- The Assistant turn-flow reorder (spec "Assistant" bullets: `present()`→`resolve()`→re-`present()`
  injection into PEX) — its own future spec.
- N2 User Preferences `save()`/`.load()` persistence — the MEM module round.
- Adding `search_documents` to the orchestrator/flow menus beyond the rename — see default D-4.

## 2. Confirmed sketches (spec said "confirm")

- The belief tool stays named `understand` (op = read/think/contemplate). No rename.
- `store_preference` stays as PEX's scoped preference write (T3) — no change.
- The op family parameter is `op` (T1) — already the case for `understand`/`manage_flows`; no change.

## 3. Required additions (call-outs per pipeline README)

New concepts — none beyond the spec. The spec's scoped tools and the redesigned ambiguity methods
are the round's deliverable, not net-new concepts. Concretely added:
- Methods: `AmbiguityHandler.recognize` (renamed from `declare`), `AmbiguityHandler.recover` (new),
  `NLU.recover` (new — the recovery reasoning).
- Wiring: `AmbiguityHandler.nlu` back-reference (set in `agent.py`, same pattern as `pex.nlu`);
  a `memory` argument on `NLU.__init__` so `NLU.recover` can call `memory.recall`.
- Tools: `declare_ambiguity`, `ask_clarification_question`, `recover_from_ambiguity`,
  `read_scratchpad`, `append_to_scratchpad`, `read_flow_stack`, `stackon_flow`, `fallback_flow`.

Big decisions — three, resolved with defaults in section 8 (C5 revision collapse, C6 scratchpad
write shape, C8 serializer merge). Each is a contained cleanup; none changes external behavior.

Alternatives considered — for the tool-surface swap, the alternative was keeping `manage_memory`/
`call_flow_stack`/`handle_ambiguity` as compatibility shims beside the new tools. Rejected: the spec
retires them, and dual surfaces defeat the "scoped, single-purpose per caller" goal. The other
alternative (one big atomic tool-surface commit) is rejected in favor of three smaller green steps
(section 7).

---

## 4. Work items — component-method cleanups (Group A)

Each item is atomic: code + every caller + its tests land together so the suite stays green.

### A1 — Ambiguity Handler redesign (C7)
`backend/components/ambiguity_handler.py`
- Rename `declare` → `recognize` (line 30). Same body/signature.
- `present()` (line 39): drop the `name` param; return `self.level` (empty string = none). Every
  current caller uses it as a truthy check, so this is safe.
- `resolve()` (line 56): add optional `explanation:str=''`; keep clearing level/metadata/observation.
  Log the explanation.
- Method-call caller updates for `declare`→`recognize` (these are direct code calls, not tools):
  - `backend/modules/nlu.py:119,201,215,228`
  - `backend/modules/pex.py:197` (`_security_check`)
  - `backend/modules/policies/base.py:218`; `research.py:25,173,207`; `draft.py:81,128,160,162,201,248`;
    `revise.py:54,82,111,125,131,163,167,264,299`; `publish.py:92,113`
- `present()`/`resolve()` code callers unchanged in behavior: `agent.py:68,69,152`;
  `pex.py:238,667,717,744`.
- NOTE: `recover` is added in B1 (needs the NLU wiring), not here.

### A2 — FlowStack `peek()` dropped, use `get_flow()` (C1)
`backend/components/flow_stack/stack.py`
- Delete `peek()` (lines 49-51). `get_flow(status=None)` (line 53) returns the same top-of-stack.
- Replace `.peek()` → `.get_flow()` at: `dialogue_state.py:203`; `pex.py:620,642,740`;
  `policies/base.py:231`.
- Tests: `pex_unit_tests.py:116,1763,1856,1870`; `mem_unit_tests.py:506,508`.

### A3 — FlowStack `pop_completed()` → `pop()` (C2)
`backend/components/flow_stack/stack.py`
- Rename method `pop_completed` → `pop` (line 75). (Private `_pop` at line 114 is untouched — no
  name clash.)
- `dialogue_state.py`: `write_state` op string `'pop_completed'` → `'pop'` (lines 168 docstring, 179,
  180 call `stack.pop()`).
- `pex.py:611`: drop the `{'pop':'pop_completed'}` remap so `manage_flows` op `'pop'` passes straight
  to `write_state`. (Keep `{'update':'update_flow'}`.)
- Tests: `nlu_unit_tests.py:622,669` (op `'pop'`); `pex_unit_tests.py:1575-1583` helper + comments.

### A4 — Drop `ContextCoordinator.find_turn_by_id()` (C3)
`backend/components/context_coordinator.py:302-308`. No callers (verified by grep). `get_turn(turn_id)`
covers the read. Delete the method; leave `self.bookmark` and `get_turn` as-is.

### A5 — snake_case ContextCoordinator outliers (C4)
`backend/components/context_coordinator.py`
- `setbookmark` → `set_bookmark` (line 295); `storecompleted_flows` → `store_completed_flows`
  (line 322). Both have no callers today (dead but spec asks to rename, not delete).

### A6 — Collapse ContextCoordinator revision paths (C5) — see default D-1
`backend/components/context_coordinator.py`
- Keep `rewrite_history` (line 288) as the single revision entry (it already routes to
  `Turn.add_revision`).
- Delete `revise_user_utterance` (line 342) and its only helper `_rebuild_recent` (line 353). Both
  are dead (no callers). This drops the truncate/undo behavior — see D-1.

### A7 — Merge serializers (C8) — see default D-2
`backend/components/dialogue_state.py`
- Delete `serialize_session()` (lines 117-128); move its body into `read_state()` (line 157) so
  `read_state` builds the session document directly.
- `save()` (line 132) calls `self.read_state()`; `write_state` return (line 186) returns
  `self.read_state()`.
- Keep `serialize()` (line 103, the per-turn form) untouched.
- Tests: `nlu_unit_tests.py:541,544` and `mem_unit_tests.py:371` → `read_state()`. Leave
  `serialize()` tests (`nlu_unit_tests.py:563,566`) as-is.

### A8 — Drop `UserPreferences.read_all()` (C9) — see default D-3
`backend/components/user_preferences.py:43-44`. Delete. `read(query=None)` (line 38) already returns
every key as the flat value view.
- Tests: `mem_unit_tests.py:536,543` read the typed record — repoint them at the private store
  `prefs._preferences[key]` to keep the `endorsed`/`confidence` assertions.

### A9 — SessionScratchpad single-shape write (C6) — see default D-5
`backend/components/session_scratchpad.py`
- `write` (line 23): signature becomes `write(entry:dict, writer:str='orchestrator')`. Drop the
  `key:str|dict` union and the `value` param. File mode: stamp `writer`, append (current dict branch,
  lines 31-34). In-memory mode: append the stamped `entry` to the OrderedDict under a required
  `entry['key']`; keep the LRU cap. `read(key)` in-memory lookup stays.
- `write_completion` (line 59): `self.write(record, writer=flow)` — `record` is already a dict; keep.
- Caller updates (key,value form → one dict):
  - `pex.py:578` (`_dispatch_save_findings_tool`): `write({'key': flow_name, ...payload})`.
  - `policies/research.py:113`: `write({'key': flow.name(), ...})`.
  - `policies/revise.py:205`: `write({'key': str(key), ...entry}, writer=flow.name())`.
  - `policies/revise.py:284`: `write({'key': 'propose', ...})`.
- Tests: `nlu_unit_tests.py:446` (`test_key_value_call_wraps_into_entry`) — rewrite to the dict form
  (`test_entry_dict_is_stamped_and_appended`). Other TestSessionScratchpad cases (439-509) pass
  entries as dicts already or via `write_completion`.

### A10 — search rename + privatize internals (T6 + C10)
`backend/components/business_context.py`
- `search_faqs` (line 83) → `search_documents` (public). Body calls `self._rerank(...)`.
- `search_all` (line 60) → `_candidates`; `rerank` (line 67) → `_rerank`.
`backend/components/memory_manager.py`
- `retrieve` (lines 28-30): `search_faqs`→`search_documents`, `search_all`→`_candidates`,
  `rerank`→`_rerank`. Docstring line 5 mention → `search_documents`.
`backend/modules/pex.py:146`
- tools dict key `'search_faqs'` → `'search_documents'`, method `'search_documents'`.
`schemas/tools.yaml:578-581`
- `search_faqs:` key + `tool_id` + `name` → `search_documents` ("Search documents"). Keep schema/caps.
- Tests: `mem_unit_tests.py:316,326,338` → `search_documents`. (`test_retrieve_faq_shortcut` at
  mem:67 exercises `retrieve(documents=['faq'])` — unchanged path, still valid.)

---

## 5. Work items — tool surface + ambiguity behavior (Group B)

Tool defs live in `pex.py`: `_component_tool_definitions()` (809, sub-agent menu via
`get_tools_for_flow` 800) and `_orchestrator_tool_definitions()` (987, orchestrator menu via
`get_tools_for_orchestrator` 973). Dispatch in `_dispatch_tool` (468) and `_orchestrator_toolset`
(161).

### B1 — `recover()` + NLU recovery method + wiring
- `agent.py`: pass `self.memory` into `NLU(...)` (line 43); after `self.pex.nlu = self.nlu` (line 45)
  add `self.ambiguity.nlu = self.nlu`.
- `backend/modules/nlu.py`: `__init__` (line 76) gains `memory`; store `self.memory = memory`. Add
  `NLU.recover()`: read the pending ambiguity (`self.ambiguity.level`/`.metadata` — what is
  `missing`), call `self.memory.recall(query)` and `self.scratchpad.read(...)`, append a recovery
  entry to the scratchpad, and if a value for the missing slot is found call
  `self.ambiguity.resolve(explanation=...)`. Return `{'recovery': <found or None>}`. Deterministic
  (no LLM) for this round; an LLM-judged version is designed-not-built.
- `backend/components/ambiguity_handler.py`: `__init__` sets `self.nlu = None`; add `recover()` that
  returns `self.nlu.recover()` (deterministic routing, no reasoning in the component).

### B2 — `declare_ambiguity` tool (sub-agents) replaces `handle_ambiguity`
- `pex.py`: replace `_dispatch_ambiguity_tool` (547) with a `declare_ambiguity` handler: flat args
  `level` / `metadata` / `observation` (no `action`); run `_validate_ambig_metadata` (67); on pass
  call `self.ambiguity.recognize(...)`; return `{'_success':True}` or corrective `invalid_input`.
- `_dispatch_tool` (478): replace the `handle_ambiguity` branch with a `declare_ambiguity` branch.
- `_component_tool_definitions` (809): replace the `handle_ambiguity` def (810-840) with a
  `declare_ambiguity` def (drop the `action` enum; keep the per-level metadata description and the
  same required `level`+`metadata`).

### B3 — `ask_clarification_question` tool (orchestrator)
- `pex.py`: new handler → if `self.ambiguity.present()` return
  `{'_success':True,'question':self.ambiguity.ask(active_flow_name)}` (active flow from
  `self.flow_stack.get_flow()`); else corrective `{'_success':False,'_error':'invalid_input',...}`.
- Add to `_orchestrator_toolset` (161) and to `_orchestrator_tool_definitions` (987). No args.

### B4 — `recover_from_ambiguity` tool (orchestrator)
- `pex.py`: new handler → if `present()` return `{'_success':True, **self.ambiguity.recover()}`; else
  corrective error. Add to `_orchestrator_toolset` and `_orchestrator_tool_definitions`. No args.

### B5 — split orchestrator scratchpad tool
- `pex.py`: `_dispatch_scratchpad` (749) → two handlers: `read_scratchpad`
  (`self.scratchpad.read(writer=..., keys=...)`) and `append_to_scratchpad`
  (`self.scratchpad.write(entry)`; writer stamped in code).
- `_orchestrator_toolset` (161): drop `'scratchpad'`, add `'read_scratchpad'` +
  `'append_to_scratchpad'`.
- `_orchestrator_tool_definitions` (987): replace the `scratchpad` def (1053-1077) with the two flat
  defs.

### B6 — replace `call_flow_stack` (sub-agents) with three flat tools
- `pex.py`: replace `_dispatch_flow_stack_tool` (521) with `read_flow_stack`
  (`self.flow_stack.to_list()` / `get_flow().slot_values_dict()` / `get_flow().to_dict()` by a
  `details` arg — keep the existing three read shapes), `stackon_flow(flow)`
  (`self.flow_stack.stackon`), `fallback_flow(flow)` (`self.flow_stack.fallback`).
- `_dispatch_tool` (484): replace the `call_flow_stack` branch with the three branches.
- `_component_tool_definitions` (809): replace the `call_flow_stack` def (879-904) with three flat
  defs (`read_flow_stack` keeps `details` ∈ {flows,slots,flow_meta}; `stackon_flow`/`fallback_flow`
  take `flow`).

### B7 — retire `manage_memory` (both surfaces) + add `read_scratchpad` to the sub-agent menu
- `pex.py`: delete `_dispatch_manage_memory` (762-776) and its `_dispatch_tool` branch (482-483).
- `get_tools_for_orchestrator` (973): drop `'manage_memory'` from the included component names
  (979-980); the orchestrator's scratchpad reads now use `read_scratchpad` (B5).
- `_component_tool_definitions` (809): delete the `manage_memory` def (866-878); the sub-agent menu
  gains `read_scratchpad` (shared with B5's def) so policies can still read the pad. Sub-agent writes
  stay on `save_findings` (append-only).
- `_guarded_call` (450-451): remove the `if '_success' not in result` status-contract fallback and
  its comment — no tool returns the `{'status':...}` shape after this.

### B8 — finish `handle_ambiguity` retirement
- Confirm no remaining `handle_ambiguity` references in `pex.py` after B2 (def, dispatch, and the
  `get_tools_for_orchestrator` inclusion list 979-980 must drop it). The orchestrator's ambiguity
  surface is now `ask_clarification_question` + `recover_from_ambiguity`; sub-agents use
  `declare_ambiguity`.

---

## 6. Work items — prompt updates (Group C)

### C-md — flow prompt `.md` files (`backend/prompts/pex/flows/`)
Mechanical renames forced by B2/B6/B7. Per-file line refs from grep:
- `handle_ambiguity(...)` → `declare_ambiguity(...)` (drop any `action='declare'`; flat level/metadata):
  find.md:16,29,97; outline.md:47,59,160; compare.md:21,25,39; schedule.md:18,32,80; release.md:22,35,136;
  write.md:27,29,50,69; compose.md:76,89,148; cite.md:18,20,36,94; audit.md:38; summarize.md:14,27,77;
  brainstorm.md:20,36,129; refine.md:29,46; propose.md:15,16,28,72,82; browse.md:15,28,94.
- `manage_memory(...)` → `read_scratchpad(...)` (reads); note that persistent findings go through
  `save_findings`: outline.md:60; release.md:36; write.md:51; audit.md:39; rework.md:34;
  and the `- manage_memory(**params)` menu lines in find/compare/schedule/compose/cite/summarize/
  brainstorm/refine/browse.
- `call_flow_stack(action=...)` → `read_flow_stack` / `stackon_flow(flow=...)` / `fallback_flow(flow=...)`:
  reads — outline.md:61; release.md:37,145; audit.md:40; rework.md:35; write.md:53; and the
  `- call_flow_stack(action, details)` menu lines. fallbacks — write.md:113; compose.md:138;
  rework.md:20.
- `coordinate_context(...)` stays (write.md:52; propose.md:29,91) — not in scope.

### C-orch — `backend/prompts/for_orchestrator.py`
- Line 226 (`_render_preferences`): "Promote durable ones via `manage_memory`" →
  "…via `store_preference`".
- Lines 89, 94-95 (`TOOL_POLICY`): the orchestrator no longer declares ambiguity. Reword the commit
  rule (88-91) so the turn completes when a flow ran OR a dispatched flow returned a clarification
  the orchestrator relayed; reword "Ask vs. proceed" (92-99) to: relay a flow-returned `question`,
  and use `ask_clarification_question`/`recover_from_ambiguity` rather than declaring.
- Line 113 already says `scratchpad op="read"`/`op="append"` — update to name `read_scratchpad` /
  `append_to_scratchpad` to match B5.

### C-pex — `backend/prompts/for_pex.py:48`
- `handle_ambiguity()` → `declare_ambiguity()` (this text is sub-agent guidance).

---

## 7. Build order (each step ends green)

Run the three suites after every step: `pytest utils/evaluation_suite/_tests/pex_unit_tests.py
mem_unit_tests.py nlu_unit_tests.py` (cwd + `sys.path[0]` = `assistants/Hugo`; conftest handles this).
`model_tests.py` is live-model — excluded from the gate.

1. A2 (peek→get_flow).
2. A3 (pop_completed→pop).
3. A4 + A5 (drop find_turn_by_id; snake_case outliers).
4. A6 (revision collapse).
5. A7 (serializer merge).
6. A8 (drop read_all).
7. A9 (scratchpad single-shape write).
8. A10 (search_documents rename + privatize).
9. A1 (ambiguity recognize/present/resolve) — updates all method callers + tests together.
10. B1 (recover + NLU wiring) — add test.
11. Tool-surface step 1: B5 + B7 (scratchpad split, manage_memory retired) + C-md manage_memory refs +
    for_orchestrator scratchpad/preference refs + D-tests.
12. Tool-surface step 2: B6 (call_flow_stack → three flow tools) + C-md flow-stack refs + D-tests.
13. Tool-surface step 3: B2 + B3 + B4 + B8 (declare/ask/recover; handle_ambiguity gone) + C-md
    ambiguity refs + C-pex + for_orchestrator commit-rule reword + D-tests.

Steps 1-10 are independent; 11-13 depend on A1/B1 and on each other only through shared test files, so
keep their order.

---

## 8. Test plan (deterministic only — no live/paid model calls)

Existing tests to update (expected result = passes after the edit):

| Change | Test (file:line) | Expected after |
|---|---|---|
| A2 | pex `test_manage_flows_stacks_and_saves`:116; stackon/injection:1763,1856,1870; mem open_session:506,508 | `.get_flow()` returns the same top flow the asserts expect |
| A3 | pex FlowStackContract helper:1575; nlu WriteStateOps:622,669 | op `'pop'` pops Completed+Invalid, activates next Pending |
| A7 | nlu `test_round_trip_identical_dict`:541; document/grounding:544; mem `test_open_session_rehydrates`:371 | `read_state()` returns the same session document old `serialize_session()` did |
| A8 | mem `test_bare_string_stores_endorsed_full_confidence`:536; `test_dict_stores_typed_record`:543 | typed record read from `prefs._preferences[key]`; endorsed/confidence assertions hold |
| A9 | nlu `test_key_value_call_wraps_into_entry`:446 → rename `test_entry_dict_is_stamped_and_appended` | `write(entry_dict)` stamps writer and appends; read returns it |
| A10 | mem `TestBusinessContext`:308-338 (`search_faqs`→`search_documents`) | same ranked matches; `test_retrieve_faq_shortcut`:67 unchanged |
| A1 | pex `test_non_completed_returns_status_and_question`:243 (`declare`→`recognize`) | question surfaced from the recognized ambiguity |
| B5+B7 | pex `test_orchestrator_tool_list_composition`:81; `test_defs_cover_dispatch_registry_exactly`:75; `test_scratchpad_tool_routes_to_memory`:145 | orchestrator names = {understand, manage_flows, read_scratchpad, append_to_scratchpad, store_preference, ask_clarification_question, recover_from_ambiguity, coordinate_context} + read-only domain allowlist; no manage_memory, no handle_ambiguity, no call_flow_stack |
| B2+B6 | pex `_COMPONENT_TOOLS` set:1680; `test_few_shot_tools_are_allowlisted`:1697 | sub-agent set = {declare_ambiguity, coordinate_context, read_scratchpad, read_flow_stack, stackon_flow, fallback_flow, execution_error, save_findings} |

New tests to add (all with a fake engineer / no network — pattern: `_FakeEngineer` in
mem_unit_tests.py:21, queue-popped `_call_claude` in pex_unit_tests.py:52):

| # | Test | Asserts |
|---|---|---|
| T-a | `test_present_returns_level_string` (nlu, AmbiguityHandler) | `recognize('specific',{'missing':'x'})` then `present()=='specific'`; after `resolve()` → `''` |
| T-b | `test_resolve_takes_explanation` (nlu) | `resolve('found in prefs')` clears level/metadata/observation |
| T-c | `test_recover_resolves_from_preference` (nlu) | recognize partial-missing slot; a matching `store_preference`; `ambiguity.recover()` writes a scratchpad entry and `present()` becomes `''` (resolved) |
| T-d | `test_recover_stays_pending_when_nothing_found` (nlu) | recover with empty prefs+pad → `{'recovery':None}`, `present()` still set |
| T-e | `test_declare_ambiguity_tool_recognizes` (pex) | `declare_ambiguity(level,metadata)` dispatch calls recognize; bad metadata → `invalid_input` |
| T-f | `test_ask_clarification_question_tool` (pex) | with a pending ambiguity returns the ask text; with none returns corrective error |
| T-g | `test_recover_from_ambiguity_tool` (pex) | routes to `ambiguity.recover`; guarded by `present()` |
| T-h | `test_read_and_append_scratchpad_tools` (pex) | `append_to_scratchpad` stamps writer + grows size; `read_scratchpad(keys=[...])` filters |
| T-i | `test_flow_stack_tools_replace_call_flow_stack` (pex) | `read_flow_stack('flows')`, `stackon_flow('outline')`, `fallback_flow('write')` behave like the old actions |
| T-j | `test_manage_memory_tool_is_gone` (pex) | `manage_memory` not in any menu and dispatch returns unknown-tool corrective error |

Acceptance criteria (all must hold):
- The three suites pass with zero skips (a skip counts as a failure).
- `grep -rn "handle_ambiguity\|manage_memory\|call_flow_stack\|search_faqs\|pop_completed\|\.peek(\|
  serialize_session\|read_all\|find_turn_by_id" backend schemas` returns only the new/renamed forms
  (no stale names in code, prompts, or tools.yaml).
- Orchestrator and sub-agent tool menus match section 5's scoped lists exactly (enforced by the
  composition tests).
- `recover()` never contains recovery reasoning — it only calls `self.nlu.recover()`.
- No live/paid model call in any test (fake engineer / queued responses only).

---

## 9. Ambiguities resolved with a default

- D-1 (C5): `revise_user_utterance` and `rewrite_history` are NOT the same operation (undo-truncate vs
  text-revision). Default: keep `rewrite_history` as the single revision entry; delete
  `revise_user_utterance` + `_rebuild_recent` (both dead code). The truncate/undo behavior is dropped;
  reintroduce it in the round that needs undo.
- D-2 (C8): "keep serialize + read_state" — default: remove `serialize_session`, fold it into
  `read_state`; `save()`/`write_state` use `read_state`; keep `serialize` (per-turn form) as-is.
- D-3 (C9): `read_all()` returns typed records, `read()` returns flat values — not identical. Default:
  drop `read_all` per spec; the two tests read `prefs._preferences[key]` for the typed assertions.
- D-4 (T6): "rename search_faqs → search_documents" — default: rename in place only (business method,
  memory_manager, pex tools dict, tools.yaml). Do NOT newly add it to the orchestrator/flow menus;
  that menu placement is beyond the rename and belongs with the spec's access-matrix work later.
- D-5 (C6): scratchpad in-memory mode still needs a key for `read(key)`. Default: `write(entry:dict)`
  requires `entry['key']` in in-memory mode; file mode ignores it and appends the stamped entry.
