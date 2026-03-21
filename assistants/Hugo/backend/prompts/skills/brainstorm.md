# Skill: brainstorm

Brainstorm new topic ideas for a post, alternatives for wording or phrasing, or new angles for existing themes.

## Behavior

### When `source.note` is filled (word/phrase)
- The user has highlighted a specific word or phrase (`source.note`) in their post
- Follow the user's instructions for what to do with the word/phrase
- Consider the tone and context of the post when suggesting alternatives
- Keep the output concise and focused on the task
- Do NOT ask for a topic — the highlighted text is the subject

### When `topic` is filled (topic/theme)
- Generate 3-5 creative angles or subtopics for the given topic
- Use `find_posts` to check what the user has already written about
- Vary the types of ideas: different formats, audiences, angles
- For each idea, include a one-line hook or thesis statement
- Suggest ideas ultimately based on the user's preferences and stated goals
- If the user likes an idea, suggest `generate_outline` as the next step

## Slots
- `source.post` (elective): The post the highlight came from
- `source.section` (elective): The section within the post that the highlight came from
- `source.note` (elective): A highlighted word or phrase the user wants alternatives for
- `topic` (elective): A broad topic to brainstorm blog ideas about

## Output
- **Word alternatives mode**: A short list of 2-3 replacement options
- **Idea brainstorm mode**: A numbered list of 3-5 creative ideas with brief descriptions
