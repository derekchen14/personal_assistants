from collections import Counter
from backend.components.flow_stack.parents import BaseFlow
from backend.components.display_frame import DisplayFrame

TEMPLATES = {
    'rework':   {'template': "{message}", 'block_hint': 'card'},
    'polish':   {'template': "{message}", 'block_hint': 'card'},
    'tone':     {'template': "{message}", 'block_hint': 'card'},
    'audit':    {'template': "{message}", 'block_hint': 'checklist'},
    'simplify': {'template': "{message}", 'block_hint': 'card'},
    'remove':   {'template': "{message}", 'block_hint': 'card'},
    'tidy':     {'template': "{message}", 'block_hint': 'card'},
}

_SEVERITY_ORDER = {'high': 0, 'medium': 1, 'low': 2}


def fill_revise_template(template:str, flow:BaseFlow, frame:DisplayFrame) -> str:
    template = TEMPLATES[flow.name()]['template']
    if flow.name() == 'audit':
        return template.format(message=_format_audit_message(frame))
    return template.format(message=frame.thoughts)


def _format_audit_message(frame:DisplayFrame) -> str:
    """Spoken readout for an audit turn. Branches on which metadata key is present:
      'reports'      → per-delegate rollup, audit just completed delegation
      'group_count'  → routing announcement, dispatch just stacked children
      otherwise      → discovery breakdown (findings + summary, may be empty for the no-findings path)"""
    metadata = frame.metadata
    if 'reports' in metadata:
        reports = metadata['reports']
        if not reports:
            return 'Audit complete.'
        rollup = '. '.join(f'{name}: {summary}' for name, summary in reports.items())
        return f'Audit complete. {rollup}.'
    if 'group_count' in metadata:
        names = metadata['flow_names']
        joined = ', '.join(names) if names else 'sub-flows'
        return f"Working on it — sending {metadata['group_count']} fix(es) to {joined}."

    findings = metadata['findings']
    summary = metadata['summary']
    if not findings:
        return summary or 'No findings — the post aligns with prior writing.'

    counts = Counter(f['severity'] for f in findings)
    breakdown = ', '.join(f'{counts[k]} {k}' for k in ('high', 'medium', 'low') if counts[k])
    parts = [f'Audit complete. Found {len(findings)} finding(s): {breakdown}.']
    if summary:
        parts.append(summary)
    sorted_findings = sorted(findings, key=lambda f: _SEVERITY_ORDER[f['severity']])
    for item in sorted_findings[:3]:
        sec = item['sec_id'] or 'whole post'
        parts.append(f"- [{item['severity']}] {item['issue']} ({sec}): {item['note']}")
    return '\n'.join(parts)
