# Fix 2 — Add the missing `propose` NLU slot-fill prompt

Status: DONE 2026-07-03 (PR #5). Discovered by the 2026-07-03 evaluation-suite run.
Owner module: **NLU** (slot-fill prompt registry). See also [[step_3_nlu.md]], [[fix_1_orchestrator_activation.md]].

---

## What is being changed

Add a `PROPOSE_PROMPT` entry to `backend/prompts/nlu/revise_slots.py` and register it in that module's
`PROMPTS` dict, so `propose` has a slot-fill prompt like every other live flow. That is the entire change:
one authored prompt entry (four fields) plus one dict key.

## Background and motivation

### The crash

Whenever NLU detects the `propose` flow, the turn crashes:
```
File ".../backend/prompts/nlu/__init__.py", line 35, in get_prompt
    return PROMPTS[flow_name]
KeyError: 'propose'
take_turn crashed: 'propose'
```
- `NLU.think` builds a transient `propose` flow and calls `_fill_slots` (`backend/modules/nlu.py:106`).
- `_fill_slots` calls `build_slot_filling_prompt(flow, ...)` (`nlu.py:391`).
- That calls `get_prompt('propose')` → `PROMPTS['propose']` (`backend/prompts/for_nlu.py:249` →
  `backend/prompts/nlu/__init__.py:34-35`), which raises `KeyError`.
- `agent.take_turn`'s top-level `except` (`backend/agent.py:49-51`) swallows it into the canned
  "Something went wrong on my end. Please try again." fallback.

### Why the gap exists

`propose` is the flow the 48→16 refactor **added** (`ProposeFlow`, `backend/components/flow_stack/
flows.py:285`). The refactor registered it in `FLOW_CATALOG` and `flow_classes`, wrote its PEX skill
(`backend/prompts/pex/skills/propose.md`), and gave it a dax — but never authored its NLU slot-fill
prompt. The registry proves it is the only gap:
```
$ python -c "from backend.prompts.nlu import PROMPTS; from schemas.ontology import FLOW_CATALOG; \
  print(sorted((set(FLOW_CATALOG)-{'plan','clarify'}) - set(PROMPTS)))"
['propose']
```
Every other flow (`research_slots`, `draft_slots`, `revise_slots`, `publish_slots`, `converse_slots`,
`nlu/__init__.py:19-27`) has an entry; `revise_slots.py` currently exports `rework`, `write`, `audit`
(`revise_slots.py:821-825`) but not `propose`.

### Why it matters

- **It is a hard crash**, not a soft miss: every `propose` turn dies. In the traces run it surfaced twice
  directly (`B01.C04 turn 3` crashed; `B03.C01 turns 3-4` fell to the crash fallback).
- `propose` is a normal, expected flow (generate 2–3 alternatives for a placeholder gap; the "options+
  select" arc leans on it). It will keep being detected, so it will keep crashing until the prompt exists.
- This is the cheapest high-severity fix in the suite: one authored entry, no design decisions.

## Connected files

| File | Role |
|---|---|
| `backend/prompts/nlu/revise_slots.py:821-825` | `PROMPTS` dict for the Revise intent — add `'propose'` here |
| `backend/prompts/nlu/__init__.py:19-31` | merges every intent module's `PROMPTS`, then filters to live flows |
| `backend/prompts/for_nlu.py:248-285` | `build_slot_filling_prompt` — consumes the four authored fields |
| `backend/components/flow_stack/flows.py:285-301` | `ProposeFlow` — the slots the prompt must cover |
| `backend/modules/nlu.py:59-72` | `_fill_slots_schema` — derives the output schema from `flow.slots` |
| `utils/tests/nlu_unit_tests.py` | `test_prompt_slot_headings_match_flow_slots`, `test_few_shot_example_keys_match_flow_slots` — the lints that will police this entry |

## The flow being filled

`ProposeFlow` (`flows.py:285-301`) declares exactly two slots:
```python
self.slots = {
  'source':  SourceSlot(1, 'sec'),         # required — the section holding the placeholder gap
  'context': FreeTextSlot(priority='optional'),  # optional — user guidance on what should fill the gap
}
self.tools = ['read_metadata', 'read_section', 'revise_content']
```
So the authored prompt only needs to cover `source` (required, entity part `sec`) and `context`
(optional). `fill_slot_values` (`flows.py:297-301`) reads `values['source']` (list of entity dicts) and
`values['context']` (list of strings).

## The change (fully specified stub)

Add to `backend/prompts/nlu/revise_slots.py`, then extend the module's `PROMPTS`:

```python
PROPOSE_PROMPT = {
    'instructions': (
        "The Propose Flow fills a specific placeholder gap in existing content — a `<fill in here>`, a "
        "TODO, or a blank slot inside a section — by generating 2-3 targeted alternatives for the user to "
        "pick. It is like Brainstorm, but scoped to ONE spot in a draft rather than the whole post.\n\n"
        "Extract `source` (the section that contains the gap; usually inherits the post from active_post) "
        "and, when the user gives direction on what the gap should contain, `context` (their guidance, "
        "captured verbatim). When the user only points at the gap with no direction, leave `context` null."
    ),
    'rules': (
        "1. `source` names the SECTION holding the gap. Fill `sec` when the user names a section ('the "
        "intro', 'the methods section'); `post` inherits from active_post unless the user names a "
        "different post. A bare 'fill in the blank here' with a grounded active post fills source from "
        "grounding and leaves `sec` for the policy to resolve.\n"
        "2. `context` (optional) captures the user's direction for the gap verbatim — 'something about "
        "cost savings', 'a concrete example'. Vague pointers with no direction ('finish this', 'fill it "
        "in') leave `context` null so the flow proposes from the surrounding content alone.\n"
        "3. Treat propose directives as current-turn-only; prior-turn direction is assumed applied. "
        "`source` is the exception — it carries forward from `state.active_post`."
    ),
    'slots': '',   # empty → procedural rendering from flow.slots (for_nlu.py:266); source+context are simple
    'examples': '''<positive_example>
## Conversation History

User: "Fill in the placeholder in my sleeper-trains post's comfort section — lead with the overnight time saved."

## Input
Active post: None

## Output

```json
{
  "reasoning": "User points at a gap in a named section (comfort) and gives direction (overnight time saved). source fills post+sec; context captures the direction verbatim.",
  "slots": {
    "source": {"post": "sleeper-trains", "sec": "comfort"},
    "context": "lead with the overnight time saved"
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "There's a TODO in the intro — give me a couple options for it."

## Input

Active post: **The Case for Sleepers Over Hotels** (id: `9f8e7d6c`)

Filled slots are shown as part of the input; slots not shown are empty so far.
source slot: {"post": "9f8e7d6c", "sec": "", "snip": "", "chl": ""}

## Output

```json
{
  "reasoning": "Active post is grounded — copy post_id verbatim from the source slot. Section named (intro). No direction on what the TODO should say → context null.",
  "slots": {
    "source": [{"post": "9f8e7d6c", "sec": "intro"}],
    "context": null
  }
}
```
</positive_example>

<edge_case>
## Conversation History

User: "Fill in the blank."

## Input
Active post: My RL Primer

## Output

```json
{
  "reasoning": "Bare gap pointer with a grounded active post and no section or direction. source inherits the post; sec stays for the policy to resolve from the placeholder location; context null.",
  "slots": {
    "source": {"post": "My RL Primer"},
    "context": null
  }
}
```
</edge_case>''',
}
```
And extend the export at `revise_slots.py:821-825`:
```python
PROMPTS = {
    'rework':  REWORK_PROMPT,
    'write':   WRITE_PROMPT,
    'audit':   AUDIT_PROMPT,
    'propose': PROPOSE_PROMPT,   # ← add
}
```

## Big-decision notes

Small change, but two choices worth recording:

- **Procedural vs. hand-authored `## Slots` section.** `build_slot_filling_prompt` renders slot headings
  procedurally from `flow.slots` when the `'slots'` field is empty (`for_nlu.py:263-266`). `propose` has
  only two simple slots, so an empty `'slots': ''` is the lazy correct choice — it stays in sync with the
  flow automatically and can never drift out of the heading lint. Hand-author a `## Slots` block only if a
  later change needs per-slot extraction nuance the procedural render can't express.
  - Pro (procedural): cannot drift from `flow.slots`; less to maintain.
  - Con (procedural): no room for slot-specific guidance beyond the rules field — acceptable here.

- **Do NOT reference a `ver` field** in the prompt or examples. `ver` is set by the grounding layer, never
  predicted by NLU (`feedback_entity_slot_rule`, MEMORY grounding notes). The examples above omit it.

## New concepts introduced

**None.** This adds one entry to an existing registry using the existing four-field contract
(`nlu/__init__.py:4-13`). No new field, key type, component, or mechanism.

## How to verify

1. **Import + registry:**
   `python -c "from backend.prompts.nlu import PROMPTS; print('propose' in PROMPTS)"` → `True`.
   The gap query above now prints `[]`.
2. **Lints (deterministic, free):** `python utils/evals/run_evaluation_suite.py --tests nlu` stays green —
   in particular `test_prompt_slot_headings_match_flow_slots` and `test_few_shot_example_keys_match_flow_slots`
   (`nlu_unit_tests.py`) now cover `propose`. With `'slots': ''` the heading lint skips procedural flows,
   so it passes; the example-keys lint checks the fenced-JSON `slots` keys ⊆ `{source, context}` — the
   stub obeys this.
3. **No crash, live:** rerun the two scenarios that crashed —
   `python utils/evals/run_evals.py --ids B01.C04,B03.C01` — and confirm no `KeyError: 'propose'` and no
   `Something went wrong on my end` fallback on the propose turns.
4. **Detection sanity (paid, bounded):** `python utils/tests/model_tests.py --module nlu` on the standard 8
   no longer errors on any propose turn; the propose turn either matches or is a normal near-miss, not a crash.
5. Full deterministic suite stays green (208): `python utils/evals/run_evaluation_suite.py --tests`.
