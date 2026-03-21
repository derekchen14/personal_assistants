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
# Unit tests (no API keys, no LLM)
pytest utils/tests/unit_tests.py -v

# Model tests (real LLM, NLU-only)
pytest utils/tests/model_tests.py -m llm -v

# E2E agent evals (real LLM, real tools, full pipeline)
pytest utils/tests/e2e_agent_evals.py -v --tb=short

# E2E with reliability checks (runs each turn 3x, slower)
pytest utils/tests/e2e_agent_evals.py -v -m reliability
```

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

| File | Purpose |
|------|---------|
| `unit_tests.py` | Pure code logic — mocked LLM, no API keys needed |
| `model_tests.py` | NLU accuracy — flow detection, confidence calibration, requires real LLM |
| `e2e_agent_evals.py` | Full pipeline — real LLM + real tools, 3-level evaluation, produces report |
| `test_cases.json` | Shared test data — conversations with labels, expected_tools, and rubrics |
| `conftest.py` | Fixtures — `agent` (real LLM), `mock_agent` (stubbed for unit routing) |

---

## Unit Tests

**File:** `unit_tests.py`
**Requires:** No API keys, no LLM calls
**Fixture:** `tmp_db` (temporary database directory, patched via monkeypatch)

Unit tests verify pure code logic with no external dependencies. The LLM is either mocked or bypassed entirely. These run fast (<1s) and catch regressions in deterministic code.

### What they cover

**PromptEngineer internals:**
- `TestResolveModel` — model ID resolution for each provider/tier
- `TestCallDispatch` — routing to Claude, Gemini, OpenAI based on provider
- `TestTallyVotes` — ensemble voting tallies from multiple NLU voters
- `TestDetectFlow` — flow detection with mocked voter responses
- `TestEnsembleConfig` — config validation (voters have family + model fields)

**NLU react() path:**
- `TestReactActionTurn` — gold DAX parsing creates correct flow with slots
- `TestReactMultiSlot` — comma-separated slot values parsed correctly
- `TestReactUtteranceTurn` — utterance turns fill slots via LLM (mocked)
- `TestReactEdgeCases` — fill_slot_values, DAX code resolution edge cases

**Service layer (real code, temporary database):**
- `TestOptionCReturnFormat` — `_success` / `_error` return envelope format
- `TestPostService` — find_posts, search_notes, read_metadata, read_section, create_post, update_post, delete_post, summarize_text, rollback_post
- `TestContentService` — generate_outline, convert_to_prose, insert_section, insert_content, revise_content, write_text, find_and_replace, remove_content, cut_and_paste, diff_section
- `TestAnalysisService` — brainstorm_ideas, inspect_post, check_readability, check_links, compare_style, editor_review, analyze_seo
- `TestPlatformService` — list_channels, channel_status, publisher connections
- `TestSnapshotInfra` — snapshot creation, rotation, version reading

### How they work

Each service test uses the `tmp_db` fixture which:
1. Creates a temporary directory structure (content/drafts, content/notes, content/posts, .snapshots, guides)
2. Writes a minimal `metadata.json`
3. Monkeypatches `_DB_DIR` in `backend.utilities.services` so all ToolService instances use the temp path
4. Service instances created within tests automatically pick up the patched paths via `__init__`

### What they do NOT cover

- Real LLM responses (all LLM calls are mocked or bypassed)
- End-to-end pipeline integration (NLU → PEX → RES)
- Tool-use loops (policy → tool dispatch → persistence)
- Response quality or template formatting

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
