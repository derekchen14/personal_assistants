# SWE2 Implementation Plan — Round 5.3 (Flow Prompt Consolidation)

Verified against live source at `1615be4`. All paths relative to `assistants/Hugo/`.
Every spec line reference was re-read at the tip and confirmed unless noted under "Spec gaps / risks".

Net shape: deletion. Additions = 4 one-line prompt sentences + 1 `extra_resolved` line + 2 thin loader
classmethods (replacing 5 deleted members).

---

## Apply order (do in this sequence so each step's tests can run)

1. Directory + file moves (`git mv`), frontmatter strip.
2. `prompt_engineer.py` loader + method renames.
3. `for_pex.py` builder renames + `_default_starter` shrink.
4. Call-site sweep: `base.py`, `research.py`, `for_orchestrator.py`, `conftest.py`.
5. Per-flow starter shrink (13 files).
6. Content fixes in the 4 `.md` files + `revise.py` audit preload.
7. Test edits in `pex_unit_tests.py`.
8. Doc update `helper_ref.md`.
9. Verify: run the free suite (5.3.10 criterion 4) + composition eyeball (5.3.10.1).

---

## 1. Directory + file moves (5.3.1, 5.3.2)

- `mkdir backend/prompts/pex/flows/` (git tracks via the moved files).
- `git mv backend/prompts/pex/skills/<f>.md backend/prompts/pex/flows/<f>.md` for the 16 flow files:
  audit, brainstorm, browse, chat, cite, compare, compose, find, outline, propose, refine, release,
  rework, schedule, summarize, write. Leave `plan.md` in `pex/skills/`.
- Frontmatter strip: each moved file currently opens with a `---` … `---` YAML block
  (audit.md lines 1-12, compose.md 1-11, outline.md 1-12 incl. `stages:`, write.md 1-10, etc.).
  Delete the block plus the single blank line after the closing `---` so the file starts at its first
  body line. Do NOT touch body prose ("This skill …" stays — 5.3.2).
- `chat.md`, `find.md`, `propose.md`, `browse.md` etc. — same strip. Confirm none has a body line that
  begins with `---` (none does; the only `---` is the frontmatter fence).

Verify: `grep -rl '^---$' backend/prompts/pex/flows/` returns nothing; `ls pex/skills/` = `plan.md` only;
`ls pex/flows/` = 16 files.

---

## 2. `backend/components/prompt_engineer.py`

### 2a. Import (line 16)
Before: `from backend.prompts.for_pex import build_skill_system, build_skill_messages`
After:  `from backend.prompts.for_pex import build_flow_system, build_flow_messages`

### 2b. Class dir constants (replace lines 70-73)
Delete `_SKILL_DIRS` tuple. Add:
```python
    _FLOW_DIR  = Path(__file__).resolve().parents[1] / 'prompts' / 'pex' / 'flows'
    _SKILL_DIR = Path(__file__).resolve().parents[1] / 'prompts' / 'pex' / 'skills'
```
(`parents[1]` of this file = `backend/`, confirmed.)

### 2c. `skill_call` → `flow_reply` (def line 181, body 184-197)
Rename method. Rename param `skill_prompt` → `flow_prompt`; keep `skill_name` (no caller passes it).
Body edits: line 186 `self.load_skill_template(...)` → `self.load_flow_prompt(...)`;
line 188 `build_skill_system(...)` → `build_flow_system(...)`;
line 189 `build_skill_messages(...)` → `build_flow_messages(...)`.
Docstring line 184 "Skill execution WITHOUT tool use. Sibling of tool_call." →
"Flow sub-agent turn WITHOUT tool use. Sibling of flow_execute."

### 2d. `tool_call` → `flow_execute` (def line 199, body 203-224)
Rename method + param `skill_prompt` → `flow_prompt` (keep `skill_name`). Body: line 209
`load_skill_template` → `load_flow_prompt`; 211 `build_skill_system` → `build_flow_system`;
212 `build_skill_messages` → `build_flow_messages`. Docstring 203 "Skill execution WITH tool use.
Sibling of skill_call." → "Flow sub-agent turn WITH tool use. Sibling of flow_reply." Leave the
`Pass model='high' … Pass schema=…` paragraph; swap the word "skills" → "flows" only where it names the
sub-agent (light, 203-207). Signature otherwise unchanged (5.3.4).
Note: the two internal tool-loop log lines (`'  skill tool=%s'`, 244/486/557) are cosmetic log strings —
leave them; out of scope and low value.

### 2e. Delete loader helpers (lines 686-719)
Delete `_resolve_skill_path` (686-692), `load_skill_template` (694-700), `load_skill_meta` (702-708),
`_split_frontmatter` (710-719). Replace with the two classmethods from 5.3.3:
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
Contract: `load_flow_prompt` returns a real str, never None; missing file raises FileNotFoundError
(desired loud failure). Remove all `or ''` / `is None` guards that only tolerated the old None return
(the affected call sites are research.py:72/1695 and test 1710 — handled below).

### 2f. `yaml` import
`import yaml` (line 12) was used only by `_split_frontmatter`. After deleting that helper, grep the file:
if no other `yaml.` reference remains, remove the import (orphan from my change). Confirm before deleting.
(`_to_json_schema`, provider methods do not use yaml — expected orphan, remove line 12.)

---

## 3. `backend/prompts/for_pex.py`

### 3a. Module docstring (1-17)
Rewrite to describe: system = persona + intent prompt + ambiguity block + flow prompt
(`pex/flows/<flow>.md`) + closing reminder; user message = filled starter (runtime parameters +
preloaded content) + recent conversation. Replace "skill body" / "skill file" / "Slot-rendering
helpers … skill" wording with "flow prompt" / "starter render helpers". No banned words (avoid
"seam", "steward", etc.).

### 3b. `build_skill_system` → `build_flow_system` (51-65)
Rename function and param `skill_prompt` → `flow_prompt` (both call sites in prompt_engineer.py pass
positionally, so no keyword update needed there). Only behavior change = divider text (line 63):
Before: `parts.append(f'\n\n--- {flow_name} Skill Instructions ---\n\n{skill_prompt}')`
After:  `parts.append(f'\n\n--- {flow_name} Flow Instructions ---\n\n{flow_prompt}')`
Also update the `if skill_prompt:` guard (61) → `if flow_prompt:` and docstring (52-56) "skill body" →
"flow prompt", "Skill Instructions" → "Flow Instructions". Keep `AMBIGUITY_AND_ERRORS` and
`flow.name().capitalize()`.

### 3c. `build_skill_messages` → `build_flow_messages` (68-84)
Rename function. Docstring line 72-73 "The starter owns task framing, preloaded content, and resolved
details." → "The starter renders runtime parameters and any preloaded content; task framing now lives
in the flow prompt." Update docstring header "skill body" → "flow prompt". No logic change.

### 3d. `_render_starter` (87-92)
Unchanged (still `import_module('...starters.'+flow.name())`, ImportError → `_default_starter`).

### 3e. `_default_starter` (95-125) — drop synthesized task
Delete `post_title`/`title_clause`/`task` (lines 101-107) and the `<task>` wrapper (122-124). Keep the
slot loop (108-120) and `_summarize_entity`. New body:
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
Note: `resolved` param stays in the signature (unused now) — `_render_starter` calls it positionally.

---

## 4. Call-site sweep

- `backend/modules/policies/base.py:83`: `self.engineer.tool_call(` → `self.engineer.flow_execute(`.
  Also line 15 comment "the engineer.tool_call loop (integration point)" → "the engineer.flow_execute
  loop" (accuracy; a comment naming a renamed symbol). Low-risk one-word edit.
- `backend/modules/policies/research.py`:
  - 46: `self.engineer.skill_call(flow, history_with_data, self.scratchpad.read())` → `.flow_reply(`.
  - 72: `skill_prompt = self.engineer.load_skill_template(flow.name()) + length_hint` →
    rename local to `flow_prompt = self.engineer.load_flow_prompt(flow.name()) + length_hint`.
    (`load_flow_prompt` now returns str, so `+ length_hint` is safe — the old `| None` return that
    could break `+` is gone.)
  - 73-76: `self.engineer.skill_call(flow, history_with_data, self.scratchpad.read(),
    skill_prompt=skill_prompt)` → `.flow_reply(..., flow_prompt=flow_prompt)`.
- `backend/prompts/for_orchestrator.py:233`: `engineer.load_skill_template("plan")` →
  `engineer.load_skill("plan")` (plan is an agent skill in pex/skills/).
- `utils/evaluation_suite/_tests/conftest.py:76` (SPEC GAP — see risks): `a.engineer.tool_call =
  _stub_tool_call` → `a.engineer.flow_execute = _stub_tool_call`. Without this the `mock_agent`
  fixture's stub no longer intercepts the renamed method and any mock_agent test that drives a tool
  loop hits a real provider. The helper name `_stub_tool_call` (54) is cosmetic; leave it.

---

## 5. Per-flow starter shrink (5.3.6) — 13 files in `backend/prompts/pex/starters/`

Rule per file: delete the `<task>…</task>` block from every TEMPLATE and delete the `build()` logic
that computed `tool_sequence`/`verb`/`end_condition`. Keep every content block (`<post_content>`,
`<post_preview>`, `<line_content>`) and `<resolved_details>`. Keep `_format_parameters` and render
helpers. Signature stays `build(flow, resolved, user_text)`.

| File | Delete | build() returns | Keep |
|---|---|---|---|
| audit.py | TEMPLATE `<task>` (9-15), `tool_sequence` in build (18-27) | `<post_content>` (new, 5.3.7.1) + `<resolved_details>` | `_format_parameters(flow, resolved)` |
| brainstorm.py | TEMPLATE `<task>` (10-16), verb/tool_sequence/end_condition branches (18-40) | `<resolved_details>` only | `_snippet_text`, `_format_parameters` |
| browse.py | TEMPLATE `<task>` (10-16) | `<resolved_details>` only | `_format_parameters(flow, resolved)` |
| cite.py | `<task>` in both templates (12-15, 24-27), tool_sequence/end_condition (34-56) | `<line_content>` (when snippet) + `<resolved_details>` | keep two-template split for content block; `_snippet_text`, `_format_parameters` |
| compare.py | `<task>` in both templates + `_DIFF_CLAUSE` (7, 9-16, 19-25) | `<post_content>` (when previews) + `<resolved_details>` | keep both templates for previews; `_post_label`, `_post_preview`, `_format_parameters` |
| compose.py | TEMPLATE `<task>` (11-13) | `<post_content>` + `<resolved_details>` | `_format_parameters` |
| outline.py | TEMPLATE `<task>` (13-15), tool_sequence/end_condition branches (23-42) | `<resolved_details>` only | `_topic_text`, `_format_parameters` |
| refine.py | TEMPLATE `<task>` (9-11) | `<post_content>` + `<resolved_details>` | `_format_parameters` |
| release.py | TEMPLATE `<task>` (7-9) | `<resolved_details>` only | `_format_parameters(flow, resolved)` |
| rework.py | TEMPLATE `<task>` (12-14), tool_sequence branches (26-31 partial) | `<post_preview>` + `<resolved_details>` | `_format_parameters` |
| schedule.py | TEMPLATE `<task>` (7-9) | `<resolved_details>` only | `_datetime_label`, `_channel_label`, `_format_parameters` |
| summarize.py | `<task>` in both templates (7-9, 17-19) | `<post_content>` (when outline) + `<resolved_details>` | keep both templates for outline block; `_length_clause`, `_format_parameters` |
| write.py | TEMPLATE `<task>` (9-11), 3-way tool_sequence (18-28) | `<resolved_details>` only | `_format_parameters`, `_render_image` |

Concrete rewrites for the tricky ones:

**compose.py::build** (drop `<task>`, keep the preview fallback wording as-is — surgical):
```python
def build(flow, resolved:dict, user_text:str) -> str:
    section_previews = render_section_preview(resolved.get('section_preview') or {})
    if not section_previews:
        section_previews = '(section previews not preloaded — call read_metadata with include_preview=True before composing)'
    return (f'<post_content>\n{section_previews}\n</post_content>\n\n'
            f'<resolved_details>\n{_format_parameters(flow)}\n</resolved_details>')
```

**brainstorm.py::build** collapses to:
```python
def build(flow, resolved:dict, user_text:str) -> str:
    return f'<resolved_details>\n{_format_parameters(flow)}\n</resolved_details>'
```
Delete `topic`/`source`/`snippet`/`seeded`/verb/tool_sequence/end_condition locals (they only fed the
`<task>`). `_snippet_text` becomes unused → delete it (orphan created by my change). Confirm no other
reference before deleting.

**outline.py::build** collapses to `<resolved_details>` only; delete `sections_filled`/`propose_mode`/
`topic`/`depth` locals and both branches; `_topic_text` becomes unused → delete it (orphan). Keep
`_format_parameters`. The propose-mode tool restriction moves into outline.md (5.3.7.4).

**write.py::build** collapses to `<resolved_details>` only; delete `has_style_notes`/`has_image`/
tool_sequence branches. Keep `_format_parameters` + `_render_image` (both still used). The image
judgment moves into write.md (5.3.7.3). Note: the deleted no-style branch contains the banned word
"tighten" — it leaves with the block, so nothing to add.

**cite.py::build** keeps the snippet/no-snippet split ONLY for `<line_content>`:
```python
def build(flow, resolved:dict, user_text:str) -> str:
    snippet = _snippet_text(flow)
    details = f'<resolved_details>\n{_format_parameters(flow)}\n</resolved_details>'
    if snippet:
        return f'<line_content>\n{snippet}\n</line_content>\n\n{details}'
    return details
```
Delete `has_url`/tool_sequence/end_condition/`common` dict and both TEMPLATE_* strings; replace with the
inline f-strings above. Keep `_snippet_text`, `_format_parameters`.

**compare.py::build** keeps previews split, drops `_DIFF_CLAUSE` (now orphan → delete):
```python
def build(flow, resolved:dict, user_text:str) -> str:
    posts = resolved.get('posts') or []
    details = f'<resolved_details>\n{_format_parameters(flow)}\n</resolved_details>'
    if posts:
        previews = '\n\n'.join(_post_preview(p) for p in posts[:2])
        return f'<post_content>\n{previews}\n</post_content>\n\n{details}'
    return details
```
`_post_label` becomes unused (it only fed `post_labels` in the deleted `<task>`) → delete it (orphan).

**summarize.py::build** keeps outline split, drops both `<task>` blocks:
```python
def build(flow, resolved:dict, user_text:str) -> str:
    outline = (resolved.get('outline') or '').strip()
    details = f'<resolved_details>\n{_format_parameters(flow)}\n</resolved_details>'
    if outline:
        return f'<post_content>\n{outline}\n</post_content>\n\n{details}'
    return details
```
`_length_clause` becomes unused (it only fed the deleted `<task>`) → delete it (orphan). `post_title`
also drops out (no longer in any template). Keep `_format_parameters`.

**rework.py::build**:
```python
def build(flow, resolved:dict, user_text:str) -> str:
    return (f'<post_preview>\n{render_section_preview(resolved["section_preview"])}\n</post_preview>\n\n'
            f'<resolved_details>\n{_format_parameters(flow)}\n</resolved_details>')
```
Delete `has_remove`/`tool_sequence`. Keep the direct `resolved["section_preview"]` index (policy
preloads it via include_preview=True; a KeyError here is a real bug we want loud).

**refine.py::build** keeps `<post_content>` (current_outline) + details; delete only the `<task>` lines
from TEMPLATE, keep the rest of build() (it already just formats).

**release.py / browse.py / schedule.py / audit.py**: delete `<task>` from TEMPLATE; audit additionally
gains the `<post_content>` block (5.3.7.1). Their `_format_parameters(flow, resolved)` signatures stay.

Acceptance: `grep -rn '<task>' backend/prompts/pex/starters/ backend/prompts/for_pex.py` → nothing.

---

## 6. Content fixes (5.3.7)

### 6a. audit: too many read actions (5.3.7.1)
`backend/modules/policies/revise.py::audit_policy` line 233-234. Before:
```python
        self.record_snapshot(self.content, flow, context, post_id)
        text, tool_log = self.llm_execute(flow, state, context, tools)
```
After:
```python
        self.record_snapshot(self.content, flow, context, post_id)
        pre = self._read_post_content(post_id, tools)
        text, tool_log = self.llm_execute(flow, state, context, tools,
            extra_resolved={'post_prose': pre.get('content', '')})
```
Leave line 244 `self._read_post_content(post_id, tools)` (post-edit card read) as its own call.

`backend/prompts/pex/starters/audit.py::build` (the ADD from §5):
```python
def build(flow, resolved:dict, user_text:str) -> str:
    prose = (resolved.get('post_prose') or '').strip()
    block = f'<post_content>\n{prose}\n</post_content>\n\n' if prose else ''
    return block + f'<resolved_details>\n{_format_parameters(flow, resolved)}\n</resolved_details>'
```

`backend/prompts/pex/flows/audit.md` step 1a (now ~line 7 after frontmatter strip; body line "a.
`editor_review(content)` … `read_section` the sections first and pass their combined text."):
replace the sentence "It takes PROSE, not an id: `read_section` the sections first and pass their
combined text." with: "It takes PROSE, not an id: the full post prose is preloaded in the
`<post_content>` block — pass that text to `editor_review`. Do NOT `read_section` every section; only
`read_section` a specific section immediately before you `revise_content` it, once each, no re-reads."
Leave step 2's "(if not already read)" clause untouched.

### 6b. compose no-re-read (5.3.7.2)
`backend/prompts/pex/flows/compose.md` Tools → Task-specific tools bullet for `read_section` (body
"- `read_section(post_id, sec_id)` — required before composing any section. Never write without
reading."): append "Read each in-scope section at most once; never re-read a section you have already
converted." Leave draft.py:209 (`include_preview=True`) as-is.

### 6c. write.md image sentence (5.3.7.3)
`backend/prompts/pex/flows/write.md` Process step 3 (the Edit/Add/Remove bullet list). Add one bullet:
"- **Image**: when an `image` parameter is present, judge whether the image fits the section's main
idea and replace or drop it via `revise_content` / `remove_content`." (style_notes priority already in
step 3's "treat it as the priority signal" bullet — leave it.)

### 6d. outline.md forbidden-tools sentence (5.3.7.4)
`backend/prompts/pex/flows/outline.md` Propose mode step 3 ("3. Do not call `generate_outline`. End the
turn by returning the text you just wrote."): replace with "3. Call NO tools in propose mode except an
optional single `find_posts`; specifically do not call `read_metadata`, `generate_outline`,
`inspect_post`, or `write_text`. End the turn by returning the text you just wrote."

### 6e. Trim "### Tools" restatement (5.3.7.5)
Per-file light trim across the 16 flow files: in `## Tools` → `### Task-specific tools`, cut bullets
that only echo the tools.yaml signature+description. Keep any bullet carrying judgment (when/order/once
per turn/fallback/"policy already did this"). When unsure, KEEP (harmless; the allowlist test still
guards names). This is judgment-per-line, not a rewrite — do it conservatively. Concretely low-risk
cuts I would make: none that remove judgment. For audit/compose/write/outline (already touched for
6a-6d) apply the trim in the same pass; for the other 12 files apply only if a bullet is a pure
signature echo. If uncertain on any file, leave it (zero-risk, test-safe).

---

## 7. Tests — `utils/evaluation_suite/_tests/pex_unit_tests.py`

- 556-557: `engineer.tool_call(flow_classes['audit'](), '', {}, [], None, skill_prompt='')` (both) →
  `engineer.flow_execute(..., flow_prompt='')`.
- 560-567: `test_skill_call_honors_model_tier` — rename calls `engineer.skill_call(...)` →
  `engineer.flow_reply(...)` and keyword `skill_prompt=''` → `flow_prompt=''` (566, 567). Test name may
  stay (cosmetic); I will keep it to minimize churn, or rename to `test_flow_reply_honors_model_tier`.
  Docstring line 561 "skill_call routes…" → "flow_reply routes…".
- 1647 import: `from backend.prompts.for_pex import build_skill_system` → `build_flow_system`.
- 1649 `_SKILL_DIR` → `_FLOW_DIR = _Path(__file__).resolve().parents[3] / 'backend' / 'prompts' /
  'pex' / 'flows'`.
- 1651 delete `_PEX_AGENT_SKILLS`.
- 1656 `_skill_files()` → `_flow_files()` globbing `_FLOW_DIR`.
- 1669-1684 delete `test_skill_tools_match_flow` entirely (its only users of `load_skill_meta` /
  `_PEX_AGENT_SKILLS` go with it).
- 1687-1698 `test_few_shot_tools_are_allowlisted`: keep; update loop `for skill in _skill_files():` →
  `_flow_files()`; line 1695 `PromptEngineer.load_skill_template(skill) or ''` →
  `PromptEngineer.load_flow_prompt(skill)` (no `or ''` — returns str now). Loop var `skill` may stay.
- 1701-1706 `test_flow_tools_are_registered`: unchanged.
- 1709-1711 repurpose `test_loader_strips_frontmatter` → `test_loader_reads_flow_prompt`:
  ```python
  def test_loader_reads_flow_prompt():
      body = PromptEngineer.load_flow_prompt('outline')
      assert body and not body.startswith('---') and '## Process' in body
  ```
- 1714-1718 `test_skill_system_ends_with_reminder`: update `build_skill_system` → `build_flow_system`
  (1718); loop var `skill_prompt` may stay (cosmetic).
- 1721-1723 `test_reminder_is_agentic`: unchanged.
- `_COMPONENT_TOOLS` (1652), `_yaml_tools`, `_few_shot_tool_calls`, `_TOOLS_YAML`: keep.
- `import yaml as _yaml` (1642): still used by `_yaml_tools` — keep. `import re as _re` (1641): still
  used by `_few_shot_tool_calls` — keep.

No test inspects `<task>` / `<resolved_details>` / "Skill Instructions" text (grep-confirmed), so the
starter shrink needs no further test edits.

---

## 8. Doc — `utils/helper_ref.md`

Spec (5.3.4 item 7) calls line 36 optional/doc-only. There are actually 6 stale references
(lines 20, 21, 31, 36, 40, 200). To keep the reference honest I will update all in one pass:
- 20 `skill_call(... skill_prompt=...)` → `flow_reply(... flow_prompt=...)`, "Loads
  `prompts/pex/flows/<...>.md`".
- 21 `tool_call(...)` → `flow_execute(...)`.
- 31 `load_skill_template(flow_name) -> str | None` → `load_flow_prompt(flow_name) -> str` reads
  `backend/prompts/pex/flows/<flow_name>.md`.
- 36 `_SKILL_DIRS → (...)` → name `_FLOW_DIR` (`pex/flows/`) and `_SKILL_DIR` (`pex/skills/`), plus
  `load_flow_prompt` / `load_skill`.
- 40 `_build_skill_prompt` and 200 `load_skill_template + build_skill_prompt + tool_call` — these
  reference names that predate this round (`_build_skill_prompt`/`build_skill_prompt` do not exist in
  live source; already stale). Update the `tool_call`→`flow_execute` and `load_skill_template`→
  `load_flow_prompt` tokens on line 200; leave the already-wrong `_build_skill_prompt` mentions alone
  (pre-existing dead reference, not my mess to clean — flag, don't fix).

---

## 9. Verify

1. `grep -rn 'skill_call\|\btool_call\b\|build_skill_system\|build_skill_messages\|load_skill_template\|
   load_skill_meta\|_split_frontmatter\|_resolve_skill_path\|_SKILL_DIRS' backend/ backend/prompts/for_orchestrator.py`
   → nothing (excluding `_openai_streaming_tool_call` and provider-loop `tool_calls` locals, which are
   unrelated and stay).
2. `grep -rn '<task>' backend/prompts/pex/starters/ backend/prompts/for_pex.py` → nothing.
3. Free suite green, ZERO skips, from `assistants/Hugo` cwd (test-cwd note: set cwd + sys.path[0] to the
   assistant dir):
   `python -m pytest utils/evaluation_suite/_tests/pex_unit_tests.py
   utils/evaluation_suite/_tests/nlu_unit_tests.py utils/evaluation_suite/_tests/mem_unit_tests.py
   utils/evaluation_suite/_tests/model_unit_tests.py`
4. Composition eyeball (5.3.10.1) for audit/outline/write: render `build_flow_system(build_system({}),
   flow, load_flow_prompt(name))` + `build_flow_messages(...)` and confirm: `<task>` gone from user
   message; same task/tool guidance now in the flow-instruction section of system; divider reads "Flow
   Instructions"; audit user message carries a `<post_content>` prose block. Nothing else vanished.

---

## Spec gaps / risks (flag, but plan as spec directs)

1. **conftest.py:76 missed by the spec's "exhaustive" grep.** `a.engineer.tool_call = _stub_tool_call`
   must be renamed to `flow_execute` or the `mock_agent` fixture stops stubbing the tool loop and
   mock_agent tests hit a live provider. I include the fix in §4; without it criterion 4 (zero skips /
   green) fails. This is the one real correctness gap.
2. **helper_ref.md has 6 stale references, not 1.** Spec scoped only line 36 (optional). I update all 6
   tokens except the already-dead `_build_skill_prompt` mentions (pre-existing, out of scope).
3. **base.py:15 comment** names `engineer.tool_call`. I update the word for accuracy; it is a comment,
   zero runtime effect.
4. **compose.py preview fallback wording**: the spec's 5.3.6 example shortens the "(section previews
   not preloaded …)" message. I keep the existing longer message (surgical; not a required change).
5. **5.3.7.5 "### Tools" trim is judgment-based and non-deterministic.** I take the conservative read
   (keep-when-unsure), so the two builders may diverge on which echo-only bullets get cut. This is
   test-safe (allowlist test guards names) but means the diff here is reviewer-dependent, not exact.
6. **Orphan cleanups from my own edits**: `import yaml` (prompt_engineer.py:12), and starter helpers
   `_snippet_text` (brainstorm), `_topic_text` (outline), `_post_label` (compare), `_length_clause`
   (summarize), `_DIFF_CLAUSE` (compare) become unused after the `<task>` deletions. I remove them
   (CLAUDE.md: remove orphans my change created). I will re-grep each before deleting to be sure no
   other caller exists.
