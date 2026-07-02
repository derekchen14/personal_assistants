# Phase 8 — Prompt Writing

Assemble the full prompt suite: system prompts, NLU classification prompts, and PEX skill prompts. PEX composes the spoken reply directly via a voice Skill in its system prompt — there is no separate naturalization layer or template registry.

## Context

Prompts are the agent's instructions. **Sub-agent and tool prompts** follow the standard 8-slot format and return JSON (classification prompts add chain-of-thought); **module skills** (orchestrator how-to guides like the Workflow Planner, `explain`, `recap`/`recall`/`retrieve`) return nothing — they are injected guidance, not assembled into this format. This phase ensures all prompts are written, versioned, and organized.

**Prerequisites**: Phase 7 complete — 32 working flows with policies and skill templates.

**Outputs**: Complete prompt suite across all `for_*.py` files, prompt versioning.

**Spec references**: [style_guide.md § Prompt Engineering](../style_guide.md), [prompt_engineer.md](../components/prompt_engineer.md), [tool_smith.md § Skill Templates](../utilities/tool_smith.md)

---

## Steps

### Step 1 — Understand the 8-Slot Format

Every assembled **sub-agent/tool** prompt follows this structure, in order (module skills are injected guidance and return nothing):

| Slot | Name | Content |
|---|---|---|
| 1 | **Grounding data** | Runtime variables: `{columns}`, `{history}`, `{facts}`, schemas, table definitions |
| 2 | **Role and task** | Who the model is and the high-level task (from persona config) |
| 3 | **Detailed instructions** | Step-by-step guidance for the specific task |
| 4 | **Keywords and options** | Valid terms, enum lists, special vocabulary |
| 5 | **Output shape** | Exact JSON keys, types, and structure |
| 6 | **Exemplars** | Diverse examples with edge cases |
| 7 | **Closing reminder** | One-liner reinforcing the output format |
| 8 | **Final request** | The current query with runtime variables |

**Why this order**: Grounding data first (30% quality improvement per Anthropic research). Final request last (model's next token is the answer).

**Non-negotiable rules**:
- All prompts return parseable JSON — no plain text, no markdown
- Classification/decision prompts include a `"thought"` key before the answer
- Consistent delimiters: `##` for sections, `---` between exemplars
- `_Output_` label before each example response, followed by ` ```json `
- Exemplar variables use double-brace escaping (`{{`, `}}`) for f-string compatibility

### Step 2 — Prompt File Organization

Organize prompts by consumer:

| File | Scope | Consumer |
|---|---|---|
| `for_experts.py` | Intent & flow classification | NLU Step 1–2 |
| `for_nlu.py` | Entity grounding, slot filling | NLU Step 3 |
| `for_pex.py` | Policy execution, code generation | PEX skills |
| `for_contemplate.py` | Re-routing prompts | NLU contemplate() |
| `for_executors.py` | Domain-specific tool prompts | PEX skills (domain-specific) |
| `for_metadata.py` | Type inference, data quality | PEX skills (domain-specific) |
| `general.py` | System prompts, persona, conversation metadata | Shared |

Each domain has its own set. `for_executors.py` and `for_metadata.py` are always domain-specific.

### Step 3 — System Prompt and Persona

Write the system prompt in `general.py`. Compose from:

- **Persona**: tone, expertise_boundaries, name, response_style (from domain YAML)
- **Domain context**: what the agent does and doesn't do (from Phase 1 scoping)
- **Behavioral instructions**: output format, language constraints
- **Guardrails reference**: content filter, topic control

The system prompt is injected as slot 2 (role and task) in every prompt assembly.

### Step 4 — NLU Prompts

**Intent classification** — `classify_intent` (`for_experts.py`):
- Slot 1: conversation history (last 5 turns)
- Slot 4: all 7 intent names (3 universal + 4 domain) with descriptions
- Slot 5: `{"thought": "...", "intent": "..."}`
- Slot 6: ~32 exemplars covering all intents (NLU classification needs the most examples)

**Flow detection** — `detect_flow` (`for_experts.py`):
- Slot 1: conversation history + active flow state
- Slot 4: candidate dacts with descriptions (from predicted intent + edge flows)
- Slot 5: `{"thought": "...", "flow": "...", "confidence": 0.0}`
- Slot 6: ~32 exemplars with edge cases, ambiguous utterances

**Slot-filling** — `fill_slots` (`for_nlu.py`):
- Slot 1: conversation history + flow slot schema
- Slot 3: instructions for extracting slot values from context
- Slot 5: `{"slots": {"<name>": "<value>", ...}, "missing": [...]}`
- Slot 6: 7–10 exemplars per flow type

**Contemplate** (`for_contemplate.py`):
- Slot 1: conversation history + failed flow info + ambiguity metadata
- Slot 4: narrowed candidate set (exclude failed, include related)
- Slot 5: `{"thought": "...", "flow": "...", "confidence": 0.0}`
- Slot 6: ~16 exemplars showing re-routing decisions

### Step 5 — PEX Prompts

**Skill execution** (`for_pex.py`):
- Slots 2–6 come from the per-flow skill template (`skills/<dact>.md`)
- Slot 1: filled slot values + execution context + tool schemas
- Slot 8: "Execute the {dact} flow with the provided context"
- Slot 7: "Your entire response should be well-formatted JSON with no further text."

**Code guardrails** (applied to skill-generated code):
- `apply_guardrails(raw_code, language, valid_entities)` — strip markdown, disallowed imports, comments; validate entity references
- `activate_guardrails(raw_code, trigger_phrase)` — extract code blocks between delimiters
- Language-specific: `ast.parse` for Python, SQL parser for queries

**Domain-specific tool prompts** (`for_executors.py`):
- SQL generation, Python script generation, API call construction
- Each domain writes these differently

### Step 6 — Response Composition

There is no naturalization prompt, template registry, or `respond` tool. PEX composes the spoken reply directly over the turn's artifacts, tool results, and sub-agent results — worded by a **voice Skill** in its system prompt (persona, verbosity, and the convention to reference the visual display, e.g., "as shown below," rather than duplicate data). Clarification wording is owned by the Ambiguity Handler, not a response template.

### Step 7 — Exemplar Standards

| Prompt type | Count | Rationale |
|---|---|---|
| NLU `classify_intent` / `detect_flow` | ~32 | High-cardinality classification; examples are primary signal |
| NLU `contemplate()` | ~16 | Multi-step reasoning with subtle distinctions |
| PEX skill/policy | 7–10 | Moderate complexity |

**Exemplar rules**:
- Cover success, ambiguous, edge, and error/null cases
- Separated by `---` delimiter
- `_Output_` label before each example output
- Double-brace escaping for f-string compatibility
- Exemplars are a testing surface — if eval scores drop, add exemplars for failing cases first

### Step 8 — Prompt Versioning

- Each prompt template gets a unique ID and version: `{template_id}.v{N}`
- Evaluation results tie to specific versions
- Enable A/B testing and rollback of prompt changes
- Track `prompt_versions_used` in session records

### Step 9 — Variable Naming

- Runtime placeholders: `{snake_case}` in single curly braces
- Double braces `{{`, `}}` for literal braces in f-string templates
- Placeholder names match source data field names

---

## File Changes Summary

| Action | File | Description |
|---|---|---|
| Create | `<domain>/backend/prompts/general.py` | System prompt, persona composition |
| Modify | `<domain>/backend/prompts/for_experts.py` | NLU intent/flow classification with ~32 exemplars each |
| Create | `<domain>/backend/prompts/for_nlu.py` | Entity grounding, slot filling |
| Create | `<domain>/backend/prompts/for_pex.py` | Policy execution, code generation |
| Create | `<domain>/backend/prompts/for_contemplate.py` | Re-routing prompts |
| Create | `<domain>/backend/prompts/for_executors.py` | Domain-specific tool prompts |
| Create | `<domain>/backend/prompts/for_metadata.py` | Type inference, data quality |

---

## Verification

- [ ] All 7 prompt files exist in `backend/prompts/`
- [ ] System prompt composes persona correctly from domain config
- [ ] Every sub-agent/tool prompt follows the 8-slot format (module skills are guidance, exempt)
- [ ] All sub-agent/tool prompts return parseable JSON (skills return nothing)
- [ ] Classification prompts include `"thought"` key for chain-of-thought
- [ ] NLU intent prediction has ~32 diverse exemplars
- [ ] NLU flow detection has ~32 exemplars covering edge cases
- [ ] PEX skill prompts inject slot 1 and slot 8 correctly around skill templates
- [ ] PEX voice Skill composes the spoken reply directly from artifacts, tool results, and sub-agent results
- [ ] Prompt versioning: each template has `{template_id}.v{N}`
- [ ] Variable placeholders use `{snake_case}` consistently
- [ ] Exemplars cover success, ambiguous, edge, and error cases
- [ ] Code guardrails strip markdown fences, validate entity references
