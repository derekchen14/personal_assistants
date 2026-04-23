from backend.components.flow_stack.parents import BaseFlow
from backend.components.display_frame import DisplayFrame

TEMPLATES = {
    'rework':   {'template': "{message}", 'block_hint': 'card'},
    'polish':   {'template': "{message}", 'block_hint': 'card'},
    'tone':     {'template': "{message}", 'block_hint': 'card'},
    'audit':    {'template': "{message}", 'block_hint': 'card'},
    'simplify': {'template': "{message}", 'block_hint': 'card'},
    'remove':   {'template': "{message}", 'block_hint': 'card'},
    'tidy':     {'template': "{message}", 'block_hint': 'card'},
}

def fill_revise_template(template:str, flow:BaseFlow, frame:DisplayFrame) -> str:
    template = TEMPLATES[flow.name()]['template']
    if flow.name() == 'audit':
        return template.format(message=_format_audit_message(frame))
    return template.format(message=frame.thoughts)


def _format_audit_message(frame:DisplayFrame) -> str:
    """Build a short spoken report from the audit card block data."""
    if not frame.blocks:
        return frame.thoughts or 'Audit complete — no structured findings to report.'

    data = frame.blocks[0].data
    report = data.get('report') or {}
    title = data.get('post_title', '')
    findings = report.get('findings') or []
    suggestions = report.get('suggestions') or []
    score = report.get('style_score')
    tone = report.get('tone_match')

    parts = []
    header = f'Audit of "{title}"' if title else 'Audit complete'
    if score is not None:
        header += f' — style score {score}'
    if tone:
        header += f', tone {tone}'
    parts.append(header + '.')

    if findings:
        parts.append(f'Found {len(findings)} finding(s):')
        for item in findings[:3]:
            aspect = item.get('aspect', 'style')
            severity = item.get('severity', 'low')
            observed = item.get('observed', '')
            line = f'- [{severity}] {aspect}'
            if observed:
                line += f': {observed}'
            parts.append(line)
    else:
        parts.append('No findings — the post aligns with prior writing.')

    if suggestions:
        parts.append('Suggestions:')
        for sug in suggestions[:3]:
            parts.append(f'- {sug}')
    return '\n'.join(parts)
