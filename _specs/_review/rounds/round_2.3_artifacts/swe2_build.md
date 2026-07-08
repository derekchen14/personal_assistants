# SWE2 build — round 4.3

## Orders echo
D1: 34 PEX exemplars added, all 13 skills now at floor 5; compare/rework/refine/write/plan untouched.
D2: limits.max_reads:3 in yaml; pex.py max_reads+_reads init, execute() reset, read_cap elif, increment after _success norm.
D3: 13 detection exemplars in experts/*_flows.py, each intent at floor 6; write/rework + refine/compose boundaries.
Authoring: no Kitty Hawk, no em-dash utterances, rotated topics, tools allowlisted.

## Diff file
/private/tmp/claude-501/-Users-derekchen-Documents-repos-personal-assistants/d8a47d03-22bc-4a83-ae1d-61010c02f371/scratchpad/round43_swe2.diff

## Stat
```
 assistants/Hugo/backend/modules/pex.py             |  9 ++++
 .../Hugo/backend/prompts/experts/converse_flows.py | 46 +++++++++++++++++-
 .../Hugo/backend/prompts/experts/draft_flows.py    | 24 +++++++++-
 .../Hugo/backend/prompts/experts/publish_flows.py  | 35 +++++++++++++-
 .../Hugo/backend/prompts/experts/research_flows.py | 24 +++++++++-
 .../Hugo/backend/prompts/experts/revise_flows.py   | 24 +++++++++-
 .../Hugo/backend/prompts/pex/skills/audit.md       | 33 +++++++++++++
 .../Hugo/backend/prompts/pex/skills/brainstorm.md  | 29 ++++++++++++
 .../Hugo/backend/prompts/pex/skills/browse.md      | 24 ++++++++++
 assistants/Hugo/backend/prompts/pex/skills/chat.md | 35 ++++++++++++++
 assistants/Hugo/backend/prompts/pex/skills/cite.md | 36 +++++++++++++++
 .../Hugo/backend/prompts/pex/skills/compose.md     | 32 +++++++++++++
 assistants/Hugo/backend/prompts/pex/skills/find.md | 25 ++++++++++
 .../Hugo/backend/prompts/pex/skills/outline.md     | 22 +++++++++
 .../Hugo/backend/prompts/pex/skills/promote.md     | 47 +++++++++++++++++++
 .../Hugo/backend/prompts/pex/skills/propose.md     | 52 +++++++++++++++++++++
 .../Hugo/backend/prompts/pex/skills/release.md     | 54 ++++++++++++++++++++++
 .../Hugo/backend/prompts/pex/skills/schedule.md    | 40 ++++++++++++++++
 .../Hugo/backend/prompts/pex/skills/summarize.md   | 26 +++++++++++
 shared/shared_defaults.yaml                        |  1 +
 20 files changed, 613 insertions(+), 5 deletions(-)
```

## Notes
Base verified at 8875217. All edits in worktree; touched only assistants/Hugo/backend/** and shared/shared_defaults.yaml (no utils/, no tests). Every .py parses; yaml max_reads=3. Deviations flagged: (1) read-counter increment placed after _success normalization per the direction's adopted order (safe if a result lacks _success). (2) Remaining em-dashes in added lines sit only in descriptor headers (### Example N — ...) matching each file's existing header style and in propose's "Final reply (no write tool — ...)" copied from its Example 1; none appear in any user utterance, satisfying the binding "no em-dashes in utterances" rule. Detection exemplars keep the JSON output block as required. Did not run pytest (tests are the orchestrator's).
