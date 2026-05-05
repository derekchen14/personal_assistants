# PEX — Policy Executor

The execution engine of the agent. Holds all policies associated with each flow — this is where the agent's actions happen. Each policy is a deterministic class method that may delegate tool calling to a skill (an LLM with access to tools). The class method handles slot review, ambiguity declaration, frame construction, and flow lifecycle. The skill, when used, handles tool selection, tool execution, and result gathering.

**Module principle**: PEX processes information through policies, but does not store the information itself. It mutates the State objects passed to it, and always returns a `DisplayFrame`. PEX does not write user-facing prose — message generation is RES's responsibility (with one exception: flows whose output IS the LLM's prose, such as `brainstorm`, place that prose in `frame.thoughts`).

- **Execute function**: primary path for running the active flow's policy
- **Recover function**: failure escalation when a policy declares ambiguity or returns an error frame

**Policy file organization**: PEX imports from one policy file per intent. Each domain has 7 intent files — three universal (`plan`, `converse`, `internal`) plus four domain-specific intents whose names the domain chooses.

| Universal | Universal | Universal | Domain-specific × 4 |
|---|---|---|---|
| `plan` | `converse` | `internal` | (e.g., Hugo: `research`, `draft`, `revise`, `publish`; Dana: `clean`, `transform`, `analyze`, `report`) |

The flows within each file are domain-specific even when structurally similar across domains.

---

## Policies and Tools

### Policy Structure — Deterministic vs. Agentic Dispatch

The deterministic-vs-agentic split is **implied by the policy code** — never declared on the flow class. There is no `flow.deterministic` flag.

**Heuristic.** Deterministic when `len(flow.tools) == 1` AND the tool's args are fully derivable from `flow.slots` + `state.active_post` without LLM reasoning. Agentic when `len(flow.tools) >= 2` OR any arg is prose/content the LLM must compose.

**Deterministic flow:**
- No skill file, no starter.
- Policy builds `params` from slots, calls `tools('<tool_name>', params)` directly, flips `flow.status = 'Completed'`, returns a `DisplayFrame`.
- On tool failure: `DisplayFrame(flow.name(), metadata={'violation': 'tool_error'}, code=result['_message'])`.

**Agentic flow:**
- Skill file at `backend/prompts/pex/skills/<flow>.md`.
- Starter at `backend/prompts/pex/starters/<flow>.py` exporting `build(flow, resolved, user_text)`.
- Policy calls `BasePolicy.llm_execute(...)` which loads the skill, builds the prompt, runs the tool loop, and returns `(text, tool_log)`.
- Policy reads `tool_log` via `engineer.tool_succeeded(tool_log, '<tool>')` and `engineer.extract_tool_result(...)` to verify persistence and pull results.
- On no save: `DisplayFrame(flow.name(), metadata={'violation': 'failed_to_save'}, thoughts=...)`.

Reference: [Flow Stack](../components/flow_stack.md), [Configuration](../utilities/configuration.md), [Tool Smith](../utilities/tool_smith.md)

### Skill Output Contract

Skills return `(text, tool_log)`. The policy is responsible for interpreting the trajectory and constructing the frame; skills do not return outcome enums.

The policy classifies the result by inspecting `tool_log`:

| Policy detection | Frame produced |
|---|---|
| `tool_succeeded(tool_log, '<tool>')` returns True | Success frame: `DisplayFrame(flow.name(), thoughts=text)` + appropriate block |
| Persistence tool ran but produced no effect | `metadata={'violation': 'failed_to_save'}` |
| Skill output couldn't be parsed | `metadata={'violation': 'parse_failure'}, code=text` |
| Tool returned `_success=False` | `metadata={'violation': 'tool_error', 'failed_tool': '<name>'}, code=msg` |

**Closed violation vocabulary (8 codes).** Cite by name; never extend without explicit approval.

| Code | Fires when |
|---|---|
| `failed_to_save` | A persistence tool ran but produced no effect |
| `scope_mismatch` | The flow ran at the wrong granularity |
| `missing_reference` | An entity in a slot doesn't exist on the post |
| `parse_failure` | Skill output couldn't be parsed into the expected shape |
| `empty_output` | Skill returned nothing when prose was expected |
| `invalid_input` | A tool rejected (or would reject) the arguments given |
| `conflict` | Two slot values contradict |
| `tool_error` | A deterministic tool returned `_success=False` |

Specifics go in `thoughts` (natural language) or `code` (raw payload), never in nested-underscore metadata keys.

### Component Tools

Skills receive a tool manifest filtered to `flow.tools` plus a small set of component tools for context access.

**Exposed to skills:**

| Tool | Component | Operations |
|---|---|---|
| `context_coordinator` | [Context Coordinator](../components/context_coordinator.md) | Read recent conversation turns |
| `memory_manager` | [Memory Manager](../components/memory_manager.md) | Read/write session scratchpad, read user preferences |
| `flow_stack` | [Flow Stack](../components/flow_stack.md) | Read slot values and prior flow results |

**Not exposed to skills:** Dialogue State (slot/flag access goes through flow_stack), Prompt Engineer (the LLM running the skill IS the reasoning engine), Ambiguity Handler (policy responsibility), Display Frame (policy responsibility).

### Tool Manifest

Every tool is registered in a manifest in domain config. See [Tool Smith](../utilities/tool_smith.md) for naming conventions, schema design, error contracts, and worked examples. Each entry specifies:

| Field | Description |
|---|---|
| `tool_id` | Unique identifier |
| `name` | Human-readable name |
| `input_schema` | JSON Schema for inputs |
| `output_schema` | JSON Schema for outputs |
| `idempotent` | Boolean (see Idempotency Annotations) |
| `timeout_ms` | Configurable timeout in milliseconds |

Validation: inputs validated against `input_schema` before execution, outputs against `output_schema` before consumption.

### Idempotency Annotations

| Annotation | Retry policy | Example |
|---|---|---|
| `idempotent: true` | Skill may auto-retry within its execution loop | SQL SELECT, API GET, file read |
| `idempotent: false` | Skill should not retry without explicit confirmation | SQL INSERT, file write, calendar create |

Persistent ownership rule: agentic flows persist via the skill; deterministic flows persist via the policy. **Never let both layers write** — double-persistence causes silent overwrites.

---

## Execute Function

Called by the Agent after NLU has routed and the flow is Active on the stack.

- **Input**: [Dialogue State](../components/dialogue_state.md), World, memory manager, ambiguity handler, prompt engineer, domain config
- **Output**: `tuple[`[DisplayFrame](../components/display_frame.md)`, bool]` — frame (always returned; never `None`) and `keep_going` flag

### Pre-Hook: `check()`

Cheap validation before spending tokens. On failure, set `has_issues` and return.

1. **Active flow exists** on the top of the flow stack
2. **Policy registered** for the active flow's name
3. **Required slots filled**
4. **Elective slots satisfied** (≥1 in each elective group)
5. **Tool manifest valid** — `flow.tools` resolves in the manifest
6. **Lethal Trifecta gate**: if a tool has all three capability tags (`accesses_private_data`, `receives_untrusted_input`, `communicates_externally`), force `requires_approval: true`. Reference: [Tool Smith § Capability Tags](../utilities/tool_smith.md)

Converse and Plan flows may have minimal slots; their readiness is primarily checks 1, 2, 5, 6.

### Method-Shape Contract

Every policy method follows the same skeleton. Sections expand or contract per flow.

```python
def <flow>_policy(self, flow, state, context, tools):
    # 1. Guard the entity slot — partial / general use early return.
    post_id, sec_id = self._resolve_source_ids(flow, state, tools)
    if not flow.slots[flow.entity_slot].check_if_filled() or not post_id:
        self.ambiguity.declare('partial', metadata={'missing_entity': 'post'})
        return DisplayFrame(flow.name())

    # 2. Branch on slot state. Most flows spend their lines here.
    if <specific ambiguity condition>:
        self.ambiguity.declare('specific', metadata={'missing_slot': '<name>'})
        frame = DisplayFrame(flow.name())
    elif <prerequisite missing>:
        self.flow_stack.stackon('<prereq>')
        state.keep_going = True
        frame = DisplayFrame(flow.name(), thoughts='<reason>')
    else:
        # 3. Dispatch.
        text, tool_log = self.llm_execute(flow, state, context, tools)
        saved, _ = self.engineer.tool_succeeded(tool_log, '<tool_name>')

        if not saved:
            frame = DisplayFrame(flow.name(),
                                 metadata={'violation': 'failed_to_save'},
                                 thoughts='<what the skill did wrong>')
        else:
            flow.status = 'Completed'
            frame = DisplayFrame(flow.name(), thoughts=text)
            frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})

    return frame  # single exit
```

**Key rules:**

- **Single return at end.** Early returns only for `partial` / `general` ambiguity (top-level grounding failures).
- **Slots route the flow.** First branch decision is "which slot state are we in?" — `flow.is_filled()` answers most of it.
- **Hand-write the guard per flow.** No universal `guard_slot` helper — slot semantics vary across flows.

### Failure Channels

Three distinct failure modes, three distinct channels:

| Failure | Channel | Frame |
|---|---|---|
| Tool-call failure (network, API down, deterministic tool returned `_success=False`) | Error frame | `metadata={'violation': 'tool_error', 'failed_tool': '<name>'}, code=msg` |
| Ambiguous user intent (missing slot, unresolved entity) | `ambiguity.declare(level, observation=, metadata=)` | Empty frame; RES asks the question |
| Skill produced malformed output | Error frame | `metadata={'violation': 'parse_failure'}, code=text` |

**Retry rule.** If a tool error is transient (timeout, lock), retry once via `BasePolicy.retry_tool(tools, name, params, max_attempts=2)`. Non-retryable or retry-failed → return the error frame.

**Never declare ambiguity for tool failures.** Tool-down is not a question for the user. Conflating channels hides root cause.

### Step 1 — Slot Review

NLU has already grounded entity, slot, and intent before the policy runs. The policy does NOT call `read_metadata` or `find_posts` to re-ground — it uses what's in `flow.slots` and the resolved-context dict.

If a required slot is missing after NLU's slot-filling phase, declare `specific` ambiguity and return — do not invoke the skill.

For optional slots with a defensible default, commit the default at policy entry and proceed:

```python
if not flow.slots['<optional>'].check_if_filled():
    flow.fill_slot_values({'<optional>': <default>})
```

### Step 2 — Tool Invocations (Agentic Flows Only)

Once required slots are filled, an agentic policy invokes the flow's skill via `llm_execute`. The skill runs in a tool-call loop (8-iteration cap) and terminates by returning `(text, tool_log)`.

**The skill does NOT:**
- Modify dialogue state or flow stack directly
- Construct the Display Frame
- Declare ambiguity through the Ambiguity Handler
- Call other flows or trigger re-routing

### Step 3 — Result Processing

The policy reads `tool_log` and constructs the frame. Single exit at the bottom of the policy. Three branches:

**Success** — persistence tool succeeded:
- Build success frame with `thoughts=text` + appropriate block (`card`, `selection`, `list`, `compare`, `toast`, etc.)
- Set `flow.status = 'Completed'`
- Route by intent: domain-specific intents typically attach a `card` block; Converse flows usually attach no block; Plan and Internal flows write findings to the scratchpad

**Violation** — skill ran but produced an unusable result:
- Build error frame with the appropriate `violation` code
- Specifics go in `thoughts` (natural language) or `code` (raw payload)

**Ambiguity** — slot state requires user input:
- `self.ambiguity.declare(level, observation=, metadata=)`
- Return empty frame; RES asks the clarification question

### Step 4 — Flow Completion

After processing results:

1. **Mark Completed** on success; leave Active on violation/ambiguity.
2. **Set flags**: `keep_going` if the Agent should continue without user input (only valid inside an active Plan); `has_issues` if results are degraded.
3. **Session scratchpad update** via `MemoryManager.write_scratchpad(flow.name(), payload)` when the flow produced findings consumers may need.

### Post-Hook: `verify()`

1. **Frame returned** (never `None`)
2. **Slot values intact** — no slots inadvertently cleared
3. **No duplicate flows** for same name in Active/Pending
4. **Flags coherent** — `keep_going` only when an active Plan owns the next flow

---

## Plan Policy

The Plan policy decomposes a complex task into sub-flows rather than executing a tool directly. Each Plan flow is restricted to a specific set of related flows, narrowing scope and increasing precision.

The process:

1. The policy receives context history and a list of candidate flows with slots and tools.
2. The policy generates two versions of the plan:
   - **Freeform plan**: describes goal, steps, open questions, verification ideas — shared with the user for feedback.
   - **Structured plan**: JSON with `description`, `sub_flows` (each with `flow_name`, `slots`, `tools`, `rationale`, `status`), `ambiguities`, `tool_calls` (lookups the plan can resolve without bothering the user), `verification` points.
3. The freeform plan goes to the user; the structured plan is stored on the Dialogue State (NOT in the scratchpad — the structure must survive).
4. On approval, push each sub-flow onto the stack; set `has_plan` and `keep_going`. On rejection, regenerate from step 2.
5. On each subsequent turn, the policy checks structured plan against verification points:
   - Sub-flow failed → set `keep_going=False`, let RES report and ask the user.
   - Sub-flow incomplete → mark `in_progress`, store partial results in scratchpad, attempt re-planning.
   - Sub-flow completed → write final results to scratchpad / frame, update status, keep `keep_going=True`.
6. When all sub-flows complete, run verification one final time. If all pass, mark Completed.
7. RES pops the plan flow and returns the final response, clearing `has_plan`.

Reference: [Flow Stack § Plan Flow Lifecycle](../components/flow_stack.md), [Dialogue State](../components/dialogue_state.md), [Memory Manager § Session Scratchpad](../components/memory_manager.md), [RES § Pre-Hook](res.md)

---

## Recover Function

Called when a policy returns an error frame or when post-hook detects issues.

- **Input**: dialogue state, last frame, ambiguity handler, domain config
- **Output**: recovery action for the Agent

### Recovery Strategies

The Agent picks one based on the situation:

1. **Retry once** — for transient tool errors (`tool_error` violations classified as transient). Use `BasePolicy.retry_tool` inside the policy when feasible; the recover-level retry is a backstop.
2. **Re-route via contemplate** — send to [NLU `contemplate()`](nlu.md) when the policy declared `partial` or `specific` ambiguity that may be the wrong flow detection. Mark current flow Invalid; best-effort slot mapping transfers compatible values to the new flow.
3. **Escalate to user** — go to RES to ask the user for clarification. This is the terminal recovery action.

### Yield-When-Stacked

When a Converse intent (`endorse`, `dismiss`) pushes onto an already-active flow during a confirmation resolution turn, the Converse policy yields with an empty frame and `state.keep_going=True` rather than running its own chit-chat skill. The underlying flow's resolution turn consumes the user's accept/decline. PEX `_validate_frame` allows empty frames when `keep_going=True` — the empty frame here is intentional, not a bug for retry to chase.

### Hard-Coded Fallbacks

Rare. Some policies redirect to a sibling flow when the user's intent maps elsewhere than NLU detected. Process: `flow_stack.fallback('<sibling>')` + `state.keep_going=True` + `thoughts='<why we re-routed>'`. Use only when the intent genuinely belongs elsewhere — never for skill errors (use error frames) or tool failures (use error frames).
