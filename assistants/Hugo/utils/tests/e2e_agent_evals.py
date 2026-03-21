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
        'utterance': 'Create a new post about Synthetic Data Generation for Classification',
        'expected_tools': ['create_post'],
        'rubric': {
            'did_action': 'Post created with title containing synthetic data',
            'did_follow_instructions': 'Post type is draft, title matches request',
        },
    },
    {
        'step': 2,
        'flow': 'outline',
        'dax': '{002}',
        'utterance': (
            'Make an outline with 4 sections: Motivation, Process, Ideas, '
            'and Takeaways. Under Motivation, add bullets about labeling being slow and '
            'expensive, and how we hit this problem building an intent classification chatbot.'
        ),
        'expected_tools': ['generate_outline'],
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
            'Add bullets to the outline. Under Process, add: design scenarios, assign labels, '
            'generate conversations, review samples, and denoise at scale. Under Ideas, add: '
            'using LLMs to generate examples, going in reverse from label to conversation, '
            'and denoising after augmentation.'
        ),
        'expected_tools': ['read_metadata', 'generate_outline'],
        'rubric': {
            'did_action': 'Process and Ideas sections updated with bullet points',
            'did_follow_instructions': 'Process has 5 bullets, Ideas has 3 bullets',
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
            'the intent classification chatbot and why manual labeling hit a wall'
        ),
        'expected_tools': ['read_section', 'revise_content'],
        'rubric': {
            'did_action': 'Prose expanded with richer detail',
            'did_follow_instructions': 'Expanded content includes chatbot story and labeling bottleneck',
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
        'utterance': 'What are the metrics on the synthetic data post?',
        'expected_tools': ['inspect_post'],
        'rubric': {
            'did_action': 'Reports word count, section count, read time',
            'did_follow_instructions': 'Metrics are for the synthetic data post',
        },
    },
    {
        'step': 11,
        'flow': 'audit',
        'dax': '{13A}',
        'utterance': 'Check if the synthetic data post matches my usual writing style',
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
        'utterance': 'Brainstorm some alternative angles for the synthetic data topic',
        'expected_tools': ['brainstorm_ideas'],
        'rubric': {
            'did_action': 'Generates multiple creative angles',
            'did_follow_instructions': 'Angles relate to synthetic data',
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
        'utterance': 'Publish the synthetic data post to Substack',
        'expected_tools': [],
        'expected_errors': {'channel_status', 'release_post'},
        'rubric': {
            'did_action': 'Attempts publication (errors from platform tools are expected)',
            'did_follow_instructions': 'Targets the synthetic data post and Substack channel',
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

def _check_level1(result, tool_log, expected_errors=None):
    """Returns list of issue strings. Empty = pass."""
    issues = []
    expected_errors = expected_errors or set()

    message = result.get('message', '')
    frame = result.get('frame') or {}
    frame_data = frame.get('data', {})
    frame_content = frame_data.get('content', '')
    content = frame_content or message

    # Frame with structured data (e.g. create returns title/post_id) counts as valid
    has_frame_data = any(v for k, v in frame_data.items() if k != 'content' and v)

    if not content or len(content) < 10:
        if not has_frame_data:
            issues.append('empty response')

    fallback_phrases = [
        "I'm having trouble understanding",
        'Could you try rephrasing',
        'Could not find',
    ]
    for phrase in fallback_phrases:
        if phrase in content:
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

    Default: each expected tool must appear at least once (any order).
    Strict:  expected tools must appear as an ordered subsequence.
    """
    issues = []
    actual = _domain_tools(tool_log)

    if not expected_tools:
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
    frame_content = frame.get('data', {}).get('content', '')
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
        f'The agent responded with:\n  "{content[:1000]}"\n\n'
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

        title = meta.get('title', 'Synthetic Data Generation for Classification')
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

        expected_errors = step_def.get('expected_errors', set())
        l1_issues = _check_level1(result, tool_log, expected_errors)
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

    def test_step_02_outline(self, request):
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
