# Template ontology + tally

A *template* is a loose, human-judged rhetorical pattern of a USER turn (how it is phrased/structured),
NOT its topic and NOT its flow/intent label. Method: design an ontology, classify all 256 user turns with an
LLM judge (Sonnet), inspect misfits, refine the ontology, re-classify. Repeat until it converges (small/empty
"Other", no mega-bucket). Goal after convergence: rewrite so no template appears > 4 times.

## Ontology v1 (decision order, most specific first)

- **T07 redirect** — mid-sentence direction change ("...actually no, scrap that..."). Ex: "Fix the exporters bit. Actually no, spans and traces is the real mess. Rebuild that."
- **T14 handoff+tip** — take the work over from here + ask for advice. Ex: "That's great. Any parting tips?" / "I can take it from here."
- **T08 multi-step plan** — one sequenced request of several steps. Ex: "Gather the sources, brief me on one, then weigh the two."
- **T16 post-spec** — name a post + list its sections. Ex: "New post 'A Practical Guide to LLM Evals' with these parts: ..." / "Block it into intro, traces vs logs, instrumenting, takeaways."
- **T15 comparison-Q** — ask how X and Y compare. Ex: "So where do DeepEval and Promptfoo differ?"
- **T10 worth-it floater** — float a topic and question its merit. Ex: "Distributed tracing, worth a post?" / "Real readership, or too niche?"
- **T09 retrieval** — ask what exists / pull up notes. Ex: "Anything in the library on LLM evals?" / "What do I have saved on red-teaming?"
- **T06 explicit defer** — hand the choice to the agent (statement). Ex: "Your call on Spans and traces." / "Whichever's best, I'm easy. You pick."
- **T05 hesitant defer-Q** — tentative question that hands the decision to the agent. Ex: "Worth fleshing into a draft?" / "Could we just make a start?"
- **T04 diagnosis+fix** — name a weak section/problem, ask to fix. Ex: "The instrumenting section's thin. Drop in an example." / "The metrics part came across as vague."
- **T12 selection** — pick among offered options. Ex: "Number three." / "Go with the first. Lay out its sections."
- **T13 approval+2 commands** — react + two chained commands. Ex: "Good. Run an editing pass and tell me what's left."
- **T01 approval+1 command** — react + one next-step imperative. Ex: "That works. Pull the sections into prose."
- **T02 bare command** — verb-led imperative, no opener. Ex: "Reorder Swan's work first." / "Comb the whole post."
- **T03 noun-fragment** — noun-led, no verb, names the next deliverable. Ex: "Full prose now." / "Security post, sections first."
- **T11 reaction-only** — just a reaction; request implied or closing. Ex: "Spot on." / "yeah" / "Good, that's plenty. Off I go."
- **T17 constraint/goal** — states a constraint or quality bar. Ex: "Keep it under a page." / "Punchy intro, no filler."
- **T18 approval+content-question** — react, then a concrete content question (not a command, not a defer). Ex: "Looks good. Should the problem come before the fix?"
- **T19 quantified/spec ask** — a request carrying a number or spec. Ex: "Two examples in the metrics part." / "Trim it to three sections."
- **T20 conditional suggestion** — a tentative "maybe/if" suggestion. Ex: "Maybe a diagram up top?" / "If it helps, add a TL;DR."
- **T21 gratitude/sign-off** — thanks or closing, no advice ask. Ex: "Perfect, thanks. That's me for today."
- **T22 urgency/time framing** — frames by time or urgency. Ex: "Let's get this out today." / "Quick pass before I run."
- **T23 worry-led** — leads with a concern, no explicit fix command. Ex: "My worry is the intro drags." / "Not sold on the ending."
- **T24 audience/goal check** — asks whether it serves the reader/goal. Ex: "Does this land for a beginner?"
- **Other** — genuine misfit (drives the next ontology refinement).

## Tally by turn (Sonnet judge, v1 ontology — 0 "Other", converged first pass)

Cap = 4 per turn. ⚠ = over cap. To get every template <=4 at a turn, that turn's 64 utterances must spread
across >=16 templates; today each turn uses only 8-10, so the dominant ones must be re-voiced into rarer shapes.

Round-1 baseline (before any variety rewrite) worst buckets per turn: t1 T09=13, t3 T01=17, t5 T01=15,
t7 T01=19. Two rewrite rounds + a slot-fidelity guard later, the round-3 judge (24-template ontology) gives:

### Round-3 over-cap (>4) by turn
- **Turn 1:** T02 bare-cmd 8 · T09 retrieval 7 · T10 worth-it 7 · T16 post-spec 5
- **Turn 3:** T03 noun-frag 10 · T09 retrieval 5 · T13 approval+2cmd 5 · T23 worry-led 5
- **Turn 5:** T01 approval+1cmd 8 · T04 diagnosis 6 · T06 defer 6
- **Turn 7:** T01 approval+1cmd 9 · T02 bare-cmd 7 · T15 compare 6 · T05 defer-Q 5

Worst-bucket-per-turn fell 16/17/15/19 → 8/10/8/9; active templates 8 → 24. Fully fixed since round 1:
T08 plan (t1 16→4), T03 noun-frag (t5 12→4), T07 redirect (t5 11→4), T01 (t3 17→3), T04 (t3 11→3).

### Why it asymptotes (structural floors)
Each (turn position) packs 8-16 turns of one use-case speech act, and the judge classifies by speech act, so
surface variety re-collapses. Two are hard floors that cannot reach <=4 without changing labels/flows or
dropping a slot:
- **T16 post-spec (~5, t1)** — U1 fresh-post openers must list their `sections` (the labeled slot).
- **T15 compare (~6, t7)** — U7 IS the compare flow; any "X vs Y" reads as comparison.
The rest (T01/T02/T03/T09/T10/T04/T06/T13/T23/T05) are soft magnets: reducible with more rounds but at rising
cost to naturalness and slot drift, never cleanly below the number of turns that genuinely share that act.

### Correction: template grain is the SENTENCE STRUCTURE, not the speech act
The "floors" above were an artifact of classifying too coarsely. A speech act splits into many sentence-
structure templates, and the cap-4 applies at that finer grain:
- **compare** = question-comparing-A-and-B / "A vs B" + comment / "A vs B" + question / reaction + follow-up
  comparison-Q (the six U7 closers are really 4 templates, max 2 each — already under cap).
- **post-spec** = inline ordered list / narrated list with fillers ("Start with an intro of course. Then...") /
  possessive-parallel ("his early years, his inventions, his legacy") / list without naming the post or topic /
  count-led. Plus content levers: vary the section COUNT (4 vs 5), the section LABELS, and the ORDER. You do
  NOT have to name the post, list exactly the canonical sections, or keep them in order.
Same for the other magnets (approval+command, noun-fragment, retrieval, worth-it, diagnosis, defer): each is
several sentence structures. Round 3 re-voices the genuine same-structure repeats into distinct structures and
exploits these freedoms; the cap is then enforced per sentence-structure.
