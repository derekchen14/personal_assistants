# Project: Assistant Factory

## New components or concepts

- **Never create new concepts without explicit user permission.** Always ask before creating new types of classes or adding new components. We want to maintain a single source of truth for the agent's behavior, so we should not be creating new concepts that are already accessible from existing components.
  - Look at the helper functions within the components to see if the behavior is already implemented.
  - If not, then you can make a new function to access data within the component
  - However, do not create new components to duplicate the data elsewhere.
- Frames have attributes of [origin, metadata, blocks, code, and thoughts]. This is enough to capture all the necessary information the agent may display to the user, so do not create new components or attributes on the display frame without explicit user permission.

## General Mindset

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- No new concepts or methods when existing ones will do
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

## Code style

1. **Variable naming:**
   - The output of `context.compile_history()` is `convo_history`. Not `history`, `history_text`, or `utterances`.
   - Unless distinguishing between `curr_state` and `prev_state`, use `state` for the dialogue state. Not `dialog_state`, `dialogue_state`, or `convo_state`.
   - Variable names should aim to be the same across all three modules (NLU, PEX, and RES) whenever possible.
      - variable names should aim to be a single token long
      - when variable names are just 4 to 7 characters long, it's often acceptable to just use the full word
      - If more than one word is needed, use underscores to separate words.
   - Never use variable names that are a single character long
      - Use `idx` instead of `i`
      - Use `slot` or `sec` instead of `s`
      - Use `flow` instead of `f`
      - Use `ent` for entity, or `entry` for dictionary entry, or `ecp` for exception

2. **Short function signatures:**
   - Pass in fewer parameters whenever possible:
      - Functions already have defaults — when not deviating from the default, don't pass the param.
      - Certain objects (e.g., `flow`, `state`, `frame`) have lots of helpful attributes, so passing the single object means you don't have to pass so many parameters.
      - Having fewer parameters often means you can keep a function call on a single line, rather than breaking it across multiple lines.
   - Preferred style is to trim the spaces within each parameter:
      - Good: `take_turn(self, text:str, dax:str|None=None, payload:dict|None=None)`
      - Bad: `take_turn(self, text: str, dax: str | None = None, payload: dict | None = None)`
   - Parameter limits:
      - Any given function should usually have 4 or fewer parameters and only 5 max (not including `self`).
      - If a function needs more than 5 parameters, it's a sign that the function is doing too much and should be refactored.
   
3. **Maximum nesting depth of 6 tabs (24 spaces).** 
   Nesting up to 6 tabs is allowed, but should be rare. When code exceeds this, fix it by:
   - Removing extraneous safety checks that guard against scenarios that can't occur in this codebase.
   - Extracting the deeply nested logic into a module-level helper function.
   - Simplifying another part of the code that contributes unnecessary nesting.

4. **Function Design**
   - Functions over 30 lines are likely doing too much and should be split up
   - Prefer flat code over multiple layers of indirection — don't extract functions prematurely
   - Only extract a helper function if it's used 3+ times; fewer than that is over-engineering
   - Helper functions should contain at least 3 lines — one-liners just add indirection without saving space

5. **Line Lengths should go to 100 characters**
   - Assume a line length of roughly 100 characters (with a hard stop of 120 chars)
   - This applies to writing comments, markdown files, and code
   - Multi-line comments should break around 100 characters rather than 70 chars
   - Avoid splitting into multiple lines when the combined result can comfortably fit in one line instead
      - Try to keep a function and its parameters in one line, rather than a new line for each param
      - Try to Keep a dictionary and its items in one line, rather than a new line for each key

## Avoid Defensive Programming

The major reason to avoid the extra guards is because the modules and pipeline of the assistant guarantee certain contracts. If an upstream module actually did pass in a broken object, we want the app to fail so we can see this error and fix the bug immediately. Loud failures can be amended, but silent failures mysteriously cause broken user experiences.

For example, in the NLU/PEX/RES modules, code downstream can rely on them. Do **not** add defensive `if x is None` / `x and ...` / `.get()` fallbacks for them.

- **NLU.understand** always returns a `DialogueState`. State is never None downstream.
- **PEX.execute** always returns a `DisplayFrame`. Never None, never a raw dict.
- **RES.respond** always returns `(utterance: str, frame: DisplayFrame)`. RES is responsible for popping completed flows from the stack, so it may assume there is an active flow at entry.

Moreover we also have guarantees for different components:

- Payloads from our own frontend are an *internal* contract, not external input. Don't add `isinstance`, `.get(key, '')`, or empty-string fallbacks in NLU / policy payload handlers — if the FE sends a broken shape, crash loudly so we fix it at the source. Prefer semantic invariants (e.g. `turn_type == 'action'` whenever `payload` is present) over shape-of-data defenses.
- **Every turn has a flow.** After NLU runs there is always an active flow on `flow_stack`; `flow_stack.get_active_flow()` returns a real `BaseFlow` inside PEX and RES. Worst case is a `DismissFlow` signalling negative sentiment — something is always there.
- **DialogueState invariants** - a state always has:
  - active_post attribute - the value may be None, but the attribute always exists
  - booleans for `keep_going`, `has_issues`, `has_plan`, `natural_birth`
  - access to the predicted flows and intent
- **DisplayFrame invariants** — a frame always has:
  - `origin: str` (may be empty)
  - `blocks: list` (may be empty)
  - `metadata: dict` (may be empty)
  - `thoughts: str` (may be empty)
  Check `frame.blocks` (truthy) when you need a non-empty list, not `hasattr` or `is not None`.

More generally, do NOT add error handling for scenarios that can't happen:

   - `dict.get(key, default)` — only when the key may legitimately be absent OR the default is a real fallback. If an earlier guard clause already verified presence/filled, use direct indexing (`d[key]`).
   - `if x and ...` / `if x is not None` — drop the check when `x` is guaranteed by contract. In this repo:
      - `flow.slots[<declared_name>]` is always present (initialized in `__init__`); only `.filled` may vary.
      - `state` is always non-None inside a policy — `Agent.take_turn` constructs it before PEX runs.
      - Service results always contain `_success`; on `_success=True`, the documented success keys are always present.
   - Don't repeat a filled-check that a guard clause higher in the same function already performed.
   - When in doubt between a defensive `.get()` with a fake default and a direct `[]` that would raise: prefer raising. A crash on a broken invariant is a bug report; a silent fallback is a ghost.
   - Function signatures should define one clean contract — don't overload them to accept many shapes (dict OR kwargs OR string OR None) "just in case." Let bad calls crash immediately, not get massaged.
   - Guardrails are for genuinely unpredictable inputs (external data, LLM output, network responses), not for caller mistakes. `setdefault`, `.get(key, '')`, and silent early-returns on wrong types hide caller bugs that should surface.
   - Nested `if` chains are usually stacked defensive checks. If you find yourself writing `if x: if y: if z:` around the core operation, most of those guards are disposable; trust the contract and crash on violation.

## Bash Commands — Permission Rules

The permission system blocks shell composition syntax (`&&`, `&`, `$()`, `2>/dev/null`, newlines).
Follow these rules to avoid permission denials:

- **Never chain commands** with `&&`, `||`, `;`, or newlines. Make separate Bash tool calls instead.
- **Never background with `&`**. Use the Bash tool's `run_in_background: true` parameter.
- **Avoid `2>/dev/null` and `2>&1` redirects**. If a command might error, just let it error — the output is still useful.
- **Avoid `$()` command substitution** in inline commands. If you need substitution, use a script file or restructure as a pipe.
- **Run independent commands as parallel Bash calls** in a single message, not as a single chained command.

## Misc and Other

1. Use native Tailwind CSS classes instead of creating custom CSS classes whenever possible.
2. Use `uv pip install` instead of `pip install` for all Python package installations.
3. Avoid using the words 'tighten' or 'delve'


