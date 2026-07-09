# SWE2 implementation plan — Round 0.1 component interface taxonomy

Normative build from the signed-off spec `round_0.1_spec.md`. I follow the PM build plan's file:line
map (it is the same ideal end-state), and add a **Normative flags** section where the minimal-diff
path would leave debt or a special case DoE should weigh. All paths under `assistants/Hugo/` unless
absolute. Style: plain language, lines to 100, no defensive guards past the LLM-input validators.

## Required call-outs

- **New concepts** — none beyond the spec. Added surface is only the redesigned ambiguity methods
  (`recognize`, `recover`) and the scoped tools the spec already lists (`declare_ambiguity`,
  `ask_clarification_question`, `recover_from_ambiguity`, `read_scratchpad`, `append_to_scratchpad`,
  `read_flow_stack`, `stackon_flow`, `fallback_flow`). Two wirings: `AmbiguityHandler.nlu`
  back-reference and a `memory` argument on `NLU.__init__`.
- **Big decisions** — three, all resolved by the PM's signed-off defaults D-1 (drop the dead
  truncate/undo revision path), D-2 (fold `serialize_session` into `read_state`), D-5 (single-dict
  scratchpad write; in-memory mode keys on `entry['key']`). I accept all three.
- **Alternatives** — kept a compatibility shim beside each retired tool (`manage_memory`,
  `call_flow_stack`, `handle_ambiguity`): rejected, dual surfaces defeat the scoped-per-caller goal
  the spec exists to reach. One atomic tool-surface commit vs three green steps: I take three steps so
  the suites stay green between them.

## Normative flags (for DoE)

1. **`recover` recovery test must run on a file-backed scratchpad.** `SessionScratchpad.read()`
   returns a dict in in-memory mode and a list in file mode. Production always binds a file path
   (`agent._ensure_session`), so `NLU.recover` iterates `read(...)` as a list. The two new recover
   tests bind a tmp `scratchpad.jsonl` to match production — do not exercise recover against the
   in-memory dict mode.
2. **In-memory scratchpad mode is now test-only.** After B7 deletes `manage_memory`, no production
   caller uses `read(key)` / the OrderedDict keyed mode. D-5 keeps it working (keys on `entry['key']`)
   so the existing in-memory unit tests pass, but the whole keyed mode is a candidate for deletion in
   a later cleanup round. Not in scope here; flagging so it is on the record.
3. **`_read_scratch_value` must switch to the flat shape (the read side of A9).** Old file-mode entry
   was `{<flow_name>: <payload>, writer: 'orchestrator'}`, so `RevisePolicy._read_scratch_value`
   (`revise.py:32-35`) filtered with `read(keys=[key])` and returned `entries[-1][key]`. After A9's
   flat `{'key': <name>, ...}` write, `read(keys=['propose'])` matches nothing: the propose pick phase
   (`revise.py:297`) always declares "options lost" and the used-count bump (`revise.py:202`) stops
   working. This reader has two live callers, so A9 (step 7) rewrites `_read_scratch_value` to match on
   `entry['key']` and return the whole entry, and adds a test that reads back a flat write. A real
   shape change forced by A9, not a rename.
4. **Removing the `{'status': ...}` fallback (B7) is correct and safe.** `_dispatch_manage_memory` was
   the only tool returning that shape; every other tool returns `_success`. Dropping the
   `if '_success' not in result` branch at `pex.py:451-452` leaves no tool uncovered.

## Confirmed sketches

`understand` keeps its name (op = read/think/contemplate). `store_preference` stays PEX's scoped
preference write. The surviving op-family parameter is `op`. No renames on these three.

---

## Group A — component-method cleanups (steps 1-9)

### A2 (step 1) — FlowStack `peek()` dropped, use `get_flow()`
`backend/components/flow_stack/stack.py`: delete `peek()` (lines 49-51); `get_flow()` already returns
top-of-stack. Replace `.peek()` → `.get_flow()` at `dialogue_state.py:203` (`_update_flow`),
`pex.py:620,642,740`, `policies/base.py:231`.
Tests: `pex_unit_tests.py:116,1763,1856,1870` and `mem_unit_tests.py:506,508` change `.peek()` →
`.get_flow()`. Satisfies test-plan row **A2**.

### A3 (step 2) — `pop_completed()` → `pop()`
`stack.py`: rename method `pop_completed` → `pop` (line 75; private `_pop` at 114 untouched).
`dialogue_state.py`: op string `'pop_completed'` → `'pop'` at line 168 docstring, 179 branch, 180
call `stack.pop()`. `pex.py:611`: drop the `'pop':'pop_completed'` remap so the `pop` op passes
straight through — keep `{'update':'update_flow'}`:
```
op = {'update': 'update_flow'}.get(params['op'], params['op'])
```
Tests: `nlu_unit_tests.py:622,669` (op `'pop'`); `pex_unit_tests.py:1575-1583` helper/comments.
Satisfies row **A3**.

### A4 + A5 (step 3) — drop `find_turn_by_id`; snake_case outliers
`context_coordinator.py`: delete `find_turn_by_id` (302-308, no callers — grep clean). Rename
`setbookmark` → `set_bookmark` (295) and `storecompleted_flows` → `store_completed_flows` (322); both
have no callers. Leave `bookmark`, `get_turn`.

### A6 (step 4) — collapse revision paths (D-1)
`context_coordinator.py`: keep `rewrite_history` (288) as the one revision entry. Delete
`revise_user_utterance` (342-351) and its only helper `_rebuild_recent` (353-359) — both dead. Drops
truncate/undo; reintroduce when an undo round needs it.

### A7 (step 5) — merge serializers (D-2)
`dialogue_state.py`: delete `serialize_session()` (117-128); move its body into `read_state()` (157)
so `read_state` builds the session document directly. Point `save()` (132) and the `write_state`
return (186) at `self.read_state()`. Keep `serialize()` (103) untouched.
Tests: `nlu_unit_tests.py:541,544` and `mem_unit_tests.py:371` → `read_state()`; leave the
`serialize()` tests (563,566). Satisfies row **A7**.

### A8 (step 6) — drop `UserPreferences.read_all()` (D-3)
`user_preferences.py`: delete `read_all()` (43-44). `read(query=None)` already returns the flat view.
Tests: `mem_unit_tests.py:536,543` read the typed record from `prefs._preferences[key]` to keep the
`endorsed`/`confidence` asserts. Satisfies row **A8**.

### A9 (step 7) — SessionScratchpad single-shape write (D-5)
`session_scratchpad.py`: `write` (23) becomes:
```
def write(self, entry:dict, writer:str='orchestrator'):
    stamped = {**entry, 'writer': writer}        # stamped by code, never trusted from LLM
    if self._scratchpad_path is None:            # in-memory (test-only) — keyed store
        key = stamped['key']
        if key in self._scratchpad:
            self._scratchpad.move_to_end(key)
        self._scratchpad[key] = stamped
        while len(self._scratchpad) > self._max_snippets:
            self._scratchpad.popitem(last=False)
        return
    with open(self._scratchpad_path, 'a', encoding='utf-8') as file:
        file.write(json.dumps(stamped) + '\n')
```
`write_completion` (59) already passes a dict — keep `self.write(record, writer=flow)`.
Write-side caller updates (key,value → one dict):
- `pex.py:578` `_dispatch_save_findings_tool`: `self.scratchpad.write({'key': key, 'version': '1',
  'turn_number': ..., 'used_count': 0, 'summary': summary, 'findings': findings,
  'references_used': references_used})`.
- `policies/research.py:113`: `write({'key': flow.name(), ...})`.
- `policies/revise.py:284`: `write({'key': 'propose', 'candidates': candidates, 'post_id': post_id,
  'sec_id': sec_id}, writer='propose')`.
Read-side updates (forced by the shape change — two live callers, per normative flag 3):
- `policies/revise.py:32-35` `_read_scratch_value(key)`: filter the flat entries by value and return
  the whole newest entry:
  ```
  def _read_scratch_value(self, key):
      """Newest scratchpad entry stored under `key` (flat single-dict shape)."""
      entries = [entry for entry in self.scratchpad.read() if entry.get('key') == key]
      return entries[-1] if entries else ''
  ```
  Callers now get the full entry dict (was the nested payload). The propose read-back
  (`revise.py:297`) still reads `saved['candidates']/['post_id']/['sec_id']` — those live at top level
  after the flat write; the `'candidates' not in saved` check still holds.
- `policies/revise.py:205` (used-count bump): the entry `_read_scratch_value` returns already carries
  `'key'`, so re-write it directly — `self.scratchpad.write(entry, writer=flow.name())` (drop the old
  `str(key)` key,value form). Line 204 (`entry.get('used_count', 0) + 1`) is unchanged.
Tests: rewrite `nlu_unit_tests.py:446` `test_key_value_call_wraps_into_entry` →
`test_entry_dict_is_stamped_and_appended` — pass a dict on the in-memory fixture and assert the
read-back carries `writer` (this is the mode the old draft dropped the stamp in) plus is appended. Add
`test_read_scratch_value_reads_flat_entry` (pex, file-backed pad via `tmp_path`): a `save_findings`-shape
flat write, then `RevisePolicy._read_scratch_value(flow_name)` returns that entry, and after the bump a
re-read shows `used_count` incremented. Satisfies row **A9** and its read side.

### A10 (step 8) — `search_faqs` → `search_documents`, privatize internals (T6 + C10)
`business_context.py`: `search_faqs` (83) → `search_documents`; `search_all` (60) → `_candidates`;
`rerank` (67) → `_rerank`; `search_documents` body calls `self._rerank(query, self._corpus, top_k)`.
`memory_manager.py`: in `retrieve` (23-30) `search_faqs`→`search_documents`, `search_all`→`_candidates`,
`rerank`→`_rerank`; docstring line 5 `search_faqs`→`search_documents`.
`pex.py:146`: tools dict key + method `'search_faqs'` → `'search_documents'`.
`schemas/tools.yaml:578-581`: `search_faqs:` key + `tool_id` + `name` → `search_documents`
("Search documents"); keep schema/capabilities.
Tests: `mem_unit_tests.py:316,326,338` → `search_documents`; `test_retrieve_faq_shortcut:67` unchanged
(still routes `documents=['faq']`). Satisfies row **A10**.

### A1 (step 9) — Ambiguity Handler redesign (C7)
`ambiguity_handler.py`:
- `__init__` (16): add `self.nlu = None` (wired by agent; used by `recover`).
- Rename `declare` → `recognize` (30); same body/signature.
- `present()` (39): drop the `name` param; `return self.level` (empty string = none):
  ```
  def present(self):
      return self.level
  ```
- `resolve()` (56): add `explanation:str=''`; keep clearing level/metadata/observation; log the
  explanation:
  ```
  def resolve(self, explanation:str=''):
      log.info('[ambig-trace] resolve was=%s explanation=%r', self.level, explanation)
      self.level = ''; self.metadata = {}; self.observation = ''
  ```
Rename every direct `declare(` caller → `recognize(`: `nlu.py:119,201,215,228`; `pex.py:197`
(`_security_check`); `policies/base.py:218`; `research.py:25,173,207`;
`draft.py:81,128,160,162,201,248`; `revise.py:54,82,111,125,131,163,167,264,299`;
`publish.py:92,113`. `present()`/`resolve()` code callers (`agent.py:68,69,152`;
`pex.py:238,667,717,744`) keep working — every one is a truthy check or a bare `resolve()`.
Tests: `pex_unit_tests.py:243` `test_non_completed_returns_status_and_question` (`declare`→`recognize`).
Satisfies row **A1**.

---

## Group B — tool surface + ambiguity behavior (steps 10-13)

### B1 (step 10) — `recover()` + NLU recovery method + wiring
`agent.py`: pass `self.memory` into `NLU(...)` (43); after `self.pex.nlu = self.nlu` (45) add
`self.ambiguity.nlu = self.nlu`.
`nlu.py`: `__init__` (76) gains `memory`; store `self.memory = memory`. Add `NLU.recover()`
(deterministic — no LLM this round):
```
def recover(self):
    missing = self.ambiguity.metadata.get('missing', '')
    found = self.memory.recall(missing).get(missing)     # L2 preference match
    if not found:
        for entry in self.scratchpad.read(keys=[missing]):  # file-backed in production
            found = entry[missing]; break
    self.scratchpad.write({'key': 'recovery', 'missing': missing, 'found': found}, writer='nlu')
    if found:
        self.ambiguity.resolve(explanation=f'recovered {missing}={found} from memory')
    return {'recovery': found}
```
`ambiguity_handler.py`: add `recover()` — routing only, no reasoning (acceptance criterion):
```
def recover(self):
    return self.nlu.recover()
```
Test-fixture change: the NLU fixture in `nlu_unit_tests.py:24-39` must build a `MemoryManager`
(`MemoryManager(world.context, UserPreferences(config), BusinessContext(engineer))`) and pass it into
`NLU(...)`. Satisfies new tests **T-c, T-d** (and unblocks all NLU tests under the new signature).

### B2 (step 13) — `declare_ambiguity` tool (sub-agents) replaces `handle_ambiguity`
`pex.py`: replace `_dispatch_ambiguity_tool` (547-564) with a flat handler (no `action`):
```
def _dispatch_declare_ambiguity(self, params:dict) -> dict:
    level, metadata = params['level'], params['metadata']
    err = _validate_ambig_metadata(level, metadata)
    if err:
        log.info('[ambig-trace] declare_ambiguity REJECTED level=%s err=%s', level, err)
        return {'_success': False, '_error': 'invalid_input', '_message': err}
    self.ambiguity.recognize(level, metadata=metadata, observation=params.get('observation', ''))
    return {'_success': True}
```
`_dispatch_tool` (478): branch `handle_ambiguity` → `declare_ambiguity`.
`_component_tool_definitions` (810-840): replace the def — name `declare_ambiguity`, drop the
`action` enum, keep the per-level metadata description; `required: ['level', 'metadata']`.

### B3 (step 13) — `ask_clarification_question` tool (orchestrator)
`pex.py` new handler:
```
def _dispatch_ask_clarification(self, params:dict) -> dict:
    if self.ambiguity.present():
        flow = self.flow_stack.get_flow()
        return {'_success': True, 'question': self.ambiguity.ask(flow.name() if flow else '')}
    return {'_success': False, '_error': 'invalid_input',
            '_message': 'No pending ambiguity to ask about.'}
```
Add `'ask_clarification_question'` to `_orchestrator_toolset` (161) and a no-arg def to
`_orchestrator_tool_definitions` (987).

### B4 (step 13) — `recover_from_ambiguity` tool (orchestrator)
`pex.py` new handler:
```
def _dispatch_recover_ambiguity(self, params:dict) -> dict:
    if self.ambiguity.present():
        return {'_success': True, **self.ambiguity.recover()}
    return {'_success': False, '_error': 'invalid_input',
            '_message': 'No pending ambiguity to recover.'}
```
Add `'recover_from_ambiguity'` to `_orchestrator_toolset` and a no-arg def.

### B5 (step 11) — split orchestrator scratchpad tool
`pex.py`: replace `_dispatch_scratchpad` (749-755) with two handlers:
```
def _dispatch_read_scratchpad(self, params:dict) -> dict:
    entries = self.scratchpad.read(writer=params.get('writer'), keys=params.get('keys'))
    return {'_success': True, 'entries': entries}

def _dispatch_append_scratchpad(self, params:dict) -> dict:
    self.scratchpad.write(params['entry'])       # writer stamped in code
    return {'_success': True, 'size': self.scratchpad.size}
```
`read_scratchpad` is the one tool both callers share, so it follows the existing borrow direction
(orchestrator borrows from the component menu). Its def lives once in `_component_tool_definitions`
(B7) and it dispatches through a `_dispatch_tool` branch (`elif tool_name == 'read_scratchpad'`) — the
same shape as `coordinate_context`. `append_to_scratchpad` is orchestrator-only (sub-agents write via
`save_findings`), so its def goes in `_orchestrator_tool_definitions` and its handler in
`_orchestrator_toolset`.
`_orchestrator_toolset` (161): drop `'scratchpad'`, add `'append_to_scratchpad'` only (read is a
`_dispatch_tool` branch, not a toolset entry).
`_dispatch_tool` (468): add `elif tool_name == 'read_scratchpad': return
self._dispatch_read_scratchpad(tool_input)` — one branch serves both the orchestrator (borrowed def)
and sub-agents.
`_orchestrator_tool_definitions` (1053-1077): replace the `scratchpad` def with the flat
`append_to_scratchpad` def only.
This keeps `test_defs_cover_dispatch_registry_exactly` true (`_orchestrator_tool_definitions` names ==
`_orchestrator_toolset` keys) and leaves exactly one `read_scratchpad` def object (the DoE fix).

### B6 (step 12) — replace `call_flow_stack` (sub-agents) with three flat tools
`pex.py`: replace `_dispatch_flow_stack_tool` (521-545) with three handlers keeping the existing read
shapes:
```
def _dispatch_read_flow_stack(self, params:dict) -> dict:
    details = params.get('details', 'flows')
    if details == 'slots':
        return {'_success': True, 'slots': self.flow_stack.get_flow().slot_values_dict()}
    if details == 'flow_meta':
        return {'_success': True, 'flow': self.flow_stack.get_flow().to_dict()}
    if details == 'flows':
        return {'_success': True, 'flows': self.flow_stack.to_list()}
    return {'_success': False, '_error': 'invalid_input',
            '_message': f"details must be 'flows', 'slots', or 'flow_meta'; got {details!r}"}

def _dispatch_stackon_flow(self, params:dict) -> dict:
    self.flow_stack.stackon(params['flow']); return {'_success': True, 'stacked': params['flow']}

def _dispatch_fallback_flow(self, params:dict) -> dict:
    self.flow_stack.fallback(params['flow']); return {'_success': True, 'fell_back_to': params['flow']}
```
`_dispatch_tool` (484): replace the `call_flow_stack` branch with three name branches.
`_component_tool_definitions` (879-904): replace the `call_flow_stack` def with three flat defs —
`read_flow_stack` keeps `details` ∈ {flows,slots,flow_meta}; `stackon_flow`/`fallback_flow` take a
`flow` string.

### B7 (step 11) — retire `manage_memory`; add `read_scratchpad` to the sub-agent menu
`pex.py`: delete `_dispatch_manage_memory` (762-776) and its `_dispatch_tool` branch (482-483). In
`_guarded_call` remove the status-contract fallback (451-452) and its comment.
`get_tools_for_orchestrator` (978-980): the borrow list becomes `('coordinate_context',
'read_scratchpad')` — drop `'manage_memory'` (B8 already drops `'handle_ambiguity'`), so the
orchestrator borrows the one `read_scratchpad` def from the component menu.
`_component_tool_definitions` (866-878): delete the `manage_memory` def and add the `read_scratchpad`
def here — this is the single def object B5 dispatches and the orchestrator borrows; sub-agent writes
stay on `save_findings`.

### B8 (step 13) — finish `handle_ambiguity` retirement
Confirm no `handle_ambiguity` remains in `pex.py` (def, dispatch, orchestrator inclusion list). The
orchestrator ambiguity surface is `ask_clarification_question` + `recover_from_ambiguity`; sub-agents
use `declare_ambiguity`.

---

## Group C — prompt updates

### C-md (steps 11-13) — flow prompt `.md` files (`backend/prompts/pex/flows/`)
Mechanical renames from the grep inventory:
- `handle_ambiguity(...)` → `declare_ambiguity(...)` (drop any `action='declare'`; flat
  level/metadata): find.md:16,29,97; outline.md:47,59,160; compare.md:21,25,39; schedule.md:18,32,80;
  release.md:22,35,136; write.md:27,29,50,69; compose.md:76,89,148; cite.md:18,20,36,94; audit.md:38;
  summarize.md:14,27,77; brainstorm.md:20,36,129; refine.md:29,46; propose.md:15,16,28,72,82;
  browse.md:15,28,94.
- `manage_memory(...)` → `read_scratchpad(...)` (reads; persistent findings still via `save_findings`):
  outline.md:60; release.md:36; write.md:51; audit.md:39; rework.md:34; and the `- manage_memory(**params)`
  menu lines in find/compare/schedule/compose/cite/summarize/brainstorm/refine/browse.
- `call_flow_stack(action=...)` → `read_flow_stack` / `stackon_flow(flow=...)` / `fallback_flow(flow=...)`:
  reads — outline.md:61; release.md:37,145; audit.md:40; rework.md:35; write.md:53; and the menu lines.
  fallbacks — write.md:113; compose.md:138; rework.md:20.
- `coordinate_context(...)` stays (write.md:52; propose.md:29,91) — out of scope.

### C-orch (step 11 + 13) — `backend/prompts/for_orchestrator.py`
- Line 226: "Promote durable ones via `manage_memory`" → "…via `store_preference`" (step 11).
- Line 113: name `read_scratchpad` / `append_to_scratchpad` (step 11).
- Lines 88-99 `TOOL_POLICY` (step 13): reword the commit rule so the turn completes when a flow ran OR
  a dispatched flow returned a clarification the orchestrator relayed; reword "Ask vs. proceed" to
  relay a flow-returned `question` and use `ask_clarification_question` / `recover_from_ambiguity`
  rather than declaring.

### C-pex (step 13) — `backend/prompts/for_pex.py:48`
`handle_ambiguity()` → `declare_ambiguity()` (sub-agent guidance text).

---

## Build order (each step ends green)
Run after every step: `pytest utils/evaluation_suite/_tests/pex_unit_tests.py mem_unit_tests.py
nlu_unit_tests.py` (cwd + `sys.path[0]` = `assistants/Hugo`; conftest handles it). `model_tests.py`
is live-model, excluded.

1. A2 · 2. A3 · 3. A4+A5 · 4. A6 · 5. A7 · 6. A8 · 7. A9 · 8. A10 · 9. A1 · 10. B1 ·
11. B5+B7 + C-md manage_memory refs + C-orch scratchpad/preference refs ·
12. B6 + C-md flow-stack refs · 13. B2+B3+B4+B8 + C-md ambiguity refs + C-pex + C-orch commit reword.

Steps 1-10 are independent; 11-13 depend on A1/B1 and share test files, so keep their order.

---

## Test updates + additions

Existing test-file edits (shared harness updates land with the step above):
- `pex_unit_tests.py:29` `_HOT_PATH_TOOLS` → `('manage_flows', 'understand', 'append_to_scratchpad',
  'store_preference', 'ask_clarification_question', 'recover_from_ambiguity')` (steps 11+13). These are
  the orchestrator's own defs == `_orchestrator_toolset` keys. `read_scratchpad` is NOT here — it is a
  borrowed component def, checked by the composition test below.
- `pex_unit_tests.py:81` `test_orchestrator_tool_list_composition`: borrowed component names checked =
  {`coordinate_context`, `read_scratchpad`}; assert no `manage_memory`, no `handle_ambiguity`, no
  `call_flow_stack`.
- `pex_unit_tests.py:75` `test_defs_cover_dispatch_registry_exactly`: defs == `_HOT_PATH_TOOLS`.
- `pex_unit_tests.py:145` `test_scratchpad_tool_routes_to_memory` → drive `append_to_scratchpad` /
  `read_scratchpad`.
- `pex_unit_tests.py:1680` `_COMPONENT_TOOLS` → {`declare_ambiguity`, `coordinate_context`,
  `read_scratchpad`, `read_flow_stack`, `stackon_flow`, `fallback_flow`, `execution_error`,
  `save_findings`}. Satisfies rows **B5+B7**, **B2+B6**.

New tests (fake engineer / queued `_call_claude`, no network):
| # | Test (file) | Asserts |
|---|---|---|
| T-a | `test_present_returns_level_string` (nlu) | `recognize('specific',{'missing':'x'})` → `present()=='specific'`; after `resolve()` → `''` |
| T-b | `test_resolve_takes_explanation` (nlu) | `resolve('found in prefs')` clears level/metadata/observation |
| T-c | `test_recover_resolves_from_preference` (nlu) | file-backed pad; recognize partial-missing slot; matching `store_preference`; `ambiguity.recover()` writes a recovery entry and `present()`→`''` |
| T-d | `test_recover_stays_pending_when_nothing_found` (nlu) | empty prefs+pad → `{'recovery':None}`, `present()` still set, and a recovery entry (`found`=None) is still appended (write runs on every attempt) |
| T-e | `test_declare_ambiguity_tool_recognizes` (pex) | `declare_ambiguity(level,metadata)` calls recognize; bad metadata → `invalid_input` |
| T-f | `test_ask_clarification_question_tool` (pex) | pending → ask text; none → corrective error |
| T-g | `test_recover_from_ambiguity_tool` (pex) | routes to `ambiguity.recover`; guarded by `present()` |
| T-h | `test_read_and_append_scratchpad_tools` (pex) | append stamps writer + grows size; read filters by keys |
| T-i | `test_flow_stack_tools_replace_call_flow_stack` (pex) | `read_flow_stack('flows')`, `stackon_flow('outline')`, `fallback_flow('write')` behave like old actions |
| T-j | `test_manage_memory_tool_is_gone` (pex) | `manage_memory` in no menu; dispatch → unknown-tool corrective error |
| T-k | `test_read_scratch_value_reads_flat_entry` (pex, file pad) | flat `save_findings`-shape write → `RevisePolicy._read_scratch_value(flow_name)` returns it; after the used-count bump a re-read shows `used_count` incremented (catches the A9 read-side break) |

## Acceptance verification
- Three suites pass, zero skips.
- `grep -rn "handle_ambiguity\|manage_memory\|call_flow_stack\|search_faqs\|pop_completed\|\.peek(\|
  serialize_session\|read_all\|find_turn_by_id" backend schemas` returns only new/renamed forms.
- Orchestrator + sub-agent menus match the spec's scoped lists (composition tests).
- `AmbiguityHandler.recover()` body is one line — `return self.nlu.recover()` — no reasoning.
- No live/paid model call in any test.
