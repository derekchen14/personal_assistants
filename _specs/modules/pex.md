# PEX — Policy Executor

The execution engine of the agent. Holds all policies associated with each flow — this is where the agent's actions happen. Each policy is a hybrid: a deterministic class method that delegates tool execution to a skill (an LLM with access to tools). The class method handles slot review, recovery, frame creation, and flow lifecycle. The skill handles tool selection, execution, and result gathering.

**Module principle**: PEX processes information but does not store it. It mutates the State and Frame objects passed to it.

- **Execute function**: primary path for running the active flow's policy
- **Recover function**: failure escalation

**Policy file imports**: PEX imports from 7 policy files per domain, one per intent:

- `plan_policies` — Plan
- `converse_policies` — Converse
- `internal_policies` — Internal
- `read_policies` — Read
- `prepare_policies` — Prepare
- `transform_policies` — Transform
- `schedule_policies` — Schedule

Each domain agent has its own set of 7 files. The flows within each are domain-specific, even if structurally similar across domains.

---

## Policies and Tools

### Policy Structure — Hybrid Model

Each policy is a class method (deterministic skeleton) that delegates tool execution to a skill (LLM-driven). One policy per flow (1:1 mapping via dact name).

**Deterministic (class method)**:
- Slot review: check, fill from context/memory, declare ambiguity if missing
- Skill invocation: call the skill with the right tools and context
- Result processing: create Frame from skill output, route by intent
- Flow completion: mark Completed, set flags, post-hook checks, results verification
- Recovery escalation: retry, gather context (internal flows), re-route (contemplate), escalate

**LLM-driven (skill)**:
- Tool selection: choose which tools to call and in what order
- Tool execution: call tools, validate results, retry on failure
- Context gathering: read conversation history, scratchpad, prior flow results
- Result gathering: assemble structured output from tool results

Reference: [Flow Stack](../components/flow_stack.md), [Configuration](../utilities/configuration.md), [Tool Smith](../utilities/tool_smith.md)

### Skill Execution Model

A skill is a per-flow prompt template executed by an LLM with tools. It is not a separate agent — it runs within the policy's execution context. The policy calls the skill, the skill runs in a loop using tools, and returns structured JSON.

**Skill output contract** — every skill returns one of three outcomes:

| Outcome | Meaning | Policy action |
|---|---|---|
| `success` | Tools executed, results gathered | Create Frame, mark Completed |
| `failure` | Tools returned errors, partial results may exist | Add warning to Frame, attempt degradation |
| `uncertain` | Skill cannot proceed, needs clarification | Carry over previous Frame, enter recovery |

Output structure:

```json
{ "outcome": "success", "data": { ... }, "scratchpad_entries": [...] }
```
```json
{ "outcome": "failure", "error_category": "...", "message": "...", "partial_data": null }
```
```json
{ "outcome": "uncertain", "reason": "...", "context": { ... } }
```

All outcomes can only be returned once per skill invocation — it terminates skill execution immediately.

### Component Tools

Skills have access to 5–7 tools: 1–3 flow-specific tools (from the tool manifest) plus component tools for context access.

**Exposed to skills:**

| Tool | Component | Operations | Rationale |
|---|---|---|---|
| context_coordinator | [Context Coordinator](../components/context_coordinator.md) | Read conversation history (default 3 turns back, skill may request more) | Skill needs conversation context for tool decisions |
| memory_manager | [Memory Manager](../components/memory_manager.md) | Read and write session scratchpad, read user preferences | Skill writes intermediate findings during execution |
| flow_stack | [Flow Stack](../components/flow_stack.md) | Read slot values, read metadata from current and previous flows | Skill needs slot values and prior flow results |

**Not exposed to skills:**

| Component | Rationale |
|---|---|
| Dialogue State | Relevant info (slots, flags) is accessible through flow_stack |
| Prompt Engineer | The LLM running the skill IS the reasoning engine — no need for a second LLM layer |
| Ambiguity Handler | Policy responsibility; if the skill is uncertain, it returns the `uncertain` outcome |
| Display Frame | Policy responsibility; skill returns data, policy creates the Frame |

**Total tools per skill invocation**: 5–7, targeting the 80–90% tool selection accuracy band.

### Tool Manifest

Every tool is registered in a manifest in domain config. See [Tool Smith](../utilities/tool_smith.md) for how to design tools from flows — naming conventions, schema design, error contracts, and worked examples. Each entry specifies:

| Field | Description |
|---|---|
| `tool_id` | Unique identifier |
| `name` | Human-readable name |
| `input_schema` | JSON Schema for inputs |
| `output_schema` | JSON Schema for outputs |
| `idempotent` | Boolean (see Idempotency Annotations) |
| `timeout_ms` | Configurable timeout in milliseconds |

Validation: inputs validated against `input_schema` before execution, outputs validated against `output_schema` before consumption. Validation failures within the skill contribute to the skill's outcome (failure or uncertain).

### Idempotency Annotations

Each tool in the manifest is annotated `idempotent: true` or `idempotent: false`.

| Annotation | Retry policy | Example |
|---|---|---|
| `idempotent: true` | Skill may auto-retry within its execution loop | SQL SELECT, API GET, file read |
| `idempotent: false` | Skill should not retry without explicit confirmation | SQL INSERT, file write, calendar create |

---

## Execute Function

Called by the Agent after NLU has routed and the flow is Active on the stack.

- **Input**: Dialogue state (active flow + filled slots), context coordinator, display frame, memory manager, ambiguity handler, domain config
- **Output**: Mutated dialogue state (flow marked Completed on success, flags updated), populated display frame (domain-specific intents only), session scratchpad update

### Pre-Hook: `check()`

Cheap validation before spending tokens on execution. On failure, set `has_issues` on dialogue state and return to Agent.

7 checks:

1. **Active flow exists**: Flow stack has an Active flow at the top
2. **Policy registered**: Active flow's dact has a registered policy in domain config
3. **Required slots filled**: All Required slots have values passing type validation (after Step 1 slot-filling attempts)
4. **Elective slots satisfied**: At least one of each Elective slot group is filled
5. **Tool manifest valid**: Policy's tools exist in the manifest with loadable schemas
6. **Timeout configured**: Each tool has a `timeout_ms` value (explicit or from shared defaults)
7. **Lethal Trifecta gate**: If any tool in this flow's manifest entry has all three capability tags set (`accesses_private_data`, `receives_untrusted_input`, `communicates_externally`), force `requires_approval: true` regardless of manifest setting. This prevents exfiltration paths where untrusted input accesses private data and sends it externally. Reference: [Tool Smith § Capability Tags](../utilities/tool_smith.md)

Note: Converse and Plan flows may have minimal or no slots (their "readiness" is primarily checks 1, 2, 5, 6). Pre-hook checks 3 and 4 run after Step 1's slot-filling attempts.

### Step 1 — Slot Review

The policy reviews all slots before invoking the skill. LLM involved only for slot-filling if necessary.

1. **Pull active flow**: Get the active flow from the flow stack via dialogue state
2. **Check missing slots**: Compare filled slots against the flow's slot requirements (Required, Elective, Optional)
3. **Fill from context**: Attempt to fill missing slots from Context Coordinator (recent conversation turns) and Memory Manager (user preferences, business context). This is a deterministic lookup, but uses LLM reasoning to read the info and decide how to fill the slot if possible — e.g., if the user mentioned "chicken parmesan" two turns ago and the `recipe` slot is empty, fill it.
4. **Declare ambiguity if still missing**: If required slots remain empty after context/memory lookup, declare ambiguity via the Ambiguity Handler and return to Agent. Do not invoke the skill.

### Step 2 — Tool Invocations

Once all required slots are filled, the policy invokes the flow's skill.

**Setup**:

- Assemble the skill prompt from the per-flow template + filled slot values + execution context
- Provide tools: flow-specific tools (1–3 from manifest) + component tools (context_coordinator, memory_manager, flow_stack)
- Set a skill-level timeout: sum of constituent tool timeouts + overhead

**Skill execution**:

The skill runs in a loop, autonomously selecting and calling tools. What the skill does:

- Chooses which tools to call and in what order based on slot values and context
- Executes tool calls, validates results against output schemas
- Retries failed tool calls if idempotent (tool-level retry, distinct from flow-level retry in recover). Generic retry strategies available to all policies: double `max_tokens` on truncation, re-generate with flow-specific hints on error. Skill-specific strategies (e.g., incomplete code regex detection for code-generating tools) are defined per-skill.
- Reads from conversation history and previous flow results via component tools
- Writes intermediate findings to session scratchpad via memory_manager
- Terminates by returning structured JSON (success, failure, or uncertain)

**Code guardrails** (applied to skill-generated code before execution):

- `apply_guardrails(raw_code, language, valid_entities)` — strip markdown fences, disallowed imports, inline comments; validate entity references against known schema
- `activate_guardrails(raw_code, trigger_phrase)` — extract code blocks between delimiters when LLM output mixes prose and code
- Language-specific validation: `ast.parse` for Python (validates single function definitions), SQL parser for query validation

**Optional reflection loop** — For flows marked as creative or complex in domain config (e.g., writing prose, generating reports, crafting long SQL, coding functions), the skill can run a generate-evaluate-revise cycle before returning its final output. The skill generates a candidate result, self-evaluates against the flow's success criteria (written in the skill template), and revises if the evaluation identifies issues. This is a single revision pass (not unbounded iteration) — one generate, one evaluate, one optional revise. Flows that benefit from reflection are flagged per-flow in domain config; most flows do not need it.

**LATS for Plan decomposition** — When the active flow is a Plan intent, the skill can use Language Agent Tree Search to explore multiple decomposition strategies before committing. See [Flow Stack § LATS for Plan Decomposition](../components/flow_stack.md).

What the skill does NOT do:

- Modify dialogue state or flow stack directly
- Create or modify the Display Frame
- Declare ambiguity through the Ambiguity Handler (returns `uncertain` outcome instead)
- Call other flows or trigger re-routing
- Push or pop flows on the stack

### Step 3 — Result Processing

The policy processes the skill's structured JSON output. Three branches:

**Success** — skill returned valid data:

- Extract result data from skill output
- Create Display Frame, route by intent:

  **Domain-specific intents** (Read, Prepare, Transform, Schedule) → **Display Frame**: set frame attributes (`data`, `source`, `display_name`, `display_type`, `chart_type`). Multi-turn flows update existing frame. Large data: first page only (default 512 rows) with `table_id` for pagination. Reference: [Display Frame](../components/display_frame.md)

  **Converse** → **Scratchpad + Dialogue State**: format results and write to scratchpad. RES reads from scratchpad to compose the user-facing response.

  **Plan** → **Flow Stack + Scratchpad**: decompose into sub-flows, push onto flow stack. Set `has_plan` and `keep_going` flags. Write plan summary to scratchpad.

  **Internal** → **Scratchpad + Dialogue State**: write findings to scratchpad. The active user-facing flow may be waiting on these results. Can update dialogue state independently but never the Display Frame.

**Failure** — skill encountered an error but is not uncertain:

- If partial results available, proceed with partial data
- Add error information to the Frame as a warning
- Set metadata on Frame so RES communicates the limitation to the user

**Uncertain** — skill could not proceed and needs clarification:

- Do NOT create a new Frame; carry over the previous Frame
- Enter recovery escalation (see [Recover Function](#recover-function))

### Step 4 — Flow Completion

After processing results:

1. **Store Frame**: Add the Frame to the agent's frame collection
2. **Update flow lifecycle**: Mark the active flow as **Completed** on the flow stack (on success). Leave Active on failure with partial results. Leave Active on uncertain (recovery may retry).
3. **Set flags**: `keep_going` if Agent should continue to next flow without user input. `has_issues` if results are degraded.
4. **Verification checks**: Validate Frame has required attributes, slot values are intact, no duplicate Active/Pending flows for same dact
5. **Session scratchpad update**: Write 3–5 summarized snippets via Memory Manager (in addition to any writes the skill made during execution). Reflective summaries of what the flow discovered, not raw tool output. Reference: [Memory Manager](../components/memory_manager.md)

### Post-Hook: `verify()`

5 checks:

1. **Dialogue state consistency**: Active flow still exists on stack, not corrupted
2. **Slot values intact**: No slots inadvertently cleared during execution
3. **Output well-formed**: Display frame has `data` and `display_type` (domain-specific intents); or scratchpad was written (Converse/Plan/Internal)
4. **No duplicate flows**: No duplicate Active/Pending flows for same dact
5. **Flags coherent**: If `keep_going` set, another Pending flow must exist on stack; if `has_issues` was set, it must not have been silently cleared

After post-hook, exit PEX and return control to Agent. Agent calls RES (starting with pre-hook RES checks).

---

## Recover Function

Called when the skill returns an `uncertain` outcome, or when post-hook detects issues. Recovery policy decides what to do in order of escalating severity.

- **Input**: Dialogue state, skill output (ambiguous reason + context), ambiguity handler, domain config
- **Output**: Recovery action for the Agent

### Recovery Escalation

Tried in order:

1. **Retry skill**: Re-invoke the same skill with the same inputs. This is a flow-level retry (distinct from tool-level retries within the skill). The retry may benefit from scratchpad entries the skill wrote before returning ambiguity. Limit: 1 retry.

2. **Gather more context**: Push Internal flows onto the flow stack to collect supporting information (peek at DB rows, check Memory/FAQs/Context). Set `keep_going` so the Agent runs the Internal flow first, then returns to retry this flow with enriched context in the scratchpad.

3. **Re-route via contemplate**: Send to NLU `contemplate()` for fallback flow or plan decomposition. Two sub-options:
   - **Fallback**: Create a simpler flow that achieves a partial goal. Best-effort slot mapping transfers compatible values. Mark current flow Invalid.
   - **Planning**: If the request is too complex for one flow, decompose into a plan. Push sub-flows onto the stack, set `has_plan` and `keep_going`.

4. **Escalate to user**: If all above fail, go to RES to ask the user for clarification. This is the terminal recovery action — the agent admits it cannot proceed without human input.

### Agent Handoff

After choosing a recovery strategy, recover() returns control to the Agent with the chosen action. Recover never calls contemplate() or RES directly. The Agent routes:

- **Retry**: Re-enter execute() for this flow
- **Internal flow**: Push Internal flow, set `keep_going`, Agent runs it
- **Re-route**: Send to NLU `contemplate()` for fallback or plan decomposition
- **Escalate**: Go to RES for user clarification

### Hard-Coded Fallbacks

Rare case — some policies have hard-coded fallback flows for known failure modes. Process follows Flow Stack fallback protocol: create new flow, best-effort slot mapping, mark old flow Invalid, push new flow. Bypasses the recovery escalation above.

**Worked example** (data analysis domain): A query returns empty results because the target data doesn't exist yet. The policy detects the error type and redirects to a structural operation (insert/merge/split) based on source/target entity counts — "staging table" redirect. This is a hard-coded fallback: the policy knows that certain query failures mean the data needs to be created first.

- Reference: [Flow Stack — Fallback Protocol](../components/flow_stack.md)
