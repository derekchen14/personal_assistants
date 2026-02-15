# Skill: generate

Generate the final domain config files from the collected requirements.

## Behavior

- Read the full config with `config_read` to verify completeness
- Check that minimum requirements are met: scope, intents (4), entities (3), persona
- Use `ontology_generate` to create the ontology.py file
- Use `yaml_generate` to create the domain YAML
- Present a summary of what was generated
- If requirements are incomplete, list what's missing and suggest next steps

## Slots

- `format` (elective): Output format preference

## Output

Summary of generated files with paths, or a list of missing requirements.
