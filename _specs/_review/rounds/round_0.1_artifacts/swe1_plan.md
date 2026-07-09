# SWE1 implementation plan — round 0.1 (component interface taxonomy)

Optimize: smallest diff, reuse existing helpers, zero new concepts beyond the signed-off spec.
All paths under `assistants/Hugo/` unless absolute. Follows the PM build order (steps 1-13); each
step ends with the three unit suites green:
`pytest utils/evaluation_suite/_tests/pex_unit_tests.py mem_unit_tests.py nlu_unit_tests.py`
(cwd + sys.path[0] = the Hugo dir; conftest sets this). `model_tests.py` is live-model, excluded.

## Three call-outs (for DoE)

- **New concepts:** none beyond the spec. Added methods (`AmbiguityHandler.recognize`/`recover`,
  `NLU.recover`), one back-reference (`AmbiguityHandler.nlu`), one `NLU.__init__` arg (`memory`),
  and the scoped tools the spec names. No new classes, files, config keys, or ontology terms.
- **Big decisions (3):** (D-A) `read_scratchpad` def lives in `_component_tool_definitions` and is
  shared into the orchestrator menu by name; `append_to_scratchpad` is orchestrator-only. (D-B) A9
  flattens scratchpad entries, so the scratchpad READ helper `_read_scratch_value` must change too
  (PM plan omitted it). (D-C) `NLU.recover` is deterministic: a preference/scratchpad lookup for the
  missing slot, no LLM this round.
- **Alternatives:** for D-A, the alternative was defining `read_scratchpad` twice (once per menu) —
  rejected, one def object avoids drift. For D-B, the alternative was keeping the nested
  `{keyname: payload}` write shape — rejected, the spec (C6) requires the single `write(entry)`
  contract, so the reader moves with it.

## Two additions the PM plan missed (I will build these)

1. **A9 read side.** A9 flattens scratchpad writes to `write({'key': <name>, ...})`. The reader
   `RevisePolicy._read_scratch_value` (`backend/modules/policies/revise.py:32-35`) still expects the
   old nested `{keyname: payload}` shape (`entries[-1][key]`). Its two callers (`revise.py:202`
   used-count bump, `revise.py:297` propose read-back) break unless the reader moves with the write.
   Fix in A9 (details below).
2. **B1 test fixture.** The `nlu` fixture (`nlu_unit_tests.py:36-39`) builds `NLU(config, ambiguity,
   engineer, world)` directly. Adding a required `memory` arg breaks it; the recover tests also need
   a real `MemoryManager` and `ambiguity.nlu` wired. Update the fixture in B1.

---

## Step 1 — A2: drop `FlowStack.peek()`, use `get_flow()`

`backend/components/flow_stack/stack.py`
- Delete `peek()` (lines 49-51). `get_flow(status=None)` (line 53) already returns the same
  top-of-stack (both walk from the end; `peek` returned `_stack[-1]`, `get_flow()` returns the first
  entry scanning reversed = `_stack[-1]`).

Replace `.peek()` → `.get_flow()` at:
- `backend/components/dialogue_state.py:203` (`_update_flow`: `flow = stack.peek()`).
- `backend/modules/pex.py:620` (`_dispatch_write_state`), `:642` (`_apply_belief_slots`),
  `:740` (`_dispatch_understand`, the `top = self.flow_stack.peek()` before the hint).
- `backend/modules/policies/base.py:231` (`self.flow_stack.peek().flow_id != flow.flow_id`).

Tests (update `.peek()` → `.get_flow()`):
- `pex_unit_tests.py:116, 1763, 1856, 1870`.
- `mem_unit_tests.py:506, 508` (`world.flow_stack.peek()` and `stack.peek()`).

Satisfies PM test-plan row **A2**.

## Step 2 — A3: rename `pop_completed()` → `pop()`

`backend/components/flow_stack/stack.py`
- Rename method `pop_completed` (line 75) → `pop`. Body unchanged. Update the comment at line 109
  (`pop_completed surfacing the next top`) → `pop surfacing the next top`. Private `_pop` (line 114)
  is untouched — no clash.

`backend/components/dialogue_state.py`
- `write_state` op string `'pop_completed'` → `'pop'`: docstring line 168, the branch at line 179
  (`elif op == 'pop_completed':`) → `'pop'`, and the call at line 180 `stack.pop_completed()` →
  `stack.pop()`.

`backend/modules/pex.py:611`
- Drop the `'pop'` entry from the remap so op `'pop'` passes straight through:
  `op = {'update': 'update_flow'}.get(params['op'], params['op'])`. Update the docstring at
  lines 606-608 mention of `pop_completed` to `pop`.

Tests:
- `nlu_unit_tests.py:622` (`write_state(path,'pop_completed',...)` → `'pop'`) and `:669` (same).
- `pex_unit_tests.py:1575-1583` Hypothesis rule `pop_completed`: keep the rule name or rename to
  `pop`; change the `write_state(..., 'pop_completed', ...)` call at line 1577 → `'pop'` and update
  the assertion messages that say `pop_completed`.

Satisfies PM test-plan row **A3**.

## Step 3 — A4 + A5: ContextCoordinator dead-method drop + snake_case

`backend/components/context_coordinator.py`
- A4: delete `find_turn_by_id` (lines 302-308). No callers (grep confirms only the def).
  `get_turn(turn_id)` (line 110) covers the read; leave `self.bookmark` and `get_turn` as-is.
- A5: rename `setbookmark` (line 295) → `set_bookmark`; `storecompleted_flows` (line 322) →
  `store_completed_flows`. Bodies unchanged. Both dead today (no callers) — rename only, per spec.

No test changes (no callers, no tests reference these). Optional: `run_traces.py:44` docstring
mentions `call_flow_stack` as an example — non-functional, out of scope; leave it.

## Step 4 — A6: collapse ContextCoordinator revision paths

`backend/components/context_coordinator.py`
- Keep `rewrite_history` (line 288) as the single revision entry (routes to `Turn.add_revision`).
- Delete `revise_user_utterance` (lines 342-351) and its only helper `_rebuild_recent`
  (lines 353-359). Both dead (grep confirms only defs). Drops the truncate/undo behavior — the round
  that needs undo reintroduces it (PM default D-1).

No test changes.

## Step 5 — A7: merge DialogueState serializers

`backend/components/dialogue_state.py`
- Move the `serialize_session` body (lines 117-128) into `read_state` (line 157): `read_state` now
  builds the session document directly (session / user_beliefs / grounding / flow_stack / flags).
- Delete `serialize_session`.
- `save` (line 132): `json.dumps(self.read_state(), indent=2)`.
- `write_state` return (line 186): `return self.read_state()`.
- Keep `serialize` (line 103, per-turn form) untouched.

Tests (repoint `serialize_session()` → `read_state()`):
- `nlu_unit_tests.py:541` (`test_round_trip_identical_dict`), `:544` (`test_document_blocks...`).
- `mem_unit_tests.py:371` (`test_open_session_rehydrates`).
- Leave `serialize()` tests (`nlu_unit_tests.py:563,566`) unchanged.

Satisfies PM test-plan row **A7**.

## Step 6 — A8: drop `UserPreferences.read_all()`

`backend/components/user_preferences.py`
- Delete `read_all` (lines 43-44). `read(query=None)` (line 38) already returns the flat
  `{key: value}` view.

Tests (the two that read the typed record → read the private store `_preferences[key]`):
- `mem_unit_tests.py:536` (`test_bare_string_stores_endorsed_full_confidence`):
  `record = prefs._preferences['verbosity']`.
- `mem_unit_tests.py:543` (`test_dict_stores_typed_record`): `record = prefs._preferences['tone']`.
  The `endorsed`/`confidence`/`triggers` assertions hold unchanged.

Satisfies PM test-plan row **A8**.

## Step 7 — A9: SessionScratchpad single-shape write (+ the read side)

`backend/components/session_scratchpad.py`
- `write` (line 23): signature `write(entry:dict, writer:str='orchestrator')`. Drop the
  `key:str|dict` union and `value`.
  - File mode (path set): stamp `entry['writer'] = writer`, append the JSON line (current lines
    31-34 behavior, minus the `dict(key)`/`{key:value}` construction — `entry` is already the dict).
  - In-memory mode (no path): `entry['writer'] = writer`, then
    `self._scratchpad[entry['key']] = entry`; `move_to_end` if the key already exists; keep the LRU
    cap loop (lines 26-29). Requires `entry['key']` (PM default D-5). `read(key)` in-memory
    (line 42) stays — it now returns the stamped entry dict.
- `write_completion` (line 59): `self.write(record, writer=flow)` — `record` is already a dict;
  unchanged call, works in file mode (the only mode `write_completion` runs in).

Caller updates (old `write(key, value)` → one dict carrying `key`):
- `backend/modules/pex.py:578` (`_dispatch_save_findings_tool`): build the payload with the key
  folded in — `self.scratchpad.write({'key': key, 'version':'1', 'turn_number':..., 'used_count':0,
  'summary':summary, 'findings':findings, 'references_used':references_used})`.
- `backend/modules/policies/research.py:113`: `self.scratchpad.write({'key': flow.name(), ...})`
  (fold `'key'` into the existing dict literal).
- `backend/modules/policies/revise.py:205`:
  `self.scratchpad.write({'key': str(key), **entry}, writer=flow.name())`.
- `backend/modules/policies/revise.py:284`:
  `self.scratchpad.write({'key': 'propose', 'candidates':candidates, 'post_id':post_id,
  'sec_id':sec_id}, writer='propose')`.

**Read side (the PM-plan gap).** `backend/modules/policies/revise.py:32-35`
`_read_scratch_value(key)` must read the new flattened shape. Rewrite:
```
def _read_scratch_value(self, key):
    """Newest scratchpad entry stamped with this key, or ''."""
    matches = [entry for entry in self.scratchpad.read(keys=['key']) if entry['key'] == key]
    return matches[-1] if matches else ''
```
This returns the whole flattened entry (it now carries `used_count`/`candidates`/`post_id`/`sec_id`
at top level). Callers still work:
- `revise.py:202` used-count bump: `entry = self._read_scratch_value(str(key))`; `entry` is the
  flat dict, `entry['used_count'] = entry.get('used_count',0)+1` then the write at :205 above.
- `revise.py:297-304` propose: `saved = self._read_scratch_value('propose')`; the guard
  `'candidates' not in saved` and `saved['candidates']/['post_id']/['sec_id']` all read top-level
  fields — correct against the flat entry.

Tests:
- `nlu_unit_tests.py:446` `test_key_value_call_wraps_into_entry` → rewrite as
  `test_entry_dict_is_stamped_and_appended`: `write({'key':'repair','value':'bad outline'})` then
  `read()[-1] == {'key':'repair','value':'bad outline','writer':'orchestrator'}`.
- The other `TestSessionScratchpad` cases (`nlu_unit_tests.py:439-512`) already pass dict entries or
  use `write_completion` — unchanged.

Note (no guard added): in-memory `write` needs `entry['key']`; production always runs file mode
(World binds `scratchpad.jsonl` at session open, `agent.py:99`), so this is exercised only by tests
that pass a key. Per the no-defensive-code rule I do not guard the missing-key case — it crashes
loudly if a caller forgets the key.

Satisfies PM test-plan row **A9**.

## Step 8 — A10: `search_faqs` → `search_documents` + privatize internals

`backend/components/business_context.py`
- `search_faqs` (line 83) → `search_documents` (public). Body calls `self._rerank(...)`.
- `search_all` (line 60) → `_candidates`; `rerank` (line 67) → `_rerank`.

`backend/components/memory_manager.py`
- `retrieve` (lines 27-30): `search_faqs`→`search_documents`, `search_all`→`_candidates`,
  `rerank`→`_rerank`. Docstring line 5 (`memory.business.search_faqs`) → `search_documents`.

`backend/modules/pex.py:146`
- tools dict key + method: `'search_faqs': (self.memory.business, 'search_faqs')` →
  `'search_documents': (self.memory.business, 'search_documents')`.

`schemas/tools.yaml:578-581`
- Key `search_faqs:` → `search_documents:`; `tool_id: search_faqs` → `search_documents`;
  `name: "Search FAQs"` → `"Search documents"`. Keep description/schema/capabilities/timeout.

Tests:
- `mem_unit_tests.py:316, 326, 338` (`svc.search_faqs(...)` → `svc.search_documents(...)`).
- `test_retrieve_faq_shortcut` (`mem_unit_tests.py:67`) exercises `retrieve(documents=['faq'])`,
  which now routes through `search_documents` internally — assertions unchanged, still valid.

Satisfies PM test-plan row **A10**.

## Step 9 — A1: AmbiguityHandler `recognize` / `present` / `resolve`

`backend/components/ambiguity_handler.py`
- Rename `declare` (line 30) → `recognize`. Same body/signature; update the log string to
  `[ambig-trace] recognize`.
- `present` (line 39): drop the `name` param; body becomes `return self.level` (empty string when
  none). Every caller uses it as a truthy check, so `''` (none) vs a level string is safe.
- `resolve` (line 56): add `explanation:str=''`; keep clearing level/metadata/observation; log the
  explanation (`[ambig-trace] resolve was=%s explanation=%r`).
- `__init__`: add `self.nlu = None` (set by Agent in B1).

Method-call callers `.declare(` → `.recognize(` (direct code calls, not tools):
- `backend/modules/nlu.py:119, 201, 215, 228`.
- `backend/modules/pex.py:197` (`_security_check`).
- `backend/modules/policies/base.py:218`; `research.py:25,173,207`;
  `draft.py:81,128,160,162,201,248`;
  `revise.py:54,82,111,125,131,163,167,264,299`; `publish.py:92,113`.

`present()`/`resolve()` callers — behavior unchanged, no edit:
- `backend/agent.py:68` (`if self.ambiguity.present():`), `:69` and `:152` (`resolve()`).
- `backend/modules/pex.py:238, 667, 717, 744` (all truthy `present()` / no-arg `resolve()`).

Tests:
- `pex_unit_tests.py:247` `test_non_completed_returns_status_and_question`:
  `pex.ambiguity.declare(...)` → `pex.ambiguity.recognize(...)`.

Satisfies PM test-plan row **A1**.

## Step 10 — B1: `recover()` + `NLU.recover` + wiring

`backend/agent.py`
- Line 43: pass memory into NLU — `self.nlu = NLU(self.config, self.ambiguity, self.engineer,
  self.world, self.memory)`.
- After line 45 (`self.pex.nlu = self.nlu`): add `self.ambiguity.nlu = self.nlu` (same wiring
  pattern as `pex.nlu`).

`backend/modules/nlu.py`
- `__init__` (line 76): add `memory` param last — `def __init__(self, config, ambiguity, engineer,
  world, memory)`; store `self.memory = memory`.
- Add `NLU.recover` (deterministic, no LLM):
```
def recover(self):
    """Internal recovery before escalating to the user: look for the missing slot's value in L2
    preferences, then the scratchpad. On a hit, resolve the pending ambiguity and note it on the
    pad; otherwise stay pending. An LLM-judged version is designed-not-built."""
    missing = self.ambiguity.metadata.get('missing', '')
    found = self.memory.recall(missing).get(missing)
    if not found:
        for entry in self.scratchpad.read():   # file mode: list of entries, newest last
            if missing in entry:
                found = entry[missing]
                break
    self.scratchpad.write({'key': 'recovery', 'missing': missing, 'found': found}, writer='nlu')
    if found:
        self.ambiguity.resolve(explanation=f'recovered {missing}={found} without asking')
    return {'recovery': found or None}
```

`backend/components/ambiguity_handler.py`
- Add `recover(self)` → `return self.nlu.recover()`. Deterministic routing only — the reasoning
  lives in NLU, so the component never contains recovery logic (acceptance criterion).

Test fixture (the PM-plan gap):
- `nlu_unit_tests.py:33-39` `nlu` fixture: build a MemoryManager and wire the back-reference:
```
from backend.components.memory_manager import MemoryManager
from backend.components.user_preferences import UserPreferences
...
memory = MemoryManager(world.context, UserPreferences(minimal_config), None)
nlu = NLU(minimal_config, ambiguity, engineer, world, memory)
ambiguity.nlu = nlu
return nlu
```

New tests (add to `nlu_unit_tests.py`, no network — the fixture's engineer is real PromptEngineer
but recover makes no LLM call):
- **T-a** `test_present_returns_level_string`: `recognize('specific',{'missing':'x'})` →
  `present()=='specific'`; after `resolve()` → `''`.
- **T-b** `test_resolve_takes_explanation`: `resolve('found in prefs')` clears
  level/metadata/observation.
- **T-c** `test_recover_resolves_from_preference`: `recognize('partial',{'missing':'tone'})`;
  `nlu.memory.preferences.store_preference('tone','wry')`; `nlu.ambiguity.recover()` returns
  `{'recovery':'wry'}`, `present()==''`, and a `key='recovery'` entry is on the pad
  (`scratchpad.size == 1`).
- **T-d** `test_recover_stays_pending_when_nothing_found`: `recognize('partial',{'missing':'tone'})`
  with empty prefs+pad → `recover()=={'recovery':None}`, `present()=='partial'` (still set;
  the recovery entry is written but nothing resolves).

Note: the fixture pad is in-memory and empty during T-c/T-d, so recover's scratchpad scan iterates
zero entries — correct. Its non-empty in-memory scan is not exercised (production is file mode).

Satisfies PM test-plan rows **T-a..T-d** and the recover acceptance criterion.

---

## Tool-surface design (applies to steps 11-13)

Two menus, one shared pool. `get_tools_for_flow` (pex:800) prepends every
`_component_tool_definitions()` entry to a flow's own tools — so the component list IS the sub-agent
menu. `get_tools_for_orchestrator` (pex:973) is `_orchestrator_tool_definitions()` plus a named
selection of component defs plus the read-only domain allowlist.

Final `_component_tool_definitions()` set (= the sub-agent menu, matches test `_COMPONENT_TOOLS`):
`declare_ambiguity, coordinate_context, read_scratchpad, read_flow_stack, stackon_flow,
fallback_flow, execution_error, save_findings`.

Final `_orchestrator_tool_definitions()` set (= `_orchestrator_toolset` keys = `_HOT_PATH_TOOLS`):
`manage_flows, understand, append_to_scratchpad, store_preference, ask_clarification_question,
recover_from_ambiguity`.

`get_tools_for_orchestrator` component-name selection: `('coordinate_context', 'read_scratchpad')`
(drops `handle_ambiguity`, `manage_memory`). Plus `READ_ONLY_DOMAIN_TOOLS`.

Dispatch: shared component tools route through explicit `elif` branches in `_dispatch_tool`
(`declare_ambiguity`, `read_scratchpad`, `read_flow_stack`, `stackon_flow`, `fallback_flow`, and the
existing `coordinate_context`/`save_findings`). Orchestrator-only tools route through
`_orchestrator_toolset`. `read_scratchpad` is defined once (component) and reused by both menus
(decision D-A).

## Step 11 — B5 + B7 + prompt refs (scratchpad split, `manage_memory` retired)

`backend/modules/pex.py`
- Replace `_dispatch_scratchpad` (749-755) with two handlers:
  - `_dispatch_read_scratchpad(params)` → `{'_success':True, 'entries':
    self.scratchpad.read(writer=params.get('writer'), keys=params.get('keys'))}`.
  - `_dispatch_append_to_scratchpad(params)` → `self.scratchpad.write(params['entry'])`
    (writer stamped in code); return `{'_success':True, 'size': self.scratchpad.size}`.
- `_orchestrator_toolset` (161-166): drop `'scratchpad'`; add `'append_to_scratchpad':
  self._dispatch_append_to_scratchpad`. (`read_scratchpad` is NOT here — it dispatches via elif.)
- `_dispatch_tool` (468-494): add an `elif tool_name == 'read_scratchpad': return
  self._dispatch_read_scratchpad(tool_input)` branch. Delete the `manage_memory` branch (482-483)
  and delete `_dispatch_manage_memory` (762-776).
- `_guarded_call` (450-451): remove the `if '_success' not in result: result['_success'] =
  result.get('status') == 'success'` fallback and its comment. No tool returns the `{'status':...}`
  shape after `manage_memory` is gone.
- `_orchestrator_tool_definitions` (987-1094): remove the `scratchpad` def (1053-1077); add flat
  `append_to_scratchpad` (arg `entry:object`, required) — order it right after `understand` so the
  def-name order matches `_HOT_PATH_TOOLS`.
- `_component_tool_definitions` (808-971): delete the `manage_memory` def (866-878); add a flat
  `read_scratchpad` def (args `writer:string`, `keys:array[string]`; no required) reusing the
  `scratchpad` op="read" description text.
- `get_tools_for_orchestrator` (979-980): component-name list → `('coordinate_context',
  'read_scratchpad')`. Update the docstring (974-976) to name the new surface.

`backend/prompts/for_orchestrator.py`
- Line 226 (`_render_preferences`): `Promote durable ones via `manage_memory`` → `... via
  `store_preference``.
- Lines 111-115 (`TOOL_POLICY` completion-records paragraph): `scratchpad` op="read" /
  op="append" → `read_scratchpad` / `append_to_scratchpad`.

`backend/prompts/pex/flows/` — `manage_memory(...)` reads → `read_scratchpad(...)`; persistent
findings stay on `save_findings`:
- `outline.md:60`, `release.md:36`, `write.md:51`, `audit.md:39`, `rework.md:34`, and the
  `- manage_memory(**params)` / `- manage_memory(action, key, value)` menu lines in
  `find.md:30`, `compare.md:40`, `schedule.md:33`, `compose.md:90`, `cite.md:37`,
  `summarize.md:28`, `brainstorm.md:37`, `refine.md:47`, `browse.md:29`.

Tests:
- `pex_unit_tests.py:29` `_HOT_PATH_TOOLS` → `('manage_flows','understand','append_to_scratchpad',
  'store_preference','ask_clarification_question','recover_from_ambiguity')` (final order; B13 adds
  the last two — see build note below).
- `pex_unit_tests.py:75` `test_defs_cover_dispatch_registry_exactly`: stays as-is (asserts
  defs-names == `_HOT_PATH_TOOLS` and toolset keys == names).
- `pex_unit_tests.py:81` `test_orchestrator_tool_list_composition`: replace the
  `('handle_ambiguity','coordinate_context','manage_memory')` loop with the new expectation —
  `coordinate_context` and `read_scratchpad` present; assert `manage_memory` and `handle_ambiguity`
  NOT in names (keep the `call_flow_stack not in names` and no-writes assertions).
- `pex_unit_tests.py:145` `test_scratchpad_tool_routes_to_memory`: rewrite to the two tools —
  `_dispatch_tool('append_to_scratchpad', {'entry':{'finding':'intro is weak'}})` returns
  `{'_success':True,'size':1}`; `_dispatch_tool('read_scratchpad', {'writer':'orchestrator'})`
  returns the stamped entry.
- New **T-h** `test_read_and_append_scratchpad_tools`: `append_to_scratchpad` stamps writer + grows
  size; `read_scratchpad(keys=[...])` filters.
- New **T-j** `test_manage_memory_tool_is_gone`: `manage_memory` not in either menu; dispatch of
  `manage_memory` returns the unknown-tool corrective error.

Build note: because `_HOT_PATH_TOOLS` and the composition tests reference tools that B3/B4 add
(step 13), the cleanest sequence is to keep step 11's suite green by staging the `_HOT_PATH_TOOLS`
constant to match whatever set exists after step 11 (manage_flows, understand, append_to_scratchpad,
store_preference), then extend it to the full six in step 13. I will set the constant to the current
step's actual set at each of steps 11 and 13 so every step ends green.

Satisfies PM test-plan rows **B5+B7**, **T-h**, **T-j**.

## Step 12 — B6: replace `call_flow_stack` with three flat sub-agent tools

`backend/modules/pex.py`
- Replace `_dispatch_flow_stack_tool` (521-545) with three handlers (keep the existing read shapes
  and error text):
  - `_dispatch_read_flow_stack(params)`: `details ∈ {flows, slots, flow_meta}` →
    `to_list()` / `get_flow().slot_values_dict()` / `get_flow().to_dict()`; unknown `details`
    returns the corrective `invalid_input` message.
  - `_dispatch_stackon_flow(params)`: `self.flow_stack.stackon(params['flow'])`;
    return `{'_success':True,'stacked':params['flow']}`.
  - `_dispatch_fallback_flow(params)`: `self.flow_stack.fallback(params['flow'])`;
    return `{'_success':True,'fell_back_to':params['flow']}`.
- `_dispatch_tool` (484-485): replace the `call_flow_stack` branch with three `elif` branches
  (`read_flow_stack`, `stackon_flow`, `fallback_flow`).
- `_component_tool_definitions`: replace the `call_flow_stack` def (879-904) with three flat defs —
  `read_flow_stack` (arg `details` enum flows/slots/flow_meta), `stackon_flow` (arg `flow`),
  `fallback_flow` (arg `flow`).

`backend/prompts/pex/flows/` — `call_flow_stack(action=...)` →
`read_flow_stack` / `stackon_flow(flow=...)` / `fallback_flow(flow=...)`:
- reads: `outline.md:61`, `release.md:37,145`, `audit.md:40`, `rework.md:35`, `write.md:53`, and the
  `- call_flow_stack(action, details)` menu lines in `find.md:31`, `compare.md:41`,
  `schedule.md:34`, `compose.md:91`, `cite.md:38`, `summarize.md:29`, `brainstorm.md:38`,
  `refine.md:48`, `browse.md:30`.
- fallbacks: `write.md:113` (`call_flow_stack(action='fallback', details='rework')` →
  `fallback_flow(flow='rework')`), `compose.md:138` (→ `fallback_flow(flow='write')`),
  `rework.md:20` (`call_flow_stack(action='fallback', flow='write')` → `fallback_flow(flow='write')`).

Note: the POLICY-level `self.flow_stack.fallback('rework')` in `revise.py:211` is a direct code call,
not a tool — unchanged.

Tests:
- `pex_unit_tests.py:1680` `_COMPONENT_TOOLS` → `{'declare_ambiguity','coordinate_context',
  'read_scratchpad','read_flow_stack','stackon_flow','fallback_flow','execution_error',
  'save_findings'}`.
- `test_few_shot_tools_are_allowlisted` (`pex_unit_tests.py:1697`) passes once the flow `.md`
  few-shot blocks use only allowlisted names (the `_COMPONENT_TOOLS` set + flow tools).
- New **T-i** `test_flow_stack_tools_replace_call_flow_stack`: `read_flow_stack('flows')`,
  `stackon_flow('outline')`, `fallback_flow('write')` behave like the old actions.

Satisfies PM test-plan rows **B2+B6** (the `_COMPONENT_TOOLS` half) and **T-i**.

## Step 13 — B2 + B3 + B4 + B8: declare / ask / recover; `handle_ambiguity` gone

`backend/modules/pex.py`
- **B2** `declare_ambiguity` (sub-agents): replace `_dispatch_ambiguity_tool` (547-564) with
  `_dispatch_declare_ambiguity(params)` — flat `level`/`metadata`/`observation` (no `action`);
  require `level` and `metadata`; run `_validate_ambig_metadata` (67); on pass
  `self.ambiguity.recognize(level, metadata=metadata, observation=params.get('observation',''))`
  and return `{'_success':True}`; on validation failure return the `invalid_input` corrective error
  (keep the existing log line).
  - `_dispatch_tool` (478): replace the `handle_ambiguity` branch with
    `elif tool_name == 'declare_ambiguity': return self._dispatch_declare_ambiguity(tool_input)`.
  - `_component_tool_definitions`: replace the `handle_ambiguity` def (810-840) with a
    `declare_ambiguity` def — drop the `action` enum and the `present` action text; keep the
    per-level metadata description; `required: ['level','metadata']`.
- **B3** `ask_clarification_question` (orchestrator, no args):
  `_dispatch_ask_clarification(params)` → if `self.ambiguity.present()` return
  `{'_success':True, 'question': self.ambiguity.ask(active_name)}` where
  `active = self.flow_stack.get_flow()` and `active_name = active.name() if active else ''`; else
  `{'_success':False,'_error':'invalid_input','_message':'No pending ambiguity to ask about.'}`.
  Add to `_orchestrator_toolset` and a flat def in `_orchestrator_tool_definitions` (no properties).
- **B4** `recover_from_ambiguity` (orchestrator, no args): `_dispatch_recover_from_ambiguity(params)`
  → if `self.ambiguity.present()` return `{'_success':True, **self.ambiguity.recover()}`; else the
  same corrective error shape. Add to `_orchestrator_toolset` and a flat def.
- **B8** confirm no `handle_ambiguity` remains in `pex.py`: the `execution_error` def text
  (line 921 `use handle_ambiguity instead`) → `use declare_ambiguity instead`; the
  `get_tools_for_orchestrator` inclusion list already dropped it in step 11.

`backend/prompts/for_pex.py:48`
- `handle_ambiguity()` → `declare_ambiguity()` (sub-agent guidance text in `AMBIGUITY_AND_ERRORS`).

`backend/prompts/for_orchestrator.py` (`TOOL_POLICY`, lines 88-99)
- Commit rule (88-91): the orchestrator no longer declares ambiguity — reword so a
  Research/Draft/Revise/Publish turn completes when a flow ran via `manage_flows` OR a dispatched
  flow returned a clarification the orchestrator relayed. Drop `handle_ambiguity`.
- Ask-vs-proceed (92-99): relay a flow-returned `question`; use `ask_clarification_question` /
  `recover_from_ambiguity` instead of declaring. Keep the explicit-imperative-is-authorization rule.

`backend/prompts/pex/flows/` — `handle_ambiguity(...)` → `declare_ambiguity(...)` (drop any
`action='declare'`; keep flat level/metadata/observation). Files + lines:
`find.md:16,29,97`; `outline.md:47,59,160`; `compare.md:21,25,39`; `schedule.md:18,32,80`;
`release.md:22,35,136`; `write.md:27,29,50,69`; `compose.md:76,89,148`; `cite.md:18,20,36,94`;
`audit.md:38`; `summarize.md:14,27,77`; `brainstorm.md:20,36,129`; `refine.md:29,46`;
`propose.md:15,16,28,72,82`; `browse.md:15,28`.

Tests:
- `pex_unit_tests.py:29` `_HOT_PATH_TOOLS`: extend to the full six (add
  `ask_clarification_question`, `recover_from_ambiguity` after `store_preference`, in the def order).
- New **T-e** `test_declare_ambiguity_tool_recognizes`: `declare_ambiguity(level,metadata)` dispatch
  calls `recognize`; bad metadata → `invalid_input`.
- New **T-f** `test_ask_clarification_question_tool`: with a pending ambiguity returns the ask text;
  with none returns the corrective error.
- New **T-g** `test_recover_from_ambiguity_tool`: routes to `ambiguity.recover`; guarded by
  `present()`.

Satisfies PM test-plan rows **B2+B6** (the declare half), **B5+B7** (final orchestrator set),
**T-e**, **T-f**, **T-g**, and the `handle_ambiguity`-retired acceptance criterion.

---

## Acceptance criteria (from the PM plan) and how this plan meets them

- Three suites pass, zero skips — every changed name has its tests updated in the same step.
- `grep -rn "handle_ambiguity\|manage_memory\|call_flow_stack\|search_faqs\|pop_completed\|\.peek(\|
  serialize_session\|read_all\|find_turn_by_id" backend schemas` returns only new/renamed forms —
  every listed occurrence in `backend/` and `schemas/` is covered above (code, prompts, tools.yaml).
- Orchestrator/sub-agent menus match the scoped sets — enforced by `_HOT_PATH_TOOLS`,
  `_COMPONENT_TOOLS`, and the two composition tests.
- `recover()` contains no recovery reasoning — it is one line, `return self.nlu.recover()`.
- No live/paid model calls in any test — recover is deterministic; all new tests use the fake
  engineer / scripted `_call_claude` / no network.

## Files touched (summary)

Source: `backend/components/{ambiguity_handler,flow_stack/stack,session_scratchpad,user_preferences,
context_coordinator,dialogue_state,business_context,memory_manager}.py`,
`backend/modules/{pex,nlu}.py`, `backend/agent.py`,
`backend/modules/policies/{research,revise}.py`, `backend/prompts/{for_orchestrator,for_pex}.py`,
`backend/prompts/pex/flows/*.md` (15 files), `schemas/tools.yaml`.
Tests: `utils/evaluation_suite/_tests/{pex_unit_tests,nlu_unit_tests,mem_unit_tests}.py`
(incl. the `nlu` fixture in nlu_unit_tests and the `conftest.py`-shared fixtures are untouched).
