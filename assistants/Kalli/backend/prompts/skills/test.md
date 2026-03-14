# Skill: test

Run validation tests against the built assistant.

## Behavior

- Use `run_tests` to execute test conversations across flow coverage
- Check slot filling accuracy, policy behavior, and edge_flow connectivity
- If scope is specified, narrow tests to that area (flows, slots, policies, coverage)
- Report pass/fail counts and highlight failures with suggested fixes

## Slots

- `scope` (optional): Area to test — flows, slots, policies, coverage, or full

## Output

List of test results with pass/fail status and failure details.
