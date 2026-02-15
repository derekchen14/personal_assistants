# Skill: confirm_export

Confirm and execute the final file export.

## Behavior

- Show a summary of what will be generated (ontology.py, domain YAML)
- Ask for final confirmation before writing files
- On confirmation, use `ontology_generate` and `yaml_generate` with dry_run=false
- Report the generated file paths

## Output

Confirmation dialog followed by export results.
