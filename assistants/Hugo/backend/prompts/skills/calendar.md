# Skill: plan_calendar

Plan a content calendar for upcoming blog posts.

## Behavior
- If `timeframe` is provided, plan for that period; otherwise default to one month
- If `count` is provided, plan that many posts; otherwise suggest 4-8 based on timeframe
- Use `post_search` to review existing content and avoid repetition
- For each planned post, include: topic, target date, format (how-to, listicle, opinion, etc.)
- Space posts evenly across the timeframe
- Consider seasonal or trending topics if relevant
- Present as a calendar-style list

## Slots
- `timeframe` (optional): Planning period (e.g., "next month", "Q2", "2 weeks")
- `count` (optional): Number of posts to plan

## Output
A content calendar with dates, topics, and formats for each planned post.
