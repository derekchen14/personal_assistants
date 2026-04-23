# Fixes — `compose` Flow

**Status:** applied (see themes listed below)

## Back-references to Part 1

- Inventory: `inventory/compose.md`
- Relevant sections: § Stack-on triggers (outline prerequisite), § Persistence calls, § Tool plan, § Frame shape, § Known gaps (double-persist risk, per-section iteration ownership)
- Primary SUMMARY.md themes: **T1 (skill/policy contract confusion — double persistence)**, **T6 (stack-on opacity)**

## Changes that landed

### Skill owns persistence — `_persist_section` removed from the policy

- **What changed:** The prior `compose_policy` wrote composed text back via `_persist_section(post_id, sec_id, text, tools)` after `llm_execute` returned, which itself called `revise_content`. The skill's few-shot example ALSO called `revise_content` per section. Two writes, one overwriting the other in ambiguous ways. Fix: policy no longer calls `_persist_section`. `llm_execute` is now invoked with `include_preview=True` so the skill has per-section previews preloaded (title + short content preview) and can plan without re-fetching. `skills/compose.md` was rewritten to state explicitly that "The skill owns persistence — you MUST call `revise_content` for every section you compose. The policy does not save automatically." The skill defaults to single-section scope unless the user explicitly asks for the whole post, in which case it loops one section at a time — per user feedback (d) confirming the per-section loop pattern.
- **Why:** Inventory § Known gaps #1 and #2 + SUMMARY.md § Theme 1 flagged the double-persist ambiguity. The clean resolution is "one owner" — and since the LLM already iterates section-by-section naturally, the skill is the correct owner.
- **Theme:** Theme 1 (skill/policy contract confusion).
- **Files touched:**
  - `backend/modules/policies/draft.py` — `compose_policy` (removed `_persist_section` call, added `include_preview=True`)
  - `backend/prompts/skills/compose.md` (rewrite: Behavior steps 2-4 now describe scope-decision + per-section loop; Important section calls out persistence ownership)

```python
# compose_policy, post-fix:
text, tool_log = self.llm_execute(flow, state, context, tools, include_preview=True)
flow.status = 'Completed'
frame = DisplayFrame(origin='compose', thoughts=text)
if post_id:
    frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
```

### Stack-on to `OutlineFlow` when the post has no sections — reason surfaced inline

- **What changed:** The "post has no `section_ids`" branch continues to stack `OutlineFlow`, but now attaches the transition reason to `thoughts`: `return DisplayFrame(thoughts='No sections yet — outlining first.')`. No new fields, no helper — inline `flow_stack.stackon('outline')` + `state.keep_going = True` + reason in `thoughts`, matching the Theme 6 convention.
- **Why:** Inventory § Stack-on triggers flagged the transition as opaque (user asks for prose, gets an outline form with no explanation). Theme 6 landed a uniform pattern across compose and refine without introducing new component attributes.
- **Theme:** Theme 6 (stack-on ergonomics).
- **Files touched:**
  - `backend/modules/policies/draft.py` — `compose_policy` lines ~221-228

```python
if result['_success'] and not result.get('section_ids'):
    self.flow_stack.stackon('outline')
    state.keep_going = True
    return DisplayFrame(thoughts='No sections yet — outlining first.')
```

## Architectural decisions applied

- **AD-6** — compose currently has no contract-violation backstop (a failed `convert_to_prose` retry is handled inside the skill by "skip this section, move on" rather than surfacing an error frame). If the whole flow produces zero `revise_content` calls, this should eventually become an error frame; tracked under follow-ups.
- **AD-5** — inline stack-on phrasing (the post "stacks on" outline); no new DisplayFrame attributes.

> **Part 2 alignment.** This fix aligns with [§ 8 Determinism boundaries](../best_practices.md#8-determinism-boundaries) and [§ 6 Stage machines inside policies](../best_practices.md#6-stage-machines-inside-policies). See [Deterministic Core, Agentic Shell — davemo.com](https://blog.davemo.com/posts/2026-02-14-deterministic-core-agentic-shell.html) on one owner per concern — skill owns persistence end-to-end, the policy does not double-write — and [SitePoint — Agentic Design Patterns 2026](https://www.sitepoint.com/the-definitive-guide-to-agentic-design-patterns-in-2026/) on surfacing stage transitions (stack-on to outline) through user-visible reason text rather than hidden flags.

## Open follow-ups

- No policy-side check that the skill actually called `revise_content` at least once. A future AD-6 contract-violation backstop could assert `tool_succeeded(tool_log, 'revise_content')` and return an error frame if the skill silently skipped every section.
- The `steps` / `guidance` slots are now exemplified only implicitly (via the "decide scope from the user's utterance" instruction). If these slots start appearing filled without coverage, add targeted few-shots similar to the `rework`/`simplify`/`polish` Theme 2 additions.
- Tone-matching guidance ("Match the tone and style of existing sections") still relies on the section_preview being useful. If the preview proves too short in practice, the skill may need an explicit `read_section` on adjacent sections — currently not exemplified.
