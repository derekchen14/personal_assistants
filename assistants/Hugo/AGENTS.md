# AGENTS.md — Hugo (Blog-Writing Assistant)

Hugo lives in the `personal_assistants` monorepo. It helps a user write, revise, and publish blog posts across channels (Substack, LinkedIn, Twitter, etc.). Turn pipeline: `Agent → NLU → PEX` — PEX composes the reply directly (RES was removed).

This file is an index for coding agents starting a fresh session. Read it once, then use it to decide **where** to read deeper. Further reference lives in `utils/helper_ref.md` (component inventory), `_specs/checklist/flow_authoring.md` (how to author a flow — cross-assistant), and `schemas/flow_reference.md` (Hugo's domain tables).

## Core principle — 80% / 20%

The 7 core components cover ~80% of every assistant's capability. Flow policies carry the remaining ~20% (flow-specific orchestration). When you reach for a helper, ask **"which component owns this?"** first. Do not create new concepts, directories, or utility modules — everything already has a home.

## Commands

- `./init_backend.sh` — FastAPI on port 8001
- `./init_frontend.sh` — frontend on port 5174
- `uv pip install -r requirements.txt` — never `pip install`
- `pytest utils/tests/unit_tests.py utils/tests/test_artifacts.py` — free-tier tests (no LLM, <1s for ~380 tests, includes the Hypothesis FlowStack state machine). **Run after every major change.**
- `pytest utils/evals/e2e_agent_evals.py -v -s --tb=short` — full pipeline scenarios (~5–8 min, LLM-heavy, includes structural snapshot checks). Run at end of feature work.
- `UPDATE_SNAPSHOTS=1 pytest utils/evals/e2e_agent_evals.py` — re-record snapshot sidecars after a *deliberate* behavior change. The `.json` diff in the resulting PR must be reviewed and justified in the PR body.
- Test catalog and how-to-read-failures: `utils/evals/evaluation_guidelines.md` (canonical reference).
- **Snapshot-sidecar rule:** snapshot-sidecar diffs require PR-body justification.
- Bash permission rules: no `&&`, `&`, `$()`, `2>&1` — run independent commands as parallel Bash calls.

## Mental model

- **World** (`backend/components/world.py`) — session-scoped registry: `states`, `frames`, `flow_stack`, `context`. `current_state()` / `latest_artifact()` never return None; a kickoff state + frame + system turn are seeded on init.
- **FlowStack** (`backend/components/flow_stack/stack.py`) — top-of-stack is authoritative past NLU. `flow_stack.get_flow()` returns top by default; pass `status='Active'` only when distinguishing lifecycle.
- **DialogueState** (`backend/components/dialogue_state.py`) — beliefs + control flags: `pred_intent`, `flow_name`, `active_post`, `keep_going`, `has_issues`, `has_plan`.
- **TaskArtifact** (`backend/components/task_artifact.py`) — turn output. A2A-aligned: an artifact is the agent's output for one task (= one flow turn). **3 stored attributes** (`origin`, `parts`, `blocks`) + **3 helper properties** (`data`, `thoughts`, `code`) that unpack the parts list. `parts: list[Part]` follows A2A v1.0's Part oneof (`text` / `raw` / `url` / `data` + optional `metadata`). The classification dict (`violation`, `missing`, `entity`, …) lives inside the first `data` Part; agent reasoning lives in a `text` Part tagged `metadata.kind='thoughts'`; generated code lives in a `text` Part tagged `metadata.kind='code'`. Readers use `artifact.data['violation']` / `artifact.thoughts` / `artifact.code`. `blocks` are visual UI building blocks (cards/lists/selections/etc.). **Never add TaskArtifact attributes without asking.**
- Module contracts are guaranteed (drop defensive `if x is None` checks for these): `NLU.understand` always returns `DialogueState`; every turn has a flow; `PEX.execute` always returns `(TaskArtifact, keep_going)` and composes the reply directly (there is no RES module).

## The 7 components — what they own

One line per component. Full method inventory in `utils/helper_ref.md`.

- **PromptEngineer** (`components/prompt_engineer.py`) — focused LLM interface. PromptEngineer is **callable**: `engineer(prompt, task='<task>', max_tokens=N)` is the standard one-shot LLM call (uses `_TASK_SUFFIXES[task]` for the system prompt). Other methods: `skill_call(flow, convo_history, scratchpad, skill_name, skill_prompt, resolved, max_tokens)` (skill-without-tools), `tool_call(flow, convo_history, scratchpad, tool_defs, call_tool, skill_name, skill_prompt, resolved, max_tokens)` (skill-with-tools, agentic loop — symmetric with skill_call), `stream(prompt, task, model, max_tokens)`, `apply_guardrails(text, format)` routing to `_parse_json` / `_parse_sql` / `_parse_markdown`, `load_skill_template`, `extract_tool_result`. For persona-only system prompt, call `build_system(engineer.persona)` from `prompts/general.py`.
- **DialogueState** — beliefs + flags. `update`, `reset`, `serialize`.
- **FlowStack** — flow lifecycle. Public: `stackon(name, plan_id=None)` push a prerequisite flow on top, `fallback(name)` replace current flow (mark Invalid, transfer slots, push new), `peek`, `get_flow(status=None)`, `find_by_name`, `pop_completed` remove done/invalid flows (returns only completed), `to_list`. Internal: `_push`, `_pop`.
- **ContextCoordinator** (`components/context_coordinator.py`) — conversation turns + checkpoints. `add_turn`, `compile_history`, `save_checkpoint`, `get_checkpoint`, `get_turn`, `last_user_text`, `rewrite_history`, `contains_keyword`.
- **TaskArtifact** — turn output container. `set_artifact`, `add_block`, `compose`, `clear`, `to_dict`. Block types: `card`, `form`, `confirmation`, `toast`, `default`, `selection`, `list`.
- **AmbiguityHandler** (`components/ambiguity_handler.py`) — clarification lifecycle. `declare`, `ask`, `resolve`, `present`, `needs_clarification`, `should_escalate`. Four levels: `general`, `partial`, `specific`, `confirmation`.
- **MemoryManager** (`components/memory_manager.py`) — 3-tier cache (L1 scratchpad, L2 preferences, L3 business context). `read_scratchpad`, `write_scratchpad`, `clear_scratchpad`, `read_preference`, `write_preference`, `should_summarize`, `dispatch_tool`.

## BasePolicy — the 20% glue

`BasePolicy` (`modules/policies/base.py`) orchestrates components on behalf of a flow. After the parsing helpers moved into `PromptEngineer`, only Hugo-specific orchestration lives here:

- `llm_execute(flow, state, context, tools)` — end-to-end LLM+tools call inside a policy (loads skill, builds prompt, runs tool loop).
- `resolve_post_id(identifier, tools)` — fuzzy title-or-UUID → post_id.
- `_read_post_content(post_id, tools)` — card-block-shaped `{post_id, title, status, content}` dict.
- `_resolve_source_ids(flow, state, tools)` — grounds policy on entity slot, syncs `state.active_post`.
- `_build_resolved_context(flow, state, tools)` — deterministic entity prefill for the LLM.
- `_persist_section(post_id, sec_id, text, tools)` — never call `revise_content` directly.
- `_persist_outline(post_id, text, tools)` — extract `##` markdown and save as outline.

## Top-5 most-forgotten recipes

- Persisting a section → `self._persist_section(post_id, sec_id, text, tools)`.
- Reading a post for a card block → `self._read_post_content(post_id, tools)`.
- Fuzzy post reference → `self.resolve_post_id(identifier, tools)`.
- Successful tool result extraction → `self.engineer.extract_tool_result(tool_log, tool_name)`.
- Standard LLM call pattern → `prompt = build_*_prompt(...); raw_output = self.engineer(prompt, '<task>', max_tokens=N); parsed = self.engineer.apply_guardrails(raw_output)`.
- Policy LLM+tools loop → `self.llm_execute(flow, state, context, tools)`.

## Naming convention for LLM output

- `raw_output` — the direct string returned by `self.engineer(...)`. Always this name, regardless of flow, unless the call is inlined.
- After parsing / post-processing, give the result a meaningful name that reflects its shape: `parsed` (generic dict from `apply_guardrails`), `pred_slots` (slot-extraction JSON), `pred_flow` (flow-detection JSON), `verdict` (quality-check string), `cleaned` (stripped/normalized raw_output), `repaired` (slot-repair candidate). Never keep a generic `text` / `result` / `output` past the parsing step.

## Terminology discipline

NLU does NOT "fire" anything. The action verbs by layer:

- **NLU** — *classifies* an intent, *detects* a flow, *fills* a slot, *extracts* an entity. Entity extraction is the grounding sub-task of slot filling — when the action is specifically filling the flow's `entity_slot`, say "extracts an entity"; otherwise "fills a slot". Never "fires", "triggers", or "activates".
- **Policies** — *call* tools, *declare* ambiguity, *write* scratchpad, *push* / *fallback* on the flow stack.
- **Skills** — *produce* output, *call* tools via the agentic loop.
- **Flows** — *complete*, *stack on*, *fallback*. They have **stages**, not *modes*.

Breaking the convention confuses code review and pattern matching. Use "stages" when describing in-flow control flow, never "modes". (Previously AD-5; moved here because it's a convention, not a code-shaping decision.)

## Outline constants

There are **exactly 4 outline levels** (+ Level 0 for the post title):

| Level | Markdown | Meaning |
|---|---|---|
| 0 | `# Title` | Post title |
| 1 | `## Heading` | Section header |
| 2 | `### Sub-heading` | Sub-section |
| 3 | ` - bullet` | Bullet point |
| 4 | `   * sub-bullet` | Sub-bullet |

Codified as the `OUTLINE_LEVELS` module-level dict in `backend/components/flow_stack/flows.py`. Reuse; do not re-define in a policy. The `depth` slot on `OutlineFlow` maps to these levels; the mapping also applies to `refine`, `compose`, `add`, and anything that talks about outline structure. (Previously AD-4; moved here because it's a reference, not a code-shaping decision.)

## Authoring a flow — 5 edit points

Every flow touches five files:

1. `backend/components/flow_stack/flows.py` — declare the flow (parent class, `flow_type`, `dax`, `entity_slot`, `goal`, `slots`, `tools`). Register in `flow_stack/__init__.py:flow_classes`.
2. `backend/modules/policies/<intent>.py` — add `<flow>_policy`. Dispatched via `match flow.name()`.
3. `backend/prompts/skills/<flow>.md` — skill prompt loaded by `PromptEngineer.load_skill_template`.
4. `backend/modules/templates/<intent>.py` — entry in `TEMPLATES` + branch in `fill_<intent>_template`. Spoken text goes here, NOT in `artifact.thoughts`.
5. `backend/prompts/nlu/<intent>_slots.py` — slot-extraction prompt for NLU `_fill_slots` phase 2.

Full authoring walkthrough (the four files, conventions): `_specs/checklist/flow_authoring.md`; Hugo's tool/scope/ID tables: `schemas/flow_reference.md`.

## Planning rule

Any non-trivial task begins with a plan. While designing the plan, default to **existing component APIs** — read the method inventories in `utils/helper_ref.md` and the `FlowStack` / `TaskArtifact` / other component sections above and use what's already there. Do NOT invent new methods, rename existing ones, or change signatures as part of a fix. If the task genuinely needs a component API change, **surface it to the user for review before editing** — do not quietly expand or modify a contract mid-task.

## Invariants (bug magnets when violated)

- Each policy owns `flow.status = 'Completed'` — PEX does not mark completion centrally.
- `state.active_post` must be set by the policy when the flow is source/target/removal/channel-grounded — PEX post-hook flips `has_issues` if missing.
- Response wording lives in `modules/templates/*.py`, not `artifact.thoughts`. Exceptions: flows whose output IS the LLM text (brainstorm, outline-thoughts).
- `flow.intent` is a property (no parens); `state.pred_intent` is NLU's guess — past NLU, trust `flow.intent`.
- Recompute slot fill at policy entry with `slot.check_if_filled()`; `.filled` is stale after earlier turns.
- Sub-flows pushed via `flow_stack.stackon()` or `fallback()` exit to the user for review unless `state.has_plan` is set — no silent chaining outside a plan.
- A Converse turn that consumes accept/decline yields to the underlying flow when `flow_stack.stack_size() > 1` — it sets `state.keep_going=True` and returns an empty frame instead of running its chit-chat skill. See `_specs/checklist/flow_authoring.md § Transitions` (yield-when-stacked).
- One `SourceSlot` per flow maximum. Hugo entity parts: `post`, `sec`, `snip`, `chl`, `ver`.
- 48 flows across Research(7) / Draft(7) / Revise(7) / Publish(7) / Converse(7) / Plan(6) / Internal(7). Ontology: `flow_stack/flows.py`.

## Boundaries — ✅ / ⚠️ / 🚫

- ✅ Edit policies, skill prompts, templates, slot definitions, existing tool implementations freely.
- ✅ Reuse helpers from the 7 components + `BasePolicy` + `pex._tools`.
- ⚠️ Ask before adding: a new tool to PEX registry, a new slot type, a new flow, a new `TaskArtifact` attribute, a new entry in `FLOW_ONTOLOGY`.
- ⚠️ Ask before a migration touching `database/content/metadata.json` or `database/tables.py`.
- 🚫 Never create new components, concepts, directories, or utility modules. The 7 components already cover ~80% of what's needed.
- 🚫 Never `pip install` — use `uv pip install`.
- 🚫 Never chain Bash with `&&`, `&`, `$()`, `2>&1` — separate calls.
- 🚫 Never single-character variable names. Use `idx`, `flow`, `slot`, `ecp`.
- 🚫 Never add defensive `.get()` / `if x is not None` for module-contract-guaranteed values (see CLAUDE.md §5).

## Directory cheat sheet

```
assistants/Hugo/
├── backend/
│   ├── agent.py                    orchestrator (turn pipeline, keep_going loop)
│   ├── components/                 7 components: world, dialogue_state, display_frame,
│   │                               flow_stack/, ambiguity_handler, memory_manager,
│   │                               context_coordinator, prompt_engineer
│   ├── modules/                    nlu.py, pex.py, res.py, policies/, templates/
│   ├── prompts/                    pex/ (skills/), nlu/, experts/, for_{nlu,pex,orchestrator,compressor,contemplate,experts}.py
│   ├── utilities/services.py       PostService, ContentService, AnalysisService, PlatformService
│   └── routers/                    chat_service.py, health_service.py
├── database/                       hugo.db, content/, tables.py, seed_data.json
├── schemas/                        ontology.py, config.py, tools.yaml, flow_reference.md (Hugo tool/scope/ID tables)
├── utils/                          helper.py, helper_ref.md, prod_replica.py, rebuild_metadata.py,
│                                   evaluation_suite/ (run_suite.py; _tests/ _traces/ _evals/;
│                                   datasets/{train,dev,test}.jsonl; harness.py scoring.py; review_app/)
└── README.md                       10-step workflow + CRUD matrix
```

## External files to load on demand

- `CLAUDE.md` (repo root) — authoritative code style, Bash rules, defensive-coding rules.
- `_specs/architecture.md` — POMDP framing, cross-assistant module/component split.
- `_specs/components/flow_stack.md` — full flow/slot architecture: class hierarchy, 12+4 slot types, grounding rules, lifecycle states, fallback, failure recovery.
- `_specs/checklist/flow_authoring.md` — authoring a flow end-to-end (cross-assistant); **canonical slot priorities** (`required` / `elective` / `optional`) under "Designing the flow". Hugo's domain tables: `schemas/flow_reference.md`.
- `utils/helper_ref.md` — component method inventory. Read before adding a helper so you don't reinvent an existing one.
- `~/.claude/projects/-Users-derekchen-Documents-repos-personal-assistants/memory/MEMORY.md` — persistent cross-session feedback.
