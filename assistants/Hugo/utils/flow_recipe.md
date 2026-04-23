# flow_recipe.md — Authoring (or Modifying) a Hugo Flow

Every flow touches five files. This recipe walks through each using `OutlineFlow` as a running concrete example — it is already wired end-to-end and passes at all three eval levels. Copy the shape, change the details.

## Before you edit

Read `AGENTS.md` → mental model + boundaries + invariants.
Read `helper_ref.md` → know which helpers exist so you don't reinvent any.
Touch one flow end-to-end; skip steps at your peril — a flow with only 4 of 5 pieces will fail at runtime (NLU can't fill slots, or RES can't phrase a response, or the policy crashes on a missing skill).

## 1. Declare the flow — `backend/components/flow_stack/flows.py`

Add a class inheriting from the correct intent parent (`DraftParentFlow`, `ResearchParentFlow`, etc.). Set:

- `flow_type` — the canonical lowercase name (`'outline'`)
- `dax` — 3-hex-digit code, DACT digits ordered verb → noun → adjective (`'{002}'`)
- `entity_slot` — the slot name that grounds the flow (`'source'`)
- `goal` — one sentence, used in NLU prompts
- `slots` dict — slot name → slot instance with `priority` set
- `tools` list — PEX tool names this flow may dispatch

Example (`flows.py:113-125`):

```python
class OutlineFlow(DraftParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'outline'
    self.entity_slot = 'source'
    self.dax = '{002}'
    self.goal = 'generate an outline including section headings, key bullet points, estimated word counts ...'
    self.slots = {
      'source': SourceSlot(1, priority='required'),
      'sections': ChecklistSlot(priority='elective'),
      'topic': ExactSlot(priority='elective'),
      'depth': LevelSlot(priority='optional', threshold=1),
    }
    self.tools = ['find_posts', 'brainstorm_ideas', 'generate_outline']
```

Be precise about their priority levels of the `slots` dict:
    - Required = necessary to complete the action correctly, these must be filled
    - Elective = exactly one must be filled (and there are at least two options to choose from)
    - Optional = nice to have but not a blocker

Register the class in `backend/components/flow_stack/__init__.py:flow_classes` so `FlowStack.stackon('create')` can resolve it.

Constraints:
- While you may have to adjust the slots for a flow, do not invent a new slot type. Use what's in `slots.py` (see `helper_ref.md` §9).
- While you may assign new tools to a flow, only create new tools in `pex._tools` after asking. The existing tools cover most needs.
- `entity_slot` must point at a slot that actually exists in `self.slots`. CreateFlow overrides the default `'source'` because creation grounds an unborn post by title, not an existing post.

## 2. NLU slot-extraction prompt — `backend/prompts/nlu/<intent>_slots.py`

Slots are incredibly important to fill correctly because they guard the policy from making assumptions that may lead to errors. Before writing the slot-filling prompt, you should be able to answer the following:
- What is the purpose of this flow? What action does it accomplish for the user?
- What assumptions would be ridiculous to get wrong because that would defeat the purpose of the flow? (e.g., for OutlineFlow, creating bulletpoints for the wrong post would be a critical failure). 
- Can I justify the slot-type and priority level of each slot?

While superficially similar, slots (within flows) are distinct from params (for tools). Parameters hold information the LLM extracts from the user's request to call a tool without errors. However, this may not satisfy the user's underlying goal. For example, the LLM may have extracted a parameter holding a valid post_id, but this post is not the one the user wants to edit! In other words, parameters care mainly about syntactical accuracy, whereas slots care about semantic accuracy. Params are about calling the tool correctly; slots are about understanding the user's intent and grounding it properly. 

Add an entry keyed by `flow_type` inside `INSTRUCTIONS`. It feeds `PromptEngineer.build_slot_fill_prompt`, which `NLU._fill_slots` calls in phase 2 when slots are still unfilled after payload-based extraction.

Structure:
- `Goal:` — one sentence mirroring the flow's `goal` field.
- `Slots:` — one line per slot with required/elective/optional + a sentence explaining when to fill it and how to format the value.
- Optional `Routing rule:` — disambiguation guidance when two slots could absorb the same utterance (see `refine` for a good example).

Slot names must match exactly what step 1 declared. The LLM response is parsed by `engineer.apply_guardrails` and fed to `flow.fill_slot_values(pred_slots['slots'])`.

## 3. Write the policy method — `backend/modules/policies/<intent>.py`

Add `<flow>_policy(self, flow, state, context, tools)`. The intent policy's `execute` dispatches via `match flow.name()`. Required structure:

1. Guard clauses for missing required or elective slots — declare ambiguity and return early, or try to fill the slots and then recurse
2. Unpack the stored information for the work ahead - for example, call `self._resolve_source_ids()` or reference `state.active_post` to get the post_id, or pull the slot-value from the filled slot
3. Main action — either a direct tool call (for deterministic flows) or `self.llm_execute(flow, state, context, tools)` for skill-based flows.
4. Persist as appropriate — `self._persist_section(...)`, `self._persist_outline(...)`, or a direct tool call for the create/update case; consider writing to scratchpad if a plan is active.
5. Based on the outcome of the action:
   a. When the result is successful, mark the flow complete — `flow.status = 'Completed'`. PEX does not do this centrally.
   b. If the task has failed, or only partially successful - declare ambiguity, stack on a flow to the stack, fall back to a different flow, or retrieve additional information as needed
6. Build and return `DisplayFrame`. If the flow is grounded on a post, add a card block with `self._read_post_content(post_id, tools)`.

Example (`policies/draft.py:199-237`, `create_policy`):

```python
def outline_policy(self, flow, state, context, tools):
    if not flow.slots['source'].check_if_filled():
        self.ambiguity.declare('partial')
        return DisplayFrame()

    if flow.slots['sections'].check_if_filled():
        flow.stage = 'direct'
        post_id = state.active_post
        text, tool_log = self.llm_execute(flow, state, context, tools)
        ...
        flow.status = 'Completed'
        frame = DisplayFrame(origin='outline', thoughts=text)
        frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})

    elif flow.slots['topic'].check_if_filled():
        flow.stage = 'propose'
        topic = flow.slots['topic'].value
        ...
        frame = self._propose_outline(flow, state, topic, tools)

    else:
        parsed = self.engineer.apply_guardrails(self.engineer(prompt, 'fill_slots'))
        flow.fill_slots_by_label({'topic': parsed and parsed.get('topic')})

        if flow.slots['topic'].filled:
            flow.stage = 'propose'
            frame = self._propose_outline(flow, state, context, tools)
        else:
            flow.stage = 'error'  # Missing topic is an error state
            self.ambiguity.declare('specific', metadata={'missing_slot': 'topic'})
            frame = DisplayFrame('error')

    return frame
```

Anti-patterns to avoid:
- Adding defensive `if state is None` / `if flow is None` — the module contracts guarantee these are non-None.
- Writing output parsers inline — use `self.engineer.apply_guardrails(text, format='json')` or `apply_guardrails(text, format='markdown', shape='candidates'|'outline')`.
- Calling `revise_content` directly — use `self._persist_section(...)`.
- Writing spoken response text into `frame.thoughts`. Only do that when the LLM text IS the response (brainstorm, outline-thoughts). Normal flows pass data to RES via blocks/metadata; RES uses a template to phrase it.

## 4. Skill prompt — `backend/prompts/skills/<flow>.md`

Loaded by `PromptEngineer.load_skill_template(flow.name())` inside `BasePolicy.llm_execute`. Skip this file entirely if the flow uses a deterministic tool path (CreateFlow itself does NOT have a skill prompt — it only calls `create_post`).

Shape (existing files — e.g., `skills/create.md`):
- `# Skill: <flow_name>` + one-sentence description.
- `## Behavior` — bullets describing what the LLM should do, including any tool-call expectations.
- `## Slots` — list of the same slots declared in step 1, with required/optional annotations.
- `## Output` — required JSON shape for the LLM reply (if structured output is expected).
- `## Few-shot examples` — at least two `User: … / Correct tool trajectory: … / Correct final reply:` triples.

The LLM sees this skill prompt merged with the user's conversation via `BasePolicy._build_skill_prompt`.

## 5. Response template — `backend/modules/templates/<intent>.py`

Two edits:
1. Add an entry in the `TEMPLATES` dict: `'flow_name': {'template': '…', 'skip_naturalize': <bool>, 'block_hint': '<hint>'}`.
2. Add a branch in `fill_<intent>_template(template, flow, frame)` that formats the template string using `flow` + `frame` data.

Example (`templates/draft.py:6-27`):

```python
TEMPLATES = {
    'create': {'template': "I've created a new draft called '{title}'", 'block_hint': 'form'},
    'outline': {'template': "{message}", 'skip_naturalize': True, 'block_hint': 'card'},
    ...
}

def fill_draft_template(template, flow, frame):
    flow_name = flow.name()
    if flow_name == 'create':
        return TEMPLATES['create']['template'].format(title=flow.slots['title'].value)
    if flow_name == 'outline':
        ...
    return TEMPLATES[flow_name]['template'].format(message=frame.thoughts)
```

`skip_naturalize: True` when the text is already human-phrased (brainstorm output, outline proposals). Leave it False when the template is a template literal — RES will rewrite through `engineer.call` with the naturalize prompt.

## Coding conventions

These rules apply to every flow touchpoint — NLU slot defs, policy methods, skill files, RES templates. They were distilled while writing the six exemplar policies; the full policy-layer list is in `utils/policy_builder/policy_spec.md § Policy-writing conventions`. The subset below is universal enough to bake in before you write any new flow code.

1. **Don't defend deterministic code.** Internal tools have known contracts. Access keys directly (`flow_metadata['outline']`, `slots['source'].values[0]`); let missing keys or `_success=False` crash so tests catch the bug. See `CLAUDE.md § "Don't defensively access known-present values"` for the canonical list of where this applies.
2. **No defaults that hide errors.** `text or ''`, `parsed or {}`, `isinstance(parsed, dict)` mask upstream bugs. If a call can legitimately return empty, branch on the value — don't coerce.
3. **Slot priorities are definitional.** Required = must be filled. Elective = exactly one of ≥2 options must be filled. Optional = nice-to-have. `flow.is_filled()` encodes both the required check and the at-least-one-elective check; don't re-derive them in policies or NLU prompts. A single elective is a flow-design bug — promote it to required or make it optional.
4. **`DisplayFrame` conventions.** `origin` is always `flow.name()` for frames a policy builds (or `'system'` for the `Agent.take_turn` crash path). Error-ness lives in `metadata['violation']`, not in `origin`. `code` holds raw payloads (tool response, failing JSON); `thoughts` holds descriptive prose. No em-dashes in `thoughts` — it's user-facing.
5. **`ambiguity.declare` uses `observation`.** `declare(level, observation=..., metadata=...)` — human-readable text goes in `observation`; metadata is classification only (`missing_entity`, `missing_slot`, `missing_reference`, `duplicate_title`). Don't stuff questions into metadata.
6. **Never invent new keys without approval.** Hard rule across metadata, `extra_resolved`, `frame.blocks[i].data`, scratchpad payloads, tool schema args. If what you want to pass doesn't fit an existing key, surface the design question first. See `CLAUDE.md § "New components or concepts"`.
7. **Standard variable names.** `flow_metadata` for `tools('read_metadata', ...)`, `text, tool_log` for `llm_execute`, `parsed` for `apply_guardrails`, `saved, _` for `tool_succeeded`. Matches `CLAUDE.md § Variable naming`.
8. **Single return at the end of a policy.** Early returns only for major errors (`partial` / `general` ambiguity — top-level grounding failures). Every other outcome assigns to `frame` and falls through to one `return frame`.

The violation vocabulary (8 categories: `failed_to_save`, `scope_mismatch`, `missing_reference`, `parse_failure`, `empty_output`, `invalid_input`, `conflict`, `tool_error`) is enumerated in `policy_spec.md § Violation vocabulary`. Use those exact strings when setting `metadata['violation']` — don't coin new ones.

## Verification checklist

When the flow is wired up:
- [ ] `python -c "from backend.components.flow_stack import flow_classes; print(flow_classes['<flow>'])"` resolves.
- [ ] `PromptEngineer.load_skill_template('<flow>')` returns the file contents (or None if the flow has no skill prompt by design).
- [ ] A test utterance triggers the flow in `e2e_agent_evals.py` — add a step or edit `test_cases.json`.
- [ ] L1 pass: policy runs, frame has data (card/form/confirmation/toast/selection/list block or non-empty thoughts/metadata).
- [ ] L2 pass: domain-tool trajectory matches what you expect given the skill prompt.
- [ ] L3 pass: the LLM-as-judge's rubric is satisfied — `did_action` + `did_follow_instructions`.
- [ ] `state.active_post` is set for any grounded flow (source/target/removal/channel). If not, PEX post-hook flips `has_issues` and RES escalates ambiguity.
- [ ] Spoken text comes from the template, not `frame.thoughts` (unless the flow is brainstorm-like).

When in doubt, trace `CreateFlow` from `flows.py:113` → `policies/draft.py:199` → `prompts/skills/create.md` → `templates/draft.py:TEMPLATES['create']` → `prompts/nlu/draft_slots.py:'create'`. Every working flow has the same five part trace.
