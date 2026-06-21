# Memory Manager Roadmap

This roadmap lifts the most relevant techniques from the memory-startup research deep-dive and
organizes them into phases a coding agent can follow. The headline novelty (trust grading + its
integration with the AmbiguityHandler) is locked from `final_judgment.md`; everything below is
*supporting machinery* — minor, validated techniques that make the trust axis defensible and the
implementation cheap.

The roadmap respects existing AssistantFactory decisions:

- Three tiers: **L1 scratchpad** (working notes, MemoryManager-owned per Q1 corrections), **L2 user
  preferences**, **L3 business context** (vetted FAQs + unvetted docs).
- Internal flows are the read API: `recap` / `store` (L1), `recall` (L2), `retrieve` / `search` /
  `study` / `reference` (L3). The agent picks via the FlowStack; we do **not** add a "memory router."
- Extraction is **per-flow** (the agent's policy is the unit of decision), not per-turn or per-message.
- Storage: **pgvector + BM25(lemmatized)**. No graph store.
- DialogueState owns belief data; MemoryManager L1 owns working notes. The split is from Q1's
  corrections, not relitigated here.

The trust-grading axis is the moat. The techniques below reinforce it without inventing concepts.

---

## What we are lifting (and from where)

The research surfaced ~20 candidate techniques. Five make this roadmap. Each one has to (a) reinforce
the trust-grading pillar, (b) be cheap to implement, and (c) not require a graph or a sleep-time
agent. The rejected ones are listed at the bottom with a brief reason — kept for posterity so we
don't relitigate them.

| Technique | Source | Tier(s) | What it gives us |
|---|---|---|---|
| **Bi-temporal 4-tuple** on every fact | Zep | L2, L3 | Trust transitions stay auditable; contradictions don't destroy history. The natural physical schema for "vetted vs unvetted over time." |
| **Enriched embedding** (concat content + keywords + tags + context summary) | A-Mem | L2, L3 | Materially better recall when query vocabulary differs from stored fact. Cheap one-shot LLM call at write time. |
| **MD5 hash dedup + UUID→integer remapping** at write time | Mem0 | L1, L2 | Skips the LLM entirely on exact duplicates; prevents the extractor LLM from hallucinating fact IDs when it sees existing memories. |
| **Filesystem-style L1 verbs** (`view`, `create`, `str_replace`, `insert`, `delete`) | Anthropic /memories | L1 | Replaces ad-hoc `store/recap` semantics with a small validated verb set. Same primitive Claude already understands. |
| **View-directory-first protocol** at the start of each flow | Anthropic /memories | L1, L2 | Agent lists *keys* (cheap) before deciding what *values* to expand. Bounded context cost; better recall than "trust the LLM to remember to look." |

The trust-grade taxonomy + the cross-pillar wire-up to AmbiguityHandler is what makes these
techniques add up to a pillar. Each phase below builds one slice.

---

## Phase 0 — Schema and trust taxonomy

This is the substrate. Everything else assumes these tables and fields exist. The phase is purely
schema + data migration; no behavior changes yet.

### Trust grade taxonomy

Four grades, ordered from highest to lowest trust:

| Grade | Source | Example |
|---|---|---|
| `VETTED_USER` | User explicitly confirmed via AmbiguityHandler resolution, the `preference` flow, or an `endorse` flow | "User confirmed: preferred tone is 'wry-but-warm'" |
| `VETTED_SOURCE` | Pulled directly from an authoritative L3 doc (FAQ / curated style guide / human-vetted markdown) | "From editorial guidelines: Oxford commas required" |
| `INFERRED` | Agent derived from context across multiple turns/flows with corroboration | "User has mentioned Substack three times — likely primary channel" |
| `SPECULATIVE` | Agent guessed mid-flow without corroboration; written for later confirmation | "User said 'shorter' — possibly means <600 words?" |

`VETTED_USER` and `VETTED_SOURCE` are the "vetted" half of the pillar #3 dichotomy. `INFERRED` and
`SPECULATIVE` are "unvetted." Retrieval surfaces the grade alongside the fact; AmbiguityHandler
reads it (Phase 1).

### Row schema (L2 / L3)

Every fact row carries this shape. Columns marked `*` are new versus today.

```python
class MemoryFact:
    id: UUID                      # primary key
    content: str                  # the fact itself
    embedding: Vector[N]          # SOTA model, dim TBD per the embedding-model decision
    bm25_tokens: list[str]        # lemmatized for keyword index
    tier: Literal["L2", "L3"]
    namespace: str                # e.g. "preference", "fact:editorial", "doc:onboarding"

    # Trust axis *
    trust_grade: TrustGrade       # VETTED_USER | VETTED_SOURCE | INFERRED | SPECULATIVE
    source_flow: str              # dax of the flow that wrote this (e.g. "{08A}" for preference)
    source_session_id: UUID       # which session produced it

    # Bi-temporal 4-tuple * (Zep)
    t_created: datetime           # transactional: when we wrote the row
    t_expired: datetime | None    # transactional: when we marked it stale (None = live)
    t_valid_from: datetime        # event: when the fact became true in the world
    t_valid_until: datetime | None  # event: when the fact stopped being true (None = still true)

    # Lineage *
    supersedes_id: UUID | None    # if this row replaces a previous one, point to it
    promoted_from_id: UUID | None # if trust was upgraded, point to the lower-grade ancestor

    # Anti-dup *
    content_hash: str             # MD5(content) — exact-dedup gate
```

Three things to note about this shape:

The bi-temporal pair is Zep's `(t'_created, t'_expired, t_valid, t_invalid)` renamed for Python
readability. `t'` is *when we observed*, plain `t` is *when it was true*. Both are needed: a user
saying "I moved to SF last March" on a turn timestamped today means `t_created = today` but
`t_valid_from = March`. The Q3 LongMemEval-style temporal questions that Mem0 loses by 15+ points
are exactly the queries this enables. Cost of carrying four timestamps per row: ~32 bytes.

`supersedes_id` is the version chain. When a new fact contradicts an old one, we don't `DELETE` (the
Mem0 mistake) — we insert the new row, set the old row's `t_expired` to now and `t_valid_until` to
the new row's `t_valid_from`, and link via `supersedes_id`. Old beliefs stay queryable for
"what did we used to think on date X." This is Supermemory's version chain + Zep's edge invalidation,
distilled to two columns.

`promoted_from_id` is the trust transition link. When AmbiguityHandler resolves a `CONFIRMATION`
ambiguity ("you said tone='warm' — confirmed?"), the `SPECULATIVE` row is `t_expired`'d and a new
`VETTED_USER` row points back to it. This is the cross-pillar surface — the link Phase 3 actually
uses.

### L1 schema

L1 stays a per-session in-memory structure backed by SQLite on session resume. No vector index. The
schema is smaller but mirrors the same disciplines:

```python
class L1Entry:
    key: str                       # namespaced path, e.g. "audit/findings", "polish/v3"
    value: str                     # serialized working note
    written_by: str                # policy_path of the writer (e.g. "policies.revise.audit")
    t_created: datetime
    content_hash: str              # for the dedup gate
    version: int                   # bumped on str_replace / insert
```

Key validation: `^[a-z][a-z0-9_]*(/[a-z][a-z0-9_]*)*$` — alphanumeric + underscore, slash-separated.
Borrowed from Anthropic's directory-traversal pattern.

### Acceptance criteria for Phase 0

- L2 and L3 tables exist in Postgres with the schema above; indexes on `(namespace, trust_grade,
  t_expired)` and `(content_hash)`.
- The L1 entry shape is implemented in MemoryManager; existing `store`/`recap` paths continue to
  work against it.
- A migration script back-populates trust grades for any existing L2/L3 data: anything from a
  `preference` flow → `VETTED_USER`; anything from L3 curated FAQs (search namespace) →
  `VETTED_SOURCE`; everything else → `INFERRED`. All `t_valid_from = t_created`, both `*_until`
  fields null.
- No behavior change visible to flows yet.

---

## Phase 1 — Read path: surface trust grade everywhere

The cheap wins. Internal flow tools start returning the trust grade and temporal validity alongside
content; AmbiguityHandler reads it; pagination caps context cost.

### Internal flow return shape

Today, `recall`, `retrieve`, `search`, `study`, `reference` return content strings. Change the
return shape to a structured envelope:

```python
class RetrievedFact:
    content: str
    trust_grade: TrustGrade
    age: timedelta              # now - t_created, for sycophancy-prevention prompts
    is_currently_valid: bool    # t_valid_until is None or > now
    is_superseded: bool         # not is_currently_valid AND supersedes a newer fact
    relevance: float            # hybrid score (semantic + BM25)
```

Each Internal flow continues to do its own retrieval (own pgvector query, own BM25, own filters
by tier). The envelope is added in the response formatter — minor refactor, no policy changes.

### AmbiguityHandler integration

This is the cross-pillar wire-up. When a policy receives a `RetrievedFact` with
`trust_grade ∈ {INFERRED, SPECULATIVE}` and intends to *act* on it (slot fill, response assertion),
the AmbiguityHandler auto-raises a `SPECIFIC`-level ambiguity. The handler's existing taxonomy from
ontology.py:

```python
class AmbiguityLevel(str, Enum):
    GENERAL = 'general'
    PARTIAL = 'partial'
    SPECIFIC = 'specific'
    CONFIRMATION = 'confirmation'
```

`SPECIFIC` is the right level: we know which fact is uncertain and why. The handler decides whether
to surface a confirmation question or proceed silently based on the policy's risk tolerance (e.g.,
the `publish` flow won't proceed on unvetted facts; the `chat` flow might).

Wire format: the handler exposes `check_trust(fact: RetrievedFact, action: str) -> AmbiguityFlag |
None`. Policies call it before consuming a low-trust retrieval in any binding decision.

### Pagination (Letta-style)

`recall`, `retrieve`, `search` accept an optional `page` parameter and return at most N results
(default 5) plus a `next_page` cursor. The agent that wants more pages issues the same Internal
flow again with the cursor. This is Letta's `archival_memory_search(query, page)` pattern —
prevents context bloat when there are many matching facts.

`recap` is exempt (L1 is bounded at 64 items by design — full enumeration is fine).

### Acceptance criteria for Phase 1

- All five long-term Internal flows (`recall`, `retrieve`, `search`, `study`, `reference`) return
  `RetrievedFact` envelopes, never raw strings.
- `AmbiguityHandler.check_trust()` exists, returns a flag on `INFERRED` or `SPECULATIVE` facts when
  the policy declares an intent to bind/assert.
- A policy that consumes an `INFERRED` fact without calling `check_trust()` first is caught by a
  PEX post-hook check (regression test).
- Pagination works on the four long-term flows; default N=5, cursor opaque.

---

## Phase 2 — Write path: extract, dedupe, enrich

This is where the per-flow extraction pipeline lives. It runs at flow-completion (the agent's
"heartbeat" per the user's design), not per turn.

### The extraction trigger

When a flow transitions `Active → Completed` (per `FlowLifecycle` in ontology.py), the policy
optionally calls `MemoryManager.extract(flow_summary, target_tier)`. Some flows always extract
(`preference` → L2, write skill output → L3); others never do (`chat`, `explain`); others extract
opportunistically based on policy logic. The trigger is policy-owned, not centralized.

### The extraction pipeline

Five steps, in order. Steps 3–5 are the "lift from research"; steps 1–2 are bookkeeping.

**Step 1 — Hash-dedup gate (Mem0).** Compute `content_hash = MD5(normalize(content))`. Query
existing rows in the namespace with the same hash. If a live row exists, return its id with a
`NOOP` outcome. This skips the LLM entirely on exact duplicates and is dramatically cheaper than
any semantic check. Normalize = lowercase + collapse whitespace; nothing fancier — we want exact
matches to hit, near-matches to fall through to step 4.

**Step 2 — Top-k similar fetch.** Pull top-10 existing facts by semantic similarity in the target
tier and namespace. These will be shown to the extractor LLM for the ADD/UPDATE/SUPERSEDE decision.

**Step 3 — UUID → integer remapping (Mem0).** Before showing the top-10 to the extractor LLM,
remap their UUIDs to integers `"0"` through `"9"`. Keep a local dict
`{"0": real_uuid, "1": real_uuid, ...}`. The LLM cannot hallucinate a UUID it never sees, which
removes a real class of bugs at zero cost. After the LLM returns, map back. This is the single
cheapest correctness win in the entire roadmap.

**Step 4 — Enrichment + decision LLM call (A-Mem).** Single call that does two jobs:

1. Generate the enrichment fields for the new fact: `keywords` (≤6 distinct), `tags` (≤4 broad),
   and a one-sentence `context_summary`. These are A-Mem's `K_i, G_i, X_i`.
2. Decide whether to `ADD` (new fact), `SUPERSEDE` an existing integer-id (contradicts a prior
   fact), or `NOOP` (no new information). Note: no `UPDATE` and no `DELETE` — those are the Mem0
   primitives we explicitly do not want, because they destroy contradiction history.

Prompt template (`memory_extract.j2`, abbreviated):

```
You are extracting a fact from a completed {{ flow_name }} flow for {{ target_tier }} storage.

CANDIDATE FACT:
{{ candidate_content }}

EXISTING FACTS (numbered for reference — use these numbers, NEVER invent new ones):
{% for f in renumbered_facts %}
[{{ f.int_id }}] (grade={{ f.trust_grade }}, valid={{ f.t_valid_from }}–{{ f.t_valid_until or 'present' }})
    {{ f.content }}
{% endfor %}

Return JSON with these fields:
{
  "decision": "ADD" | "SUPERSEDE" | "NOOP",
  "supersedes_int_id": <integer or null>,    // only if decision=SUPERSEDE
  "keywords": [<at most 6 strings>],
  "tags": [<at most 4 strings>],
  "context_summary": "<one sentence>"
}

Guidelines:
- ADD: the candidate is new information, no existing fact covers it.
- SUPERSEDE: the candidate directly contradicts existing fact [N]; choose N from the list above.
- NOOP: the candidate is already covered by an existing fact (no new information).
- Do NOT invent integer ids. Only use numbers from the EXISTING FACTS list.
- Keywords/tags must be present even on NOOP — they may be applied to the existing fact.
```

The prompt parallels Mem0's `DEFAULT_UPDATE_MEMORY_PROMPT` in structure but the operation set is
trust-grade-friendly. The explicit "do NOT invent integer ids" line is belt-and-suspenders on top
of the remapping.

**Step 5 — Embedding generation (A-Mem).** Compute the embedding over the **concatenation** of
`content + " " + " ".join(keywords) + " " + " ".join(tags) + " " + context_summary`, not just
`content`. A-Mem's ablation showed disabling this (along with link generation) drops Multi-Hop F1
from 27 to 9.7 — the enrichment is doing most of the work. The cost is zero at retrieval time;
the cost at write time is one embedding call, which is happening anyway.

### Trust grade assignment at write

The extractor doesn't decide trust grade — the *source flow* does. Defaults:

| Source flow | Default grade |
|---|---|
| `preference` | `VETTED_USER` |
| Any `publish.*` flow that writes back into L3 | `VETTED_SOURCE` |
| `audit` writing findings → L1 | `INFERRED` (working note) |
| Any policy writing mid-flow speculation → L1 or L2 | `SPECULATIVE` |
| L3 ingest from a curated source doc | `VETTED_SOURCE` |
| L3 ingest from an unvetted scrape | `INFERRED` |

Phase 3 changes grades; Phase 2 just sets the initial value per the source flow.

### SUPERSEDE wiring

When the extractor returns `SUPERSEDE` with `supersedes_int_id = 3`, the write transaction:

1. Looks up the real UUID via the remap dict.
2. Sets `old.t_expired = now()` and `old.t_valid_until = now()`.
3. Inserts the new row with `supersedes_id = old.id` and `t_valid_from = now()`.

Both rows live forever. Queries default to `t_expired IS NULL` (live rows only); historical queries
override.

### Acceptance criteria for Phase 2

- `MemoryManager.extract()` exists, follows the five-step pipeline, returns
  `(operation, new_id_or_existing_id)`.
- MD5 dedup gate measurable: a unit test writes the same content twice and the second call returns
  `NOOP` without invoking the LLM (mock the LLM and assert call count = 0 on the second call).
- The integer-remap test: feed the LLM a deliberately-broken prompt asking it to "use UUID
  abc-def-…" and assert the post-processor catches and rejects.
- Enriched-embedding test: write the same content with two different keyword/tag sets, retrieve via
  a query that matches only one keyword set, assert the right row ranks first.
- SUPERSEDE preserves the old row (test: query with `include_superseded=True` returns both).

---

## Phase 3 — Trust promotion and the AmbiguityHandler loop

This phase closes the cross-pillar loop. Pillar #1 (AmbiguityHandler) doesn't just *read* trust
grades — it *promotes* them when it resolves uncertainty. This is the integration the
`final_judgment` calls "the part nobody can copy quickly."

### Promotion paths

There are three ways a fact's trust grade changes:

**Path A — User confirms via AmbiguityHandler.** AmbiguityHandler raises a
`CONFIRMATION` ambiguity referencing a `SPECULATIVE` or `INFERRED` fact. User confirms. The
handler calls `MemoryManager.promote(fact_id, to_grade=VETTED_USER, evidence=ambiguity_id)`. The
write path: insert a new row with the same content, `trust_grade = VETTED_USER`,
`promoted_from_id = old.id`, `t_valid_from = now()`. The old row gets `t_expired = now()` so the
chain is auditable. Queries return the promoted row by default.

**Path B — Corroboration over N flows (configurable, default N=3).** When a `SPECULATIVE` fact
is read by N distinct downstream flows without being contradicted or superseded, it auto-promotes
to `INFERRED`. This is a background job, not a hot-path operation. The signal is the
`source_session_id` and reading-flow telemetry; we already log this for pillar #2's transparency
dividend, so the data is in the JSONL log.

**Path C — Contradiction.** When a SUPERSEDE happens (Phase 2), the *new* row inherits the source
flow's default grade. But there's a special case: if the new row is `VETTED_USER` superseding a
`VETTED_SOURCE`, log a `trust_conflict` event for human review (don't auto-resolve). Vetted-source
trumping vetted-user is also possible (rare; usually the user is right about their own preferences,
but they can be wrong about editorial guidelines).

### Decay for SPECULATIVE

SPECULATIVE rows that aren't promoted within 30 days get garbage-collected
(`t_expired = now(), t_valid_until = now()`). This is the Anthropic /memories pattern of
"30-day version retention" applied to the unvetted tier specifically. INFERRED and vetted grades
have no decay — they age into the bi-temporal record gracefully.

### What the AmbiguityHandler now sees

The handler's existing four-level taxonomy maps cleanly:

| Ambiguity level | Memory situation that raises it |
|---|---|
| `GENERAL` | Multiple retrieved facts conflict at high trust; the handler doesn't know which to use |
| `PARTIAL` | One slot is filled from `INFERRED`, another from `VETTED_USER`; mismatched confidence |
| `SPECIFIC` | A bound action depends on a single `INFERRED` or `SPECULATIVE` fact |
| `CONFIRMATION` | The handler is asking the user to upgrade a specific fact's trust grade |

This is the productized form of "uncertainty as content" — the handler isn't separately tracking
trust; it's reading it directly from MemoryManager and using its existing levels.

### Acceptance criteria for Phase 3

- `MemoryManager.promote(fact_id, to_grade, evidence)` exists; promotions create new rows with
  `promoted_from_id` set, never overwrite.
- A confirmation-flow test: AmbiguityHandler raises CONFIRMATION on a SPECULATIVE fact, user
  confirms, post-condition is two live rows in the chain (the old `t_expired`'d, the new
  `VETTED_USER` with `promoted_from_id` pointing back).
- A decay test: insert a SPECULATIVE row with `t_created` 31 days ago, run the GC, assert it's
  expired but still queryable with `include_expired=True`.
- A trust-conflict test: write a `VETTED_USER` fact that SUPERSEDEs a `VETTED_SOURCE` fact, assert
  the `trust_conflict` event appears in the JSONL log.

---

## Phase 4 — Filesystem-style L1 verbs (optional cleanup)

This phase replaces L1's existing `store/recap` semantics with a small validated verb set borrowed
from Anthropic's `/memories` tool. Optional because the current `store/recap` works; do it when
you have a free week and an appetite for cleanup, or when a policy needs `str_replace`-style atomic
correction (audit findings being polished into final form is the use case that motivates it).

### The verb set

Five verbs, all already implementable against the L1Entry schema from Phase 0:

| Verb | Semantics | Replaces |
|---|---|---|
| `view(key_prefix=None)` | List keys matching prefix, return key + brief metadata (no values) | `recap` keys-only mode |
| `read(key)` | Return the value at `key` | `recap` (current behavior) |
| `create(key, value)` | New entry; fails if key exists | `store` (when new) |
| `str_replace(key, old, new)` | Find-and-replace within the value; fails if `old` not unique | (new) |
| `insert(key, line, text)` | Insert at specific line; fails if out of bounds | (new) |
| `delete(key)` | Remove the entry | (new) |

`view` is the directory listing. `read` is the explicit value fetch. The separation matters: at
flow start, the agent can `view` (cheap) before deciding what to `read` (expensive). Today, `recap`
returns the full L1 contents, which is fine at 64 items but conceptually muddy.

### View-directory-first protocol

Anthropic's recommended pattern: agents always `view` memory before doing anything else. Implement
as a PEX pre-hook on every policy: if the policy has declared (via its metadata) that it reads L1,
auto-inject a `view("policies.{this_policy}/")` result into its context before the policy's main
LLM call. The agent doesn't have to remember to look — the system looks for it.

This is *not* a global `recap` injection — it's namespaced by writing policy. The Q1-corrected
discipline of "L1 stores working notes" means most flows shouldn't see most of L1, only the keys
in their own namespace plus a small set of shared namespaces (e.g., `audit/*` is shared between
revise sub-flows).

### Path validation

L1 keys go through the regex from Phase 0 plus a length check (max 200 chars) and a depth check
(max 4 slashes). Borrowed straight from the Anthropic directory-traversal-prevention pattern.

### Acceptance criteria for Phase 4

- All five verbs exist on `MemoryManager.l1.*`; `store` and `recap` become thin shims over them
  during a deprecation window.
- A PEX pre-hook runs `view` for the policy's namespace and injects the keys into context.
- A path-validation test: `create("../../etc/passwd", "...")` raises a `KeyValidationError`.

---

## Phase 5 — Reflexion pass on extraction (optional, defer)

This is the smallest possible quality win and is genuinely optional. After the Phase 2 extractor
returns, run a one-line check: "Did you miss any keywords or tags?" If yes, regenerate. Zep does
this for entity extraction; the cost is one extra LLM call per write that produces non-empty
revisions. Probably worth ~3–5% retrieval quality but it's marginal — only do this once the rest of
the stack is stable and there's a measurable retrieval-quality gap to close.

The honest framing: this is one prompt template addition and a loop counter. Ship it if you measure
a need; don't ship it speculatively.

---

## What we deliberately rejected

For posterity, so the next reviewer doesn't re-litigate:

| Rejected technique | Source | Why rejected |
|---|---|---|
| **Sleep-time agents** | Letta | Per-flow heartbeat already does this. A separate async agent is solving a problem we don't have. |
| **Graph layer with entity/relation triples** | Mem0 / Zep | Pillar #3 doesn't need it; user explicitly excluded. Adds operational complexity (Neo4j or equivalent) for no pillar value. |
| **A-Mem memory evolution** (rewrite k neighbors on every write) | A-Mem | 3 + k LLM calls per insert. Costs are ruinous for SaaS economics; benchmark wins don't translate to production. |
| **Mem0's destructive `DELETE` operation** | Mem0 | Destroys contradiction history. The whole point of bi-temporal versioning is that contradictions stay queryable. |
| **A separate fact-extractor LLM call before the decision LLM call** | Mem0 (paper) | Mem0's own V3 implementation consolidated them; we do the same in Phase 2 step 4 (single LLM call). |
| **Community detection / label propagation** | Zep | Requires the graph layer; rejected with it. |
| **Cross-encoder reranker** | Zep | Hybrid (semantic + BM25) is already in place; cross-encoder is a real cost for a small recall bump on hard queries. Revisit if a specific query class fails. |
| **Memory rethink / sleep-time block rewriting** | Letta | We don't have memory blocks; L1 is per-flow working notes. The primitive doesn't map. |
| **Heartbeat keyword in LLM output** | MemGPT / Letta | Our flow lifecycle (`Pending → Active → Completed`) is the heartbeat. We don't need an LLM-emitted keyword. |
| **Verbatim conversation log as recall memory** | MemGPT / Letta | We have the JSONL session log from pillar #2 for this. Don't duplicate. |
| **Anthropic per-store read-only / read-write flags** | Anthropic /memories | L3 is already effectively read-only from policies (only ingest can write); L2 / L1 are intrinsically read-write. The flag would add ceremony without surfacing a real distinction. |
| **Anthropic 8-stores-per-session attachment** | Anthropic /memories | Our three tiers are fixed at session start by design; we already don't hot-attach. |

---

## Sequencing summary

Recommended order, with rough effort estimates assuming a single competent coder and AF's existing
substrate:

1. **Phase 0** (schema + taxonomy + migration) — ~1 week. No flow changes.
2. **Phase 1** (read path + AmbiguityHandler integration + pagination) — ~1 week. Visible value
   on day one once policies start raising ambiguity on low-trust hits.
3. **Phase 2** (write path with dedup / remap / enriched embedding) — ~2 weeks. The biggest single
   chunk. Most of the LLM-prompt engineering lives here.
4. **Phase 3** (promotion + decay + conflict logging) — ~1 week. Closes the cross-pillar loop.
5. **Phase 4** (filesystem L1 verbs) — ~1 week, **defer** until a use case demands it.
6. **Phase 5** (reflexion extraction) — ~2 days, **defer** until retrieval quality measurably
   plateaus.

Phases 0–3 are the roadmap proper (~5 weeks). Phases 4–5 are quality-of-life and ship on demand.

### What ships visibly to a user, by phase

- After Phase 1: the agent stops asserting unvetted facts; AmbiguityHandler starts asking "did you
  mean X?" on low-trust retrievals. This is the first user-visible win.
- After Phase 2: extraction quality on L2 preferences goes up materially (A-Mem-style enriched
  embedding); writes become idempotent (Mem0 dedup); contradictions stop destroying history.
- After Phase 3: trust grades evolve over time; the agent gets smarter about its own users without
  expert intervention. This is the pillar-#3 differentiator fully realized.

The three pillars compound: trust-graded memory + low-trust ambiguity raising + structured
worldview together produce the anti-sycophancy story the `final_judgment` calls out. Phase 3 is
where that story becomes operational.

---

## Open questions to revisit after Phase 1 ships

1. **Embedding model choice.** User noted "take latest SOTA, not something to worry about." Once
   Phase 1 is live, measure recall@10 on a small held-out set of AF interactions and pick from the
   current SOTA shortlist (likely a 1024-dim or larger model). Lock for a quarter.
2. **N for corroboration-based promotion.** Default N=3 in Phase 3 is a guess. Measure the
   distribution of "times a fact is read before being superseded" and pick N where the promotion
   rate stabilizes.
3. **Decay window for SPECULATIVE.** 30 days mirrors Anthropic's pattern. If we observe many
   speculations being confirmed weeks later, extend to 60–90.
4. **Whether to extract on every flow completion or only some.** Currently policy-owned; if the
   distribution turns out to be 80/20 (one or two flows produce most writes), formalize that into
   the flow metadata to save us from boilerplate.
