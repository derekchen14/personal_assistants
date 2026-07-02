# Step 1 — The 64-conversation seed

The hand-generated core of the Train set (`step_1_evals.md` → Dataset coverage funnel). **64 = 4 personas ×
8 use cases × 2 topic clusters.** Uniqueness comes from three orthogonal axes: the **persona** sets tone +
ambiguity, the **use case** sets the 4-turn flow sequence, the **topic** sets the subject. Each conversation
is **7 turns** (4 user + 3 agent) in the `test_cases.json` shape (`convo_id`, `available_data`, `turns[]` with
`labels{intent,flow,dax}`, `slots`, `expected_tools`, `rubric`).

Scenario ID = **`P{1-4}.U{1-8}.T{1-2}`** (persona · use case · topic).

---

## Axis 1 — Personas (tone + focus)

| # | Persona | Tone | Ambiguity |
|---|---|---|---|
| **P1** | Clear sense of what they want | warm, **conversational**, full sentences | low |
| **P2** | Clear sense of what they want | **terse, business** imperative; few words | low |
| **P3** | *Some* sense — **needs hand-holding** | hesitant, vague, asks the agent to decide | **high** — the ambiguity persona |
| **P4** | Good sense but **absent-minded** | fluent but **changes direction** mid-conversation | medium (mid-task switches) |

**P3 across all 8 use cases × 2 topics = 16** — exactly the funnel's *ambiguity-recovery core*. P4 adds a
direction-change on one turn; P1/P2 are the clean happy paths in two tones.

## Axis 2 — Use cases (the 4-turn flow sequence)

The use case names the intents; the **proposed flow per turn** is below (to confirm — flows are from the
16-flow catalog). `[Clarify]` = an intentionally ambiguous user turn the agent must recognize and recover from
(NLU-only, no flow).

| # | Use case | Turn 1 | Turn 2 | Turn 3 | Turn 4 |
|---|---|---|---|---|---|
| **U1** | Draft → Draft → Revise → Revise (standard blogging) | `outline` `{002}` | `compose` `{3AD}` | `write` `{003}` | `audit` `{13A}` |
| **U2** | Draft → Revise×3 (editing-heavy) | `compose` | `rework` | `audit` | `propose` |
| **U3** | Research → Draft → Revise → Publish (basic E2E) | `find` `{001}` | `outline` `{002}` | `write` `{003}` | `release` `{004}` |
| **U4** | Draft + Converse | `chat` | `brainstorm` | `outline` | `chat` |
| **U5** | Research + Draft + **Clarify** | `browse` | `[Clarify]` | `outline` | `compose` |
| **U6** | **Plan** → Draft phase | `Plan` | `outline` | `compose` | `refine` |
| **U7** | **Plan** → Research phase | `Plan` | `find` | `summarize` | `compare` |
| **U8** | Draft + Revise + **Clarify** | `compose` | `[Clarify]` | `rework` | `audit` |

Clarify appears explicitly in **U5 + U8** (all personas) and pervasively under **P3**.

**Parked (not in the seed):** the alternate **Research → Research → Draft → Draft** opener
(`browse → summarize → outline → compose`) — kept for a later expansion, not one of the 8 seed use cases.

## Axis 3 — Topics (2 clusters, sub-topic per cell)

- **T1 — Tech / AI-infra:** Observability, OpenTelemetry, Traces, LLM Evals, Red-teaming, Security
- **T2 — History of electricity:** Edison, Lightbulb, Bringing Electricity to Homes, Electric vs Diesel Cars,
  Street Lamps

One sub-topic is assigned per **(use case × cluster)** so all 4 personas of a cell share a subject (tone
varies, topic doesn't). Proposed assignment:

| Use case | T1 sub-topic | T2 sub-topic |
|---|---|---|
| U1 | Observability | Edison |
| U2 | OpenTelemetry | The Lightbulb |
| U3 | LLM Evals | Bringing Electricity to Homes |
| U4 | Traces | Street Lamps |
| U5 | Red-teaming | Electric vs Diesel Cars |
| U6 | Security | Edison's workshop |
| U7 | LLM Evals (compare frameworks) | The Lightbulb (rival inventors) |
| U8 | Observability dashboards | Electric vs Diesel Cars |

---

## Per-scenario format

Each scenario is one block; user turns carry the full label set, agent turns carry a response gist. This maps
1:1 to `test_cases.json` (a user turn → `{utterance, labels, slots, expected_tools, rubric}`; an agent turn →
`{role: agent, utterance}`). `completion` notes the per-turn expected primary flow and any ambiguity recovery.

---

## Exemplars (format anchors)

### P1.U1.T1 — clear+conversational × standard blogging × Observability  *(happy path)*

A fresh post built end-to-end: outline → compose → revise → audit. No seeded data.

1. **User → `outline` ({002}):** "Hey! I want to write a post on observability for LLM apps. Let's start with
   an outline — intro, traces vs logs, instrumenting with OpenTelemetry, and takeaways."  · slots
   `{source: {post: "Observability for LLM Apps"}, sections: [...]}` · tools `[generate_outline]`
2. **Agent:** "Outline ready: 1) Why observability matters 2) Traces vs logs 3) Instrumenting with
   OpenTelemetry 4) Takeaways."
3. **User → `compose` ({3AD}):** "Love it — turn that into a full first draft."  · slots
   `{source: {post: "Observability for LLM Apps"}}` · tools `[convert_to_prose]`
4. **Agent:** "Drafted all four sections — the instrumenting one came out a bit thin."
5. **User → `write` ({003}, Revise):** "Yeah, flesh out the instrumenting section with a concrete
   OpenTelemetry tracing example."  · slots `{source: {post: "…", sec: "Instrumenting with OpenTelemetry"}}` ·
   tools `[write_text]`
6. **Agent:** "Expanded it with a span-instrumentation example."
7. **User → `audit` ({13A}, Revise):** "Nice. Do a quick quality pass on the whole post — readability and any
   gaps?"  · slots `{source: {post: "Observability for LLM Apps"}}` · tools `[editor_review]`

*completion:* primary flows `outline → compose → write → audit`; no ambiguity; all four activate.

### P3.U5.T1 — hand-holding × Research+Draft+Clarify × Red-teaming  *(ambiguity-recovery core)*

`available_data`: notes `{Prompt injection basics, Red-team playbook}`.

1. **User → `browse`:** "I think I want to write about… security stuff for AI? Maybe red-teaming? Can you see
   what I have?"  · slots `{query: "AI security"}` · tools `[search_notes]`
2. **Agent:** "I found 2 related notes: *Prompt injection basics* and *Red-team playbook*. Are you leaning
   toward red-teaming specifically, or AI security broadly?"
3. **User → `[Clarify]`** (ambiguous draft request): "Let's just draft it."  → **agent must recognize the
   ambiguity** (which topic? what post?) and ask, not guess.  · expected: `handle_ambiguity(declare)`
4. **Agent (clarify):** "Happy to start — should the post focus on **red-teaming** specifically, titled
   *A Red-Team Playbook for LLM Apps*?"
5. **User → `outline`** (resolves): "Yes, red-teaming, that title's good. Outline it."  · slots
   `{source: {post: "A Red-Team Playbook for LLM Apps"}}` · tools `[generate_outline]`
6. **Agent:** "Outline: 1) Threat model 2) Attack catalog 3) Running a red-team 4) Fixing what you find."
7. **User → `compose`** (still leans on the agent): "Okay um… write the first part? Whatever you think is
   best."  · slots `{source: {post: "A Red-Team Playbook for LLM Apps", sec: "Threat model"}}` · tools
   `[convert_to_prose]`

*completion:* primary flows `browse → (clarify) → outline → compose`; **the agent recovers from the turn-2
ambiguity by asking a concrete question; recovery completes at turn 5.** This is what the ambiguity core tests.

---

## How we fill the rest (iteration plan)

1. **Confirm the framework** — the U1–U8 flow sequences, the sub-topic grid, and the format above.
2. **Fill by use case, both topics, all 4 personas** (8 conversations per use case) — so each batch reuses one
   flow sequence and we just re-voice it across personas/topics. U1 and U5 are seeded above (P1/P3); we add the
   other personas + T2.
3. **Convert to `test_cases.json`** under `utils/evals/datasets/scenarios/` once a batch is locked.
4. **Reconcile the funnel labels** in `step_1_evals.md`: the ambiguity core = P3 × 8 × 2 = 16 ✓; the E2E-32 =
   the two most-collaborative personas × 8 × 2 (the funnel currently says "× 4 topics" — should read "× 2").

Progress: **2 / 64** drafted (P1.U1.T1, P3.U5.T1).
