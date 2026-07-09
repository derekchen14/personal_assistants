# Round 4.1 — MEM operational: a real mem.py, durable L2, honest reads

Status: **built 2026-07-09** — decisions reviewed via AskUserQuestion (D1-A, D2-A, D4-A; D3
flipped to defer by Derek mid-build); smoke transcript below. First sub-round of
`_specs/_review/round_4_mem.md`, re-read under the Round-0 architecture (follows
[[round_0.3_spec.md]], the sequential turn loop). The biggest — yet relatively easy — change is
converting the MemoryManager component into the MemoryExtensionModule module at
`backend/modules/mem.py`. Wiring refinement during the build (Derek): the username is passed all
the way down — `MemoryExtensionModule(config, engineer, username)` →
`UserPreferences(config, username)`, which binds `database/memory/<username>.json` and loads it
in its own constructor; the Assistant just passes the name through.

## Where round 4 already landed (no work)

Most of round 4 shipped during rounds 0.1-0.3 under new names:

- L1 `ContextCoordinator` — turns + `messages.jsonl` mirror + compression + checkpoints. Real.
- L2 `UserPreferences` — typed `Preference` records, `render()` endorsed-vs-guessed, `read()`.
- L3 `BusinessKnowledge` (was BusinessContext/BusinessDocuments) — absorbed FAQService;
  `search_documents` is wired as a PEX tool.
- `SessionScratchpad` extracted (PEX-owned, per 0.1 — supersedes round 4's "owned by the World,
  reached as nlu.scratchpad").
- The facade with `recap` / `recall` / `retrieve` + `store_turn` (0.3).

Round 4's locked decision "`MemoryManager` IS the module, no separate mem.py" is SUPERSEDED by
the Round-0 module ladder: modules live in `backend/modules/` (`nlu.py`, `pex.py`, and now
`mem.py`).

## The gaps that make MEM not-operational

1. **No `backend/modules/mem.py`.** The module class sits in
   `backend/components/memory_manager.py` — a module hiding in the components layer under a
   retired name. NLU and PEX construct their components from `backend/modules/`; MEM must too.
2. **L2 dies with the process.** `store_preference` writes an in-memory dict; nothing saves or
   loads. The PEX tool description already promises "Survives the session" — today that is
   false. mem.md says L2 is per-account and persistent, frozen into the prompt at session start.
3. **`recap` / `recall` / `retrieve` have zero callers.** They exist as methods; nothing invokes
   them. PEX-side near-equivalents exist for two of three (`coordinate_context` ≈ recap,
   `search_documents` ≈ retrieve's FAQ path); `recall` has none (the prompt snapshot and the
   ambiguity recover path are the only L2 reads).
4. **Past sessions are written but never read.** `store_turn` saves `state.json` per turn;
   nothing ever loads a previous session's record.

## The work

### 4.1.1 — Move the module: `backend/modules/mem.py`

- Move `MemoryExtensionModule` (+ `MEM` alias) from `components/memory_manager.py` to
  `modules/mem.py`; delete `memory_manager.py`. Class name and surface unchanged.
- Update imports: `backend/assistant.py`; fix the stale "MemoryManager" mention in
  `for_orchestrator.py`'s module docstring.

### 4.1.2 — Durable L2: `UserPreferences.save` / `load`

- Store: `database/memory/<username>.json` — per-account, cross-session (sessions/ is per-convo;
  memory/ is the durable record). One JSON object `{key: Preference-as-dict}`.
- `load(path)` in `Assistant.__init__` right after modules are wired (the Assistant knows the
  username; MEM's constructor does not). `save()` inside `store_preference` — every write lands
  on disk immediately, so the PEX tool description becomes true.
- Round-trips the full typed record (endorsed, rankings, triggers, confidence), not just values.
- `reset()` is NOT wired to prefs (a new session keeps the account's preferences — resetting L2
  would defeat its purpose; wiping is a manual file delete for now).

### 4.1.3 — Read paths (decisions D2/D3 below)

## Decisions for sign-off

### D1 — L2 store location

- **D1-A (recommended)** — `database/memory/<username>.json`, loaded once in `Assistant.__init__`,
  saved on every `store_preference`. New `database/memory/` dir; nothing else changes.
- **D1-B** — keep preferences inside the session dir. Rejected-by-default: preferences are
  per-account, not per-conversation; putting them in `sessions/<id>/` loses them on reset.

### D2 — Do the three memory skills get tool wiring this round?

- **D2-A (recommended)** — not yet. The orchestrator already reaches L1 via `coordinate_context`
  and L3 via `search_documents`; L2 arrives frozen in the prompt and via the ambiguity recover
  path. Wire `recap`/`recall`/`retrieve` as tools only when a flow actually needs them (the
  eval rounds will show it). Methods stay as the module surface.
- **D2-B** — add one `recall_preferences` tool for PEX now (mid-session preference reads are
  invisible today because the prompt snapshot is frozen at session start).

### D3 — Artifact long-term storage

mem.md: the Assistant hands each turn's artifact to MEM for the durable record. Today artifacts
live only in `world.artifacts` (memory).

- **D3-A** — `store_turn` also appends the latest artifact (as dict) to `artifacts.jsonl` in the
  session dir.
- **D3-B (DECIDED — Derek, mid-build)** — defer with a designed-not-built marker in `store_turn`.

### D4 — Reading past sessions

- **D4-A (recommended)** — defer. `DialogueState.load` already exists as the throwaway read;
  what MEM should *do* with past sessions (recall across conversations) needs its own design.

## Spec truth pass

`_specs/modules/mem.md` still says MEM is a "continuous LLM-loop" peer running in parallel,
names the old NLU writer tools (`classify_intent`/`detect_flow`/`fill_slots`), and calls L3
"Business Context". Update it to the Round-0 reality: code-only module, `BusinessKnowledge`,
the store_turn record, and the background loop as designed-not-built.

## File touch list

- `backend/modules/mem.py` — new home (moved from `components/memory_manager.py`, then deleted).
- `backend/components/user_preferences.py` — `save`/`load`, Preference round-trip.
- `backend/assistant.py` — import path; prefs load after wiring.
- `backend/prompts/for_orchestrator.py` — docstring truth.
- `_specs/modules/mem.md` — the truth pass.

## Done means

`utils/smoke_turn.py` gains a preference beat: a turn that stores a preference ("remember I
always post to Substack"), then a NEW Assistant instance whose session prompt renders it — proof
that L2 survives the process. The 3-turn find→outline→release smoke still passes.

### Smoke transcript (2026-07-09, live run)

```
== turn 1 ==  find     Completed   belief: Research/find 1.0
== turn 2 ==  outline  Active      belief: Draft/outline 1.0   (3 outline options drafted)
== turn 3 ==  release  Completed   belief: Publish/release 1.0 ("...is live on the blog!")
== turn 4 ==  "Remember that I always publish to Substack first."
AGENT:  Got it — I've saved that preference and will always lead with Substack for future
        publishes.

== reborn assistant (new instance, same account) ==
L2 store: {'publish_channel_first': 'Substack'}
prompt renders it: True
```

This run's outline flow also completed its ask properly (turn 2 drafted 3 options), unlike the
0.3 run — the grounding hand-off gap is intermittent, still open. The released post was moved
back to `drafts/` and `metadata.json` restored after the run (standing library stays intact).
