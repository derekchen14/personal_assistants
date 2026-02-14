# Phase 6 — Policies

Write per-flow policies and skill templates. Code flows in batches, test each batch before continuing. This is where the agent learns to do real work.

## Context

Each flow has a policy (deterministic skeleton) and a skill template (LLM prompt). The hybrid model keeps the deterministic parts predictable and the creative parts flexible. Policies are organized by intent — 7 policy files per domain. Flows are brought up in batches: first 16, then 16 more, then stub the remaining 16.

**Prerequisites**: Phase 5 complete — all components, modules, and Agent orchestrator are implemented and working.

**Outputs**: 32 working flows with unit tests, 16 stubbed flows, complete skill templates.

**Spec references**: [pex.md § Policies and Tools](../modules/pex.md), [flow_stack.md](../components/flow_stack.md), [tool_smith.md § Skill Templates](../utilities/tool_smith.md)

---

## Steps

### Step 1 — Create Policy File Structure

Create 7 policy files per domain, one per intent:

```
backend/modules/policies/
├── __init__.py
├── plan_policies.py
├── converse_policies.py
├── internal_policies.py
├── <read_intent>_policies.py      # e.g., source_policies.py, analyze_policies.py
├── <prepare_intent>_policies.py   # e.g., prep_policies.py, clean_policies.py
├── <transform_intent>_policies.py # e.g., cook_policies.py, transform_policies.py
└── <schedule_intent>_policies.py  # e.g., plate_policies.py, report_policies.py
```

Each file contains policy class methods for all flows in that intent.

### Step 2 — Understand the Hybrid Model

Each policy has two parts:

**Deterministic skeleton** (class method):
- Slot review: check required/elective/optional slots, fill from context/memory, declare ambiguity if missing
- Skill invocation: call the skill with the right tools and context
- Result processing: create Frame from skill output, route by intent
- Flow completion: mark Completed, set flags, post-hook verification
- Recovery escalation: retry, gather context, re-route, escalate

**LLM-driven skill**:
- Tool selection: choose which tools to call and in what order
- Tool execution: call tools, validate results, retry on failure
- Context gathering: read conversation history, scratchpad, prior flow results
- Result gathering: assemble structured output from tool results

**Skill output contract** — every skill returns exactly one of:

| Outcome | Meaning | Policy action |
|---|---|---|
| `success` | Tools executed, results gathered | Create Frame, mark Completed |
| `failure` | Tools returned errors, partial results may exist | Add warning to Frame, attempt degradation |
| `uncertain` | Skill cannot proceed, needs clarification | Carry over previous Frame, enter recovery |

### Step 3 — Per-Flow Checklist

Each flow requires these 8 artifacts:

1. **Domain config entry**: `ontology.py` entry + YAML tool bindings (already done in Phase 2–3)
2. **10 utterances**: Diverse user requests that should trigger this flow — used for guidance, testing, and debugging
3. **NLU prompt update**: Add exemplars for flow detection to `for_experts.py` (or create new prompt)
4. **Concrete slots**: Types, validators, defaults — make the slot schema executable
5. **Policy class method**: Deterministic skeleton in the intent's policy file — slot review, skill invocation, result processing, flow completion
6. **Skill template**: Markdown file in `backend/prompts/skills/<dact>.md` — flow description, slot-to-parameter mapping, expected tool sequence, output format
7. **Display Frame output**: Define the exact frame attributes and block type for this flow
8. **Reflection loop decision**: Decide whether this flow benefits from a generate-evaluate-revise cycle. Enable for: creative generation (writing prose), complex code generation, multi-source synthesis. Most flows do NOT need it.

### Step 4 — Write Skill Templates

Each skill template lives in `backend/prompts/skills/<dact>.md` and provides slots 2–6 of the 8-slot prompt format:

```markdown
# <flow_name>

<Flow description — what this flow accomplishes, one paragraph>

## Slot-to-Parameter Mapping

Use these mappings as your default. Try them first. If a tool call fails,
you may adjust parameters based on error context.

| Slot | Tool | Parameter | Notes |
|---|---|---|---|
| <slot> | <tool_id> | <param> | <guidance> |

## Tool Sequence

1. Call `<tool_id>` with the mapped parameters
2. <conditional steps>
3. Return the result for display

## Output Format

<What shape the result should take for the Display Frame>
```

The Prompt Engineer injects slot 1 (grounding data) and slot 8 (final request) at assembly time. Slot 7 (closing reminder) is appended after exemplars.

**Slot mapping is guidance, not deterministic** — the LLM should:
1. Try the predicted mapping first
2. Adjust on failure based on error context
3. Stay within the tool's JSON Schema

### Step 5 — Code First 16 Flows (Batch 1)

Select 16 flows covering at least 5 intents so large parts of the pipeline are exercised early. **Avoid Plan and Internal flows** for this batch — focus on domain-specific and Converse flows.

For each flow, complete the per-flow checklist (Step 3).

**Testing**:
- Write 3–5 unit tests per flow
- Randomly select 4 utterances per flow → 64 test utterances total
- Run the agent end-to-end: verify all utterances classify correctly
- Iterate on code and NLU prompts until classification works

**Output**: 16 working flows with unit tests and passing classification.

### Step 6 — Code Next 16 Flows (Batch 2, 32 Total)

Code 16 more flows using the per-flow checklist. **Include Plan and Internal flows** this time to exercise the full assistant's capabilities.

For each flow, complete the per-flow checklist (Step 3).

**Testing**:
- Write 3–5 unit tests per flow
- Randomly select 3 utterances per flow → 96 test utterances total
- Run the agent end-to-end: verify all utterances classify correctly
- Iterate on code and NLU prompts as needed
- **Merge consideration**: If two flows are often confused with each other, consider merging them

**Output**: 32 working flows with unit tests and passing classification.

### Step 7 — Stub Remaining 16 Flows (48 Total)

Set a default warning for the remaining 48 − 32 = 16 flows:

```python
async def stubbed_flow(self, state, ...):
    """Default handler for unimplemented flows."""
    return {
        'outcome': 'failure',
        'error_category': 'not_implemented',
        'message': f'{state.active_flow.dact} flow is still in development',
    }
```

This ensures graceful handling when a user hits an unimplemented flow. The max limit is 64 flows per domain, leaving room for future expansion.

**Output**: 48 flows registered, 32 fully working, 16 stubbed with development warnings.

### Step 8 — Component Tools for Skills

Ensure the component tools are properly exposed to skills during PEX execution:

| Tool | Component | Operations |
|---|---|---|
| context_coordinator | Context Coordinator | Read conversation history (default 3 turns, can request more) |
| memory_manager | Memory Manager | Read/write scratchpad, read user preferences |
| flow_stack | Flow Stack | Read slot values, read metadata from current/previous flows |

These are NOT in the tool manifest — PEX provides them directly alongside flow-specific tools. Total tools per skill: 5–7.

### Step 9 — Test Structure

```
tests/
├── conftest.py              # Module-scoped fixtures for DB, auth, test data
├── test_nlu.py              # NLU classification tests
├── test_pex.py              # Policy execution tests
├── test_res.py              # Response generation tests
└── test_flows/
    ├── {001}_query.py       # Per-flow integration tests
    ├── {002}_measure.py     # Named by dax code + flow name
    └── ...
```

**Test naming**: `{dax}_flow_name.py` — ordered by dax code. Tests are stateful and accumulate conversation history across a test file.

**Assertion patterns**: Substring matching on response text, token membership, SQL/code inspection, action verification, negative assertions.

---

## Files to Modify/Create

| Action | File | Description |
|---|---|---|
| Create | `<domain>/backend/modules/policies/plan_policies.py` | Plan intent policies |
| Create | `<domain>/backend/modules/policies/converse_policies.py` | Converse intent policies |
| Create | `<domain>/backend/modules/policies/internal_policies.py` | Internal intent policies |
| Create | `<domain>/backend/modules/policies/<intent>_policies.py` | 4 domain-specific intent policy files |
| Create | `<domain>/backend/prompts/skills/<dact>.md` | Skill template per flow (48 files) |
| Modify | `<domain>/backend/prompts/for_experts.py` | NLU intent/flow classification prompts with exemplars |
| Create | `<domain>/tests/test_flows/{dax}_{flow}.py` | Per-flow integration tests |
| Create | `<domain>/tests/test_nlu.py` | NLU classification tests |
| Create | `<domain>/tests/test_pex.py` | Policy execution tests |
| Create | `<domain>/tests/test_res.py` | Response generation tests |

---

## Verification

- [ ] 7 policy files created (one per intent)
- [ ] Each of the 32 working flows has all 8 per-flow checklist items complete
- [ ] Each flow has 10 sample utterances
- [ ] Each flow has a skill template in `skills/<dact>.md`
- [ ] Skill templates follow the 8-slot format (providing slots 2–6)
- [ ] 3–5 unit tests per working flow
- [ ] Batch 1 (16 flows): all 64 test utterances classify correctly
- [ ] Batch 2 (32 flows): all 96 test utterances classify correctly
- [ ] 16 stubbed flows return graceful "in development" messages
- [ ] Plan flows correctly decompose into sub-flows and set `has_plan`/`keep_going`
- [ ] Internal flows run as background tasks without user-facing output
- [ ] Reflection loop works for flows that enable it
- [ ] No two flows frequently confused (merge if so)
- [ ] Component tools (CC, MM, flow_stack) accessible to skills
- [ ] End-to-end agent handles: simple query, multi-turn conversation, Plan decomposition
