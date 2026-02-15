# Skill: inspect

Inspect a specific draft config section in detail.

## Behavior

- Use `config_read` with the section slot to get the section data
- Present all fields, their values, and any validation notes
- Compare against spec requirements if detail_level is "full"

## Slots

- `section` (required): Config section to inspect
- `detail_level` (elective): "summary" or "full"
