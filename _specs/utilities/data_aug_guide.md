# Seed conversation generation spec (for the generator agents)

Generate hand-quality seed eval conversations for **Hugo** (a blog-writing assistant). The full set is
64 = 4 personas × 8 use cases × 2 topic clusters. You own ONE use case (given in your task) and write its
conversations across the 4 personas × 2 topics.

## Read first
- `/Users/derekchen/Documents/repos/personal_assistants/_specs/_review/step_1_seed_scenarios.md` — the design.
- **The whole `scenarios/` folder is the exemplar bank.** There are no separate exemplar blocks; the manual
  conversations are the exemplars. Read several to absorb the *voice and quality bar* only.
- **Do not overfit to the exemplars.** They are a quality bar, not templates to copy. Reusing their sentence
  shapes is the main failure mode. At this stage we want *more* structural diversity than the current set has,
  not less. Invent genuinely different phrasings.

Append each conversation as one JSON line to `utils/evaluation_suite/datasets/train.jsonl`.

## JSON shape (7 turns = 4 user + 3 agent)
```jsonc
{
  "convo_id": "P{p}.U{n}.T{t}",
  "persona": "...", "use_case": "...", "topic": "...", "title": "<the blog post title>",
  "available_data": {  /* posts/notes the turns reference; {} if the conversation starts a fresh post */
    "posts": [ { "post_id": "...", "title": "...", "status": "draft",
                 "sections": { "<section-name>": "<section prose>" } } ],
    "notes": [ /* separate key, unchanged */ ]
  },
  "turns": [
    { "turn_count": 1, "role": "user", "utterance": "...",
      "labels": { "intent": "...", "stack": [ { "flow": "...", "dax": "{...}" } ] },
      "slots": { /* e.g. source:{post|note,sec}, query, sections, channel */ } },
    { "turn_count": 2, "role": "agent", "actions": ["..."],
      "utterance": "<short realistic reply that sets up the next user turn>" }
    /* ...user 3, agent 4, user 5, agent 6, user 7, closing agent 8 (actions only) */
  ]
}
```
- **Canonical `posts` shape (approved 2026-07-03):** every entry is
  `{"post_id": str, "title": str, "status": str, "sections": {"<name>": "<prose>", ...}}` — the exact
  `_seed_post` contract. Sections map names to real prose (never a bare name list); `notes` stays its own
  key. Legacy shapes in older batches (bare title strings, dicts without `sections`, `sections` as a name
  list) are upgraded on read by `_normalize_post` in `run_evals.py` until the next regeneration batch
  rewrites them — new batches must emit the canonical shape directly.
- User turns (1,3,5,7) carry `labels`/`slots`/`ambiguity`. Each agent turn carries `actions` — the ordered
  domain tools that complete the PRECEDING user request — plus a short utterance. The conversation ends with a
  closing agent turn holding `actions` only (its ground-truth reply is unauthored until a future batch).
- **`labels` is always `{intent, stack}`**, where `stack` is an ordered list of `{flow, dax}` entries. MOST
  turns have a ONE-item stack (a single flow). There is no separate top-level `flow`/`dax` — the label IS the
  stack. `intent` = the single flow's intent, or `"Plan"` when the stack has more than one flow.
- **Ambiguous turn:** `ambiguity` is a single value = the level (general|partial|specific|confirmation),
  `null` when not ambiguous (no boolean). `general` = the flow itself is unknown, so the `stack` is EMPTY and
  `intent` is null; `partial`/`specific`/`confirmation` = the flow is known but an entity/value is missing, so
  the one-flow stack stays. Both run NO domain tool — the agent asks, so the reply turn's `actions` is `[]` —
  plus a `"note"`. `clarify` is NOT a flow, and declaring ambiguity is NOT a tool: it rides the `ambiguity`
  level field, never `actions`. The agent's next reply asks a concrete question and the NEXT user turn
  resolves it. See axis 5.
- **Plan turn:** `labels {"intent":"Plan"}` whose `stack` holds the MULTI-flow decomposition (`[{flow,dax},
  ...]`), a reply turn with `actions []`, and a `"note"`. There is no separate `plan` flow — a plan is just a turn whose
  stack has more than one flow. The agent proposes the stack, shares its key steps, waits for the user's
  go-ahead, then runs it over the next turns.

## Rules (write like a real person, not an AI)
- **Sound human, not like an AI.**
  - No em-dashes, no ellipses (`…`), no Unicode tells. Restructure: split into two short sentences, or a comma.
  - No AI tells: no over-explanation, no "happy to" / "I'd love to", no needless politeness, no symmetrical
    triads, no restating what the agent just said.
  - Banned words: 'load-bearing', 'byte-identical', 'delve', 'genuinely', 'absolutely', 'tighten'.
    Greeting/filler openers ("Hey!", "Right,", "Okay so,") kept rare.
- **Keep turns SHORT.** Drop whole sentences; lean on shared context and anaphora; one move per turn; reactions
  are 1-3 words. The agent already knows the post and section, so the user rarely respells them. The bar
  (before → after):
  - "That's ready, ship it to the engineering blog." → "That's ready to ship!"
  - "Nice, now pull it into a full draft." → "Nice, full draft now."
  - "Time for an editor sweep on the Edison post, gaps flagged." → "Time for a sweep to flag the gaps."
  - "Yes, that's the cost one." (full hand-off) → "yeah"
- **Maximize variety.**
  - Fresh paraphrases, not synonym swaps. Carry the intent without naming the action ("Take a pass at the draft
    now.", "Check it over for voice issues."); find a genuinely different sentence structure.
  - No reused templates. A *template* is the loose rhetorical pattern of a turn (e.g. "agree + take over the
    writing + ask for a tip"), a human judgment, not a rule you can mechanize. No pattern recognizable more
    than ~4 times, and the two topics of a use case never feel the same. Turn 7 (the close) is the worst
    offender: vary the *move*, not just the words (name a worry, ask a question, react only, add a constraint,
    defer, approve flatly, compare to a goal).
  - Vary openings: not every turn starts with a verb, sometimes lead with a noun, subject, or hedge.
- **Phrase it like the user, not the system.**
  - Mostly avoid flow names in utterances. Users usually don't say the 16 internal flow names (find, browse,
    summarize, compare, outline, compose, refine, brainstorm, rework, write, audit, propose, release,
    schedule, cite, chat); express the intent with a natural synonym instead (outline → "sketch the
    structure"; compose → "turn it into prose"; audit → "give it a once-over"). ("draft" and "publish" are
    always fine; they aren't flow names.)
  - A flow name IS occasionally acceptable — the "easy case" — when it reads naturally and is NOT a bare
    command: an intent ("I want to write something on X"), a noun/artifact ("the outline is set"), or a
    natural question ("how's that compare to..."). Bare imperatives ("outline it", "write it up", "compare
    the two") should still be reworded. Cap these easy cases at ~1/8 of conversations: at most 2 per batch
    of 16.
  - Prefer anaphora ("it", "that one"), partial or fuzzy names, or position ("the second one"); this stresses
    the grounding layer.
  - **Say the post title rarely, or not at all.** The ground-truth title lives in the metadata; the agent
    already knows it. Establish the subject once at most, then use "it" / "the draft" / "the sections". Never
    repeat the title every turn (e.g. "the Menlo Park sections... the Menlo Park draft... the Menlo Park
    piece") — respelling it each turn is a machine tell.
- **Imply the intent, don't state it (the core surface-form rule for augmentation).** Real users almost never
  give a directly obvious command or name what they want done; they describe the PROBLEM or the FEELING and let
  the agent infer the flow. Reading implicit intent is the agent's job, so the utterance must leave room for it.
  Describe the problem, do not request the deliverable:
  - Good (implied): "there's a hole in the middle and I don't know what belongs there" -> propose.
    Bad (too direct): "give me some options for that gap".
  - Good: "does this even sound like me?" -> audit.  Bad: "run a voice pass on it".
  - Good: "the intro drags for a screen before it says anything" -> write/refine.  Bad: "trim the intro".
  Implicit is not the same as ambiguous: an implied intent can still be perfectly decidable (the hole line is a
  clean `propose`, not a `general`). When augmenting, push variants toward MORE implicit phrasing; never
  paraphrase into a blunter command.
- **Agent turns are the ground truth — keep them realistic.** The agent turn is the reference answer the
  model is graded toward, so it must model how the agent actually behaves.
  - It reports what it did and stops. It does NOT tack on unsolicited "Want me to X?" / "Sound good?" /
    "Should I look at the rest?" offers of next steps (a few across the whole set at most). It asks a
    question ONLY when the user was genuinely vague — a real clarification, not a proactive offer.
  - Its voice stays CONSTANT across every conversation. It never mirrors the user's persona: a terse or
    blunt user does not make the agent terse or telegraphic ("Drafted." / "Done." / "Restructured:").
- **Stay correct.**
  - Flow-logic sanity: the turn sequence must be physically possible (you cannot outline a post after it is
    already prose, or re-draft a published post).
  - Use the exact dax codes from your task. Slot values are carried by the utterance or clearly implied by
    immediate context (brevity allows anaphora). Titles are real blog titles from the sub-topic.
- **Review app (meta).** Each labeled turn shows as `flow {dax}` primary, intent secondary; verdicts are
  needs (red) / minor (yellow) / approve (green), saved under `datasets/feedback/`.

## Diversity Axes

Each axis is an independent knob that provides degrees of freedom for the generation pipeline.  We vary the axes to prevent the set from collapsing into a small number of repeated templates. A generated conversation should sample a value on every axis, most often just choosing the safe default. Choosing an axis does *not* mean applying that style on every turn in the conversation, but rather the style should show up somewhere in the conversation.

1. Template Structure: multiple surface renderings of the same intent/slots
  * Conversation level — an arc which occurs across multiple turns. Six shapes below are just a small sample of the possible variations. Ambiguity and Planning are particularly complex so they will get further details below.
    1) straight build: a linear happy path, no twist; each turn cleanly advances one task to done
      a. "outline it" ->  "draft it" ->  "give it a polish" ->  "ship it"
      b. "what's saved on heat pumps?" -> "good, sketch a structure from those" -> "now write it up" -> "publish to the home blog"
    2) redirect or backtrack: a cross-turn direction change; the user pivots to a different angle, emphasis, or scope
      a. "Fix the exporters bit." -> "Actually no, the traces section is the real mess, rebuild that."
      b. "Lead with cost." -> "On second thought, open with the payoff."
    3) User asks for options, which the agent provides. Then the user selects from the options:
      a. "give me a few title options" -> "the second one, that's it" -> "sections next"
      b. "what angles could this take?" -> "let's go with the contrarian one" -> "rough it out"
    4) iteration loop: the user circles the same deliverable across turns until it lands
      a. "draft it to sound like a human" -> "not there yet, another pass to get rid of AI slop keywords" -> "closer, but we should get rid of short punchy phrases too"
      b. "rework the intro" -> "still flat, make it punchier" -> "better, now trim the second line" -> "yeah, that's it"
    5) Ambiguity: there are many sources of uncertainty, but the shape typically involves asking clarification questions (more details below)
      a. "fix the post" -> "the Edison one, the intro specifically"
      b. "make it better" -> "I mean the tone, it's too stiff right now"
    6) Planning: a task is so complex that it needs to be broken down before being acted on
      a. "turn my notes into a full published series" -> "yep, that plan works, start on part one"
      b. "I need a launch post, social blurbs, and a newsletter from this draft" -> "good breakdown, do them in that order"
    Other major arc variations blur into later axes: Ambiguity / Clarify (axis 5), Planning / Plan (axis 6),
    and use-case or flow mixes (axis 3).
  * Turn level — the loose rhetorical shape of one user turn. A template is a human judgment, not a rule you can mechanize so descriptions are loose.
    1) Command: a direct verb-led instruction; the user has decided and tells the agent exactly what to do
      a. Approval prefix: "That works, pull the sections into prose.", "Looks good, give it a full draft."
      b. Bare command: "Reorder Swan's work first.", "Comb the whole post for gaps to clean up the slop.", "We should drop in another example since the section is a bit thin", "Keep it under a page.", "Trim it to three sections."
      c. Multi-command: "Run an editing pass and tell me what's left.", "Cut the intro and add a TL;DR."
    2) Noun-fragment: names the deliverable as a noun phrase with no verb; the action is implied by the noun
      a. 1 part: "Full prose now."
      b. 2 parts: "Security post, sections first.", "Punchy intro, no filler."
    3) Implied recommendation: a hedged suggestion the user leaves for the agent to decide. Unlike Explicit recommendation, it still hints at a preference
      a. 1 part: "Worth fleshing into a draft?", "Could we just make a start?", "Maybe a diagram up top would look good."
      b. 2 parts: "Real readership here, or too niche?", "Distributed tracing, worth a post?", "If it helps, add a TL;DR."
      c. approval prefix: "I can take it from here, any parting tips?", "That's great, anything I should watch for?"
    4) Explicit recommendation: the user abdicates the choice entirely and names no preference of their own
      a. 1 part: "Your call on spans vs traces."
      b. 2 parts: "Whichever's best, you pick.", "Doesn't matter to me, both versions are fine"
    5) Question: seeks information or the agent's read. it expects an answer back, not an action
      a. What exists: "Anything in the library on LLM evals?", "What do I have saved on red-teaming?"
      b. Comparison: "So where do DeepEval and Promptfoo differ?", "Which holds up better for a small team?"
      c. Approval prefix: "Looks good. Should the problem come before the fix?", "Nice. Does the example belong up top?"
    6) Approval: a positive reaction; the next step is implied or the turn just closes, with no new instruction
      a. 1 part: "Spot on.", "Let's get this out today."
      b. 2 parts: "Great work, we're done here."
      c. 3 parts: "Good, that's plenty, off I go.", "Perfect, thanks, that's me for today."
    7) Rejection: a negative reaction; the user wants a different direction but names no fix, leaving the agent to infer the change (the mirror of Approval)
      a. 1 part: "My worry is the intro drags.", "Not sold on the ending."
      b. 2 parts: "Seem complicated, does this land for a beginner?"
    8) Selection: picks from options the agent already offered. It needs a prior menu, unlike a Noun-fragment that names something new
      a. 1 part: "Number three.", "Two examples in the metrics part."
      b. 2 parts: "Go with the first, lay out its sections."
    9) Explanation: implicit command due by explaining what is expected
      a. 1 part: "If the section is too long then readers won't even read it"
      b. 2 parts: "The use of words like 'load-bearing' and 'delve' stand out as clearly slop. 'byte-identical' is another obvious tell"
    10) Multi-step list: one turn requesting three or more ordered steps at once
      a. 3 items: "Gather the sources, brief me on one, then weigh the two.", "Pull my notes, draft an intro,
      flag what's missing."
      b. 4 items: "New post on LLM evals: intro, building a set, judging, takeaways.", "Block it into intro, traces vs logs, instrumenting, takeaways."
      c. 1 + 3 items: "We should set up the background first. Then we can go into inputs, processing, and outputs."
      d. 2 + 2 items: "First look into Angels and Dodgers. Then study the Lakers and Clippers."

  * Sentence level — re-voice one turn template into distinct sentence structures (these are the a/b/c
    sub-variants used above). A core move is either a few heterogeneous PARTS or an enumerated list of ITEMS,
    and an optional PREFIX or SUFFIX can wrap it. The cap-4 applies at this grain.
    1) prefix: a lead-in clause before the core move, usually a reaction that sets it up ("Nice, now sharpen the ending."); the mirror of suffix
    2) 1 part (default): the move stated once as a single clause or fragment, no enumeration ("Cost section next.")
    3) 2 parts: two heterogeneous clauses joined, not a list (a command plus an assessment tail: "Cut the intro, the rest's fine.")
    4) 3 parts: three such clauses in a row ("Love it, that's enough, I'm out.")
    5) 2 items (comparison): an enumerated list of exactly two, prototypically weighing A against B ("Roth or Traditional, which wins?")
    6) 3 items: a flat enumerated list of three ("cover the setup, the run, and the results")
    7) 1 + 3 items: one element set up first, then a group of three ("open with a hook to begin with. Next, I'd like to talk about the problem, fix, and proof of why it works.")
    8) 3 + 1 items: a group of three, then a single closing element ("setup, results, caveats, then a TL;DR to finish")
    9) 2 + 2 items: two elements, then a second pair ("first the why and the what, then the how and the cost")
    10) suffix: a trailing clause or modifier after the core move, like a time tail or a tacked-on ask ("wrap the draft by end of day")

2. Use case — the ordered sequence of flows, one dact per labeled user turn. This is the menu of plausible
   flow combinations to sample from. Composition can mix intents, mix flows within one intent, or let a single
   flow carry across turns to resolve.
  * Count: at least 4 flows for a 7-turn convo, 5 flows for a 9-turn convo. Clarify and Plan turns carry no
    flow, so a convo that uses one runs longer to still hit the count.
  * How these were chosen: sample a flow sequence, write a storyline, then have a separate LLM judge reject
    anything that goes backwards or isn't a common scenario. The list below is the survivors.
  * Plausibility rules the judge applied (the full space is 16^4):
    - Move forward through the pipeline Research -> Draft -> Revise -> Publish; don't go backwards.
    - Draft internal order is brainstorm -> outline -> refine -> compose. refine adjusts the OUTLINE, so it
      comes before compose, never after prose exists.
    - Revise and Publish flows act on prose, so they need a prior compose (or an existing draft pulled via find).
    - A flow may dwell at most twice in a row (one flow across two turns); three in a row is banned.
    - A session never opens on audit or summarize (awkward cold openers).
    - `browse` (search prior notes) rarely OPENS a session — `find` (pull past posts) is the usual research
      opener. `browse` reads more naturally MID-conversation: the user is drafting a post and pauses to check
      "what did I already jot down on X?" (see prior notes related to the post in progress). Keep browse-first
      openers to a small minority; place most browse beats in the middle.
    - `propose` most commonly fills a ONE- or TWO-WORD blank in existing content (a `<placeholder>`, a missing
      term, a name/number the writer left as a gap), not a whole-section rewrite. Its slots are `source`
      {post, sec} + `context` (what the blank needs); the preceding turn should surface the gap.
    - (edge_flows in ontology.py are the SIMILAR / confusable flows for a flow, NOT a transition graph.)
  * Flows by stage: Research {find, browse, summarize, compare}, Draft {brainstorm, outline, refine, compose},
    Revise {rework, write, audit, propose}, Publish {cite, release, schedule}, Converse {chat}.
  * Emphasis: the set centers on the outlining + writing process (Draft + Revise). Publish flows (cite,
    release, schedule) are kept sparse on purpose.

  The verified set lives in `use_cases.md` (128 unique, each with a full storyline). It was produced by the
  `verify-use-cases` workflow: write a storyline per case, strict + adversarial plausibility judging, prune,
  then backfill writing-centric candidates to 128 (deduped to 127). The compact seed list below is the input
  to that pass, kept here as a quick reference. Doubled flows (e.g. "write -> write") are one flow spanning two
  turns, common for audit, rework, write, outline, chat, refine, and propose. Each line is "flows : storyline":

  * New post, draft-led [14]
    brainstorm -> outline -> refine -> compose : take a raw idea through angles, structure, a tidied outline, then first prose
    brainstorm -> outline -> compose -> write : ideate, structure, draft prose, then fix a rough paragraph
    brainstorm -> brainstorm -> outline -> compose : push for more angles, then settle on a structure and draft
    outline -> refine -> compose -> write : structure a known idea, tidy the outline, draft, polish a line
    outline -> refine -> refine -> compose : structure, two rounds of outline tweaks, then draft
    outline -> compose -> compose -> write : structure, draft a long post across two passes, fix a line
    brainstorm -> outline -> compose -> audit : ideate, structure, draft, check it sounds like me not AI
    outline -> refine -> compose -> audit : structure, tidy, draft, then a voice check
    brainstorm -> outline -> compose -> rework : ideate, structure, draft, restructure a weak stretch
    outline -> compose -> write -> write : structure, draft, fix two paragraphs in turn
    brainstorm -> outline -> compose -> propose : ideate, structure, draft, fill a leftover gap with options
    outline -> refine -> compose -> rework : structure, tidy outline, draft, then a bigger rework pass
    brainstorm -> outline -> compose -> compose : ideate, structure, then draft a long post across two passes
    brainstorm -> outline -> outline -> compose : ideate, structure across two passes, draft
  * Research then draft [18]
    find -> summarize -> outline -> compose : pull a past post, condense it, structure a follow-up, draft
    browse -> brainstorm -> outline -> compose : scan saved notes for ideas, ideate, structure, draft
    find -> compare -> outline -> compose : pull two posts, compare their style, structure a new one, draft
    find -> summarize -> brainstorm -> outline : pull a post, condense, spin angles, structure the new piece
    browse -> find -> outline -> compose : browse ideas, pull a related post, structure, draft
    find -> find -> summarize -> outline : search a couple of past posts, condense, then structure
    browse -> brainstorm -> brainstorm -> outline : browse for gaps, ideate across two passes, structure
    find -> summarize -> compare -> outline : pull a post, condense, compare to another, structure
    browse -> brainstorm -> outline -> refine : browse, ideate, structure, tidy the outline
    find -> summarize -> outline -> refine : pull a post, condense, structure, tidy the outline
    find -> browse -> brainstorm -> outline : search posts, browse notes, ideate, structure
    find -> summarize -> summarize -> outline : pull posts, condense two of them, then structure
    find -> outline -> refine -> compose : pull a related post, structure a new one, tidy the outline, draft
    browse -> outline -> compose -> write : browse notes for an idea, structure, draft, polish a line
    find -> outline -> compose -> audit : pull a post, structure a follow-up, draft, voice check
    browse -> outline -> compose -> audit : browse for an idea, structure, draft, voice check
    browse -> find -> outline -> refine : browse, pull a related post, structure, tidy the outline
    find -> outline -> compose -> write : pull a post, structure, draft, polish a line
  * Research-only session [3]
    find -> browse -> summarize -> compare : hunt a past post, browse related notes, condense, compare style
    browse -> find -> summarize -> compare : browse ideas, pull a post, condense, compare to another
    browse -> find -> summarize -> brainstorm : browse, pull a post, condense, spin angles for a follow-up
  * Revise loop, stays in revise [13]
    rework -> write -> audit -> rework : restructure, line fix, voice check, another restructure
    write -> write -> audit -> rework : fix two paragraphs, check voice, a structural pass
    rework -> propose -> write -> audit : restructure, fill a resulting gap with options, polish, voice check
    rework -> write -> propose -> write : restructure, fix a line, fill a gap, integrate it
    write -> rework -> audit -> write : line fix, restructure, voice check, final polish
    rework -> write -> write -> audit : restructure, fix two paragraphs, voice check
    write -> audit -> rework -> write : line fix, voice check, restructure, polish
    rework -> audit -> write -> audit : restructure, voice check, line fix, re-check
    write -> propose -> rework -> write : fix a line, fill a gap, restructure, polish
    rework -> rework -> write -> audit : two restructuring passes, line fix, voice check
    write -> propose -> write -> audit : line fix, fill a gap, integrate, voice check
    rework -> propose -> write -> write : restructure, fill a gap, then fix two lines
    write -> rework -> propose -> write : line fix, restructure, fill a gap, polish
  * Draft then revise [22]
    compose -> write -> rework -> audit : draft prose, fix a line, restructure, voice check
    outline -> compose -> rework -> write : structure, draft, restructure, polish a line
    compose -> audit -> rework -> write : draft, voice check, restructure, polish
    compose -> write -> audit -> rework : draft, line fix, voice check, restructure
    outline -> compose -> audit -> rework : structure, draft, voice check, restructure
    compose -> rework -> write -> audit : draft, restructure, polish, voice check
    compose -> write -> propose -> write : draft, fix a line, fill a leftover gap, integrate
    compose -> audit -> write -> rework : draft, voice check, line fix, restructure
    outline -> compose -> write -> audit : structure, draft, line fix, voice check
    compose -> rework -> rework -> write : draft, two restructuring passes, polish
    compose -> write -> rework -> write : draft, line fix, restructure, polish
    outline -> refine -> compose -> audit : structure, tidy outline, draft, voice check
    compose -> propose -> write -> audit : draft with a gap, fill it, integrate, voice check
    compose -> audit -> rework -> audit : draft, voice check, restructure, re-check
    outline -> compose -> rework -> audit : structure, draft, restructure, voice check
    compose -> write -> write -> audit : draft, fix two paragraphs, voice check
    compose -> audit -> audit -> rework : draft, voice check across two turns, then restructure
    outline -> compose -> audit -> audit : structure, draft, then a two-turn voice check
    outline -> compose -> rework -> rework : structure, draft, two restructuring passes
    compose -> propose -> propose -> write : draft, fill two gaps in turn, integrate
    compose -> rework -> write -> write : draft, restructure, then polish two paragraphs
    compose -> rework -> rework -> audit : draft, two restructuring passes, voice check
  * Revise then publish [4]
    rework -> write -> release -> schedule : restructure, polish, publish, schedule a channel
    rework -> write -> audit -> release : restructure, polish, final voice check, publish
    write -> rework -> write -> release : polish, restructure, final polish, publish
    rework -> audit -> write -> release : restructure, voice check, polish, publish
  * Publish-focused [3]
    cite -> cite -> release -> schedule : add two citations, publish to blog, schedule a cross-post
    write -> cite -> release -> schedule : polish, cite, publish, schedule a channel
    write -> audit -> cite -> release : polish, voice check, cite, publish
  * Full pipeline [5]
    find -> outline -> compose -> release : pull a related post, structure, draft, publish
    brainstorm -> outline -> compose -> release : ideate, structure, draft, publish
    find -> outline -> compose -> schedule : pull a post, structure, draft, schedule for later
    find -> outline -> compose -> cite : pull a post, structure, draft, add a citation
    browse -> outline -> compose -> release : browse for an idea, structure, draft, publish
  * Chat-led / mixed entry [7]
    chat -> brainstorm -> outline -> compose : talk through an idea, ideate, structure, draft
    chat -> find -> summarize -> outline : ask a question, pull a past post, condense, structure
    chat -> find -> outline -> compose : chat, pull a related post, structure, draft
    chat -> brainstorm -> brainstorm -> outline : chat, ideate across two passes, structure
    chat -> outline -> refine -> compose : chat, structure, tidy outline, draft
    chat -> outline -> compose -> write : chat, structure, draft, polish a line
    chat -> chat -> outline -> compose : a longer chat, then structure and draft
  * Inspect then fix [14]
    find -> audit -> rework -> write : pull a post, check its voice, restructure, polish
    compare -> audit -> write -> rework : compare against a past post, voice check, polish, restructure
    find -> compare -> audit -> rework : pull a post, compare style, voice check, restructure
    compare -> audit -> rework -> write : compare, voice check, restructure, polish
    find -> audit -> write -> release : pull a draft, voice check, polish, publish
    compare -> rework -> write -> audit : compare, restructure, polish, voice check
    find -> audit -> rework -> release : pull a draft, voice check, restructure, publish
    find -> rework -> write -> release : pull a draft, restructure, polish, publish
    compare -> audit -> write -> release : compare, voice check, polish, publish
    find -> compare -> rework -> write : pull two drafts, compare, restructure one, polish
    find -> rework -> write -> audit : pull a draft, restructure, polish, voice check
    find -> audit -> audit -> rework : pull a draft, voice check across two turns, restructure
    find -> rework -> rework -> write : pull a draft, restructure across two passes, polish
    find -> write -> write -> audit : pull a draft, fix two paragraphs, voice check

3. Ambiguity — conversations where the agent cannot act confidently, so it recognizes the gap, asks **one**
   clarification, and the user resolves it. Recognizing uncertainty instead of guessing (and NOT asking when
   context already resolves it) is the core thing being tested. 64 cases, 16 per level.
  * **Built by "clear, then remove context."** Write a conversation that is clear from its context, then
    delete the one critical piece that resolved it. The same utterance is now ambiguous, and **which piece
    you removed decides the level**. The clear baseline is kept as **metadata** on each case (the `clear:`
    note), not as a separate conversation, so the set also tests the hard direction: when the context is
    present, the agent must just act and not ask.
  * **The four locked levels** (each is the NLU correctness gate that failed):
    - `general` (gate 1): the **task/goal** reads as open — the flow itself is unknown — so the `stack` is
      EMPTY and `intent` is null. The agent asks "what are we doing?" and runs NO domain tool
      (the reply turn's `actions` is `[]`); the next turn names the real flow. There is no `clarify` flow; the empty stack +
      `ambiguity "general"` IS the label.
    - `partial` (gate 2): flow known, the grounded **entity** (post/section) is missing. Agent asks "which
      post?", or on a fuzzy match offers a candidate "did you mean 'X'?".
    - `specific` (gate 3): entity known, a **required value** (tone/channel/date/source) is missing AND
      nothing lets the agent infer it. Agent asks an open question "which tone?".
    - `confirmation` (the fork): the explicit value is missing but history/the series/a typo gives a
      candidate, so the agent **verifies its guess** "casual, like your last posts?". Never about an entity
      (verifying an entity is `partial`); always a single inferred or fuzzy value, never a proposed deliverable
      (proposing options is not ambiguity, see the label model).
  * **Label model.** `ambiguity` is one value (a level, or null). `general` = flow unknown -> EMPTY stack +
    null intent; `partial`/`specific`/`confirmation` = flow known, keep the one-flow stack; all three run no
    domain tool (`actions []` — ambiguity is the level field, not a tool). `clarify` is NOT a flow —
    the 16 catalog flows are the only labels.
    **Proposing options is NOT
    ambiguity:** a flow that presents choices and lets the user pick (`propose`, `outline`) is operating
    normally, so it is never a `confirmation` — a chosen fill routes to `write` (insert), a reject re-runs the
    flow with new options.
  * **specific vs confirmation:** `specific` has nothing to infer (open question); `confirmation` has a
    strong inference it verifies. Both differ from a `clear` turn, where the value is present and the agent
    just acts.
  * **Variations (NOT levels; tags on the resolution):** `reroute` (the answer reveals a DIFFERENT intent, so
    the agent re-routes via contemplate), `reject` (the user rejects the agent's candidate and supplies the
    real one), `invalid` (`specific` only: a given value is unmatchable, the agent re-asks). `general` is
    always clean (no flow to reroute from, no candidate to reject).
  * **Format (a lead-up plus the ambiguous exchange; 7+ turns).** Each case is a short conversation, not a lone
    turn: an optional 1-2 turn lead-up sets up the state the ambiguity depends on, then the ambiguous exchange,
    then it CONTINUES past resolution to other topics/flows so every case runs 7+ turns (4+ user turns). Each
    case opens with a `Post:` metadata line naming the ground-truth post and a `grounded: yes|no` flag; that
    post reaches the agent only through that channel, so **user turns almost never name it** (anaphora: "it",
    "that one"). Every user turn is labeled `(<flow> {dax})`; the ambiguous turn is `(ambiguous: <flow> {dax},
    level: <level>)` and `general` keeps its underlying flow too (no `clarify`/no-flow case).
    `ambiguity_cases.md` holds all 64 in this format.
  * **Authoring rules (L1-L10), applied to every case:**
    1. **No dead turns.** Strict U/A alternation; every user turn changes state or redirects. Never narrate
       reading or acknowledging an artifact already on the panel ("let me read it", "ok", "looks good").
    2. **Label every turn** (format above). `general` = empty stack + null intent; the other levels keep the
       one-flow stack; `clarify` is not a flow.
    3. **Ambiguity only where the flow truly stalls.** If the flow has a default action, the agent ACTS, it
       does not ask: `cite` searches the web on its own (ambiguous only when the search returns several
       candidates -> confirmation, or nothing -> specific); `release` with no channel defaults to the blog
       (ambiguous only when history implies a non-default channel, or the user asks for one without naming it).
       Do not manufacture a question the flow would not need.
    4. **A vague resolution is a NEW ambiguity, not a green light.** "trim it", "the technical ones", "make it
       pop" -> the agent confirms or asks; it does not silently execute. Either make the resolution concrete or
       model the extra beat.
    5. **Keep the lead-up internally consistent.** The agent's statements match established state; nothing
       already done is described as pending, and the agent never knows what it could not.
    6. **Resolutions obey domain rules.** A full post releases only to long-form channels: the blog, Substack,
       LinkedIn. TWITTER CANNOT take a post release; it needs a NOTE (a short snippet) drafted from the post
       first, then the note posts. Valid channels: the primary blog (the default), Substack, LinkedIn, Medium,
       and Twitter. dev.to is NOT valid. A full post goes to the blog, Substack, LinkedIn, or Medium; Twitter
       takes a NOTE drafted from the post first.
    7. **Ground-truth post as metadata, not spoken.** Every case attaches the real post via the `Post:` line;
       it reaches the agent through a separate metadata channel (an active-post payload) only when
       `grounded: yes`. User turns use anaphora and almost never name the title (a user turn that names it, or
       even "the finance post", is a defect) - the one exception is a `partial` resolution pointing at one of
       several the agent just listed. `grounded: no` only for `partial`.
    8. **7+ turns (4+ user turns).** The ambiguity usually resolves by mid-conversation (sometimes the agent
       clarifies inside its own turn); after it resolves the conversation continues to other topics/flows.
       Ending unresolved is fine; being short is not.
    9. **No false ambiguity by vagueness.** An ambiguity requires the flow (or, for `general`, the task) to be
       genuinely undecidable. A single clean ask phrased vaguely is not ambiguous - especially one that
       resolves to `propose` / `brainstorm` / `outline` presenting options (that is the flow working, rule 4).
       A `general` opener must be undecidable between multiple flows ("is it missing a section or just badly
       ordered?"), not one obvious flow dressed up ("I don't know what to write here" -> that is just `propose`).
    10. **Label the action on every turn, continuations included.** Each `(flow {dax})` must match what that
        turn actually does, and continuation turns get the same scrutiny as the ambiguous one. `audit` is ONLY
        the voice/tone/consistency pass; "read it and remove / rewrite / strip / fix content X" is `write` or
        `rework`, not `audit`.
  * **Turn-level diversity (the openers were almost all bland commands; they must not be).** About one third of
    openers are commands and two thirds are questions or explanations. A real user never says a blunt "Do X";
    commands are long contextual instructions. No command is bare verb-object
    ("edit the post", "publish it") - each carries supporting information: an observation ("the intro drags,
    cut it back"), a reason ("the editor wants sources, add them"), a condition ("if it reads clean, send it
    out"), or a reference ("like last time, cross-post it"). Vary openings, use anaphora, keep turns short.
  * The compact index below is a quick reference; `ambiguity_cases.md` holds the fully-written 64 (lead-up plus
    labeled exchange) and is the source of truth. The 64:
  * general [16] (remove the task/goal; no flow; always clean)
    [-> rework {006}]   "the heat-pump post is a mess" -> "the structure's all over, rebuild it" · clear: rebuild already the agreed goal
    [-> outline {002}]  "do something with my Edison notes" -> "rough them into a structure" · clear: shaping the notes already underway
    [-> release {004}]  "what's next for the barbell post" -> "get it live today" · clear: publishing already the plan
    [-> find {001}]     "the RAG thing, I'm lost" -> "dig up what I wrote on it before" · clear: a research thread already open
    [-> audit {13A}]    "make the finance post better" -> "the voice, it's too stiff" · clear: a voice pass already queued
    [-> brainstorm {39D}] "I'm stuck on the astronomy piece" -> "need a few fresh angles" · clear: ideation already underway
    [-> chat {000}]     "can you help me out" -> "how long should an intro run?" · clear: a Q&A already in flight
    [-> write {003}]    "the cycling post, ugh" -> "the intro's bloated, trim it" · clear: an edit already in progress
    [-> compare {18A}]  "what do I do with the security draft" -> "set it against the older one" · clear: a comparison already set up
    [-> cite {15B}]     "sort out the train-travel post" -> "it needs sources on the claims" · clear: citing already the task
    [-> refine {02B}]   "the gardening thing needs work" -> "clean up the outline, the order's off" · clear: refining the outline already underway
    [-> summarize {19A}] "help with my observability notes" -> "boil the old post down first" · clear: a summary already requested
    [-> schedule {4AC}] "this Roman-engineering post" -> "line it up for next week" · clear: scheduling already discussed
    [-> propose {39B}]  "I don't know, the burnout post" -> "fill the blank in the middle" · clear: filling the gap already the task
    [-> browse {012}]   "the language-learning one" -> "what topics am I still missing" · clear: a coverage check already underway
    [-> compose {3AD}]  "the clean-energy post" -> "the outline's done, make it prose" · clear: drafting from the outline already the plan
  * partial [16] (remove the grounded entity; 8 clean, 4 guess/reject, 4 reroute)
    [audit {13A}]   "give that one a once-over" -> "the cycling post" (clean) · clear: cycling post already active
    [write {003}]   "edit that bit" -> "Edison, the intro" (clean) · clear: Edison post already open
    [rework {006}]  "restructure it" -> "the index-funds draft" (clean) · clear: that draft already active
    [compare {18A}] "set them side by side" -> "the two RAG ones" (clean) · clear: both RAG posts already referenced
    [audit {13A}]   "check the voice on that" -> "the gardening post" (clean) · clear: gardening post already active
    [write {003}]   "smooth that out" -> "train travel, the overnight bit" (clean) · clear: that section already open
    [rework {006}]  "fix the middle section" -> "Roman roads, the trade part" (clean) · clear: Roman roads post already active
    [compare {18A}] "look at the differences" -> "this draft vs the live version" (clean) · clear: both versions already in view
    [write {003}]   "edit the barbell post" -> guess 'Machines Aren't Cheating' -> "yes" (guess) · clear: only one barbell post exists
    [summarize {19A}] "open the Edison piece" -> guess 'Edison Didn't Invent the Lightbulb' -> "no, the grid one" (guess, reject) · clear: only one Edison post exists
    [audit {13A}]   "the cycling post" -> guess 'Skip the Road Bike' -> "no, the bike-lanes one" (guess, reject) · clear: only one cycling post exists
    [rework {006}]  "the index post" -> guess 'Index Funds for People...' -> "no, the IRA one" (guess, reject) · clear: only one finance post matches
    [write {003} -> release {004}] "polish that paragraph" -> "the solar one, it's fine, just publish it" (reroute) · clear: solar post active, edit intent clear
    [rework {006} -> audit {13A}] "rework the middle" -> "heat pumps, actually just check the voice" (reroute) · clear: heat-pump post active, rework intent clear
    [audit {13A} -> find {001}] "look over that one" -> "strength training, pull my saved notes first" (reroute) · clear: post active, review intent clear
    [compare {18A} -> audit {13A}] "weigh them up" -> "the finance takes, actually just check the newer one" (reroute) · clear: posts referenced, compare intent clear
  * specific [16] (remove the required value, nothing to infer; 10 clean, 3 invalid, 3 reroute)
    [audit {13A}]    "set the tone on the Edison post" -> "casual" (clean) · clear: tone set earlier
    [schedule {4AC}] "schedule the barbell post" -> "friday 9am" (clean) · clear: a cadence already set
    [release {004}]  "publish the finance post" -> "substack" (clean) · clear: channel known
    [cite {15B}]     "back up that claim" -> search returns nothing -> "use the DOT report" (clean, empty) · clear: a public source turns up
    [audit {13A}]    "set the register on the burnout post" -> "technical" (clean) · clear: register set earlier
    [schedule {4AC}] "schedule the Roman post for the morning" -> "monday" (clean) · clear: the day already known
    [release {004}]  "publish the security post" -> "linkedin" (clean) · clear: channel known
    [audit {13A}]    "give the astronomy post a tone pass" -> "witty" (clean) · clear: tone set earlier
    [cite {15B}]     "source the delay stat" -> "it's from your trip logs, where to point it?" -> "my travel spreadsheet" (clean, private) · clear: a public source exists
    [schedule {4AC}] "schedule the index-funds post for thursday" -> "8am" (clean) · clear: the time already known
    [schedule {4AC}] "schedule the RAG post for blursday" -> "next friday" (invalid) · clear: a valid date given
    [release {004}]  "can this go up on dev.to?" -> "dev.to's not one of my channels; blog, substack, linkedin, medium, or a twitter note?" -> "substack" (invalid) · clear: a valid channel given
    [audit {13A}]    "make the language-learning post sound stern" -> "yeah, formal" (invalid) · clear: a known register given
    [audit {13A} -> rework {006}] "set the voice on the gardening post" -> "skip the voice, just restructure it" (reroute) · clear: tone present, voice intent clear
    [schedule {4AC} -> find {001}] "schedule the heat-pump post for thursday" -> "it's not ready, pull my notes first" (reroute) · clear: time present, post ready
    [release {004} -> audit {13A}] "publish the cycling post" -> "hold off, run the voice once more first" (reroute) · clear: channel present, post ready
  * confirmation [16] (remove the explicit value, a basis to infer remains; 10 clean, 6 reject)
    [release {004}]  "post it to my usual spot" -> "substack?" -> "yes" (clean, inferred) · clear: "to substack" stated outright
    [audit {13A}]    "match my usual voice on the finance post" -> "casual?" -> "yeah" (clean, inferred) · clear: "make it casual" stated outright
    [schedule {4AC}] "same time as last week for the barbell post" -> "friday 9am?" -> "yep" (clean, inferred) · clear: "friday 9am" stated outright
    [release {004}]  "cross-post the cycling one like before" -> "linkedin post and a twitter note?" -> "that's right" (clean, inferred) · clear: channels named outright
    [audit {13A}]    "keep the burnout post consistent with the series" -> "technical register?" -> "correct" (clean, inferred) · clear: "technical" stated outright
    [release {004}]  "publish to linkdin" -> "linkedin?" -> "yes" (clean, fuzzy) · clear: "linkedin" spelled cleanly
    [schedule {4AC}] "schedule it for fridya 9" -> "friday 9am?" -> "yep" (clean, fuzzy) · clear: "friday 9am" typed cleanly
    [audit {13A}]    "make it casuel" -> "casual?" -> "yeah" (clean, fuzzy) · clear: "casual" typed cleanly
    [audit {13A}]    "keep it consistent with the finance series" -> "casual, like the rest?" -> "yeah" (clean, inferred) · clear: "casual" stated outright
    [cite {15B}]     "source it the way I usually do" -> "your research wiki?" -> "yes" (clean, inferred) · clear: the source named outright
    [audit {13A}]    "match my usual voice on the astronomy post" -> "casual?" -> "no, formal this time" (reject, inferred) · clear: "formal" stated outright
    [release {004}]  "post it where I usually do" -> "substack?" -> "no, linkedin this time" (reject, inferred) · clear: "linkedin" stated outright
    [schedule {4AC}] "same slot as always for the Roman post" -> "friday 9am?" -> "no, make it monday" (reject, inferred) · clear: "monday" stated outright
    [audit {13A}]    "keep the cycling post in the house style" -> "casual?" -> "no, a bit more formal" (reject, inferred) · clear: "formal" stated outright
    [schedule {4AC}] "put it on the usual morning slot" -> "friday 9am?" -> "no, monday this week" (reject, inferred) · clear: "monday" stated outright
    [audit {13A}]    "give it the usual edge" -> "witty, like before?" -> "no, keep it dry this time" (reject, inferred) · clear: "dry" stated outright
  * Anchor conversations (the voice and the label model in practice). User turns carry labels; only `general`
    is no-flow. The `clear:` baseline is the same convo with the removed piece restored, where the agent acts
    without asking.
    - general · personal finance (clean)
      U1 [Clarify]: make the finance post better
      A2: Better in what way, the structure, the facts, or how it reads?
      U3 [resolves -> audit {13A}]: the voice, it's too stiff
      A4 [audit]: Running a voice pass. The hedging in the intro is what reads stiff.
      U5 [close]: that's it exactly
    - partial · Edison (guess, reject)
      U1 [summarize {19A}]: open the Edison piece
      A2: Did you mean 'Edison Didn't Invent the Lightbulb'?
      U3 [resolves -> summarize {19A}]: no, the grid one
      A4 [summarize]: Here's the gist of 'Edison's Real Genius Was the Grid'.
    - partial · clean energy (reroute)
      U1 [write {003}]: polish that paragraph
      A2: Which post?
      U3 [resolves -> release {004}]: the solar one, it's fine, just publish it
      A4 [release]: Skipping the edit then. Published the solar post.
    - specific · personal finance (clean)
      U1 [release {004}]: publish the finance post
      A2: Which channel?
      U3 [resolves -> release {004}]: substack
      A4 [release]: Live on Substack.
    - specific · gardening (invalid)
      U1 [release {004}]: can this go up on dev.to where the eng readers are
      A2: dev.to isn't one of my channels. For the post it's the blog, Substack, LinkedIn, or Medium, or a Twitter note.
      U3 [resolves -> release {004}]: linkedin
      A4 [release]: Live on LinkedIn.
    - confirmation · personal finance (inferred, clean)
      U1 [audit {13A}]: match my usual voice on the finance post
      A2: Casual, like your last ones?
      U3 [resolves -> audit {13A}]: yeah
      A4 [audit]: Done, casual throughout.
    - confirmation · train travel (inferred, reject)
      U1 [release {004}]: post it where I usually do
      A2: Substack?
      U3 [resolves -> release {004}]: no, linkedin this time
      A4 [release]: Published to LinkedIn instead.
    - confirmation · heat pumps (fuzzy typo)
      U1 [release {004}]: this one's ready, put it on linkdin
      A2: LinkedIn?
      U3 [resolves -> release {004}]: yeah, that
      A4 [release]: Posted to LinkedIn.

4. Planning — conversations that open with a **Plan turn** the agent must decompose. The user states a
   multi-step goal in a **terse, implicit** opener (1-2 parts, usually 1, naming the goal not the steps); the
   agent infers an ordered sequence of existing flows, runs it, and judges when the goal is met. Inferring the
   decomposition from incomplete information is the thing being tested; spelling out every step is the main
   realism failure to avoid.
  * The Plan turn carries `intent "Plan"` and a `stack` holding the ordered decomposition (`[{flow, dax}, ...]`)
    — the same `{intent, stack}` label every turn has, just with more than one flow. There is no separate
    `plan` flow; the reply turn's `actions` is `[]`. The stack is the ground truth for the plan. The agent proposes the stack
    and shares its key steps, WAITS for the user's go-ahead (it does not barrel ahead), then runs it; the first
    post-plan user turn approves the plan, and later user turns react at checkpoints.
  * Shape: **2 or 3 unique flows only**, and the plan **stays within a phase or two adjacent ones** (no single
    plan runs outline -> publish). Realism comes from either a **heterogeneous** short sequence (distinct
    flows, one each) or a **fan-out** (one flow repeated per sub-task, each a sub-agent, plus a join), or a
    mix. Fan-out is one pattern, not the default.
  * Turn structure: flows batched in one turn (same-type sub-agents in parallel) vs. spread one-per-turn. With
    no checkpoint, even different-type flows chain on one turn.
  * Three handling types: **straightforward [24]** decompose immediately (8 with no checkpoint, 16 with a
    mid-plan checkpoint for human-in-the-loop), and **a few interpretations [8]** which stay Plan intent but
    open with a **Step 0** checkpoint for one targeted clarification. A *completely* unclear request is
    Clarify intent, handled in axis 5, not here.
  * Disruptions live at the checkpoints: reject / redirect (user pushes back, agent replans) and prereq (a
    flow discovers a missing input and stacks it). Same forward rules apply; avoid find -> compose and
    compose -> release.
  * Intent mix across the set skews ~20% Research / 30% Draft / 40% Revise / 10% Publish (blog work is mostly
    revising).
  * Notation: `plan` = the Plan opener (intent Plan; its label stack IS the multi-flow decomposition); `->` = a later turn; `+` = flows batched in one turn;
    `[check]` = a checkpoint (not a flow); tags = clean / reject / redirect / prereq (mid-plan) or
    confirm / specific (the Step 0 clarification level). The 32 verified chains:
  * Straightforward, no checkpoint [8]
    [draft]          plan -> outline -> compose -> write : notes to a polished draft
    [draft sections] plan -> compose + compose + compose + compose -> rework : draft four sections, join
    [research]       plan -> find -> summarize -> compare : pull a past post, condense, set against a newer one
    [research]       plan -> find + find + find -> compare : pull three posts, compare
    [revise]         plan -> rework -> write -> audit : restructure a weak middle, polish, voice-check
    [draft sections] plan -> compose + compose + compose -> audit : draft a 3-part series, voice-check
    [prep]           plan -> brainstorm -> outline -> refine : angles, structure, tidy the outline (no prose)
    [revise]         plan -> audit + audit + audit -> rework : voice-check three sections, fix what surfaces
  * Straightforward, mid-plan checkpoint [16]
    [draft]          plan -> outline -> [check] -> compose -> [check] -> write (clean)
    [draft sections] plan -> compose -> [check] -> compose -> [check] -> compose -> rework (clean)
    [revise]         plan -> rework -> [check] -> write -> [check] -> write -> audit (reject)
    [revise sections] plan -> write -> [check] -> write -> [check] -> write -> rework (clean)
    [draft]          plan -> brainstorm -> [check] -> outline -> [check] -> compose -> compose (clean)
    [draft]          plan -> compose -> [check] -> rework -> [check] -> audit (redirect)
    [draft sections] plan -> compose -> [check] -> compose -> rework (reject)
    [revise]         plan -> audit -> [check] -> rework -> [check] -> write (redirect)
    [publish]        plan -> audit -> [check] -> cite -> release (prereq)
    [publish]        plan -> cite -> [check] -> release (clean)
    [publish]        plan -> audit -> [check] -> release (redirect)
    [publish]        plan -> write -> [check] -> write -> audit -> release (reject)
    [research]       plan -> find -> [check] -> find -> [check] -> find -> compare (clean)
    [research]       plan -> browse -> [check] -> find -> [check] -> find -> compare (redirect)
    [revise sections] plan -> rework -> [check] -> rework -> [check] -> write (reject)
    [draft sections] plan -> compose -> [check] -> compose -> [check] -> compose -> audit (clean)
  * A few interpretations, Step 0 checkpoint [8]
    [draft sections] plan -> [check] -> compose + compose + compose -> rework (specific)
    [research]       plan -> [check] -> find -> summarize -> compare (specific)
    [publish]        plan -> [check] -> audit -> release -> release (confirm)
    [draft]          plan -> [check] -> outline -> compose -> write (specific)
    [revise sections] plan -> [check] -> write + write -> audit (specific)
    [revise]         plan -> [check] -> rework -> write -> audit (confirm)
    [research]       plan -> [check] -> find + find -> compare (specific)
    [publish]        plan -> [check] -> cite -> release -> schedule (confirm)
  * Each chain's full storyline is in `planning_cases.md`; an anchor conversation per case (terse opener,
    checkpoints, disruptions) is in `planning_scenarios.md`.

5. Length — sample VERBOSITY, not a word count. There are no length targets or buckets; a turn runs as long
   as its content earns. Keep two kinds of "long" apart:
   - human-verbose (sample this): a real person thinking out loud, over-explaining a worry, or piling on a
     side detail. Rambly, but every clause is genuine.
     "ok the intro's fine I think, but the metrics bit, yeah that's the one that bugs me, there's no numbers in there."
   - AI-padded (still banned — see the SHORT / no-AI-tell rules): filler, restating the agent, needless
     politeness, symmetrical triads.
     "I really appreciate the work so far. The draft looks wonderful. If it's not too much trouble, could we revisit the metrics section?"
   Notice that we can still have long sentences that are just a single part. In general, we should aim for single-part turns that are average length.
  * Conversation — how many turns the task actually takes (7 / 9 / 11). Extra turns come from real work (a
    clarification, an iteration loop, a redirect), not from dragging out a settled point.
  * Turn — how many moves it makes. We should not write any turns with 4 or more parts.
    1) Typical = 1 part (60%)
    2) Stacked = 2 parts (30%)
    3) Verbose = 3 parts (10%)
  * Sentence — how much one sentence elaborates. Even a single fragment can be expressed in multiple lengths:
    1) Terse: Cut out unicorn stuff (25%)
    2) Average: I'd like to remove anything talking about unicorns. (50%)
    3) Long: We should remove or replace any references to unicorns because they are too closely related to fantasy themes. (25%)

6. Persona - each sub-axis use discrete levels. The guidelines in the Persona options are not absolute, they can be adjusted tone *within* those rails, so Persona can still be blunt in a single turn, but formal overall.

  * Formality (3 levels) - The formal end is precise, while the casual end contains slang and contractions, maybe written in lowercase. Weight ~ 30 / 50 / 20.
    - casual:  "OK cool, lets just ship it"
    - neutral: "Looks good, go ahead and publish"
    - formal:  "This reads as ready for release, please publish it"

  * Emotion (5 levels) — One baseline per conversation that MAY shift once across turns (neutral then frustrated
    after a weak agent turn; neutral then appreciative at the close). Weight ~ 50 / 18 / 12 / 12 / 8.
    - neutral    (default, dominant): plain task voice
    - positive   (folds excited + appreciative): forward energy or thanks, "love it, keep going"
    - frustrated : something is wrong, irritated; escalated, this trips the Dismiss / negative path
    - skeptical  : doubts the output, pushes back, "are you sure that section holds up?"
    - pressured  (folds impatient + time-crunch): urgency, "just need it before standup" — pressure, not
      negative sentiment, so it does NOT trip Dismiss
    Default: neutral; a hesitant voice may lean skeptical-of-self

  * Directness (3 levels) —  Mostly per-conversation, may vary by a single turn (a blunt
    voice can still hedge once). Weight ~ 30 / 50 / 20.
    - blunt imperative  : "cut the intro"
    - plain request     : "can you cut the intro?"
    - hedged/deferential: "the intro maybe could go, if you think so?"

7. Distractor / off-topic turns — a chit-chat aside or interruption, then a return to the task to test
   robustness and segmentation. The test: is there a plausible real-world *trigger* that pulled the user
   away, and is the return natural? A good distractor is something the user's actual context throws at them
   (an interruption, a genuine adjacent worry); the agent should acknowledge it briefly and not treat it as a
   task. A contrived one is a topic dropped in from nowhere with no trigger, there only to test the parser.
  * Appropriate (realistic trigger, natural return):
    - "hold on, standup just started, one sec" ... "ok back, where were we" (environment pulled them away)
    - "ugh did I leave the oven on. anyway, keep going on the draft" (a real human aside, then snaps back)
  * Contrived (no trigger, mechanical, screams "test"):
    - "by the way whats the capital of france? ok anyway" (random trivia no editor would ask mid-draft)
    - "can you suggest a good pizza recipe? back to the intro now" (unrelated to their work, forced snap-back)
  * Don't leave the distractor draw perpetually null. The best asides are an *adjacent worry* about the user's
    own work ("did that other post ever ship?", "is the Friday newsletter still queued?") folded into one
    interior turn: the flow label stays the main request, the agent answers the aside in one clause and returns.
    Target the drawn rate (~0.12) across a batch; converted/legacy content especially tends to carry none.

8. Noise injection. Realistic noise only. The test: would a real person actually produce this slip? Avoid contrived noise (random letter-shuffles, misspellings no one makes).
  * typos — real spelling/typing errors, not scrambles. Dropped silent/repeated letters and classic confusions.
    - "shedule it for friday" (schedule, dropped silent c)
    - "the comparsion section is thin" (comparison, dropped i)
    - "did you recieve my notes" (receive, ei/ie confusion)
  * missing punctuation — what people drop typing fast, mostly apostrophes and end marks.
    - "Thats good, lets ship it" (dropped apostrophes)
    - "Is the intro done yet" (no question mark)
    - "Intro then traces then takeaways keep it short" (no periods, sentences run together)
  * dropped/repeated tokens — a small function word vanishes or doubles; the sentence still parses.
    - "Pull up cost section" (dropped article: the cost section)
    - "We get a draft off these" (dropped helper: can we)
    - "Now lets do the the full draft" (accidental repeat)
  * slight word-order changes — natural casual reorderings, still readable, not word-salad.
    - "its solid, the intro" (right-dislocation of the subject)
    - "that section I'd cut" (fronted object instead of "I'd cut that section")
    - "tomorrow lets publish it" (fronted time adverb)
  * voice-transcript style: fillers, run-ons — dictation artifacts: fillers, comma-splice run-ons, false starts.
    - "um yeah that ones good" (filler-led)
    - "Do the intro then traces and then takeaways at the end keep it short" (run-on, no breaks)
    - "Can you, yeah just turn it into prose" (false start then restart)
  * mild non-native phrasing — ESL article/preposition/tense slips that still read clearly.
    - "Please draft a post for engineering blog" (dropped article before "engineering")
    - "Can you discuss about the cost part" (extra preposition: discuss about)
    - "The intro is already done or you are still writing" (tense/aspect slip)

9. Writer model — generate with different models so idiolect varies
  * Haiku: weaker model provides more variance
  * Sonnet: should be used most often
  * Opus: built for coding, so the prose might be weaker
  * Across providers: DeepSeek, GLM, ChatGPT

10. Topic — different subject matter and sub-topics. Each sub-topic has its own sections:
  * Agent Observability
    - Your Agent's Token Count Is a Vanity Metric        (take)
    - Don't Trace Prompts, Trace the Tool Calls          (guide)
  * Agent Evaluations
    - You Don't Need an Eval Framework, Just 20 Examples  (vs)
    - LLM-as-Judge Grades on a Curve                     (take)
  * Agent Security
    - Guardrails Won't Save You; Least Privilege Will    (vs)
    - Prompt Injection Has No Fix, Only Blast Radius     (take)
  * RLVR / RL Environments
    - Hidden Traps in a Verifiable-Reward Environment    (guide)
    - Why Reward Hacking Still Beats Us                  (take)
  * RAG on a Company Wiki
    - Vector DBs Are Not Needed for RAG                  (compares the DBs, lands on Postgres)
    - Your Wiki RAG Fails at Chunking, Not the Model     (take)
  * Thomas Edison
    - Edison Didn't Invent the Lightbulb (and Knew It)   (vs)
    - Edison's Real Genius Was the Grid, Not the Bulb    (take)
  * Ancient Roman Engineering
    - Roman Roads Weren't Built for Trade                (take)
    - Roman Concrete Heals Itself; Ours Just Crumbles    (take)
  * Personal Finance
    - Index Funds for People Who Hate Spreadsheets       (guide)
    - How a Traditional IRA Quietly Loses You Money      (vs)
  * Long-Distance Train Travel
    - Skip the Eurail Pass: Point Tickets Cost Less      (vs)
    - An Overnight Train Is a Hotel in Disguise          (take)
  * Strength Training
    - Machines Aren't Cheating: Against Barbell Purism   (vs)
    - Soreness Is Not Progress                           (take)
  * Urban Vegetable Gardening
    - Skip the Raised Bed: a Bucket Grows More           (vs)
    - Why Most Beginner Gardens Die in July             (take)
  * Amateur Astronomy
    - Skip the Telescope: Start With Binoculars          (vs)
    - A Dark Sky Beats a Bigger Telescope                (take)
  * Adult Language Learning
    - You Don't Need Immersion; You Need Output          (vs)
    - Why Flashcards Stop Working at B1                  (take)
  * Burnout & Mindfulness
    - Delete Your Meditation App                         (vs)
    - Burnout Looks Like Cynicism, Not Exhaustion        (take)
  * Urban Cycling
    - Skip the Road Bike: a Used Hybrid Commutes Better  (vs)
    - Why Bike Lanes Pay for Themselves                  (take)
  * Clean Energy
    - Rooftop Solar Is the Wrong First Move              (vs)
    - Heat Pumps Work Fine in the Cold                   (take)
