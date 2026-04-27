# Evaluation Guidelines

## Background

Hugo's agent pipeline has three stages: NLU → PEX → RES. A single user turn flows through:

1. **NLU** — classifies intent, detects flow, fills slots, assigns confidence
2. **PEX** — selects a policy, runs the agentic tool-use loop (`llm_execute`), persists results
3. **RES** — applies a response template, optionally naturalizes the text

Previous evals mocked the LLM and/or tool dispatch, which hid real failures. We discovered that outlines weren't being saved, tools were silently dropped, and "passing" tests were meaningless. All E2E evals now run with real LLM calls and real tool execution. No mocks, no stubs.

## Setup

### Prerequisites
- API keys in `.env`: `ANTHROPIC_API_KEY` (required), `TAVILY_API_KEY`, `GOOGLE_API_KEY` (optional)
- The `database/` directory with `metadata.json` and seed content (posts, drafts, notes)
- Run from Hugo root: `cd assistants/Hugo`

### Running

```bash
# Free tier — no API keys, no LLM, ~6s for ~210 tests. Run after every major change.
pytest utils/tests/unit_tests.py utils/tests/policy_evals/ utils/tests/test_artifacts.py

# NLU accuracy (real LLM, flow-detection benchmark on test_cases.json)
pytest utils/tests/model_tests.py -m llm

# E2E full pipeline (real LLM + real tools, ~7 min)
pytest utils/tests/e2e_agent_evals.py -v --tb=short

# E2E with reliability checks (runs each turn 3x, slower)
pytest utils/tests/e2e_agent_evals.py -v -m reliability
```

The free tier covers service behavior, policy orchestration, and static lints — three layers that catch most local regressions without burning tokens. Run it after every non-trivial change. Reserve `model_tests.py` for changes touching NLU prompts/schemas, and `e2e_agent_evals.py` for end-of-feature integration verification.

### Test case format

Each test case in `test_cases.json` is a multi-turn conversation:
```json
{
  "convo_id": 1,
  "turns": [
    {
      "turn_count": 1,
      "role": "user",
      "utterance": "Create a new post about morning routines",
      "labels": {
        "intent": "Draft",
        "flow": "create",
        "dax": "{05A}"
      },
      "slots": {"title": "Morning Routines"},
      "expected_tools": ["create_post"],
      "rubric": {
        "did_persist": "post appears in metadata.json with correct title",
        "did_follow_instructions": "title matches or closely reflects 'morning routines'"
      }
    },
    {
      "turn_count": 2,
      "role": "agent",
      "utterance": "..."
    }
  ]
}
```

Labels on user turns:
- `labels.intent`, `labels.flow`, `labels.dax` — routing ground truth (used by model_tests and e2e_agent_evals)
- `slots` — expected slot fills (used by model_tests)
- `expected_tools` — ordered list of domain tool names the agent should call (used by e2e_agent_evals Level 2)
- `rubric` — verification criteria for response quality (used by e2e_agent_evals Level 3)

### File responsibilities

| File | Purpose | LLM? | Speed |
|------|---------|------|-------|
| `unit_tests.py` | Service-layer behavior on a tmp DB — disk round-trips, format invariants, regression tests | No | ~3s |
| `policy_evals/` | Per-flow policy orchestration with mocked `llm_execute` — argument passing, guard clauses, ambiguity declarations, frame shapes, scratchpad contracts | No | ~2s |
| `test_artifacts.py` | Static lints — skill-file frontmatter, few-shot tool alignment vs `flow.tools`, NLU JSON schema rules | No | ~0.1s |
| `model_tests.py` | NLU accuracy benchmarks against `test_cases.json` — flow detection, confidence calibration | Yes (`-m llm`) | ~1 min |
| `e2e_agent_evals.py` | Full pipeline scenarios — real LLM + real tools, 3-level evaluation, produces report next to the file | Yes | ~5–8 min |
| `test_cases.json` | Shared test data — conversations with labels, expected_tools, and rubrics |  |  |
| `conftest.py` | Fixtures — `agent` (real LLM), `config` |  |  |

---

## Unit Tests

**File:** `unit_tests.py`
**Requires:** No API keys, no LLM calls
**Fixture:** `tmp_db` (temporary database directory, patched via monkeypatch)

Behavioral tests for the service layer (PostService, ContentService, AnalysisService, PlatformService) plus pure helpers in `services.py` (`split_sentences`, `join_sentences`, `_rebuild_content`, `_validate_outline`). Also covers PromptEngineer model resolution, ensemble voting math, NLU action-turn dispatch, and template fill helpers.

### What earns its keep

The strongest tests in this file write to a temp DB and **read content back from disk** to verify the round-trip:
- `test_revise_content_replaces_existing_outline_section` — asserts `'- evaluate model' in saved`.
- `test_insert_section_preserves_blank_separator` — asserts `'- pain point\n\n## Takeaways' in saved` (regression test).
- `test_update_post_renames_section_via_sections_list` — verifies position-based rename writes the right `## Heading`.
- `test_save_section_content_validates_duplicate_h2` — exercises `_validate_outline` raising `OutlineValidationError`.
- `test_split_sentences_*` and `test_split_join_*_roundtrip` — round-trip property tests, each guarding a specific past bug (e.g., bullets collapsing into `- a - b - c`).
- `test_rebuild_content_does_not_double_blank` — exact-string assertion on rebuilt markdown.

### How they work

Each service test uses the `tmp_db` fixture which:
1. Creates a temporary directory structure (`content/drafts`, `content/notes`, `content/posts`, `.snapshots`, `guides`).
2. Writes a minimal `metadata.json`.
3. Monkeypatches `_DB_DIR` in `backend.utilities.services` so all ToolService instances use the temp path.
4. Service instances created within tests automatically pick up the patched paths via `__init__`.

### What they do NOT cover

- Live LLM behavior (any test that touched the LLM was moved to `model_tests.py` or `e2e_agent_evals.py`).
- End-to-end pipeline integration (NLU → PEX → RES) — covered by `e2e_agent_evals.py`.
- Per-flow policy orchestration — covered by `policy_evals/`.
- Skill-file structural correctness — covered by `test_artifacts.py`.

---

## Policy Evals

**Directory:** `policy_evals/`
**Requires:** No API keys, no LLM calls
**Fixture:** `monkeypatch` to stub `BasePolicy.llm_execute`

One file per flow (`test_outline_policy.py`, `test_refine_policy.py`, `test_release_policy.py`, etc.). Stubs `llm_execute` to return a controlled `(text, tool_log)` tuple, then asserts on what the policy *did* with that signal — argument passing, guard clauses, frame shapes, ambiguity declarations, scratchpad contracts.

### What they catch

- **Argument drift.** "I refactored the policy and forgot to pass `propose_mode=True` through `extra_resolved`" — caught.
- **Tool gating bugs.** Release only fires `update_post(status='published')` when both `channel_status` AND `release_post` succeeded; a regression that flips the gate is caught here.
- **Guard-clause regressions.** Compose stacking-on Outline when the post has no sections; Refine declaring `partial` ambiguity when source is missing.
- **Frame-shape contracts.** Right block types (`card`, `list`, `selection`, `toast`), right `origin`, right `data` keys.
- **Scratchpad write contracts.** Find writes `{version, turn_number, used_count, query, items: [{post_id, title, status, preview}]}`. Audit/Brainstorm have their own shapes.
- **Algorithmic correctness.** Find dedupes by `post_id` across expansion terms; Rework checks off ChecklistSlot suggestions when the skill returns `{"done": [...]}`.

### What they cannot catch

- Skill-prompt bugs (the LLM is mocked).
- Tool-implementation bugs (tools are stubbed by `make_tool_stub`).
- Wire-format bugs between PEX and the frontend (the policy never sees the wire).
- NLU classification bugs (flows are pre-stacked).
- Cross-flow control-flow bugs where one policy's `call_flow_stack` mutation should drive another flow on the next iteration. (Add the tool_log entry yourself if you need to test this seam.)

### Pattern to follow

```python
def _stub_llm_execute(return_text, tool_log=None, captured=None):
    log = list(tool_log or [])
    def stub(self, flow, state, context, tools, include_preview=False,
            extra_resolved=None, exclude_tools=()):
        if captured is not None:
            captured.append({'extra_resolved': dict(extra_resolved or {}),
                             'exclude_tools': tuple(exclude_tools)})
        return return_text, log
    return stub

def test_<flow>_<scenario>(monkeypatch):
    policy, comps = build_policy('<flow>')
    comps['flow_stack'].stackon('<flow>')
    top = comps['flow_stack'].get_flow()
    top.slots['source'].add_one(post=_POST_ID)
    # ... fill remaining slots ...
    captured = []
    tool_log = [{'tool': '<save_tool>', 'input': {}, 'result': {'_success': True}}]
    monkeypatch.setattr(BasePolicy, 'llm_execute',
        _stub_llm_execute('<skill text>', tool_log=tool_log, captured=captured))
    tools = make_tool_stub({...})
    frame = policy.execute(state, context, tools)
    # assert on captured args, frame shape, flow status, ambiguity, scratchpad
```

---

## Static Lints

**File:** `test_artifacts.py`
**Requires:** No API keys, no LLM calls

Three layers of offline lints, each parameterized over the relevant universe:

1. **Skill frontmatter** (`test_skill_tools_match_flow`) — every `.md` in `backend/prompts/pex/skills/` has YAML frontmatter whose `tools:` list matches `flow.tools` of the owning flow.
2. **Few-shot tool alignment** (`test_few_shot_tools_are_allowlisted`) — every `name(` token in a skill's `## Few-shot` block is either in `flow.tools` or in the `COMPONENT_TOOLS` allowlist (`handle_ambiguity`, `coordinate_context`, `manage_memory`, `call_flow_stack`, `execution_error`, `save_findings`).
3. **NLU JSON schema rules** — locally encodes Anthropic structured-output rules empirically observed via API rejections:
   - Rule A: `minimum`/`maximum`/`exclusiveMinimum`/`exclusiveMaximum` not allowed on `number`.
   - Rule B: `enum` cannot combine with a list-valued `type` (use `anyOf`).
   - Rule C: `additionalProperties` cannot be a schema object (must be `false` or absent).

**Adding a new rule:** when a live-API rejection surfaces in dev, add a clause to `_lint_schema()` and a self-test (`test_lint_detects_rule_<X>`). That converts a one-time discovery into permanent offline coverage.

### What they catch

- Skill `.md` references a tool that isn't in the flow's tools list (typo, stale prompt, retired tool).
- Flow's tool list contains a tool with no entry in `schemas/tools.yaml` (orphan registration).
- NLU emits a JSON schema that Anthropic would reject (any of the three rules above).

### What they cannot catch

- Skill prompts that are syntactically valid but semantically wrong (wrong instructions, missing examples).
- Tool YAML entries whose schema is malformed in ways outside the encoded rules.
- Anthropic provider rules we haven't encoded yet (a new rejection type would surface in dev first; encode it then).

---

## Model Tests

**File:** `model_tests.py`
**Requires:** `ANTHROPIC_API_KEY` (real LLM calls)
**Fixture:** `agent` (real Agent instance)
**Marker:** `@pytest.mark.llm` on all test classes

Model tests measure NLU accuracy with real LLM calls. They test whether the NLU module correctly classifies intent, detects the right flow, and produces meaningful confidence scores. These do NOT test PEX or RES — only the understanding stage.

### What they cover

**Flow detection accuracy (eval dataset):**
- `TestFirstTurnFlowAccuracy` — runs the first user turn of each conversation in `test_cases.json` through NLU, compares detected flow against the `labels.flow` ground truth. Reports accuracy as a percentage, fails if below threshold (currently 60%).
- `TestMultiTurnFlowAccuracy` — runs all user turns in sequence (with context buildup), checks flow detection at each turn. Tests whether NLU handles context-dependent utterances (e.g., "summarize that one" after a search).

**Confidence calibration:**
- `TestConfidenceScoresMeaningful` — verifies that no conversation produces a confidence score below the floor (currently 0.3). Catches cases where the model is guessing randomly.

**Canonical flow detection (representative utterances):**
- `TestCanonicalFlowDetection` — 10 hand-picked utterances across 7 intents, run through the full `agent.take_turn()` pipeline (NLU + PEX + RES). Checks both flow routing and that a real response is produced. These are smoke tests — one per intent minimum.

### How they work

- `_detect_flow(agent, utterance)` adds the turn to context, runs `nlu.understand()`, and returns the state
- Each test resets the agent between conversations to avoid context contamination
- Gold DAX is NOT used — these tests measure the NLU's real classification ability
- The eval dataset (`test_cases.json`) provides ground-truth labels for comparison

### What they do NOT cover

- Tool execution correctness (that's E2E Level 2)
- Response quality (that's E2E Level 3)
- Slot-filling accuracy (labels exist in test_cases.json but no test asserts on them yet)

---

## E2E Agent Evals

**File:** `e2e_agent_evals.py`
**Requires:** `ANTHROPIC_API_KEY` (real LLM + real tools)
**Fixture:** `agent` (real Agent instance)
**Data:** `test_cases.json` (conversations with labels, expected_tools, rubrics)

E2E evals test the complete pipeline with real LLM calls and real tool execution. No mocks, no stubs. Each conversation runs through NLU → PEX → RES with the gold DAX to isolate execution quality from NLU classification noise.

### Three evaluation levels

Levels are cumulative — Level 1 failures block Level 2, Level 2 failures block Level 3.

#### Level 1: Basic Functionality

**Question:** Did the agent complete the turn without crashing?

**Checks:**
- The pipeline ran end-to-end without Python exceptions
- No `_error` results from tool calls that should have succeeded
- The agent returned a `message` or `frame` with non-empty content
- No fallback responses ("I'm having trouble understanding")

**Implementation:**
- `agent.take_turn(text, dax=gold_dax)` with real LLM, real tools
- Gold DAX bypasses NLU uncertainty — we're testing PEX + RES, not classification
- Check `result['message']` or `result['frame']['data']['content']` is non-empty and >10 chars
- Scan tool log for any `_success: False` results on expected tools

**Failure examples:**
- Uncaught exception during policy execution
- `generate_outline` returns `_error: validation` because content was empty
- Agent returned empty message with no frame
- Agent returned a clarification prompt when the utterance was unambiguous

#### Level 2: Tool Trajectory

**Question:** Did the agent call the right tools in the right order?

**Checks:**
- The agent called the expected domain tools listed in `expected_tools`
- Tool call order respects dependencies:
  - `read_metadata` before `read_section` (need section_ids first)
  - `find_posts` before `read_metadata` (when resolving by title)
  - `read_metadata`/`read_section` before `revise_content` (read before write)
  - `generate_outline` called with non-empty content
- No hallucinated tool names (tools not in the flow's `tools` list)
- No excessive redundant calls (e.g., `find_posts` called 5 times with same query)

**Implementation:**
- Monkey-patch `pex._dispatch_tool` to log all calls: `(tool_name, input, success)`
- Extract the domain tool subsequence (filter out component tools: `handle_ambiguity`, `coordinate_context`, `manage_memory`, `read_flow_stack`)
- Compare domain tool sequence against `expected_tools` from the test case
- Matching is ordered — the domain tools must appear in the expected order, but extra component tool calls may be interspersed

**Label format:**
```json
"expected_tools": ["find_posts", "generate_outline"]
```

**Failure examples:**
- Outline flow never called `generate_outline` (content not persisted)
- `revise_content` called before `read_section` (writing blind)
- Agent called `delete_post` which isn't in the flow's tool list
- `generate_outline` called with empty string as content

#### Level 3: Response Quality

**Question:** Did the agent actually do the job correctly?

**Three dimensions:**
1. **Useful** — the agent took a meaningful action, not just acknowledged the request
2. **Trustworthy** — the agent followed the user's stated instructions, not its own interpretation
3. **Reliable** — running the same turn again produces structurally consistent results (opt-in, off by default)

**Implementation:**
- LLM-as-a-Judge using Opus (`claude-opus-4-6`) — a stronger model than the agent to avoid self-grading
- The judge receives: user utterance, rubric, agent response, tool call log, and disk state
- Judge scores useful + trustworthy as pass/fail with brief explanation
- Reliability (opt-in via `-m reliability`): run the same turn N=3 times, compare key outputs for structural consistency

**Rubric format:**
```json
"rubric": {
  "did_persist": "outline saved to disk with ## headings matching user's 4 requested sections",
  "did_follow_instructions": "exactly 4 sections, not 3 or 5; section titles reflect (a) (b) (c) (d)",
  "side_effects": "state.active_post is set to the created post_id"
}
```

**Judge prompt structure:**
```
You are evaluating a blog writing assistant. The user said:
  "{utterance}"

The expected behavior is:
  {rubric}

The agent responded with:
  "{agent_response}"

The agent called these tools:
  {tool_log}

The post on disk now contains:
  {disk_state}

Score each dimension (pass/fail + one-line explanation):
1. Useful: Did the agent take a real action (not just acknowledge)?
2. Trustworthy: Did the agent follow the user's stated goal exactly?
```

**Failure examples:**
- Agent said "Outline saved!" but disk has no outline content
- User asked for 4 sections, agent produced 5 (added an unrequested Introduction)
- Agent produced a vague summary instead of actually writing prose
- Agent ignored the specified topic and wrote about something else

### Report format

Each eval run produces a summary report:

```
═══ E2E Agent Eval Report ═══

Test cases: 32
Level 1 (Basic Functionality):  30/32 pass (93.8%)
Level 2 (Tool Trajectory):      28/32 pass (87.5%)
Level 3 (Response Quality):     25/32 pass (78.1%)

Failures:
  convo_003 T2: L1 FAIL — generate_outline returned _error: validation
  convo_007 T1: L2 FAIL — missing expected tool: read_metadata
  convo_012 T2: L3 FAIL — agent added 5 sections, user asked for 4
  ...
```

### Adding new test cases

1. Write the conversation in `test_cases.json` with user turns, labels, expected_tools, and rubric
2. Agent turns can be placeholder text — they're not used for evaluation
3. Each user turn needs: `labels` (intent, flow, dax), `expected_tools` (ordered domain tools), `rubric` (quality criteria)
4. Run `pytest utils/tests/e2e_agent_evals.py -v -k "conv_XXXX"` to test just the new case
5. If Level 1 passes but Level 3 fails, the issue is usually in the skill prompt or policy — not the test

---

## E2E Test Scenario

The E2E eval (`e2e_agent_evals.py`) uses a single grounded scenario: a blog post titled **"Synthetic Data Generation for Classification"**. The post is created, developed, and published across 14 sequential steps. Each step builds on the previous — earlier steps must pass for later ones to work.

### Post structure

The outline evolves through the first 4 steps:

**After step 2 (outline)** — 4 sections with bullets under Motivation only:
1. **Motivation** — labeling is slow and expensive; hit this problem building an intent classification chatbot
2. **Process** — (empty)
3. **Ideas** — (empty)
4. **Takeaways** — (empty)

**After step 3 (refine — add bullets)** — Process and Ideas now have bullet points:
1. **Motivation** — (unchanged)
2. **Process** — design scenarios, assign labels, generate conversations, review samples, denoise at scale
3. **Ideas** — using LLMs to generate examples, going in reverse from label to conversation, denoising after augmentation
4. **Takeaways** — (empty)

**After step 4 (refine — reorder)** — sections swapped and Ideas renamed:
1. **Motivation** — (unchanged)
2. **Breakthrough Ideas** — (formerly Ideas, moved up)
3. **Process** — (moved down)
4. **Takeaways** — (unchanged)

**After step 5 (compose)** — entire outline converted to prose.

Step 8 adds:
5. **Best Practices** — inserted after Process via AddFlow

### The 14-step lifecycle

| Step | Flow | DAX | Phase | What happens |
|------|------|-----|-------|--------------|
| 1 | create | {05A} | Build | Create the post with title |
| 2 | outline | {002} | Build | Generate 4-section outline (Motivation, Process, Ideas, Takeaways) |
| 3 | refine | {02B} | Build | Add bullets to Process (5) and Ideas (3) |
| 4 | refine | {02B} | Build | Reorder: swap Ideas before Process, rename to Breakthrough Ideas |
| 5 | compose | {003} | Write | Convert entire outline into prose |
| 6 | rework | {006} | Develop | Expand Motivation with richer chatbot story |
| 7 | simplify | {7BD} | Edit | Cut sentences from Breakthrough Ideas paragraph (creates snapshot) |
| 8 | add | {005} | Build | Add "Best Practices" section after Process (part 2 starts here) |
| 9 | polish | {3BD} | Edit | Tighten the opening paragraph of Motivation |
| 10 | inspect | {1BD} | Analyze | Report metrics (word count, sections, read time) |
| 11 | audit | {13A} | Analyze | Compare style against existing posts |
| 12 | brainstorm | {29A} | Research | Generate alternative angles for the topic |
| 13 | find | {001} | Research | Search for posts about data augmentation |
| 14 | release | {04A} | Ship | Publish to Substack |

### Flow scope rules

These distinctions are critical for correct eval assertions:

- **refine** — operates on outline bullets only (steps 3-4). Can add bullets, reorder sections, rename headings. Does NOT edit prose.
- **compose** — one-time conversion from bullets to prose (step 5). Converts the entire outline in one pass. Not for editing existing prose.
- **rework** — expands/restructures an entire section's prose (step 6). Changes substance and depth.
- **polish** — tightens a specific paragraph or sentence (step 7). Improves word choice without changing meaning.
- **simplify** — removes sentences or reduces complexity (step 9). Makes content shorter.
- **add** — inserts a new empty section at a specific position (step 8). Does not generate content.

### Deterministic post resolution

The `_build_resolved_context` method in `BasePolicy` pre-resolves post and section IDs before calling `llm_execute`. The LLM receives a "Resolved entities" block in the system prompt:

```
Resolved entities:
  post_id: 4c1b3412
  post_title: Synthetic Data Generation for Classification
  section_ids: [motivation, breakthrough-ideas, process, takeaways]
  target_section: motivation
```

This prevents the LLM from guessing IDs or passing titles where UUIDs are expected.

### Extending the scenario

To add a new flow to the lifecycle:
1. Add a step definition to the `STEPS` list in `e2e_agent_evals.py`
2. Add a `test_step_NN_flowname` method to `TestSyntheticDataPostE2E`
3. Ensure the step's utterance references the synthetic data post naturally
4. Update the skill prompt if the flow needs resolved-entity instructions
5. Update this table with the new step
