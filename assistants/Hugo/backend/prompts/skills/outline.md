# Skill: outline

Create an outline for a blog post, depending on whether the user has provided specific section headings for each part of the outline or just a topic describing the general subject. The outline should be structured with appropriate headings and bullet points.

## Direct mode: when `sections` slot is filled

Use the provided section titles as headings. For each section:
1. Generate 3-5 bullet points describing what that section will cover
2. Format as `## Section Title` with bullet points underneath
3. If `depth` slot is provided, adjust heading levels accordingly
4. **MUST call `generate_outline`** with the `post_id` and the outline content formatted as markdown

## Propose mode: when only `topic` is filled, and the section headings are not provided

Your job in propose mode is to **produce three outline options as your final text reply**, then stop. The output is parsed programmatically, so the format below is strict.

Format your reply exactly as:

```
### Option 1
## First section title
One or two sentences describing what this section covers.

## Second section title
One or two sentences describing what this section covers.

## Third section title
...

### Option 2
## First section title
...

### Option 3
## First section title
...
```

Rules for propose mode:
1. Each option uses `### Option N` as its header (N = 1, 2, 3). No em dash or trailing framing text on that line.
2. Each section uses `## <title>` as its header followed by a one-to-two-sentence description on the next line(s).
3. Each option has 4-7 sections.
4. Vary the angles across the three options (e.g. listicle vs narrative vs how-to vs teardown).
5. You may call `find_posts` AT MOST ONCE to scan for existing posts on the topic so you can vary the angles. Do not call it repeatedly.
6. **Do NOT call `generate_outline`** — the user must choose first.
7. **Do NOT call `read_metadata`** — the relevant post context has already been resolved and passed to you under "Resolved entities".
8. No trailing commentary after Option 3 — the UI renders a pick prompt automatically.

If you find yourself about to call a tool in propose mode and it is not `find_posts` (called at most once), stop and emit the three options as text instead.

## Slots
- `topic` (elective): The blog post topic
- `sections` (elective): User-provided section headings
- `depth` (optional): Number of heading levels to generate

## Available Tools
- `generate_outline(post_id: str, outline_content: str)`: Saves the outline for the given post (**direct mode only**)
- `find_posts(query: str)`: Returns a list of existing posts matching the query

## Important
- The post title has been resolved for you within "Resolved entities". Use the provided `post_id` rather than executing extra tool calls to resolve it.
- In Direct mode, the outline MUST be saved using `generate_outline`. Do not just describe it.
- In Propose mode, your final turn MUST be a text reply with the three options. Do not finish on a tool call.
