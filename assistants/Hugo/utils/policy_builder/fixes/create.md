# Fixes — `create` Flow

**Status:** applied (see themes listed below)

## Back-references to Part 1

- Inventory: `inventory/create.md`
- Relevant sections: § Guard clauses, § Persistence calls, § Ambiguity patterns, § Few-shot coverage, § Known gaps
- Primary SUMMARY.md themes: **T1 (skill/policy contract confusion)**, **T3 (output-shape drift)**, **T6 (stack-on)**

## Changes that landed

### Skill file deleted — `create` is a deterministic, non-LLM flow

- **What changed:** `backend/prompts/skills/create.md` was deleted outright. The policy never called `llm_execute`; the skill was pure dead-code documentation for a path that did not exist (and the skill's declared JSON output shape was never parsed or rendered anywhere).
- **Why:** Inventory § Known gaps #1 and SUMMARY.md § Theme 1 both flagged the skill as dead code. `_theme3_feedback.md § create` resolved this as "Option A: keep create deterministic, delete the aspirational skill." That is what landed.
- **Theme:** Theme 1 (skill/policy contract confusion) with Theme 3 as the secondary driver (no more shape mismatch because there is no more skill).
- **Files touched:**
  - `backend/prompts/skills/create.md` (deleted)

### Duplicate-title branch: `'specific'` ambiguity on an error frame

- **What changed:** The duplicate-title branch in `create_policy` no longer routes through `ambiguity.declare('confirmation', metadata={'reason': 'duplicate_file'})` with a confirmation block. It now calls `self.ambiguity.declare('specific', metadata={'duplicate_title': slots['title']})` and returns `DisplayFrame('error', metadata={'duplicate_title': slots['title']})`.
- **Why:** Per user's (d) feedback on Theme 4 — a duplicate title is a user mistake, not a candidate value awaiting sign-off. `confirmation` is reserved for genuine "candidate value needs user approval" cases (AD-6 § 3).
- **Theme:** Theme 4 (error-path gaps) informed the reclassification; Theme 3 (output-shape drift) informed dropping the confirmation block.
- **Files touched:**
  - `backend/modules/policies/draft.py` — `create_policy` lines ~286-288

```python
elif result.get('_error') == 'duplicate':
    self.ambiguity.declare('specific', metadata={'duplicate_title': slots['title']})
    frame = DisplayFrame('error', metadata={'duplicate_title': slots['title']})
```

### Topic-provided path stacks on `OutlineFlow` inline

- **What changed:** After a successful `create_post`, if the `topic` slot was filled the policy now pushes `OutlineFlow` on top of the stack, pre-fills the new post's id into `outline_flow.slots['source']` (as the `post=` entity part) and forwards the topic into `outline_flow.slots['topic']`, then sets `state.keep_going = True` and attaches a short transition note to `frame.thoughts` ("Created the post — moving on to outline.").
- **Why:** Inventory § Known gaps #2 flagged topic handling as undefined: the slot was passed to `create_post` but nothing ever generated the promised initial outline. The Theme 6 convention (inline `flow_stack.stackon()` + `state.keep_going = True` + reason in `thoughts`, no helper) is used verbatim. No new flags or fields invented.
- **Theme:** Theme 6 (stack-on ergonomics). Theme 7 rejected the `stack_on` helper, so the pattern is inline.
- **Files touched:**
  - `backend/modules/policies/draft.py` — `create_policy` lines ~277-284

```python
if 'topic' in slots:
    self.flow_stack.stackon('outline')
    state.keep_going = True
    outline_flow = self.flow_stack.get_flow()
    outline_flow.slots['source'].add_one(post=new_id)
    outline_flow.slots['topic'].add_one(slots['topic'])
    frame.thoughts = 'Created the post — moving on to outline.'
```

## Architectural decisions applied

- **AD-3** (outline recursion safety) — the stacked `OutlineFlow` may not itself `stackon('outline')`, so the topic-provided chain is bounded at one extra flow deep.
- **AD-6** (three failure modes, three channels) — duplicate-title is reclassified as **ambiguous user intent** at the `specific` level (known intent, invalid slot value) rather than `confirmation`. Not a tool-call failure, not a contract violation.
- **AD-5** (terminology) — "stacks on" is the correct term; no references to NLU "firing" anything were introduced.

> **Part 2 alignment.** This fix aligns with [§ 8 Determinism boundaries](../best_practices.md#8-determinism-boundaries). See [Deterministic Core, Agentic Shell — davemo.com](https://blog.davemo.com/posts/2026-02-14-deterministic-core-agentic-shell.html) on pushing the LLM boundary outward — `create` has no judgment-shaped step, so the aspirational skill was dead code that the deterministic policy already subsumed.

## Open follow-ups

- The eval rubric for step 1 (`create`) does not yet assert that a `topic`-provided utterance results in an `OutlineFlow` being stacked. Part 4 should add that assertion.
- RES template text for the transition thought ("Created the post — moving on to outline.") lives directly in the policy for now. If a third stack-on reason appears, revisit centralizing the strings in `modules/templates/draft.py` per the Theme 6 feedback note.
