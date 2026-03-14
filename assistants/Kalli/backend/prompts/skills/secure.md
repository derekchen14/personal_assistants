# Skill: secure

Configure authentication, API keys, and access permissions for the deployed assistant.

## Behavior

- Use `update_auth` to set or rotate API keys, rate limits, and access controls
- Validate that required credentials are present before deployment
- Report current security configuration state

## Slots

- `setting` (required): Key-value pair for the security setting to configure

## Output

Confirmation of updated security settings.
