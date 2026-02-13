# Prompt Engineer

Model-agnostic prompt interface. Assembles, executes, and validates prompts for any calling component.

## Core Responsibilities

### Model Invocation
- Model-agnostic interface: swap providers without changing calling code
- Streaming vs. regular response modes
- Exposes a generic prompt function — any component (NLU, PEX, RES, Ambiguity Handler) can request a prompt execution without caller-specific logic or special treatment

### Prompt Composition
- Assembles prompts from multiple sources: system prompt, persona, conversation history, memory context, tool results
- **Persona**: per-domain config (tone, expertise boundaries) loaded from Configuration utility; composed into the system prompt alongside instructions — minimal, just a config block
- **Output style** (concise/verbose, technical/casual, markdown/plain) is a per-call override of persona defaults, passed as a structured parameter
- **Format standards**: All prompts follow the standard 8-slot format defined in the [Style Guide's Prompt Engineering section](../style_guide.md#prompt-engineering) — grounding data first, exemplars (count varies by module), JSON output, closing reminder
- **Few-shot examples**: Intent classification and flow prediction prompts should include domain-specific few-shot examples. The scaffold's prompt files serve as the starting point for prompt development in new domains

### Prompt File Organization

Prompt templates are organized by consumer, following a `for_{consumer}.py` naming convention:

| File | Scope | Consumer |
|---|---|---|
| `for_experts.py` | Intent & flow classification | NLU Step 1–2 |
| `for_nlu.py` | Entity grounding, slot filling | NLU Step 3 |
| `for_pex.py` | Policy execution, code generation | PEX skills |
| `for_res.py` | Response generation, naturalization | RES generate() |
| `for_contemplate.py` | Re-routing prompts | NLU contemplate() |
| `for_executors.py` | Domain-specific tool prompts (SQL, Python, API) | PEX skills (domain-specific) |
| `for_metadata.py` | Type inference, data quality detection | PEX skills (domain-specific) |
| `general.py` | System prompts, persona, conversation metadata | Shared |

Each domain has its own set of prompt files. `for_executors.py` and `for_metadata.py` contain domain-specific content — every domain defines these but with different templates.

### Backoff & Retry
- All model invocations use exponential backoff on rate limits, timeouts, and server errors
- Retry policy configured via resilience settings in domain config (max attempts, backoff base/max, retriable error types)
- Prompt Engineer owns all retry logic — callers do not implement their own backoff

### Guardrails & Retries
- Validate structured output against expected schemas (JSON, SQL, Python)
- When validation fails, retry with a reformulated prompt — add stronger constraints or examples of the expected format
- Track which reformulations succeed to improve first-pass accuracy over time
- Sandbox or sanitization for safety

### Output Parsing
- Parse LLM output into structured format
- Handle partial/malformed responses gracefully

### Data Preparation
- Format tables, lists, and structured data for LLM consumption
- Standard formatting protocol for data previews

### Token Budget Logging
- Track token usage across prompt sections (conversation history, memory, tool results, system prompt, response) for developer diagnostics
- Does not affect agent logic — purely logging/informational

### Prompt Versioning
- Each prompt template gets a unique ID and version
- Evaluation results are tied to specific template versions (see `evaluation.md`)
- Enables A/B testing and rollback of prompt changes
