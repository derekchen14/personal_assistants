# User Preferences

[MEM](../modules/mem.md)'s **L2** Level — what the user normally wants, the good defaults that override the
agent's baseline behavior. This is the closest equivalent to Claude's memory: coding conventions, response
verbosity, technical depth. Scope is a single user account; preferences persist across all conversations and
are frozen into PEX's system prompt (tier 3) at session start. Sub-agents reach this Level through MEM's
**`recall`** skill.

## Storage Format

Key-value pairs where the key is found by:

| Key Type | Description |
|---|---|
| Graph search | Semantically designed vector with discrete hops |
| ID | Explicit identifier for known flows where a preference always applies |

Values are discrete rules (lambda functions) that modify agent behavior when triggered — effectively binary:
either applicable to the current situation or not.

- **Retrieval**: Hybrid lookup — embedding similarity for open-ended situations, direct ID lookup when inside
  a known flow. Latency target: sub-second, 1 second maximum.
- **Write triggers**:
  - User onboarding (like Netflix seeding recommendations, or Lyft distinguishing drivers from riders)
  - Promotion from the [Session Scratchpad](./session_scratchpad.md) when patterns are detected
  - Explicit user configuration
- **Example**: user persona classification (data practitioner, data savvy, data consumer) determines response
  verbosity and technical depth.

Domain config defines the available preference types as a starting point (e.g., analysis depth, time horizon);
the runtime values stored are the source of truth.

## Typed Preference Record

A stored preference is more than a bare value — it carries the metadata needed to apply it *at the right
confidence*. This is the structured form behind the key→value mapping above; a plain string preference is just
the degenerate case (`endorsed=True`, `confidence=1.0`, no candidates), so the simple store still works.

| Field | Meaning |
|---|---|
| `value` | the current setting (the chosen default) |
| `endorsed` | `True` if the user confirmed it; `False` if the agent inferred it from behavior |
| `rankings` | ordered candidate values, each with a short `detail` — the runner-up defaults |
| `triggers` | keywords that surface this preference on the current utterance (a cheap relevance gate) |
| `confidence` | `[0,1]`, nudged by feedback (a learning-rate update on each confirm / correction) |

**Endorsed-vs-tentative rendering is the important part.** `render()` produces the prompt fragment, and the
phrasing turns on `endorsed`:

- **Endorsed** → a standing instruction: *"Remember, the user wants {value}."*
- **Guessed (un-endorsed)** → a tentative default the user can override: *"If the user hasn't said otherwise,
  assume {value} — but confirm if it matters."*

So an inferred preference is applied *as a default* before the user confirms it, then *authoritatively* once
endorsed. Feedback moves a preference along that path: repeated confirmation raises `confidence` and flips
`endorsed`; a correction lowers `confidence` and may promote a `rankings` runner-up.

**Determinism note.** Preferences are frozen into PEX's system prompt at session start (tier 3), so `render()`
output must be stable for a given record and emitted in sorted key order — otherwise the prompt-cache key
churns. Mid-session writes apply next session, as today. The typed record is an enrichment of the existing L2
store, **not** a parallel state component.

## Caution / Risk Tolerance  *(specified, not yet wired)*

One preference type is reserved for a user-tunable **caution dial** — how cautious the agent is about acting
versus checking in. It is a normal typed preference whose `value` is one of three levels:

| Level | Meaning |
|---|---|
| `ignore` | proceed on reasonable guesses; surface only the most severe issues |
| `warning` | the balanced default; ask when a key entity or required slot is unresolved |
| `alert` | confirm aggressively; surface even minor issues before acting |

The intent is to make **ask-vs-proceed** and **how aggressively to surface issues** a user setting rather than a fixed
constant. This release **defines the shape only** — the dial is **not yet read** by the
[Ambiguity Handler](./ambiguity_handler.md)'s `nlu_confidence_min` threshold or by detector/audit strictness.
Wiring is deferred so the record shape can be reviewed before any behavior changes. When wired, `alert` would
raise the clarification threshold and loosen the issue-surfacing cutoffs; `ignore` would do the reverse.

_(Trajectory playbooks were considered for this Level and dropped — not part of the design.)_
