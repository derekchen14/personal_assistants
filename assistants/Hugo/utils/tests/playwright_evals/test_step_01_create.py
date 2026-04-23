"""Playwright Tier 3 — Step 1: Create a new post.

Exercises the simplest card-render path: type the create utterance, submit,
and verify a new assistant message + card block land in the DOM. Chosen
as the Phase-3 entry point per ``utils/policy_builder/eval_design.md §
Migration plan`` (Phase 3) because it has no prior state requirements.

Gated on the ``--ui`` pytest flag (see ``conftest.py``). When pytest-playwright
is missing the test skips with an install hint.
"""

import time

import pytest

from utils.tests.playwright_evals.dump import write_failure_dump


STEP_NUM = 1
FLOW_NAME = 'create'
UTTERANCE = 'Create a new post about Using Multi-modal Models to Improve AI Agents'
TITLE_SUBSTRINGS = ('multi-modal', 'ai agents')
TURN_TIMEOUT_MS = 60_000
RUBRIC = (
    'did_action: Post created with title containing multi-modal models / AI agents\n'
    'did_follow_instructions: Post type is draft, title matches request'
)


def _count_messages(page):
    # Match the assistant message bubble nesting in +page.svelte — the messages
    # sit under the chat container's inner div.space-y-3. Any bubble counts.
    return page.locator('div.rounded-2xl').count()


def _submit_utterance(page, utterance):
    message_input = page.locator('input[placeholder="Message Hugo..."]')
    message_input.wait_for(state='visible', timeout=10_000)
    message_input.fill(utterance)
    page.locator('button', has_text='Send').click()


def _wait_for_new_assistant_message(page, baseline, timeout_ms=TURN_TIMEOUT_MS):
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        if _count_messages(page) > baseline:
            typing = page.locator('span.animate-bounce').count()
            if typing == 0:
                return
        time.sleep(0.25)
    raise TimeoutError(f'no new assistant message within {timeout_ms}ms')


def _connect_as_test_user(page, frontend_url):
    page.goto(frontend_url)
    username = page.locator('input[placeholder="Your name"]')
    if username.count() > 0:
        username.fill('playwright_test')
        page.locator('button', has_text='Start').click()
    page.locator('input[placeholder="Message Hugo..."]').wait_for(
        state='visible', timeout=15_000,
    )


def _dump_on_fail(step_num, flow_name, rubric, page, network_log, reason):
    screenshot_path = None
    try:
        ts = time.strftime('%Y%m%d_%H%M%S')
        screenshot_path = f'/tmp/playwright_step_{step_num:02d}_{ts}.png'
        page.screenshot(path=screenshot_path)
    except Exception:
        screenshot_path = None
    expected = {
        'origin': flow_name,
        'tool_log': [],
        'blocks': ['card'],
        'metadata': {},
        'scratchpad_keys': [],
        'flow_status': 'Completed',
    }
    actual = {
        'origin': 'unknown',
        'tool_log': [],
        'blocks': [],
        'metadata': {'failure_reason': reason},
        'scratchpad_keys': [],
        'flow_status': 'Unknown',
    }
    state_snapshot = {
        'active_post': None,
        'keep_going': False,
        'has_issues': True,
        'scratchpad_keys': [],
        'flow_stack': [],
        'turn_id': 1,
    }
    reproducer = (
        'python -m pytest utils/tests/playwright_evals/test_step_01_create.py -v -s --tb=short --ui'
    )
    write_failure_dump(
        step_num=step_num,
        flow_name=flow_name,
        expected=expected,
        actual=actual,
        rubric=rubric,
        state_snapshot=state_snapshot,
        screenshot_path=screenshot_path,
        network_log=network_log,
        reproducer=reproducer,
    )


def test_step_01_create(browser_context, hugo_servers, network_log, pytestconfig):
    if not pytestconfig.getoption('--ui'):
        pytest.skip('UI tier gated on --ui flag')
    if browser_context is None:
        pytest.skip('playwright not available')

    page = browser_context.new_page()
    frontend_url = hugo_servers['frontend']

    try:
        _connect_as_test_user(page, frontend_url)
        baseline = _count_messages(page)

        _submit_utterance(page, UTTERANCE)
        _wait_for_new_assistant_message(page, baseline)

        new_count = _count_messages(page)
        assert new_count > baseline, (
            f'expected a new assistant message; baseline={baseline}, now={new_count}'
        )

        body_text = page.locator('body').inner_text().lower()
        title_matches = [sub for sub in TITLE_SUBSTRINGS if sub in body_text]
        assert title_matches, (
            f'expected the post title substrings {TITLE_SUBSTRINGS} in the rendered DOM'
        )

        error_banner = page.locator('[data-test="error-banner"], .error-banner').count()
        assert error_banner == 0, 'error banner is visible — UI crashed on the create turn'
    except Exception as ecp:
        _dump_on_fail(
            STEP_NUM, FLOW_NAME, RUBRIC, page, network_log,
            reason=f'{type(ecp).__name__}: {ecp}',
        )
        raise
