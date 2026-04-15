"""E2E agent evals — sequential story through Hugo's 14 basic flows.

The eval IS the test: a single post lifecycle from create → publish.
Each step builds on the previous one. Earlier steps must pass for later ones to work.

Levels:
  1. Basic Functionality — pipeline runs, no crashes, non-empty response
  2. Tool Trajectory — correct domain tools called in correct order
  3. Response Quality — LLM-as-Judge scores usefulness and trustworthiness

Run:
  pytest utils/tests/e2e_agent_evals.py -v -s --tb=short
  pytest utils/tests/e2e_agent_evals.py -v -s --tb=short --strict   # also check tool order
  pytest utils/tests/e2e_agent_evals.py -v -s --tb=short --verbose  # save report to disk
"""

import json
from datetime import datetime
from pathlib import Path

import pytest

llm = pytest.mark.llm

_COMPONENT_TOOLS = {'handle_ambiguity', 'coordinate_context', 'manage_memory', 'read_flow_stack'}
_TEST_POST_ID = 'TestPost'
_REPORT_DIR = Path(__file__).parent / 'reports'


def pytest_addoption(parser):
    parser.addoption('--strict', action='store_true', default=False,
                     help='Enforce tool call order in L2 checks')
    parser.addoption('--eval-verbose', action='store_true', default=False,
                     help='Log detailed step output and save report to disk')


# ── Step definitions ─────────────────────────────────────────────────

STEPS = [
    {
        'step': 1,
        'flow': 'create',
        'dax': '{05A}',
        'utterance': 'Create a new post about Using Multi-modal Models to Improve AI Agents',
        'expected_tools': ['create_post'],
        'rubric': {
            'did_action': 'Post created with title containing multi-modal models / AI agents',
            'did_follow_instructions': 'Post type is draft, title matches request',
        },
    },
    {
        'step': 2,
        'flow': 'outline',
        'dax': '{002}',
        'utterance': (
            'Make an outline with 4 sections: Motivation, Process, Ideas, '
            'and Takeaways. Under Motivation, add bullets about text-only agents '
            'missing visual context, and how we hit this problem building a '
            'screen-reading customer support agent.'
        ),
        'expected_tools': ['generate_outline'],
        'expected_block_type': 'card',
        'max_message_chars': 300,
        'rubric': {
            'did_action': '4 sections saved to disk with bullet points under Motivation',
            'did_follow_instructions': 'Sections are Motivation, Process, Ideas, Takeaways in that order',
        },
    },
    {
        'step': 3,
        'flow': 'refine',
        'dax': '{02B}',
        'utterance': (
            'Add bullets to the outline. Under Process, add: pick a vision encoder, '
            'wire it to the planner, fine-tune on UI traces, evaluate on held-out '
            'workflows, and ship behind a flag. Under Ideas, add: using video for '
            'temporal grounding, treating screenshots as a tool the agent can call, '
            'and falling back to text-only when latency budget is tight.'
        ),
        'expected_tools': ['read_metadata', 'generate_outline'],
        'rubric': {
            'did_action': 'Process and Ideas sections each have the requested bullets appended to (not replacing) any existing bullets',
            'did_follow_instructions': 'All 5 new Process bullets and all 3 new Ideas bullets are present; prior bullets are preserved',
        },
    },
    {
        'step': 4,
        'flow': 'refine',
        'dax': '{02B}',
        'utterance': (
            'Reorder the outline: move Ideas before Process, and rename it to '
            'Breakthrough Ideas. The final order should be Motivation, Breakthrough Ideas, '
            'Process, Takeaways.'
        ),
        'expected_tools': ['read_metadata', 'generate_outline'],
        'rubric': {
            'did_action': 'Sections reordered and Ideas renamed to Breakthrough Ideas',
            'did_follow_instructions': 'Order is Motivation, Breakthrough Ideas, Process, Takeaways',
        },
    },
    {
        'step': 5,
        'flow': 'compose',
        'dax': '{003}',
        'utterance': 'Convert the entire outline into prose',
        'expected_tools': ['convert_to_prose'],
        'rubric': {
            'did_action': 'Outline bullets converted to prose paragraphs across all sections',
            'did_follow_instructions': 'All sections now have prose content, not just bullets',
        },
    },
    {
        'step': 6,
        'flow': 'rework',
        'dax': '{006}',
        'utterance': (
            'Expand the Motivation section — flesh out the customer story about '
            'the screen-reading support agent and why text-only context kept failing'
        ),
        'expected_tools': ['read_section', 'revise_content'],
        'rubric': {
            'did_action': 'Prose expanded with richer detail',
            'did_follow_instructions': 'Expanded content includes the screen-reading agent story and the text-only context limitation',
        },
    },
    {
        'step': 7,
        'flow': 'simplify',
        'dax': '{7BD}',
        'utterance': 'The second paragraph of Breakthrough Ideas is too wordy. Cut a sentence or two.',
        'expected_tools': ['read_section', 'revise_content'],
        'rubric': {
            'did_action': 'Shorter, cleaner paragraph',
            'did_follow_instructions': 'Second paragraph reduced in length',
        },
    },
    {
        'step': 8,
        'flow': 'add',
        'dax': '{005}',
        'utterance': 'Add a new section called Best Practices after Process',
        'expected_tools': ['insert_section'],
        'rubric': {
            'did_action': 'New section added to the post',
            'did_follow_instructions': 'Section titled Best Practices inserted after Process',
        },
    },
    {
        'step': 9,
        'flow': 'polish',
        'dax': '{3BD}',
        'utterance': 'Tighten the opening paragraph of the Motivation section — make it punchier',
        'expected_tools': ['read_section'],
        'rubric': {
            'did_action': 'Paragraph improved, meaning preserved',
            'did_follow_instructions': 'Opening paragraph is shorter and more impactful',
        },
    },
    {
        'step': 10,
        'flow': 'inspect',
        'dax': '{1BD}',
        'utterance': 'What are the metrics on the multi-modal models post?',
        'expected_tools': ['inspect_post'],
        'rubric': {
            'did_action': 'Reports word count, section count, read time',
            'did_follow_instructions': 'Metrics are for the multi-modal models post',
        },
    },
    {
        'step': 11,
        'flow': 'audit',
        'dax': '{13A}',
        'utterance': 'Check if the multi-modal models post matches my usual writing style',
        'expected_tools': ['find_posts', 'compare_style'],
        'rubric': {
            'did_action': 'Produces a style consistency report',
            'did_follow_instructions': 'Compares against existing posts',
        },
    },
    {
        'step': 12,
        'flow': 'brainstorm',
        'dax': '{29A}',
        'utterance': 'Brainstorm some alternative angles for the multi-modal models topic',
        'expected_tools': ['brainstorm_ideas'],
        'rubric': {
            'did_action': 'Generates multiple creative angles',
            'did_follow_instructions': 'Angles relate to multi-modal models for AI agents',
        },
    },
    {
        'step': 13,
        'flow': 'find',
        'dax': '{001}',
        'utterance': 'Search for posts about data augmentation',
        'expected_tools': ['find_posts'],
        'rubric': {
            'did_action': 'Returns search results',
            'did_follow_instructions': 'Results relate to data augmentation',
        },
    },
    {
        'step': 14,
        'flow': 'release',
        'dax': '{04A}',
        'utterance': 'Publish the multi-modal models post to Substack',
        'expected_tools': ['channel_status'],
        'expected_errors': {'channel_status', 'release_post'},
        'expected_ambiguity': {'channel_unavailable'},
        'rubric': {
            'did_action': 'Attempts publication (errors from platform tools are expected)',
            'did_follow_instructions': 'Targets the multi-modal models post and Substack channel',
        },
    },
]


# Propose/select sub-steps for the outline flow. These run between
# test_step_01_create and test_step_02_outline; the direct step at
# STEPS[1] then overwrites with the canonical Motivation/Process/
# Ideas/Takeaways sections that later steps reference.
OUTLINE_SUBSTEPS = [
    {
        'step': '02a',
        'flow': 'outline',
        'dax': '{002}',
        'utterance': 'Make an outline — propose a few options I can pick from',
        # Propose mode: the policy pre-resolves the active post (read_metadata)
        # and the skill MAY call find_posts once to vary angles, but MUST NOT
        # call generate_outline. No other tools allowed.
        'expected_tools': ['read_metadata'],
        'expected_block_type': 'selection',
        'max_message_chars': 300,
        'rubric': {
            'did_action': 'Generated multiple outline options without saving to disk',
            'did_follow_instructions': 'Offered options for the user to pick between',
        },
    },
    {
        'step': '02b',
        'flow': 'outline',
        'dax': '{002}',
        'utterance': "Let's go with Option 2",
        'expected_tools': ['generate_outline'],
        'expected_block_type': 'card',
        'rubric': {
            'did_action': "Persisted the selected option's sections to disk",
            'did_follow_instructions': "Saved Option 2's sections, not Option 1 or Option 3",
        },
    },
]


# ── Tool logging ──────────────────────────────────────────────────────

def _install_tool_logger(agent):
    """Monkey-patch pex._dispatch_tool to capture all tool calls."""
    log = []
    original = agent.pex._dispatch_tool

    def logging_dispatch(tool_name, tool_input):
        result = original(tool_name, tool_input)
        log.append({
            'tool': tool_name,
            'input': {k: (v[:200] if isinstance(v, str) and len(v) > 200 else v)
                      for k, v in tool_input.items()},
            'success': result.get('_success'),
            'error': result.get('_error'),
        })
        return result

    agent.pex._dispatch_tool = logging_dispatch
    return log


def _domain_tools(tool_log):
    """Extract ordered domain tool names, filtering out component tools."""
    return [tc['tool'] for tc in tool_log if tc['tool'] not in _COMPONENT_TOOLS]


# ── Level 1: Basic Functionality ──────────────────────────────────────

def _check_level1(step_def, result, tool_log, agent):
    """Returns list of issue strings. Empty = pass.

    Checks:
      - The active flow matches step_def['flow'] (or it was completed this turn).
      - The frame has the expected block_type.
      - state.has_issues is False and no ambiguity is present (unless the step expects one).
      - Message length, fallback phrases, tool errors.
    """
    issues = []
    expected_errors = step_def.get('expected_errors') or set()
    expected_bt = step_def.get('expected_block_type')
    expected_flow = step_def.get('flow')
    max_chars = step_def.get('max_message_chars')

    message = result.get('message', '')
    frame = result.get('frame') or {}
    blocks = frame.get('blocks') or []
    block_types = [b.get('type') for b in blocks]
    merged_data = {}
    for b in blocks:
        bd = b.get('data') or {}
        if isinstance(bd, dict):
            merged_data.update(bd)
    frame_content = merged_data.get('content', '')

    # Active-flow check: either still on the stack, or it just completed this turn.
    active_flow = agent.world.flow_stack.get_flow()
    state = agent.world.current_state()
    flow_name = active_flow.name() if active_flow else state.flow_name
    if expected_flow and flow_name != expected_flow:
        issues.append(f'expected active flow={expected_flow}, got {flow_name}')

    # State invariants after the turn.
    expected_amb = step_def.get('expected_ambiguity') or set()
    if state.has_issues and not expected_amb:
        issues.append('state.has_issues is True — policy or verifier flagged a problem')
    if agent.ambiguity.present():
        amb_label = (agent.ambiguity.metadata or {}).get('reason') or agent.ambiguity.level
        if amb_label not in expected_amb:
            issues.append(f'unexpected ambiguity: {amb_label!r}')

    # For block-expecting steps, the payload must live in frame.blocks, not the chat utterance.
    if expected_bt in ('card', 'selection', 'list', 'compare', 'form', 'confirmation', 'toast'):
        if not blocks:
            issues.append(f'empty {expected_bt} — no blocks in frame')
    else:
        content = frame_content or message
        has_block_data = any(v for k, v in merged_data.items() if k not in ('content',) and v)
        if (not content or len(content) < 10) and not has_block_data:
            issues.append('empty response')

    if expected_bt:
        if expected_bt not in block_types:
            issues.append(f'expected block_type={expected_bt}, got {block_types}')

    if max_chars and len(message) > max_chars:
        issues.append(f'message too long ({len(message)} > {max_chars} chars) — should be in block data, not utterance')

    fallback_phrases = [
        "I'm having trouble understanding",
        'Could you try rephrasing',
        'Could not find',
    ]
    combined = frame_content or message
    for phrase in fallback_phrases:
        if phrase in combined:
            issues.append(f'fallback response: "{phrase}"')
            break

    failed_tools = [tc for tc in tool_log
                    if not tc['success'] and tc['tool'] not in _COMPONENT_TOOLS
                    and tc['tool'] not in expected_errors]
    for tc in failed_tools:
        issues.append(f'tool error: {tc["tool"]} -> {tc["error"]}')

    return issues


# ── Level 2: Tool Trajectory ─────────────────────────────────────────

def _check_level2(tool_log, expected_tools, strict=False):
    """Check domain tools match expected. Returns issues.

    expected_tools == []:  no domain tools are allowed (used for Converse-style
                           flows that do no external work).
    expected_tools == [..]: each tool must appear at least once; under --strict
                           they must appear in order as a subsequence.
    """
    issues = []
    actual = _domain_tools(tool_log)

    if not expected_tools:
        if actual:
            issues.append(f'expected no domain tools, got {actual}')
        return issues

    if strict:
        search_from = 0
        for exp in expected_tools:
            found = False
            for idx in range(search_from, len(actual)):
                if actual[idx] == exp:
                    search_from = idx + 1
                    found = True
                    break
            if not found:
                issues.append(f'missing expected tool (strict order): {exp}')
    else:
        actual_set = set(actual)
        for exp in expected_tools:
            if exp not in actual_set:
                issues.append(f'missing expected tool: {exp}')

    return issues


# ── Level 3: Response Quality (LLM-as-Judge) ─────────────────────────

def _check_level3(utterance, rubric, result, tool_log, agent):
    """Use Opus as judge. Returns issues list."""
    issues = []

    if not rubric:
        return issues

    message = result.get('message', '')
    frame = result.get('frame') or {}
    merged = {}
    for b in (frame.get('blocks') or []):
        bd = b.get('data') or {}
        if isinstance(bd, dict):
            merged.update(bd)
    frame_content = merged.get('content', '')
    content = frame_content or message

    tool_summary = '\n'.join(
        f'  {tc["tool"]}({_compact_input(tc["input"])}) -> success={tc["success"]}'
        for tc in tool_log if tc['tool'] not in _COMPONENT_TOOLS
    )

    rubric_text = '\n'.join(f'  - {key}: {val}' for key, val in rubric.items())

    judge_prompt = (
        f'You are evaluating a blog writing assistant called Hugo.\n\n'
        f'The user said:\n  "{utterance}"\n\n'
        f'The expected behavior is:\n{rubric_text}\n\n'
        f'The agent responded with:\n  "{content}"\n\n'
        f'The agent called these tools:\n{tool_summary}\n\n'
        f'Score each dimension. Reply ONLY with this exact format:\n'
        f'useful: pass OR fail — one line explanation\n'
        f'trustworthy: pass OR fail — one line explanation\n'
    )

    judge_system = (
        'You are an evaluator primarily focused on OUTCOMES, rather than process. '
        'Judge whether the agent achieved the correct result.\n'
        '- A tool succeeding means the action was taken — even if the displayed '
        'response is a summary rather than the full content.\n'
        '- "useful" = the agent took a real action that moved the task forward.\n'
        '- "trustworthy" = the final result matches what the user asked for.\n'
        'Be lenient on presentation; be strict on whether the right data was '
        'persisted via tool calls.'
    )

    try:
        judge_response = agent.engineer.call(
            judge_prompt,
            system=judge_system,
            model='opus',
            max_tokens=256,
        )

        for line in judge_response.strip().split('\n'):
            line = line.strip().lower()
            # Match "fail" as verdict, not as substring (e.g. "failure modes")
            if line.startswith('useful:'):
                verdict = line.split('—')[0] if '—' in line else line.split('-')[0]
                if 'fail' in verdict:
                    issues.append(f'L3 useful: {line}')
            elif line.startswith('trustworthy:'):
                verdict = line.split('—')[0] if '—' in line else line.split('-')[0]
                if 'fail' in verdict:
                    issues.append(f'L3 trustworthy: {line}')
    except Exception as ecp:
        issues.append(f'L3 judge error: {type(ecp).__name__}: {ecp}')

    return issues


def _compact_input(input_dict):
    """Compact tool input for display."""
    parts = []
    for key, val in input_dict.items():
        if isinstance(val, str) and len(val) > 60:
            val = val[:57] + '...'
        parts.append(f'{key}={val!r}')
    return ', '.join(parts)


# ═══════════════════════════════════════════════════════════════════
# Sequential E2E test class
# ═══════════════════════════════════════════════════════════════════

@llm
class TestSyntheticDataPostE2E:
    """E2E eval: 14-step lifecycle of a single blog post.

    Steps run in definition order. Each builds on the previous.
    State persists via the agent's conversation context and active_post.
    """

    _agent = None
    _post_id = None
    _strict = False
    _verbose = False
    _report_lines = []

    @classmethod
    def _get_agent(cls):
        """Lazy-init a module-level agent that persists across all steps."""
        if cls._agent is None:
            from schemas.config import load_config
            from backend.agent import Agent
            import backend.agent as agent_mod
            orig_load = agent_mod.load_config
            agent_mod.load_config = lambda: load_config(overrides={'debug': True})
            cls._agent = Agent(username='test_user')
            agent_mod.load_config = orig_load
        return cls._agent

    @classmethod
    def _seed_part2_context(cls):
        """Seed agent state for part 2 (steps 8-14) from the disk snapshot.

        Finds the test post on disk, sets active_post, and injects synthetic
        conversation history so the LLM has context about prior work.
        """
        agent = cls._get_agent()
        from backend.utilities.services import PostService
        svc = PostService()
        meta = svc.read_metadata(_TEST_POST_ID)
        if not meta.get('_success'):
            return
        cls._post_id = _TEST_POST_ID

        # Ensure a state exists with active_post set
        from backend.components.dialogue_state import DialogueState
        state = agent.world.current_state()
        if not state:
            state = DialogueState(agent.config)
            agent.world.insert_state(state)
        state.active_post = _TEST_POST_ID

        title = meta.get('title', 'Using Multi-modal Models to Improve AI Agents')
        sections = meta.get('section_ids', [])

        context = agent.world.context
        context.add_turn('User', f'Create a new post about {title}')
        context.add_turn('Agent', f'Created draft "{title}" with post ID {_TEST_POST_ID}.')
        context.add_turn('User', 'Generate an outline and convert it to prose.')
        context.add_turn('Agent', (
            f'Done. The post has {len(sections)} sections: {", ".join(sections)}. '
            f'All sections have been composed into prose, expanded, and simplified.'
        ))

    @classmethod
    def teardown_class(cls):
        """Close the agent. Post is left on disk for part 2 reruns."""
        if cls._verbose and cls._report_lines:
            _REPORT_DIR.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            path = _REPORT_DIR / f'e2e_report_{stamp}.txt'
            path.write_text('\n'.join(cls._report_lines), encoding='utf-8')
            print(f'\n  Report saved to {path}')
        if cls._agent:
            cls._agent.close()
            cls._agent = None

    def _log(self, msg):
        """Log a message to console (if verbose) and report buffer."""
        self._report_lines.append(msg)
        if self._verbose:
            print(f'    [log] {msg}')

    def _run_step(self, step_def, request):
        """Execute one step and evaluate all three levels."""
        self._strict = request.config.getoption('--strict', default=False)
        self._verbose = request.config.getoption('--eval-verbose', default=False)

        agent = self._get_agent()
        tool_log = _install_tool_logger(agent)

        result = agent.take_turn(step_def['utterance'], dax=step_def['dax'])
        state = agent.world.current_state()

        # Capture post_id from create step
        if step_def['flow'] == 'create' and state and state.active_post:
            TestSyntheticDataPostE2E._post_id = state.active_post

        self._log(f'Step {step_def["step"]} [{step_def["flow"]}] — tools: {_domain_tools(tool_log)}')

        l1_issues = _check_level1(step_def, result, tool_log, agent)
        l2_issues = (
            _check_level2(tool_log, step_def['expected_tools'], strict=self._strict)
            if not l1_issues else ['skipped (L1 failed)']
        )

        if not l1_issues and not l2_issues and step_def.get('rubric'):
            l3_issues = _check_level3(
                step_def['utterance'], step_def['rubric'],
                result, tool_log, agent,
            )
        elif step_def.get('rubric'):
            l3_issues = ['skipped (L1 or L2 failed)']
        else:
            l3_issues = []

        for issue in l1_issues + l2_issues + l3_issues:
            self._log(f'  issue: {issue}')

        return {
            'step': step_def['step'],
            'flow': step_def['flow'],
            'l1_pass': not l1_issues,
            'l1_issues': l1_issues,
            'l2_pass': not l2_issues,
            'l2_issues': l2_issues,
            'l3_pass': not l3_issues,
            'l3_issues': l3_issues,
            'domain_tools': _domain_tools(tool_log),
        }

    def _assert_step(self, step_def, request):
        """Run and assert a single step, printing diagnostics."""
        res = self._run_step(step_def, request)
        step = step_def['step']
        flow = step_def['flow']

        print(f"\n  Step {step} [{flow}]:")
        print(f"    domain tools: {res['domain_tools']}")
        print(f"    L1 (functionality): {'PASS' if res['l1_pass'] else 'FAIL ' + str(res['l1_issues'])}")
        print(f"    L2 (trajectory):    {'PASS' if res['l2_pass'] else 'FAIL ' + str(res['l2_issues'])}")
        print(f"    L3 (quality):       {'PASS' if res['l3_pass'] else 'FAIL ' + str(res['l3_issues'])}")

        failures = []
        if not res['l1_pass']:
            failures.append(f'L1 FAIL — {"; ".join(res["l1_issues"])}')
        if not res['l2_pass'] and 'skipped' not in str(res['l2_issues']):
            failures.append(f'L2 FAIL — {"; ".join(res["l2_issues"])}')
        if not res['l3_pass'] and 'skipped' not in str(res['l3_issues']):
            failures.append(f'L3 FAIL — {"; ".join(res["l3_issues"])}')

        if failures:
            pytest.fail(f"Step {step} [{flow}]: " + "; ".join(failures))

        return res

    # ── Individual test steps (run in definition order) ──────────────

    def test_step_01_create(self, request):
        """Delete any leftover test post before creating fresh."""
        from backend.utilities.services import PostService
        svc = PostService()
        svc.delete_post(_TEST_POST_ID)  # no-op if not found

        # Patch uuid generation so create_post uses our deterministic ID
        import uuid
        orig_uuid4 = uuid.uuid4
        uuid.uuid4 = lambda: type('', (), {'__str__': lambda s: _TEST_POST_ID + '-0000-0000'})()
        try:
            self._assert_step(STEPS[0], request)
        finally:
            uuid.uuid4 = orig_uuid4

    def test_step_02a_outline_propose(self, request):
        """Propose mode: 3 options rendered in the card, nothing persisted."""
        self._assert_step(OUTLINE_SUBSTEPS[0], request)

    def test_step_02b_outline_select(self, request):
        """Select mode: user picks Option 2, sections saved to disk."""
        self._assert_step(OUTLINE_SUBSTEPS[1], request)

    def test_step_02_outline(self, request):
        """Direct mode: explicit sections overwrite the selected outline."""
        self._assert_step(STEPS[1], request)

    def test_step_03_refine_bullets(self, request):
        self._assert_step(STEPS[2], request)

    def test_step_04_refine_reorder(self, request):
        self._assert_step(STEPS[3], request)

    def test_step_05_compose(self, request):
        self._assert_step(STEPS[4], request)

    def test_step_06_rework(self, request):
        self._assert_step(STEPS[5], request)

    def test_step_07_simplify(self, request):
        self._assert_step(STEPS[6], request)

    def test_step_08_add_section(self, request):
        """Part 2 starts here. Seeds context if no prior steps ran."""
        if not self._post_id:
            self._seed_part2_context()
        self._assert_step(STEPS[7], request)

    def test_step_09_polish(self, request):
        self._assert_step(STEPS[8], request)

    def test_step_10_inspect(self, request):
        self._assert_step(STEPS[9], request)

    def test_step_11_audit(self, request):
        self._assert_step(STEPS[10], request)

    def test_step_12_brainstorm(self, request):
        self._assert_step(STEPS[11], request)

    def test_step_13_find(self, request):
        self._assert_step(STEPS[12], request)

    def test_step_14_release(self, request):
        """Reset post status to draft before attempting release."""
        from backend.utilities.services import PostService
        svc = PostService()
        svc.update_post(_TEST_POST_ID, {'status': 'draft'})
        self._assert_step(STEPS[13], request)


# ═══════════════════════════════════════════════════════════════════
# Report (called via conftest or manually)
# ═══════════════════════════════════════════════════════════════════

def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Print summary after all tests."""
    reports = terminalreporter.stats.get('passed', []) + terminalreporter.stats.get('failed', [])
    step_reports = [r for r in reports if 'test_step_' in r.nodeid]
    if not step_reports:
        return

    total = len(STEPS)
    passed = len([r for r in step_reports if r.passed])
    failed = len([r for r in step_reports if r.failed])

    terminalreporter.write_line('')
    terminalreporter.write_line('═' * 50)
    terminalreporter.write_line(' E2E Agent Eval Report')
    terminalreporter.write_line('═' * 50)
    terminalreporter.write_line(f' Steps: {total}')
    terminalreporter.write_line(f' Passed: {passed}/{total}')
    terminalreporter.write_line(f' Failed: {failed}/{total}')

    for report in step_reports:
        if report.failed:
            step_name = report.nodeid.split('::')[-1]
            terminalreporter.write_line(f'  FAIL: {step_name}')
            if report.longreprtext:
                for line in report.longreprtext.split('\n')[:3]:
                    terminalreporter.write_line(f'    {line.strip()}')

    terminalreporter.write_line('═' * 50)
