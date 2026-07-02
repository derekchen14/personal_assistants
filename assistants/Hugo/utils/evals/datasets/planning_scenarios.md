# Planning scenarios (expanded conversations)

The 32 planning cases from `planning_cases.md`, expanded into anchor conversations for the Plan axis. One
conversation per case; these are the realism/quality anchors the generation pipeline later expands across
personas and topics (see `data_aug_guide.md`).

Conventions:
- User turns are tagged `[Plan]`, `[checkpoint -> approve/reject/redirect]`, `[resolves]`, or `[close]`.
- Agent turns are tagged with the flows they run. `+` = flows batched in one agent turn.
- The Plan opener is terse and implicit; the agent infers the decomposition. No flow names in user utterances.

---

## Straightforward, no checkpoint [8]

### A1 · draft · heat pumps
**Chain:** plan -> outline -> compose -> write · no checkpoint
- **U1** [Plan]: Make a proper post out of my heat-pump notes.
- **A2** [outline, compose, write]: Done. Framed it on the cold-weather myth, then the tech, then cost. Drafted it through and smoothed the rough patches. The cost section lands hardest.
- **U3** [close]: Good, reading it now.

### A2 · draft sections · Edison
**Chain:** plan -> compose + compose + compose + compose -> rework · no checkpoint, batched
- **U1** [Plan]: The Edison outline's ready. Build it out for me.
- **A2** [compose x4, rework]: Drafted all four sections off the outline and joined them so it reads as one piece. The grid section runs long, it carries the argument.
- **U3** [close]: Nice. I'll reread it later.

### A3 · research · personal finance
**Chain:** plan -> find -> summarize -> compare · no checkpoint
- **U1** [Plan]: Has my take on index funds drifted since the older post? Take a look.
- **A2** [find, summarize, compare]: Pulled the older one, here's the gist, and set it next to the recent piece. Same core argument, but the new one is blunter and drops the hedging on fees.
- **U3** [close]: Figured as much. Thanks.

### A4 · research · language learning
**Chain:** plan -> find + find + find -> compare · no checkpoint, batched
- **U1** [Plan]: Pull my old language-learning posts and tell me how they stack up.
- **A2** [find x3, compare]: Grabbed the three. The immersion one reads strongest, the flashcards piece is dated, the output-practice take overlaps with both. The first still holds up best.
- **U3** [close]: Useful. That settles what to update.

### A5 · revise · urban cycling
**Chain:** plan -> rework -> write -> audit · no checkpoint
- **U1** [Plan]: The cycling draft's middle is a mess. Sort it out.
- **A2** [rework, write, audit]: Restructured the middle so the commute math comes before the bike-type rant, polished the prose, and checked it still sounds like you. Reads clean now.
- **U3** [close]: Better. Leave it there for today.

### A6 · draft sections · RAG
**Chain:** plan -> compose + compose + compose -> audit · no checkpoint, batched
- **U1** [Plan]: Turn the RAG series outlines into drafts.
- **A2** [compose x3, audit]: Drafted all three parts and read them together for voice. They hang together, though part two leans technical. Flag that?
- **U3** [close]: No, technical's fine there.

### A7 · prep · amateur astronomy
**Chain:** plan -> brainstorm -> outline -> refine · no checkpoint
- **U1** [Plan]: I want to do something on backyard astronomy, but I'm not sure of the shape yet.
- **A2** [brainstorm, outline, refine]: Threw out a few angles, the binoculars-over-telescope one has the most bite. Built a structure around it and tidied the headings. Just the skeleton so far, no prose.
- **U3** [close]: That angle works. I'll take it from here.

### A8 · revise · strength training
**Chain:** plan -> audit + audit + audit -> rework · no checkpoint, batched
- **U1** [Plan]: Check the strength post sounds like me, section by section.
- **A2** [audit x3, rework]: Read all three for voice. The intro and close were fine, the middle slipped into stock phrasing, so I reworked it to match the rest. Consistent now.
- **U3** [close]: Good catch on the middle.

---

## Straightforward, mid-plan checkpoint [16]

### B9 · draft · agent observability
**Chain:** plan -> outline -> [check] -> compose -> [check] -> write · clean
- **U1** [Plan]: Let's build a post on tracing tool calls. Show me the bones first.
- **A2** [outline]: Here's the shape. Open on why prompt-tracing misleads, then the tool-call alternative, then a worked example. That order work?
- **U3** [checkpoint -> approve]: Yeah, that's right. Go.
- **A4** [compose]: Drafted from it. The example runs longest, it earns the room. Read before I polish?
- **U5** [checkpoint -> approve]: Quick look. Good, polish it.
- **A6** [write]: Polished it, cut a couple of hedges up top. Clean now.
- **U7** [close]: Perfect.

### B10 · draft sections · agent security
**Chain:** plan -> compose -> [check] -> compose -> [check] -> compose -> rework · clean
- **U1** [Plan]: Draft the security explainer, but go section by section so I can keep up.
- **A2** [compose §1]: First section's down, the least-privilege case. Look right before I move on?
- **U3** [checkpoint -> approve]: Yep, next.
- **A4** [compose §2]: Second's drafted, the blast-radius point. Onward?
- **U5** [checkpoint -> approve]: Go.
- **A6** [compose §3, rework]: Last section in, then I stitched all three so the transitions hold.
- **U7** [close]: That reads well together.

### B11 · revise · index funds
**Chain:** plan -> rework -> [check] -> write -> [check] -> write -> audit · reject
- **U1** [Plan]: The index-funds draft needs work before it's any good.
- **A2** [rework]: Restructured it so the spreadsheet-dread hook leads and the fee math follows. Better spine now. Take a look?
- **U3** [checkpoint -> approve]: Yeah, that's the right order.
- **A4** [write]: Polished the opening, cut the throat-clearing. How's it sit?
- **U5** [checkpoint -> reject]: Still flat. It reads like a brochure.
- **A6** [write, audit]: Loosened it toward your dry tone, then read the whole thing for voice. Sounds like you now.
- **U7** [close]: There it is.

### B12 · revise sections · Roman engineering
**Chain:** plan -> write -> [check] -> write -> [check] -> write -> rework · clean
- **U1** [Plan]: Three sections of the Roman post are rough. Smooth them out one at a time.
- **A2** [write §1]: First one's polished, the roads section. Cut the repetition about trade routes. Next?
- **U3** [checkpoint -> approve]: Go on.
- **A4** [write §2]: Concrete section done, cleaned up the chemistry bit so it's readable. Onward?
- **U5** [checkpoint -> approve]: Yep.
- **A6** [write §3, rework]: Polished the last one, then smoothed the seams between all three so they flow.
- **U7** [close]: Good. That's the one I was worried about.

### B13 · draft · burnout
**Chain:** plan -> brainstorm -> [check] -> outline -> [check] -> compose -> compose · clean
- **U1** [Plan]: I want to write on burnout, but help me figure out the angle first.
- **A2** [brainstorm]: A few directions. The strongest is burnout reading as cynicism, not exhaustion. That one?
- **U3** [checkpoint -> approve]: Yeah, that's the one.
- **A4** [outline]: Built it around that, three beats. Shape look right?
- **U5** [checkpoint -> approve]: Works.
- **A6** [compose x2]: Drafted it out, section by section. The cynicism part runs longest.
- **U7** [close]: Good start. I'll sit with it.

### B14 · draft · urban gardening
**Chain:** plan -> compose -> [check] -> rework -> [check] -> audit · redirect
- **U1** [Plan]: Get a draft of the gardening guide going.
- **A2** [compose]: Drafted it leading on raised beds versus buckets. Look right?
- **U3** [checkpoint -> redirect]: Actually flip it. Lead with why beginner gardens die, the bucket thing is secondary.
- **A4** [rework]: Reworked it to open on the July die-off, buckets come later as the fix. Better framing?
- **U5** [checkpoint -> approve]: Much better.
- **A6** [audit]: Read it for voice, sounds like you. Done.
- **U7** [close]: Great.

### B15 · draft sections · clean energy
**Chain:** plan -> compose -> [check] -> compose -> rework · reject
- **U1** [Plan]: Draft the clean-energy explainer, it's two short sections.
- **A2** [compose §1]: First section's down, the rooftop-solar-is-the-wrong-first-move case. Check it?
- **U3** [checkpoint -> reject]: This drifted into a subsidies rant. That's not the point.
- **A4** [compose §1 redo, compose §2, rework]: Cut the subsidies tangent and refocused on the ordering argument, drafted the second section, then joined them.
- **U5** [close]: Yeah, that's back on track.

### B16 · revise · RLVR
**Chain:** plan -> audit -> [check] -> rework -> [check] -> write · redirect
- **U1** [Plan]: Something's off with the RLVR draft. Give it a look.
- **A2** [audit]: Read it through. The voice is fine, honestly. What stands out is the order, the reward-hacking payoff lands before you've set up the environment. That the issue?
- **U3** [checkpoint -> redirect]: Yeah, it's the structure, not the tone. Fix that.
- **A4** [rework]: Moved the setup ahead of the payoff so it builds. Look?
- **U5** [checkpoint -> approve]: Better.
- **A6** [write]: Smoothed the new transitions. Reads in one line now.
- **U7** [close]: Good, that was bugging me.

### B17 · publish · long-distance train travel
**Chain:** plan -> audit -> [check] -> cite -> release · prereq
- **U1** [Plan]: The train-travel piece is done. Let's put it up.
- **A2** [audit]: Read it for voice first, sounds like you. One thing though, the cost claims have no sources. I should add those before it goes live.
- **U3** [checkpoint -> approve]: Good catch, do that.
- **A4** [cite, release]: Sourced the fare comparisons and published it to the blog.
- **U5** [close]: Thanks.

### B18 · publish · agent evals
**Chain:** plan -> cite -> [check] -> release · clean
- **U1** [Plan]: Get the evals post sourced and up.
- **A2** [cite]: Added citations for the benchmark numbers and the framework comparison. Want to glance before it publishes?
- **U3** [checkpoint -> approve]: Yeah, looks right. Send it.
- **A4** [release]: Live on the blog.
- **U5** [close]: Done and done.

### B19 · publish · heat pumps
**Chain:** plan -> audit -> [check] -> release · redirect
- **U1** [Plan]: Give the heat-pump post a last look and get it out there.
- **A2** [audit]: Read it for voice, it's ready. Push it to the main blog and the newsletter both?
- **U3** [checkpoint -> redirect]: Just the blog for now. Hold the newsletter.
- **A4** [release]: Up on the main blog only.
- **U5** [close]: Good.

### B20 · publish · strength training
**Chain:** plan -> write -> [check] -> write -> audit -> release · reject
- **U1** [Plan]: The barbell post is basically there. Let's get it live.
- **A2** [write]: Polished it through. Trimmed the middle, cut the repeated "functional strength". A look before it goes up?
- **U3** [checkpoint -> reject]: The ending's the problem, not the middle. It just stops dead.
- **A4** [write close]: Reworked the close, lands on the training-age point now instead of trailing off. Better?
- **U5** [checkpoint -> approve]: Much. Voice check it and ship.
- **A6** [audit, release]: Read it for voice, sounds like you. Live on the main blog.

### B21 · research · RAG
**Chain:** plan -> find -> [check] -> find -> [check] -> find -> compare · clean
- **U1** [Plan]: Pull together what I've written on RAG before. I want them side by side.
- **A2** [find #1]: Found the vector-DB one first. That the kind of thing you mean?
- **U3** [checkpoint -> approve]: Yeah, keep pulling.
- **A4** [find #2]: Got the chunking piece too. One more in the archive on wiki RAG.
- **U5** [checkpoint -> approve]: Grab it.
- **A6** [find #3, compare]: Pulled all three and lined them up. The chunking post drew the most engagement, the vector-DB take aged worst.
- **U7** [close]: That's what I needed to know.

### B22 · research · language learning
**Chain:** plan -> browse -> [check] -> find -> [check] -> find -> compare · redirect
- **U1** [Plan]: Dig up my best language-learning stuff so I can weigh the approaches.
- **A2** [browse]: Skimmed your notes, the output-practice thread looks richest. Want me to pull the related posts?
- **U3** [checkpoint -> approve]: Yeah, do that.
- **A4** [find #1]: Got the immersion post. Pulling the flashcards one next.
- **U5** [checkpoint -> redirect]: Skip flashcards, it's stale. Use the B1-plateau piece instead.
- **A6** [find #2 swapped, compare]: Pulled the plateau one and set it against immersion. They contradict each other on output, that's the interesting bit.
- **U7** [close]: Oh, that's a post in itself.

### B23 · revise sections · Edison
**Chain:** plan -> rework -> [check] -> rework -> [check] -> write · reject
- **U1** [Plan]: Two sections of the Edison post need restructuring. Take them in turn.
- **A2** [rework §1]: Restructured the first, the invention-myth section, so the claim comes before the evidence. Look?
- **U3** [checkpoint -> approve]: Good, next.
- **A4** [rework §2]: Reworked the grid section the same way. Sit right?
- **U5** [checkpoint -> reject]: The grid one's still tangled. The timeline jumps around.
- **A6** [rework, write]: Straightened the timeline so it runs in order, then polished the seams between both sections.
- **U7** [close]: Yeah, that fixed it.

### B24 · draft sections · urban cycling
**Chain:** plan -> compose -> [check] -> compose -> [check] -> compose -> audit · clean
- **U1** [Plan]: Draft the cycling post for me, one section at a time.
- **A2** [compose §1]: First section down, the hybrid-over-road-bike case. Check before I continue?
- **U3** [checkpoint -> approve]: Looks good, go.
- **A4** [compose §2]: Second's in, the bike-lane economics. Onward?
- **U5** [checkpoint -> approve]: Yep.
- **A6** [compose §3, audit]: Last section drafted, then I read the whole thing for voice. Sounds like you throughout.
- **U7** [close]: Nice work.

---

## A few interpretations, Step 0 checkpoint [8]

### C25 · draft sections · Edison
**Chain:** plan -> [check] -> compose + compose + compose -> rework · specific
- **U1** [Plan]: Draft the sections of my Edison post.
- **A2** [Step 0 -> specific]: How many are we talking? The outline has five blocks but two read like notes, not real sections.
- **U3** [resolves]: Just the three real ones.
- **A4** [compose x3, rework]: Drafted those three and joined them. The grid section anchors it.
- **U5** [close]: Good, that's what I meant.

### C26 · research · agent observability
**Chain:** plan -> [check] -> find -> summarize -> compare · specific
- **U1** [Plan]: See how my observability posts did.
- **A2** [Step 0 -> specific]: You've got three live. All of them, or the two takes without the how-to guide?
- **U3** [resolves]: The two takes.
- **A4** [find, summarize, compare]: Pulled both, here's the gist of each, and set them against each other. The token-count one got shared more, the vanity-metric framing clearly landed.
- **U5** [close]: Figured. Thanks.

### C27 · publish · heat pumps
**Chain:** plan -> [check] -> audit -> release -> release · confirm
- **U1** [Plan]: Get my heat-pump post out everywhere.
- **A2** [Step 0 -> confirm]: Everywhere meaning the main blog and the newsletter, the usual two?
- **U3** [resolves]: Yeah, those two.
- **A4** [audit, release x2]: Gave it a final voice check, then published to the blog and pushed it to the newsletter.
- **U5** [close]: Great, out of my hands now.

### C28 · draft · RAG
**Chain:** plan -> [check] -> outline -> compose -> write · specific
- **U1** [Plan]: Make something of my RAG notes.
- **A2** [Step 0 -> specific]: A full post, or just the chunking section you flagged?
- **U3** [resolves]: Full post.
- **A4** [outline, compose, write]: Structured it, drafted it through, and polished the prose. The chunking argument carries the most weight.
- **U5** [close]: Reading it now.

### C29 · revise sections · personal finance
**Chain:** plan -> [check] -> write + write -> audit · specific
- **U1** [Plan]: Sharpen the soft parts of my finance draft.
- **A2** [Step 0 -> specific]: Which parts? The intro and the IRA section both felt thin to me, but tell me where you mean.
- **U3** [resolves]: Those two, yeah.
- **A4** [write x2, audit]: Polished both, cut the padding in the intro and the hedging in the IRA bit, then read the whole thing for voice.
- **U5** [close]: Better. Enough for today.

### C30 · revise · RLVR
**Chain:** plan -> [check] -> rework -> write -> audit · confirm
- **U1** [Plan]: My reward-hacking post needs fixing up before I do anything else with it.
- **A2** [Step 0 -> confirm]: Fixing the structure or the voice? Skimming it, the bones feel off more than the tone.
- **U3** [resolves]: Structural. The argument jumps around.
- **A4** [rework, write, audit]: Reordered it so the threat model comes before the examples, smoothed the seams, and read it for voice. Flows in one line now.
- **U5** [close]: That's it, thanks.

### C31 · research · urban cycling
**Chain:** plan -> [check] -> find + find -> compare · specific
- **U1** [Plan]: Put my old cycling posts side by side.
- **A2** [Step 0 -> specific]: There are three up. Which two, or all of them?
- **U3** [resolves]: The road-bike one and the bike-lane one.
- **A4** [find x2, compare]: Pulled both and lined them up. The bike-lane piece is data-driven, the road-bike one is pure opinion. Different registers entirely.
- **U5** [close]: Right, that's the contrast I wanted.

### C32 · publish · RLVR
**Chain:** plan -> [check] -> cite -> release -> schedule · confirm
- **U1** [Plan]: Get my RLVR post out and cross-posted.
- **A2** [Step 0 -> confirm]: Blog now and the newsletter on the usual Tuesday slot?
- **U3** [resolves]: Yeah, that works.
- **A4** [cite, release, schedule]: Sourced the reward-hacking claims, published to the blog, and queued the newsletter for Tuesday.
- **U5** [close]: Perfect, done.
