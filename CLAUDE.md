# Project: Personal Assistants

## Package Management

- Use `uv pip install` instead of `pip install` for all Python package installations.

## Bash Commands — Permission Rules

The permission system blocks shell composition syntax (`&&`, `&`, `$()`, `2>/dev/null`, newlines).
Follow these rules to avoid permission denials:

- **Never chain commands** with `&&`, `||`, `;`, or newlines. Make separate Bash tool calls instead.
- **Never background with `&`**. Use the Bash tool's `run_in_background: true` parameter.
- **Avoid `2>/dev/null` and `2>&1` redirects**. If a command might error, just let it error — the output is still useful.
- **Avoid `$()` command substitution** in inline commands. If you need substitution, use a script file or restructure as a pipe.
- **Run independent commands as parallel Bash calls** in a single message, not as a single chained command.

## New components or concepts

- **Never create new concepts without explicit user permission.** Always ask before creating new types of classes or adding new components. We want to maintain a single source of truth for the agent's behavior, so we should not be creating new concepts that are already accessible from existing components.
  - Look at the helper functions within the components to see if the behavior is already implemented.
  - If not, then you can make a new function to access data within the component
  - However, do not create new components to duplicate the data elsewhere.

## Code style

1. **Pass in fewer parameters whenever possible:**
   - Functions already have defaults — when not deviating from the default, don't pass the param.
   - Certain objects (e.g., `flow`, `state`, `frame`) have lots of helpful attributes, so passing the single object means you don't have to pass so many parameters.
   - Any given function should usually have 4 or fewer parameters and only 5 max (not including `self`).
   - Having fewer parameters often means you can keep a function call on a single line, rather than breaking it across multiple lines.

2. **Consistent naming:**
   - The output of `context.compile_history()` is `convo_history`. Not `history`, `history_text`, or `utterances`.
   - Unless distinguishing between `curr_state` and `prev_state`, use `state` for the dialogue state. Not `dialog_state`, `dialogue_state`, or `convo_state`.
   - Variable names should aim to be the same across all three modules (NLU, PEX, and RES) whenever possible.

