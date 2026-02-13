# Style Guide

## Languages & Runtimes

| Layer | Language | Runtime |
|---|---|---|
| Backend | Python | 3.14 |
| Frontend | TypeScript | Node 24 |

## Formatting

- **Indentation**: 4 spaces for both Python and TypeScript
- **Line length**: 100 characters preferred, 120 absolute maximum
- **Quotes**:
  - Single quotes for all internal strings (code logic, keys, identifiers)
  - Double quotes only for user utterances (external-facing text)
  - Rationale: Distinguishes internal strings from user input. User utterances are more likely to contain contractions (e.g., "don't") that conflict with single quotes.

## Naming

### Files and Folders
- Always `snake_case`

### Code Identifiers

| Construct | Python | TypeScript |
|---|---|---|
| Functions | `snake_case` | `camelCase` |
| Variables | `snake_case` | `camelCase` |
| Classes | `PascalCase` | `PascalCase` |

### Naming Rules
- Functions are **verbs**, classes are **nouns**
- Names should be **2-4 words** to provide sufficient descriptive power
- 1-word names are too vague — add context
- 5+ word names signal the function is doing too much — refactor into a class with focused methods

## Imports

Order: `stdlib` → `third-party` → `local`, alphabetized within each group.

- Each import line should import from a single source and fit on one line
- Aim for a maximum of **3 items** per source, with **4 as a hard limit**
- Beyond 4 items: use a wildcard import (for helper modules) or refactor to reduce dependencies
- Wildcard sources rely on underscore-prefix convention (`_private`) rather than requiring `__all__`

## Tooling

| Tool | Python | TypeScript |
|---|---|---|
| Linter | Ruff | ESLint |
| Package manager | uv | npm |
| Test framework | pytest | — |

### Test Conventions (Python only)
- Test files mirror source files: `test_<module>.py`
- Test functions: `test_<behavior>()`
- No TypeScript tests

## Configuration & Constants

- **Configs**: Stored in YAML files
- **Assistant setup**: `config.py` at the root of each assistant folder
- **Constants / ontology**: `ontology.py` at the root of each assistant folder

## Documentation

- Only add docstrings to **public** functions and classes, and only if they are **complex**
- A function over 10 lines generally warrants a docstring
- Do not add docstrings to simple/obvious code

## Functions & Complexity

- No hard line limit, but functions should **fit on one screen**
- No inheritance deeper than **3 levels**
- Global state is acceptable if **read-only**, but should be avoided when possible

## Logging

Use Python's `logging` module with levels (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`). No bare `print()` statements in production code.

## Prompt Engineering

Non-negotiable standards for all LLM prompts in the system. These apply to skill/policy prompts assembled by the Prompt Engineer component.

### Standard Prompt Format

Every assembled prompt follows this 8-slot structure, in order:

| Slot | Name | Content |
|---|---|---|
| 1 | **Grounding data** | Runtime variables: `{columns}`, `{history}`, `{facts}`, schemas, table definitions. All context the model needs to reference goes here. |
| 2 | **Role and task** | Who the model is and the high-level task. Loaded from the domain's persona config. |
| 3 | **Detailed instructions** | Step-by-step guidance for the specific task. The core of the skill template. |
| 4 | **Keywords and options** | Valid terms, enum lists, special vocabulary. Constrains the model's output space. |
| 5 | **Output shape** | Exact JSON keys, types, and structure expected in the response. |
| 6 | **Exemplars** | 7-10 diverse examples with edge cases (see [Exemplar Standards](#exemplar-standards)). |
| 7 | **Closing reminder** | One-liner reinforcing the output format (see [Closing Reminder](#closing-reminder)). |
| 8 | **Final request** | The current query with injected runtime variables. Always last. |

Grounding data goes first because Anthropic measured a 30% quality improvement with data-first ordering — the model attends better to context placed before the task. The final request goes last so the model's next token is the answer.

Skill templates (see `tool_smith.md`) provide slots 2-6. The Prompt Engineer injects slot 1 (grounding data) and slot 8 (final request) at assembly time. Slot 7 (closing reminder) is appended by the Prompt Engineer after the template's exemplars.

### Output Rules

- All prompts return a parseable JSON object — no plain text, no markdown, no exceptions
- This includes RES response generation: even user-facing responses are wrapped in a JSON envelope
- Classification and decision prompts must include a `"thought"` key before the answer key for chain-of-thought reasoning
- After the JSON output, no further text or explanations

### Exemplar Standards

Exemplar count varies by prompt complexity and how much the task depends on pattern-matching vs. instruction-following:

| Prompt type | Count | Rationale |
|---|---|---|
| NLU `think()` — intent prediction, flow detection | ~32 | High-cardinality classification across 48 flows; examples are the primary teaching signal |
| NLU `contemplation()` | ~16 | Multi-step reasoning with fewer categories but subtle distinctions |
| PEX skill/policy prompts | 7-10 | Moderate complexity; balanced between examples and instructions |
| RES response generation | 3-5 | Output shaped more by instructions and persona than by pattern-matching |

- Exemplars must be diverse: cover success cases, ambiguous inputs, edge cases, and at least one error/null case
- Each exemplar is separated by a `---` delimiter
- Use `_Output_` label before each example's output, followed by a ` ```json ` code fence
- Exemplar variables use double-brace escaping (`{{`, `}}`) for f-string compatibility
- Exemplars are a testing surface — if evaluation scores drop, add exemplars for the failing cases first

### Delimiter Convention

- **Section boundaries**: Markdown headings (`##`) for major sections within a prompt
- **Example boundaries**: `---` between exemplars
- **Output labels**: `_Output_` before each example response
- **Code fences**: Triple backticks with language tag (` ```json `, ` ```sql `)
- No XML tags, no `#############`, no mixed delimiter styles

### Context Placement

- All grounding data (schemas, column lists, conversation history, facts) goes at the **top** of the prompt (slot 1)
- The final request / current query goes at the **bottom** (slot 8)
- Both static context (table schemas, valid options) and dynamic context (conversation history) go early
- Rationale: Anthropic measured 30% quality improvement with data-first ordering in long-context prompts

### Closing Reminder

- One-liner placed after the exemplars section, before the final request (slot 7)
- Reinforces the output format, e.g.: "Your entire response should be well-formatted JSON with no further text after the output."
- Varies slightly per prompt but always references the expected format
- Per OpenAI research, a closing reminder reduces output format violations

### Variable Naming

- Runtime placeholders: `{snake_case}` wrapped in single curly braces
- Use double braces `{{`, `}}` for literal braces in f-string templates
- Placeholder names match the source data field names when possible

### Consensus Norms

These principles are shared by all major prompt engineering guides (OpenAI, Anthropic, Google) and are non-negotiable:

- **Be explicit and specific** — a single clarifying sentence can change model behavior
- **Positive instructions** — tell the model what TO do, rarely what NOT to do
- **Consistent delimiters** — Markdown headings + `---` throughout, no mixing styles
- **Explicit output format** — specify exact JSON keys, types, and structure
- **Chain-of-thought** — classification/decision prompts include a `"thought"` key before the answer
- **Diverse exemplars** — examples must cover success cases, edge cases, and error conditions
- **Iterate empirically** — prompt engineering is experimental; use the evaluation framework to test changes
