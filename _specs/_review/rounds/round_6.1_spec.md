# Round 6.1 — Context Unification: One History, Six Turn Kinds

Maps to **Master Plan · Round 6 (Infra)**. Design spec — evidence is the 2026-07-19 design
discussion, not an eval run. The Context Coordinator currently keeps two overlapping stores:
`_history` (human-readable `Turn` objects) and `messages` (the API-shaped PEX transcript, mirrored
to `messages.jsonl`). This round merges them: **history becomes the single source of truth and the
API message list becomes a projection computed from it.** The double-entry writes in `take_turn`
disappear, restarts restore the full record instead of only the model transcript, tool calls get
turn positions, and compaction becomes non-destructive.

Rulings recorded up front:

- **Option 1 chosen**: history stores everything; `messages` is derived, rather than written directly.
- **Six turn kinds** — the 2×3 grid of `turn_type` (utterance, action) × `role` (user, agent,
  system). No other turn_type values: the live `'checkpoint'` (mem.py:55) and `'system'`
  (world.py:45) values migrate into the grid.
- **Speaker vs actor.** The field is `role` in both cases; the vocabulary depends on `turn_type`:
  on an utterance the role is a **speaker** (someone said something), on an action the role is an
  **actor** (someone did something). Prose, docstrings, and specs use whichever word matches.
- **The merge must net-delete code.** A single source of truth is only won if the two-store
  plumbing goes with it; the tally in 6.1.5 is part of the round's definition of done.
- **Checkpoint is a system activity, not a turn_type.** Vocabulary: a *snapshot* is a passive copy
  of state at a moment (what `state.json` is); a *checkpoint* is a **named marker at a position in
  the stream** that can be returned to by label. A checkpoint stores `{label, turn_id, data}` and
  never a copy of history — "history as of the checkpoint" is the slice of turns up to its
  position, so the old `history_snapshot` field is dropped and the store holds no recursive
  copies of itself.
- **Kind 3 (`agent`/`utterance`) is the final reply only.** Mid-loop assistant text rides inside
  kind 4, so MEM recap and the frontend keep an unambiguous "the reply" turn.
- **One kind-4 turn per loop round**, holding the round's text plus tool_use AND tool_result
  blocks together — the pair can never be separated, which is what makes compaction alignment
  free (see 6.1.4).

---

## 6.1.1 — The turn taxonomy

Every turn is `{role, turn_type, content, turn_id, timestamp}` — nothing else; revisions are
append-only activities, not Turn fields (ruled 2026-07-19, replacing `is_revised`/`original`).
`content` is a dict whose shape is fixed per kind. `turn_id` keeps its
current semantics: the utterance counter, stamped as-is on non-utterance turns so a turn's tool
traffic and reply share the position of the exchange they belong to.

| # | role | turn_type | content | holds |
|---|---|---|---|---|
| 1 | user | utterance | `{text}` | the message the user typed |
| 2 | user | action | `{dax, payload, text}` | a click; `text` filled when typed alongside |
| 3 | agent | utterance | `{text}` | the final reply PEX produced this turn |
| 4 | agent | action | `{tool_uses, tool_results, text}` | one PEX loop round |
| 5 | system | utterance | `{text}` | compaction summaries, nudges, wrap-ups, [nlu]/[contemplate] notes |
| 6 | system | action | `{activity, result, text}` | compaction events, checkpoints, revisions, session start |

**Every content dict carries `text`** — the invariant that lets `utt()`, log lines, and every view
render `content['text']` with no per-kind branching. On kind 6 it is the human-readable one-line
rendering of the activity; on kind 2 and kind 4 it may be empty but is always present.

Concrete examples of all six:

```python
# 1 — user utterance
{'role': 'user', 'turn_type': 'utterance', 'turn_id': 4,
 'content': {'text': 'Rework the intro of the datacenters draft'}}

# 2 — user click (a selection from grounding choices; the run button sends
#     payload={'fields': {'status': 'Active'}} in the same shape)
{'role': 'user', 'turn_type': 'action', 'turn_id': 6,
 'content': {'dax': '{001}', 'text': '',
             'payload': {'kind': 'post', 'label': 'Energy Needs of Datacenters',
                         'entity': {'post': '8a9b0c1d', 'sec': '', 'snip': '', 'chl': '',
                                    'ver': True}}}}

# 3 — the final reply (written once, by MEM's recap)
{'role': 'agent', 'turn_type': 'utterance', 'turn_id': 5,
 'content': {'text': 'I restructured the intro around the cooling-costs argument. '
                     'Want to read the new opening?'}}

# 4 — one loop round: the round's text plus its tool traffic, results attached to their calls.
#     A text-only round (e.g. the superseded reply before a contemplate re-entry) has empty lists.
{'role': 'agent', 'turn_type': 'action', 'turn_id': 5,
 'content': {'text': 'Reading the current intro first.',
             'tool_uses': [{'type': 'tool_use', 'id': 'toolu_01', 'name': 'read_section',
                            'input': {'post_id': '8a9b0c1d', 'section': 'intro'}}],
             'tool_results': [{'type': 'tool_result', 'tool_use_id': 'toolu_01',
                               'content': '{"_success": true, "text": "Data centers now..."}'}]}}

# 5 — system steering text (also: the compaction summary, _NUDGE_MESSAGE, _WRAP_UP_MESSAGE,
#     '[contemplate] NLU re-routed the flow...')
{'role': 'system', 'turn_type': 'utterance', 'turn_id': 5,
 'content': {'text': '[nlu] Stacked rework for the newest message. Live stack (top first): '
                     'rework·Active | chat·Pending. Decide with manage_flows...'}}

# 6 — system activities: checkpoint and compaction (see 6.1.4 for the compaction pair)
{'role': 'system', 'turn_type': 'action', 'turn_id': 5,
 'content': {'text': 'completed: rework | active: none | post: 8a9b0c1d',
             'activity': 'checkpoint',
             'result': {'label': 'turn_wrap', 'turn_id': 5,
                        'data': {'completed': ['rework'], 'active': None, 'post': '8a9b0c1d'}}}}
{'role': 'system', 'turn_type': 'action', 'turn_id': 12,
 'content': {'text': 'Compacted turns 3-41 into a summary.',
             'activity': 'compaction',
             'result': {'start': 3, 'cut': 41, 'summary_index': 57, 'before': 58, 'after': 21}}}
```

## 6.1.2 — Writer and reader inventory (the full scan)

Every site that writes either store today, and the kind it writes after the merge:

| Site | Today | Becomes |
|---|---|---|
| assistant.py:46 `add_turn('User', ...)` | text-only Turn | kind 1, or kind 2 when `dax` (carries payload+text) |
| assistant.py:62 `append_user_message` | duplicate message write | **deleted** — decoration moves into the projection |
| assistant.py:80-91 contemplate re-entry | assistant + user messages | kind 4 (text-only, the superseded reply) + kind 5 (the note) |
| assistant.py:88 final-reply append | duplicate message write | **deleted** — MEM's kind-3 write covers it |
| assistant.py:111 fallback reply | Agent Turn | kind 3 |
| world.py:45 `'Session started.'` (`turn_type='system'`) | stray turn_type | kind 6 `activity='session_start'` |
| mem.py:37 recap's agent turn | Agent Turn | kind 3 (the single writer of the final reply) |
| mem.py:55 turn-wrap checkpoint (`turn_type='checkpoint'`) | stray turn_type | kind 6 `activity='checkpoint'` |
| pex.py:350-351 interim text + [nlu] note | two messages | kind 4 (text-only) + kind 5 |
| pex.py:357 `_NUDGE_MESSAGE` | user message | kind 5 |
| pex.py:363 + :384 tool blocks + results | two messages | **one** kind 4 per loop round |
| pex.py:397 `_WRAP_UP_MESSAGE` | user message | kind 5 |
| pex.py:450 `[tool:{name}]` history turn | second recorder of tool traffic | **deleted** — redundant with kind 4 |
| context_coordinator.py:196 `save_checkpoint` | `_checkpoints` dict with `history_snapshot` | kind 6 `activity='checkpoint'`, no snapshot copy |
| context_coordinator.py:193 compaction handoff | spliced message | kind 5 summary + kind 6 event (6.1.4) |
| context_coordinator.py:307 `add_actions` | dead (no callers) | **deleted**, with `last_actions` |

Readers, and what changes for each:

- **pex.py:337, :398** — `context.messages` becomes `context.compile_messages()`, the on-demand
  projection (6.1.4); the stored `messages` list is deleted.
- **full_conversation** — becomes the raw all-kinds view. Today it filters on speaker only
  (context_coordinator.py:109-117), so `[tool:]` action turns leak into `compile_history` output
  despite the docstring saying "all utterance turns"; under the merge the utterance filter moves
  into `compile_history` itself, where it belongs.
- **compile_history / recent** — `compile_history` filters kind 1/3 (kind 5 on `keep_system`);
  `recent` folds into it as a filter rather than surviving as a parallel rolling list.
- **get_checkpoint** (context_coordinator.py:137, exposed as a PEX tool at pex.py:502) — scans
  history in reverse for kind-6 checkpoint turns matching the label; the tool surface is
  unchanged.
- **last_user_text / last_user_turn** — `role == 'user'`, read `content['text']`.
- **trace_writer.py:110** — reads `messages.jsonl`; repoint to `history.jsonl` and derive the
  transcript view from the turn kinds.
- **mem_unit_tests.py** compaction and checkpoint suites — update in place (moratorium: no new
  tests; existing ones are updated or deleted).

Dead surfaces found by the scan, no callers anywhere: `add_actions`/`last_actions` (deleted with
this round — kinds 4/6 supersede them), and `Turn.action_target`, `rewrite_history`,
`contains_keyword` (flagged for Derek's call; not deleted by default).

Found mid-migration state: `Turn` already carries `role` (context_coordinator.py:24-25) but
`add_turn` and four readers still say `.speaker` (`full_conversation`:114, `last_user_text`:275,
`last_user_turn`:282, `rewrite_history`:291) — currently inconsistent; T1 finishes the rename.

## 6.1.3 — Storage: history.jsonl replaces messages.jsonl

One file per session, one turn per line, append-only. `attach_messages` becomes `load_history`
(world.py:61) — *load*, because it binds the path and replays the file; not `load_checkpoint`,
because a checkpoint is a named marker in the stream and this loads the whole stream. An existing
file rebuilds the turn list and `num_utterances`; a fresh path stays lazy and the first write
flushes the in-memory seed turn, so disk matches memory from then on. The file is **strictly
append-only**. A user-utterance revision follows the compaction pattern (ruled 2026-07-19) — a
kind-5 turn holds the revised text, a kind-6 `revision` event `{target, revised_index}` points
the views at it, and the original turn is unchanged; with `rewrite_history` deleted (T12) the
pattern is designed-not-built until a writer needs it. `state.json` and `scratchpad.jsonl` are
untouched; architecture.md's Disk Storage section updates its third file from `messages.jsonl`
to `history.jsonl`.

## 6.1.4 — The projection and the three read surfaces

The coordinator exposes three reads, one per consumer; nothing else walks `_history` directly:

- **`full_conversation()`** — every turn, all six kinds, in order. For traces, debugging, and
  checkpoint slicing.
- **`compile_history(look_back)`** — kind 1 and kind 3 rendered `role: text` (kind 5 included
  when `keep_system=True`). For NLU and expert prompts; output variable stays `convo_history`.
- **`compile_messages()`** — the API projection for the PEX agent's model calls, **computed on
  demand each call** — there is no stored `messages` list, no mirror to keep consistent, and no
  rebuild step on resume. Re-rendering the turns is dict assembly, trivial next to the LLM call
  it feeds. pex.py:337 and :398 change from `context.messages` to `context.compile_messages()`.

Per-kind rendering inside `compile_messages()`:

| Kind | API messages emitted |
|---|---|
| 1 | one `{'role': 'user', 'content': text}` |
| 2 | one user message carrying the `[click]`/`[action]` decoration built from dax + payload + text (moved here from `append_user_message`) |
| 3 | one `{'role': 'assistant', 'content': text}` |
| 4 | one assistant message (text block + tool_use blocks); plus one user message with the tool_result blocks when `tool_results` is non-empty |
| 5 | one `{'role': 'user', 'content': text}` |
| 6 | nothing — activities are invisible to the model; the compaction event controls the splice |

Tool-result pruning becomes a **rendering rule instead of stored state**: when a kind-4 turn sits
older than the protected tail, results over `_PRUNE_MIN_CHARS` render as the placeholder. This
deletes `_prune_tool_results` and the mirror-consistency rewrite; disk keeps the full results,
which the trace tier wants anyway.

**Compaction** appends two turns and touches nothing else: a kind-5 turn holding the summary, then
a kind-6 event `{'text': ..., 'activity': 'compaction', 'result': {start, cut, summary_index,
before, after}}`
where `start`/`cut` are history indices bounding the compacted region and `summary_index` points
at the kind-5 turn. The projection replays the event by emitting the summary at the splice point
and skipping turns in `[start, cut)` plus the summary turn at its own position. Because a kind-4
turn holds its calls and results together, the region boundary can never separate a pair —
`_align_forward` and `_align_backward` are deleted; `_anchor_last_user` survives as a simple
index computation over turns (the newest kind-1 turn stays out of the region). `previous_summary`
seeds from the newest kind-5 summary turn on resume, replacing the `SUMMARY_PREFIX` scan in
`_middle_window`. The summarizer input is the rendered projection of the middle region, so
`build_compaction_prompt` is unchanged.

The old compaction "checkpoint" (context_coordinator.py:196-198) is subsumed by the kind-6 event.

## 6.1.5 — Simplification tally

The round deletes more than it adds; this list is checked at close:

**Deleted** — `append_message` (as a public write), `append_user_message`, the stored `messages`
list, the `recent` rolling list, the pex.py:450 `[tool:]` turn write, `add_actions` +
`last_actions`, `_prune_tool_results`, `_align_forward`, `_align_backward`, the `SUMMARY_PREFIX`
scan in `_middle_window`, `_rewrite_messages_file` (compaction appends, revisions append),
`Turn.is_revised`/`original`/`add_revision`, `rewrite_history` + `Turn.action_target` (T12),
`_checkpoints` + the `history_snapshot` copies, the `messages.jsonl` mirror, and every
double-entry write in `take_turn`.

**Added** — the per-kind content schemas on `Turn`, `compile_messages()` (one function plus a
small per-kind mapping), and the kind-6 skip range it reads.

**Net** — one store, one write path per event, one file on disk, and compaction/pruning logic that
no longer needs pair-alignment helpers because pairing is structural.

## Out of scope (recorded, not taken)

- The `[click]`/`[action]` decoration wording itself — moves verbatim; MEM taking ownership of it
  stays Unresolved 3.
- Deleting `contains_keyword` — no callers today; the last flagged dead surface
  (`rewrite_history` and `action_target` were deleted under T12).
- Any frontend or webserver change — no router reads either store today.
- Thinking blocks in kind 4 — PEX runs without thinking; if that changes, blocks ride in
  `tool_uses` unchanged since the projection replays content verbatim.

## Verification

1. `run_suite.py --tests` green throughout; mem_unit_tests' compaction/checkpoint cases updated in
   place (no new tests under the moratorium — isolated component checks instead).
2. **Projection equivalence** (deterministic, the key check): replay a recorded session's turns
   through the new writers and compare the projection against that session's saved
   `messages.jsonl` — identical model-visible transcripts, before any live run.
3. Compaction check in isolation: build a long synthetic history, compact, assert the projection
   splices the summary, keeps pairs intact, and the file was appended to, not rewritten.
4. One live smoke conversation (find → rework → reply), then replay 2-3 gate ids (B03.C14,
   B01.C13) as the regression canary against `evals_20260718_170229.json`.
5. Commit before any eval run; restore `database/content` after (standing eval hygiene).

## Todo List

- [x] **T1 — finish the role rename.** DONE 2026-07-19. `add_turn(role, content, turn_type)`
  with lowercase values at every call site; all `.speaker` readers now read `.role`; log line
  keeps the uppercase rendering; `utt()` renders `Role.capitalize()`.
- [x] **T2 — Turn carries `content` per kind.** DONE 2026-07-19. `Turn = {role, turn_type,
  content, turn_id, timestamp}` — `is_revised`/`original` dropped under the revision ruling;
  every kind carries `text`; `turn_id` semantics unchanged.
- [x] **T3 — migrate every writer.** DONE 2026-07-19, per the 6.1.2 table. `append_user_message`,
  the external `append_message` calls, the pex.py `[tool:]` turn, and
  `add_actions`/`last_actions` all deleted; MEM's recap is the single kind-3 writer.
- [x] **T4 — build `compile_messages()`.** DONE 2026-07-19. On-demand projection; decoration
  moved in (`_decorate_click`); pruning is a rendering rule (store keeps full results);
  `full_conversation` is the raw view; `compile_history` owns the utterance filter.
- [x] **T5 — compaction on the unified store.** DONE 2026-07-19. Appends the kind-5 summary +
  kind-6 event only; skip range and splice read at render time; alignment helpers deleted;
  last-user anchor kept; `previous_summary` seeds from the newest summary turn on load.
- [x] **T6 — checkpoints as kind-6 turns.** DONE 2026-07-19. `save_checkpoint(label, data,
  text)` writes the marker turn; `get_checkpoint` scans history; `_checkpoints` deleted; MEM's
  turn_wrap and the PEX `coordinate_context` tool ride the new shape unchanged.
- [x] **T7 — storage swap.** DONE 2026-07-19. `history.jsonl` via `load_history` (lazy on fresh
  paths; first write flushes the seed); the file is strictly append-only — revisions append a
  kind-5 revised-text turn + kind-6 `revision` event instead of rewriting;
  trace_writer/run_traces/harness repointed.
- [x] **T8 — the three read surfaces.** DONE 2026-07-19. Both compile views apply revisions;
  kind 6 never reaches the model; the `[tool:]` leak into `compile_history` is gone.
- [x] **T9 — update existing tests.** DONE 2026-07-19. mem_unit_tests' compression/store suites
  rebuilt on turn seeding (`_seed_transcript`/`_seed_tool_round`); pex/nlu/model_tests
  accessors swapped to `compile_messages()`/`compile_history()`; 229 passed, no new tests.
- [x] **T10 — spec sync.** DONE 2026-07-19. architecture.md outline + Context Coordinator +
  Disk Storage updated (role/speaker/actor, checkpoint-as-activity, snapshot distinction,
  history.jsonl); `components/context_coordinator.md` rewritten to the six kinds and three
  read surfaces; `utilities/evaluation_suite.md` repointed. Historical round specs untouched.
- [x] **T11 — verification pass.** DONE 2026-07-19. Projection equivalence: five recorded
  sessions (B03.C14, B01.C13, B06.C04, B02.C06, B11.C08) converted to turns and re-projected —
  IDENTICAL to their saved `messages.jsonl` byte-for-byte (pruning disabled for the diff, as
  it is a deliberate change). Compaction + revision isolation checks passed. Live probe turn
  ran find → grounded reply end-to-end on the merged store. Gate-id replay
  `evals_20260719_145910.json`: B03.C14 completion 0.5 (= its clean-run baseline), B01.C13
  completion 1.0 (baseline 0.75) — no regression from the merge. The first replay attempt
  scored 0.0/0.0 and exposed a pre-existing crash, fixed as f8cd919: take_turn called
  `classify_intent()` with no arguments, so every live text turn fell into the fallback
  before PEX ran; the turn-level safety net logs nothing, which is why it was silent.
- [x] **T12 — delete `rewrite_history` and `Turn.action_target`.** DONE 2026-07-19 (Derek's
  ruling). Both had no callers. `rewrite_history` was the only writer of `revision` events, so
  the render support (`_revision_map` + the substitution in both compile views) went with it —
  the revision pattern stays fully spec'd in 6.1.3 as designed-not-built. 229 tests green.
