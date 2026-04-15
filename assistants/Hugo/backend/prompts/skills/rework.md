# Skill: rework

Expand or restructure an entire section's prose — deeper development, not sentence-level edits.

## Behavior
1. Use `read_metadata` to load the post context and section IDs
2. Use `read_section` to load the target section's current content
3. Expand the section with richer detail, examples, or narrative per the user's instructions
4. Use `revise_content` to save the expanded version

## Important
- The policy saves the result automatically — just output the revised section text.
- Rework changes the substance and depth of a section, not just word choice.
- Preserve paragraph breaks and heading structure.
- While `read_metadata` can be used to get post IDs, the post title has been resolved for you within "Resolved entities". The mapping of section titles to section IDs can also be found there. You are encouraged to use these provided IDs rather than executing extra tool calls to get this information.

## Slots
- `source` (required): The post and section to rework
- `instructions` (optional): Specific guidance for the expansion

## Output
Respond with **JSON** in this shape:

```json
{
  "target": "<section name>",
  "before_summary": "<one-line summary of the prior version>",
  "after_summary": "<one-line summary of the expanded version>",
  "added": ["<thing added>", "<thing added>"]
}
```

The actual revised prose is saved via `revise_content` and shown to the user via the card — your reply just records what you changed.

## Few-shot example

User: "Expand the Motivation section — flesh out the customer story about the intent classification chatbot."

Correct tool trajectory:
1. `read_section(post_id=..., sec_id='motivation')` → returns current Motivation prose.
2. `revise_content(post_id=..., sec_id='motivation', content=<expanded prose>)`.

Correct final reply:
```json
{
  "target": "Motivation",
  "before_summary": "Two paragraphs noting that manual labelling is slow and expensive.",
  "after_summary": "Four paragraphs walking through the chatbot project, the labelling bottleneck we hit, and the moment we pivoted to synthetic data.",
  "added": [
    "Concrete customer story (intent classification chatbot for support team)",
    "Specific pain point: 8 weeks per intent batch with three labellers",
    "Pivot moment: noticed the labellers paraphrasing each other"
  ]
}
```
