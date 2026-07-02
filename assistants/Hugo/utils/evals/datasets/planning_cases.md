# Planning use cases (Plan intent, multi-flow chains)

The 32 planning storylines for the Plan axis (data_aug_guide.md axis 6). A planning convo opens with a
multi-step goal that NLU labels **Plan intent** (no flow of its own); PEX decomposes it into ordered
**existing** catalog flows, chains them, and judges when the goal is met. These are a rough sketch like
`use_cases.md`: generation follows the FLOWS, the turn structure, and the checkpoint pattern, not the
storyline wording.

## What a realistic plan looks like

Real plans are bigger than a 9-turn happy path, and they do **not** march outline -> publish in one go.
Realism comes from staying focused and from real work between turns. Plans take a few shapes:

- **Heterogeneous sequence** — 2 or 3 distinct flows, one each (e.g. structure, draft, then polish a
  section).
- **Fan-out (repetition)** — one flow repeated, one per sub-task (a section / source / part / channel), each
  a sub-agent, usually closed by a join flow (`rework`/`write` to stitch, `compare` to synthesize). This is
  **one** pattern, not the default; most plans are not pure fan-outs.
- **Mix** — some repetition plus a distinct flow or two.

Two firm limits across all shapes: **2 or 3 unique flows only**, and a plan **stays within a phase or two
adjacent ones** (drafting+revising, or revising+publishing on an existing post) rather than running a whole
post from outline to live publish.

**Intent mix.** Across all 32, the flows the plans produce skew by intent roughly **20% Research / 30% Draft /
40% Revise / 10% Publish** — blog work is mostly revising. (Current tally: 21 / 32 / 44 / 11 = 19 / 30 / 41 /
10%.)

**The opener is terse and implicit.** The Plan turn names the goal in **1-2 parts (usually 1), not the steps**:
"get the barbell post ready to publish," not "polish it, then voice-check it, then publish to the blog." The
agent must infer the decomposition from incomplete or implied information; that inference is the thing being
tested. An occasional opener may list a couple of steps, but most must not. Over-specifying the steps is the
main realism failure.

## Notation

`- [family] <chain> : <storyline> (tag)`

- `plan` — the Plan-intent opener (turn 1, no flow/dax).
- `->` — the next item is a **later turn**.
- `+` — items joined by `+` run in the **same turn** (batched same-type sub-agents, in parallel). This is the
  "single turn, multiple flows" case; a `->` chain of single flows is the "multiple turns, single flows" case.
  With no checkpoint, even a `->` chain of different-type flows runs on one turn (PEX keeps going).
- `[check]` — a checkpoint where PEX pauses for user input; **not a flow**. Right after `plan` = Step 0
  (upfront); between flows = mid-plan.
- Tag: `clean` (user approves at the checkpoint), `reject` / `redirect` (user pushes back, agent replans),
  `prereq` (a flow discovers a missing input and stacks it), `confirm` / `specific` (the Step 0 clarification
  level). Chains show the **realized** path; the storyline explains the original ask for a redirect.

## Three ways a plan is handled

1. **Straightforward [24]** — instructions are clear, so PEX decomposes immediately. **8 run with no
   checkpoint** (low-stakes, often short or batched, no live publish) and **16 carry a mid-plan checkpoint**
   (human-in-the-loop between steps, especially before publishing).
2. **A few interpretations [8]** — still **Plan intent**, but a **Step 0** checkpoint up front: the agent asks
   one targeted clarification (which sections / sources / channels, or which kind of fix), the user resolves
   it, then execution runs.
3. **Completely unclear** — that is **Clarify intent**, not Plan, and belongs to the Ambiguity axis, not here.

## Rules (carried from axis 3 / axis 6)

Forward through Research -> Draft -> Revise -> Publish; no `find -> compose`; no `compose -> release`; and no
single plan spanning outline -> publish (out of scope to evaluate). Repeated same-type flows are sub-tasks,
not iteration. Publish-phase plans assume the post already exists (the work is finishing and shipping, not a
fresh draft).

## What the evals score

Per planning convo: (1) turn 1 intent = Plan; (2) the **decomposition** (the ordered flows, scored on
selection and order); (3) **turn structure** (batched in one turn vs. spread across turns); (4) **checkpoint
behavior** (paused where `[check]` is marked, chained where it is not); (5) per-flow dax / slots /
expected_tools from the catalog; (6) **goal completion** (concludes after the last flow); (7) disruption
resolution where tagged.

---

## Straightforward, no checkpoint [8]
- [draft] plan -> outline -> compose -> write : Structure the heat-pump piece, draft it from there, and smooth the one rough paragraph, all in a single pass.
- [draft sections] plan -> compose + compose + compose + compose -> rework : Draft all four sections of the Edison post from the outline at once, then a pass to join them.
- [research] plan -> find -> summarize -> compare : Pull a past finance post, condense it, and set it against the newer one to see how the tone shifted.
- [research] plan -> find + find + find -> compare : Pull three old language-learning posts together and compare how they read. Pure prep.
- [revise] plan -> rework -> write -> audit : Restructure the weak middle of the cycling draft, polish it, and check it still sounds like the writer.
- [draft sections] plan -> compose + compose + compose -> audit : Draft all three parts of a RAG series from their outlines, then one voice check across them.
- [prep] plan -> brainstorm -> outline -> refine : Spin a few angles for an astronomy post, lay out a structure, and tidy the outline. No prose yet.
- [revise] plan -> audit + audit + audit -> rework : Voice-check three sections of the strength-training post, then a rework to fix what the checks surface.

## Straightforward, mid-plan checkpoint [16]
- [draft] plan -> outline -> [check] -> compose -> [check] -> write : Structure the observability post, approve the shape, draft the prose, look it over, then a polish pass. (clean)
- [draft sections] plan -> compose -> [check] -> compose -> [check] -> compose -> rework : Draft the agent-security explainer section by section, a quick look after each, then join them. (clean)
- [revise] plan -> rework -> [check] -> write -> [check] -> write -> audit : Restructure the index-funds draft, review, polish it, but the user says it still reads flat, so another pass before the final voice check. (reject)
- [revise sections] plan -> write -> [check] -> write -> [check] -> write -> rework : Polish three sections of the Roman-engineering post in turn, reviewing each, then a rework to smooth the transitions. (clean)
- [draft] plan -> brainstorm -> [check] -> outline -> [check] -> compose -> compose : Spin angles for the burnout post, pick a direction, structure it, approve, then draft it out section by section. (clean)
- [draft] plan -> compose -> [check] -> rework -> [check] -> audit : Draft the gardening guide, then restructure a weak stretch and voice-check; at the first review the user shifts the angle, so the rework follows the new one. (redirect)
- [draft sections] plan -> compose -> [check] -> compose -> rework : Draft a two-section clean-energy explainer; after section one the user says it drifted, so it is redrafted before the second and the join. (reject)
- [revise] plan -> audit -> [check] -> rework -> [check] -> write : Voice-check the RLVR draft, then restructure and polish; at the review the user says the voice is fine but the structure is the real problem, narrowing the work. (redirect)
- [publish] plan -> audit -> [check] -> cite -> release : Final voice check on the train-travel post; at the review the agent flags uncited claims and adds them before publishing. (prereq)
- [publish] plan -> cite -> [check] -> release : Add citations to the finished agent-evals post, confirm, then publish it to the blog. (clean)
- [publish] plan -> audit -> [check] -> release : Voice-check the heat-pump post, planning to publish to two channels; at the check the user pulls it back to just the main blog. (redirect)
- [publish] plan -> write -> [check] -> write -> audit -> release : Final polish on the strength-training post; the user rejects the close at the review, so it is redone, voice-checked, then published. (reject)
- [research] plan -> find -> [check] -> find -> [check] -> find -> compare : Pull past RAG posts one at a time, confirming each is relevant, then compare them. (clean)
- [research] plan -> browse -> [check] -> find -> [check] -> find -> compare : Browse notes for an angle, pull two related posts, then compare; at a checkpoint the user swaps one source for a better one. (redirect)
- [revise sections] plan -> rework -> [check] -> rework -> [check] -> write : Restructure two weak sections of the Edison post in turn, then a polish to connect them; at the second review the user asks for one more restructure. (reject)
- [draft sections] plan -> compose -> [check] -> compose -> [check] -> compose -> audit : Draft the cycling post section by section with a review after each, then a single voice check. (clean)

## A few interpretations, Step 0 checkpoint [8]
- [draft sections] plan -> [check] -> compose + compose + compose -> rework : "Draft the sections of my Edison post." How many sections is unclear, so the agent confirms the list, composes them, then joins. (specific)
- [research] plan -> [check] -> find -> summarize -> compare : "See how my observability posts did." Which posts is ambiguous, so the agent asks, pulls one, condenses it, then compares to another. (specific)
- [publish] plan -> [check] -> audit -> release -> release : "Publish my heat-pump post everywhere." The agent confirms the two channels meant, voice-checks, then publishes to both. (confirm)
- [draft] plan -> [check] -> outline -> compose -> write : "Write up my RAG notes." Whether that is a full post or one section is unclear, so the agent confirms, then structures, drafts, and polishes. (specific)
- [revise sections] plan -> [check] -> write + write -> audit : "Tighten the weak parts of my finance draft." Which sections is unclear, so the agent confirms the two, polishes them, then a voice check. (specific)
- [revise] plan -> [check] -> rework -> write -> audit : "Fix up my reward-hacking post." A structural or a voice fix is unclear; the agent confirms it is structural, reworks, polishes, then checks voice. (confirm)
- [research] plan -> [check] -> find + find -> compare : "Compare my old cycling posts." Which two is unclear, so the agent asks, pulls both, then compares. (specific)
- [publish] plan -> [check] -> cite -> release -> schedule : "Get my RLVR post out and cross-posted." Channels and timing are unclear, so the agent confirms, cites, publishes, then schedules. (confirm)
