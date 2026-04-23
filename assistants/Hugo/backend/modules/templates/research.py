from backend.components.flow_stack.parents import BaseFlow
from backend.components.display_frame import DisplayFrame

TEMPLATES = {
    'browse':    {'template': "Here are some topic ideas: {message}", 'block_hint': 'list'},
    'check':     {'template': "Here are your current drafts: {message}", 'block_hint': 'list'},
    'summarize': {'template': "Here's a summary: {message}"},
    'inspect':   {'template': "{message}"},
    'find':      {'template': "Here's what I found: {message}", 'block_hint': 'list'},
    'compare':   {'template': "Here's how they compare: {message}", 'block_hint': 'card'},
    'diff':      {'template': "{message}", 'block_hint': 'card'},
}

# Human-friendly labels for metric keys returned by inspect_post.
_INSPECT_LABELS = {
    'word_count': 'words',
    'section_count': 'sections',
    'estimated_read_time': 'minute read',
    'image_count': 'images',
    'link_count': 'links',
    'avg_paragraph_length': 'avg paragraph length',
    'heading_depth': 'heading depth',
    'empty_sections': 'empty sections',
}


def fill_research_template(template:str, flow:BaseFlow, frame:DisplayFrame) -> str:
    template = TEMPLATES[flow.name()]['template']
    if flow.name() == 'inspect':
        return template.format(message=_format_inspect_message(frame))
    return template.format(message=frame.thoughts)


def _format_inspect_message(frame:DisplayFrame) -> str:
    """Produce the spoken utterance for the inspect flow directly from metadata."""
    metrics = frame.metadata.get('metrics') or {}
    if not metrics:
        return frame.thoughts or 'No metrics available for that post.'

    parts = []
    if 'word_count' in metrics:
        parts.append(f'{metrics["word_count"]:,} words')
    if 'section_count' in metrics:
        parts.append(f'{metrics["section_count"]} sections')
    if 'estimated_read_time' in metrics:
        parts.append(f'{metrics["estimated_read_time"]}-minute read')
    if 'image_count' in metrics:
        parts.append(f'{metrics["image_count"]} images')
    if 'link_count' in metrics:
        parts.append(f'{metrics["link_count"]} links')
    if 'avg_paragraph_length' in metrics:
        parts.append(f'avg paragraph {metrics["avg_paragraph_length"]} words')
    if 'heading_depth' in metrics:
        parts.append(f'heading depth {metrics["heading_depth"]}')

    empty = metrics.get('empty_sections') or []
    if parts:
        summary = 'Your post has ' + ', '.join(parts) + '.'
    else:
        # Fall back — stringify remaining metrics with their labels.
        labelled = [f'{_INSPECT_LABELS.get(key, key)}: {val}' for key, val in metrics.items()]
        summary = 'Metrics — ' + '; '.join(labelled) + '.'
    if empty:
        summary += f' Empty sections: {", ".join(empty)}.'
    return summary
