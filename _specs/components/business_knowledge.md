# Business Knowledge

[MEM](../modules/mem.md)'s **L3** Level — the closest equivalent to RAG. It holds unstructured data the user
has provided (messages, PDFs, documents, emails, Slack threads, call transcripts) that explains business
decisions, product launches, and contextual events. It is most commonly used for **answering FAQs**. Scope is
the client organization, shared across that tenant's users. Sub-agents reach this Level through MEM's
**`retrieve`** skill (KB + vector-DB retrieval).

## Storage Format

Documents are embedded in a shared vector space.

| Component | Approach |
|---|---|
| Chunking | Needs design for optimal chunk size and overlap |
| Embedding | Optimize for precision and recall |
| Retrieval | Vector search returning ~100 candidates |
| Re-ranking | Reduce to top 10 documents for the context window |

- **Retrieval**: triggered via an explicit tool call (not every turn). Tenants may share anonymized industry
  patterns.
- **Write triggers**:
  - Ingestion from connected data sources (docs, email, Slack, call transcripts)
  - Manual upload to `agent.md` (solves cold-start, similar to Claude Code's agent.md)
  - Promotion from the [Session Scratchpad](./session_scratchpad.md) for salient patterns
