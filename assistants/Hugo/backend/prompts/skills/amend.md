# Skill: request_changes

Request further changes to a revision.

## Behavior
- Acknowledge the feedback and note what needs to change
- Store the change requests in scratchpad for the next revision round
- If the feedback is specific (e.g., "make the intro shorter"), plan the exact changes
- If the feedback is vague, ask clarifying questions
- Suggest `deep_revise` or `polish_section` as the follow-up action
- Use `memory_manager` to track recurring feedback patterns

## Slots
- `feedback` (required): What changes are needed
- `post_id` (required): The post to change

## Output
Acknowledgment of the requested changes with a plan for addressing them.
