"""Skill prompt assembly.

Three layers, each owned by a different file:

  - System prompt = persona (`general.build_system`) + intent prompt
    (`pex/sys_prompts.py::PROMPTS[intent]`) + skill body
    (`pex/skills/<flow>.md`) + execution rules suffix.

  - User message = filled starter (`pex/starters/<flow>.py::build`) +
    recent conversation + latest utterance.

  - Per-flow customization lives entirely in the skill file (static
    behavior) and the starter (runtime parameters with placeholders).

Slot-rendering helpers below are used by starter modules; add new ones
here on demand. The helpers are deliberately minimal — most slots
serialize fine via direct attribute access in the starter template.
"""

from importlib import import_module


AMBIGUITY_AND_ERRORS = """## Handling Ambiguity and Errors

If you encounter issues during execution, there are a few ways to manage them. You can retry calling a tool if there is a transient network issue. If you face uncertainty in the user's request because there are multiple possible interpretations, you should ask for clarification instead of making assumptions.

| ambiguity level | description |
|---|---|
| confirmation | Confusion among a small set of options; often just a decision on whether or not to proceed with a potentially risky action |
| specific | A specific piece of information or user preference is missing |
| partial | Unclear which post, note, or section is being discussed; indicates a lack of grounding |
| general | the user's request is gibberish; highly unlikely to encounter at this point in the process |

In contrast to semantic mis-understanding, there may also be systemic errors caused by syntactical or technical issues. Such errors are categorized into 8 possible violations:

| violation code | description |
|---|---|
| `failed_to_save` | A persistence tool didn't run or produced no effect |
| `scope_mismatch` | The flow ran at the wrong granularity |
| `missing_reference` | An entity referenced in a slot doesn't exist on the post |
| `parse_failure` | Skill output couldn't be parsed into the expected shape |
| `empty_output` | Skill returned nothing when prose was expected |
| `invalid_input` | A tool would reject or has rejected the arguments given |
| `conflict` | Two slot values contradict |
| `tool_error` | A deterministic tool returned `_success=False` |

Use the `handle_ambiguity()` or `execution_error()` tools to signal such issues only after considering all other paths to resolution."""


def build_skill_system(base_system:str, flow, skill_prompt:str|None) -> str:
    """System prompt = persona + intent prompt + ambiguity block + skill body.

    Execution rules have been folded into per-intent prompts and per-flow
    skills, so there is no shared suffix. The `--- {Flow_name} Skill
    Instructions ---` divider keeps the handoff from context to skill
    body visually obvious.
    """
    from backend.prompts.pex.sys_prompts import get_intent_prompt
    intent_prompt = get_intent_prompt(flow.intent)

    parts = [base_system, '\n\n', intent_prompt, '\n\n', AMBIGUITY_AND_ERRORS]
    if skill_prompt:
        flow_name = flow.name().capitalize()
        parts.append(f'\n\n--- {flow_name} Skill Instructions ---\n\n{skill_prompt}')
    return ''.join(parts)


def build_skill_messages(flow, convo_history:str,
                         user_text:str|None=None,
                         resolved:dict|None=None) -> list[dict]:
    """User message = filled starter + <recent_conversation>.

    The starter owns task framing, preloaded content, and resolved
    details. Conversation history follows in its own XML tag; the tail
    of that tag is the latest utterance, so no separate block is
    emitted. Falls back to a minimal scaffold for flows that don't yet
    have a starter module.
    """
    starter_text = _render_starter(flow, resolved or {}, user_text or '')

    segments = []
    if starter_text:
        segments.append(starter_text)
    if convo_history:
        segments.append(f'<recent_conversation>\n{convo_history}\n</recent_conversation>')

    return [{'role': 'user', 'content': '\n\n'.join(segments)}]


def _render_starter(flow, resolved:dict, user_text:str) -> str:
    try:
        module = import_module(f'backend.prompts.pex.starters.{flow.name()}')
        return module.build(flow, resolved, user_text)
    except ImportError:
        return _default_starter(flow, resolved)


def _default_starter(flow, resolved:dict) -> str:
    """Generic fallback for flows without a custom starter module.

    Produces the canonical XML shape (<task>, <resolved_details>) so that
    unmigrated flows still render a consistent prompt. Per-flow starters
    can override this for shape-specific needs (e.g. <post_content>).
    """
    post_title = resolved.get('post_title', '')
    title_clause = f' for "{post_title}"' if post_title else ''
    task = (
        f'Execute the {flow.name()} skill{title_clause}. '
        'Follow the Process steps in the skill instructions above. '
        'Call the task-specific tools in the order they describe.'
    )
    details_lines = []
    for slot_name, slot in flow.slots.items():
        if not slot.check_if_filled():
            continue
        label = slot_name.replace('_', ' ').capitalize()
        if slot_name == flow.entity_slot:
            val = slot.values[0] if slot.values else ''
            details_lines.append(f'{label}: {_summarize_entity(val)}')
        elif slot.values:
            details_lines.append(f'{label}: ' + '; '.join(str(v) for v in slot.values))
    details = '\n'.join(details_lines) if details_lines else '(no parameters filled)'
    return (
        f'<task>\n{task}\n</task>\n\n'
        f'<resolved_details>\n{details}\n</resolved_details>'
    )


def _summarize_entity(val) -> str:
    if isinstance(val, dict):
        return ', '.join(f'{key}={val[key]}' for key in ('post', 'sec', 'snip', 'chl') if val.get(key))
    return str(val)


# ── Slot renderers ──────────────────────────────────────────────────────
# Used by per-flow starter modules to format slot values in a way the
# LLM can read at a glance. Add new ones as flow-specific needs arise.


def render_source(slot) -> str:
    """SourceSlot → compact `post=<id>, section=<id>` form, omitting empty fields."""
    if not slot.values:
        return ''
    val = slot.values[0]
    parts = []
    for key, label in (('post', 'post'), ('sec', 'section'), ('snip', 'snippet'), ('chl', 'channel')):
        if val.get(key):
            parts.append(f'{label}={val[key]}')
    return ', '.join(parts)


def render_freetext(slot) -> str:
    """FreeTextSlot values are a list of strings. Join with '; ' for display."""
    if not slot.values:
        return ''
    return '; '.join(str(v) for v in slot.values)


def render_checklist(slot) -> str:
    """ChecklistSlot stores items in `steps` (dicts with name/description/checked).
    Fall back to `values` for non-checklist GroupSlots that happen to be passed in.
    """
    steps = getattr(slot, 'steps', None)
    if steps:
        return '; '.join(str(s.get('name', '')) for s in steps if s.get('name'))
    if slot.values:
        return '; '.join(str(v) for v in slot.values)
    return ''


def render_section_preview(preview:dict) -> str:
    """Nested `{sec_id: {title, preview}}` → readable markdown blocks."""
    if not preview:
        return ''
    blocks = []
    for sec_id, data in preview.items():
        title = data.get('title', sec_id)
        body = (data.get('preview') or '').rstrip()
        blocks.append(f'**{title}** (`{sec_id}`)\n{body}')
    return '\n\n'.join(blocks)
