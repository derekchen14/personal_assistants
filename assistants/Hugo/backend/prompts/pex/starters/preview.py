"""Per-turn starter prompt for PreviewFlow.

Renders a publication-ready view of a post. Lightweight — read-only. The `<post_content>` block
carries section previews so the skill can render without re-fetching every section.
"""

from backend.prompts.for_pex import render_section_preview


TEMPLATE_WITH_PREVIEW = """<task>
Preview "{post_title}" {channel_clause}. Read each section, assemble a publication-ready preview (title, body, metadata, estimated read time), and surface any pre-publish issues. End by emitting the preview.
</task>

<post_content>
{section_previews}
</post_content>

<resolved_details>
{parameters}
</resolved_details>"""


TEMPLATE_NO_PREVIEW = """<task>
Preview "{post_title}" {channel_clause}. Call `read_metadata` for the section list, then `read_section` per section to assemble the preview. End by emitting the preview.
</task>

<resolved_details>
{parameters}
</resolved_details>"""


def build(flow, resolved:dict, user_text:str) -> str:
    section_previews = render_section_preview(resolved.get('section_preview') or {})
    channel_label = _channel_label(flow)
    channel_clause = f'for {channel_label}' if channel_label else 'for the primary blog'

    common = {
        'post_title': resolved.get('post_title', 'this post'),
        'channel_clause': channel_clause,
        'parameters': _format_parameters(flow),
    }
    if section_previews:
        return TEMPLATE_WITH_PREVIEW.format(section_previews=section_previews, **common)
    return TEMPLATE_NO_PREVIEW.format(**common)


def _channel_label(flow) -> str:
    channel = flow.slots['channel']
    if channel.check_if_filled() and channel.values:
        val = channel.values[0]
        if isinstance(val, dict):
            return val.get('chl') or val.get('name') or ''
        return str(val)
    return ''


def _format_parameters(flow) -> str:
    lines = []
    channel = flow.slots['channel']
    if channel.check_if_filled():
        lines.append(f'Channel: {_channel_label(flow)}')
    return '\n'.join(lines) if lines else '(no parameters filled — interpret latest utterance)'
