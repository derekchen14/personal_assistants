# Chat → Internal Sub-flow Dispatch — Master Plan

## Goal

Today, `chat_policy` is a single LLM call over conversation history with no tool access. We
want Chat (`{000}`) to be able to *decide*, per turn, whether to:

- **a.** delegate to **Search** (`{189}`) for FAQ lookups (e.g. "What can you do?",
  "Tell me about who made you.", "How do you handle SEO?")
- **b.** delegate to **Reference** (`{139}`) for dictionary/thesaurus help
  (e.g. "synonym for important", "definition of ephemeral")
- **c.** respond directly when the question is conversational and self-contained.

The dispatch pattern already exists: `audit_policy` (`backend/modules/policies/revise.py:211`)
uses a routing-LLM call + `flow_stack.stackon(...)` + `state.keep_going = True` to push
sub-flows onto the stack, let them run in subsequent inner-loop passes, and then read
their findings back from the scratchpad. We will reuse that pattern almost verbatim, with
two adjustments:

1. The sub-flows here are **Internal** (`Intent.INTERNAL`) rather than user-facing
   Revise flows. Internal flows already have correct semantics: they don't surface a
   user-visible response (`res.py:29`), and they're excluded from NLU detection
   (`nlu.py:381`), so they can only be reached via `flow_stack.stackon()` from a parent
   policy. Exactly what we need.
2. The router's classification space is **3-way** (search / reference / direct)
   rather than the audit router's 4-flow split.

## Phase ordering (and why)

Chat dispatch is the *easy* part — the hard parts are making Search and Reference
actually useful. Build the leaves first, then wire them up.

| Phase | What | File |
|------|------|------|
| 1 | Make Search look up real FAQs and write findings to the scratchpad | [search.md](search.md) |
| 2 | Make Reference look up real dictionary/thesaurus entries | [reference.md](reference.md) |
| 3 | Teach Chat to dispatch via a 3-way router and consume sub-flow findings | [internal_flows.md](internal_flows.md) |
| 4 | Integration — manual smoke + e2e eval covering all three branches | (this file, §Integration) |

Phases 1 and 2 are independent and could run in parallel; phase 3 depends on both. Phase
4 is verification, not new code.

## Decisions baked in

These are choices I'm making up-front based on the codebase shape. Push back on any.

- **Router LLM call lives inside `chat_policy`**, mirroring `_audit_dispatch` at
  `revise.py:259`. Output schema is a 3-enum (`search`, `reference`, `direct`) with an
  optional `query` field; we follow the audit precedent of a tiny JSON-schema-validated
  call. No new "Router" component.
- **Single dispatch per turn (v1).** A user message routes to at most one sub-flow.
  Multi-dispatch (e.g. "what's the synonym for *X* — and also what can you do?") is
  rare in chat and adds re-entrancy complexity for no proven win. Revisit if eval data
  shows demand.
- **Sub-flow findings flow through the scratchpad**, keyed by `flow.name()`. Audit
  already does this (`revise.py:201-208`) — same pattern. Chat reads back via
  `self.memory.read_scratchpad('search')` or `'reference'` on the second pass.
- **Two-stage `chat_policy`.** Stage 1 (router) decides; stage 2 (compose) runs
  *after* the sub-flow completes and incorporates findings. Implemented via
  `flow.stage` attribute (`'pre_dispatch'` → `'post_dispatch'`), exactly as
  `audit_policy` uses `flow.stage` ('discovery' → 'delegation').
- **Search corpus = JSON file** at `database/faq_data/faqs.json`, structured as
  `[{"question": ..., "answer": ..., "tags": [...]}]`. Hugo-relevant content
  authored from scratch (the Soleda/Dana JSON is a *shape* reference, not a content
  source — its content is for a different product). The existing
  `database/guides/faq_guide.md` becomes the source-of-truth doc that the JSON is
  generated from (or vice versa — see search.md).
- **Reference data source = LLM-knowledge** for v1 — no WordNet / WordsAPI dependency.
  GPT/Claude know dictionary definitions, synonyms, and antonyms well enough for
  blog-writing assistance. Migrate to WordNet later if quality bites.
- **Internal flows excluded from NLU stays correct.** Confirmed at `nlu.py:381`. We
  reach Search/Reference only via `flow_stack.stackon()` from inside `chat_policy`.
  Users typing "search the FAQ" still hit Chat first; the router promotes the dispatch.
- **No TaskArtifact surfaced from sub-flows.** Internal flows return empty frames
  (`res.py:29` returns `('', frame)` for INTERNAL intent), so the user only sees
  Chat's final composed response in the second pass. This is correct behavior — Search
  and Reference are advisors, not narrators.

## Decisions to confirm

These are open enough that I want a yes/no before phase 3 starts. Phases 1 and 2 don't
depend on these answers.

1. **Router placement.** Inline LLM call in `chat_policy`, or extract to a helper like
   `build_chat_dispatch_prompt` in `backend/prompts/pex/support/converse_prompts.py`
   (mirroring `revise_prompts.py`)? My default is the helper — easier to test the
   prompt in isolation.
2. **FAQ corpus authoring.** Want me to seed `database/faq_data/faqs.json` with a
   dozen Hugo-specific entries during phase 1, or do you want to write them yourself
   and have me build only the retrieval plumbing?
3. **Should "direct" responses still be allowed to call `find_posts`?** Today
   `chat_policy` has no tools. If the user asks "do I have a post on auth?", Chat
   could either route to a *Find*-flow-like search, route through a new "find_posts"
   in chat's tool list, or stay tool-less and answer "I don't know — try /find".
   Cleanest is *route to find*, but that means the router has 4 options. Default for
   now: keep router 3-way and Chat tool-less; add Find as a 4th branch later if
   users want it.

## Integration (Phase 4)

After phases 1–3 land, verify end-to-end via three flavors of input:

1. **Search branch** — "What can Hugo do for me?"
   - Router classifies → `search`. Stack pushes `SearchFlow`.
   - Inner loop: `search_policy` runs, retrieves matching FAQ entries, writes
     `{'matches': [...], 'summary': '...'}` to scratchpad under key `'search'`,
     completes.
   - Outer loop: `chat_policy` re-enters in stage `'post_dispatch'`, reads scratchpad,
     composes a natural-language response grounded in the matched FAQ answer.
2. **Reference branch** — "What's a synonym for 'important'?"
   - Router → `reference`. Stack pushes `ReferenceFlow`.
   - `reference_policy` runs the LLM dictionary lookup, writes
     `{'word': 'important', 'synonyms': [...], 'definition': '...'}` to scratchpad
     under key `'reference'`, completes.
   - Chat resumes, surfaces the synonyms in a clean conversational reply.
3. **Direct branch** — "Tell me a joke about marketing."
   - Router → `direct`. No stackon. `chat_policy` runs the existing single-LLM-call
     path and returns the response.

Verification commands (after each phase, then at the end):

```bash
# Free tier — must stay green throughout
pytest utils/tests/unit_tests.py utils/tests/test_artifacts.py

# NLU accuracy — only relevant if NLU prompts changed (they should NOT for this work)
pytest utils/tests/model_tests.py -m llm

# E2E (real LLM) — add a 3-scenario chat_dispatch eval to e2e_multiturn_evals.py
pytest utils/tests/e2e_multiturn_evals.py -v -k chat_dispatch
```

## File inventory across all phases

Phase 1 (search):
- `backend/modules/policies/internal.py` — rewrite `search_policy`
- `backend/utilities/post_service.py` (or new `faq_service.py`) — FAQ retrieval helper
- `backend/modules/pex.py` — register the FAQ tool
- `schemas/tools.yaml` — add `search_faqs` tool entry
- `database/faq_data/faqs.json` (new file) — corpus
- `utils/tests/unit_tests.py` — coverage for retrieval helper

Phase 2 (reference):
- `backend/modules/policies/internal.py` — rewrite `reference_policy`
- `backend/prompts/pex/support/converse_prompts.py` (new) — reference lookup prompt
- `utils/tests/unit_tests.py` — covers prompt-shape lint

Phase 3 (internal-flow dispatch from Chat):
- `backend/modules/policies/converse.py` — rewrite `chat_policy` with two stages + router
- `backend/components/flow_stack/flows.py` — add `stage` attribute usage on `ChatFlow`
- `backend/prompts/pex/support/converse_prompts.py` — add
  `build_chat_dispatch_prompt` + `CHAT_DISPATCH_SCHEMA`
- `utils/tests/e2e_multiturn_evals.py` — 3-branch dispatch scenario

No frontend, no NLU, no new components.

## Risks

- **Router false positives on Search.** "What can you do?" is unambiguous; "tell me
  about your features" is borderline. The router prompt needs strong enough
  *examples* to generalize. Empirical — eval will show.
- **FAQ corpus quality.** A 12-entry seed is enough to demonstrate the pipeline but
  too thin for production. Plan for an expanded corpus authored from real user
  questions over the next few sessions.
- **Reference quality from LLM-only knowledge.** Modern LLMs are reliable on common
  English vocabulary but can hallucinate on rarer words. v1 ships with no validator;
  if eval shows hallucination rates above ~5%, escalate to WordNet.
