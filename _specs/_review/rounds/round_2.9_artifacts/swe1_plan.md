# Round 5.3 — SWE1 Implementation Plan (Flow Prompt Consolidation)

Verified against live source at tip `1615be4`. All paths relative to `assistants/Hugo/`.
Every spec line reference below was re-read at the tip and confirmed unless noted under "Spec gaps".

This plan covers the WHOLE change (spec 5.3.1–5.3.8). If the orchestrator splits work with SWE2,
sections are independent enough to hand off by numbered step; apply order is stated at the end.

---

## Spec gaps found while verifying (implement anyway, flagged)

1. **conftest.py:76 monkeypatch missed by the "exhaustive" sweep (5.3.4).**
   `utils/evaluation_suite/_tests/conftest.py:76` does `a.engineer.tool_call = _stub_tool_call`.
   This is a real call site the spec's grep list omits. If not renamed to `flow_execute`, the
   `mock_agent` fixture stubs a method that no longer exists → every test using `mock_agent` calls
   the live tool loop. MUST change to `a.engineer.flow_execute = _stub_tool_call`. (The local helper
   `_stub_tool_call` name at line 54 is cosmetic; leave it.)

2. **base.py:15 comment references `engineer.tool_call` as a method.** Acceptance criterion 5.3.10-2
   greps for `tool_call` as a method returning nothing in `backend/`. The comment on line 15
   ("post_tool's body lives in the engineer.tool_call loop") still matches. Update the comment to
   `engineer.flow_execute loop`. (`tool_call_id` at prompt_engineer.py:561 and `_openai_streaming_tool_call`
   are unrelated API/local names, explicitly excluded by the criterion — leave them.)

3. **audit.md few-shot examples 1/3/5 and the Tools line 42 still say "read_section each section
   → editor_review(content=<combined prose>)".** After 5.3.7.1 preloads the prose via
   `<post_content>`, these exemplars contradict the new step 1a. The spec does NOT list them for edit
   and 5.3.7.5 says "when unsure, keep". Leaving them creates a mild internal contradiction in
   audit.md. Flagged; NOT edited (staying inside the spec's named edits).

---

## Decision: keep method PARAMETER names, rename only method NAMES (spec-permitted)

Spec 5.3.9 allows either renaming `skill_prompt`/`skill_name` params to `flow_*` or keeping them
("Keeping the old param names also works — pick one and apply consistently"). I keep `skill_name` /
`skill_prompt` on `flow_reply` and `flow_execute`. Reason: renaming them forces keyword-argument edits
at research.py:73 (`skill_prompt=`) and four test call sites (556/557/566/567, `skill_prompt=''`) for
zero behavior gain. This is the smaller, consistent diff.

Exception, per explicit spec instruction 5.3.5.2: I DO rename `build_flow_system`'s parameter
`skill_prompt` → `flow_prompt`. Both callers pass it positionally, so this costs zero caller churn.

---

## Step 1 — Directory + file moves (5.3.1)

`git mv` these 16 files from `backend/prompts/pex/skills/` to `backend/prompts/pex/flows/` (git creates
the target dir):

`audit brainstorm browse chat cite compare compose find outline propose refine release rework schedule
summarize write` (`.md`).

Leave `plan.md` in `pex/skills/`. After the move: `pex/skills/` = `plan.md` only; `pex/flows/` = the 16.

Sixteen separate `git mv` calls (no shell chaining per repo rules), or one `git mv ... <dir>` per file.

---

## Step 2 — Frontmatter removal, all 16 flow files (5.3.2)

Delete the leading `---` … `---` YAML block AND the blank line after it, so each file starts at its
first body line. Confirmed closing-`---` line / first-body line per file:

| file | delete lines 1– | body starts |
|---|---|---|
| audit | 12 | "This skill audits…" |
| brainstorm | 10 | "This skill produces…" |
| browse | 9 | "This skill narrates a browse…" |
| chat | 5 | "This skill is the chat…" |
| cite | 10 | "This skill attaches a citation…" |
| compare | 10 | "This skill narrates a side-by-side…" |
| compose | 11 | "This skill describes how to convert…" |
| find | 7 | "This skill narrates a find…" |
| outline | 12 | "This skill describes how to generate…" |
| propose | 9 | "This skill fills a placeholder gap…" |
| refine | (close `---`) | "This skill…" |
| release | 9 | "This skill publishes a post…" |
| rework | 11 | "This skill describes how to rework…" |
| schedule | 10 | "This skill schedules a post…" |
| summarize | 9 | "This skill produces a standalone…" |
| write | 10 | "This skill edits a paragraph…" |

Do it with `Edit` per file: `old_string` = the whole `---\n…\n---\n\n` block through the blank line,
`new_string` = ''. Do NOT touch body "This skill …" prose (5.3.2 forbids the prose sweep).
`plan.md` has no frontmatter — untouched.

---

## Step 3 — Four content edits inside flow `.md` files (5.3.7.1–.4)

### 3a. audit.md step 1a (line 19)
Replace the substring
`It takes PROSE, not an id: \`read_section\` the sections first and pass their combined text.`
with
`It takes PROSE, not an id: the full post prose is preloaded in the \`<post_content>\` block — pass that text to \`editor_review\`. Do NOT \`read_section\` every section; only \`read_section\` a specific section immediately before you \`revise_content\` it, once each, no re-reads.`
Leave step 2's "(if not already read)" clause as-is.

### 3b. compose.md Tools line 94
Append to `- \`read_section(post_id, sec_id)\` — required before composing any section. Never write
without reading.`:
` Read each in-scope section at most once; never re-read a section you have already converted.`

### 3c. outline.md Propose mode step 3 (line 24)
Replace `Do not call \`generate_outline\`. End the turn by returning the text you just wrote.` with
`Call NO tools in propose mode except an optional single \`find_posts\`; specifically do not call \`read_metadata\`, \`generate_outline\`, \`inspect_post\`, or \`write_text\`. End the turn by returning the text you just wrote.`

### 3d. write.md Process step 3 — add image bullet after line 28
After the `- When a style hint or \`suggestions\` slot…priority signal…` bullet, add:
`   - When an \`image\` parameter is present, judge whether the image fits the section's main idea and replace or drop it via \`revise_content\` / \`remove_content\`.`

### 3e. Tools trim (5.3.7.5) — minimal, near-zero
Per 5.3.7.5 the test is "when unsure, keep" and a kept redundant line is harmless. To avoid slop
(orders rule 2) I will trim ONLY lines that are a pure signature echo with no judgment, and only where
obvious. Expected outcome: a handful of lines at most, possibly zero. `test_few_shot_tools_are_allowlisted`
still guards tool names, so no risk. I lean toward keeping. (Flagged as low-value / high-slop-risk.)

---

## Step 4 — `backend/components/prompt_engineer.py` (5.3.3, 5.3.4, 5.3.9)

**Line 16 import:**
before `from backend.prompts.for_pex import build_skill_system, build_skill_messages`
after  `from backend.prompts.for_pex import build_flow_system, build_flow_messages`

**Lines 70–73 (`_SKILL_DIRS`)** replace with:
```python
    _FLOW_DIR  = Path(__file__).resolve().parents[1] / 'prompts' / 'pex' / 'flows'
    _SKILL_DIR = Path(__file__).resolve().parents[1] / 'prompts' / 'pex' / 'skills'
```

**Line 181 `skill_call` → `flow_reply`** (keep params). Body:
- 184 docstring: `"Sub-agent turn WITHOUT tool use. Sibling of flow_execute."`
- 186 `self.load_skill_template(...)` → `self.load_flow_prompt(...)`
- 188 `build_skill_system(...)` → `build_flow_system(...)`
- 189 `build_skill_messages(...)` → `build_flow_messages(...)`

**Line 199 `tool_call` → `flow_execute`** (keep params). Body:
- 203 docstring: `"Sub-agent turn WITH tool use. Sibling of flow_reply."`; 205 "for skills" →
  "for flows" (single word, in the same docstring — allowed, it names the renamed method's siblings).
- 209 `load_skill_template` → `load_flow_prompt`
- 211 `build_skill_system` → `build_flow_system`
- 212 `build_skill_messages` → `build_flow_messages`

**Delete lines 686–719** (`_resolve_skill_path`, `load_skill_template`, `load_skill_meta`,
`_split_frontmatter`) and add the two loaders in their place:
```python
    @classmethod
    def load_flow_prompt(cls, flow_name:str) -> str:
        """Full markdown instruction prompt for a flow sub-agent (pex/flows/<flow>.md)."""
        return (cls._FLOW_DIR / f'{flow_name}.md').read_text(encoding='utf-8')

    @classmethod
    def load_skill(cls, skill_name:str) -> str:
        """An agent-level skill body (pex/skills/<skill>.md) — currently only the Workflow Planner."""
        return (cls._SKILL_DIR / f'{skill_name}.md').read_text(encoding='utf-8')
```
No `None` return, no `or ''` guard (contract: file always exists; missing → `FileNotFoundError` loud).
`yaml` import (line 12) becomes unused after `_split_frontmatter` deletion → remove the `import yaml`
line (orphan cleanup of my own change). Verify no other `yaml.` use in the file first (grep: only
`_split_frontmatter` used it).

Leave `_TASK_SUFFIXES['skill']` (26), `['clarify']` (36), `_get_temperature(task='skill')`,
and the `'  skill tool=%s'` log labels (244, 486, 557) — out of scope (5.3.4 note, 5.3.12).

---

## Step 5 — `backend/prompts/for_pex.py` (5.3.5)

**Module docstring (1–17):** rewrite to describe system = persona + intent prompt + ambiguity block +
flow prompt (`pex/flows/<flow>.md`) + closing reminder; user message = filled starter (runtime
parameters + preloaded content) + recent conversation. Replace "Skill prompt assembly" / "skill body" /
"skill file" / "Slot-rendering helpers…starter modules". No banned words.

**`build_skill_system` → `build_flow_system` (51–65):**
- rename function; rename param `skill_prompt` → `flow_prompt`; docstring: "persona + intent prompt +
  ambiguity block + flow prompt + closing reminder"; drop "Skill Instructions" wording from docstring.
- line 61 `if skill_prompt:` → `if flow_prompt:`
- line 63:
  `parts.append(f'\n\n--- {flow_name} Flow Instructions ---\n\n{flow_prompt}')`
- line 62 `flow_name = flow.name().capitalize()` unchanged.
- `AMBIGUITY_AND_ERRORS` (24–48) untouched (5.3.12).

**`build_skill_messages` → `build_flow_messages` (68–84):**
- rename function; docstring line "The starter owns task framing, preloaded content, and resolved
  details." → "The starter renders runtime parameters and any preloaded content; task framing now
  lives in the flow prompt." No other logic change.

**`_default_starter` (95–125):** drop the `<task>` synthesis:
```python
def _default_starter(flow, resolved:dict) -> str:
    """Generic renderer for flows without a custom starter module. Emits only <resolved_details>;
    task framing lives in the flow prompt."""
    details_lines = []
    for slot_name, slot in flow.slots.items():
        if not slot.check_if_filled():
            continue
        label = slot_name.replace('_', ' ').capitalize()
        if slot_name == flow.entity_slot and slot.criteria == 'multiple':
            val = slot.values[0] if slot.values else ''
            details_lines.append(f'{label}: {_summarize_entity(val)}')
        elif slot.criteria == 'multiple':
            if slot.values:
                details_lines.append(f'{label}: ' + '; '.join(str(v) for v in slot.values))
        else:
            details_lines.append(f'{label}: {slot.to_dict()}')
    details = '\n'.join(details_lines) if details_lines else '(no parameters filled)'
    return f'<resolved_details>\n{details}\n</resolved_details>'
```
Delete the `post_title`/`title_clause`/`task` lines (101–107) and the `<task>` wrapper in the return
(122–124). `_render_starter` (87–92) and `_summarize_entity` (128–131) unchanged. The call
`_render_starter` still passes `_default_starter(flow, resolved)` — signature kept.

---

## Step 6 — Per-flow starters, delete `<task>` (5.3.6) + audit ADD (5.3.7.1)

Rule per starter: delete the `<task>…</task>` block from every TEMPLATE and delete the `build()` logic
that computed `tool_sequence`/`verb`/`end_condition`/`_DIFF_CLAUSE`. Keep content blocks
(`<post_content>`/`<post_preview>`/`<line_content>`), keep `<resolved_details>`, keep `_format_parameters`
and render helpers. Signature stays `build(flow, resolved, user_text)`.

Per-file:

- **audit.py** — special (ADD). New TEMPLATE loses `<task>`; build renders a `<post_content>` block from
  `resolved['post_prose']` when present:
  ```python
  def build(flow, resolved:dict, user_text:str) -> str:
      prose = (resolved.get('post_prose') or '').strip()
      block = f'<post_content>\n{prose}\n</post_content>\n\n' if prose else ''
      return block + f'<resolved_details>\n{_format_parameters(flow, resolved)}\n</resolved_details>'
  ```
  Delete `TEMPLATE`, the `tool_sequence` construction, and the `render_source, render_checklist` import
  line ONLY if `_format_parameters` no longer needs them — it DOES (`render_source`, `render_checklist`
  used at lines 34/45) → keep the import. Verified: import stays.
- **brainstorm.py** — delete `<task>` + verb/tool_sequence/end_condition (9–45); build returns
  `f'<resolved_details>\n{_format_parameters(flow)}\n</resolved_details>'`. Keep `_snippet_text`? It is
  used only by the deleted branch logic. After removing the topic/snippet branching, `_snippet_text`
  becomes an orphan created by my change → delete it (and its only caller gone). `render_source` import
  still used by `_format_parameters` → keep.
- **browse.py** — delete `<task>` (10–16); build returns `<resolved_details>` only via
  `_format_parameters(flow, resolved)`.
- **cite.py** — delete `<task>` + tool_sequence/end_condition from both templates. Keep the
  snippet-vs-none branch: WITH-snippet returns `<line_content>` + `<resolved_details>`; NO-snippet
  returns `<resolved_details>` only. `_snippet_text` still used → keep.
- **compare.py** — delete `<task>` + `_DIFF_CLAUSE`. WITH-previews returns `<post_content>` +
  `<resolved_details>`; NO-previews returns `<resolved_details>` only. `_post_label`/`_post_preview`
  still used by the previews block → keep.
- **compose.py** — delete `<task>` (11–21). Post-change build (spec 5.3.6 example):
  ```python
  def build(flow, resolved:dict, user_text:str) -> str:
      section_previews = render_section_preview(resolved.get('section_preview') or {})
      if not section_previews:
          section_previews = '(section previews not preloaded — read_metadata include_preview=True first)'
      return (f'<post_content>\n{section_previews}\n</post_content>\n\n'
              f'<resolved_details>\n{_format_parameters(flow)}\n</resolved_details>')
  ```
- **outline.py** — delete `<task>` + tool_sequence/end_condition (13–45). build returns
  `<resolved_details>` only. `_topic_text` was used only to fill the deleted `<task>` `{topic}` →
  orphan by my change → delete it. `render_freetext` import: used by `_format_parameters`? No —
  `_format_parameters` uses `render_checklist` only. `render_freetext` was unused already (pre-existing);
  I will NOT remove it (not my orphan — pre-existing dead import; mention, don't delete per CLAUDE.md).
  Actually recheck at apply time: if `render_freetext` is referenced nowhere, it is pre-existing dead —
  leave it and note.
- **refine.py** — delete `<task>` (9–19). build returns `<post_content>` (current_outline) +
  `<resolved_details>`.
- **release.py** — delete `<task>` (7–13). build returns `<resolved_details>` only.
- **rework.py** — delete `<task>` + tool_sequence (12–37). build returns `<post_preview>` +
  `<resolved_details>`. `has_remove`/`tool_sequence` computation deleted.
- **schedule.py** — delete `<task>` (7–13). build returns `<resolved_details>` only.
  `_datetime_label`/`_channel_label` still used by `_format_parameters` → keep.
- **summarize.py** — delete `<task>` from both templates. WITH-outline returns `<post_content>` +
  `<resolved_details>`; NO-outline returns `<resolved_details>` only. `_length_clause` was used only in
  the deleted `<task>` `{length_clause}` → orphan by my change → delete it. Length stays surfaced via
  `_format_parameters` (`Length: …`). Confirm: `_format_parameters` already emits Length, so no data lost.
- **write.py** — delete `<task>` + 3-way tool_sequence (9–33). build returns `<resolved_details>` only.
  `has_style_notes`/`has_image`/`tool_sequence` deleted. `_render_image` still used by
  `_format_parameters` → keep. (The banned word "tighten" lives only inside the deleted else-branch
  tool_sequence — removed by this deletion.)

After each starter edit, prune imports my deletion orphaned (e.g. brainstorm still needs `render_source`;
audit still needs both). Do NOT touch pre-existing unused imports.

---

## Step 7 — `backend/modules/policies/base.py`

- **Line 15 comment:** `engineer.tool_call loop` → `engineer.flow_execute loop` (gap #2).
- **Line 83:** `result = self.engineer.tool_call(` → `self.engineer.flow_execute(`.
  Leave the `llm_execute` docstring "skill" prose (no prose sweep; 5.3.2 spirit).

---

## Step 8 — `backend/modules/policies/research.py`

- **46:** `self.engineer.skill_call(...)` → `self.engineer.flow_reply(...)`.
- **72:** `self.engineer.load_skill_template(flow.name())` → `self.engineer.load_flow_prompt(flow.name())`.
  Local var name `skill_prompt` may stay (kept param name).
- **73:** `self.engineer.skill_call(` → `self.engineer.flow_reply(`. The `skill_prompt=skill_prompt`
  keyword stays valid (param name kept).

---

## Step 9 — `backend/modules/policies/revise.py::audit_policy` (5.3.7.1)

Between line 233 (`self.record_snapshot(...)`) and 234 (`text, tool_log = self.llm_execute(...)`),
preload the pre-edit prose and pass it via `extra_resolved`:
```python
        self.record_snapshot(self.content, flow, context, post_id)
        pre = self._read_post_content(post_id, tools)
        text, tool_log = self.llm_execute(flow, state, context, tools,
            extra_resolved={'post_prose': pre.get('content', '')})
```
Leave line 244's post-edit `self._read_post_content(post_id, tools)` (the card read AFTER edits) alone.
`_read_post_content` returns a dict with `content` key via `read_metadata(include_outline=True)` — verified
signature at base.py:94. `.get('content', '')` is a real fallback (a post with no body yields no content),
so the `.get` here is legitimate, not defensive.

---

## Step 10 — `backend/prompts/for_orchestrator.py:233`

`engineer.load_skill_template("plan")` → `engineer.load_skill("plan")` (plan is an agent skill in
`pex/skills/`, read by the loader that targets `_SKILL_DIR`).

---

## Step 11 — Tests (5.3.8)

`utils/evaluation_suite/_tests/pex_unit_tests.py`:
- **556, 557:** `engineer.tool_call(` → `engineer.flow_execute(` (keep `skill_prompt=''`).
- **566, 567:** `engineer.skill_call(` → `engineer.flow_reply(` (keep `skill_prompt=''`). Test name
  `test_skill_call_honors_model_tier` may stay (cosmetic); I keep it to minimize churn. Docstring 561
  "skill_call routes…" → "flow_reply routes…".
- **1647 import:** `build_skill_system` → `build_flow_system`.
- **1649:** `_SKILL_DIR = … 'pex' / 'skills'` → `_FLOW_DIR = … 'pex' / 'flows'`.
- **1651:** delete `_PEX_AGENT_SKILLS`.
- **1656:** `_skill_files()` → `_flow_files()` (globs `_FLOW_DIR` → the 16 stems).
- **1669–1684:** delete `test_skill_tools_match_flow` entirely.
- **1687–1698 (`test_few_shot_tools_are_allowlisted`):** KEEP. `_skill_files()` → `_flow_files()`;
  1695 `load_skill_template(skill) or ''` → `load_flow_prompt(skill)` (no `or ''` — loader never None);
  loop var `skill` may stay. Drop the now-unused `if skill not in flow_classes: continue` only if every
  `_flow_files()` stem is in `flow_classes` — it is (16 flows all registered), but the guard is harmless;
  KEEP it as-is to stay surgical.
- **1701–1706 (`test_flow_tools_are_registered`):** unchanged.
- **1709–1711 (`test_loader_strips_frontmatter`):** repurpose to `test_loader_reads_flow_prompt`:
  ```python
  def test_loader_reads_flow_prompt():
      body = PromptEngineer.load_flow_prompt('outline')
      assert body and not body.startswith('---') and '## Process' in body
  ```
- **1714–1718 (`test_skill_system_ends_with_reminder`):** KEEP; `build_skill_system(` → `build_flow_system(`
  at 1718. Loop var `skill_prompt` may stay.
- **1721–1723 (`test_reminder_is_agentic`):** unchanged.
- `_COMPONENT_TOOLS` (1652), `_yaml_tools`, `_few_shot_tool_calls`: KEEP.

`utils/evaluation_suite/_tests/conftest.py`:
- **76:** `a.engineer.tool_call = _stub_tool_call` → `a.engineer.flow_execute = _stub_tool_call` (gap #1).

---

## Step 12 — Doc: `utils/helper_ref.md:36`

Rewrite the `_SKILL_DIRS` sentence to name the two new constants and loaders:
`Class constants: \`_FLOW_DIR\` → \`backend/prompts/pex/flows/\` (the 16 flow prompts, read by
\`load_flow_prompt\`) and \`_SKILL_DIR\` → \`backend/prompts/pex/skills/\` (agent skills, e.g. \`plan.md\`,
read by \`load_skill\`).` Leave the rest of the line (`_TASK_SUFFIXES`) unchanged.

---

## Apply order

1. Step 1 (git mv). 2. Step 2 (frontmatter). 3. Step 3 (4 md content edits + minimal Tools trim).
4. Step 4 (prompt_engineer). 5. Step 5 (for_pex). 6. Step 6 (starters). 7. Steps 7–10 (policies +
orchestrator). 8. Step 11 (tests) + Step 12 (doc).

Order rationale: moves and loader before call-site renames so a mid-run grep is meaningful; tests last.

## Verification (5.3.10, run from `assistants/Hugo` cwd with sys.path[0]=that dir)

- `python -m pytest utils/evaluation_suite/_tests/pex_unit_tests.py nlu_unit_tests.py
  mem_unit_tests.py model_unit_tests.py` → green, ZERO skips.
- Grep acceptance (5.3.10-2): no `skill_call`, `tool_call` (method), `build_skill_system`,
  `build_skill_messages`, `load_skill_template`, `load_skill_meta`, `_split_frontmatter`,
  `_resolve_skill_path`, `_SKILL_DIRS` in `backend/` + `for_orchestrator.py`.
- Grep `<task>` in `starters/*.py` and `for_pex._default_starter` → none.
- Composition diff (5.3.10.1): render `audit`, `outline`, `write` system+user before/after; confirm
  `<task>` gone from user msg, same guidance now under "--- {Flow} Flow Instructions ---" in system,
  audit user msg carries `<post_content>`. Nothing else vanishes.
- Net diff must be deletion-heavy (16 frontmatter blocks, 13 `<task>` blocks, 1 test, 4 loader helpers)
  vs 4 one-line md ADDs, 2 loaders, 1 `extra_resolved` line.
