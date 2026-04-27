# Policy Builder — Lessons Reference

A forward-looking guide for writing Hugo policies, skills, starters, and the supporting code around them. Read this when starting a new flow; cite specific sections in code review.

**Six parts, in the order an author works:**

1. **Foundations** — universal architectural surfaces, identifier formats, and closed vocabularies that span every Hugo agent and every flow.
2. **Designing the Flow** — decisions before any code is written (dispatch, slots, cross-turn channel, transitions, output budget).
3. **Writing the Policy** — Python in `backend/modules/policies/*.py`.
4. **Writing the Prompt** — system prompt, user-message starter, and skill file (agentic flows only).
5. **Verifying & Process** — evals, anti-patterns, project discipline.
6. **Reference** — lookup tables and quick answers.

Conventions are described where they apply: in Part II for flow-design rules, Part III for policy rules, Part IV for prompt rules, Part V for verification rules. Foundations holds only the cross-cutting surfaces and vocabularies.

Use this as a guide, not a checklist. Deviations need an inline comment citing which convention justifies them. The goal is **consolidation** (removing variance that hides bugs), not uniformity for its own sake.

This document organizes hard-won lessons; over time, settled lessons should be merged into the canonical specs at `personal_assistants/_specs/`.

---

# Part I — Foundations

The architectural surfaces, identifier formats, and closed vocabularies that cross every Hugo agent and every flow.

## I.A — Architectural Surfaces

### Component contracts

Hugo's runtime layers communicate through fixed surfaces. Don't widen them.

| Surface | Direction | Channel |
|---|---|---|
| NLU → PEX | Pre-grounded context | `DialogueState` (slots already filled) |
| PEX → RES | Display payload | `DisplayFrame` (origin, metadata, blocks, thoughts, code) |
| Policy → Skill / Tools | Dispatch | `BasePolicy.llm_execute(...)` (agentic) or inline `tools(name, params)` (deterministic) |
| Policy → AmbiguityHandler | Clarification | `self.ambiguity.declare(level, observation=..., metadata=...)` |
| Policy → FlowStack | Transitions | `self.flow_stack.stackon('<name>')` / `.fallback('<name>')` |
| Policy → MemoryManager | Cross-turn state | `self.memory.write_scratchpad(flow.name(), payload)` |
| Skill → Tools | Tool-calls during agentic loop | `engineer.tool_call` 8-iteration cap |

**NLU has already grounded** the entity, slot, and intent before the policy runs. Do NOT call `read_metadata` or `find_posts` in the policy to re-ground — use what's in `flow.slots` and the resolved-context dict. Re-grounding wastes rounds and tokens.

### Slot architecture

Hugo's slot priority follows the spec's three-level scheme, plus an entity convention:

- **`required`** — must be filled before execution. Missing → `specific` ambiguity with `metadata={'missing_slot': '<name>'}`.
- **`elective`** — exactly one of ≥2 must be filled. Single-elective is invalid (convert to required or optional). All electives empty → `specific` with `missing_slot` listing the alternatives.
- **`optional`** — nice-to-have. With a defensible default, commit it inline (see Part II ch. 2). Without, treat absence as OK.

`flow.is_filled()` already encodes "all required filled AND ≥1 elective filled (if any)." Trust it; don't re-derive.

**Entity slot** is the special required slot identifying what the flow operates on (post, section, channel, tags, title). Often a `SourceSlot`; sometimes `ExactSlot`, `FreeTextSlot`, or `ImageSlot`. Missing entity → `partial` ambiguity (top-level grounding failure):

```python
if not flow.slots[flow.entity_slot].check_if_filled():
    self.ambiguity.declare('partial', metadata={'missing_entity': '<entity>'})
    return DisplayFrame(flow.name())  # early return — see Convention #11
```

### Terminology discipline

Words have specific meanings. Use them precisely:

| Layer | Verbs that apply | Verbs that don't |
|---|---|---|
| NLU | classifies intent, detects flow, fills slot | "fires", "triggers", "activates" |
| Policy | calls a tool, declares ambiguity, returns a frame, scans tool_log | — |
| Skill | produces output | "saves" (unless skill owns persistence) |
| Flow | completes, stacks on, falls back | — |
| In-flow control | "stages" | "modes" |

Crisp terminology lets reviewers reason about which layer is responsible without ambiguity.

## I.B — Identifier Formats

Universal identifier conventions used across all flows:

- **Post ID** — 8-char lowercase hex (first 8 of UUID4).
- **Section ID** — slug (lowercase, punctuation-stripped, dashes, ≤80 chars).
- **Flow name** — bare lowercase string (`outline`, `refine`, `compose`); used as scratchpad key and `DisplayFrame.origin`.

Example post ID: `abcd0123`. Example section ID: `motivation-and-goals`.

## I.C — Closed Vocabularies

Closed sets. Cite by name; never extend without explicit user approval.

### Violation codes (8)

`metadata['violation']` names what kind of failure occurred. Specifics go in `thoughts` (natural language), not nested keys.

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

### Ambiguity levels (4)

Match the spec exactly. Use exactly one when declaring user-intent ambiguity.

| Level | Meaning |
|---|---|
| `general` | Intent itself is unclear; gibberish; rare in the PEX and policy phase |
| `partial` | Intent known, key entity unresolved (which post? which section?) |
| `specific` | Intent + entity known; a slot value is missing or invalid |
| `confirmation` | A candidate value exists and needs user sign-off |

### Block types

Render-targeting choice for `frame.blocks`. Pick the type the flow's RES template expects.

| Block | Used for | Required data |
|---|---|---|
| `card` | Updates the post card (most Draft / Revise flows) | `{post_id, title, sections, ...}` |
| `selection` | Presents candidate options (outline propose, audit findings) | `{options: [{label, id}, ...]}` |
| `list` | Search results (find, browse) | `{items: [{post_id, title, ...}]}` |
| `compare` | Side-by-side comparison | `{left, right}` |
| `toast` | Lightweight notification (release, schedule) | `{message, level}` |
| (none) | Chat-only flows (inspect, explain, undo) | — |

**"No block" does NOT mean "empty screen"** — whatever was on screen stays. Chat-only flows are additive to the conversation, not a screen-clear.

### Content tags

XML wrappers for preloaded data in the user message. Match the tag to the scope of the data.

| Tag | Scope |
|---|---|
| `<post_content>` | Whole post (used when post is just an outline) |
| `<post_preview>` | Post with sections and first few lines of each section (used when post is prose) |
| `<section_content>` | Single-section work (most Revise-intent flows) |
| `<line_snippet>` | Snippet-level work (single sentence or bullet span) |
| `<channel_content>` | Publish-intent flows |

### Outline depth scheme (5 levels)

| Level | Markdown |
|---|---|
| 0 | `# Post Title` (not editable) |
| 1 | `## Section Subtitle` |
| 2 | `### Sub-section` |
| 3 | `- bullet point` |
| 4 | `  * sub-bullet` |

Most outlines use Level 1 + Level 3. Add Level 2 only when a section needs explicit sub-structure; use Level 4 only when a bullet genuinely needs supporting detail.

---

# Part II — Designing the Flow

Decisions to make before writing any code.

## 1. Deterministic vs Agentic Dispatch

**Heuristic.** Deterministic when `len(flow.tools) == 1` AND the tool's args are fully derivable from `flow.slots` + `state.active_post` without LLM reasoning. Agentic when `len(flow.tools) >= 2` OR any arg is prose/content the LLM must compose.

**Deterministic flow.**
- No skill file, no starter.
- Policy builds `params` from slots, calls `tools('<tool_name>', params)` directly, flips `flow.status = 'Completed'`, returns a `DisplayFrame`.
- On tool failure: `DisplayFrame(flow.name(), metadata={'violation': 'tool_error'}, code=result['_message'])`.

**Agentic flow.**
- Skill file at `backend/prompts/pex/skills/<flow>.md`.
- Starter at `backend/prompts/pex/starters/<flow>.py`.
- Policy calls `BasePolicy.llm_execute(...)`; the sub-agent picks the trajectory from `flow.tools`.
- On no save: `DisplayFrame(flow.name(), metadata={'violation': 'failed_to_save'}, thoughts=...)`.

The deterministic-vs-agentic split is **implied by the policy code** — never declared on the flow class. No `flow.deterministic` flag.

## 2. Slot Design & Optional-Slot Defaults

When designing a flow's slot schema:

- **Required vs elective vs optional.** Every required slot must be filled. Electives must come in groups of ≥2; if there's only one alternative, make it required or optional. Optional slots represent nice-to-haves.
- **Entity slot is required.** Pick the slot type that fits — `SourceSlot` for post/section, `ExactSlot` for title, `FreeTextSlot` for tags, `ImageSlot` for images.
- **Don't widen the slot vocabulary** unless you have a contract change to back it. Inventing slot priorities or types triggers cascading consumer changes.

When in doubt: ask *does the skill have enough to produce the right output given what `is_filled()` accepts?* If not, the flow's slot priorities are wrong — fix the flow, not the policy.

### Default-with-commit for optional slots

**Rule.** Optional slots with a sensible default commit the default at policy entry and let downstream decide whether to clarify. Do NOT declare ambiguity upfront on optional-slot absence.

**Why.** Asking when a default exists wastes a turn; the expected value of perfect information is often negative.

**When to apply.** Optional slots only. Required and elective slots never get defaults — they drive routing. If no defensible default exists, treat absence as OK and proceed.

```python
# At policy entry, when default-with-commit applies:
if not flow.slots['<optional>'].check_if_filled():
    flow.fill_slot_values({'<optional>': <default>})  # commit default
```

## 3. Cross-Turn Contract — Session Scratchpad

The Session Scratchpad is the canonical cross-turn channel for findings and produced output. The spec describes it as natural-language snippets; Hugo's policies use it more structurally — keyed dicts with a small required envelope, plus flow-specific payload.

### Hugo scratchpad convention

Use the Session Scratchpad (`MemoryManager`, L1, turn-surviving) as the standard cross-policy findings channel. Never add a new `DialogueState` or `DisplayFrame` attribute.

**Convention.**
- **Key** = bare `flow.name()` (e.g., `'inspect'`, `'audit'`).
- **Value** = `dict` with required envelope fields: `version`, `turn_number` (= `context.turn_id`), `used_count`, plus flow-specific payload keys.
- **Type** of the whole pad: `dict[str, dict]` (serializable).

Producers write at entry. Consumers filter by key (or walk the whole pad — capped at 64 snippets) and increment `used_count` on entries they reference.

```python
# Producer
self.memory.write_scratchpad(flow.name(), {
    'version': 1, 'turn_number': context.turn_id, 'used_count': 0,
    'findings': [...],
})

# Consumer
entry = self.memory.read_scratchpad('audit')  # live reference, mutate in place
if entry:
    findings = entry.get('findings', [])
    entry['used_count'] += 1
    self.memory.write_scratchpad('audit', entry)
```

### Designing the cross-turn contract

When designing a flow, decide whether it:

- **Writes findings.** It produces output another flow will consume (research-style flows). Write at policy entry with the Hugo scratchpad convention.
- **Reads findings.** Walk or filter-by-key on the scratchpad; increment `used_count` for entries you consume.
- **Neither.** Most flows don't touch the scratchpad.

Keep payloads structured (lists of dicts, not freeform prose). Downstream consumers depend on the shape, and the shape is your contract.

## 4. Transitions

Three transition channels, each with different UX. Always set `state.keep_going = True` so PEX continues to the next flow on the same turn.

### Stack on (prerequisite setup)

The current flow needs another flow's output before it can run. Push the prerequisite, resume after.

```python
self.flow_stack.stackon('<prereq_flow>')
state.keep_going = True
frame = DisplayFrame(flow.name(), thoughts='<reason — surfaces to user via RES>')
```

The user sees the sub-flow's work before returning to the original.

### Fall back (re-route to sibling)

The user's intent maps to a different flow than NLU detected. Pop current, push sibling.

```python
self.flow_stack.fallback('<sibling_flow>')
state.keep_going = True
frame = DisplayFrame(flow.name(), thoughts='<why we re-routed>')
```

Use only when the intent genuinely belongs elsewhere — never for skill errors (use error frames) or tool failures (use failure-channel frames in Part III).

### Self-recursion safety

A policy may self-recurse only if the recursive call enters a different branch — one that does NOT self-recurse. The recursion must drain its trigger slot before recursing.

**How.** Document the safety in a comment at the recursion call-site. Don't rewrite to iterative; don't add depth guards — those mask the contract instead of stating it.

**Anti-pattern:** treating any self-recursion as dangerous. Some flows naturally recurse ("propose 3 candidates, user picks one, refine if needed") — the contract is the safety, not extra machinery. `OutlineFlow` may NOT `stackon('outline')` itself; other flows may.

## 5. Output Budget

Per-flow `max_response_tokens` (set on `BaseFlow.__init__`, default 4096). This is a flow-design decision — it directly constrains what the prompt and skill can produce, so the output shape must be designed against the cap.

### Sizing guidance

- Short-output flows (inspect, find post-dedup, release notifications): 1024.
- Most single-section flows: 2048.
- Multi-section prose flows (whole-post compose, polish-informed): keep default 4096.

### Implications for prompt design (Part IV)

The cap chosen here directly shapes how the prompt and skill must be written:

- **Schema must fit under the cap.** A skill capped at 1024 cannot ask for a 4096-token response — it will truncate mid-output and surface as `parse_failure`. Document the expected response size in the skill body so the LLM doesn't over-produce.
- **Few-shot examples consume the cap.** If examples occupy >60% of the cap, shrink them or raise the cap. The skill needs headroom for actual generation.
- **Tighter caps favor structured output.** A 1024-cap flow should ask for JSON or short-form lists, not prose paragraphs. Prose-heavy flows justify the default 4096.
- **Cap changes can break previously-passing evals.** Re-run Tier 2 on any flow whose cap moved.

---

# Part III — Writing the Policy

## 1. Method-Shape Contract

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
            thoughts = '<what the skill did wrong>'
            frame = DisplayFrame(flow.name(), metadata={'violation': 'failed_to_save'}, thoughts=thoughts)
        else:
            flow.status = 'Completed'
            frame = DisplayFrame(flow.name(), thoughts=text)
            frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})

    return frame  # single exit
```

**Key rules:**
- **Single return at end.** Early returns only for `partial` / `general` ambiguity (top-level grounding failures).
- **Slots route the flow.** The first branch decision is "which slot state are we in?" — `flow.is_filled()` answers most of it.
- **Hand-write the guard per flow.** No universal `guard_slot` helper — slot semantics vary too much across flows for an abstraction to fit.
- **Default-commit is rare.** Only when an optional slot has a defensible default; cite the convention in the comment.

## 2. The 12 Conventions

Distilled from real review. Every Hugo policy must respect these. Deviations need an inline comment citing the specific number.

1. **Don't defend deterministic code.** Service tools have known contracts. `flow_metadata['outline']`, not `flow_metadata.get('outline', '')`. If a key is missing or `_success=False`, that's a bug to surface, not a branch to guard.

2. **No defaults that hide errors.** `text or ''`, `parsed or {}`, `isinstance(parsed, dict)` — banned. Trust the contract; let the code crash on unexpected state so tests catch it.

3. **Slot priorities are definitional, not advisory.** Trust `flow.is_filled()` instead of re-checking each elective.

4. **Build `frame_meta` and `thoughts` first, then the frame.** Assemble the dict and prose on their own lines, then instantiate `DisplayFrame` in a single line. Empty guard frames shorten to `DisplayFrame(origin=flow.name())`.

   ```python
   thoughts = 'Outline shrunk from 5 bullets to 3 without an explicit removal directive.'
   frame = DisplayFrame(flow.name(), metadata={'violation': 'failed_to_save'}, thoughts=thoughts)
   ```

5. **`code` holds actual code; `thoughts` holds descriptive text.** `code` is for copy-paste payloads (raw tool response, failing JSON, error stack). Prose explanation goes in `thoughts`. Many error frames have no `code` at all, and that's fine.

6. **Keep metadata sparse.** Metadata is for classification (violation category, missing-slot name). Flow identity lives in `origin`, not metadata. Specifics go in `thoughts` (natural free-form text), not nested-underscore tokens.

7. **`ambiguity.declare` uses `observation`, not metadata keys.** `declare(level, observation=<human_text>, metadata=<classification>)`. Don't stuff `question` / `reason` / `prompt` into metadata.

   ```python
   self.ambiguity.declare('partial',
       observation='Simplify needs either a section or an image to target.',
       metadata={'missing_entity': 'section_or_image'})
   ```

8. **Never invent new keys without approval.** Hard rule. Whether in `metadata`, `extra_resolved`, `frame.blocks` data, or anywhere else — don't introduce a new key. If what you want to pass doesn't fit an existing key, surface the design question.

9. **Standard variable names.** Consistency lets reviewers pattern-match instantly.

   | Concept | Name |
   |---|---|
   | result of `tools('read_metadata', ...)` | `flow_metadata` |
   | result of `llm_execute` | `text, tool_log` |
   | result of `apply_guardrails` | `parsed` |
   | result of `tool_succeeded` | `saved, _` (or `saved_any`, `content_saved` when distinguishing) |

10. **No em-dashes in `frame.thoughts`.** Thoughts are user-facing. Use commas and short sentences. Em-dashes are hard to parse on small screens.

11. **Single return at end; early returns only for major errors.** See § III.1. `partial` / `general` ambiguity use early returns. Everything else — `specific`, `confirmation`, stack-on, fallback, success, error frames — assigns to `frame` and falls through to one `return frame` at the bottom.

12. **`origin` is always the name of the flow.** Every `DisplayFrame` a policy builds sets `origin` to `flow.name()` — guards, stack-on, fallback, error, and success frames alike. Error-ness lives in metadata (`'violation' in frame.metadata`). The only exception is frames built outside the policy layer (e.g., an `Agent.take_turn` try-catch can use `'system'`).

## 3. Failure Channels

Three failure modes, three distinct channels. Two channels live here (policy-side: tool failures and ambiguity); the third — contract violations from skills — lives in Part IV.C, since the skill's prompt determines whether output parses.

### Tool failures vs. user-intent ambiguity

**Tool-call failure** (network, API down, permission denied, deterministic tool returned `_success=False`):

```python
return DisplayFrame(flow.name(),
    metadata={'violation': 'tool_error', 'failed_tool': '<tool_name>'},
    code=result['_message'])
```

No ambiguity. Use `code` for raw payloads. **Retry rule:** if the error is transient (timeout, lock), retry once via `BasePolicy.retry_tool(tools, name, params, max_attempts=2)`. Non-retryable or retry-failed → return the error frame.

**Ambiguous user intent** (missing or unclear slot, unresolved entity):

```python
self.ambiguity.declare(level, observation=..., metadata=...)
```

The only channel that produces a clarification question. One clarification per turn — return immediately after `declare()`.

**Why split.** Tool failures are infrastructure (no question for the user). Ambiguity is a user-facing clarification need. Conflating them hides root cause.

### Picking the ambiguity level

| When the policy discovers... | Declare | Metadata | Frame shape |
|---|---|---|---|
| No entity slot filled, no candidate in scratchpad | `general` | none | empty; RES asks "what are we doing?" |
| Entity is post/section but `post_id` unresolvable | `partial` | `{missing_entity: 'post'}` | empty; RES asks "which post?" |
| Required value slot missing | `specific` | `{missing_slot: <name>}` | RES asks "what value do you want?" |
| All electives empty | `specific` | `{missing_slot: <alt1>_or_<alt2>}` | "Which direction do you want to go?" |
| Candidate exists needing sign-off (duplicate title, audit threshold) | `confirmation` | `{candidate: <value>}` or `{reason: <code>}` | optional confirmation block |

### Forward-pointer to contract violations

When the skill returns malformed output, the policy uses:

```python
parsed = self.engineer.apply_guardrails(text, format='json')
if 'findings' not in parsed:
    return DisplayFrame(flow.name(),
        metadata={'violation': 'parse_failure'},
        code=text)
```

The skill is broken, not the user's intent — don't route to `AmbiguityHandler`. Skill-side prevention (output schemas, schema-reinforced few-shots) lives in Part IV.C.

## 4. Frame Construction

`DisplayFrame` is the policy → RES contract. Single-meaning fields:

- **`origin`** = flow name
- **`metadata`** = classification only (`violation`, `missing_slot`, `missing_entity`, `missing_reference`, `failed_tool`). Sparse (Convention #6).
- **`thoughts`** = user-facing prose (no em-dashes; commas and short sentences). Goes through RES naturalization.
- **`code`** = raw payloads (tool error text, failing JSON, stack traces). Machine-consumable.
- **`blocks`** = render-targeting list. Pick the type the flow's RES template expects.
- **`flow.status = 'Completed'`** = set by the policy on successful terminal frames.

**Frame patterns:**

```python
DisplayFrame(origin=flow.name())                                                        # empty guard
frame = DisplayFrame(flow.name(), thoughts='No outline yet, outlining first.')   # stack-on
frame = DisplayFrame(flow.name(), metadata={'violation': 'failed_to_save'}, thoughts=...)  # error
frame = DisplayFrame(flow.name(), thoughts=text)                                 # success
frame.add_block({'type': 'card', 'data': {...}})                                 # add block
```

---

# Part IV — Writing the Prompt

Agentic flows only. Deterministic flows have no skill file or starter.
The prompt has three layers, owned by three different files; this Part is organized to match.

- **IV.A — System Prompt** (Layer 1: persona + intent + universal tables + skill body)
- **IV.B — Starter / User Message** (Layer 2: per-turn task framing + preloaded data)
- **IV.C — Skill File** (the body of Layer 1 specific to this flow)

## IV.A — System Prompt

### 1. Three-Layer Architecture

| Layer | Owner | Contents | Cacheable? |
|---|---|---|---|
| **Layer 1 — System prompt** | `prompts/general.py::build_system` (universal persona) + `prompts/pex/sys_prompts.py::PROMPTS[intent]` (intent-scoped Background) + `prompts/pex/skills/<flow>.md` (skill body) | Persona, ID schema, outline depth, ambiguity + violation tables, intent Background, skill behavior | ✅ Stable across turns |
| **Layer 2 — User message** | `prompts/pex/starters/<flow>.py::build` | `<task>` framing, content tag with preloaded data, `<resolved_details>`, `<recent_conversation>` | ❌ Per-turn |
| **Layer 3 — Tool definitions** | `schemas/tool_manifest_hugo.json` (filtered to `flow.tools`) | Tool signatures and descriptions | ✅ Stable per flow |

**Critical division.** System prompt = constraints (persona, guardrails, schemas, hard rules). User message = task (this turn's job, this turn's data). Claude weights user messages slightly higher, so critical per-flow rules go there.

**Tool descriptions are a prompting surface.** Refining tool descriptions yields more compliance gains than prompt edits. Treat `schemas/tool_manifest_hugo.json` as instructions; invest in precise descriptions with examples and gotcha sub-bullets.

### 2. System Prompt Composition

`build_skill_system` concatenates persona → intent prompt → universal `## Handling Ambiguity and Errors` → skill body.

**Concrete ordering** (top to bottom):

1. Universal persona + 3 rules (response length, visual blocks, no-fabrication) — stable across ALL flows.
2. Intent-woven persona sentence opening with `"You are currently working on {Intent} tasks, which {definition}"`, plus the per-intent `## Background` block (locked in `sys_prompts.py`).
3. `## Handling Ambiguity and Errors` (universal tables).
4. Skill body (stable within a flow).

**Hard-rule reinforcement.** Rules that absolutely cannot be violated appear in the system prompt AND get reinforced in the skill body. Empirically improves Claude compliance. Repetition is a feature.

**Assembly conventions:**
- Single blank lines between blocks. Joined with `'\n\n'.join(segments)`, never double-blanks. No trailing divider cruft.
- Divider between intent prompt and skill body: `--- {Flow_name} Skill Instructions ---` (Title Case flow name).

**Prompting techniques (apply across all three layers):**
- **Explain WHY, not just WHAT.** *"Never output more than 5 sections — users reported feeling overwhelmed by longer outlines."* The why lets Claude reason about edge cases.
- **Negative examples are first-class.** *"Don't add docstrings to code you didn't change"* outperforms *"be concise"*. Specific negatives are actionable; general positives are ambiguous.
- **Repetition is a feature.** Say critical things three separate times if needed. *"Repeating one more time the core loop here for emphasis:"* is a legitimate pattern.
- **Conversational, first-person register.** Write like a Slack message from a teammate, not strict documentation. Be firm. Use ALL CAPS at least once for non-negotiable rules.
- **Don't over-constrain.** Clear constraints + freedom to reason. Define what the sub-agent must accomplish and what it must not do; let it reason about *how*.

### 3. Prompt Caching

Stable content first; volatile content last. The system prompt's universal + intent-scoped blocks are stable across all flows in an intent and heavily cacheable.

**Cache markers.** Add `cache_control={'type': 'ephemeral'}` to the system-prompt tail and tool-defs array in `PromptEngineer._call_claude`. 1-hour TTL. Reads cost 0.1× input tokens; writes cost 1.25× (5-min) or 2× (1-hour). Pure cost + latency win.

**Hard rule.** Never interleave per-turn tokens (date, session ID, latest utterance) inside cacheable prefixes. A single per-turn token invalidates the cache entry on every call.

The user message (Layer 2) is per-turn and uncacheable; that's the right place for volatile content.

## IV.B — Starter / User Message

### 1. Starter Construction

`backend/prompts/pex/starters/<flow>.py` exports `TEMPLATE` and a `build(flow, resolved, user_text)` function. Canonical user-message envelope:

```xml
<task>
{flow_verb} {target} of "{post_title}". {tool_sequence}. {optional end_condition}.
</task>

<post_content>  [or <section_content>, <line_snippet>, <channel_content>]
{preloaded content — omit block entirely if nothing to preload}
</post_content>

<resolved_details>
Source: {render_source(...)}
Feedback: {render_freetext(...)}
Guidance: {render_freetext(...)}
</resolved_details>

<recent_conversation>
{compiled convo history — tail is the latest utterance}
</recent_conversation>
```

**Preload what the skill would otherwise re-fetch.** When the starter can carry post content, embed it in `<post_content>` so the skill skips a redundant `read_section` / `read_metadata`. Counter-example: scope-varying flows preload nothing and read at runtime.

### 2. Slot Serialization

Slot-serialization helpers live in `for_pex.py`. Aim for 3-5 helpers total across all flows, not one per slot:

- `render_source` — SourceSlot → `post=<id>, section=<sec_id>` line.
- `render_freetext` — FreeTextSlot → quoted prose.
- `render_checklist` — ChecklistSlot → bullet list.
- `render_section_preview` — per-section title + first-N-line preview.

Helpers strip empty fields, drop internal flags (`ver`), and collapse list wrappers.

**Don't expose the "slots" concept to the LLM.** Render values in `<resolved_details>` with semantic labels (`Source:`, `Feedback:`, `Guidance:`, `Steps:`, `Image:`, `Channel:`, `Schedule:`, `Tone:`, `Topic:`) — never raw slot names. The LLM is in execution mode; grounding is already done by NLU.

### 3. Editorial Conventions for User Content

**XML for content.** XML tags wrap user-supplied or retrieved content the model treats as data (`<user_input>`, `<post_content>`, `<resolved_details>`). Markdown headers (`##`, `###`) belong in system prompt and skill — not in user messages.

**Single blank lines between blocks.** Starter / convo / utterance joined with `'\n\n'.join(segments)`, never double-blanks.

## IV.C — Skill File

### 1. Skill File Structure

`backend/prompts/pex/skills/<flow>.md`. Canonical layout:

```markdown
---
name: <flow_name>
description: <1-sentence purpose>
version: 1
tools: [<list>]
---

[one-line intro: "This skill describes how to X. The relevant content is in the `<...>` block; use it directly."]

## Process

1. Read user guidance from `<resolved_details>` and `<recent_conversation>`.
   a. Only act on the latest utterance — prior turns are context only.
2. <Identify target.>
3. <Do the work.>
4. <Save via the appropriate tool.>
5. End the turn.

## Error Handling

[invalid_input branch + handle_ambiguity branch + tool retry policy]

## Tools

### Task-specific tools

- `tool_name(params)` — description with em dash separator. Sub-bullets call out gotchas.
  * Sub-bullet for nuance.

### General tools

- `execution_error(violation, message)`
- `handle_ambiguity(**params)`
- `manage_memory(**params)`
- `call_flow_stack(action, details)`

## Few-shot examples

### Example 1: <scenario name>

Resolved Details:
- Field: <value>

Trajectory:
1. `<tool_call>` → `_success=True`. End turn.
```

**Conventions inside the skill body:**
- Section headers (`##`)
- Sub-section headers (`###`) use Title Case consistently.
- Bullets (`- `)
- Sub-bullets (`  * `)

### 2. Skill Frontmatter

Every file in `backend/prompts/pex/skills/*.md` starts with YAML frontmatter:

```yaml
---
name: <flow_name>               # matches flow.name()
description: <1-sentence purpose>
version: 1
stages:                         # optional; only if multi-stage
  - propose
  - direct
tools:                          # optional; explicit allowlist
  - find_posts
  - generate_outline
---
```

**Why.** `description` becomes a routing key for future registries. The `tools` field asserts against `flow.tools` to catch skill-registry mismatches at load time. `PromptEngineer.load_skill_template` parses + strips the frontmatter; `load_skill_meta(name)` returns the parsed dict.

### 3. Few-Shot Examples

Per skill: typically 3 scenarios that exercise *different tool paths*, not just different content. Variation is what teaches; redundant scenarios train for the same case.

**Scenario coverage.** Cover normal case + ≥1 edge case (reordering, deletion, malformed input, ambiguity branch). If the flow has an error-handling branch, show it firing.

**Example content.** Pick a realistic post topic that doesn't overlap with the eval set. Use a consistent post ID format (8-char hex) and section names that read naturally.

**Format:**

```markdown
### Example 1: <descriptive scenario name>

Resolved Details:
- Source: post=abcd0123
- Feedback: "..."

Trajectory:
1. <reasoning step or tool call> → `<result>`.
2. `<tool_call>` → `_success=True`. End turn.
```

**Heading is `Resolved Details:` — capital D.** Never `Starter parameters:` or `Resolved details:` (lowercase).

**Scenario setup must agree with the rendered user message.** The scenario's `sec`, `target_section`, `user_text`, content-tag heading, and recent conversation must all agree. A mismatch silently breaks the example.

**Embed example outlines with 2-space indent** under a parent list item — never raw `## Heading` mid-example. Raw headings risk being parsed as new prompt sections.

### 4. Contract Compliance

When a skill's output doesn't parse into the expected shape, the policy returns a `parse_failure` error frame (see Part III.3). Skill authors prevent this through three mechanisms:

**Specify a strict output schema.** If the skill returns JSON, document the exact keys and types in the skill body. If prose, name the format constraints (e.g., "exactly 3 bullets, each starting with a verb"). Schemas embedded in the skill body are reinforcement against drift.

**Reinforce the schema in few-shot examples.** Each example's "Trajectory" should end with the parseable output, demonstrating the contract concretely. Examples that show the right shape are stronger than prose-only specifications.

**Honor the output-budget cap.** A skill capped at 1024 tokens must not be told to produce a 4096-token response — the response will truncate mid-output and surface as `parse_failure`. Match the schema size to the cap (Part II ch. 5).

**Skill-side failure path.** When prevention fails, the policy catches it deterministically:

```python
parsed = self.engineer.apply_guardrails(text, format='json')
if 'findings' not in parsed:
    return DisplayFrame(flow.name(),
        metadata={'violation': 'parse_failure'},
        code=text)
```

`apply_guardrails(text, format='json')` parses-and-fails-closed. Frequent contract violations from a skill mean the skill prompt is broken — not the user's intent.

# Part V — Verifying & Process

## V.A — Verification

### 1. Three-Tier Evaluation

Three tiers with increasing fidelity and decreasing speed. Same rubric keys, asserted at different scope.

| Tier | Location | Speed | Fidelity | What it catches |
|---|---|---|---|---|
| **Tier 1 — policy in isolation** | `utils/tests/policy_evals/ test_<flow>_policy.py` | ~5s per policy | No LLM, mocked tools | Tool-call sequence, frame shape, metadata keys, block types, scratchpad writes, failure-channel branches |
| **Tier 2 — E2E CLI** | `utils/tests/e2e_agent_evals.py` | ~20 min per scenario | Real LLM, persistent disk | Step-by-step lifecycle, inter-flow state propagation, frame→block serialization |
| **Tier 3 — Playwright UI** | `utils/tests/playwright_evals/` | ~10 min | Real browser | UI rendering, click-to-emit payloads, error-frame display |

**Failure dumps.** On any failure, write `utils/policy_builder/failures/<run_id>/step_<N>.md` with: utterance, expected/actual tools and frames, scratchpad state, tool call trajectory. The dump must be sufficient for a fresh Claude instance to debug from cold — no conversation context required.

**Eval-failure-as-success principle.** During harness construction, success means **seeing the tests fail** — that's the signal evals catch what the app breaks on. Mock over early failures so downstream steps run and surface their own failures. Once the harness produces a realistic failure profile, design policies to get everything green.

### 2. Frame Validation

**`_validate_frame` checks values, not just presence.** It asserts that expected values are present on frame blocks (e.g., `card` blocks have `post_id`, `title`, `content` keys), not just that `.blocks` is non-empty.

**`_llm_quality_check` defaults off.** The LLM-as-judge secondary check only runs for flows where prose quality is the entire contract. Per-flow `BaseFlow.llm_quality_check` flag (default False). Override True only when warranted (polish, rework, brainstorm).

**Why.** Deterministic value-checks are cheaper and more reliable than LLM re-verification. Probabilistic verification of probabilistic output is no verification.

### 3. LLM Nondeterminism

Even at `temperature=0`, accuracy swings up to 15% across runs. Don't pretend tests are deterministic when an LLM is in the loop.

**Mitigations:**
- Set `temperature=0` in the agent's eval-mode config.
- Require **2-of-3 successive passes** for "green" on Tier 2 / Tier 3.
- **Retry-with-diagnostic.** Re-run a flaky turn up to 2x; fail only if both runs fail; log the divergence regardless.
- **Eval-level tolerances** for LLM-judge flakes. If a step legitimately bounces between success and `'partial'` ambiguity, set `'expected_ambiguity': {'partial'}` rather than retrying inside PEX.
- Tier 1 (no LLM) is single-run-gatable.

**Common eval mistakes to avoid:**
- Testing prose quality with `assert 'X' in response['thoughts']`. Prose is subjective; use LLM-as-judge sparingly and only for genuinely subjective rubrics.
- Mocking the LLM or content service to avoid setup. Real failures live in the data layer; mocks hide them. Mock only where the tool is irrelevant to the test.
- Asserting exact tool sequences for agentic flows. They have multiple valid trajectories — assert valid outcomes, not exact paths.

### 4. Anti-Patterns to Scan For

Common pitfalls. Each is a specific failure mode the conventions are designed to prevent.

| Anti-pattern | Why it's wrong | Convention |
|---|---|---|
| `text or ''`, `parsed or {}`, `dict.get('key', '')` | Silently converts errors to empty values. Tests pass; prod breaks. | #2 |
| Declaring ambiguity for tool failures | Conflates failure channels. Tool down is not a question for the user. | III.3 |
| Em-dashes in `frame.thoughts` | Hard to parse on small screens; user-facing text. | #10 |
| Inventing new metadata keys | Downstream RES templates silently drop unrecognized keys. | #8 |
| `if post_id and post_id != ''` after NLU resolved it | Defensive checks hide missing contracts. | #1 |
| Hallucinated APIs (`engineer.tools`, `flow.resolved`) | Crashes at runtime; verify imports against the actual module. | CLAUDE.md |
| Both policy and skill writing to disk | Double-persistence causes silent overwrites. | VI.1 |
| `if _legacy_flag: ... else: ...` shims | Doubles code paths; testing twice as complex. Remove old paths cleanly. | — |
| `stage = 'error'` instead of error frames | Stages should reflect genuine control-flow divergence, not cosmetic labels. | AGENTS.md |
| `## Slots` headers in skill files | LLM is in execution mode; grounding is done by NLU. | IV.B.2 |
| Asking for clarification despite all slots filled | Usually means a slot is missing from the flow design. Fix the flow. | #7 |

## V.B — Project Discipline

### 1. Don't Create New Concepts Without Permission

Hard project rule (`CLAUDE.md`). Maintain a single source of truth for the agent's behavior.

**Process when tempted:**
1. Check existing helper functions on the relevant component first.
2. If the behavior isn't there, consider adding a *new function* that accesses data within the existing component.
3. Do NOT create a new component to duplicate data elsewhere.
4. If a genuinely new concept is needed, surface it as a design question before writing code.

**Threshold for promoting a pattern to a helper:**
- ≥3 call-sites AND
- The shape doesn't vary meaningfully across them AND
- The helper contains ≥3 lines (one-liners just add indirection without saving space).

**Common rejected proposals (don't regrow):**
- `BasePolicy.stack_on(...)` helper — belongs in the flow_stack object
- `BasePolicy.guard_slot(...)` — slot semantics vary too much.
- `BasePolicy.complete_with_card(...)` — saves only 3 lines; future variation will diverge.
- `flow.deterministic` flag — implied by the policy code.
- `DialogueState.findings` / `DisplayFrame.findings` attribute — use scratchpad.
- `error_class` parallel taxonomy on metadata — `violation` + `tool_log` covers PEX recovery.
- Cached fields like `active_post_title` — call the service on demand.
- New metadata keys outside the 8-violation vocab.

### 2. Migration Discipline

How to ship large refactors safely.

**Lock shared helpers + conventions BEFORE per-flow rewrites.** Order that works:
1. Pure refactor first (zero behavior change — extract a helper, no signature change).
2. Surface shrink (delete dead code; split conflicting tools).
3. Exemplar rewrites against the new contract.
4. Structured-output fixes + scratchpad writes.
5. Failure-channel work (tool errors, contract violations, ambiguity).
6. Cross-turn channel wiring (producers/consumers).
7. Inline-reason surfaces (stack-on `thoughts`).

Each step validates against the previous one. Reversing the order leads to drift.

**Update test fixtures in lockstep with metadata key changes.** When renaming a key (e.g., `missing_ground` → `missing_entity`), update fixtures in the same commit. Otherwise green tests mask the new bugs the refactor was meant to surface. Grep templates and tests for the old key before the rename.

**Fix root cause; don't chase cascading symptoms.** When N steps fail in a sequence, isolate the first failure. Downstream symptoms often clear automatically once upstream is fixed.

Pattern when many tests fail at once:
1. Isolate the earliest failure with focused re-runs.
2. Hypothesize the upstream fix.
3. Re-run a small slice (steps 1-5) before committing to a full sweep.
4. Don't open separate PRs for cascading symptoms.

### 3. Communication Patterns

**Surface design questions with tradeoff analysis.** Don't just propose a solution; explain why the alternative was rejected. Two-option presentations beat single-option proposals.

**Verify with code, not memory.** When proposing changes, verify assumptions with `git log` / `grep` before writing. Read actual call-sites, not mental models. Hallucinated APIs produce code that crashes at runtime and looks confident in review.

**Land by theme, gate on evals.** Large refactors need waypoints. Don't ship many policy rewrites at once — land by theme (or batch), with validation gates between each. Mid-project, lessons from earlier batches inject into later batch proposals.

---

# Part VI — Reference

## 1. Tool Registry

One canonical tool per CRUD operation per entity. Cite by name; don't extend without approval.

### CRUD × entity grid

| Entity | Create | Read | Update | Delete |
|---|---|---|---|---|
| metadata | `create_post` | `read_metadata` | `update_post` | `delete_post` |
| post outline | `generate_outline` | `read_metadata(include_outline=True)` | `generate_outline` | N/A (use `delete_post`) |
| section outline | `insert_section` (shell) + `generate_section` (body) | `read_section` | `generate_section` | `remove_content` |
| section prose | `insert_section` (shell) + `revise_content` (body) | `read_section` | `revise_content` | `remove_content` |
| snippet | `revise_content(snip_id=int)` | `read_section(snip_id=...)` | `revise_content(snip_id=(start, end))` | `remove_content(snip_id=...)` |
| channel | N/A (configured at app setup) | `channel_status` | `release_post` / `promote_post` / `cancel_release` | N/A |

### Snippet semantics (`snip_id`)

Section content is modeled as an ordered list of sentences. Every snippet-scoped tool accepts:

| `snip_id` | Meaning |
|---|---|
| `None` | Whole section |
| `<int>` | Single sentence at that index (0-based; `-1` is last) |
| `(start, end)` | Slice of sentences, Python-style end-exclusive |

**For `revise_content`:** `snip_id=<int>` inserts at index (pushes existing sentences right; `-1` appends). `snip_id=(start, end)` replaces the range.

**For `remove_content`:** `snip_id=<int>` deletes one sentence. `snip_id=(start, end)` deletes the slice.

**Range rule.** Both endpoints must be non-negative integers in `0 ≤ start ≤ end ≤ sentence_count`. `-1` is never valid as a range endpoint — only as a single-int `snip_id`.

**Source of truth for sentence count.** `read_metadata(post_id)` returns a `sentence_count` per section. Use it before constructing ranges.

### Tool persistence ownership

- **Agentic flows** (skill has tools): the skill owns persistence via `revise_content`, `generate_section`, `generate_outline`. The policy does NOT auto-save.
- **Deterministic flows** (no skill): the policy saves inline via `tools(tool_name, params)`.

Never let both layers write. Double-persistence causes silent overwrites and lost edits.

### Transient helpers (not in the grid)

Wrapped by canonical tools, never standalone:
- `write_text(prompt)` — generate short text fragment; wrap with `revise_content` or `insert_content` to persist.
- `brainstorm_ideas(topic)` — generate angles; wrap with `generate_outline` or `insert_content`.
- `convert_to_prose(bullets)` — bullets → prose; wrap with `revise_content`.

## 2. Quick Reference

| Question | Answer | See |
|---|---|---|
| User's post is missing — how do I signal? | `partial` ambiguity with `missing_entity='post'` | III.3 |
| Skill returned bad JSON — how do I respond? | `apply_guardrails(format='json')` first, then `parse_failure` error frame | III.3 + IV.C ch.4 |
| Tool failed (network down) — how do I respond? | `tool_error` error frame, not ambiguity | III.3 |
| Optional slot is missing — ask or default? | If sensible default exists, commit it. Otherwise, OK to proceed. | II.2 |
| Which tool saves an outline section? | `generate_section` for outline content; `revise_content` for prose | VI.1 |
| How do I pass findings from one flow to another? | Session Scratchpad with `key=flow_name`, fields `{version, turn_number, used_count}` | II.3 |
| Should I call `read_metadata` to load context? | No — NLU already resolved it; use `_resolve_source_ids` or `extra_resolved` | I.A |
| How do I create a `DisplayFrame` with metadata? | Build metadata dict and thoughts first, then one-line instantiation | III.2 #4 |
| What's the outline depth scheme? | Level 0: `# Title`; 1: `##`; 2: `###`; 3: `-`; 4: `  *` | I.C |
| Can I add a new attribute to `DialogueState`? | No. Use the Session Scratchpad for findings; per-turn payload in `frame.metadata` | II.3 |
| Single elective slot — required or optional? | Convert to required (or optional). Single-elective is invalid. | I.A |
| Should I retry on tool failure? | Yes, once via `BasePolicy.retry_tool` if transient. Otherwise return error frame. | III.3 |
| Can my flow self-recurse? | Only if the recursive call hits a non-recursive branch. Outline excepted. | II.4 |
| Can I add a new violation code? | No. The 8-item vocabulary is closed. Surface a design question. | I.C |
| Where do hard rules go — system or skill? | Both. Repeat critical rules in system AND skill. | IV.A.2 |
| Deterministic or agentic flow? | Deterministic if 1 tool + args derivable from slots. Otherwise agentic. | II.1 |
| How do I prerequisite another flow? | `flow_stack.stackon(name)` + `state.keep_going = True` + `frame.thoughts = <reason>` | II.4 |
| What `max_response_tokens` should my flow use? | 1024 short / 2048 single-section / 4096 multi-section prose. Match output schema to cap. | II.5 |
| Where does YAML frontmatter live on a skill? | Top of `backend/prompts/pex/skills/<flow>.md`. | IV.C ch.2 |

---

## Final Notes

This document is a reference, not a rigid checklist. Every policy follows multiple conventions and a shared vocabulary; deviations need an inline comment citing the convention number that justifies them. Goal: consolidation (removing variance that hides bugs), not uniformity for its own sake.

**Update cadence.** As new flows surface lessons that would help future authors, add them to the relevant chapter. If a new lesson contradicts an existing one or conflicts with the canonical specs at `personal_assistants/_specs/`, flag it for review — don't silently override.