# Round 2.11 — Grounding hand-off between flows

Status: **draft for alignment**. Owner modules: **PEX** (policies write grounding at the moments
they learn an entity) + **NLU** (entity references inside group slots resolve to real ids). Builds
on the grounding redesign (commit 1bd3ee3: `state.grounding.entities` is the single source of
truth, `get_active_post` / `set_active_entity` are the accessors) and round 3.2 (the scratchpad
contract; completion records now carry origin + turn_number).

---

## The change in one paragraph

Today a flow that RESOLVES an entity mostly keeps that knowledge to itself: `find` completes
without writing the found post into `state.grounding.entities`, NLU's entity repair skips group
slots so a source slot filled with a TITLE never becomes a post_id in belief, and unverified
references reach sub-agents raw. The result is the observed turn-2 stall: `find` surfaces a post,
then `outline` asks "which post?". This round closes the hand-off: every moment the system truly
learns an entity (a discovery flow narrowing to one post, a user click on a selection, a policy
resolving a reference) writes it to grounding with an honest `ver` flag, and NLU's repair ladder
learns to resolve the `post` part of source-family slots against the real post catalog.

## Evidence

`database/sessions/smoke_20260708_190203/messages.jsonl` (and the same shape in eval traces):

- Turn 1: `find` returns the Roman Concrete draft; its completion record carries only
  `{summary, metadata:{query}}` — nothing lands in `grounding.entities`.
- Turn 2: `outline` arrives with the source slot holding the post TITLE, `ver: false`; the
  sub-agent stalls ("which post or topic should the outline be built around?").
- Turn 3: the same request works once the post_id (`b8a350a3`) appears verbatim in context.

## Current state (verified, with refs)

1. **Only two grounding writers exist.** `resolve_source_ids` writes
   `state.set_active_entity(post=post_id, sec=sec_id or '')` (`policies/base.py:180`) — but only
   flows that call it, at execution time, and WITHOUT `ver`. `outline_policy` sets
   `set_active_entity(post=post_id, sec='', ver=True)` after creating a post (`draft.py:144`).
2. **Discovery flows never write grounding.** `find_policy` (`research.py`) lists matches, writes
   its scratchpad entry, completes — no `set_active_entity`, even when exactly one post matched.
3. **NLU repair skips group slots.** `_repair_entities` handles single-string slots only; source /
   target / removal / channel values "don't go through case-normalization" (`nlu.py:239-243`).
   So the title inside `{'post': 'The Case for Sleepers Over Hotels'}` is never resolved to an id
   in belief, and `ver` stays False.
4. **`ver` is written but almost never read.** `_check_grounding` gates completion on a non-empty
   `grounding.post` (`dialogue_state.py:237`), not on `ver`; no policy opts into the verification
   gate yet (round_3_nlu §3.2.2 says that stays opt-in — unchanged here).

## Target behavior

### 1. Discovery writes grounding when it narrows to one post

`find_policy` (and `browse` when it returns post entities): after the tool result, if exactly ONE
post matched — or the query was an exact title match — write it as the active entity, marked as a
prediction:

```python
# research.py — find_policy, after items are known
if len(items) == 1:
    state.set_active_entity(post=items[0]['post_id'], ver=False)   # predicted, not user-approved
```

Multi-match stays unwritten — the selection block is the user's pick, and the pick is the write.

### 2. A selection click is a verified write

The pick arrives as an action turn; `_fill_slices` already routes `choices` into
`state.grounding['choices']` (`nlu.py:355-364`). When the chosen payload carries a post (the
selection block's option data), the click handler writes `set_active_entity(post=..., ver=True)` —
the user literally pointed at it. This is the one moment `ver` flips True without a policy running.

### 3. NLU resolves the `post` part of source-family slots

Extend `_repair_entities` with a group-slot rung: for slots whose `slot_type` is in
`('source', 'target', 'removal')`, take each value dict's `post` part and resolve it against the
post catalog (`self._posts` is already on NLU — `nlu.py:86`):

```python
# nlu.py — _repair_entities, new branch where non-strings are currently skipped
if slot.slot_type in ('source', 'target', 'removal'):
    for ent in slot.values:
        if ent['post'] and not _looks_like_id(ent['post']):
            post_id, exact = self._resolve_post_reference(ent['post'])   # catalog lookup
            if post_id:
                ent['post'] = post_id
                state.set_active_entity(post=post_id, ver=exact)   # exact title → verified
                if not exact:
                    self.ambiguity_handler.recognize('confirmation', metadata={...})
            # unresolved → leave the title; the policy's resolve_source_ids is the last resort
    continue
```

Rungs mirror the existing ladder: exact title match commits clean (`ver=True`); case/lexical/LLM
matches commit with `ver=False` + a `confirmation` declaration (round_3_nlu §3.2.2 semantics).
`_resolve_post_reference` reads titles via `PostService` (sync lookup, no cached title field).

### 4. `resolve_source_ids` stops dropping `ver`

`policies/base.py:180` writes `post` and `sec` but not `ver`, silently keeping whatever was there.
When the reference resolved by EXACT title/id it should pass `ver=True`; a fuzzy
`_resolve_post_id` hit stays a prediction (`ver=False`). No blanket gate on `ver` — a policy that
cares reads it itself (unchanged, §3.2.2).

## Decisions

### D1 — Where does the discovery write live?

**Recommendation: in the discovery policies themselves** (find/browse), at the single-match
moment. Alternative — centrally in `complete_flow` — rejected: `complete_flow` sees only
`(flow, summary, metadata)`; it doesn't know what the policy resolved, and forcing entity data
into `metadata` just to re-read it is a side channel.

### D2 — Does NLU write grounding at repair time, or only slot values?

**Recommendation: both.** Grounding is belief and NLU owns belief; writing the resolved id only
into the transient flow's slot would leave `grounding.entities` stale until a policy happens to
run `resolve_source_ids`. The `_check_grounding` completion gate then passes for exactly the
right reason: the entity is actually known.

### D3 — What counts as `ver=True`?

**Recommendation: only user-anchored moments** — a selection click (target §2), an exact title/id
the user typed (repair rung 1, resolve_source_ids exact hit), or a confirmed `confirmation`
answer. Every fuzzy/LLM resolution stays `ver=False` with the confirmation declared. Nothing else
flips it.

## Out of scope

- A blanket PEX gate on `ver` (stays opt-in per policy, round_3_nlu §3.2.2).
- `sec`/`snip`/`chl` reference resolution (post first; the section rung follows the same shape
  later).
- Cross-session grounding (MEM territory).

## Verification

1. Unit (free): a `find` single match writes `grounding.entities[0] == {post: id, ver: False}`;
   a selection click flips `ver` True; `_repair_entities` resolves a title-filled source slot to
   the id (exact → `ver=True`, fuzzy → `ver=False` + `confirmation`); `resolve_source_ids`
   passes `ver` through.
2. Live (bounded): rerun the smoke chain (find titled draft → outline) — turn 2 must run without
   the "which post?" stall; then ~3 eval ids that chain Research→Draft (e.g. B02.C03-shape
   conversations) via `run_suite.py --evals --ids ...`.
