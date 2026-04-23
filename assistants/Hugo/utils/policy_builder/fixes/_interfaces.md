# PEX Interface Changes — Fixes

**Status:** applied (see architectural decisions below)

API contract changes between PEX and its neighbors (`AmbiguityHandler`, `FlowStack`, `MemoryManager`, `DialogueState`, `RecoveryAction`) that emerged from the Theme 1-7 execution.

## Back-references to Part 1

- Inventory summary: `inventory/SUMMARY.md § Theme 4` (error-path gaps), `§ Theme 5` (cross-turn findings), `§ Theme 6` (stack-on), `§ Theme 7` (shared helpers)
- Ambiguity patterns observed in: `inventory/create.md`, `inventory/release.md`, `inventory/audit.md`, `inventory/refine.md`, `inventory/outline.md`, `inventory/inspect.md`, `inventory/find.md`, `inventory/compose.md`, `inventory/polish.md`
- Stack-on patterns observed in: `inventory/outline.md`, `inventory/compose.md`, `inventory/refine.md`
- Scratchpad consumption observed in: `inventory/polish.md`
- AmbiguityHandler spec: `_specs/components/ambiguity_handler.md` (4 levels)

## Six architectural decisions (all locked in `policy_spec.md`)

### AD-1 — Scratchpad as cross-turn findings channel

- **Key** = the producer's `flow_name` (`'inspect'`, `'find'`, `'audit'`, future `'browse'`, `'summarize'`, `'check'`, …). No `'flow:inspect'`, no `'findings:inspect'` prefix — just the bare flow name.
- **Value** = `dict`. Required fields: `version` (currently `'1'`), `turn_number` (set to `context.turn_id`), `used_count` (starts at 0, incremented by consumers).
- **Producers (landed):** `inspect_policy`, `find_policy`, `audit_policy`.
- **Producers (pending):** `browse_policy`, `summarize_policy`, `check_policy`, `compare_policy`, `diff_policy` all carry a `TODO(Theme 5 AD-1)` comment and will write on demand when a downstream consumer appears.
- **Consumers (landed):** `polish_policy` walks the scratchpad via `self.engineer.apply_guardrails(text, ...)['used']` and increments `used_count` for each key the skill reports it consumed.
- **Rejected:** no `DialogueState.findings` attribute, no `DisplayFrame.findings`. New attribute adds go through explicit user review.

### AD-2 — No "informed mode" on polish

- The skill reads conversation history + scratchpad unconditionally. No policy-level `flow.stage = 'informed'` branching. Every flow "always tries to be informed"; if the scratchpad is empty, the skill just polishes.
- The polish skill emits `{'used': [<keys>]}` so the policy can bump `used_count` — but presence of prior findings is not a precondition for the flow to run.

### AD-3 — Outline recursion is safe by construction

- `outline_policy` self-recurses only after draining `proposals → sections`. The recursive call takes the sections-filled branch (which does not self-recurse), so max depth = 1.
- **Invariant:** `OutlineFlow` may NOT `flow_stack.stackon('outline')` itself. Compose and refine (other flows) may stack on outline; outline may not stack on itself.
- Fix landed as a comment, not a rewrite; no iterative refactor, no depth guard, no extracted `_execute_direct_outline` helper.

### AD-4 — 4-level outline scheme (canonical constant)

- `OUTLINE_LEVELS` dict in `backend/components/flow_stack/flows.py` (+ Level 0 for the post title).
- Used by the `depth` slot on `OutlineFlow` and by `refine`, `compose`, `add` for markdown rendering.

### AD-5 — Terminology discipline

- NLU only: **classifies** an intent, **detects** a flow, **fills** a slot. Never "fires", "triggers", or "activates".
- Policies "call a tool" or "declare ambiguity"; skills "produce output"; flows "complete", "stack on", or "fallback".
- In-flow control flow uses the word **stages**, not "modes".
- All fix docs in this directory were swept for the wrong terminology.

### AD-6 — Three failure modes, three distinct channels

1. **Tool-call failure** → `DisplayFrame(origin='error', metadata={'tool_error': <name>, 'reason': <code|msg>, ...}, code=<raw err text>)`. Do NOT declare ambiguity. Landed in `release_policy`.
2. **Contract violation** → first-line fixes are prompt tightening + JSON output + `engineer.apply_guardrails(text, format='json')`. If validation still fails at runtime: `DisplayFrame(origin='error', metadata={'contract_violation': <field>}, code=<offending raw output>)`. Landed in `audit_policy` (`'audit_findings_missing'`) and `refine_policy` (`'outline_shrunk_after_merge'`, `'refine_did_not_persist'`).
3. **Ambiguous user intent** → `self.ambiguity.declare(level, metadata=...)` with one of the 4 levels (`general | partial | specific | confirmation`) from `_specs/components/ambiguity_handler.md`. The only channel that produces a clarification question.

## PEX ↔ AmbiguityHandler

- Used **only** for AD-6 Section 3 (user-intent ambiguity). Tool-call failure and contract violation do not declare ambiguity.
- 4 levels per `_specs/components/ambiguity_handler.md`:
  - `general` — intent unclear / dialog act unknown
  - `partial` — intent known, key entity unresolved (post / section / channel)
  - `specific` — intent + entity known, a slot value is missing or invalid
  - `confirmation` — a candidate value exists and needs user sign-off
- Canonical call pattern: `self.ambiguity.declare(level, metadata={...})` then `return DisplayFrame()` (empty frame — RES synthesises the clarification question).
- Threshold breach in `audit_policy` uses `confirmation` + `metadata={'reason': 'audit_threshold_exceeded', 'findings_preview': findings[:3]}` so the spoken line can reference what triggered the escalation.
- Duplicate-title in `create_policy` was **reclassified** from `confirmation` to `specific` (known intent, invalid slot value — a user mistake, not a candidate value awaiting sign-off).

## PEX ↔ FlowStack

- Stack-on is the inline three-line pattern:
  ```python
  self.flow_stack.stackon(flow_name)
  state.keep_going = True
  frame.thoughts = <reason>     # for user-visible transitions
  return frame
  ```
- `BasePolicy.stack_on` helper was **rejected** — `flow_stack.stackon()` already exists (`_theme7_feedback.md § Overall Feedback #4`).
- `flow.status = 'Completed'` is owned by each policy at the point of terminal success (per AGENTS.md invariant: RES is responsible for popping completed flows, so policies must mark completion before returning).
- Outline recursion invariant (AD-3): `OutlineFlow` may not stack on `'outline'`; other flows may.
- `fallback(flow_name)` usage landed in `polish_policy` (when `inspect_post` reports `structural_issues`, polish falls back to `rework`).

## PEX ↔ MemoryManager

- Scratchpad is dict-valued (AD-1): `dict[str, dict]`. Type hint on `write_scratchpad` widened `str` → `str | dict`.
- Write: `self.memory.write_scratchpad(flow.name(), {'version': '1', 'turn_number': context.turn_id, 'used_count': 0, <payload>})`.
- Read (key lookup): `self.memory.read_scratchpad(key)` returns the live dict reference (not a copy — consumers can bump `used_count` in place and write it back).
- Read (whole pad): `self.memory.read_scratchpad()` returns the full `dict[str, dict]` for skills that prompt-inject the entire scratchpad.
- Polish's `used_count` bump uses the live reference:
  ```python
  entry = self.memory.read_scratchpad(str(key))
  if isinstance(entry, dict):
      entry['used_count'] = entry.get('used_count', 0) + 1
      self.memory.write_scratchpad(str(key), entry)
  ```

## PEX ↔ DialogueState

- Contract surface (attributes PEX reads or writes): `state.keep_going` (stack-on continuation flag), `state.active_post` (set by `_resolve_source_ids` as a side-effect), `state.has_issues` (read by Plan-related flows and by `polish` for rework fallback decisions), `state.has_plan` (read by tone_policy for scratchpad write gating).
- **No new attributes added during Theme 1-7.** Every new cross-flow need was routed through scratchpad (AD-1) or frame.metadata (AD-6 error path).
- `DialogueState.findings` was **rejected** (AD-1).
- `active_post_title` etc. were **rejected** per MEMORY.md § "Sync lookups over cached state fields" — use `PostService.get_title(id)` on demand instead of adding a parallel cached field.

## AD-7 — Skill files carry YAML frontmatter

Every file in `backend/prompts/skills/` gets a frontmatter header with at least `name` / `description` / `version`, optionally `stages` and `tools`. Loader update in `PromptEngineer.load_skill_template` parses + strips the frontmatter before returning the skill body; new `load_skill_meta(name)` exposes the dict for registries. Details and schema in `policy_spec.md § AD-7` + research in `components_as_skills_proposal.md`.

## AD-8 — EVPI default-with-commit for optional slots

Optional slots with a sensible default **commit with the default** and let downstream (tool error, contract violation) decide whether to escalate via AD-6 or clarify via AmbiguityHandler. Do NOT declare `ambiguity.declare('specific', metadata={'missing_slot': …})` on optional-slot absence.

Existing callers that already implement this (canonical references):
- `audit_policy` — `if not flow.slots['reference_count'].filled: flow.fill_slot_values({'reference_count': 5})` (`revise.py:~98-103`)

Add to any flow that has an optional slot with a default. Does NOT apply to required slots or to optional slots without a defensible default.

## AD-9 — `_validate_frame` tightens; `_llm_quality_check` off by default

`_validate_frame` checks **value correctness** on the returned frame, not just non-emptiness. Concrete checks per block type:
- `card`: `post_id`, `title`, `content` present (or whichever the per-flow contract expects)
- `list`: `items` is a list, each item has `post_id` + `title`
- `confirmation`: `prompt`, `confirm_label`, `cancel_label` present
- `toast`: `message` present
- `error` origin: short-circuit to `passed=True` (AD-6 — the policy already decided to fail)

`_llm_quality_check` (the LLM-as-judge secondary check) is **off by default**. Activate only for flows whose prose quality is the entire output (candidate allowlist: `polish`, `rework`, `brainstorm`). Gate via a `BaseFlow.llm_quality_check = False` attribute that prose-heavy flows override. Rationale: the deterministic value-checks above are cheaper and catch more; LLM-as-judge on every turn doubles latency + cost with diminishing signal.

## AD-10 — Token-budgeting easy wins

Two additive changes, no AD conflicts:

1. **Prompt caching** on the `system_prompt` and `tool_defs` segments passed to `PromptEngineer.tool_call`. Wire `cache_control={'type': 'ephemeral'}` in `_call_claude` on those segments. 1-hour TTL, automatic cache hits across calls that share the same system + tools. Pure cost + latency reduction.
2. **Per-flow `max_response_tokens`** attribute on `BaseFlow`, default 4096, override per flow. Short flows (`inspect` if it ever runs LLM, `release`, `find` formatting) can drop to 1024; prose-heavy flows (`rework`, `compose`) keep the default or bump higher.

## `RecoveryAction` enum

- **Still present** in `backend/modules/pex.py` (line 27 + usage at 123, 250, 273, 291, 306, 319) — PEX's retry / escalate / reroute signalling plumbing predates this policy work.
- **Not touched by Theme 1-7.** The enum was never used as a cross-neighbour contract in the 12 policies we rewrote; it sits inside PEX's own recovery loop.
- **Recommended disposition (open follow-up, not in Theme 1-7 scope):** audit usage in a future cleanup and either (a) delete it if the `ESCALATE` path is the only live one, or (b) document the two-tier recovery (retry inside PEX vs. AD-6 error frame surfaced to RES) so both layers' semantics are clear.

## Best-practice justifications

> **Part 2 alignment.** The six ADs map onto three best-practices topics:
>
> - **AD-1 / AD-2 (scratchpad as interface, no informed-mode branching)** — [§ 9 Cross-turn state / findings channel](../best_practices.md#9-cross-turn-state--findings-channel). See [State of AI Agent Memory 2026 — mem0.ai](https://mem0.ai/blog/state-of-ai-agent-memory-2026) on structured scratchpads with `version` / `turn_number` / `used_count` metadata beating free-text memory; polish's unconditional scratchpad read matches the "always try to be informed" pattern.
> - **AD-3 / AD-4 / AD-5 (recursion safety, canonical outline levels, terminology discipline)** — [§ 5 Ambiguity / clarification protocols](../best_practices.md#5-ambiguity--clarification-protocols) and [§ 1 Skill-prompt structure](../best_practices.md#1-skill-prompt-structure). See [MAC — arXiv 2512.13154](https://arxiv.org/abs/2512.13154) on supervisor vs. expert routing (NLU classifies, policies call, skills produce — no cross-layer "fires" language) and [Anthropic skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) on consistent terminology across the system.
> - **AD-6 (three failure modes, three channels)** — [§ 3 Error recovery](../best_practices.md#3-error-recovery). See [Error Recovery and Graceful Degradation — notes.muthu.co](https://notes.muthu.co/2026/02/error-recovery-and-graceful-degradation-in-ai-agents/) on classification before recovery and [Your ReAct Agent Is Wasting 90% of Its Retries — TDS](https://towardsdatascience.com/your-react-agent-is-wasting-90-of-its-retries-heres-how-to-stop-it/) on distinguishing transient tool failures from semantic contract violations from user-intent ambiguity — the exact three-channel split AD-6 codifies.
