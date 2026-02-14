# Phase 8 — Prompt Writing

Assemble the full prompt suite: system prompts, NLU classification prompts, PEX skill prompts, RES naturalization prompts, and the template registry.

## Context

Prompts are the agent's instructions. Every LLM call follows the standard 8-slot format, every output is JSON, and every classification prompt includes chain-of-thought reasoning. This phase ensures all prompts are written, versioned, and organized.

**Prerequisites**: Phase 7 complete — 32 working flows with policies and skill templates.

**Outputs**: Complete prompt suite across all `for_*.py` files, template registry with base + domain overrides, prompt versioning.

**Spec references**: [style_guide.md § Prompt Engineering](../style_guide.md), [prompt_engineer.md](../components/prompt_engineer.md), [tool_smith.md § Skill Templates](../utilities/tool_smith.md)

---

## Steps

### Step 1 — Understand the 8-Slot Format

Every assembled prompt follows this structure, in order:

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
| `for_res.py` | Response generation, naturalization | RES generate() |
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

**Intent prediction** (`for_experts.py`):
- Slot 1: conversation history (last 5 turns)
- Slot 4: all 6 user-facing intent names with descriptions
- Slot 5: `{"thought": "...", "intent": "..."}`
- Slot 6: ~32 exemplars covering all intents (NLU classification needs the most examples)

**Flow prediction** (`for_experts.py`):
- Slot 1: conversation history + active flow state
- Slot 4: candidate dacts with descriptions (from predicted intent + edge flows)
- Slot 5: `{"thought": "...", "flow": "...", "confidence": 0.0}`
- Slot 6: ~32 exemplars with edge cases, ambiguous utterances

**Slot-filling** (`for_nlu.py`):
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

### Step 6 — RES Prompts

**Naturalization** (`for_res.py`):
- Slot 1: filled template string + conversation history (5 turns) + user preferences (verbosity, depth)
- Slot 3: "Smooth this filled template into natural language. The response will be accompanied by a visual display, so reference it (e.g., 'as shown below') rather than duplicating data."
- Slot 5: `{"message": "...", "raw_utterance": "..."}`
- Slot 6: 3–5 exemplars (RES shaped more by instructions than pattern-matching)

**Multi-flow merge** (`for_res.py`):
- For >2 flows or overlapping outputs: LLM call to weave individual naturalized outputs into one coherent response
- For ≤2 non-overlapping: deterministic concatenation with transition phrases

**Clarification generation** (`for_res.py`):
- Dispatched by ambiguity level: general_ask, partial_ask, specific_ask, confirmation_ask
- Three generation modes: lexicalize (template → surface form), naturalize (rewrite to sound natural), compile (summarize metadata into response)

### Step 7 — Template Registry

Set up the template registry consumed by RES.

**Base templates** (`schemas/templates/base/`):
- One template per intent: `converse.txt`, `read.txt`, `prepare.txt`, `transform.txt`, `schedule.txt`, `plan.txt`, `internal.txt`
- Each defines the response structure for that intent

**Domain overrides** (`schemas/templates/<domain>/`):
- Override keyed by dact name, completely replaces the base intent template
- Example:
  ```
  draft_preview:
    template: "Here's your draft — {title}. Preview it on the right."
    block_hint: card
    skip_naturalize: false
  ```

**Features supported**:
- `block_hint` — suggested block type for display()
- `skip_naturalize` — skip LLM naturalization for structured confirmations
- Conditional sections — `{% if conflict %}Note: overlaps with {conflict_event}.{% endif %}`

**Lookup order**: domain override (by dact) → base template (by intent).

### Step 8 — Exemplar Standards

| Prompt type | Count | Rationale |
|---|---|---|
| NLU `think()` — intent/flow | ~32 | High-cardinality classification; examples are primary signal |
| NLU `contemplate()` | ~16 | Multi-step reasoning with subtle distinctions |
| PEX skill/policy | 7–10 | Moderate complexity |
| RES response generation | 3–5 | Shaped more by instructions and persona |

**Exemplar rules**:
- Cover success, ambiguous, edge, and error/null cases
- Separated by `---` delimiter
- `_Output_` label before each example output
- Double-brace escaping for f-string compatibility
- Exemplars are a testing surface — if eval scores drop, add exemplars for failing cases first

### Step 9 — Prompt Versioning

- Each prompt template gets a unique ID and version: `{template_id}.v{N}`
- Evaluation results tie to specific versions
- Enable A/B testing and rollback of prompt changes
- Track `prompt_versions_used` in session records

### Step 10 — Variable Naming

- Runtime placeholders: `{snake_case}` in single curly braces
- Double braces `{{`, `}}` for literal braces in f-string templates
- Placeholder names match source data field names

---

## Files to Modify/Create

| Action | File | Description |
|---|---|---|
| Create | `<domain>/backend/prompts/general.py` | System prompt, persona composition |
| Modify | `<domain>/backend/prompts/for_experts.py` | NLU intent/flow classification with ~32 exemplars each |
| Create | `<domain>/backend/prompts/for_nlu.py` | Entity grounding, slot filling |
| Create | `<domain>/backend/prompts/for_pex.py` | Policy execution, code generation |
| Create | `<domain>/backend/prompts/for_res.py` | Response generation, naturalization |
| Create | `<domain>/backend/prompts/for_contemplate.py` | Re-routing prompts |
| Create | `<domain>/backend/prompts/for_executors.py` | Domain-specific tool prompts |
| Create | `<domain>/backend/prompts/for_metadata.py` | Type inference, data quality |
| Create | `<domain>/schemas/templates/base/*.txt` | Base intent templates (7 files) |
| Create | `<domain>/schemas/templates/<domain>/*.txt` | Domain override templates |

---

## Verification

- [ ] All 8 prompt files exist in `backend/prompts/`
- [ ] System prompt composes persona correctly from domain config
- [ ] Every prompt follows the 8-slot format
- [ ] All prompts return parseable JSON
- [ ] Classification prompts include `"thought"` key for chain-of-thought
- [ ] NLU intent prediction has ~32 diverse exemplars
- [ ] NLU flow prediction has ~32 exemplars covering edge cases
- [ ] PEX skill prompts inject slot 1 and slot 8 correctly around skill templates
- [ ] RES naturalization produces natural-sounding output from filled templates
- [ ] Template registry has base templates for all 7 intents
- [ ] Domain overrides load correctly (by dact name)
- [ ] `block_hint` and `skip_naturalize` work in domain templates
- [ ] Conditional sections in templates render correctly
- [ ] Prompt versioning: each template has `{template_id}.v{N}`
- [ ] Variable placeholders use `{snake_case}` consistently
- [ ] Exemplars cover success, ambiguous, edge, and error cases
- [ ] Code guardrails strip markdown fences, validate entity references
