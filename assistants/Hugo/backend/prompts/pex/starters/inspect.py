"""Per-turn starter prompt for InspectFlow.

Inspect is read-only. The skill gathers metrics/metadata itself via read tools;
this starter shows which post (if any), which metrics, and any threshold bound."""


def build(flow, resolved:dict, user_text:str) -> str:
    return f'<resolved_details>\n{_format_parameters(flow, resolved)}\n</resolved_details>'


def _format_parameters(flow, resolved:dict) -> str:
    lines = []
    source = flow.slots['source']
    if source.values:
        refs = [entry['post'] for entry in source.values if entry.get('post')]
        lines.append(f"Source: {', '.join(refs)}")
    else:
        lines.append('Source: (empty — library-wide question)')
    metrics = flow.slots['metrics']
    if metrics.steps:
        names = [step['name'] for step in metrics.steps]
        lines.append(f"Metrics: {', '.join(names)}")
    threshold = flow.slots['threshold']
    if threshold.check_if_filled():
        lines.append(f'Threshold: {threshold.level}')
    return '\n'.join(lines)
