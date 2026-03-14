# Skill: version

Tag a release version of the assistant.

## Behavior

- Use `tag_version` to create a versioned snapshot of the current config
- Generate a changelog with diff from the previous release
- Include release notes if provided

## Slots

- `tag` (required): Version tag (e.g., "v1.0", "v2.3.1")
- `notes` (optional): Release notes describing what changed

## Output

Version card with tag, timestamp, changelog, and release notes.
