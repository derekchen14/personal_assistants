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
2. `flow_reply(flow, convo_history, scratchpad, skill_name=None, flow_prompt=None, resolved=None, max_tokens=1024, user_text=None, model='med') -> str`  →  flow sub-agent turn WITHOUT tools (sibling of flow_execute). Loads `prompts/pex/flows/<skill_name or flow.name()>.md`, builds `[system, user]`, returns LLM text. Pass `flow_prompt=` to override the loaded prompt.
3. `flow_execute(flow, convo_history, scratchpad, tool_defs, tool_dispatcher, skill_name=None, flow_prompt=None, resolved=None, max_tokens=4096, user_text=None, model='med', schema=None) -> tuple[str, list[dict]]`  →  flow sub-agent turn WITH tools (sibling of flow_reply). Same assembly API; adds `tool_defs` and `tool_dispatcher` for the agentic loop; `schema=` forces a schema-constrained final emit.
4. `stream(prompt:str, task='skill', model='sonnet', max_tokens=4096)`  →  async token streaming (future scaffolding).

Output parsing (dispatched via `apply_guardrails`):
5. `apply_guardrails(text, format='json', shape=None)`  →  router. Strips fences, dispatches to:
  * `_parse_json(text) -> dict | None`  →  JSON parse with fallback regex for embedded `{}`.
  * `_parse_sql(text) -> str`  →  strip whitespace, return cleaned SQL (stub for Dana).
  * `_parse_markdown(text, shape)`  →  `shape='outline'` extracts `##` sections; `shape='candidates'` parses `### Option N / ## Section`.

File I/O + tool-log helpers:
6. `load_flow_prompt(flow_name) -> str`  →  reads `backend/prompts/pex/flows/<flow_name>.md`. `load_skill(skill_name) -> str`  →  reads `backend/prompts/pex/skills/<skill_name>.md` (currently only `plan.md`).
7. `extract_tool_result(tool_log, tool_name) -> dict`  →  first successful result for a given tool; strips underscore-prefixed keys.

Instance attribute: `persona` (public) — `dict` loaded from `config.persona`. For the persona-based system prompt, call `build_system(engineer.persona)` directly from `prompts/general.py`.

Class constants: `_FLOW_DIR` → `backend/prompts/pex/flows/` (flow instruction prompts, read by `load_flow_prompt`) and `_SKILL_DIR` → `backend/prompts/pex/skills/` (agent skills, read by `load_skill` — currently only `plan.md`). Task suffixes in `_TASK_SUFFIXES` (module-level) map each `task` label to a system-prompt suffix: `classify_intent`, `detect_flow`, `fill_slots`, `contemplate`, `repair_slot`, `skill`, `naturalize`, `quality_check`, `clarify`.

**Prompt compilation is NOT a PromptEngineer concern.** The `backend/prompts/` module owns prompt-text compilation; consumer modules import what they need:
- NLU owns `_detect_flow_prompt`, `_fill_slot_prompt`, `_contemplate_prompt` (all >2 lines of real work). `build_intent_prompt` is called inline at its one use site.
- `for_pex.py` owns `build_flow_system` / `build_flow_messages` (called inside flow_reply / flow_execute).
- PEX composes the reply directly from blocks/metadata — no RES, no separate naturalize prompt.
- AmbiguityHandler renders clarification text via `ask()` — level-specific prose lives in the handler itself.

## 2. DialogueState — beliefs + flags

`backend/components/dialogue_state.py`. Direct construction is the primary entry point;
`from_dict` exists for restoring multi-session state.

1. `__init__(intent, dax, turn_count, confidence=0.5)` — direct init for a fresh turn.
2. `flow_name(string=False)` — returns the dax by default; `string=True` returns the human-readable name via `dax2flow`.
3. `reset()` — clear all fields back to a seed-state shape.
4. `serialize() -> dict` — JSON-compatible snapshot for persistence.
5. `from_dict(data)` (classmethod) — reconstruct from a serialized dict.

Attributes: `pred_intent`, `pred_flow` (dax), `confidence`, `pred_flows`, `turn_count`, `keep_going`, `has_issues`, `has_plan`, `natural_birth`, `active_post`, `slices`. (The structured plan now lives on the active Plan flow in the flow_stack — not on state.)

## 3. FlowStack — flow lifecycle

`backend/components/flow_stack/stack.py` contains 6 core methods.

1. `stackon(flow_name, plan_id=None) -> BaseFlow`  →  instantiate + push; slots NOT filled here  (:20)
2. `fallback(flow_name) -> BaseFlow`  →  replace top of stack with a different flow  (:25)
3. `peek() -> BaseFlow | None`  (:37)
4. `get_flow(status=None) -> BaseFlow | None`  →  top of stack by default; pass `status='Active'` etc. only when the caller truly distinguishes lifecycle  (:41)
5. `find_by_name(flow_name) -> BaseFlow | None`  →  skips completed/invalid  (:49)
6. `pop_completed() -> list[BaseFlow]`  →  pops both Completed and Invalid from top; returns only Completed. Driven by the orchestrator via PEX's `write_state` `pop_completed` op  (:58)

Serialization (non-core): `to_list() -> list[dict]`  (:76).

## 4. ContextCoordinator — turns + checkpoints

`backend/components/context_coordinator.py` contains 7 core methods.

1. `add_turn(speaker, text, turn_type) -> Turn`  →  `turn_type` ∈ `utterance` / `action` / `system` / `clarification` / `agent_response`  (:55)
2. `compile_history(look_back=5, keep_system=True) -> str`  →  canonical name for the string history consumed by prompts  (:66)
3. `full_conversation(keep_system=True, as_turns=False) -> list`  (:75)
4. `recent[-1] -> get the last turn`
5. `get_turn(turn_id) -> Turn | None`  (:85)
6. `save_checkpoint(label, data=None)`  (:91)
7. `get_checkpoint(label) -> dict | None`  (:99)

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

## 5. TaskArtifact — turn output container

`backend/components/task_artifact.py` contains the core methods plus a `Part` class (A2A v1.0 oneof).

`TaskArtifact` shape: **3 stored attributes** (`origin`, `parts: list[Part]`, `blocks`) + **3 helper properties** (`data`, `thoughts`, `code`) that unpack the parts list. The constructor accepts the legacy `parts=dict` shape (wrapped as a single data Part) plus `thoughts`/`code` kwargs (each wrapped as a `text` Part tagged via `Part.metadata.kind`). **Never add new top-level attributes.**

1. `add_part(**kwargs)`  →  append a `Part` (text / data / file) to `parts`  (:95)
2. `update_data(**kwargs)`  →  merge kwargs into the existing data Part, or create one  (:98)
3. `set_artifact(origin='', blocks=[], new_data={})`  →  merges blocks + data  (:105)
4. `add_block(block_data)`  →  auto-routes `form/confirmation/toast` to `top`, others to `bottom`  (:113)
5. `clear()`  (:116)
6. `compose(block, data) -> dict`  →  build a frontend-shaped block dict  (:121)
7. `to_dict() -> dict`  (:124)

`BuildingBlock`: `block_type`, `data`, `panel`; `to_dict()`.

Valid block types: `card`, `form`, `confirmation`, `toast`, `default`, `selection`, `list`.

## 6. AmbiguityHandler — clarification lifecycle

`backend/components/ambiguity_handler.py` contains 6 core methods.

Four levels: `general`, `partial`, `specific`, `confirmation` (`schemas/ontology.py:AmbiguityLevel`).

1. `declare(level, metadata=None, observation=None)`  →  start a clarification round
2. `present() -> bool`  →  is a clarification pending?
3. `ask() -> str`  →  phrase the user-facing question (returns observation if set, else level-specific prose)
4. `resolve()`  →  clear state
5. `needs_clarification(confidence) -> bool`  →  threshold check against NLU confidence
6. `should_escalate() -> bool`  →  true when total declared rounds ≥ max_turns

Properties: `level` (:90), `metadata` (:94), `observation` (:98).

## 7. MemoryManager — 3-tier facade

`backend/components/memory_manager.py` is the synchronous facade over the three tiers. It holds
references to the tier sub-components (`context`, `preferences`, `business`) and exposes one read
skill per tier. Tier-specific writes are reached through the sub-component.

- `recap(n_turns=None, filter=None) -> str`  →  L1, recent session events via `context.compile_history`  (:14)
- `recall(query, flow_name=None) -> dict`  →  L2, user preferences via `preferences.read(query)`  (:18)
- `retrieve(query, top_k=10, documents=None) -> dict`  →  L3, business knowledge / FAQs  (:23)

Tier sub-components (set in `__init__`):
- `context` (L1) — the `ContextCoordinator` event stream (see §4).
- `preferences` (L2) — `UserPreferences`: `store_preference(key, value_or_record)` (:24), `read(query=None)` (:38).
- `business` (L3) — `BusinessContext`: `search_faqs`, `search_all`, `rerank`.

Session scratchpad is a separate component — `SessionScratchpad` (`backend/components/session_scratchpad.py`), reached via `world.scratchpad`, not MemoryManager.

## 8. BaseFlow — flow contract + slot filling

`backend/components/flow_stack/parents.py`

Core flow API:
- Property `intent`  →  `self.parent_type`  (:23)
- `name(full=False) -> str`  →  `'create'` or `'Draft(create)'`  (:30)
- `is_complete()` (:46), `is_filled()` (:49)
- `fill_slots_by_label(labels: dict) -> bool`  →  System-1 targeted single-slot fill from PEX label extraction. Routes entity values through `extract_entity`  (:58)
- `fill_slot_values(values: dict)`  →  transfer prediction values onto slot objects; aliases `title→target`, `post/post_id→source`  (:74)
- `slot_values_dict() -> dict`  →  only filled / non-empty slots  (:136)
- `to_dict() -> dict`  (:144)
- `extract_entity(entity)`  →  add entity to the primary grounding slot; override in domain parents for validation  (:90)
- `entity_values(size=False)`  →  values of `self.slots[self.entity_slot]`  (:157)
- `needs_to_think() -> bool`  (:161)
- `match_action(action_name) -> bool`  →  starts-with `self.parent_type.upper()`  (:166)

Attributes every flow has: `slots`, `tools`, `is_newborn`, `is_uncertain`, `stage`, `entity_slot` (default `'source'`), `flow_id`, `plan_id`, `turn_ids`, `status` ∈ `Pending / Active / Completed / Invalid`.

Parent classes (each sets `parent_type` only): `ResearchParentFlow`, `DraftParentFlow`, `ReviseParentFlow`, `PublishParentFlow`, `ConverseParentFlow`.

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

- `llm_execute(flow, state, context, tools, include_preview=False, extra_resolved=None, exclude_tools=(), model='med', schema=None) -> tuple[str, list[dict]]`  →  pre_llm hook + build_resolved_context + flow_execute + post_llm hook  (:62)
- `_read_post_content(post_id, tools) -> dict`  →  card-block-shaped `{post_id, title, status, content}` with `##` headers per section  (:30)
- `resolve_post_id(identifier, tools) -> str | None`  →  UUID-looking → direct; otherwise fuzzy `find_posts` across status suffixes  (:55)
- `_resolve_source_ids(flow, state, tools) -> tuple[str|None, str|None]`  →  extracts `(post_id, sec_id)` from entity slot; side-effect: syncs `state.active_post`  (:86)
- `_build_resolved_context(flow, state, tools) -> dict | None`  →  pre-resolve entities for the LLM, falls back to `state.active_post`  (:99)
- `_persist_section(post_id, sec_id, text, tools)`  →  wraps `revise_content` tool  (:118)
- `_persist_outline(post_id, text, tools)`  →  parse `##` sections via `engineer.apply_guardrails(text, format='markdown', shape='outline')` then call `generate_outline` tool  (:123)

Class constant: `_STATUS_SUFFIXES = (' draft', ' post', ' note', ' published')`.

## 11. PEX tool registry — 33 domain tools + component/orchestrator tools

`backend/modules/pex.py:106–144` (domain dispatch table), `:888–998` (orchestrator tool definitions).

Before proposing a new tool, grep for the capability here first.

**PostService** (9): `find_posts`, `search_notes`, `read_metadata`, `read_section`, `create_post`, `update_post`, `delete_post`, `summarize_text`, `rollback_post`.

**ContentService** (10): `generate_outline`, `convert_to_prose`, `insert_section`, `revise_content`, `write_text`, `remove_content`, `cut_and_paste`, `diff_section`, `insert_media`, `web_search`.

**AnalysisService** (8): `brainstorm_ideas`, `inspect_post`, `check_readability`, `check_links`, `compare_style`, `editor_review`, `explain_action`, `analyze_seo`.

**PlatformService** (4): `release_post`, `cancel_release`, `list_channels`, `channel_status`.

**BusinessContext** (1): `search_faqs`.

**Orchestrator hot-path tools** (6, `_orchestrator_dispatch`): `read_state`, `write_state`, `activate_flow`, `append_to_scratchpad`, `store_preference`, `read_scratchpad`. Writes still route through a flow via `activate_flow`; flow-stack ops are `write_state` ops. `read_flow_stack` / `call_flow_stack` is retired — its job lives in `read_state` / `write_state`.

**Component tools** (3): `handle_ambiguity`, `coordinate_context`, `manage_memory`.

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
