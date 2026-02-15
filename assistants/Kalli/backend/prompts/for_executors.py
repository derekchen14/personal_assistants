SPEC_READ_GUIDANCE = (
    'When reading spec files:\n'
    '- Use the exact spec name (e.g., "nlu", "pex", "display_frame")\n'
    '- Request specific sections when possible to reduce context\n'
    '- Spec files are in _specs/ directory organized by category: '
    'modules/, components/, utilities/\n'
    '- If a spec_name doesn\'t match, try common variations '
    '(e.g., "flow_stack" vs "flow-stack")'
)

CONFIG_WRITE_GUIDANCE = (
    'When writing config sections:\n'
    '- Valid sections: scope, persona, guardrails, intents, entities, flows, '
    'tools, display, key_entities\n'
    '- Use merge=true (default) to update fields without overwriting\n'
    '- Use merge=false to completely replace a section\n'
    '- Validate that required fields are present before writing'
)

ONTOLOGY_GENERATE_GUIDANCE = (
    'When generating ontology.py:\n'
    '- Requires at minimum: intents (4 domain-specific), dacts (8+), '
    'flows (16+)\n'
    '- Use dry_run=true first to preview the output\n'
    '- Confirm with user before writing (dry_run=false)'
)

YAML_GENERATE_GUIDANCE = (
    'When generating domain YAML:\n'
    '- Requires at minimum: persona (name, tone, style), '
    'key_entities, tools\n'
    '- Use dry_run=true first to preview\n'
    '- Confirm with user before writing'
)

PYTHON_EXECUTE_GUIDANCE = (
    'When executing Python code:\n'
    '- Only for ad hoc generation tasks (creating config snippets, '
    'formatting data)\n'
    '- Never for file I/O or network access\n'
    '- Set reasonable timeout (default 30s)\n'
    '- Validate output before presenting to user'
)

TOOL_GUIDANCE = {
    'spec_read': SPEC_READ_GUIDANCE,
    'config_write': CONFIG_WRITE_GUIDANCE,
    'ontology_generate': ONTOLOGY_GENERATE_GUIDANCE,
    'yaml_generate': YAML_GENERATE_GUIDANCE,
    'python_execute': PYTHON_EXECUTE_GUIDANCE,
}


def get_tool_guidance(tool_name: str) -> str:
    return TOOL_GUIDANCE.get(tool_name, '')
