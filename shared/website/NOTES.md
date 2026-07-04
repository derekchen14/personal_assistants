# Assistant Factory — Marketing Site Notes

Operational notes, story brainstorm, and deployment cheatsheet for the marketing
site that lives in `shared/website/`.

## Current files

| File | What it is | Status |
|---|---|---|
| `index.html` | Baseline — kitchen-sink content, elevated design (Fraunces + Geist + vermilion) | ready |
| `theory_of_mind.html` | Story 1 — agents with a model of you, the conversation, your domain | ready |
| `ambiguity_bottleneck.html` | Story 2 — three flavors of unclear (contextual/temporal/communication) | ready |
| `beliefs_not_prompts.html` | Story 4 — explicit beliefs vs implicit context windows | ready |
| `NOTES.md` | This file | living |

The user reviews all four pages and gives feedback on which story lands.

## Deployment — Netlify (drag and drop)

We ship this as a static site via Netlify's drag-and-drop UI.

1. Open <https://app.netlify.com/drop>.
2. Drag the entire `shared/website/` folder onto the page.
3. Netlify gives you a temporary `*.netlify.app` URL.
4. To promote to a real domain: claim the site (sign in), open **Site
   settings → Domain management**, point a custom domain at it.

To re-deploy after edits: drag the folder again. Netlify versions each drop;
old URLs keep working until you delete them.

There's no build step — the HTML files are self-contained (Tailwind via CDN,
fonts via Google Fonts, no JS bundle). If we ever need a build, switch to
Netlify CLI or git-based deploys.

## Hard constraints we've agreed on

- **3 new concepts max** per page. One major theme; the rest is plain English.
- **Audience**: technical hiring managers, AI engineers, Applied Scientists,
  Senior MTS. Skim 5 seconds → maybe stay 5–10 minutes if hooked.
- **Brand**: just "Assistant Factory" for now. Soleda not surfaced.
- **Names allowed**: Hugo (blog), Dana (data), Rowan (recruiting), Kalli
  (onboarding). Use sparingly.
- **Allowed component names**: Ambiguity Handler, Context Coordinator,
  Dialogue State, Memory Manager, World Model. Pick a subset; don't list all.
- **Excluded component names**: Display Frame, Prompt Engineer, Flow Stack.
- **Excluded module names**: NLU, PEX, RES — internal jargon, do not surface.
- **Avoid words**: "tighten", "delve" (per CLAUDE.md).

## The technical anchor sentence

> "Our assistants have a World Model which enables Theory of Mind, made
> possible through an NLU module which tracks the degree of ambiguity in a
> situation in a dedicated dialogue state."

This is the connective tissue. Each story foregrounds a different part of it.
Public-facing copy should not say "NLU module" — say "understanding module" or
similar.

## Storylines considered

### Story 1 — Theory of Mind  (recommended)

- **Pitch**: Most agents read your message; ours read the room.
- **A/B/C**: Model of *you* / model of *the conversation* / model of *your domain*.
- **Strengths**: brand-able, sticky phrase; differentiates from ReAct in a single line.
- **Risks**: phrase carries cog-sci baggage; "models your domain" is the squishy pillar.
- **File**: `theory_of_mind.html`

### Story 2 — Ambiguity Is the Bottleneck

- **Pitch**: Code either runs or it doesn't. Real work doesn't.
- **A/B/C**: Contextual / Temporal / Communication ambiguity (from the blog post).
- **Strengths**: aligned with published thesis; viscerally true for any IC who has shipped agents.
- **Risks**: A/B/C are *problems*, not *solutions*; risks reading like a diagnosis without a cure.
- **File**: `ambiguity_bottleneck.html`

### Story 3 — Built for the Long Conversation  (rejected)

- **Pitch**: Most agents are built for one shot. Ours are built for the long conversation.
- **Why we passed**: not defensible IP; anyone with a memory layer could claim it.

### Story 4 — Beliefs, Not Prompts

- **Pitch**: Most agents are a prompt and a while loop. Ours track explicit beliefs.
- **A/B/C**: What we believe / what we remember / what we don't know.
- **Strengths**: maximum technical credibility; cleanest engineering signal for AI engineers.
- **Risks**: cold framing; less viral than Theory of Mind.
- **File**: `beliefs_not_prompts.html`

## What "make them care" looks like

The audience already has 20 agent SDKs in their browser tabs. They are skim
readers by default. To earn a 5–10 minute read, every page needs:

1. A hook in the first two seconds that names a pain they recognize.
2. A specific defensible claim no other framework makes.
3. Evidence we've thought harder than the competition (the depth signal).
4. A concrete payoff — what does this unlock that ReAct can't?
5. One memorable line they'll quote later.

## Open questions / parking lot

- Do we want a single canonical page or a "pick your framing" landing page
  that links to multiple essays?
- Should the four assistants (Hugo, Dana, Rowan, Kalli) get their own pages
  eventually, or stay as a "the line" callout?
- The blog at morethanoneturn.com is the proof point — should we link out
  more aggressively, or quote/embed key paragraphs in-page?
- Eventual CTA: book a demo? sign up? GitHub? Decide once we know which
  story wins.

## Inputs we're drawing from

- `_specs/architecture.md` — modules, components, World concept
- `_specs/components/ambiguity_handler.md` — four levels (general, partial,
  specific, confirmation)
- `_specs/components/memory_manager.md` — three-tier cache hierarchy
- `assistants/Hugo/README.md` — 10-step workflow, CRUD matrix
- <https://morethanoneturn.com/2025/08/07/ambiguity-is-the-bottleneck.html>
- <https://morethanoneturn.com/2026/03/23/beyond-guardrails.html>
