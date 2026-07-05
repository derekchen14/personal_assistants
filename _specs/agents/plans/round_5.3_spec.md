# Round 5.3 Spec — Flow Prompt Consolidation

Verified against live source at commit `1615be4`. Every file:line below was read from that tip.
All paths are relative to `assistants/Hugo/`.

## 5.3.0 Goal and shape of the change

Hugo's 16 per-flow markdown files under `backend/prompts/pex/skills/` are NOT progressively-loaded
agent skills — every flow sub-agent loads its own file unconditionally on each turn. They are flow
instruction prompts. This round:

- moves them to `backend/prompts/pex/flows/` and drops their frontmatter,
- collapses each per-flow starter to a runtime-parameter renderer (no more duplicated task/tool-order
  prose in the starter),
- makes `schemas/ontology.py::FLOW_CATALOG` the sole home of the flow description and the flow class
  `tools` list the sole tool registry,
- renames the four `skill`-named methods/functions to say "flow",
- keeps `plan.md` (the Workflow Planner) as the one real agent skill, in `backend/prompts/pex/skills/`,
- folds in two content fixes (audit: too many read actions; compose no-re-read),
- retires the one drift test that only policed the now-deleted frontmatter/tools duplication.

Expected net: deletion. Starters lose their `<task>` prose; 16 files lose frontmatter; one test and
three private loader helpers go away. The only additions are four specified one-line prompt edits and
one `extra_resolved` preload.

---

## 5.3.1 Directory and file moves

1. Create `backend/prompts/pex/flows/`.
2. `git mv` all 16 flow files from `backend/prompts/pex/skills/` to `backend/prompts/pex/flows/`:
   `audit, brainstorm, browse, chat, cite, compare, compose, find, outline, propose, refine,
   release, rework, schedule, summarize, write` (`.md`).
3. `plan.md` STAYS in `backend/prompts/pex/skills/`. After the move, `pex/skills/` holds only
   `plan.md`, and `pex/flows/` holds exactly the 16 flow prompts.

Reason (5.3.11-a): two real directories, each holding one concept — flow prompts vs agent skills.
`pex/flows/` globs to exactly the 16 flow names, so no exclusion list is needed anywhere.

---

## 5.3.2 Frontmatter removal (all 16 flow files)

Delete the leading `---` … `---` YAML block from every file in `pex/flows/`. Each file begins at its
first body line (for most, the "This flow …" paragraph or the first `#` heading). Concretely each file
loses: `name`, `description`, `version`, `tools` (and `outline.md` also loses `stages`).

- The `description` now lives only in `FLOW_CATALOG` (already present — see `schemas/ontology.py`
  lines 55–187, one `description` per flow). Do not touch `FLOW_CATALOG`.
- The `tools` list now lives only on the flow class (`backend/components/flow_stack/flows.py`,
  `flow.tools`). Do not touch the flow classes.
- `version`, `name`, `stages` had no runtime consumer at all (only `load_skill_meta` read frontmatter,
  and its only caller is the drift test being retired — see 5.3.8).

`plan.md` has no frontmatter today; leave it as-is.

Do NOT mass-rewrite the word "skill" inside the body prose of the 16 files. Rewriting every "This
skill …" sentence is high-churn, non-deterministic, and risks introducing slop. The reframe is
structural (location + frontmatter + method names + starter merge), not a prose sweep. The only body
edits are the four specified in 5.3.6/5.3.7.

---

## 5.3.3 Loader rewrite — `backend/components/prompt_engineer.py`

Current (lines 70–73, 686–719): `_SKILL_DIRS` (two dirs, second one `prompts/skills/` does not exist),
`_resolve_skill_path` (loops dirs), `load_skill_template` (strips frontmatter, returns body or None),
`load_skill_meta` (returns frontmatter dict), `_split_frontmatter`.

Replace with two explicit class-level dir constants and two thin classmethods; delete the three private
helpers and `load_skill_meta`.

```python
# class-level, replacing _SKILL_DIRS (lines 70-73)
_FLOW_DIR  = Path(__file__).resolve().parents[1] / 'prompts' / 'pex' / 'flows'
_SKILL_DIR = Path(__file__).resolve().parents[1] / 'prompts' / 'pex' / 'skills'

@classmethod
def load_flow_prompt(cls, flow_name:str) -> str:
    """Full markdown instruction prompt for a flow sub-agent (pex/flows/<flow>.md)."""
    return (cls._FLOW_DIR / f'{flow_name}.md').read_text(encoding='utf-8')

@classmethod
def load_skill(cls, skill_name:str) -> str:
    """An agent-level skill body (pex/skills/<skill>.md) — currently only the Workflow Planner."""
    return (cls._SKILL_DIR / f'{skill_name}.md').read_text(encoding='utf-8')
```

Delete: `_resolve_skill_path` (686–692), `load_skill_template` (694–700), `load_skill_meta` (702–708),
`_split_frontmatter` (710–719), and the old `_SKILL_DIRS` (70–73).

Contract note (no defensive programming): every flow has a `pex/flows/*.md`, so `load_flow_prompt`
returns a real string and never None. A missing file raises `FileNotFoundError` loudly — that is the
desired failure. Remove the old `None` return and every `or ''` / `is None` guard that only existed to
tolerate a missing file (see the call sites in 5.3.4).

Reason (5.3.11-b): two named methods beat one two-dir search because the two directories now mean two
different things; a flow prompt and an agent skill should not resolve through the same fuzzy lookup.
Each method is a one-liner, so there is no shared helper (a 2-use helper would be over-extraction).

---

## 5.3.4 Rename map (every call site)

| Old | New | Kind |
|---|---|---|
| `PromptEngineer.skill_call` | `PromptEngineer.flow_reply` | method (sub-agent, no tools → str) |
| `PromptEngineer.tool_call` | `PromptEngineer.flow_execute` | method (sub-agent, with tools → (str, tool_log)) |
| `for_pex.build_skill_system` | `for_pex.build_flow_system` | function |
| `for_pex.build_skill_messages` | `for_pex.build_flow_messages` | function |
| `PromptEngineer.load_skill_template` | `PromptEngineer.load_flow_prompt` | method (5.3.3) |
| `PromptEngineer.load_skill_meta` | — (deleted, 5.3.3) | — |
| divider `--- {Flow} Skill Instructions ---` | `--- {Flow} Flow Instructions ---` | text, for_pex.py:63 |

`flow_reply` keeps its round-4.6 `model:str='med'` argument. `flow_execute` keeps its full signature
(`schema`, `model`, etc.) unchanged apart from the name.

Call sites to sweep (exhaustive — grep confirms no others):

1. `backend/components/prompt_engineer.py`
   - line 16 import: `from backend.prompts.for_pex import build_flow_system, build_flow_messages`.
   - `skill_call` def (181) → `flow_reply`; body uses `load_flow_prompt` (186), `build_flow_system`
     (188), `build_flow_messages` (189).
   - `tool_call` def (199) → `flow_execute`; body uses `load_flow_prompt` (209), `build_flow_system`
     (211), `build_flow_messages` (212).
2. `backend/prompts/for_pex.py` — rename the two functions (51, 68); update the divider (63); update
   `_render_starter`/`_default_starter` per 5.3.5.
3. `backend/modules/policies/base.py:83` — `self.engineer.tool_call(...)` → `self.engineer.flow_execute(...)`.
4. `backend/modules/policies/research.py`
   - line 46: `self.engineer.skill_call(...)` → `flow_reply`.
   - line 72: `self.engineer.load_skill_template(flow.name())` → `load_flow_prompt(flow.name())`.
   - line 73: `self.engineer.skill_call(...)` → `flow_reply`.
5. `backend/prompts/for_orchestrator.py:233` — `engineer.load_skill_template("plan")` →
   `engineer.load_skill("plan")` (plan is an agent skill in `pex/skills/`, not a flow prompt).
6. Tests (see 5.3.8): `utils/evaluation_suite/_tests/pex_unit_tests.py` lines 556–557 (`tool_call` →
   `flow_execute`), 560/566/567 (`skill_call` → `flow_reply`), 1647 import, 1695/1710
   (`load_skill_template` → `load_flow_prompt`), and the drift block.
7. Doc-only: `utils/helper_ref.md:36` mentions `_SKILL_DIRS` — update the sentence to name `_FLOW_DIR`
   / `_SKILL_DIR` and `load_flow_prompt`/`load_skill`. Optional but keeps the reference honest.

Note: `_TASK_SUFFIXES` still has a `'skill'` key (prompt_engineer.py:26) and `_get_temperature(task=
'skill')` — that is a `__call__`/`stream` task label, a different concept from the flow sub-agent
methods. Leave it. Out of scope for this round.

---

## 5.3.5 `backend/prompts/for_pex.py` — assembly + starter shrink

### 5.3.5.1 Module docstring (1–17) and function docstrings

Rewrite the docstring to describe: system = persona + intent prompt + ambiguity block + flow prompt
(`pex/flows/<flow>.md`) + closing reminder; user message = filled starter (runtime parameters +
preloaded content) + recent conversation. Replace the words "skill body"/"skill file"/"Skill-rendering
helpers" with "flow prompt" / "starter render helpers". No banned words.

### 5.3.5.2 `build_flow_system` (was build_skill_system, 51–65)

Behavior unchanged except the divider text. `parts` still = `[base_system, intent_prompt,
AMBIGUITY_AND_ERRORS, (divider + flow_prompt), SLOT_7_REMINDER]`. Only line 63 changes:

```python
parts.append(f'\n\n--- {flow_name} Flow Instructions ---\n\n{flow_prompt}')
```

Rename the `skill_prompt` parameter to `flow_prompt` for clarity (local rename; both call sites in
prompt_engineer.py pass positionally / update the keyword). `AMBIGUITY_AND_ERRORS` stays as-is (the
shared block is kept per the approved direction).

### 5.3.5.3 `build_flow_messages` (was build_skill_messages, 68–84)

No logic change beyond the rename. Update the docstring line "The starter owns task framing, preloaded
content, and resolved details." → "The starter renders runtime parameters and any preloaded content;
task framing now lives in the flow prompt."

### 5.3.5.4 `_default_starter` (95–125) — drop the synthesized task

`chat`, `find`, `propose` use this (no per-flow starter module). Remove the `<task>` synthesis; return
only the resolved-details block. Keep the slot-iteration that builds `details` and keep
`_summarize_entity`.

```python
def _default_starter(flow, resolved:dict) -> str:
    """Generic renderer for flows without a custom starter module. Emits only <resolved_details>;
    task framing lives in the flow prompt."""
    details_lines = []
    for slot_name, slot in flow.slots.items():
        ...  # unchanged loop, lines 109-120
    details = '\n'.join(details_lines) if details_lines else '(no parameters filled)'
    return f'<resolved_details>\n{details}\n</resolved_details>'
```

Delete the `post_title` / `title_clause` / `task` lines (102–107, 122–124). `_render_starter` (87–92)
is unchanged.

---

## 5.3.6 Per-flow starter shrink + merge plan

Rule for every starter in `backend/prompts/pex/starters/`: delete the `<task> … </task>` block from the
`TEMPLATE`(s) and delete the `build()` logic that computed `tool_sequence` / `verb` / `end_condition`.
Keep every preloaded content block (`<post_content>`, `<post_preview>`, `<line_content>`) and the
`<resolved_details>` block. Keep `_format_parameters` and the render helpers unchanged. The `build`
signature stays `build(flow, resolved, user_text)` (still called positionally by `_render_starter`;
`user_text` stays in the signature even where unused, so the call site needs no change).

The task/tool-order prose being deleted is already present in the corresponding flow `.md` (Process +
Tools). So the default per-flow action is DELETE-ONLY. Four flows also need one specified sentence
ADDED to their `.md` because the starter carried a judgment the `.md` did not state; those are called
out below and in 5.3.7.

| Starter | Action | New `build()` output | Notes |
|---|---|---|---|
| `audit.py` | delete `<task>`+`tool_sequence` (9–28); ADD `<post_content>` prose block (5.3.7) | `<post_content>` + `<resolved_details>` | keep `_format_parameters` |
| `brainstorm.py` | delete `<task>`+verb/tool_sequence/end_condition (9–45) | `<resolved_details>` only | topic-vs-snippet judgment already in brainstorm.md Process 2/3 |
| `browse.py` | delete `<task>` (10–16) | `<resolved_details>` only | narration rule already in browse.md |
| `cite.py` | delete `<task>`+tool_sequence from both templates (12–53) | `<line_content>` (when snippet) + `<resolved_details>` | keep the two-template split (snippet vs none) for the content block only |
| `compare.py` | delete `<task>`+`_DIFF_CLAUSE` (7–28) | `<post_content>` (when previews) + `<resolved_details>` | keep both templates for the previews block only |
| `compose.py` | delete `<task>` (11–21) | `<post_content>` + `<resolved_details>` | compose.md Process 3 already has the read/convert/save loop |
| `outline.py` | delete `<task>`+tool_sequence/end_condition (13–45); ADD forbidden-tools sentence to outline.md (5.3.7) | `<resolved_details>` only | |
| `refine.py` | delete `<task>` (9–19) | `<post_content>` + `<resolved_details>` | refine.md Process 4 + Tools already carry the full tool map |
| `release.py` | delete `<task>` (7–13) | `<resolved_details>` only | |
| `rework.py` | delete `<task>`+tool_sequence (12–37) | `<post_preview>` + `<resolved_details>` | |
| `schedule.py` | delete `<task>` (7–13) | `<resolved_details>` only | |
| `summarize.py` | delete `<task>` from both templates (7–39) | `<post_content>` (when outline) + `<resolved_details>` | keep both templates for the outline block only; Length stays in resolved_details |
| `write.py` | delete `<task>`+3-way tool_sequence (9–33); ADD image sentence to write.md (5.3.7) | `<resolved_details>` only | style_notes priority already in write.md step 3 |

For starters that keep a conditional content block (cite/compare/summarize), the `build()` still
branches on whether the block's data is present, but returns the block(s) + `<resolved_details>` with no
`<task>`. Example, `compose.py::build` after the change:

```python
def build(flow, resolved:dict, user_text:str) -> str:
    section_previews = render_section_preview(resolved.get('section_preview') or {})
    if not section_previews:
        section_previews = '(section previews not preloaded — read_metadata include_preview=True first)'
    return (f'<post_content>\n{section_previews}\n</post_content>\n\n'
            f'<resolved_details>\n{_format_parameters(flow)}\n</resolved_details>')
```

---

## 5.3.7 Content fixes (folded in while touching the files)

### 5.3.7.1 Audit: too many read actions (approved point 5a)

Problem: `audit.md` step 1a tells the sub-agent to `read_section` every section before `editor_review`
— N repeated read actions. Fix by preloading the full post prose once in the policy and telling the flow to use
it.

`backend/modules/policies/revise.py::audit_policy` (225–245): at line 233–234, fetch the pre-edit prose
once and pass it via `extra_resolved`. `_read_post_content` already returns the full post markdown via
`read_metadata(include_outline=True)`.

```python
self.record_snapshot(self.content, flow, context, post_id)
pre = self._read_post_content(post_id, tools)
text, tool_log = self.llm_execute(flow, state, context, tools,
    extra_resolved={'post_prose': pre.get('content', '')})
```

Leave line 244 (`self._read_post_content(post_id, tools)` for the card) as its own call — that read must
happen AFTER edits to show the updated post.

`backend/prompts/pex/starters/audit.py`: render the prose as a `<post_content>` block when present
(this is the ADD in 5.3.6):

```python
def build(flow, resolved:dict, user_text:str) -> str:
    prose = (resolved.get('post_prose') or '').strip()
    block = f'<post_content>\n{prose}\n</post_content>\n\n' if prose else ''
    return block + f'<resolved_details>\n{_format_parameters(flow, resolved)}\n</resolved_details>'
```

`audit.md` step 1a: replace "It takes PROSE, not an id: `read_section` the sections first and pass their
combined text." with: "It takes PROSE, not an id: the full post prose is preloaded in the
`<post_content>` block — pass that text to `editor_review`. Do NOT `read_section` every section; only
`read_section` a specific section immediately before you `revise_content` it, once each, no re-reads."
Also in step 2 ("For each section that drifted, `read_section` it (if not already read)…"), keep the
"(if not already read)" clause — it already forbids re-reads; leave it.

### 5.3.7.2 Compose no-re-read (approved point 5a, "same treatment … if its policy allows")

`compose.md` needs one `read_section` per in-scope section (the preview carries only the first
lines; conversion needs the full bullets), so the fix here is the no-re-read rule, not a prose preload.
The compose policy (`draft.py:209`) already passes `include_preview=True`; leave it. In `compose.md`
Tools, change the `read_section` line to add: "Read each in-scope section at most once; never re-read a
section you have already converted."

### 5.3.7.3 write.md image sentence (the ADD in 5.3.6)

`write.py`'s image branch tool_sequence ("assess the image vs the section's main idea, propose a
replacement") is not stated in write.md. Add one sentence to write.md Process step 3 (or the Tools
section): "When an `image` parameter is present, judge whether the image fits the section's main idea
and replace or drop it via `revise_content` / `remove_content`." (style_notes priority is already
covered by step 3's "treat it as the priority signal".)

### 5.3.7.4 outline.md forbidden-tools sentence (the ADD in 5.3.6)

`outline.py`'s propose-mode tool_sequence forbids `read_metadata`, `generate_outline`, `inspect_post`,
`write_text`. outline.md propose mode only forbids `generate_outline`. In outline.md "Propose mode" step
3 (currently "Do not call `generate_outline`. End the turn…"), extend to: "Call NO tools in propose mode
except an optional single `find_posts`; specifically do not call `read_metadata`, `generate_outline`,
`inspect_post`, or `write_text`. End the turn by returning the text you just wrote."

### 5.3.7.5 Trim "### Tools" to judgment-only (approved point 5b)

Across the 16 flow files, in the `## Tools` → `### Task-specific tools` lists, drop lines that only
restate the `tools.yaml` description (plain signature + what the tool does). Keep lines that carry flow
judgment (when to call it, ordering, "once per turn", "fallback only", "the policy already did this").
This is a light trim, per file, of redundant restatement — not a rewrite. Where a bullet is purely a
signature echo (e.g. summarize.md "`read_metadata(post_id)` — fallback when `<resolved_details>` is
missing data" carries judgment → keep; a bullet that only echoes the yaml sentence → cut). Builders
apply the same test per line; when unsure, keep the line (a kept redundant line is harmless; the test
`test_few_shot_tools_are_allowlisted` still guards tool names).

---

## 5.3.8 Tests — retire / keep / repurpose

All in `utils/evaluation_suite/_tests/pex_unit_tests.py`, drift-catcher block 1636–1723.

- `test_skill_tools_match_flow` (1669–1684): RETIRE. It only existed to keep the frontmatter `tools:`
  list in sync with `flow.tools`; the frontmatter list is deleted, so the test has nothing to compare.
  Delete the function.
- `_PEX_AGENT_SKILLS` (1651): DELETE — its only use was inside the retired test. (`plan` is now excluded
  simply by living in `pex/skills/`, which `_flow_files()` no longer globs.)
- `_SKILL_DIR` (1649): rename to `_FLOW_DIR` and point at `…/backend/prompts/pex/flows`. `_flow_files()`
  (rename of `_skill_files`, 1656) then returns exactly the 16 flow stems.
- `test_few_shot_tools_are_allowlisted` (1687–1698): KEEP. It reads `flow_classes[skill]().tools` (flow
  class) and the file body — no frontmatter dependency. Update: `load_skill_template` → `load_flow_prompt`
  (1695); the loop var `skill` may stay named or be renamed to `flow` (cosmetic).
- `test_flow_tools_are_registered` (1701–1706): KEEP unchanged (pure flow class + tools.yaml).
- `test_loader_strips_frontmatter` (1709–1711): REPURPOSE to `test_loader_reads_flow_prompt`:
  `body = PromptEngineer.load_flow_prompt('outline'); assert body and not body.startswith('---') and
  '## Process' in body`. (Frontmatter no longer exists, so "strips" is obsolete; this stays a loader
  smoke test.)
- `test_skill_system_ends_with_reminder` (1714–1718): KEEP. Update import (1647) and call to
  `build_flow_system`.
- `test_reminder_is_agentic` (1721–1723): KEEP unchanged.
- `_COMPONENT_TOOLS` (1652): KEEP (used by `test_few_shot_tools_are_allowlisted`). `_yaml_tools` /
  `_few_shot_tool_calls` KEEP.
- `test_call_cap_read_from_config` (546–558): update `engineer.tool_call(...)` → `flow_execute` (556,
  557).
- `test_skill_call_honors_model_tier` (560–568): update `engineer.skill_call(...)` → `flow_reply` (566,
  567); the test name may stay or become `test_flow_reply_honors_model_tier` (cosmetic).

No test inspects raw starter `<task>` output or `<resolved_details>` text (grep-confirmed), so the
starter shrink needs no test edits beyond the above.

---

## 5.3.9 Pseudo-code summary of changed methods

`PromptEngineer.flow_reply` (was skill_call) — body identical, renamed calls:

```python
def flow_reply(self, flow, convo_history, scratchpad, skill_name=None, flow_prompt=None,
               resolved=None, max_tokens=1024, user_text=None, model='med') -> str:
    if flow_prompt is None:
        flow_prompt = self.load_flow_prompt(skill_name or flow.name())
    system = build_flow_system(build_system(self.persona), flow, flow_prompt)
    messages = list(build_flow_messages(flow, convo_history, user_text, resolved))
    ...  # provider match unchanged
```

(Optionally rename the `skill_name`/`skill_prompt` params to `flow_name`/`flow_prompt`; if renamed,
update research.py:73's `skill_prompt=` keyword to `flow_prompt=`. Keeping the old param names also
works — pick one and apply consistently. Recommended: rename to `flow_prompt`, keep `skill_name` since
callers never pass it.)

`PromptEngineer.flow_execute` (was tool_call) — same rename pattern; signature otherwise unchanged.

`load_flow_prompt` / `load_skill` — see 5.3.3.

`for_pex._default_starter` — see 5.3.5.4. `build_flow_system` — see 5.3.5.2.

`audit_policy` — see 5.3.7.1.

---

## 5.3.10 Acceptance criteria

1. `pex/skills/` contains only `plan.md`; `pex/flows/` contains the 16 flow prompts; none has a `---`
   frontmatter block; `plan.md` unchanged.
2. No symbol named `skill_call`, `tool_call` (as a PromptEngineer method), `build_skill_system`,
   `build_skill_messages`, `load_skill_template`, `load_skill_meta`, `_split_frontmatter`,
   `_resolve_skill_path`, or `_SKILL_DIRS` remains. `grep -rn` for each returns nothing in `backend/`
   and `for_orchestrator.py`. (`_openai_streaming_tool_call` and the `tool_calls` locals inside the
   provider loops are unrelated and stay.)
3. Every starter `build()` returns only content blocks + `<resolved_details>` — no `<task>` substring
   appears in any `starters/*.py` or in `for_pex._default_starter`.
4. The free suite runs green with ZERO skips from the `assistants/Hugo` cwd:
   `python -m pytest utils/evaluation_suite/_tests/pex_unit_tests.py
   utils/evaluation_suite/_tests/nlu_unit_tests.py utils/evaluation_suite/_tests/mem_unit_tests.py
   utils/evaluation_suite/_tests/model_unit_tests.py` (match the suite's existing invocation / cwd +
   sys.path[0] per the test-cwd note). No live evals — the orchestrator runs the 8-scenario gate after
   ship.
5. Prompt-composition content is preserved except the deliberately removed duplication. Verify by eye
   (5.3.10.1).

### 5.3.10.1 Composition diff check (both builders run this before reporting done)

Render the composed system + user message for `audit`, `outline`, and `write` before and after, and
diff by eye:

```python
from backend.components.prompt_engineer import PromptEngineer
from backend.prompts.for_pex import build_flow_system, build_flow_messages
from backend.prompts.general import build_system
from <flow_classes import path> import flow_classes  # as the tests import it
for name in ('audit', 'outline', 'write'):
    flow = flow_classes[name]()
    fp = PromptEngineer.load_flow_prompt(name)
    print(build_flow_system(build_system({}), flow, fp))
    print(build_flow_messages(flow, 'U: hi', 'hi', {'post_title': 'X', 'post_prose': '## A\nbody'}))
```

Expected differences vs `1615be4`: the `<task>` prose is gone from the user message; the same task/tool
guidance is present in the system prompt's flow-instruction section; the divider reads "Flow
Instructions"; audit's user message carries a `<post_content>` prose block. No other content should
vanish. If anything else disappears, a starter deletion went too far — restore it.

---

## 5.3.11 Open-question resolutions (one paragraph each)

- **(a) Directory + naming.** Flow prompts → `backend/prompts/pex/flows/`; the loader is
  `load_flow_prompt`. This mirrors the existing `pex/starters/` sibling and reads as "the flow's
  instruction prompt". `pex/skills/` is kept for the single real agent skill (`plan.md`), loaded by
  `load_skill`. Two directories = two concepts; no exclusion list needed since `pex/flows/` globs to
  exactly the flows.
- **(b) Method names.** `skill_call → flow_reply` (sub-agent turn with no tools, returns the spoken
  string) and `tool_call → flow_execute` (sub-agent turn that runs the tool loop, returns
  `(text, tool_log)`). "flow_" names both as flow sub-agent invocations, distinct from the intent/NLU
  `__call__(task=…)` path. `build_skill_system/messages → build_flow_system/messages`. These say what
  they are without inventing a new noun.
- **(c) Where plan.md lives.** It stays in `pex/skills/` because it is a real agent-level skill (the
  orchestrator, not a flow sub-agent, loads it, and it is guidance the orchestrator applies itself). It
  is not a flow prompt, so it must not sit in `pex/flows/`.
- **(d) Starter API.** Signature stays `build(flow, resolved, user_text)` — unchanged so `_render_starter`
  needs no edit, and `user_text` remains available for any starter that wants it later. What changes is
  the body: it no longer emits `<task>`/tool-order prose, only runtime parameters + preloaded content.
  Simplifying the signature further (dropping `user_text`) is not worth touching every module for zero
  gain.
- **(e) Compose preload.** No — compose keeps its per-section `read_section` because the preview holds
  only the first lines and conversion needs the full bullets. Its fix is the no-re-read rule only. Audit
  is different: `editor_review` wants the whole post prose at once, so preloading it via `extra_resolved`
  removes a real case of N repeated read actions.
- **(f) Retired drift tests.** Exactly one is retired: `test_skill_tools_match_flow` (it only synced the
  frontmatter `tools:` list with `flow.tools`, and that list is deleted). Its sibling helper
  `_PEX_AGENT_SKILLS` goes with it. `load_skill_meta` and `_split_frontmatter` are deleted because that
  test was their only caller. `test_loader_strips_frontmatter` is repurposed (not retired) into a loader
  smoke test. Everything else in the drift block is kept and only re-pointed at `pex/flows/` /
  `load_flow_prompt` / `build_flow_system`.

---

## 5.3.12 Out of scope / notes

- `AMBIGUITY_AND_ERRORS` (for_pex.py) and the intent prompts (`sys_prompts.py`) are untouched (kept per
  the approved direction). Each flow file keeps its own `## Handling Ambiguity and Errors` section — the
  duplication between that section and the shared block predates this round and is not in scope.
- `_TASK_SUFFIXES['skill']` / `['clarify']` and `_get_temperature(task='skill')` are the `__call__` task
  labels, not the flow sub-agent — left as-is.
- The body prose of the 16 files still says "This flow / this skill …" in places; not swept (5.3.2).
- `write.md`, `cite.md`, `compare.md`, `summarize.md`, `refine.md` few-shot exemplars are kept intact
  (round 4.3 content, per the approved direction).
- If the final diff ADDS more than it removes, something went wrong — the expected shape is net
  deletion (one test, three loader helpers, 16 frontmatter blocks, 13 `<task>` blocks) against four
  one-line prompt additions and one `extra_resolved` line.
