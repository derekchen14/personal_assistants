# Best Practices — Skills, Policies, Agent Loops (2026)

## Sources surveyed

### Tier 1 — Anthropic / OpenAI primary docs (2026)

- [Skill authoring best practices — Claude API Docs](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) — skill structure, degrees-of-freedom, progressive disclosure.
- [Building agents with the Claude Agent SDK](https://claude.com/blog/building-agents-with-the-claude-agent-sdk) — "gather → act → verify → repeat" loop.
- [Agent Skills overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview) — skill vs system-prompt boundary, metadata preloading.
- [Subagents in the SDK](https://platform.claude.com/docs/en/agent-sdk/subagents) — isolated context windows, tool scoping.
- [How and when to use subagents](https://claude.com/blog/subagents-in-claude-code) — when delegation wins.
- [Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) — workspace isolation, 1-hour TTL.
- [Extended thinking](https://platform.claude.com/docs/en/build-with-claude/extended-thinking) — adaptive thinking, `budget_tokens` deprecated on 4.6+.
- [OpenAI — Migrate to Responses API](https://developers.openai.com/api/docs/guides/migrate-to-responses) — stateful agentic loop via `previous_response_id`.
- [OpenAI — Structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs) — JSON-schema constrained decoding.
- [OpenAI — Reasoning models](https://developers.openai.com/api/docs/guides/reasoning) — reasoning tokens persist across tool turns.

### Tier 2 — 2026 papers & in-depth industry writing

- [Ask or Assume? Uncertainty-Aware Clarification — arXiv 2603.26233](https://arxiv.org/html/2603.26233) — EVPI cost/value for asking.
- [MAC — arXiv 2512.13154](https://arxiv.org/abs/2512.13154) — one-clarification-per-turn, supervisor vs. expert routing.
- [AMBIG-SWE — ICLR 2026](https://arxiv.org/pdf/2502.13069) — asking beats committing on under-specified tasks.
- [Long-Horizon Plan Execution — arXiv 2604.12126](https://arxiv.org/html/2604.12126) — entropy-guided branching on large tool spaces.
- [The Long-Horizon Task Mirage — arXiv 2604.11978](https://arxiv.org/html/2604.11978) — where long-horizon agents break.
- [Grounding Agent Memory in Contextual Intent — arXiv 2601.10702](https://arxiv.org/abs/2601.10702) — intent-indexed memory beats similarity.
- [Active Context Compression — arXiv 2601.07190](https://arxiv.org/pdf/2601.07190) — agent-controlled forgetting.
- [State of AI Agent Memory 2026 — mem0.ai](https://mem0.ai/blog/state-of-ai-agent-memory-2026) — MemoryArena: passive recall ≠ active use.
- [State of Context Engineering 2026 — SwirlAI](https://www.newsletter.swirlai.com/p/state-of-context-engineering-in-2026) — multi-step pipelines as the median.
- [Error Recovery and Graceful Degradation — notes.muthu.co](https://notes.muthu.co/2026/02/error-recovery-and-graceful-degradation-in-ai-agents/) — five-level recovery taxonomy.
- [When Agents Fail — Mindra](https://mindra.co/blog/fault-tolerant-ai-agents-failure-handling-retry-fallback-patterns) — per-tool circuit breakers + fallback chains.
- [Your ReAct Agent Is Wasting 90% of Its Retries — TDS](https://towardsdatascience.com/your-react-agent-is-wasting-90-of-its-retries-heres-how-to-stop-it/) — classify errors before retry.
- [Why Multi-Agent Systems Fail — Augment Code](https://www.augmentcode.com/guides/why-multi-agent-llm-systems-fail-and-how-to-fix-them) — MAST taxonomy.
- [Deterministic Core, Agentic Shell — davemo.com](https://blog.davemo.com/posts/2026-02-14-deterministic-core-agentic-shell.html) — the canonical 2026 determinism pattern.
- [Deterministic vs. LLM Evaluators — DEV](https://dev.to/anshd_12/deterministic-vs-llm-evaluators-a-2026-technical-trade-off-study-11h) — discovery deterministic, interpretation LLM.
- [Defeating Nondeterminism — Thinking Machines Lab](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/) — 15% accuracy swing at temp=0.
- [Automatic Context Compression — The AI Forum](https://medium.com/the-ai-forum/automatic-context-compression-in-llm-agents-why-agents-need-to-forget-and-how-to-help-them-do-it-43bff14c341d) — sliding window + summarisation hybrids.
- [Agentic Workflow Architectures — StackAI](https://www.stackai.com/blog/the-2026-guide-to-agentic-workflow-architectures) — flow engineering ≠ prompt engineering.
- [Agentic Design Patterns — SitePoint](https://www.sitepoint.com/the-definitive-guide-to-agentic-design-patterns-in-2026/) — stage-gated state machines.
- [DSPy](https://dspy.ai/) — declarative signatures + compiled prompts.
- [Agent Harness Engineering — QubitTool](https://qubittool.com/blog/agent-harness-evaluation-guide) — log every prompt/response/tool/result.

### Tier 3 — baselines for comparison

- [AutoGen vs LangGraph vs CrewAI 2026 — DEV](https://dev.to/synsun/autogen-vs-langgraph-vs-crewai-which-agent-framework-actually-holds-up-in-2026-3fl8) — LangGraph = StateGraph, CrewAI = roles, AutoGen = async actors.
- [CrewAI vs LangGraph vs AutoGen vs OpenAgents — Feb 2026](https://openagents.org/blog/posts/2026-02-23-open-source-ai-agent-frameworks-compared) — framework snapshot.

---

## 1. Skill-prompt structure

**Principle.** In 2026 the three layers are distinct: (a) **system prompt** = persona + universal rules; (b) **skill file** = one focused capability with trigger, inputs, workflow, output shape; (c) **runtime context** = resolved, grounded data for *this* call. Skills should be concise, testable, under ~500 lines; `description` is preloaded at startup and doubles as routing key ([Anthropic](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)). Match **degrees of freedom** to task fragility: low (explicit script) for destructive ops, medium (pseudocode) for templated, high (text guidance) for open-ended reasoning.

**Evidence.** Anthropic insists on direct commands ("Always run tests" not "You might consider"), consistent terminology, concrete input/output examples rather than abstract descriptions ([Anthropic](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)). DSPy's signature-first approach echoes this: typed signature + compiled prompts ([DSPy](https://dspy.ai/)).

**Hugo today.** Per `inventory/SUMMARY.md § Theme 2` and per-flow B-sections (`inventory/create.md § Skill contract`, `inventory/audit.md § Skill contract`), every skill has a resolved-entities block in its system envelope plus a `## Behavior` / `## Slots` / `## Output` / `## Few-shot` structure. Post-Theme-2, every declared slot has at least one exemplar (`policy_spec.md § Theme execution status` T2).

**Alignment.** Hugo's four-section template maps cleanly to Anthropic's recommendation. Gap: Hugo skills lack YAML frontmatter (`name`/`description`); because skills load by `flow.name()` rather than LLM-side discovery this is acceptable, but it means Hugo can't reuse Anthropic's skill-registry ecosystem directly. Degrees-of-freedom match is strong: `create` and `inspect` are low-freedom deterministic paths (per `inventory/create.md § Persistence calls`, `policy_spec.md § Theme execution status` T3 row); `rework`/`polish` remain high-freedom because prose revision genuinely needs LLM judgment.

## 2. Tool-call loop shape

**Principle.** 2026 loops are **"gather → act → verify → repeat"** with a forcing function that terminates when the model returns no `tool_use` block ([Anthropic — Building agents with the Claude Agent SDK](https://claude.com/blog/building-agents-with-the-claude-agent-sdk)). OpenAI's Responses API makes the same loop stateful by design, passing `previous_response_id` so reasoning tokens persist across turns ([OpenAI — Migrate to Responses API](https://developers.openai.com/api/docs/guides/migrate-to-responses)). Two-level decision: *open-ended loop* (model decides how many tools to call) when the task is discovery-shaped; *forced single tool-call* when the task is deterministic and the policy already knows what to call.

**Evidence.** Anthropic's SDK guide treats tools as "primary building blocks of execution" and recommends visible, prominent tool placement ([Anthropic — Agent SDK](https://claude.com/blog/building-agents-with-the-claude-agent-sdk)). The 2026 consensus is that sub-agents exist for **context isolation** and **parallelization** — they are the right call when the parent context would otherwise be polluted by verbose intermediate tool output ([Anthropic — Subagents in the SDK](https://platform.claude.com/docs/en/agent-sdk/subagents), [Anthropic — How and when to use subagents](https://claude.com/blog/subagents-in-claude-code)).

**Hugo today.** `backend/modules/policies/base.py::BasePolicy.llm_execute` (lines 18–41) is Hugo's open-ended loop wrapper, which calls `PromptEngineer.tool_call` (`backend/components/prompt_engineer.py` lines 188–234) — a 10-iteration cap with explicit accumulation of `tool_log`. For deterministic flows, the policy bypasses the loop entirely and calls `tools(name, params)` directly: `create` is the exemplar (`inventory/create.md § Persistence calls`), with `inspect` following after Theme 3 (`policy_spec.md § Theme execution status`, T3 row).

**Alignment.** Loop shape matches 2026 practice. Two nuances: (a) Hugo does not treat each policy as a "sub-agent with isolated context window" — the skill runs inside the main conversation envelope (per `prompt_engineer.py::tool_call` lines 197–199, skill system prompt prepended, full history appended via `build_skill_messages`). Fine for Hugo's ~14-step flows; would bleed context on longer horizons. (b) `exclude_tools` (`base.py::llm_execute` line 37) is Hugo's version of the SDK's `allowedTools` / `permissionMode: dontAsk` pattern — strong match, used correctly for outline propose-mode tool-stripping per `policy_spec.md § Theme execution status` T4 row.

**Dispatch contract (Phase 2).** Two execution paths, written directly into each per-flow policy method — no shared helper, no flow-class flag:

- **Deterministic path** — the policy builds `params` from filled slots, calls `tools(tool_name, params)` directly, flips `flow.status = 'Completed'`, and returns a `DisplayFrame`. On tool failure returns `DisplayFrame(origin='error', metadata={'tool_error': ..., 'reason': ...}, code=result['_message'])` per AD-6. The corresponding skill file is deleted — `llm_execute` would narrate what the caller already knows. Reference implementations: `create_policy` (draft.py), `inspect_policy` / `find_policy` (research.py), `explain_policy` / `undo_policy` (converse.py).
- **Agentic path** — the policy calls `BasePolicy.llm_execute(...)`. The sub-agent picks the tool trajectory from `flow.tools`. Used for outline, refine, compose, rework, polish, simplify, add, audit, release, etc.

Heuristic for picking the path: deterministic when `len(flow.tools) == 1` AND the tool's args are fully derivable from `flow.slots` + `state.active_post` without LLM reasoning. Agentic when `len(flow.tools) >= 2` OR any tool arg is prose/content the LLM must compose. A flow's deterministic nature is *implied* by what its policy does — it is not a declared attribute.

## 3. Error recovery

**Principle.** 2026 converges on a five-level ladder: **retry → rephrase → reroute → replan → escalate** ([notes.muthu.co](https://notes.muthu.co/2026/02/error-recovery-and-graceful-degradation-in-ai-agents/)). Rule #1: **classify before retrying** — transient (timeout), semantic (schema violation), and contract (user intent) are distinct; blind retry on semantic errors wastes 90% of attempts ([TDS](https://towardsdatascience.com/your-react-agent-is-wasting-90-of-its-retries-heres-how-to-stop-it/)). Per-tool circuit breakers are standard ([Mindra](https://mindra.co/blog/fault-tolerant-ai-agents-failure-handling-retry-fallback-patterns)).

**Evidence.** The MAST taxonomy: 41.8% spec/design, 36.9% inter-agent misalignment, 21.3% verification ([Augment Code](https://www.augmentcode.com/guides/why-multi-agent-llm-systems-fail-and-how-to-fix-them)). Anthropic's guidance: verification-as-feedback via rules > visual > LLM-as-judge, in decreasing reliability ([Agent SDK](https://claude.com/blog/building-agents-with-the-claude-agent-sdk)).

**Hugo today.** AD-6 locks three distinct channels: (1) **tool-call failure** → `DisplayFrame(origin='error', metadata={'tool_error': ...}, code=<raw>)`; (2) **contract violation** → `engineer.apply_guardrails(format='json')` fails-closed to an error frame; (3) **ambiguous user intent** → `self.ambiguity.declare(level, metadata=...)`. `RecoveryAction` (`pex.py` lines 27–31) has only `RETRY` and `ESCALATE` live; `GATHER_CONTEXT` / `REROUTE` are `# future` stubs.

**Alignment / proposed direction on `RecoveryAction`.** Hugo's three-channel rule matches the 2026 "classify before retry" principle tightly. But `RecoveryAction` as coded is incoherent with AD-6: it was designed for a legacy retry-then-escalate model AD-6 replaced. **Recommendation: shrink the enum.** The real recovery axis is what PEX does *after* `_validate_frame` rejects a frame — `RETRY` (re-run once with repair scratchpad) and `ESCALATE` (surface via partial-ambiguity). Replace `GATHER_CONTEXT` and `REROUTE` with comments pointing to AD-6: routing belongs in NLU `contemplate()`; context enrichment belongs in the Internal-flow chain (per `CLAUDE.md § Module Contracts`). Shrink-and-document honors the lock without re-architecting.

## 4. Grounding vs. reasoning

**Principle.** 2026 winners on long-horizon benchmarks use **pre-computed grounded context** instead of tool-based discovery — resolve deterministically before the LLM runs ([arXiv 2604.12126](https://arxiv.org/html/2604.12126), [arXiv 2604.11978](https://arxiv.org/html/2604.11978)). Intent-indexed memory beats similarity-indexed memory because grounding narrows the search space before reasoning ([arXiv 2601.10702](https://arxiv.org/abs/2601.10702)).

**Evidence.** MemoryArena: models at 95%+ passive recall drop to 40–60% on active, decision-relevant retrieval ([mem0.ai](https://mem0.ai/blog/state-of-ai-agent-memory-2026)) — unresolved context is costly. "Deterministic core, agentic shell" formalizes the split: discovery deterministic, interpretation LLM ([davemo.com](https://blog.davemo.com/posts/2026-02-14-deterministic-core-agentic-shell.html), [DEV](https://dev.to/anshd_12/deterministic-vs-llm-evaluators-a-2026-technical-trade-off-study-11h)).

**Hugo today.** Per `policy_spec.md § Motivation`, NLU slot-fills before any policy runs; `BasePolicy._build_resolved_context` (`base.py` lines 116–139) resolves `post_id`/`sec_id` and fetches metadata *before* `llm_execute`, passing the resolved dict into the skill system prompt via `tool_call(..., resolved=...)`. Under Theme 1 skills are forbidden from re-grounding: `create`/`find` skills deleted, Theme 1 rule ("resolved context is source of truth; skills do not re-ground") enforced by skill-file audit.

**Alignment.** Hugo's strongest alignment with 2026 practice. NLU-as-pre-grounder is exactly what "deterministic core, agentic shell" and the long-horizon-planning literature describe, applied one layer higher (flow/slot resolution) than most 2026 frameworks. Remaining gap: **grounded findings**. The scratchpad (AD-1) carries findings across turns, but resolved-entity enrichment only happens for the current turn's active flow — a flow running under `stackon` inherits scratchpad but re-runs `_build_resolved_context` on its own entity. Correct (different flow = different grounding surface) but it implies cross-flow chains should pipe IDs through scratchpad rather than trusting NLU to re-resolve.

## 5. Ambiguity / clarification protocols

**Principle.** 2026 treats clarification as a **cost/value decision**: ask only when expected value of perfect information exceeds interruption cost ([arXiv 2603.26233](https://arxiv.org/html/2603.26233)). MAC recommends **one clarification per turn** and splits responsibility between supervisor (global) and expert (domain) ([arXiv 2512.13154](https://arxiv.org/abs/2512.13154)). AMBIG-SWE (ICLR 2026) confirms interactive clarification beats silent-assumption on under-specified tasks ([arXiv 2502.13069](https://arxiv.org/pdf/2502.13069)).

**Evidence.** Shared failure mode across all three papers: agents either ask too many shallow questions (friction) or commit silently on under-specified requests (wrong output). Resolution is a **typed ambiguity hierarchy** — general / partial / specific / confirmation — each level with distinct generation.

**Hugo today.** `backend/components/ambiguity_handler.py` implements the 4-level scheme — `AmbiguityLevel.GENERAL | PARTIAL | SPECIFIC | CONFIRMATION` — with per-level ask methods and `should_escalate()` on cumulative count vs. `ambiguity_escalation_turns`. Policies call `declare()` and return empty; RES consumes `ambiguity.present()` and renders. Per AD-6 this is the **only** channel producing clarification questions.

**Alignment.** Hugo's 4 levels map one-for-one to the 2026 typed hierarchy (general = missing intent, partial = missing entity, specific = missing slot value, confirmation = candidate awaiting sign-off). One-clarification-per-turn is implicit: policies return immediately after `declare()`. **Minor gap:** `should_escalate()` exists but isn't consumed — a 2026-aligned approach would route persistent ambiguity into the `ESCALATE` path of `RecoveryAction` (see § 3). **Stronger gap:** no EVPI-style cost/value gate — every missing slot declares ambiguity. For optional slots with sensible defaults, 2026 guidance says *commit with the default and only clarify if downstream fails* (e.g. `reference_count=5` in audit per `inventory/audit.md § Guard clauses`). Worth exploring in Part 3, needs user sign-off because it changes user-facing behavior.

## 6. Stage machines inside policies

**Principle.** 2026 agentic workflows are **stage-gated state machines** with deterministic gates at each transition ([SitePoint](https://www.sitepoint.com/the-definitive-guide-to-agentic-design-patterns-in-2026/), [StackAI](https://www.stackai.com/blog/the-2026-guide-to-agentic-workflow-architectures)). LangGraph's StateGraph is the framework embodiment: named stages, explicit transitions, deterministic gates ([DEV](https://dev.to/synsun/autogen-vs-langgraph-vs-crewai-which-agent-framework-actually-holds-up-in-2026-3fl8)). Strong caution: stages must reflect **genuine control-flow divergence**, not cosmetic labels — conflating them with modes/flags produces the 36.9% "inter-agent misalignment" failures in MAST.

**Evidence.** 2026 hybrid: state machines inside policies for multi-stage work, single-call for deterministic one-shots. LangGraph's checkpointing/resume works because each stage is an explicit node — a defining advantage over CrewAI's sequential roles and AutoGen's async messages ([DEV 2026](https://dev.to/synsun/autogen-vs-langgraph-vs-crewai-which-agent-framework-actually-holds-up-in-2026-3fl8), [OpenAgents Feb 2026](https://openagents.org/blog/posts/2026-02-23-open-source-ai-agent-frameworks-compared)).

**Hugo today.** `flow.stage` is the in-flow control mechanism; historically used values have been `propose`, `direct`, `error`, `informed`. Per AD-2 (`policy_spec.md § Architectural decisions`), `informed` is **removed** for polish — the skill is always informed via scratchpad, and there is no branch. Per AD-5 (terminology discipline), the correct word is **stages**, not modes. `outline` retains `propose` vs. `direct` as a genuine control-flow split (different tool set, different output shape) — per `inventory/outline.md` and AD-3 the recursion is documented as safe. `create` has no stages (`inventory/create.md § Staging`); `audit` runs single-pass with a conditional completion on threshold (`inventory/audit.md § Staging`).

**Alignment.** Post-AD-2, Hugo is tighter than the 2026 baseline: stages only where divergence is real (outline propose/direct), not as a flag for "did we get findings yet." Right call — 2026 literature warns against stage-as-flag. Small extension: document allowed stage set per flow class (e.g. in `backend/components/flow_stack/flows.py` docstrings) so reviewers catch unintended stage invention during Part 5b batches.

## 7. Token budgeting and streaming

**Principle.** 2026 budget discipline: (a) **prompt caching** covers most savings; (b) **adaptive thinking** replaces explicit `budget_tokens` on Claude 4.6+; (c) **context compression** (sliding window + summarization) for long loops. Output limits: Sonnet 4.6/Haiku 4.5 = 64k, Opus 4.6/4.7 = 128k.

**Evidence.** Anthropic's Feb 2026 workspace-level caching: writes 1.25× input (5-min) or 2× (1-hr); reads 0.1× input — default-on choice ([Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)). `budget_tokens` is deprecated on 4.6+; new code uses adaptive thinking ([Extended thinking](https://platform.claude.com/docs/en/build-with-claude/extended-thinking)). Compression consensus: 50–80% token reduction on long sessions ([AI Forum](https://medium.com/the-ai-forum/automatic-context-compression-in-llm-agents-why-agents-need-to-forget-and-how-to-help-them-do-it-43bff14c341d)).

**Hugo today.** `PromptEngineer.tool_call` defaults `max_tokens=4096` (line 191 of `prompt_engineer.py`); `skill_call` uses `max_tokens=1024` (line 175). The Claude path (`_call_claude`) sets `tools=`, `system=`, `messages=` via a single `client.messages.create`, with no `cache_control` markers on the system prompt or tool defs. Conversation history compilation (`ContextCoordinator.compile_history`) does not compress; it simply returns recent turns. Streaming exists in `engineer.stream` but is not used by any policy — only for naturalization in RES per `backend/modules/res.py`.

**Alignment / gaps.** Hugo's biggest gap vs. 2026 practice.

1. **No prompt caching on skill system prompt or tool defs** — both rebuilt fresh every turn. Adding `cache_control={'type': 'ephemeral'}` markers on the tail of the system block and the tool-defs array would capture most of the 90% cost reduction cached inputs enable. Purely additive, no AD conflict.
2. **`max_tokens=4096`** is conservative for 2026 Sonnet/Opus but per `inventory/<flow>.md § Frame shape` every skill output is a short JSON blob or a prose paragraph — 4096 is already over-provisioned. No bump needed.
3. **No extended thinking.** Hugo runs Sonnet for skills (`_MODEL_IDS` in `prompt_engineer.py`). Extended thinking would help the multi-tool audit loop (`find_posts` → `compare_style` → `editor_review`) but adds latency; defer until Part 4 evals show a reasoning-quality gap.

## 8. Determinism boundaries

**Principle.** Canonical 2026 pattern: **"deterministic core, agentic shell"** — everything that can be code should be; LLM sits at the interpretation layer ([davemo.com](https://blog.davemo.com/posts/2026-02-14-deterministic-core-agentic-shell.html)). "Deterministic tools for discovery, LLMs for interpretation" is now an engineering constraint, not a preference: probabilistic verification of probabilistic output is no verification ([DEV](https://dev.to/anshd_12/deterministic-vs-llm-evaluators-a-2026-technical-trade-off-study-11h)).

**Evidence.** Even at `temperature=0`, accuracy swings 15% across runs from batch-size non-determinism ([Thinking Machines Lab](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/)) — any "deterministic" layer that is really an LLM call is untrustworthy. Push the LLM boundary outward.

**Hugo today.** Per `policy_spec.md § Theme execution status`, post-Theme-3 `inspect` became fully deterministic (skill deleted, policy calls `inspect_post` directly), `create` was already deterministic (`inventory/create.md § Persistence calls`), `find` was always deterministic. The remaining LLM-driven flows (audit, rework, simplify, polish, compose, refine, add, release) all have genuine judgment-heavy steps. Compare-style in audit is an LLM call *inside the deterministic audit policy* — correctly scoped.

**Alignment.** Post-Theme-3 Hugo matches "deterministic core, agentic shell" closely. Subtle gap: `pex.py::_validate_frame` (lines 172–197) uses `_llm_quality_check` (lines 228–245) — LLM verifying LLM. Weak signal by the 2026 principle. It's gated by `recovery.llm_validate_flows` and short-circuits on failure so it doesn't harm, but shouldn't be treated as a real gate. Rules-based checks (frame-shape validation, required block types, `tool_succeeded`) carry the actual safety.

## 9. Cross-turn state / findings channel

**Principle.** 2026 agents maintain a **structured scratchpad** as working memory, distinct from (and feeding) episodic memory ([mem0.ai](https://mem0.ai/blog/state-of-ai-agent-memory-2026)). The scratchpad is written every turn and filtered by **contextual intent**, not lexical similarity ([arXiv 2601.10702](https://arxiv.org/abs/2601.10702)). Agent-controlled compression emerging: give the agent a "compress" tool ([arXiv 2601.07190](https://arxiv.org/pdf/2601.07190)).

**Evidence.** MemoryArena: 95%+ passive recall drops to 40–60% on active, decision-relevant use ([mem0.ai](https://mem0.ai/blog/state-of-ai-agent-memory-2026)). Implication: structured keys with `version`/`turn_number` metadata beat freeform text.

**Hugo today.** AD-1 (`policy_spec.md § Architectural decisions`) codifies the convention: scratchpad key = `flow_name`; value is a dict with required fields `version`, `turn_number`, `used_count`, plus flow-specific payload. Per `policy_spec.md § Theme execution status`, T5 is executed: producers (`inspect`, `find`, `audit`) write scratchpad using `context.turn_id`, and the polish skill emits `used:[...]` which the policy reads to increment `used_count`. No new attribute on `DialogueState` or `DisplayFrame`.

**Alignment.** Hugo's convention matches the 2026 structured-scratchpad pattern and is **stronger than most framework defaults** in one respect: `used_count` gives an explicit active-use signal — the decision-relevant memory metric MemoryArena highlights. `version` handles re-audits. Two forward-looking notes (not fixes now): (a) no intent-filter — polish walks the whole scratchpad and filters by `key=flow_name`, fine at 64 snippets but wouldn't scale; (b) no compression path — a long audit finding stays verbatim. Neither urgent.

---

## Gap analysis — Hugo vs. 2026 practice

| Topic | Hugo state | Strength or gap | Recommended direction |
|---|---|---|---|
| 1. Skill structure | 4-section template, every slot exemplified post-Theme-2 | Strong alignment (per `inventory/SUMMARY.md § Theme 2`, `policy_spec.md § Theme execution status`) | Keep. Consider adding YAML frontmatter for future skill-registry compatibility. |
| 2. Tool-call loop | `BasePolicy.llm_execute` → `tool_call` 10-iteration cap + `exclude_tools` | Strong alignment; matches Anthropic SDK "gather → act → verify" (per `prompt_engineer.py:188`) | Keep. No change. |
| 3. Error recovery | AD-6 three-channel split; `RecoveryAction` enum with 2 live values | Alignment on classification; dead code in `RecoveryAction` | Shrink `RecoveryAction` to `{RETRY, ESCALATE}`, document the omitted levels as out-of-scope per AD-6. |
| 4. Grounding vs reasoning | NLU slot-fills before policy; `_build_resolved_context` pre-fetches | Hugo's signature strength; matches "deterministic core, agentic shell" | Keep. Document as exploitable advantage in Part 3 fixes. |
| 5. Ambiguity protocols | 4-level `AmbiguityHandler`; one-per-turn by return convention | Strong alignment on levels; no EVPI-style cost/value gate | Consider default-with-commit pattern for optional slots with obvious defaults (per § 5). Part 3 proposal, not a lock. |
| 6. Stages | Post-AD-2, stages only where divergence is real | Tighter than 2026 baseline | Document allowed stage set per flow class in Part 3. |
| 7. Token budgeting | `max_tokens=4096` default; no prompt caching; no extended thinking | **Largest gap** — no `cache_control` markers on system/tools | Add `cache_control={'type':'ephemeral'}` to system prompt + tool defs in `_call_claude`. Purely additive; cites § 7. |
| 8. Determinism boundaries | Post-Theme-3 alignment very close to "deterministic core, agentic shell" | Strong | Audit `_llm_quality_check` usage — don't treat LLM-as-judge as a gate. |
| 9. Cross-turn findings | AD-1 scratchpad convention with `version`/`turn_number`/`used_count` | Strong; `used_count` beats most 2026 defaults | Keep. No change. |

**Top 3 gaps worth flagging for Part 3:**

1. **No prompt caching on skill system prompt + tool defs** (§ 7) — cheap win, purely additive.
2. **`RecoveryAction` enum is incoherent with AD-6** (§ 3) — shrink + document the AD-6 pointers.
3. **No EVPI-style default-with-commit for optional slots** (§ 5) — harder call; propose in Part 3 but needs user sign-off because it changes user-facing behavior.

---

## Proposed ideal PEX architecture

The architecture below is a **consolidation** of what already landed (post Themes 1–7) plus the small, AD-respecting extensions that emerge from the 2026 research above. No decision here contradicts AD-1 through AD-6.

### Policy entrypoint contract

Every policy method receives `(state, context, tools)` from `PEX.execute` (`pex.py` line 118) and must, in order:

1. **Guard entity slot.** If `flow.entity_slot` is SourceSlot-derived, confirm `.filled`; if missing, `declare('partial', metadata={'missing_entity': ...})` and return an error frame. Topic-entity flows declare `'specific'`.
2. **Guard required slots.** For each `priority='required'` non-entity slot, check `.filled`; declare `'specific'` and return. Optional slots MAY take a sensible default (per § 5 EVPI guidance).
3. **Resolve context.** `self._build_resolved_context(flow, state, tools)` — deterministic-core step; never delegate to the skill.
4. **Dispatch** — either direct tool call (`create`, `inspect`, `find` per `policy_spec.md § Theme execution status`) or skill loop via `self.llm_execute(...)` with success check `self.engineer.tool_succeeded(tool_log, name)` (Theme 7).
5. **Persist** if owned by policy (ownership per `inventory/SUMMARY.md § Theme 1`).
6. **Build frame** — origin = flow name; blocks per `inventory/<flow>.md § Frame shape`; thoughts only when LLM wording *is* the response.
7. **Complete** — `flow.status = 'Completed'` on success; PEX post-hooks (`_verify`, `_verify_active_post`) handle invariants.

### Error-recovery flowchart (AD-6 codified)

```
                          policy.execute()
                                 │
                                 ▼
                ┌────────────────────────────────┐
                │ Which kind of "not smooth"?    │
                └────────────────────────────────┘
                   │            │              │
       tool failure        contract         ambiguous
       (network, API,     violation         user intent
       permission)      (bad JSON,          (missing /
           │            schema miss)        wrong slot)
           ▼                 │                  │
  DisplayFrame(               │                  │
   origin='error',            ▼                  ▼
   metadata={          apply_guardrails    self.ambiguity.
     'tool_error':    (format='json')       declare(level,
      <name>,             │                    metadata)
     'reason': ...},      │                  return empty
   code=<raw>)            ▼                    DisplayFrame
   return           still mismatched?
                         │
                    YES  │  NO
                         ▼   ▼
                    same error      continue flow
                    frame as LHS
```

PEX's `_validate_frame` + `recover` ladder (`pex.py` lines 172–319) is the outer safety net, stays thin:

- **Tier 1 (RETRY)** — re-run policy once with a `scratchpad['repair']` note. Live.
- **Tier 4 (ESCALATE)** — declare `partial` ambiguity with `failure_reason`. Live.
- **Tiers 2/3** — AD-6-deprecated. `reroute` belongs in NLU `contemplate()`; `gather_context` belongs in the Internal-flow chain (`recap`/`recall`/`retrieve`) per `CLAUDE.md § Module Contracts`.

### AmbiguityHandler integration (which level when)

| When the policy discovers… | Declare | Metadata | Frame shape |
|---|---|---|---|
| No entity slot filled, no candidate in scratchpad | `general` | none | empty; RES renders a broad "what are we doing?" question |
| Entity slot type is source/target/removal/channel but `post_id` unresolvable | `partial` | `{missing_entity: 'post'}` | empty; RES renders "which post?" |
| Required value slot missing (e.g. `title`, `type`, `proposals` selection) | `specific` | `{missing_slot: <name>}` | empty |
| Candidate exists needing sign-off (duplicate title in create, audit threshold exceeded) | `confirmation` | `{candidate: <value>}` or `{reason: <code>}` | optional confirmation block with `confirm_label` / `cancel_label` |

One-clarification-per-turn is enforced by returning immediately after `declare()`. Persistent ambiguity (≥ `ambiguity_escalation_turns` in a row) is currently counted but not acted on — a Part-3 candidate: consume `should_escalate()` in PEX's recover tier 4 to switch from `partial` to `general` ("let's start over").

### `RecoveryAction` — recommended contract

Keep the enum; shrink to the two live values; document AD-6 pointers:

```python
class RecoveryAction(Enum):
    RETRY = 'retry'       # Tier 1: re-run policy with repair scratchpad
    ESCALATE = 'escalate' # Tier 4: declare partial ambiguity to user
    # NOTE: 'gather_context' and 'reroute' were considered and rejected.
    # Per AD-6, routing-level recovery belongs to NLU.contemplate();
    # context enrichment belongs to the Internal flow chain. Do not
    # re-introduce these values without user approval.
```

### Shared helpers (current + 2026-informed proposals)

Post-Theme-7 only one helper landed: `PromptEngineer.tool_succeeded(log, name) → (bool, dict)` — migrated to 4 call-sites in `draft.py` + `revise.py`. User explicitly rejected `guard_slot`, `complete_with_card`, `stack_on` — principled rejection (slot treatments vary, completion frames will diverge, `stackon` is already on `flow_stack`). Do not re-litigate.

**2026-informed additions (proposals, not locked):**

1. **`BasePolicy.error_frame(origin, tool_error=None, contract_violation=None, reason='', raw='')`** — thin constructor for the AD-6 error-origin frame. Every policy currently inlines `DisplayFrame(origin='error', metadata={...}, code=<raw>)`; a helper codifies AD-6 and prevents metadata-key drift (`tool_error` vs. `tool_failure` vs. `error_tool`). Will have ≥5 call-sites post-Part-3.
2. **Prompt-cache markers in `PromptEngineer._call_claude`** (§ 7) — add `cache_control={'type': 'ephemeral'}` on the system-block tail and `tools=` array. Additive, no AD conflict.

Flag both for user sign-off in Part 3.

---

## Key citations with Part 1 back-references

- **Skill structure** — Hugo 4-section template (`inventory/SUMMARY.md § Theme 2`, `inventory/create.md § Skill contract`) ⇄ [Anthropic skill best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices).
- **Tool-call loop** — `base.py::llm_execute` → `prompt_engineer.py::tool_call` (`inventory/audit.md § Tool plan`, `inventory/create.md § Persistence calls`) ⇄ [Anthropic — Building agents with the Claude Agent SDK](https://claude.com/blog/building-agents-with-the-claude-agent-sdk).
- **Error recovery** — AD-6 (`policy_spec.md § Architectural decisions`), `pex.py::RecoveryAction`, `inventory/SUMMARY.md § Theme 4` ⇄ [notes.muthu.co — Error recovery](https://notes.muthu.co/2026/02/error-recovery-and-graceful-degradation-in-ai-agents/), [TDS — ReAct retries](https://towardsdatascience.com/your-react-agent-is-wasting-90-of-its-retries-heres-how-to-stop-it/).
- **Grounding** — `base.py::_build_resolved_context`, `policy_spec.md § Motivation`, Theme 1 rule in `inventory/SUMMARY.md` ⇄ [davemo.com — Deterministic Core, Agentic Shell](https://blog.davemo.com/posts/2026-02-14-deterministic-core-agentic-shell.html), [arXiv 2601.10702](https://arxiv.org/abs/2601.10702).
- **Ambiguity** — `ambiguity_handler.py`, `inventory/audit.md § Ambiguity patterns`, `inventory/create.md § Ambiguity patterns`, AD-6 ⇄ [arXiv 2603.26233 — Ask or Assume?](https://arxiv.org/html/2603.26233), [arXiv 2512.13154 — MAC](https://arxiv.org/abs/2512.13154).
- **Stages** — AD-2, AD-5, `inventory/outline.md § Staging`, `inventory/audit.md § Staging` ⇄ [SitePoint — Agentic Design Patterns 2026](https://www.sitepoint.com/the-definitive-guide-to-agentic-design-patterns-in-2026/), [DEV — AutoGen vs LangGraph vs CrewAI 2026](https://dev.to/synsun/autogen-vs-langgraph-vs-crewai-which-agent-framework-actually-holds-up-in-2026-3fl8).
- **Token budget** — `prompt_engineer.py::tool_call`, `_call_claude` ⇄ [Anthropic — Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching), [Anthropic — Extended thinking](https://platform.claude.com/docs/en/build-with-claude/extended-thinking).
- **Determinism** — `policy_spec.md § Theme execution status` T3 row, `inventory/inspect.md`, `inventory/create.md § Persistence calls`, `pex.py::_llm_quality_check` ⇄ [DEV — Deterministic vs. LLM Evaluators 2026](https://dev.to/anshd_12/deterministic-vs-llm-evaluators-a-2026-technical-trade-off-study-11h), [Thinking Machines Lab — Defeating Nondeterminism](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/).
- **Scratchpad** — AD-1, `policy_spec.md § Theme execution status` T5 row ⇄ [mem0.ai — State of AI Agent Memory 2026](https://mem0.ai/blog/state-of-ai-agent-memory-2026), [arXiv 2601.10702](https://arxiv.org/abs/2601.10702).

---

## Prompting Best Practices

  * Hybrid approach with XML-tagged headers and Markdown sub-sections
    - XML tags serve as the primary structure
    - Some Markdown parts sparingly nested in between
      -  Wrapping any user-supplied or retrieved content that the model must treat as data, not instructions. <user_input>, <document>, <search_results>
      -  Naming behavioral blocks you want the model to recognize as a unit and that you might refer to by name elsewhere in the prompt — e.g. <style_guide>...</style_guide> if your prompt later says "follow the style guide above."
      - Structuring multi-part examples where the parts have distinct roles (<input>, <expected_output>, <reasoning>).
  * Explain the why, not just the what
    - Provide the reasoning chain for your instructions
    - Avoid super rigid structures, these should be reserved for code
  * Negative examples are everywhere ('NEVER do X')
    - despite the guide preferring positive ones
    - General positive instructions ('be concise') are ambiguous. Specific negative instructions ('don't add docstrings to code you didn't change') are actionable
  * Repetition is a feature, not a bug
    - Say it three separate times if needed
    - "Repeating one more time the core loop here for emphasis:"
  * Conversational, first-person-ish register
    - Like a Slack message from a teammate, not strict documentation
    - Be firm and pushy when making a request, use ALL CAPS at least once


  Instruction Hierarchy: Precedence Order

  From highest to lowest priority:

  ┌──────────┬─────────────────────────────────────────────────┬───────────────────────────────────────────────────────────────────┐
  │ Priority │                    Mechanism                    │                          What goes here                           │
  ├──────────┼─────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────┤
  │ 1        │ System prompt (Anthropic's built-in)            │ Always wins conflicts. You can't override this in Claude Code.    │
  ├──────────┼─────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────┤
  │ 2        │ CLI flags / API system prompt                   │ Your PEX sub-agent calls — this is the system prompt you control. │
  ├──────────┼─────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────┤
  │ 3        │ User message                                    │ The assembled prompt your policy sends to the model.              │
  ├──────────┼─────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────┤
  │ 4        │ CLAUDE.md (subdirectory > project > user-level) │ Loaded into Claude Code sessions, not your runtime agents.        │
  ├──────────┼─────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────┤
  │ 5        │ SKILL.md                                        │ On-demand, loaded only when triggered. Claude Code only.          │
  ├──────────┼─────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────┤
  │ 6        │ Auto-memory                                     │ Complements, never overrides.                                     │
  └──────────┴─────────────────────────────────────────────────┴───────────────────────────────────────────────────────────────────┘

  Critical distinction: CLAUDE.md, AGENT.md, and SKILL.md are development-time mechanisms — they guide Claude Code (or Cursor/Copilot)
  while you build the assistants. They do not reach your runtime agents. Your PEX sub-agents only see what you explicitly pass in the
  API call's system and messages fields.

  ---
  CLAUDE.md vs AGENT.md vs SKILL.md

  ┌───────────┬──────────────────────────────┬─────────────────────────────────────────────────────────────────────────────────────┐
  │   File    │            Scope             │                                     When to use                                     │
  ├───────────┼──────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────┤
  │ CLAUDE.md │ Horizontal rules that apply  │ Naming conventions, forbidden patterns, repo structure, coding style. Your current  │
  │           │ everywhere                   │ CLAUDE.md is a good example.                                                        │
  ├───────────┼──────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────┤
  │ AGENT.md  │ Cross-tool equivalent of     │ Same purpose, but works with Cursor/Copilot/Windsurf too. Functionally identical —  │
  │           │ CLAUDE.md                    │ you can symlink one to the other.                                                   │
  ├───────────┼──────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────┤
  │ SKILL.md  │ Vertical workflows triggered │ Slash commands like /commit, /deploy. Loaded only when invoked.                     │
  │           │  on demand                   │                                                                                     │
  └───────────┴──────────────────────────────┴─────────────────────────────────────────────────────────────────────────────────────┘

  Key empirical finding (Vercel eval): passive always-on context (CLAUDE.md/AGENT.md) achieved 100% compliance vs skills at 79% —
  skills were never invoked in 56% of cases. Lesson: put critical rules in CLAUDE.md, not skills.

  Practical advice: Keep CLAUDE.md minimal. For each line, ask "would removing this cause Claude to make mistakes?" If not, cut it. Use
   linters/formatters for style enforcement instead of CLAUDE.md.

  ---
  What This Means for Your PEX Sub-Agents

  Your runtime agents (the LLM calls inside policies like converse.py, draft.py, etc.) don't see CLAUDE.md at all. You're assembling
  prompts yourself via PromptEngineer. Here's the layered pattern that works best:

  Layer 1: System Prompt (persona + guardrails)

  - Role/identity: "You are Hugo, a blog writing assistant..."
  - Hard constraints: output format, forbidden behaviors, entity definitions
  - Keep short, versioned, stable across turns
  - Use XML tags or markdown headers to delimit sections

  Layer 2: Skill/Flow Instructions (injected per-flow in user message)

  - The flow's objective: "Help the user outline a new blog post"
  - Available tools: what this policy can call
  - Output shape: what format to return
  - 2-3 flow-specific "must/never" rules
  - Loaded dynamically — only the active flow's instructions appear

  Layer 3: Per-Turn Context (conversation history + slots)

  - convo_history from context.compile_history()
  - Current slot values and entity state
  - Retrieved context (search/retrieve results)
  - Cleanly separated from instructions

  Concrete Recommendations for Your Architecture

  1. System prompt = constraints. User message = task. Put persona and guardrails in system prompt. Put the flow skill template +
  conversation history in the user message. Claude gives slightly more weight to user messages, so critical per-flow rules should go
  there.
  2. Repeat critical constraints in both layers. For rules that absolutely cannot be violated (e.g., "never fabricate sources"), put
  them in the system prompt AND reinforce in the skill template. Empirically this improves compliance with Claude models specifically.
  3. Tool descriptions are a prompting surface. Anthropic found that refining tool descriptions yielded "dramatic improvements" — more
  than prompt changes. Your tool_manifest_hugo.json schemas are effectively instructions. Invest in precise descriptions with examples.
  4. Add rationale to rules. Instead of "Never output more than 3 sections", write "Never output more than 3 sections — users reported
  feeling overwhelmed by longer outlines." The why increases compliance because the model can reason about edge cases.
  5. For cheaper model tiers (your confidence experiment), be more explicit. IFEval++ benchmarks show weaker models drop up to 61.8% on
   instruction-following under variation. When calling Haiku or Qwen-7B, make instructions more redundant and explicit than you would
  for Opus.
  6. Don't over-constrain. Anthropic warns against hardcoding complex brittle logic. The sweet spot is clear constraints + freedom to
  reason. Your policies should define what the sub-agent must accomplish and what it must not do, but let it reason about how.

  Mapping to Your Codebase

  ┌───────────────────────────────────────┬─────────────────────────────┬─────────────────────────────────────────────┐
  │            Your component             │           Maps to           │                  Contains                   │
  ├───────────────────────────────────────┼─────────────────────────────┼─────────────────────────────────────────────┤
  │ prompts/general.py                    │ Layer 1 (system prompt)     │ Persona, guardrails, entity defs            │
  ├───────────────────────────────────────┼─────────────────────────────┼─────────────────────────────────────────────┤
  │ prompts/skills/*.md                   │ Layer 2 (flow instructions) │ Per-flow objective, tools, output shape     │
  ├───────────────────────────────────────┼─────────────────────────────┼─────────────────────────────────────────────┤
  │ context_coordinator.compile_history() │ Layer 3 (per-turn)          │ Conversation history, retrieved context     │
  ├───────────────────────────────────────┼─────────────────────────────┼─────────────────────────────────────────────┤
  │ schemas/tool_manifest_hugo.json       │ Tool descriptions           │ Effectively instructions — treat as prompts │
  ├───────────────────────────────────────┼─────────────────────────────┼─────────────────────────────────────────────┤
  │ modules/policies/*.py                 │ Prompt assembly             │ Stitches layers 1-3 together per turn       │
  └───────────────────────────────────────┴─────────────────────────────┴─────────────────────────────────────────────┘

  The policy module is your context engineer — it decides what configuration of context is most likely to produce the right behavior
  for each sub-agent call. That's the 2026 framing from Anthropic: "context engineering > prompt engineering."

