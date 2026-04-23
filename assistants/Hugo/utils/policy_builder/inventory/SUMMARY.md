# Policy Inventory — Summary

Cross-flow patterns observed across the 12 inventoried policies + skills. Each theme lists the inventory files that evidence it so Part 3 can back-reference concretely.

## Theme 1 — Skill/policy contract confusion

The boundary between what the deterministic policy owns vs. what the LLM sub-agent is asked to do is muddled in most flows. Work gets done twice, or the skill describes behavior the policy silently bypasses.

- `create.md` — skill describes title-formatting and "generate brief initial outline" behavior that the policy never invokes; policy calls `create_post` directly without ever running `llm_execute`. The skill is documentation for a code path that does not exist.
- `find.md` — skill tells the LLM to "expand query with synonyms and run 3 queries," but the policy has already done the grounding. Skill can't tell whether to fetch or just format.
- `simplify.md` — skill says "policy saves automatically," but both the policy (`_persist_section`) AND the skill (calls `revise_content` in few-shot) write to disk; potential double-write.
- `compose.md` — same double-persist pattern: policy calls `_persist_section` after `llm_execute`, but the skill's own few-shot example loops over sections and calls `revise_content` each. Final-text ownership is ambiguous.
- `refine.md` — both the policy (line 110) and the skill (line 6) call `read_metadata` to load the outline.
- `rework.md` — `read_metadata` allowed in the skill's tool list even though the policy has already grounded source.

**Implication for Part 3:** need a clear rule — "resolved context is source of truth; skills do not re-ground" — and a decision for every flow on which layer owns persistence.

## Theme 2 — Unexemplified slots

Many slots are declared on the flow class (and therefore exposed to NLU) but have no example in the skill's few-shot, so the sub-agent has no idea what to do with them when NLU fills them.

- `rework.md` — `suggestion`, `remove` slots unexemplified
- `simplify.md` — `image`, `guidance` unexemplified
- `polish.md` — `style_notes`, `image` unexemplified
- `add.md` — `points`, `additions`, `image` — few-shot is focused on the wrong case (new top-level sections) rather than detail-into-existing (which is the actual semantics per `ADD_PROMPT`)
- `outline.md` — `depth` slot defined in the schema but used nowhere in policy or skill

**Implication for Part 3:** every declared slot needs at least one few-shot example OR should be removed. A declared-but-unused slot is always a silent bug.

## Theme 3 — Output-shape drift

The final turn from a skill frequently doesn't match what downstream (policy post-processing, template rendering, or later eval steps) expects.

- `audit.md` — returns post content in the card block instead of a structured style report (AGENTS.md § "Known e2e quality gaps" confirms). Findings are buried in `thoughts`.
- `inspect.md` — skill specifies a JSON metrics output, but the policy accepts raw LLM text. No structural enforcement → step 13 polish cannot parse reliably from the scratchpad.
- `find.md` — list block lacks post metadata (status, outline) that downstream audit needs, forcing re-fetches.
- `create.md` — skill specifies a JSON output shape, but policy ignores it (policy uses the tool result, not the skill's return).

**Implication for Part 3:** every skill needs a strict output schema, and the policy must parse-and-fail-closed on bad shapes.

## Theme 4 — Error-path gaps

Happy paths are mostly covered; error/ambiguity paths are not.

- `release.md` — eval expects `channel_unavailable` ambiguity, but policy doesn't catch/route platform failures there. Worse: post status flips to `published` on disk even when `release_post` fails → stale state.
- `audit.md` — silent escalation: when audit finds issues, policy returns empty frame + confirmation ambiguity without showing the findings first.
- `refine.md` — `generate_outline` overwrites the full outline instead of appending (AGENTS.md-flagged known gap); skill says "append not replace" but few-shot only shows a single case.
- `outline.md` — propose-mode constraint "MUST NOT call generate_outline" is enforced only by LLM compliance; the graceful-fallback in policy (line 86) covers it at runtime but doesn't fix the upstream contract.

**Implication for Part 3:** every policy's `# Ambiguity patterns` section needs expansion, and `state.has_issues` / frame metadata should carry the failure so users see something actionable.

## Theme 5 — Downstream-consumption blockers for step 13 polish

The new 14-step sequence has `inspect → find → audit → polish` as a chain where step 13's polish is supposed to ingest the findings of 10/11/12. Today nothing in the policy layer makes that possible.

- `polish.md` — current policy treats step 9 (basic) and step 13 (informed) identically. Resolved context doesn't carry prior-step findings.
- `inspect.md` — unstructured text output; downstream can't parse metrics.
- `find.md` — list block too thin; audit and polish can't cite specific prior posts.
- `audit.md` — findings buried in `thoughts`; downstream polish can't retrieve them.

**Resolved (AD-1 + AD-2):** cross-turn channel = scratchpad with key convention (`key=flow_name`, required fields `version` / `turn_number` / `used_count`). No new `DialogueState` / `DisplayFrame` attributes. No "informed" stage on polish — the skill always reads conversation history + scratchpad and behaves accordingly.

## Theme 6 — Stack-on and recursion risk

- `outline.md` — recursion on proposal selection (lines 56-60 in draft.py); infinite loop risk if `proposals` slot doesn't clear after one iteration.
- `compose.md` — stack-on `outline` when sections missing. Works, but the transition is opaque to the user.
- `refine.md` — stack-on `outline` when bullets missing.

**Implication for Part 3:** stack-on ergonomics deserve a helper (`self.stack_on(name, state)` that sets `keep_going`) and clear documentation of when the user sees the sub-flow exit vs. when it's chained silently.

## Theme 7 — Repeated guard-clause and tool-log patterns

Observed near-verbatim in almost every policy (see inventory files for line refs):

- `if not flow.slots[<slot>].check_if_filled(): self.ambiguity.declare(...); return DisplayFrame()` — candidate for `self.guard_slot(flow, slot_name, level)`
- `[tc for tc in tool_log if tc.get('tool') == X]` + success-check — candidate for `self.engineer.tool_succeeded(tool_log, name)`
- `flow.status = 'Completed'; frame = DisplayFrame(origin=X); frame.add_block({'type': 'card', ...})` — candidate for `self.complete_with_card(flow, post_id, tools)`
- `self.flow_stack.stackon('outline'); state.keep_going = True; return DisplayFrame()` — candidate for `self.stack_on('outline', state)`

**Implication for Part 3:** `fixes/_shared.md` should extract these helpers with line-refs to every call-site they replace.

## Per-flow headline gap (one sentence each)

| Flow | Headline gap |
|---|---|
| create | Skill is dead code — policy never invokes it |
| outline | Propose-mode constraint is LLM-trust-only; `depth` slot unused |
| refine | Append-vs-overwrite regression (AGENTS.md gap) |
| compose | Double-persistence risk (policy + skill both write) |
| rework | Suggestion/remove slots unexemplified; scope creep in goal vs. entity_part |
| simplify | Dual-slot guard + unclear persistence contract |
| add | Skill few-shot focuses on new-section case, contradicting flow goal |
| polish | No difference between basic (step 9) and informed (step 13) policy branches |
| inspect | Unstructured output → downstream can't consume |
| find | Sparse list-block metadata → downstream re-fetches |
| audit | Card block shows post content instead of findings (AGENTS.md gap) |
| release | `channel_unavailable` not handled; stale-state on failure |

## Top three cross-cutting priorities for Part 3

1. **Skill/policy ownership rules** — one written contract (grounding, persistence, output shape) applied to all 12 flows.
2. **Cross-turn findings channel** — scratchpad convention (AD-1) unblocks step 13 polish and any future chained flow.
3. **Shared helpers** — extract the guard-clause / tool-log / stack-on / complete-with-card patterns before per-flow rewrites so fixes don't drift.
