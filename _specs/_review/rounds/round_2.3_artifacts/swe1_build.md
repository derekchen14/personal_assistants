# SWE1 build — round 4.3

## Orders echo
D1: 34 PEX skill exemplars added, all skills at floor 5; compare/rework/refine/write/plan untouched.
D2: max_reads:3 in yaml; pex.py max_reads+_reads init, execute() reset, read_cap elif, increment on success.
D3: 13 contrastive detection exemplars; every intent at floor 6; write/rework boundary pinned.
Authorship: no Kitty Hawk, no em-dashes in new utterances, multi-word titles, topics rotated.
Scope: only assistants/Hugo/backend/** + shared/shared_defaults.yaml; utils/ untouched.

## Diff file
/private/tmp/claude-501/-Users-derekchen-Documents-repos-personal-assistants/d8a47d03-22bc-4a83-ae1d-61010c02f371/scratchpad/round43_swe1.diff

## Stat
```
 assistants/Hugo/backend/modules/pex.py             |  9 ++++
 .../Hugo/backend/prompts/experts/converse_flows.py | 46 +++++++++++++++++-
 .../Hugo/backend/prompts/experts/draft_flows.py    | 24 +++++++++-
 .../Hugo/backend/prompts/experts/publish_flows.py  | 35 +++++++++++++-
 .../Hugo/backend/prompts/experts/research_flows.py | 24 +++++++++-
 .../Hugo/backend/prompts/experts/revise_flows.py   | 24 +++++++++-
 .../Hugo/backend/prompts/pex/skills/audit.md       | 31 ++++++++++++
 .../Hugo/backend/prompts/pex/skills/brainstorm.md  | 31 ++++++++++++
 .../Hugo/backend/prompts/pex/skills/browse.md      | 23 +++++++++
 assistants/Hugo/backend/prompts/pex/skills/chat.md | 36 ++++++++++++++
 assistants/Hugo/backend/prompts/pex/skills/cite.md | 35 ++++++++++++++
 .../Hugo/backend/prompts/pex/skills/compose.md     | 32 +++++++++++++
 assistants/Hugo/backend/prompts/pex/skills/find.md | 24 ++++++++++
 .../Hugo/backend/prompts/pex/skills/outline.md     | 23 +++++++++
 .../Hugo/backend/prompts/pex/skills/promote.md     | 42 +++++++++++++++++
 .../Hugo/backend/prompts/pex/skills/propose.md     | 51 ++++++++++++++++++++
 .../Hugo/backend/prompts/pex/skills/release.md     | 55 ++++++++++++++++++++++
 .../Hugo/backend/prompts/pex/skills/schedule.md    | 43 +++++++++++++++++
 .../Hugo/backend/prompts/pex/skills/summarize.md   | 21 +++++++++
 shared/shared_defaults.yaml                        |  1 +
 20 files changed, 605 insertions(+), 5 deletions(-)
```

## Notes
Base verified 8875217. All .py parse; allowlist + skill-tool + loader tests pass (4 passed); production load_config exposes max_reads=3; every intent at floor 6.

MUST-FLAG (orchestrator/utils scope, I cannot touch utils/): two test fixtures hardcode a full `limits` override that omits max_reads, so PEX.__init__ raises KeyError. Add `'max_reads': 3` to: conftest.py:109-111 (broad fixture) and pex_unit_tests.py:518-520 (test_max_rounds_read_from_config). Production is fine; only these fixtures need the one-line add.

Deviation adopted per direction: increment counter AFTER _success normalization (no KeyError risk). chat.md new exemplars follow chat's own voice-layer shape (Recent conversation/Scratchpad/Final reply), not write.md's Resolved Details shape, since chat has no tools and its file established that shape; all other skills match write.md. propose sibling-fallback slot omitted (undocumented tool for that skill); covered its real op space instead.
