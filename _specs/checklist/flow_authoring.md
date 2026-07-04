# Flow Authoring — Reference

The durable, **cross-assistant** conventions for authoring (or modifying) a flow: its class, its
slot-fill prompt, its policy, and its skill. This is the deep how-to that `phase_7_policies.md` and
`phase_8_prompt_writing.md` point to; those phases give the build order, this gives the conventions.

Closed vocabularies are **not** restated here — they live in their component specs and are the source of
truth: ambiguity levels → [ambiguity_handler.md](../components/ambiguity_handler.md), the violation /
classification dict → [task_artifact.md](../components/task_artifact.md), the cross-turn channel →
[session_scratchpad.md](../components/session_scratchpad.md), render blocks →
[blocks.md](../utilities/blocks.md). Evals → [evaluation_suite.md](../utilities/evaluation_suite.md).

Domain-specific tables (a domain's tool grid, its content scopes, its ID formats) live in that
assistant's own docs — e.g. Hugo's are in `assistants/Hugo/schemas/flow_reference.md`.

Use this as a guide, not a checklist. Deviations get an inline comment citing the convention they bend.
The goal is **consolidation** — removing variance that hides bugs — not uniformity for its own sake.

---

## The four files

Every flow touches four files. A flow with only three of them fails at runtime (NLU can't fill slots, or
the policy crashes on a missing skill). Author one flow end-to-end; copy the shape of a working sibling.

1. **The flow class** — `backend/components/flow_stack/flows.py`. Inherit the intent parent
   (`<Intent>ParentFlow`) and set: `flow_type` (canonical lowercase name), `dax` (DACT code, digits
   ordered verb → noun → adjective), `entity_slot` (the slot that grounds the flow), `goal` (one
   sentence, reused in NLU prompts), the `slots` dict (name → slot instance with a priority), and the
   `tools` list. Register the class in `flow_stack/__init__.py:flow_classes`.
   - Do **not** invent a slot type — use the existing ones. Do **not** add a tool without approval.
   - `entity_slot` must name a slot that actually exists in `self.slots`.

2. **The slot-fill prompt** — `backend/prompts/nlu/<intent>_slots.py`, keyed by `flow_type`. Slots guard
   the policy from acting on wrong assumptions, so before writing it, answer: what does this flow do for
   the user? what assumption would be catastrophic to get wrong (e.g. editing the wrong entity)? can I
   justify every slot's type and priority? (See "The slot-fill prompt" below for structure.)

3. **The policy** — `backend/modules/policies/<intent>.py`, method `<flow>_policy(self, flow, state,
   context, tools)`, dispatched by the intent policy's `execute` on `flow.name()`. (See "Writing the
   policy".)

4. **The skill** — `backend/prompts/pex/skills/<flow>.md`. **Agentic flows only.** A deterministic flow
   (one tool, args fully derivable from slots) has no skill file. (See "Writing the prompt".)

---

## Designing the flow (decisions before code)

### Slots ≠ params

A **param** is what the LLM extracts to call a tool without a syntax error (a valid id). A **slot** is
what grounds the user's intent semantically (the *right* entity, not merely a valid one). Params care
about calling the tool correctly; slots care about understanding intent and grounding it properly.

### Slot priorities

Three levels, plus the entity convention. `flow.is_filled()` already encodes "all required filled AND ≥1
elective filled (if any)" — trust it; don't re-derive it in policies or prompts.

- **required** — must be filled before execution. Missing → `specific` ambiguity `metadata={'missing':
  '<slot>'}`.
- **elective** — exactly one of **≥2** must be filled. A single elective is a flow-design bug: promote it
  to required or drop it to optional. All electives empty → `specific` listing the alternatives.
- **optional** — nice-to-have. With a defensible default, commit it at policy entry; without one, absence
  is fine.
- **entity slot** — the special required slot naming what the flow operates on. Missing entity →
  `partial` ambiguity (a top-level grounding failure), early return.

**Optional default-with-commit.** When an optional slot has a sensible default, commit it at policy entry
and let downstream decide whether to clarify — don't declare ambiguity upfront (asking when a default
exists wastes a turn). Required/elective slots never get defaults; they drive routing.

```python
if not flow.slots['<optional>'].check_if_filled():
    flow.fill_slot_values({'<optional>': <default>})   # commit default; cite this convention
```

### Deterministic vs agentic dispatch

Deterministic when `len(flow.tools) == 1` **and** the tool's args are fully derivable from `flow.slots` +
grounding without LLM reasoning. Agentic when `len(flow.tools) >= 2` **or** any arg is prose the LLM must
compose. The split is **implied by the policy code** — never a flag on the flow class.

- **Deterministic:** no skill file. The policy builds params from slots, calls the tool directly, sets
  `flow.status = 'Completed'`, returns the artifact.
- **Agentic:** skill file + the policy calls `llm_execute(...)`; the sub-agent picks its trajectory from
  `flow.tools`.

### Cross-turn contract (scratchpad)

If a flow produces findings another flow consumes, write them to the Session Scratchpad at policy entry;
if it consumes, filter by key and increment `used_count`. Key = bare flow name; value = a dict with the
required envelope + structured payload (lists of dicts, not prose). **Never add a `DialogueState` or
`TaskArtifact` attribute for cross-turn state.** Full convention: [session_scratchpad.md](../components/session_scratchpad.md).

### Transitions

Three channels; always set `state.keep_going = True` so the loop continues to the next flow this turn.

- **stack on** — the flow needs another flow's output first: `flow_stack.stackon('<prereq>')`, artifact
  `thoughts` carries the reason.
- **fall back** — the intent belongs to a sibling flow: `flow_stack.fallback('<sibling>')`. Only for
  genuine misroutes — never for skill errors or tool failures.
- **yield when stacked** — a Converse turn ("yes" / "do option 2") landing on an already-active flow's
  confirmation should yield (complete, `keep_going=True`, empty artifact) so the underlying flow consumes
  the accept/decline, rather than answering with generic chit-chat.
- **self-recursion** is safe only if the recursive call enters a *different*, non-recursive branch and
  drains its trigger slot first. State the safety in a call-site comment; don't add depth guards.

### Output budget

Per-flow `max_response_tokens` (default 4096) is a design decision — it constrains what the skill can
produce, so design the output shape against it. Short signals ~1024; single-scope work ~2048; multi-scope
prose keeps 4096. A skill capped low must ask for compact/structured output, or it truncates and surfaces
as `parse_failure`. Changing a cap can break previously-passing evals — re-run the trajectory tier.

---

## The slot-fill prompt

The `rules` block mirrors the priority hierarchy top-to-bottom (required, then electives, then optional).
**One numbered step per slot, written as an imperative** (verb-first: "Fill", "Pick", "Capture", "Leave
null on…") — not a description (descriptions belong in the `slots` block). Nuance goes in sub-points.

```
1. <Imperative for required slot 1.> <Default behavior; anchor cases.>
   a. <Sub-rule for nuance, only when needed.>
3. Exactly one of <electives> fills (or all stay null when <bare-request condition>).
   a. `<elective>` fires when <trigger>; <how to capture>.
4. <Imperative for optional slot.>
N. Treat <slot-class> directives as current-turn-only — do NOT carry a prior-turn value into this fill
   unless the current turn co-references it ("yes", "do option 2"). The entity slot is the exception: it
   carries forward from grounding.
```

Most flows fit in 3–5 numbered steps; push detail into sub-points rather than fanning out to 6–10 rules.
The `slots` block holds descriptions only (name, priority, slot type, what it stores) — no when-it-fires
logic. Every unfilled slot must appear in each example's output. When you change a slot in `flows.py`,
grep the prompt and update the slots block, rules, and examples in lockstep.

---

## Writing the policy

### Method shape

```python
def <flow>_policy(self, flow, state, context, tools):
    # 1. Guard the entity slot — partial / general ambiguity use an EARLY return.
    if not flow.slots[flow.entity_slot].check_if_filled():
        self.ambiguity.declare('partial', metadata={'missing': '<slot>', 'entity': '<entity>'})
        return TaskArtifact(flow.name())

    # 2. Branch on slot state — most policies spend their lines here.
    if <specific ambiguity condition>:
        self.ambiguity.declare('specific', metadata={'missing': '<slot>'})
        artifact = TaskArtifact(flow.name())
    elif <prerequisite missing>:
        self.flow_stack.stackon('<prereq>'); state.keep_going = True
        artifact = TaskArtifact(flow.name(), thoughts='<reason>')
    else:
        # 3. Dispatch (agentic) or call the tool (deterministic), then persist.
        text, tool_log = self.llm_execute(flow, state, context, tools)
        saved, _ = self.engineer.tool_succeeded(tool_log, '<tool>')
        if not saved:
            artifact = TaskArtifact(flow.name(), parts={'violation': 'failed_to_save'}, thoughts=...)
        else:
            flow.status = 'Completed'
            artifact = TaskArtifact(flow.name(), thoughts=text)
            artifact.add_block({'type': '<block>', 'data': {...}})

    return artifact   # single exit
```

**Rules:** single return at the end (early returns only for `partial` / `general` grounding failures);
slots route the flow (the first branch is "which slot state are we in?"); hand-write each guard (slot
semantics vary too much for a `guard_slot` helper); default-commit is rare and cited.

### Conventions

1. **Don't defend deterministic code.** Tools have known contracts. Index directly
   (`result['outline']`, `slots['source'].values[0]`); let a missing key or `_success=False` crash so
   tests catch the bug.
2. **No defaults that hide errors.** `text or ''`, `parsed or {}`, `isinstance(parsed, dict)` mask
   upstream bugs. Branch on the value; don't coerce.
3. **Slot priorities are definitional.** Trust `flow.is_filled()`; don't re-check each elective.
4. **Build `parts` + `thoughts` first, then the artifact** in one line. Empty guards shorten to
   `TaskArtifact(flow.name())`.
5. **`code` holds payloads; `thoughts` holds prose.** `code` = raw tool response / failing JSON / stack;
   many error artifacts have no `code`, and that's fine.
6. **Keep metadata sparse** — classification only (violation category, missing-slot name). Specifics go
   in `thoughts`, not nested keys.
7. **`ambiguity.declare` uses `observation`** for human text; metadata is classification only. Don't stuff
   the question into metadata.
8. **Never invent new keys without approval** — in metadata, block data, scratchpad payloads, or tool
   args. If what you want to pass doesn't fit an existing key, surface the design question.
9. **Standard variable names** so reviewers pattern-match: `text, tool_log` from `llm_execute`, `parsed`
   from `apply_guardrails`, `saved, _` from `tool_succeeded`.
10. **No em-dashes in `thoughts`** — it is user-facing; commas and short sentences.
11. **Single return at end**; early returns only for major (grounding) errors.
12. **`origin` is always the flow name** for policy-built artifacts; error-ness lives in the
    classification dict, not `origin`. (Artifacts built outside the policy layer may use `'system'`.)

### Failure channels

Three failure modes, three distinct channels — conflating them hides root cause.

- **Tool failure** (network, permission, deterministic tool `_success=False`): error artifact with
  `parts={'violation': 'tool_error', 'failed_tool': '<tool>'}`, raw text in `code`. Retry once if
  transient (timeout, lock); otherwise return the error artifact. **No** ambiguity.
- **Ambiguous user intent** (missing/unclear slot, unresolved entity): `ambiguity.declare(level,
  observation=..., metadata=...)` — the only channel that produces a clarification. One per turn; return
  immediately. Level per the grounding gradient in [ambiguity_handler.md](../components/ambiguity_handler.md).
- **Skill contract violation** (output won't parse into the expected shape): `apply_guardrails(text,
  format='json')` fails closed, then `parts={'violation': 'parse_failure'}`, `code=text`. The skill is
  broken, not the user's intent — don't route to the ambiguity handler.

The artifact field contract (`origin` / `parts` / `thoughts` / `code` / `blocks`) is in
[task_artifact.md](../components/task_artifact.md).

---

## Writing the prompt (agentic flows)

### Three layers

| Layer | Owner | Contents | Cacheable |
|---|---|---|---|
| **System prompt** | universal persona builder + intent-scoped background + the skill body | persona, hard rules, closed-vocabulary tables, intent background, skill behavior | ✅ stable across turns |
| **User message (starter)** | `prompts/pex/starters/<flow>.py::build` | `<task>` framing, preloaded content, resolved details, recent conversation | ❌ per-turn |
| **Tool definitions** | the tool manifest, filtered to `flow.tools` | tool signatures + descriptions | ✅ stable per flow |

**System = constraints; user message = the task.** Claude weights the user message slightly higher, so
critical per-flow rules go there. **Tool descriptions are a prompting surface** — precise descriptions with
examples and gotcha sub-bullets buy more compliance than prompt edits.

**Composition:** persona → intent background → universal ambiguity/error tables → skill body, joined with
single blank lines. Hard rules that must not break appear in the system prompt **and** are reinforced in
the skill body (repetition is a feature).

**Caching:** stable content first, volatile last; never interleave a per-turn token (date, session id,
latest utterance) inside a cacheable prefix — it invalidates the entry every call.

**Prompting technique:** explain WHY not just WHAT; negative examples are first-class ("Don't add
docstrings to code you didn't change" beats "be concise"); conversational first-person register; define
what to accomplish and what to avoid, then let the model reason about how.

### Starter (user message)

Envelope: `<task>` (one line: verb + target + tool sequence + optional end condition), an optional
content block preloading what the skill would otherwise re-fetch, `<resolved_details>` with **semantic
labels** (never raw slot names — the LLM is in execution mode, grounding is done), and the recent
conversation. Serialization helpers strip empty fields and internal flags; aim for a handful shared across
flows, not one per slot. XML wraps data the model treats as content; markdown headers stay in the system
prompt and skill.

### Skill file

Frontmatter (`name` matching `flow.name()`, `description`, optional `tools` allowlist asserted against
`flow.tools` at load), then a `## Process` (imperative steps; act only on the latest utterance), an error
branch, a `## Tools` section, and **few-shot examples**. Typically 3 examples that exercise *different tool
paths* (variation teaches; redundant scenarios train one case); cover a normal case + ≥1 edge/error
branch; each example's trajectory ends with the parseable output (the schema, shown concretely). Pick a
realistic topic that does **not** overlap the eval set. The scenario's setup must agree with the rendered
user message, or the example silently breaks.

---

## Verifying & process

### The three eval tiers

Same rubric keys, widening scope: **Tests** (a single decision), **Traces** (an ordered tool trajectory),
**Evals** (the end-to-end result). Structure, runners, and how to run are canonical in
[evaluation_suite.md](../utilities/evaluation_suite.md). When wiring a new flow, confirm: the class
resolves in `flow_classes`; the skill template loads (or is absent by design for a deterministic flow); a
sample utterance routes to the flow; the tool trajectory matches the skill; grounding is set for any
grounded flow; spoken text is composed by the acting loop from blocks/data, not stuffed into `thoughts`
(unless the flow's whole contract is prose).

### LLM nondeterminism

Even at `temperature=0`, accuracy swings across runs — don't pretend an LLM-in-the-loop test is
deterministic. Gate the probabilistic tiers on 2-of-3 passes and retry-with-diagnostic (fail only if both
retries fail; log the divergence). The deterministic tier is single-run-gatable. Don't assert exact tool
sequences for agentic flows (multiple valid trajectories) or prose quality with substring checks (use an
LLM judge sparingly, only for genuinely subjective rubrics).

### Anti-patterns to scan for

| Anti-pattern | Why it's wrong |
|---|---|
| `text or ''`, `parsed or {}`, `.get('k', '')` | Silently converts errors to empty; tests pass, prod breaks |
| Declaring ambiguity for a tool failure | Conflates failure channels — a tool being down is not a user question |
| Em-dashes in `thoughts` | User-facing text |
| Inventing metadata / block / scratchpad keys | Downstream silently drops unrecognized keys |
| Defensive `if id and id != ''` after grounding | Hides a missing contract |
| Hallucinated APIs | Crashes at runtime, looks confident in review — verify against the module |
| Both policy and skill persisting | Double-write, silent overwrite |
| `if legacy_flag: … else: …` shims | Doubles code paths; remove old paths cleanly |
| `## Slots` header inside a skill file | The LLM is in execution mode; grounding is done by NLU |

### Project discipline

- **No new concepts without approval.** Check existing helpers first; a genuinely new concept is a design
  question surfaced *before* code. Promote to a helper only at ≥3 call-sites with a stable shape and ≥3
  lines of body.
- **Migration order.** Lock shared helpers + conventions before per-flow rewrites: pure refactor → surface
  shrink → exemplar rewrites → structured-output + scratchpad → failure channels → cross-turn wiring. Each
  step validates against the previous. Update test fixtures in the same commit as any key rename. Fix the
  earliest failure first — downstream symptoms often clear on their own.
- **Communicate with tradeoffs.** Two-option proposals beat one; verify assumptions with `grep` / `git`,
  not memory; land large refactors by theme with eval gates between.

---

## Quick reference

| Question | Answer |
|---|---|
| Entity slot unfilled? | `partial` ambiguity, early return |
| Required value slot missing? | `specific` ambiguity `{missing: <slot>}` |
| Tool failed (infra)? | `tool_error` artifact, retry once if transient — not ambiguity |
| Skill returned bad output? | `apply_guardrails` first, then `parse_failure` artifact |
| Optional slot missing? | Commit a defensible default, else proceed |
| Pass findings between flows? | Session Scratchpad, key = flow name |
| Load context in the policy? | No — NLU already grounded it; use the filled slots |
| New attribute on `DialogueState`? | No — scratchpad for cross-turn, `parts` for per-turn |
| Single elective slot? | Invalid — make it required or optional |
| Deterministic or agentic? | Deterministic iff 1 tool + args derivable from slots |
| Where do hard rules go? | Both system prompt and skill body |
| New violation / ambiguity level? | No — the sets are closed; surface a design question |
