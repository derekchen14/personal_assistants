# Round 0.1 QA verdict

Ran from `assistants/Hugo` (cwd + `sys.path[0]`), per the test cwd rule.

```
pytest utils/evaluation_suite/_tests/pex_unit_tests.py \
       utils/evaluation_suite/_tests/mem_unit_tests.py \
       utils/evaluation_suite/_tests/nlu_unit_tests.py
```
Result: **248 passed, 0 failed, 0 skipped** (1 unrelated deprecation warning from `google.genai`).
`model_tests.py` not run — live-model, excluded by the build plan.

Retired-name grep (backend + schemas):
```
grep -rn "handle_ambiguity\|manage_memory\|call_flow_stack\|search_faqs\|pop_completed\|\.peek(\|
serialize_session\|read_all\|find_turn_by_id" backend schemas
```
Result: **no matches.** Also checked `ambiguity.declare` / `handle_ambiguity` bare and
`action='declare'` shapes — none found.

## Verdict table(Research, Draft, Revise, Publish)

| Criterion | Pass/Fail | Evidence |
|---|---|---|
| Three suites pass, zero skips | PASS | 248 passed, 0 skipped, 0 failed (run above) |
| A1 — Ambiguity Handler redesign (recognize/present/resolve) | PASS | `ambiguity_handler.py:30` `recognize`, `:39` `present` returns `self.level` no `name` param, `:56` `resolve(explanation='')`; all method callers updated (`nlu.py`, `pex.py`, `policies/base.py`, `research.py`, `draft.py`, `revise.py`, `publish.py`) — grep for bare `declare(` found none; `test_present_returns_level_string`, `test_resolve_takes_explanation` pass |
| A2 — `peek()` dropped, `get_flow()` used | PASS | `stack.py` has no `peek` method (only `get_flow`); `test_manage_flows_stacks_and_saves` etc. pass |
| A3 — `pop_completed` renamed to `pop` | PASS | `stack.py:71 def pop`; `pex.py:600` op remap keeps only `{'update':'update_flow'}`, no `pop` remap; `test_manage_flows_pop_clears_the_stack` passes |
| A4 — `find_turn_by_id()` dropped | PASS | grep of `context_coordinator.py` shows no `find_turn_by_id`; only `get_turn` remains |
| A5 — snake_case `set_bookmark`/`store_completed_flows` | PASS | `context_coordinator.py:295 set_bookmark`, `:314 store_completed_flows` |
| A6 — revision paths collapsed (D-1) | PASS | `rewrite_history` (line 288) is the sole revision entry; `revise_user_utterance`/`_rebuild_recent` grep for zero matches |
| A7 — serializer merge (D-2) | PASS | `dialogue_state.py` has `serialize` (103), `save` (117, calls `read_state`), `read_state` (144); no `serialize_session`; `test_round_trip_identical_dict`, `test_open_session_rehydrates` pass |
| A8 — `read_all()` dropped (D-3) | PASS | `user_preferences.py` has only `read(query=None)`; `TestUserPreferences::test_bare_string_stores_endorsed_full_confidence` / `test_dict_stores_typed_record` pass reading `prefs._preferences[key]` |
| A9 — scratchpad single-shape `write(entry)` | PASS | `session_scratchpad.py:23 def write(self, entry:dict, writer:str='orchestrator')`; every caller (`pex.py:566`, `:743`, `nlu.py:159`, `research.py:113`, `revise.py:205,284`) passes a dict; `test_entry_dict_is_stamped_and_appended` passes |
| A10 — `search_faqs` → `search_documents`, internals privatized | PASS | `business_context.py` has `search_documents` (public), `_candidates`, `_rerank`; `memory_manager.py:retrieve` calls the renamed methods; `pex.py` tools dict and `schemas/tools.yaml:578` use `search_documents`; `TestBusinessContext` + `test_retrieve_faq_shortcut` pass |
| B1 — `recover()` + NLU wiring | PASS | `agent.py:43` passes `self.memory` into `NLU(...)`, `:46` sets `self.ambiguity.nlu = self.nlu`; `ambiguity_handler.py:44-47 recover()` is a one-line delegate `return self.nlu.recover()` — no reasoning in the component; `nlu.py:148 def recover()` implements the memory+scratchpad lookup; `test_recover_resolves_from_preference`, `test_recover_stays_pending_when_nothing_found` pass |
| B2 — `declare_ambiguity` tool replaces `handle_ambiguity` | PASS | `pex.py:544 _dispatch_declare_ambiguity` — flat `level`/`metadata`, no `action`; validates via `_validate_ambig_metadata`; dispatch branch at `:478`; tool def at `:801`; `test_declare_ambiguity_tool_recognizes` passes |
| B3 — `ask_clarification_question` tool | PASS | handler present, dispatched via `_orchestrator_toolset` (`:166`) and defined at `:1088`; `test_ask_clarification_question_tool` passes |
| B4 — `recover_from_ambiguity` tool | PASS | handler at `_orchestrator_toolset` (`:167`), def at `:1098`; `test_recover_from_ambiguity_tool` passes |
| B5 — scratchpad tool split | PASS | `_orchestrator_toolset` has `append_to_scratchpad` (`:164`); `read_scratchpad` shared via the component-tool menu (`get_tools_for_orchestrator` line ~984); `_dispatch_read_scratchpad` (`:738`); `test_read_and_append_scratchpad_tools` passes |
| B6 — `call_flow_stack` replaced by three flat tools | PASS | `_dispatch_read_flow_stack`/`_dispatch_stackon_flow`/`_dispatch_fallback_flow` (pex.py:525-542), dispatched at `:484-489`, defs at `:870,886,898`; `test_flow_stack_tools_replace_call_flow_stack` passes |
| B7 — `manage_memory` retired both surfaces + status-contract fallback removed | PASS | grep finds zero `manage_memory` refs in `pex.py`; `_guarded_call` (`:428-454`) indexes `result['_success']` directly, no `if '_success' not in result` fallback; `test_manage_memory_tool_is_gone` passes |
| B8 — `handle_ambiguity` fully retired | PASS | zero matches anywhere in `backend`/`schemas`; orchestrator surface is `ask_clarification_question` + `recover_from_ambiguity`; sub-agent surface is `declare_ambiguity` |
| C-md — flow prompt `.md` renames | PASS | every listed flow file (find, outline, compare, schedule, release, write, compose, cite, audit, summarize, brainstorm, refine, propose, browse) contains `declare_ambiguity`; `read_scratchpad`/`read_flow_stack`/`stackon_flow`/`fallback_flow` present where the plan calls for them; `test_few_shot_tools_are_allowlisted` passes |
| C-orch — `for_orchestrator.py` reword | PASS | line ~228 says "via `store_preference`"; lines ~95-96/115-116 name `recover_from_ambiguity`, `ask_clarification_question`, `read_scratchpad`, `append_to_scratchpad` |
| C-pex — `for_pex.py:48` rename | PASS | line 48 reads `declare_ambiguity()` (was `handle_ambiguity()`) |
| Orchestrator/sub-agent tool menus match section 5 exactly | PASS | `test_defs_cover_dispatch_registry_exactly`, `test_orchestrator_tool_list_composition`, `test_few_shot_tools_are_allowlisted` (against `_COMPONENT_TOOLS` = declare_ambiguity, coordinate_context, read_scratchpad, read_flow_stack, stackon_flow, fallback_flow, execution_error, save_findings) all pass |
| `recover()` never contains recovery reasoning | PASS | `ambiguity_handler.py` `recover()` body is exactly `return self.nlu.recover()`; all reasoning (`memory.recall`, scratchpad read, `ambiguity.resolve`) lives in `nlu.py:148-161` |
| No live/paid model call in any test | PASS (by inspection) | new tests (T-a..T-j) use `_FakeEngineer` / queued `_call_claude` fixtures consistent with existing suite pattern; no network calls observed in the 2.6s run time for 248 tests |

## Retired-name leftovers

None. The combined grep (`handle_ambiguity`, `manage_memory`, `call_flow_stack`, `search_faqs`,
`pop_completed`, `.peek(`, `serialize_session`, `read_all`, `find_turn_by_id`) across `backend` and
`schemas` returns zero matches. Separately checked `ambiguity.declare` / bare `declare(` /
`action='declare'` shapes — zero matches.

## Needs live (not run — would make paid LLM calls)

- `model_tests.py` (excluded by the build plan; live-model contract tests).
- Any E2E/trace runs through the full agent loop that would call a live model.

All other acceptance criteria in the build plan are deterministic and were checked above.
