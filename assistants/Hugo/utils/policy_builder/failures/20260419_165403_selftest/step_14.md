# Step 14 failure — release

## Expected
- origin: release
- tool_log: ['channel_status', 'release_post']
- blocks: ['toast']
- metadata: ['tool_error']
- scratchpad_keys: []
- flow_status: Completed

## Actual
- origin: error
- tool_log: ['channel_status']
- blocks: []
- metadata: ['tool_error']
- scratchpad_keys: []
- flow_status: Running

## Diff
- origin: expected='release' actual='error'
- tool_log: expected=['channel_status', 'release_post'] actual=['channel_status']
- blocks: expected=['toast'] actual=[]
- flow_status: expected='Completed' actual='Running'

## State snapshot
- active_post: TestPost
- keep_going: False
- has_issues: True
- scratchpad keys: ['inspect', 'audit']
- flow stack: ['release']
- turn_id: 14

## Rubric
did_action: Attempts publication; did_follow_instructions: Targets Substack.

## (Playwright only) Screenshot
./step_14.png

## (Playwright only) Network log (last 20 requests)
| timestamp | method | url | status |
| --- | --- | --- | --- |
| 12:00:00 | POST | /api/chat | 200 |
| 12:00:05 | GET | /api/posts/TestPost | 200 |

## Reproducer
pytest utils/tests/e2e_agent_evals.py::TestSyntheticDataPostE2E::test_step_14 -v -s --tb=short
