# Skill: plan_series

Plan a multi-part blog series.

## Behavior
- Design a cohesive series structure around the given theme
- If `part_count` is specified, plan that many parts; otherwise suggest 3-5
- For each part: topic, angle, how it connects to previous/next parts
- Use `post_search` to check for existing content that could be part of the series
- Include a publication schedule suggestion

## Slots
- `theme` (required): The overarching theme for the series
- `part_count` (optional): Number of parts in the series

## Output
A series plan with individual part descriptions and connections.
