# Supporting prompts for Revise flows

ROUTE_FINDINGS_SCHEMA = {
    'type': 'object',
    'properties': {
        'groups': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'flow_name': {'type': 'string', 'enum': ['rework', 'polish', 'simplify', 'tone']},
                    'finding_idxs': {'type': 'array', 'items': {'type': 'integer'}},
                },
                'required': ['flow_name', 'finding_idxs'],
                'additionalProperties': False,
            },
        },
    },
    'required': ['groups'],
    'additionalProperties': False,
}


_FLOW_GUIDE = (
    "rework — substantive cross-section rewrites; structural reorganization; suggestions that touch multiple sections.\n"
    "polish — prose-level edits; word choice; phrasing; minor clarity nits within a single passage.\n"
    "simplify — reduce complexity (long sentences, jargon, dense paragraphs, high reading-level scores).\n"
    "tone — voice, register, and stylistic alignment with the user's prior writing."
)


def build_route_findings_prompt(findings:list[dict]) -> str:
    """Build a routing prompt that assigns each picked audit finding to one of the four
    revise sub-flows. Findings can be grouped: if multiple should be addressed together
    (same target section, same flow), put their indices in one group."""
    rows = []
    for idx, f in enumerate(findings):
        sec = f.get('sec_id') or 'whole post'
        rows.append(f"  [{idx}] severity={f.get('severity', 'low')} issue={f.get('issue', '?')} "
                    f"target={sec} note={f.get('note', '')[:160]}")
    findings_block = '\n'.join(rows) if rows else '  (none)'
    return (
        "You are routing audit findings to remediation flows. For each finding (referenced by its "
        "[index] below), assign it to exactly one flow. Group findings that should be addressed "
        "together — typically those targeting the same section or calling for the same kind of edit.\n\n"
        f"Flows:\n{_FLOW_GUIDE}\n\n"
        f"Findings:\n{findings_block}\n\n"
        "Return JSON of shape: {\"groups\": [{\"flow_name\": ..., \"finding_idxs\": [...]}, ...]}. "
        "Every finding index must appear in exactly one group; flows with no findings should be omitted."
    )
