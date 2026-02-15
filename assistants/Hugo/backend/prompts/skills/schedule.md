# Skill: schedule_post

Schedule a post for future publication.

## Behavior
- Use `post_get` to verify the post exists and is ready
- Parse the `datetime` slot into a publication date/time
- Use `platform_list` to verify the target platform is connected
- Use `platform_publish` with the scheduled datetime
- Confirm the scheduled date and time with the user
- Store the schedule in the post metadata via `post_update`

## Slots
- `post_id` (required): The post to schedule
- `platform` (required): Target platform
- `datetime` (required): When to publish (e.g., "tomorrow at 9am", "March 15 2pm")

## Output
Confirmation of the scheduled publication with date, time, and platform.
