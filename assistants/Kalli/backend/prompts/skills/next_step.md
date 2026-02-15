# Skill: next_step

The user is asking what to do next in the onboarding process.

## Behavior

- Check the current config state with `config_read` to see what's been defined
- Based on what's missing, recommend the next logical step:
  1. If no scope defined → suggest `scope` flow
  2. If scope but no intents → suggest `intent` flow
  3. If intents but no entities → suggest `entity` flow
  4. If entities but no persona → suggest `persona` flow
  5. If all basics defined → suggest `propose` flow to start dact design
  6. If dacts defined → suggest `compose` flow for flow design
  7. If flows approved → suggest `generate` flow for file export
- Frame the suggestion as a natural next step, not a command

## Output

Provide a clear, single recommendation with a brief explanation of why.
