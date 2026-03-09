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

## Experiment Runs

- **Never kick off experiment runs (API calls) without explicit user permission.** Always ask before starting new processes that make API calls, even to resume incomplete runs.
