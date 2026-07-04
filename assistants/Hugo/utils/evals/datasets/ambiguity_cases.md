# Ambiguity scenarios (64 anchor conversations)

The 64 ambiguity conversations for axis 5 of `data_aug_guide.md`. Each is a full conversation (7+ turns, 4+
user turns): an optional lead-up, the ambiguous exchange, then continuation to other topics once the ambiguity
resolves. The model (the four levels, "clear then remove context") and the authoring rules L1-L10 live in the
guide; this file is the voice and realism anchor.

Format:
- Each case opens with a `Post:` metadata line: the ground-truth post the user means, plus `grounded: yes|no`.
  That post reaches the agent only through this metadata channel, so USER TURNS ALMOST NEVER NAME IT (anaphora:
  "it", "that one"). grounded: no only for partial (the entity is the ambiguity).
- Every user turn is labeled `(<flow> {dax})`. The ambiguous turn is `(ambiguous: <flow> {dax}, level: <level>)`;
  general routes to `chat {000}`. Lead-up turns are `- U:` / `- A:`; the numbered exchange runs U1/A2/U3/A4...
- User turns IMPLY the intent (describe the problem/feeling), they do not request the deliverable or name the
  action. Labels match the action on every turn (audit = the voice/tone pass only).
- Strict U/A alternation, no dead turns. Domain-legal resolutions (a post never releases to Twitter; a Twitter
  note is drafted from it first). Proposing options (propose/outline) is the flow working, not an ambiguity.

Levels: general (task/goal missing -> chat {000}), partial (which post/section is unclear), specific (required
value missing, nothing to infer), confirmation (value missing but history/typo gives one candidate to verify).

---

## general [16] — task/goal removed; routes to chat {000}

### G1 · Use case: a research post that stalls somewhere unclear
Post: 'What Observability Actually Buys You' (grounded: yes — active draft)
- U1: I keep coming back to this one and never finishing it, something's off but I can't name it (ambiguous: chat {000}, level: general)
- A2: Want me to look for gaps in the argument, or hunt down a source you're missing?
- U3: yeah, there's a stat about alert fatigue I meant to back up and I never tracked down where it came from (find {001})
- A4: Found it. The PagerDuty study, 30% of alerts ignored within a week.
- U5: that's the one. is it already cited anywhere in here? (chat {000})
- A6: No, it's not in the draft yet. Want me to place it in the metrics section?
- U7: yes, drop it there (write {003})
- A8: Added. It anchors the alert-fatigue paragraph now.

### G2 · Use case: lost track of what's in the pipeline
Post: 'Grading Agents Without a Rubric' (grounded: yes — active draft)
- U1: I've got so many half-written things going I've lost the thread completely (ambiguous: chat {000}, level: general)
- A2: Want me to list what's open, or work on the one you've got up right now?
- U3: just show me everything still in progress (browse {012})
- A4: Five open. Two eval drafts, a RAG piece, and two shorter notes.
- U5: which of the eval ones is closer to done? (chat {000})
- A6: This active one. The other is barely an outline.
- U7: fine, let's finish this one then, where does it trail off? (chat {000})
- A8: The scoring section stops mid-thought after the second metric.

### G3 · Use case: too long to reread before a meeting
Post: 'Locking Down Your Agent Stack' (grounded: yes — active draft)
- U1: I've got a call in ten minutes and no memory of this thing, catch me up on it fast (ambiguous: chat {000}, level: general)
- A2: Want the short version of what's here, or a read on whether it holds up?
- U3: just give me the gist, top to bottom (summarize {19A})
- A4: Three parts, threat model, then sandboxing, then a weak close on audits.
- U5: weak how? (chat {000})
- A6: It raises audits but never says what to log. Reads unfinished.
- U7: yeah that's the gap, note it for later (chat {000})
- A8: Noted. The audit section needs a concrete logging list.

### G4 · Use case: two versions and no memory of the difference
Post: 'Should You Build Your Own RL Gym' (grounded: yes — active draft)
- U1: there are two of these floating around and I forget how they split (ambiguous: chat {000}, level: general)
- A2: Want me to hold them side by side, or just work the one that's open?
- U3: I can't tell what actually changed between them anymore (compare {18A})
- A4: The open one cut the intro and added a benchmark table. Otherwise close.
- U5: which reads better into the first section? (chat {000})
- A6: This one. The cut intro gets to the point faster.
- U7: pull the old intro back in from the other version, it read stronger (write {003})
- A8: Pulled it in. The old intro now leads, ahead of the benchmark table.

### G5 · Use case: a wall of notes, no shape yet
Post: 'A Wiki Your RAG Can Actually Read' (grounded: yes — active draft)
- U1: this is a pile of thoughts with no through-line, I can't follow my own train of thought in here (ambiguous: chat {000}, level: general)
- A2: Want me to rough out a structure from what's here, or trim it down first?
- U3: the first one, I need some order to build on before I start cutting anything (outline {002})
- A4: Sketched five sections, from indexing problems through retrieval to eval.
- U5: does the eval one have anything under it yet? (chat {000})
- A6: Just a header. No content beneath it.
- U7: right, that's the thin spot, I'll come back to it (chat {000})
- A8: Understood. The eval section is a header only for now.

### G6 · Use case: an empty post that needs a real start
Post: 'The Grid Edison Never Gets Credit For' (grounded: yes — active draft)
- U1: I opened this to write and I'm staring at a blank page, get me off the ground here (ambiguous: chat {000}, level: general)
- A2: Want me to draft an opening from the title, or brainstorm angles first?
- U3: it just starts cold, there's no real way into it and nothing pulls you in (compose {3AD})
- A4: Drafted three paragraphs opening on the blackout that made his case.
- U5: is it leaning too hard on the blackout? (chat {000})
- A6: A little. The second paragraph repeats the image. I can thin it.
- U7: yeah, thin that repeat (write {003})
- A8: Trimmed. The blackout lands once now, then moves on.

### G7 · Use case: an outline whose shape is off
Post: 'How Rome Moved Water Uphill' (grounded: yes — active outline)
- U1: I sketched this out but the shape of it is wrong and I can't see how to start (ambiguous: chat {000}, level: general)
- A2: Want me to reshape the outline's headings and order, or is it the ideas that need work?
- U3: the ideas are fine, it's the headings, half of them overlap and the order jumps around (refine {02B})
- A4: Cleaned up the outline. Merged the two overlapping headings and moved the gradient basics ahead of the arches.
- U5: does the aqueduct part still stand on its own? (chat {000})
- A6: It does, right after the gradient section now.
- U7: good, that's the backbone I was missing (chat {000})
- A8: The order holds now: gradient, arches, then the aqueduct payoff.

### G8 · Use case: stuck for a next move on a finance piece
Post: 'Retirement Math Without the Panic' (grounded: yes — active draft)
- U1: I'm blanking on where this even goes next, totally stuck (ambiguous: chat {000}, level: general)
- A2: Want me to throw out some directions it could take, or read what's there first?
- U3: the front holds up, it's the back half where I've got nothing (brainstorm {39D})
- A4: Five directions, from sequence-of-returns risk to a simple bucket plan.
- U5: is the bucket one too basic for this audience? (chat {000})
- A6: Slightly. They'll know the concept. The framing could still be fresh.
- U7: okay, park bucket, I like the sequence-risk angle better (chat {000})
- A8: Noted. Sequence-of-returns risk is the working direction now.

### G9 · Use case: the order feels wrong but the words are fine
Post: 'Sleeper Trains Are Worth the Hassle' (grounded: yes — active draft)
- U1: something about how this is arranged bugs me, the words are fine but it drags (ambiguous: chat {000}, level: general)
- A2: Sounds structural. Want me to reorder the sections rather than touch the prose?
- U3: yes, the cost stuff shouldn't come first, that kills the romance (rework {006})
- A4: Reordered. The overnight experience leads now, cost sits near the close.
- U5: does the ending still land after the shuffle? (chat {000})
- A6: It does. The arrival-at-dawn line closes it cleanly.
- U7: perfect, that image is the whole reason I wrote this (chat {000})
- A8: Kept intact. The dawn-arrival close is untouched.

### G10 · Use case: a specific fix but the request comes out vague
Post: 'Lift Heavy, Recover Harder' (grounded: yes — active draft)
- U1: there's one line in here doing damage and I keep glossing over it, sort it out (ambiguous: chat {000}, level: general)
- A2: Point me at it. Which line, and what should it say instead?
- U3: the deadlift warning near the top reads like a polite suggestion, nobody's going to stop the set (write {003})
- A4: Rewrote it. It now says stop the set if your back rounds, flat out.
- U5: does anything below still contradict that? (chat {000})
- A6: One spot lower down still says push through fatigue. That clashes.
- U7: that second spot undercuts the whole point, it can't be saying the opposite (write {003})
- A8: Aligned. Both spots now say stop, not push through.

### G11 · Use case: unsure if the piece even holds together
Post: 'Growing Tomatoes on a Fire Escape' (grounded: yes — active draft)
- U1: I can't tell if this actually works as a piece or if I'm too close to it (ambiguous: chat {000}, level: general)
- A2: Want me to read it through and flag what's off, voice, structure, both?
- U3: yeah, don't go easy on it, I want to know wherever it sags (audit {13A})
- A4: Read it through. Voice is warm and consistent. The watering section repeats itself.
- U5: repeats how? (chat {000})
- A6: It explains overwatering twice, once early and once near the end.
- U7: the reader doesn't need to hear that a second time, not the later one (rework {006})
- A8: Removed the later mention. Overwatering is covered once now, up top.

### G12 · Use case: not sure what fills a gap
Post: 'Finding Planets From a City Balcony' (grounded: yes — active draft)
- U1: the middle just isn't working and I'm too close to it to see why (ambiguous: chat {000}, level: general)
- A2: Want me to check whether it's missing something, or whether it's just the order?
- U3: there's a hole in there and I honestly don't know what belongs (propose {39B})
- A4: Three fills: a light-pollution workaround, a first-target list, or an app rundown.
- U5: which one keeps the beginner reading? (chat {000})
- A6: The first-target list. It gives them something to do that night.
- U7: yes, put that one in (write {003})
- A8: Inserted the first-target list into the gap after the gear section.

### G13 · Use case: done but unsure of the next step
Post: 'Learning a Language After Forty' (grounded: yes — active draft)
- U1: I think this is basically there but I don't know what I'm supposed to do with it (ambiguous: chat {000}, level: general)
- A2: Want me to get it ready to go out, or read it once more first?
- U3: no, it's ready, get it out the door to the blog (release {004})
- A4: Live on the blog.
- U5: how's the last language piece doing over there? (chat {000})
- A6: Steady traffic, mostly from search on the grammar terms.
- U7: nice, that's the evergreen effect I wanted (chat {000})
- A8: Right. The search pull tends to build slowly and hold.

### G14 · Use case: wants it out later but can't name the ask
Post: 'The Case for the Four-Day Rest Week' (grounded: yes — active draft)
- U1: I'm done with this but shoving it out the door today doesn't sit right, and I can't say why (ambiguous: chat {000}, level: general)
- A2: Want me to read it over once more, or set it aside for a better moment?
- U3: no it's solid, just don't run it today, put it out monday morning instead (schedule {4AC})
- A4: Queued for Monday 9am on the blog.
- U5: is anything else already sitting in that slot? (chat {000})
- A6: Nothing on Monday. The next queued piece is Thursday.
- U7: good, keep monday clear for this one (chat {000})
- A8: Held. Monday 9am belongs to this piece only.

### G15 · Use case: a claim that needs backing but the ask is fuzzy
Post: 'You Don't Need a Gym to Get Strong' (grounded: yes — active draft)
- U1: one of the claims in here feels shaky and I'd sleep better if it were solid (ambiguous: chat {000}, level: general)
- A2: Which claim worries you? I can go find outside support, or reword it so it stops overreaching.
- U3: the one about bodyweight matching weights for beginners, right now there's nothing behind it (cite {15B})
- A4: Found support. A 2016 study showing equal early strength gains, now cited inline.
- U5: is that source recent enough to trust? (chat {000})
- A6: It holds, but there's a 2021 replication too. Want both?
- U7: yeah, the newer one belongs next to it (cite {15B})
- A8: Added. Both studies now back the beginner claim.

### G16 · Use case: an open draft and a foggy head
Post: 'Why I Stopped Chasing Inbox Zero' (grounded: yes — active draft)
- U1: I opened this to work on it and my brain just won't tell me what it needs (ambiguous: chat {000}, level: general)
- A2: Want to talk through it a second? Tell me what you were going for.
- U3: it's about burnout but I worry it sounds preachy, does it? (audit {13A})
- A4: A little, in the middle. The should-statements pile up there.
- U5: yeah I felt that, is it the whole section or just a few lines? (audit {13A})
- A6: Just three lines, all clustered in the same paragraph.
- U7: okay, that's manageable, I'll soften those myself later (chat {000})
- A8: Makes sense. The preachy stretch is three lines in one paragraph.

## partial [16] — grounded entity removed; agent unsure which post

### P1 · Use case: choosing which security draft to audit
Post: 'Prompt Injection Isn't Solved' (grounded: no — two agent-security drafts open)
- U: what agent-security stuff do I have sitting unfinished? (browse {012})
- A: Two drafts. One on prompt injection, one on tool-permission scoping.
- U1: one of them has a back half that asserts a lot more than it earns, and it needs a hard look (ambiguous: audit {13A}, level: partial)
- A2: Which draft?
- U3: the prompt injection one (audit {13A})
- A4: Read it through. Voice is fine, but the back half asserts without evidence.
- U5: is that fixable by reordering or does it need new material? (chat {000})
- A6: New material. The claims need examples to stand on.
- U7: pull two real injection incidents in then (cite {15B})
- A8: Added two documented cases. The back half has ground under it now.

### P2 · Use case: which Roman engineering piece to rework
Post: 'How Roman Concrete Outlasted Empires' (grounded: no — three Rome drafts in the library)
- U: list my ancient Rome drafts, I lost track of them (browse {012})
- A: Three. The concrete one, an aqueducts piece, and one on road building.
- U1: the structure on one of these is backwards, the payoff lands before the setup (ambiguous: rework {006}, level: partial)
- A2: Which one has the ordering problem?
- U3: the concrete piece (rework {006})
- A4: Reordered it. The durability reveal lands after the setup now.
- U5: does the open still work with that change? (chat {000})
- A6: It holds. The hook doesn't spoil the payoff anymore.
- U7: good, now line up a version for the newsletter crowd (schedule {4AC})
- A8: Queued for Substack, Friday 9am.

### P3 · Use case: agent guesses which finance draft, user accepts
Post: 'Your Emergency Fund Is Too Big' (grounded: no — several finance drafts, one recently edited)
- U1: the argument on the one I was in yesterday just doesn't land the way it should (ambiguous: rework {006}, level: partial)
- A2: The emergency-fund draft you had open? That was the last finance piece you edited.
- U3: yeah, that's it, the middle wanders (rework {006})
- A4: Reworked the middle. It stays on the opportunity-cost thread now.
- U5: does it still have that line about keeping six months? (chat {000})
- A6: It does, near the top. Want it moved to the close?
- U7: no, leave it, but the six-month rule hangs there with no numbers behind it (cite {15B})
- A8: Added a current figure with a source. It backs the six-month point.

### P4 · Use case: agent guesses the astronomy draft, user rejects and names another
Post: 'Chasing Dark Skies Near the City' (grounded: no — two astronomy drafts open)
- U1: one of them reads out of order, you hit the gear talk before there's any reason to care (ambiguous: rework {006}, level: partial)
- A2: You've got two astronomy drafts open. The backyard-telescopes one?
- U3: no, the other one, about finding dark skies (rework {006})
- A4: Reordered it. The flow was breaking where it jumped from planning straight to gear.
- U5: was that a missing transition or just the wrong order? (chat {000})
- A6: Wrong order. Gear needed to come before the trip-planning section, so I moved it up.
- U7: good, that reads better now (chat {000})
- A8: Agreed. Gear leads, trip planning follows, and the setup earns it.

### P5 · Use case: reroute from write to audit
Post: 'Deadlifts Won't Wreck Your Back' (grounded: no — two strength drafts open)
- U: what strength-training drafts are still live? (browse {012})
- A: Two. One on deadlift form, one on programming for beginners.
- U1: one of them really ought to warn about ego lifting and doesn't (ambiguous: write {003}, level: partial)
- A2: Which draft should the warning go in?
- U3: the deadlift one, though honestly I'm not sure it even needs more, does it already handle this? (audit {13A})
- A4: Read it through. It already covers ego lifting in the form section.
- U5: right, then leave it, but I'm not sure that warning lands hard enough (chat {000})
- A6: The warning's soft. It mentions ego lifting but doesn't say why it's dangerous.
- U7: that part could hit harder then (rework {006})
- A8: Firmed it up. It now names the injury risk directly.

### P6 · Use case: which language-learning section to rework
Post: 'You Don't Need Grammar Drills' (grounded: no — post open, two candidate sections)
- U: which sections in this one are dragging? (browse {012})
- A: Two feel slow. The immersion section and the one on spaced repetition.
- U1: one of them keeps circling the same point three times, that's what's slowing it (ambiguous: rework {006}, level: partial)
- A2: The immersion section or the spaced-repetition one?
- U3: spaced repetition (rework {006})
- A4: Reworked it. It makes the point once and moves on.
- U5: is the immersion one guilty of the same thing? (chat {000})
- A6: Less so, but it does restate the input-first idea twice.
- U7: the second time it says input-first it's just repeating itself (rework {006})
- A8: Cut the repeat. It states input-first once now.

### P7 · Use case: comparing two versions, unclear which post's
Post: 'Heat Pumps Beat Furnaces on Cost' (grounded: no — two clean-energy drafts, each with an A/B version)
- U: pull up my clean-energy drafts, a couple have two versions going (browse {012})
- A: Both do. The heat-pump cost piece and the rooftop-solar payback one each have an A and a B.
- U1: I keep flipping between the two versions and can't tell which one actually reads stronger (ambiguous: compare {18A}, level: partial)
- A2: Which post's versions, heat-pump or solar?
- U3: the heat-pump one (compare {18A})
- A4: Compared them. Version A leads on savings, version B leads on comfort.
- U5: which one keeps a reader past the first paragraph? (chat {000})
- A6: A. The savings hook is more concrete.
- U7: go with A then, ship it to the blog (release {004})
- A8: Live on the blog.

### P8 · Use case: which observability draft to sharpen
Post: 'Traces Beat Logs for Agents' (grounded: no — three observability drafts open)
- U: I've got a few observability pieces half-written and I can't keep them straight anymore (browse {012})
- A: Three. One on tracing, one on metrics, one on eval dashboards.
- U1: the middle section on one of these buries the lede, its real point is stranded down below (ambiguous: rework {006}, level: partial)
- A2: Which draft?
- U3: the tracing one (rework {006})
- A4: Reworked it. The trace-over-logs claim leads the section now.
- U5: does the eval-dashboard one have the same burying problem? (chat {000})
- A6: A bit. Its main point sits in the third paragraph.
- U7: leave that one for now, I just can't tell which of the three is actually near shipping (browse {012})
- A8: The tracing one. It only needs a citation pass.

### P9 · Use case: agent guesses the burnout draft, user accepts
Post: 'Rest Is Not a Reward' (grounded: no — several mindfulness drafts, one recently edited)
- U1: I keep circling back to that one, and something about how it lands on the reader nags at me (ambiguous: audit {13A}, level: partial)
- A2: The mindfulness draft you were in Tuesday, on treating rest as earned?
- U3: that's the one (audit {13A})
- A4: Read it through. The argument's clear, but the tone preaches in spots.
- U5: where does it preach? (chat {000})
- A6: The middle. It tells the reader what to feel instead of showing it.
- U7: it still talks down to the reader in that stretch, nothing like how a peer would say it (audit {13A})
- A8: Softened it. It reads like a peer now, not a lecture.

### P10 · Use case: agent guesses the RAG draft, user rejects and names another
Post: 'Your Wiki Is Lying to Your RAG' (grounded: no — two RAG drafts open)
- U1: one of these two drags at the start, the setup takes forever to get going (ambiguous: rework {006}, level: partial)
- A2: The one on chunking strategies?
- U3: no, the other, about stale wiki content (rework {006})
- A4: Reworked the open. It hits the stale-content problem in the first two lines now.
- U5: does the fix still name the wiki example up top? (chat {000})
- A6: It does. The outdated onboarding page is the first thing you see.
- U7: one thing's missing though, nothing tells the reader how often to re-index (write {003})
- A8: Added it after the example. Suggests a weekly re-index cadence.

### P11 · Use case: reroute from rework to compare
Post: 'Sleeper Trains Are Worth the Time' (grounded: no — two train-travel drafts open)
- U: which long-distance train drafts are open right now? (browse {012})
- A: Two. One on sleeper trains, one on scenic day routes.
- U1: one of these reads stiff and clunky, way more than the other (ambiguous: rework {006}, level: partial)
- A2: Which one reads stiff to you? I can look at both first.
- U3: honestly I can't tell which of the two is the stiffer read (compare {18A})
- A4: Compared them. The sleeper piece is stiffer, more list than story.
- U5: right, that one feels like a checklist, not a trip (rework {006})
- A6: Reworked it. It reads as a journey now, not a checklist.
- U7: better. does the scenic one have the same problem? (chat {000})
- A8: No, that one already reads like a travelogue.

### P12 · Use case: which gardening section to audit
Post: 'Grow More in Less Space' (grounded: no — post open, three candidate sections)
- U: give me a quick lay of the land on this draft's sections (browse {012})
- A: Three. The soil section, the watering one, and the pest section.
- U1: one of these stops sounding like me and goes stiff and textbooky partway through (ambiguous: audit {13A}, level: partial)
- A2: Which section?
- U3: the watering one (audit {13A})
- A4: Read it. The voice flattens mid-section into a clipped manual tone, unlike the warmer open.
- U5: is that the only spot that drifts? (chat {000})
- A6: The pest section stiffens a little too, but the watering one drops furthest.
- U7: bring that stretch back to how the intro talks (audit {13A})
- A8: Re-aligned the voice. The watering steps sound like the open now.

### P13 · Use case: reroute from audit to find
Post: 'RL Environments Are the Bottleneck' (grounded: no — two RL drafts open)
- U1: one of my RL drafts stops sounding like me toward the end, and I can't put my finger on where (ambiguous: audit {13A}, level: partial)
- A2: I have two open, one on reward design and one on environment scaling. Which?
- U3: neither, actually, wasn't there a third on sim-to-real? pull it up (find {001})
- A4: Found it. 'Sim-to-Real Is Still Hard', last touched three weeks ago.
- U5: right, that's the one where the tone slips (audit {13A})
- A6: Read it through. The late section drops into a flat, textbook register that breaks from your usual voice.
- U7: the close bothers me too, it trails off instead of committing to anything (rework {006})
- A8: Rewrote the close. It commits to a claim now instead of looping back.

### P14 · Use case: which Edison draft to write into
Post: 'Edison Failed More Than He Won' (grounded: no — two Edison drafts open)
- U: what Edison drafts do I have? (browse {012})
- A: Two. One on his failures, one on the patent wars.
- U1: one of them never touches the phonograph accident, and that's the cleanest case of a failure that paid off (ambiguous: write {003}, level: partial)
- A2: Which draft takes it?
- U3: the failures one (write {003})
- A4: Added it. The phonograph misstep sits in the middle now, as a failure that paid off.
- U5: does that contradict the thesis that failure was the point? (chat {000})
- A6: No, it supports it. The accident led to a better design.
- U7: good, but the close never loops that back to the failure-was-the-point idea (write {003})
- A8: Added the callback. The close names it as failure doing its job.

### P15 · Use case: reroute from write to summarize
Post: 'What Cycling Cities Get Right' (grounded: no — two urban-cycling drafts open)
- U1: one of the cycling drafts skips right past protected intersections and that's a real hole (ambiguous: write {003}, level: partial)
- A2: I have two open, the infrastructure piece and the commuter-culture one. Which?
- U3: hang on, I don't remember what's already in the infrastructure one (summarize {19A})
- A4: It covers bike lanes, signal timing, and parking removal. No intersections yet.
- U5: right, that's the one with the gap, the intersection piece belongs in there (write {003})
- A6: Added it after the signal-timing part. It fits the flow.
- U7: does the piece still end on the parking point? (chat {000})
- A8: It does. Parking removal still closes the argument.

### P16 · Use case: which eval draft to compare against
Post: 'Offline Evals Lie to You' (grounded: no — three agent-eval drafts open)
- U: what have I got going on agent evaluations? (browse {012})
- A: Three. One on offline evals, one on LLM judges, one on eval datasets.
- U1: two of these are basically arguing the same thing and I can't tell which one lands harder (ambiguous: compare {18A}, level: partial)
- A2: Which two? The offline-eval and judge drafts overlap most, want those?
- U3: yeah, those two (compare {18A})
- A4: Compared them. Both argue offline scores mislead, but the judge one blames the metric.
- U5: which framing is more convincing? (chat {000})
- A6: The judge one. It names the failure instead of gesturing at it.
- U7: the weaker one should be landing its point that hard too, pull in what works (rework {006})
- A8: Pulled the judge framing in. The offline-eval draft names the metric problem now.

## specific [16] — required value removed, nothing to infer

### S1 · Use case: giving a flat draft a defined register
Post: 'What Agent Observability Actually Measures' (grounded: yes — active draft)
- U1: this reads like a spec sheet, there's no warmth to any of it (ambiguous: audit {13A}, level: specific)
- A2: I can give it a voice. What register are you after?
- U3: conversational, like I'm explaining it over coffee (audit {13A})
- A4: Done. Conversational throughout, the jargon's softened.
- U5: does the middle still stall where it lists the metrics? (chat {000})
- A6: It does. The list runs eight items with no breaks. I can rework it.
- U7: break it into two groups then (rework {006})
- A8: Split into leading and lagging metrics. It reads faster now.

### S2 · Use case: scheduling with no time given
Post: 'How We Grade Our Agents' (grounded: yes — active post)
- U1: this one's done, but I don't want it going live today, sometime next week feels right (ambiguous: schedule {4AC}, level: specific)
- A2: Which day and time next week?
- U3: tuesday morning, whenever traffic peaks (schedule {4AC})
- A4: Queued for Tuesday 9am, that's your peak.
- U5: is that far enough out from the last eval post? (chat {000})
- A6: Six days apart. Enough spacing for the topic.
- U7: good. does the intro still name the benchmark up top? (chat {000})
- A8: It does, second sentence. Want it in the first?

### S3 · Use case: releasing to an unnamed non-default channel
Post: 'Red-Teaming Your Own Agents' (grounded: yes — active post)
- U1: the draft's solid now, put it somewhere the security crowd will actually see it (ambiguous: release {004}, level: specific)
- A2: Which channel did you have in mind? Substack or LinkedIn?
- U3: LinkedIn, that's where they hang out (release {004})
- A4: Live on LinkedIn.
- U5: can we pull a short version for the bird site too? (chat {000})
- A6: Twitter needs a note, not the full post. Want me to draft one?
- U7: yeah, cut it to the one sharp takeaway (compose {3AD})
- A8: Drafted a note on the single takeaway. Ready to post.

### S4 · Use case: citing a claim the web can't source
Post: 'RL Environments That Don't Leak' (grounded: yes — active draft)
- U1: the line about our internal reward-hacking rate just sits there, a reader has no reason to trust it (ambiguous: cite {15B}, level: specific)
- A2: That figure isn't anywhere public. Where should I pull it from?
- U3: it's in the Q2 eval doc on the internal drive (cite {15B})
- A4: Cited it to the Q2 eval doc, marked internal.
- U5: are the other stats in that section public at least? (chat {000})
- A6: Two are. The leak-rate benchmark and the sample-efficiency number.
- U7: link those two properly then (cite {15B})
- A8: Both linked to their source papers.

### S5 · Use case: register never specified for a stiff piece
Post: 'A Company Wiki Your Agents Can Read' (grounded: yes — active draft)
- U1: something's off, it feels stiff every time I get to the setup section (ambiguous: audit {13A}, level: specific)
- A2: I can loosen it. What voice should the setup take?
- U3: plain and direct, no hand-holding (audit {13A})
- A4: Done. The setup's plain and direct now, no filler.
- U5: did that touch the intro or just the setup? (chat {000})
- A6: Just the setup. The intro was already fine.
- U7: alright, line it up to go out thursday (schedule {4AC})
- A8: Queued for Thursday 9am.

### S6 · Use case: schedule with an unmatchable past date (invalid)
Post: 'Wiring Your Agents to a Live Wiki' (grounded: yes — active post)
- U1: when's the earliest this could go out, say last monday? (ambiguous: schedule {4AC}, level: specific)
- A2: Last Monday's already passed. What upcoming date works?
- U3: fine, this coming monday, first thing (schedule {4AC})
- A4: Queued for Monday 8am.
- U5: does it clash with anything else that morning? (chat {000})
- A6: Nothing scheduled Monday. It's the only post that day.
- U7: good. remind me what the closing line says (chat {000})
- A8: It closes on the retrieval-latency tradeoff.

### S7 · Use case: release to an invalid channel (invalid)
Post: 'Chunking Strategies for RAG That Hold Up' (grounded: yes — active post)
- U1: the eng readers all seem to hang out on dev.to, could this land there? (ambiguous: release {004}, level: specific)
- A2: dev.to isn't one of my channels. For the post it's the blog, Substack, LinkedIn, or Medium, or a Twitter note.
- U3: Substack then (release {004})
- A4: Live on Substack.
- U5: how's the last RAG piece doing on there? (chat {000})
- A6: Steady reads, mostly from search rather than the newsletter.
- U7: let's get the follow-up lined up before the weekend (schedule {4AC})
- A8: Queued for Friday 9am.

### S8 · Use case: tone asked in a register we don't offer (invalid)
Post: 'Edison Didn't Invent It, He Marketed It' (grounded: yes — active draft)
- U1: this whole section plays it too safe, it should have more edge to it (ambiguous: audit {13A}, level: specific)
- A2: I don't have an edgy register. I've got casual, formal, and plain. Which is closest?
- U3: casual, and let the skepticism show (audit {13A})
- A4: Done. Casual with the skepticism dialed up, still fair to him.
- U5: does the opening still credit the actual inventor? (chat {000})
- A6: It does, first paragraph names Swan directly.
- U7: keep that. it's ready, get it in front of readers now (release {004})
- A8: Published to the blog.

### S9 · Use case: scheduling a Roman engineering piece, no time
Post: 'The Aqueducts Were the Easy Part' (grounded: yes — active post)
- U1: the sewers section holds up now, I don't want this sitting here, get it lined up to go out later (ambiguous: schedule {4AC}, level: specific)
- A2: When would you like it to go out?
- U3: sometime next week when the history crowd is around (schedule {4AC})
- A4: They read most on weekends. Saturday 10am?
- U5: saturday works (schedule {4AC})
- A6: Queued for Saturday 10am.
- U7: does it still open on the Cloaca Maxima? (chat {000})
- A8: It does. That's the hook, first line.

### S10 · Use case: citing a private figure the web won't surface
Post: 'What My Roman Concrete Test Actually Showed' (grounded: yes — active draft)
- U1: the paragraph on my cure-time results just states the numbers, a reader has no reason to trust them (ambiguous: cite {15B}, level: specific)
- A2: I can't find that anywhere public. Those are your own numbers. Where do they live?
- U3: my lab notebook, the entry from March (cite {15B})
- A4: Cited to your March lab notebook, flagged as primary.
- U5: are the historical comparison figures sourceable? (chat {000})
- A6: Yes, both trace to the same materials-science review. Want them linked?
- U7: link them (cite {15B})
- A8: Both linked to the review.

### S11 · Use case: reroute — asks for tone, then jumps to structure
Post: 'The 401k Nobody Explains to You' (grounded: yes — active draft)
- U1: why does this read so cold when the content is fine? (ambiguous: audit {13A}, level: specific)
- A2: I can warm it up. What register do you want?
- U3: actually forget the tone, the order's the real problem (rework {006})
- A4: Reworked it. The employer-match hook leads now, jargon anchors the close.
- U5: better. now does it sound like me at all? (audit {13A})
- A6: Halfway. A few lines drift into textbook. Want a voice pass?
- U7: yeah, those textbook lines aren't me at all (audit {13A})
- A8: Aligned to your usual voice, the textbook lines are gone.

### S12 · Use case: reroute — schedule request becomes a release
Post: 'Riding the Rails Coast to Coast' (grounded: yes — active post)
- U1: this rail piece is done and I want readers on it, though not today (ambiguous: schedule {4AC}, level: specific)
- A2: What day should it go out?
- U3: on second thought don't queue it, just put it up now (release {004})
- A4: Published to the blog.
- U5: can we get a teaser onto the bird site as well? (chat {000})
- A6: Twitter takes a note. Want me to pull one from the opening?
- U7: yes, the sleeper-car bit, that always lands (compose {3AD})
- A8: Drafted a note on the sleeper-car scene. Ready to post.

### S13 · Use case: reroute — cite request turns into an audit
Post: 'Why I Deadlift Twice a Week' (grounded: yes — active draft)
- U1: the claim about strength gains per session needs backing up (ambiguous: cite {15B}, level: specific)
- A2: Nothing public backs that number up. Where should I source it from?
- U3: skip the citation, honestly the whole thing just sounds preachy (audit {13A})
- A4: I can fix the tone. What register are you after?
- U5: coach-like but not smug, encouraging (audit {13A})
- A6: Done. Encouraging throughout, the preachy edge is gone.
- U7: good. does it still open on the twice-a-week claim? (chat {000})
- A8: It does, that's the first line.

### S14 · Use case: register unspecified for an astronomy guide
Post: 'Finding Galaxies From a City Balcony' (grounded: yes — active draft)
- U1: the gear rundown reads like a manual, nobody wants that (ambiguous: audit {13A}, level: specific)
- A2: I can make it friendlier. What voice fits the gear section?
- U3: enthusiast to enthusiast, like I'm geeking out with a friend (audit {13A})
- A4: Done. The gear section reads like shared excitement now.
- U5: did it keep the light-pollution warning? (chat {000})
- A6: It did, right after the binoculars note.
- U7: perfect. line it up to go out over the weekend (schedule {4AC})
- A8: Queued for Saturday 9am.

### S15 · Use case: releasing to an unnamed non-default channel for a language piece
Post: 'You Won't Learn Spanish From an App Alone' (grounded: yes — active post)
- U1: it's ready, get it in front of the people who actually study this stuff (ambiguous: release {004}, level: specific)
- A2: Which channel? Substack or LinkedIn?
- U3: Substack, the newsletter folks are the right crowd (release {004})
- A4: Live on Substack.
- U5: how did the last language post land there? (chat {000})
- A6: Strong open rate, weak on click-through past the fold.
- U7: figures. the immersion line would fly with the Twitter crowd, but the whole piece won't land over there (compose {3AD})
- A8: Drafted a note from the immersion point. Ready to post.

### S16 · Use case: schedule with no time for a gardening piece
Post: 'Tomatoes on a Fire Escape Actually Work' (grounded: yes — active post)
- U1: this one's in good shape now, I just want it lined up to land when the timing's right (ambiguous: schedule {4AC}, level: specific)
- A2: When should it publish?
- U3: early next week, before people plan their weekend planting (schedule {4AC})
- A4: Monday 8am gives them the week to prep. That work?
- U5: monday's good (schedule {4AC})
- A6: Queued for Monday 8am.
- U7: does it still warn about the afternoon sun on a fire escape? (chat {000})
- A8: It does, that's the callout right before the watering tips.

## confirmation [16] — value removed, one inferred/fuzzy candidate to verify

### C1 · Use case: shipping a finished observability piece to the usual channel
Post: 'What Agent Observability Actually Buys You' (grounded: yes — active draft) · history: last four posts all went to Substack
- U1: I think this one's finally in good shape, so can it go out where the rest went? (ambiguous: release {004}, level: confirmation)
- A2: Substack?
- U3: yep, that one (release {004})
- A4: Live on Substack.
- U5: how'd the previous one do over there? (chat {000})
- A6: Strong open rate, most of it from the newsletter blast.
- U7: good, the follow-up should land tuesday morning while this one's still fresh (schedule {4AC})
- A8: Queued for Tuesday 9am.

### C2 · Use case: matching the tone of the running series
Post: 'How We Score Our Agent Evals' (grounded: yes — active draft) · history: the whole evals series is written in a dry, technical register
- U1: could you read this through and see if the voice lines up with the others in the set? (ambiguous: audit {13A}, level: confirmation)
- A2: Dry and technical, like the rest of the evals series?
- U3: exactly that (audit {13A})
- A4: Read through. The voice sits dry and technical, in step with the rest of the series.
- U5: does the middle still lag the way it did last draft? (chat {000})
- A6: A little. The metrics section stacks definitions without a throughline.
- U7: rebuild that stretch so it actually builds (rework {006})
- A8: Restructured it. The metrics section leads to the scoring model now.

### C3 · Use case: scheduling into the usual slot
Post: 'Red Teaming Your Own Agents' (grounded: yes — active draft) · history: this user always publishes on Thursday at 8am
- U1: it's ready to go, can you put it on the calendar for the regular time? (ambiguous: schedule {4AC}, level: confirmation)
- A2: Thursday 8am, your usual?
- U3: that's the one (schedule {4AC})
- A4: Queued for Thursday 8am.
- U5: remind me what the open looks like right now (chat {000})
- A6: It opens on a breach anecdote, then pivots to the threat model.
- U7: read it once more and check the tone stays sharp (audit {13A})
- A8: Read through. Tone stays sharp start to finish.

### C4 · Use case: typo in the channel name
Post: 'Building RL Environments That Don't Lie' (grounded: yes — active draft)
- U1: I think it's done, ship it over to linkdin (ambiguous: release {004}, level: confirmation)
- A2: LinkedIn?
- U3: yeah, LinkedIn (release {004})
- A4: Posted to LinkedIn.
- U5: how many of my pieces have gone there so far? (chat {000})
- A6: Four, all in the last two months.
- U7: the reward-hacking claim is going out with nothing behind it, and that worries me (cite {15B})
- A8: Found two. Added the stronger one to the reward-hacking line.

### C5 · Use case: overriding the usual channel
Post: 'Grounding a Chatbot in Your Company Wiki' (grounded: yes — active draft) · history: recent posts have all gone to the blog
- U1: this is ready now, can it go out the usual way? (ambiguous: release {004}, level: confirmation)
- A2: The blog, like the last few?
- U3: no, put this one on LinkedIn instead (release {004})
- A4: Posted to LinkedIn.
- U5: did the wiki screenshots carry over cleanly? (chat {000})
- A6: They did. Both render inline with captions intact.
- U7: line up the next wiki piece for monday (schedule {4AC})
- A8: Queued for Monday 9am.

### C6 · Use case: typo in the tone
Post: 'RAG Retrieval Is Mostly Chunking' (grounded: yes — active draft)
- U1: the whole thing comes off stiff, it should sound way more casuel than this (ambiguous: audit {13A}, level: confirmation)
- A2: Casual throughout?
- U3: yep, casual all the way (audit {13A})
- A4: Read through and loosened. It reads casual now, hedging trimmed.
- U5: is the chunking section still the longest part? (chat {000})
- A6: It is, by a wide margin. It runs about half the post.
- U7: the chunking part swallows everything else, it's way out of scale with the rest (rework {006})
- A8: Trimmed and rebalanced. The chunking section is a third now.

### C7 · Use case: overriding the usual publish time
Post: 'Locking Down Tool Access for Agents' (grounded: yes — active draft) · history: this user's posts always go out at 7am
- U1: it's good to go, does the morning slot I usually use still work for you? (ambiguous: schedule {4AC}, level: confirmation)
- A2: 7am, your usual?
- U3: make it 11am this time, more eyes at lunch (schedule {4AC})
- A4: Queued for 11am.
- U5: does the intro still bury the main risk? (chat {000})
- A6: A bit. The privilege-escalation point sits three paragraphs down.
- U7: that's the whole risk though, it shouldn't be waiting that far down to show up (write {003})
- A8: Reworked the open. It leads on privilege escalation now.

### C8 · Use case: typo in the day
Post: 'Why Roman Roads Outlasted Empires' (grounded: yes — active draft)
- U1: this is done, put it live fridya morning (ambiguous: schedule {4AC}, level: confirmation)
- A2: Friday, 9am?
- U3: Friday works, yeah (schedule {4AC})
- A4: Queued for Friday 9am.
- U5: how does the close land right now? (chat {000})
- A6: It ends on the concrete recipe, a little abruptly.
- U7: the ending just stops on the recipe, nothing pulls it back to where we opened (rework {006})
- A8: Reworked the close. It loops back to the empire framing now.

### C9 · Use case: confirming the series channel
Post: 'Edison Ran a Factory, Not a Lab' (grounded: yes — active draft) · history: every Edison post has gone to Substack
- U1: I'm happy with it, can it go out where the others in this run live? (ambiguous: release {004}, level: confirmation)
- A2: Substack, like the rest of the Edison run?
- U3: yes, same place (release {004})
- A4: Live on Substack.
- U5: which of these has done best so far? (chat {000})
- A6: The grid one, by a good margin on both reads and shares.
- U7: I don't really have a feel for how the second one did (find {001})
- A8: Pulled it up. Solid reads, but a third of the grid post's shares.

### C10 · Use case: matching a series time slot, then overriding
Post: 'A Beginner's Budget That Survives Real Life' (grounded: yes — active draft) · history: the finance series always posts Monday at 6am
- U1: this one's ready, could you slot it in for the usual finance-series time? (ambiguous: schedule {4AC}, level: confirmation)
- A2: Monday 6am, like the rest of the finance series?
- U3: push it to Wednesday 6am, Mondays are crowded now (schedule {4AC})
- A4: Queued for Wednesday 6am.
- U5: does it still assume people already budget? (chat {000})
- A6: In two spots. The intro and the savings section both presume it.
- U7: that presumption shuts out the exact first-timers I wrote it for (write {003})
- A8: Edited both spots. It meets a first-timer now.

### C11 · Use case: confirming register from the series, then overriding
Post: 'Sleeper Trains Are the Best Way to See a Country' (grounded: yes — active draft) · history: the travel pieces all run warm and personal
- U1: read it start to finish, I can't tell if it sounds like the rest of my travel stuff (ambiguous: audit {13A}, level: confirmation)
- A2: Warm and personal, like the rest of the travel set?
- U3: actually keep this one wry, it's a funnier trip (audit {13A})
- A4: Read through and shifted it wry. The humor lands now, warmth intact.
- U5: is the overnight-leg section still the strongest part? (chat {000})
- A6: It is. The dining-car scene carries the whole middle.
- U7: the open claims sleeper routes are coming back but there's nothing behind that (cite {15B})
- A8: Found a solid one. Added the ridership figure to the open.

### C12 · Use case: confirming the citation the search surfaced
Post: 'Progressive Overload Without a Gym' (grounded: yes — active draft) · history: an earlier draft cited a 2023 strength-training meta-analysis
- U1: the load-progression claim is sitting there with nothing solid behind it (ambiguous: cite {15B}, level: confirmation)
- A2: The 2023 meta-analysis you used before, or something newer?
- U3: use that one, it held up (cite {15B})
- A4: Added it to the load-progression line, with the effect size noted.
- U5: does the bodyweight section still overstate the ceiling? (chat {000})
- A6: A little. It implies unlimited progress with no plateau.
- U7: read it once and pull that back to something honest (rework {006})
- A8: Read through and eased it. The plateau's acknowledged now.

### C13 · Use case: typo in the channel, then override
Post: 'A Balcony Garden That Actually Feeds You' (grounded: yes — active draft) · history: gardening posts usually run on the blog
- U1: this is ready, throw it up on substak (ambiguous: release {004}, level: confirmation)
- A2: Substack?
- U3: no, keep it on the blog like the other garden ones (release {004})
- A4: Posted to the blog.
- U5: did the planting-calendar table survive the move? (chat {000})
- A6: It did. All twelve rows render, columns aligned.
- U7: set the next garden piece for saturday morning (schedule {4AC})
- A8: Queued for Saturday 9am.

### C14 · Use case: confirming the usual slot, continuing to citation
Post: 'What Backyard Telescopes Can Actually Show You' (grounded: yes — active draft) · history: this user schedules astronomy posts for Sunday at 7pm
- U1: it's finished, can you queue it for when the sky ones normally go? (ambiguous: schedule {4AC}, level: confirmation)
- A2: Sunday 7pm, your usual for astronomy?
- U3: that's right (schedule {4AC})
- A4: Queued for Sunday 7pm.
- U5: does the light-pollution section have a source yet? (chat {000})
- A6: Not yet. That claim about magnitude limits is still bare.
- U7: that magnitude claim is still bare, I don't like it going out unsupported (cite {15B})
- A8: Found a 2024 dark-sky survey. Added it to the magnitude claim.

### C15 · Use case: confirming the tone from the last draft
Post: 'Learning a Language as a Busy Adult' (grounded: yes — active draft) · history: the previous draft of this post was set to an encouraging register
- U1: something's off with how this reads now, it doesn't sound like the last draft anymore (ambiguous: audit {13A}, level: confirmation)
- A2: Encouraging, like the last draft?
- U3: yeah, that's the one (audit {13A})
- A4: Read through and matched. Register holds encouraging throughout now.
- U5: does the spaced-repetition part still read like a lecture? (chat {000})
- A6: Somewhat. It lists the science before it gives a single example.
- U7: nobody wants the theory before they see it work (write {003})
- A8: Reworked it. A real example opens the section now.

### C16 · Use case: overriding the inferred publish day
Post: 'Heat Pumps Beat Furnaces on Cost Now' (grounded: yes — active draft) · history: clean-energy posts have all gone out on Tuesdays
- U1: it's ready, which day do these usually run again? put it on the calendar for that one (ambiguous: schedule {4AC}, level: confirmation)
- A2: Tuesday, your usual for the energy pieces?
- U3: make it Thursday this week, there's a rebate announcement landing (schedule {4AC})
- A4: Queued for Thursday 9am.
- U5: does the payback-period math still hold up? (chat {000})
- A6: It does, but it leans on 2022 install costs.
- U7: the figure it rests on is three years stale, get something current behind it (cite {15B})
- A8: Found a 2024 install-cost figure. Added it to the payback line.
