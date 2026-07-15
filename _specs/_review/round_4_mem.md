# Round 4 — MEM, the Head

> **Status (round 4.1 shipped, 2026-07-10).** MEM landed as a **module** at `backend/modules/mem.py` — there
> is no `MemoryManager` facade class; the module holds the three Levels (L1 Context Coordinator / L2
> `user_preferences` / L3 Business Knowledge), and `store_turn` runs at turn end. Durable L2 preferences and
> the grounding-entities redesign shipped with it. **Everything below is the pre-4.1 design record** kept for
> reference; read it as the plan that produced the module, not the current shape.

Maps to **Master Plan · Round 4**. Effort **L**. Depends on: the component shapes below (confirmed with the user
2026-06-21). Foundational facade that Rounds 3/5 read.

**Goal:** stand up memory as a real module with the three tiers and the read skills, as a **synchronous
facade** (the continuous background loop is deferred). **Deliverable:** `MemoryManager` rebuilt as the facade
over L1/L2/L3, the new `UserPreferences` and `BusinessContext` components, a typed `Preference` record, and
`recap`/`recall`/`retrieve`; the scratchpad extracted to its own `SessionScratchpad` component; the
aspirational pieces stubbed and marked.

Spec: `modules/mem.md`, `components/{context_coordinator,user_preferences,business_context,
session_scratchpad}.md`.

**Project-rule guard:** do **not duplicate data**. Each tier is the *single* store for its data — move
storage out of `MemoryManager`, don't copy it. After this step: `ContextCoordinator`=L1, `UserPreferences`=L2,
`BusinessContext`=L3, `SessionScratchpad`=the working ledger (its own component), `MemoryManager`=the facade.

---

## Decisions

**Locked (decided 2026-06-21):**
- **`MemoryManager` *is* the MEM module.** No separate `mem.py` / `MEM` class — the existing `MemoryManager`
  becomes the facade `__init__(context_coordinator, user_preferences, business_context)` holding
  `.context` / `.preferences` / `.business`, with `recap` / `recall` / `retrieve` as its public surface.
- **Reach tier ops through the sub-component**, not flattened onto the facade:
  `memory.preferences.store_preference(...)`, `memory.business.search_faqs(...)` — the same idiom as
  `nlu.ambiguity.*`.
- **The scratchpad leaves MEM.** It is not part of memory; extract it into a `SessionScratchpad` component
  owned by the World and reached as `nlu.scratchpad` (beside `nlu.ambiguity`). PEX and the policies read/write
  it through that one shared instance.
- **No separate FAQService.** `BusinessContext` is the single interface for all business-knowledge retrieval,
  including FAQs; it absorbs `utilities/faq_service.py`.
- **No trajectory playbooks** and **no MEM-outranks-NLU precedence rule** — both dropped from the design.

**Resolved here — confirm or override:**
- **E1 · memory tools.** rec: add `recap` / `recall` / `retrieve` as the public surface over the existing
  `compile_history` / `manage_memory` / `search_faqs` implementations; don't rename them. (§4.1, §4.5)

---

## 4.1 — Component shapes

**`MemoryManager` — the facade (the "Head").** Synchronous; holds the three tiers; exposes the read skills.
```python
class MemoryManager:
    def __init__(self, context_coordinator, user_preferences, business_context):
        self.context = context_coordinator        # L1
        self.preferences = user_preferences       # L2
        self.business = business_context          # L3

    def recap(self, n_turns=None, filter=None) -> str           # L1 — over ContextCoordinator
    def recall(self, query, flow_name=None) -> dict             # L2 — over UserPreferences
    def retrieve(self, query, top_k=10, documents=[]) -> dict   # L3 — over BusinessContext
```
- `recap` → `self.context.compile_history(look_back=n_turns, keep_system=True)`.
- `recall` → `self.preferences.read(query)` — the matching preferences. Semantic embedding lookup is deferred
  (no vector store yet), so the degenerate case returns the rendered set. `flow_name` is accepted but unused
  (playbooks dropped).
- `retrieve` → FAQ shortcut when `documents[0] == 'faq'` (`self.business.search_faqs`); otherwise rank the
  supplied `documents`, or `self.business.search_all(query, top_k=1000)` candidates, through
  `self.business.rerank(query, candidates, top_k)`.

**`backend/components/user_preferences.py` — L2.** The single preference store (migrated out of
`MemoryManager._preferences`). Holds typed records; renders endorsed-vs-guessed.
```python
class UserPreferences:
    def store_preference(self, key, value_or_record)    # bare str → endorsed=True, confidence=1.0
    def get_preference(self, key, default='') -> str     # degenerate value accessor (keeps current API)
    def read(self, query=None) -> dict                   # what `recall` returns; degenerate = all records
    def read_all(self) -> dict                           # every typed record
    def render(self) -> str                              # sorted-by-key (cache-stable); endorsed vs guessed
```

**`Preference` record (typed)** — `user_preferences.md`. A plain string is the degenerate case.
```python
Preference = { value:str, endorsed:bool, rankings:list=[], triggers:list=[], confidence:float=1.0 }
# caution dial: a reserved Preference whose value ∈ {ignore, warning, alert} — SHAPE ONLY, not wired to
# nlu_confidence_min (deferred); see Deferred register.
```

**`backend/components/business_context.py` — L3.** The single business-knowledge interface; absorbs
`faq_service.py`.
```python
class BusinessContext:
    def __init__(self, engineer)                         # loads the FAQ corpus, as FAQService did
    def insert_record(self, record)                      # ingestion / promotion seam
    def search_faqs(self, query, top_k=3) -> dict        # the existing FAQ rerank (tool surface unchanged)
    def search_all(self, query, top_k=1000) -> list      # candidate retrieval (whole corpus for now)
    def rerank(self, query, candidates, top_k=10) -> dict   # LLM rerank of the candidates
    # vector/embedding retrieval + agent.md cold-start ingestion = designed-not-built stub
```

**`backend/components/session_scratchpad.py` — the working ledger (NOT memory).** Extracted from the current
`MemoryManager` scratchpad code; owned by the World, reached as `nlu.scratchpad`.
```python
class SessionScratchpad:
    def write(self, key, value=None, writer='orchestrator')
    def read(self, key=None, writer=None, keys=None)
    def write_completion(self, flow, summary, metadata=None) -> dict
    def clear(self)
    @property
    def size(self) -> int
```

---

## 4.2 — L2: create `user_preferences.py`
- Move preference storage out of `MemoryManager` (the `_preferences` dict + the read/write methods) into
  `UserPreferences`.
- Implement the typed `Preference` record; `store_preference(bare_str)` writes the degenerate `endorsed=True`
  record so the existing `store_preference` tool keeps working unchanged.
- `render()` (endorsed → standing instruction, guessed → overridable default), sorted by key for prompt-cache
  stability — replaces the flat bullets at `for_orchestrator.py:180-189` (keep the sort).
- Update call sites: `pex.py` `_dispatch_store_preference` → `memory.preferences.store_preference`; the
  `manage_memory` read-preferences path → `memory.preferences.read_all`; the `for_orchestrator.py` render call.

## 4.3 — L3: create `business_context.py`
- Fold `FAQService` (`utilities/faq_service.py`) into `BusinessContext`: move the corpus load, `search_faqs`,
  and the rerank prompt + schema. Delete `faq_service.py`.
- Add `search_all` (return candidates — the whole corpus until a vector store exists) and `rerank` (the LLM
  rerank, extracted from `search_faqs`). `search_faqs` stays as the FAQ shortcut and keeps its current
  `{_success, matches}` contract.
- Re-point the `search_faqs` tool (`pex.py:145`) to `memory.business.search_faqs`; drop the `FAQService`
  import + `self._faq_service`.
- Mark vector retrieval + `agent.md` ingestion `# designed-not-built` at the seam.

## 4.4 — Extract `session_scratchpad.py` (owned by the World)
- Move the scratchpad code out of `MemoryManager` into a `SessionScratchpad` component
  (`write`/`read`/`write_completion`/`clear`/`size`), preserving the current dual-mode (in-memory dict vs
  append-only JSONL) and the `writer` recorded in code.
- Own one instance on the World (`world.scratchpad`); expose that same instance as `nlu.scratchpad` and hand
  it to PEX + the policies. Bind the session-file path where the session dir is set, replacing `agent.py:94`'s
  `memory._scratchpad_path` poke.
- Re-point every call site: `pex.py` (`write_scratchpad`/`read_scratchpad`/`write_completion`/
  `scratchpad_size` + the `append_to_scratchpad`/`read_scratchpad` calls + the `manage_memory` scratchpad
  actions), `policies/{base,research,revise}.py`, and the `agent.py` reset.
- The completion-record schema reconciliation (`write_completion` vs the minimal entry schema) stays in
  Round 3 §3.3.1.

## 4.5 — The facade: rebuild `MemoryManager`
- Strip scratchpad + preference storage out of `MemoryManager`; its `__init__` now takes the three tiers and
  holds them as `.context` / `.preferences` / `.business`.
- Implement `recap` / `recall` / `retrieve` per 4.1. Keep the `manage_memory` / `search_faqs` /
  `store_preference` tool names; route their calls through the facade or the tiers.
- Instantiate in `agent.py` alongside NLU/PEX: build `UserPreferences`, `BusinessContext`, and the
  `SessionScratchpad` (on the World), then `MemoryManager(world.context, preferences, business)`. The
  session-dir layout (`world.py`) is unchanged.

## 4.6 — Stubs + markers (deferred)
- `# designed-not-built` at each seam: scratchpad auto-promotion (salience + `used_count` judge — keep the
  `used_count` plumbing), proactive push (prefetch + anticipatory scratchpad notes), vector L3 retrieval +
  `agent.md` ingestion, and the caution-dial → threshold wiring.

---

## Verification
- Offline gate suites green (cwd wrapper). Update any test that imported preference/scratchpad APIs off
  `MemoryManager` to the new `UserPreferences` / `SessionScratchpad` / `MemoryManager` surface.
- No duplication: preferences live only in `UserPreferences`; the scratchpad lives only in
  `SessionScratchpad`; `grep -rn "_preferences" backend/` shows no second store.
- Smoke: `recap()` returns recent history; `recall(key)` returns a stored preference; `retrieve(q)` returns
  FAQ matches — all through `MemoryManager`. The scratchpad round-trips through `nlu.scratchpad` /
  `world.scratchpad`.

## Out of scope (Deferred register)
Real background MEM loop; auto-promotion; proactive push; vector/`agent.md` L3; caution-dial wiring.
