# Skill: preview

Preview generated output before committing to disk.

## Behavior

- Use `ontology_generate` or `yaml_generate` with dry_run=true
- Display the generated content for review
- If file_type is specified, only preview that type

## Slots

- `file_type` (elective): "ontology" or "yaml"
