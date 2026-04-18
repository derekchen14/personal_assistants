# helper_ref.md — Component-First Helper Inventory

Every capability Hugo needs to operate likely already lives somewhere. Ask **which component owns this?** before writing new code. Existing components cover ~80% of functionality; `BasePolicy` covers the remaining ~20% of flow-specific orchestration. Signatures below are `name  →  purpose  (file:line)`.

## 1. PromptEngineer — focused LLM interface

`backend/components/prompt_engineer.py` contains 7 core methods.

1. Standard pattern: 
```python
prompt = build_*_prompt(...)
raw_output = self.engineer(prompt, '<task_name>')
parsed = self.engineer.apply_guardrails(raw_output)
```
self.engineer() also takes in parameters for `model` and `max_tokens` when deviating from defaults.
Modules import `build_*_prompt` helpers directly from `backend/prompts/`.
Use `raw_output` before parsing, with meaningful name (`parsed`, `pred_slots`, `verdict`, `cleaned`, `repaired`, etc.) after.

Special LLM calls:
2. `skill_call(flow, convo_history, scratchpad, skill_name=None, skill_prompt=None, resolved=None, max_tokens=1024) -> str`  →  skill execution WITHOUT tools (sibling of tool_call). Loads `prompts/skills/<skill_name or flow.name()>.md`, builds `[system, user]`, returns LLM text. Pass `skill_prompt=` to override the loaded template.
3. `tool_call(flow, convo_history, scratchpad, tool_defs, dispatcher, skill_name=None, skill_prompt=None, resolved=None, max_tokens=4096) -> tuple[str, list[dict]]`  →  skill execution WITH tools (sibling of skill_call). Same skill-assembly API; adds `tool_defs` and `dispatcher` for the agentic loop.
4. `stream(prompt:str, task='skill', model='sonnet', max_tokens=4096)`  →  async token streaming (future scaffolding).

Output parsing (dispatched via `apply_guardrails`):
5. `apply_guardrails(text, format='json', shape=None)`  →  router. Strips fences, dispatches to:
  * `_parse_json(text) -> dict | None`  →  JSON parse with fallback regex for embedded `{}`.
  * `_parse_sql(text) -> str`  →  strip whitespace, return cleaned SQL (stub for Dana).
  * `_parse_markdown(text, shape)`  →  `shape='outline'` extracts `##` sections; `shape='candidates'` parses `### Option N / ## Section`.

File I/O + tool-log helpers:
6. `load_skill_template(flow_name) -> str | None`  →  reads `backend/prompts/skills/<flow_name>.md`.
7. `extract_tool_result(tool_log, tool_name) -> dict`  →  first successful result for a given tool; strips underscore-prefixed keys.

Instance attribute: `persona` (public) — `dict` loaded from `config.persona`. For the persona-based system prompt, call `build_system(engineer.persona)` directly from `prompts/general.py`.

Class constant: `_SKILL_DIR` → `backend/prompts/skills/`. Task suffixes in `_TASK_SUFFIXES` (module-level) map each `task` label to a system-prompt suffix: `classify_intent`, `detect_flow`, `fill_slots`, `contemplate`, `repair_slot`, `skill`, `naturalize`, `quality_check`, `clarify`.

**Prompt compilation is NOT a PromptEngineer concern.** The `backend/prompts/` module owns prompt-text compilation; consumer modules import what they need:
- NLU owns `_detect_flow_prompt`, `_fill_slot_prompt`, `_contemplate_prompt` (all >2 lines of real work). `build_intent_prompt` is called inline at its one use site.
- BasePolicy owns `_build_skill_prompt`.
- RES inlines `get_naturalize_prompt` at the naturalize call site.
- AmbiguityHandler inlines `build_clarification` from `prompts/for_res.py`.

## 2. DialogueState — beliefs + flags

`backend/components/dialogue_state.py` contains 3 core methods and 11 attributes.

1. `update(pred_intent, flow_name, confidence)`  →  also increments `turn_count`, resets `keep_going`/`has_issues`  (:23)
2. `serialize() -> dict`  (:49)
3. `from_dict(data, config)` (classmethod)  (:65)

Attributes: `pred_intent`, `flow_name`, `confidence`, `pred_flows`, `turn_count`, `keep_going`, `has_issues`, `has_plan`, `structured_plan`, `natural_birth`, `active_post`.

## 3. FlowStack — flow lifecycle

`backend/components/flow_stack/stack.py` contains 6 core methods.

1. `stackon(flow_name, plan_id=None) -> BaseFlow`  →  instantiate + push; slots NOT filled here  (:20)
2. `fallback(flow_name) -> BaseFlow`  →  replace top of stack with a different flow  (:25)
3. `peek() -> BaseFlow | None`  (:37)
4. `get_flow(status=None) -> BaseFlow | None`  →  top of stack by default; pass `status='Active'` etc. only when the caller truly distinguishes lifecycle  (:41)
5. `find_by_name(flow_name) -> BaseFlow | None`  →  skips completed/invalid  (:49)
6. `pop_completed() -> list[BaseFlow]`  →  pops both Completed and Invalid from top; returns only Completed. Called by `RES.start()` every turn  (:58)

Serialization (non-core): `to_list() -> list[dict]`  (:76).

## 4. ContextCoordinator — turns + checkpoints

`backend/components/context_coordinator.py` contains 7 core methods.

1. `add_turn(speaker, text, turn_type) -> Turn`  →  `turn_type` ∈ `utterance` / `action` / `system` / `clarification` / `agent_response`  (:55)
2. `compile_history(look_back=5, keep_system=True) -> str`  →  canonical name for the string history consumed by prompts  (:66)
3. `full_conversation(keep_system=True, as_turns=False) -> list`  (:75)
4. `recent_turns(count=3) -> list[Turn]`  (:85)
5. `get_turn(turn_id) -> Turn | None`  (:89)
6. `save_checkpoint(label, data=None)`  (:95)
7. `get_checkpoint(label) -> dict | None`  (:103)

Properties: `turn_count` (:119), `last_user_text` (:123), `last_user_turn` (:130).

Extended (turn rewriting + search + lifecycle):
- `reset()`  →  session lifecycle; clear all turns and checkpoints  (:109)
- `rewrite_history(revised)`  →  revise the most recent user utterance in place  (:138)
- `setbookmark(speaker='')`  (:145)
- `find_turn_by_id(turn_id, clearbookmark=False)`  (:152)
- `contains_keyword(keyword, look_back=3) -> bool`  →  splits on space/hyphen/underscore  (:160)
- `find_action_by_name(action_name) -> Turn | None`  (:175)
- `actions_include(target_actions, speaker='Agent') -> bool`  (:182)
- `add_actions(actions, actor)`  (:186)
- `revise_user_utterance(turns_back)`  →  truncate history to nth-back user turn  (:192)

`Turn`: `speaker`, `text`, `turn_type`, `turn_id`, `timestamp`, `is_revised`, `original`; methods `action_target()`, `add_revision(new_text)`, `utt(as_dict=False)`.

## 5. DisplayFrame — turn output container

`backend/components/display_frame.py` contains 5 core methods and 5 attributes.

`DisplayFrame` attributes: `origin`, `metadata`, `blocks`, `code`, `thoughts`. **Never add more.**

1. `set_frame(origin='', blocks=[], new_data={})`  →  merges blocks + metadata  (:30)
2. `add_block(block_data)`  →  auto-routes `form/confirmation/toast` to `top`, others to `bottom`  (:37)
3. `clear()`  (:51)
4. `compose(block, data) -> dict`  →  build a frontend-shaped block dict  (:58)
5. `to_dict() -> dict`  (:65)

`BuildingBlock`: `block_type`, `data`, `location`; `to_dict()`.

Valid block types: `card`, `form`, `confirmation`, `toast`, `default`, `selection`, `list`.

## 6. AmbiguityHandler — clarification lifecycle

`backend/components/ambiguity_handler.py` contains 7 core methods.

Four levels: `general`, `partial`, `specific`, `confirmation` (`schemas/ontology.py:AmbiguityLevel`).

1. `declare(level, metadata=None, observation=None, generation=None)`  →  start a clarification round  (:34)
2. `present() -> bool`  →  is a clarification pending?  (:45)
3. `ask() -> str`  →  phrase the user-facing question  (:48)
4. `generate() -> str`  →  LLM-based clarification when `generation` flags are set  (:67)
5. `resolve()`  →  clear state  (:77)
6. `needs_clarification(confidence) -> bool`  →  threshold check against NLU confidence  (:82)
7. `should_escalate() -> bool`  →  true when total declared rounds ≥ max_turns  (:85)

Properties: `level` (:90), `metadata` (:94), `observation` (:98).

## 7. MemoryManager — 3-tier cache

`backend/components/memory_manager.py` contains 9 core methods.

- Scratchpad (L1, session-scoped):
  1. `write_scratchpad(key, value)` (:22)
  2. `read_scratchpad(key=None)` returns str-or-dict (:29)
  3. `clear_scratchpad()` (:34), property `scratchpad_size` (:38).
- Preferences (L2, per-user in-memory):
  4. `read_preference(key, default='')` (:46)
  5. `write_preference(key, value)` (:49).
- Long-term (L3, per-user in DB):
  6. `read_long_term(key)` (:54),
  7. `write_long_term(key, value)` (:57).
- Other:
  8. `dispatch_tool(action, params)`  →  component-tool interface consumed by PEX `manage_memory`  (:59)
  9. `should_summarize(turn_count) -> bool`  →  checkpoint trigger from config  (:54)

## 8. BaseFlow — flow contract + slot filling

`backend/components/flow_stack/parents.py`

Core flow API:
- Property `intent`  →  `self.parent_type`  (:23)
- `name(full=False) -> str`  →  `'create'` or `'Draft(create)'`  (:30)
- `is_complete()` (:46), `is_filled()` (:49)
- `fill_slots_by_label(labels: dict) -> bool`  →  System-1 targeted single-slot fill from PEX label extraction. Routes entity values through `validate_entity`  (:58)
- `fill_slot_values(values: dict)`  →  transfer prediction values onto slot objects; aliases `title→target`, `post/post_id→source`  (:74)
- `slot_values_dict() -> dict`  →  only filled / non-empty slots  (:136)
- `to_dict() -> dict`  (:144)
- `validate_entity(entity)`  →  add entity to the primary grounding slot; override in domain parents for validation  (:152)
- `entity_values(size=False)`  →  values of `self.slots[self.entity_slot]`  (:157)
- `needs_to_think() -> bool`  (:161)
- `match_action(action_name) -> bool`  →  starts-with `self.parent_type.upper()`  (:166)

Attributes every flow has: `slots`, `tools`, `interjected`, `is_newborn`, `is_uncertain`, `fall_back`, `stage`, `entity_slot` (default `'source'`), `flow_id`, `plan_id`, `turn_ids`, `status` ∈ `Pending / Active / Completed / Invalid`.

Parent classes (each sets `parent_type` only): `InternalParentFlow` (also sets `interjected=True`), `ResearchParentFlow`, `DraftParentFlow`, `ReviseParentFlow`, `PublishParentFlow`, `ConverseParentFlow`, `PlanParentFlow`.

## 9. Slot hierarchy — by type

`backend/components/flow_stack/slots.py`

Every slot has: `filled`, `uncertain`, `criteria` (`single` / `multiple` / `numeric`), `priority` (`required` / `elective` / `optional`), `value`, `check_if_filled()`, `to_dict()`, `reset()`.

Group slots (`criteria='multiple'`, carry `values: list`):
- **SourceSlot** — `add_one(post, sec='', snip='', chl='', ver=False)` (:101), `replace_entity(old_post, old_sec, new_post='', new_sec='')` (:123), `drop_unverified(conditional=False)` (:132), `drop_ambiguous()` (:142), `is_verified()` (:147), `post_name()` (:150)
- **TargetSlot** — subclass of SourceSlot (for new entities)
- **RemovalSlot** — subclass of SourceSlot (for entities to remove)
- **ChannelSlot** — subclass of SourceSlot with `entity_part='chl'` (domain-specific)
- **FreeTextSlot** — `add_one(text)` (:179), `extract(labels)` (:184)
- **ChecklistSlot** — `add_one(name, description='', checked=False)` (:204), `mark_as_complete(step_name)` (:214), `current_step(detail='')` (:220), `is_verified()` (:211)
- **ProposalSlot** — `add_one(option)` (:239); set `options` before calling

Numeric slots (`criteria='numeric'`, carry `level: float`):
- **LevelSlot** (:247) — base class for numeric slots; defines `assign_one(value)`
- **PositionSlot** (:282), **ProbabilitySlot** (:299), **ScoreSlot** (:312) — subclasses of LevelSlot, inherit `assign_one(value)`

Single-value slots (`criteria='single'`, carry `value: str`):
- **CategorySlot** — `assign_multiple(options)` (:328), `assign_one(option)` (:337)
- **ExactSlot** — `add_one(term)` (:352)
- **DictionarySlot** — `add_one(key, val)` (:366)
- **RangeSlot** — `add_one(start=None, stop=None, time_len=0, unit='', recurrence=False)` (:398), `get_details()` (:417)
- **ImageSlot** (domain-specific) — `assign_one(image_type, src='', alt='', position=-1)` (:444)

Hugo entity parts inside SourceSlot entities: `{post, sec, snip, chl, ver}`.

## 10. BasePolicy — orchestration glue (the 20%)

`backend/modules/policies/base.py`

- `llm_execute(flow, state, context, tools) -> tuple[str, list[dict]]`  →  build_resolved_context + load_skill_template + build_skill_prompt + tool_call  (:18)
- `_read_post_content(post_id, tools) -> dict`  →  card-block-shaped `{post_id, title, status, content}` with `##` headers per section  (:30)
- `resolve_post_id(identifier, tools) -> str | None`  →  UUID-looking → direct; otherwise fuzzy `find_posts` across status suffixes  (:55)
- `_resolve_source_ids(flow, state, tools) -> tuple[str|None, str|None]`  →  extracts `(post_id, sec_id)` from entity slot; side-effect: syncs `state.active_post`  (:86)
- `_build_resolved_context(flow, state, tools) -> dict | None`  →  pre-resolve entities for the LLM, falls back to `state.active_post`  (:99)
- `_persist_section(post_id, sec_id, text, tools)`  →  wraps `revise_content` tool  (:118)
- `_persist_outline(post_id, text, tools)`  →  parse `##` sections via `engineer.apply_guardrails(text, format='markdown', shape='outline')` then call `generate_outline` tool  (:123)

Class constant: `_STATUS_SUFFIXES = (' draft', ' post', ' note', ' published')`.

## 11. PEX tool registry — 34 domain tools + 4 component tools

`backend/modules/pex.py:55–94` (domain), `:425–478` (component tool definitions).

Before proposing a new tool, grep for the capability here first.

**PostService** (9): `find_posts`, `search_notes`, `read_metadata`, `read_section`, `create_post`, `update_post`, `delete_post`, `summarize_text`, `rollback_post`.

**ContentService** (12): `generate_outline`, `convert_to_prose`, `insert_section`, `insert_content`, `revise_content`, `write_text`, `find_and_replace`, `remove_content`, `cut_and_paste`, `diff_section`, `insert_media`, `web_search`.

**AnalysisService** (8): `brainstorm_ideas`, `inspect_post`, `check_readability`, `check_links`, `compare_style`, `editor_review`, `explain_action`, `analyze_seo`.

**PlatformService** (5): `release_post`, `promote_post`, `cancel_release`, `list_channels`, `channel_status`.

**Component tools** (4): `handle_ambiguity`, `coordinate_context`, `manage_memory`, `read_flow_stack`.

## 12. DAX / flow lookups

`utils/helper.py`

- `dax2dact(dax) -> list[str]` (:11)
- `dact2dax(dact_names) -> str` (:18)
- `flow2dax(flow_name) -> str | None` (:24)
- `dax2flow(dax) -> str | None` (:29)
- `flows_by_intent(intent) -> dict` (:34)
- `flow_names_by_intent(intent) -> list[str]` (:41)
- `all_dax_codes() -> list[str]` (:48)
- `edge_flows_for(flow_name) -> list[str]` (:52)
- `output_for_flow(flow_name) -> str` (:57)
- `required_slots(flow_name) -> list[str]` (:62)

`FLOW_CATALOG`, `DACT_CATALOG`, `Intent`, `FlowLifecycle`, `AmbiguityLevel` all live in `schemas/ontology.py`.
