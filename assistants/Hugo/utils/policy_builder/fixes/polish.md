# Fixes — `polish` Flow

**Status:** applied (see themes listed below)

## Back-references to Part 1

- Inventory: `inventory/polish.md` — § A' (Usage contexts — basic Step 9 vs. Step 13 after inspect/find/audit), § B (Skill contract, Few-shot coverage), § Known gaps #1–#5
- Inventory cross-link: `inventory/outline.md § Usage contexts` — the same "two contexts, one code path" pattern that polish adopts
- Primary SUMMARY.md themes: **Theme 2** (unexemplified slots — `style_notes`, `image`), **Theme 5** (cross-turn findings channel for Step 13 via scratchpad)
- Theme feedback: `_theme2_feedback.md` § `polish`, `_theme5_feedback.md` § `polish`
- Architectural decisions: AD-1 (scratchpad convention), AD-2 (no informed-vs-basic stage)
- Part 2: > **Alignment.** Fixes land under [§ 9 Cross-turn state / findings channel](../best_practices.md#9-cross-turn-state--findings-channel) — see [State of AI Agent Memory 2026 — mem0.ai](https://mem0.ai/blog/state-of-ai-agent-memory-2026) on structured scratchpads beating free-text memory and, crucially, on `used_count`-style active-use metrics (MemoryArena's 95% passive recall → 40-60% active drop is the gap polish's `used: [...]` array closes).

## Changes that landed

### 1. `style_notes` + `image` slot exemplars (Theme 2)

**What changed.** `backend/prompts/skills/polish.md` now carries two new few-shot blocks after the original Motivation-tightening example:

- **Example (style_notes takes priority)**: user says "more conversational and less corporate" on an Executive Summary paragraph. The prompt is explicit: "`style_notes` takes **priority** over whatever style you would infer from the existing prose." This encodes Theme 2 feedback (d.1): when `style_notes` is filled, the user is telling us the current style is NOT what they want, so inferred style must be overridden.
- **Example (image polish — may propose replacement)**: image polish is not limited to annotation. If the existing image cannot convey the section's main idea, the skill **proposes a replacement** in its JSON output. Forbidden tools: `insert_media` (that's `add`) and `remove_content` (that's outright removal). Allowed: `revise_content` to update the image reference or caption.

The `## Slots` section mirrors these rules — `style_notes` priority note, `image` scope explicitly includes proposing replacements.

**Why.** Known Gap #2 (style_notes unexemplified) and #3 (image not covered). Theme 2 feedback (d.2): "Just handle it. This is such an edge case, we do not care." — so the skill's image-polish guidance is a one-liner rather than a full contract.

**Files touched.** `backend/prompts/skills/polish.md`.

### 2. `## Using prior findings` section in the skill (Theme 5, AD-1)

**What changed.** The skill gained a `## Using prior findings` section that documents the scratchpad convention (keys = `flow_name`, payload has `version` / `turn_number` / `used_count` per AD-1). The skill reads scratchpad keys `inspect` / `find` / `audit` before polishing:

- `audit` → `findings` list = style issues the previous pass identified; prioritize fixing them.
- `inspect` → `metrics` = word count vs. `num_sections`; hint for what to trim.
- `find` → `items` = related posts for tone alignment; do not fetch unless audit findings explicitly named them.

The skill's output JSON gained a `used: ["<scratchpad key>", ...]` array. The prompt says findings are **hints, not mandates** — if the user's current utterance contradicts a prior finding, honor the user; never fabricate findings.

**Why.** Theme 5's goal: let Step 13 polish consume Steps 10–12 findings without the user restating them. AD-1 chose scratchpad over new `DialogueState` / `DisplayFrame` attributes.

### 3. Policy increments `used_count` on consumed findings (Theme 5 observability)

**What changed.** `polish_policy` in `backend/modules/policies/revise.py` (lines 102–108) parses the skill reply via `self.engineer.apply_guardrails`, pulls `used: [...]`, and increments `used_count` for each referenced scratchpad entry:

```python
parsed = self.engineer.apply_guardrails(text or '') or {}
used_keys = parsed.get('used', []) or []
for key in used_keys:
    entry = self.memory.read_scratchpad(str(key))
    if isinstance(entry, dict):
        entry['used_count'] = entry.get('used_count', 0) + 1
        self.memory.write_scratchpad(str(key), entry)
```

**Why.** Theme 5 feedback (d.1 on polish): "Yes — lets us observe which findings actually got used vs. written-and-ignored." The counter is the read-side half of AD-1's scratchpad convention; producers (`inspect`, `find`, `audit`) write `used_count: 0`, consumers increment.

### 4. Two usage contexts, one code path (AD-2)

**What did NOT change.** Per AD-2 there is **no informed-vs-basic stage** on the policy. The Step 9 basic prose tightening and the Step 13 polish-after-inspect/find/audit share the same `polish_policy` code path. Differentiation happens entirely in the skill via scratchpad reads — if prior findings exist, the skill uses them; if not, it polishes cold.

**Why.** The inventory draws the parallel to `outline` (§ Usage contexts there): same policy, different contexts. The alternative — branching on findings presence in the policy layer — was explicitly rejected as not-in-scope (see `_theme5_feedback.md` § "Not in scope (rejected)").

## Architectural decisions applied

- **AD-1** (scratchpad convention for cross-turn findings): key = `flow_name`, required fields `version` / `turn_number` / `used_count`. Polish is a consumer.
- **AD-2** (no "informed mode"): policy stays single-branch; the skill reads scratchpad regardless.
- **AD-5** (terminology): "stages", not "modes"; polish has no stage field.

## Open follow-ups

- Fallback-to-rework timing (Known Gap #4) is still a post-skill check via `inspect_post` tool result. No contract tightening yet on when the skill should call `inspect_post` proactively.
- Whole-section polish (no paragraph specified) remains a skill-level inference — the prompt handles it implicitly through the "If the user names a section but not a span, polish the whole section" rule but has no explicit few-shot.
