# Skill

Pull FAQs, business data, or reference information from the knowledge base.

## Behavior

- Search the organizational knowledge base via `context_coordinator` for the requested topic.
- Check `memory_manager` for previously stored business data or FAQs.
- If found, present the information clearly with its source.
- If not found, let the user know and suggest alternative ways to find the information.
- This flow is for reference/business data, not for loading datasets into the workspace.

## Slots

- `topic` (required): The subject or question to look up.
- `source` (optional): Where to search (e.g., "FAQs", "policies", "business rules").

## Output

A `card` block with the retrieved information.
