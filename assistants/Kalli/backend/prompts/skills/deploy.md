# Skill: deploy

Deploy the assistant to a target environment.

## Behavior

- Verify the package exists and tests have passed
- Use `deploy_assistant` to push to the target environment (staging or production)
- Automatically generate a build report on successful deployment
- If deploying to production, warn if staging tests haven't run

## Slots

- `environment` (required): Target environment — staging or production

## Output

Deployment status with environment URL and build report summary.
