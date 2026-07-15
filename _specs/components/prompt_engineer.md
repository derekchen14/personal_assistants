# Prompt Engineer

A [PEX](../modules/pex.md) surface: the provider-agnostic prompt interface that every module's model call
routes through (NLU detection, MEM summarization, PEX skills), owned by PEX as the module that executes. It
assembles, executes, and validates prompts for any calling component, and owns model selection, prompt caching,
retry/backoff, and structured-output parsing.

## Provider-Agnostic Model Selection

`PromptEngineer` routes through a single-token family swap.

- **`ACTIVE_FAMILY`** — module-level constant naming the current provider family (`claude`, `gemini`, `gpt`, `together`).
- **`FAMILY_TIERS`** — map from family → `(low, med, high)` tuple of concrete model IDs.
- **Call sites pass abstract tiers** (`'low' | 'med' | 'high'`); the engineer resolves them through the active family on every call.

| Tier | Used for |
|---|---|
| `low` | Fast classification, lightweight tools |
| `med` | Skill execution, slot-filling, default flow detection |
| `high` | Difficult re-routing, plan decomposition, ensemble tiebreakers |

Per-family code paths handle the bits that differ:

- `_call_claude_with_tools` — Anthropic SDK; native `cache_control` markers
- `_call_gemini_with_tools` — Google SDK; `_sanitize_for_gemini` strips `oneOf/anyOf/allOf` (Gemini's restricted JSON Schema subset)
- `_call_gpt_with_tools`, `_call_together_with_tools` — share an OpenAI-compatible loop
- Reasoning-token budgets (Claude extended thinking, Gemini Pro, GPT-5 reasoning, Kimi) are absorbed inside `_call_<family>` — never pushed onto the caller's `max_tokens`.

Swapping families is a one-line change. Domain code never references a concrete model ID.

## Two Skill Entry Points

`flow_reply` and `flow_execute` are siblings — both run a per-flow skill prompt; they differ only in whether tools are exposed.

```python
text = engineer.flow_reply(flow, convo_history, scratchpad,
                           skill_name=..., skill_prompt=..., resolved=..., max_tokens=N)

text, tool_log = engineer.flow_execute(flow, convo_history, scratchpad, tool_defs,
                                    call_tool, skill_name=..., skill_prompt=...,
                                    resolved=..., max_tokens=N)
```

- `flow_reply` — single-shot LLM call; returns text only. Used when the skill produces prose or structured output that the policy parses.
- `flow_execute` — agentic loop with an 8-iteration cap; returns `(text, tool_log)`. Used when the skill must select tools and persist results.

`PromptEngineer` is also **callable** for one-shot prompts that don't go through a skill: `engineer(prompt, task='<task>', max_tokens=N)` uses `_TASK_SUFFIXES[task]` for the system prompt.

The deterministic-vs-agentic split is implied by the policy code — a deterministic flow calls `tools(name, params)` directly and never enters the engineer's skill path. There is no `flow.deterministic` attribute.

## Three-Layer Prompt Architecture

Every agentic flow assembles its prompt from three layers, owned by three different files.

| Layer | Owner | Contents | Cacheable? |
|---|---|---|---|
| **System prompt** | `prompts/general.py::build_system` (universal persona) + `prompts/pex/sys_prompts.py::PROMPTS[intent]` (intent-scoped Background) + `prompts/pex/skills/<flow>.md` (skill body) | Persona, ID schema, outline depth, ambiguity + violation tables, intent Background, skill behavior | yes |
| **User message** | `prompts/pex/starters/<flow>.py::build(flow, resolved, user_text)` | `<task>` framing, content tag with preloaded data, `<resolved_details>`, `<recent_conversation>` | no |
| **Tool definitions** | `schemas/tool_manifest_<domain>.json` filtered to `flow.tools` | Tool signatures and descriptions | yes |

**Critical division.** System prompt = constraints (persona, guardrails, schemas, hard rules). User message = task (this turn's job, this turn's data). Tool defs = the agentic loop's action space. Per-turn tokens (date, session ID, latest utterance) live in the user message *only* — they must never appear inside cacheable prefixes.

## Prompt Caching

Prompt caching is first-class. Stable content goes first; volatile content goes last.

- **Marker.** `cache_control={'type': 'ephemeral'}` is set on the tail of the system prompt and on the last entry of the tool-defs array.
- **TTL.** 1 hour. Reads cost 0.1× input tokens; writes cost 1.25× (5-minute) or 2× (1-hour). Pure cost + latency win at any non-trivial prompt size.
- **Invalidation hazard.** A single per-turn token interleaved into the cacheable prefix invalidates the entry on every call. Keep the date, session ID, and latest utterance strictly in the user message.

The user message (Layer 2) is per-turn and uncacheable; that's the right place for volatile content.

## Skill File Structure

Per-flow skill prompts live at `backend/prompts/pex/skills/<flow>.md` and start with YAML frontmatter:

```yaml
---
name: <flow_name>            # matches flow.name()
description: <1-sentence purpose>
version: 1
stages:                      # optional; only if multi-stage
  - propose
  - direct
tools:                       # optional; explicit allowlist
  - find_posts
  - generate_outline
---
```

`load_skill_template(name)` parses + strips the frontmatter; `load_skill_meta(name)` returns the parsed dict. The `tools` field asserts against `flow.tools` to catch skill-registry mismatches at load time. The `description` is a routing key for future registries.

The skill body that follows is in standard markdown — Process, Error Handling, Tools, Few-shot examples — and joins the system prompt under a divider:

```
--- {Flow_name} Skill Instructions ---
```

## Prompt File Organization

Templates live under `backend/prompts/`, split by consumer:

| Path | Scope | Consumer |
|---|---|---|
| `general.py` | Universal persona, system-prompt assembly | All callers |
| `for_experts.py` | Intent & flow classification | NLU detection |
| `for_nlu.py` | Slot-filling templates | NLU slot phase |
| `for_pex.py` | Policy execution helpers | PEX policies |
| `for_contemplate.py` | Re-routing prompts | NLU contemplate |
| `nlu/<intent>_slots.py` | Per-intent slot-filling prompt blocks | NLU slot phase |
| `pex/sys_prompts.py` | Per-intent Background blocks | Skill system prompt |
| `pex/skills/<flow>.md` | Per-flow skill body | `flow_reply` / `flow_execute` |
| `pex/starters/<flow>.py` | Per-flow user-message builder | `flow_reply` / `flow_execute` |

## Backoff & Retry

- All model invocations use exponential backoff on rate limits, timeouts, and server errors.
- Retry policy configured via resilience settings in domain config (max attempts, backoff base/max, retriable error types).
- The engineer owns all retry logic — callers do not implement their own backoff.

## Guardrails & Output Parsing

`apply_guardrails(text, format=...)` parses LLM output into structured form, routing to `_parse_json` / `_parse_sql` / `_parse_markdown`. Failure-closed: malformed output raises rather than returning a degraded default, so the policy can route the caller through a `parse_failure` violation.

- Strip markdown fences and disallowed imports (code formats)
- Validate structured output against expected JSON shape
- Return parsed dict / cleaned string for the caller to consume

`extract_tool_result(tool_log, tool_name)` and `tool_succeeded(tool_log, tool_name)` are the canonical readers of the agentic-loop trajectory. Policies should not walk `tool_log` directly.

## Token Budget Logging

- Track token usage across prompt sections (system, history, scratchpad, tool defs, response) for developer diagnostics.
- Logs include cache-hit / cache-miss counts so cache configuration can be tuned over time.
- Does not affect agent logic — purely informational.
