# Skill: propose

Present proposed core dacts for the user's domain.

## Behavior

- Read the current config with `config_read` to get intents and entities
- Generate 16 core dacts following the grammar:
  - 8 universal: chat, insert, update, delete, user, agent, accept, reject
  - 8 domain-specific: 4 verbs + 3 nouns + 1 adjective derived from the user's intents/entities
- Present the dacts in a table with: name, hex code, POS, rationale
- Ask the user to review and approve/modify each one
- Use `config_write` to save approved dacts to the "dacts" section

## Output

A structured list of 16 proposed dacts for the user to review.
