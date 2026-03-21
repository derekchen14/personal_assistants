# Skill: cite

Add a citation to a note, or search the web for a supporting source.

## Behavior
- Use `post_get` to load the post and locate the target note
- If a URL is provided: attach it directly to the note using `post_update`
- If only a note is provided: use `web_search` to find a credible supporting source
  - Prefer primary sources (papers, official docs) over secondary blogs
  - Present the proposed citation with title, domain, and a one-sentence rationale
  - Attach only after the proposal is accepted (the user confirmation is part of the flow policy)
- Use `post_update` to persist the citation

## Slots
- `source` (elective): The note to attach a citation to; `note` field targets the specific note
- `url` (elective): The URL to attach directly; at least one of source or url is required

## Output
Confirmation of the attached citation, or a proposed source for user approval.
