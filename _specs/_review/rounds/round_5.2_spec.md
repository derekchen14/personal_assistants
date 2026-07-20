# Round 5.2 — One Tool Surface: manage_flows / scratchpad / handle_ambiguity Everywhere

Maps to **Master Plan · Round 5 (Plan)** — managing the stack is workflow planning. DRAFT;
builds on [round 2.16](round_2.16_spec.md) and starts only after it lands (it uses the 2.16
names: `orchestrate()`, `execute()`, `call_tool`). Line refs cite pre-2.16 pex.py and will
shift.

Today the orchestrator and the policy sub-agents reach the same components through
differently-named tools: two flow tools next to `manage_flows`, two scratchpad tools, two
ambiguity tools, and four differently-shaped policy results. This round makes both loops re-use
one tool surface, with level-specific behavior expressed as one rule per tool — never a separate
tool.

Rulings recorded up front (2026-07-19):

- **One flow tool, one scratchpad tool, one ambiguity tool** — shared by both loops. A
  sub-agent and the orchestrator see the same names, schemas, and descriptions.
- **Level differences are rules, not gates**: the only behavioral split is WHO runs newly
  surfaced work — the orchestrator's `manage_flows` runs it inline via `execute()`; a
  sub-agent's `manage_flows` defers it to the PEX layer (no fourth level — already the standing
  rule for stacked-on flows).
- **One result shape** for every policy run, success or failure — the agent and the prompt docs
  describe exactly one payload.

---

## 5.2.1 — One flow tool: `manage_flows` at both levels

Delete the sub-agent-only pair — `stackon_flow` / `fallback_flow` (methods pex.py:492-498,
tool definitions pex.py:904-927) — and put `manage_flows` in the sub-agent toolset instead
(`_component_tool_definitions`). Same ops, same schema, same description at both levels.

The one level rule: when a `manage_flows` op surfaces runnable work (stackon, fallback, a
promoting pop, `update status='Active'`),

- called from the **orchestrator loop** → `execute()` runs the new flow inline; the policy
  result is the tool result (2.16 behavior, unchanged);
- called from **inside a policy run** → no inline run. The flow lands on the stack and
  re-surfaces at the PEX layer; the agent runs it on a later round. This closes a latent hole:
  today `_tool` already routes `manage_flows` (it sits in `_orchestrator_toolset`,
  pex.py:446-447), so a sub-agent that guessed the name could recurse into a fourth level.

Wiring without a new flag: `execute()` hands sub-agents a callable whose `manage_flows` routes
to the defer variant — the level is carried by which callable you were given, not by state.

## 5.2.2 — One scratchpad tool + one stamping site

Replace `read_scratchpad` (definition pex.py:871-887, method pex.py:759-761) and
`append_to_scratchpad` (definition pex.py:1071-1084, method pex.py:763-771) with a single
`scratchpad` tool, ops `read` / `append` — the shape the pex.md tool catalog has documented all
along. Both loops get it.

Stamping dedup: the contract fields `{version, used_count}` are hand-written at four sites —
`_append_scratchpad` (pex.py:767-770), `_save_findings_tool` (pex.py:522-529),
`complete_flow` (base.py:223-227), and the synthesized completion entry in `activate_flow`
(pex.py:714-719). `SessionScratchpad.append_entry` stamps them itself; `turn_number` stays the
caller's field (every caller holds the context, the scratchpad does not).

## 5.2.3 — One ambiguity tool: `handle_ambiguity`

Replace `declare_ambiguity` (definition pex.py:819-845, method pex.py:500-508) and
`ask_clarification_question` (definition pex.py:1101-1110, method pex.py:778-785) with the
`handle_ambiguity` tool pex.md already describes, ops `declare` / `ask`. The per-level metadata
validation (`_validate_ambig_metadata`, pex.py:63-83) moves under op='declare' unchanged;
op='ask' keeps NLU as the author of the question. The other two methods stay code-side:
`is_present` is a property read, `resolve` is NLU's move on the answer turn — neither is a tool.

## 5.2.4 — One result shape from `execute()`

`activate_flow` today returns four shapes: approval_required, execution_error / validation
failure, non-completed (status + question), and completed (completion + popped + next_flow) —
pex.py:689-741. Replace with a single result builder so every policy run returns:

```python
{'_success': bool, 'status': str, 'thoughts': str, 'blocks': list,
 '_error': str, '_message': str,          # failure only
 'question': str,                         # a pending clarification, else ''
 'completion': dict, 'popped': list, 'next_flow': dict}   # completion only, else absent
```

The `manage_flows` tool description and the orchestrator system prompt then document exactly
one payload. Field names and semantics are unchanged — the round only adds the guarantee that
they always arrive in the same flat dict.

## Todo list

- [ ] **T1 — manage_flows at both levels**: add it to `_component_tool_definitions`; delete
  `stackon_flow` / `fallback_flow` (methods + definitions); implement the defer rule via the
  callable handed to sub-agents (5.2.1). Update the sub-agent-facing description to state the
  defer behavior plainly.
- [ ] **T2 — scratchpad tool**: one definition with ops read/append replacing the two tools;
  `append_entry` stamps `{version, used_count}`; delete the four hand-stampings (5.2.2).
- [ ] **T3 — handle_ambiguity tool**: ops declare/ask replacing the two tools; metadata
  validation under declare; `is_present` / `resolve` stay code-side (5.2.3).
- [ ] **T4 — one result builder** in `execute()` per 5.2.4; update the `manage_flows`
  description and for_orchestrator.py to document the single shape.
- [ ] **T5 — prompt/skill sync**: sweep `backend/prompts/pex/skills/*.md`, starters, and
  support prompts for the deleted tool names (`stackon_flow`, `fallback_flow`,
  `declare_ambiguity`, `read_scratchpad`, `append_to_scratchpad`) and rewrite to the merged
  names; grep to zero before done.
- [ ] **T6 — tests**: update `pex_unit_tests.py` call sites and any fixtures naming the old
  tools (moratorium: update or delete only). Run the three test files from the Hugo dir.
- [ ] **T7 — verification**: commit first; one live probe turn where a sub-agent stacks a
  prerequisite through `manage_flows` and the flow re-surfaces (the defer rule); replay gate
  canaries B03.C14 and B01.C13 — completion no worse than baseline; restore `database/content`.

## Out of scope

- `understand` op='think' (documented in pex.md's catalog, still unwired) — separate decision.
- `call_mcp` implementation (carried from 2.16's out-of-scope).
- Any change to which ops exist on `manage_flows` — this round moves surfaces, it does not
  redesign them.
