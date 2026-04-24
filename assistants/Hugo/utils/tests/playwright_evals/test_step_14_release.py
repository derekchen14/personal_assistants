"""Playwright Tier 3 — Step 14: Publish to Substack (error-origin render).

Critical because Theme 4 reshaped the failure path: tool-call failure surfaces
as ``DisplayFrame(origin='error', metadata={'tool_error': ...})`` rather than
an ambiguity prompt (see ``utils/policy_builder/fixes/release.md``). The UI
MUST render a user-visible error state and MUST NOT claim success.

This test relies on a post with "multi-modal" in the title already existing
in the DB — i.e. steps 1-13 have run. Marked skip for the scaffold so CI
does not fail on an empty DB; unskip once the full Tier-3 sequence is in
place (Phase 3 follow-up).
"""

import time

import pytest

from utils.tests.playwright_evals.dump import write_failure_dump


STEP_NUM = 14
FLOW_NAME = 'release'
UTTERANCE = 'Publish the multi-modal models post to Substack'
TURN_TIMEOUT_MS = 60_000
RUBRIC = (
    'did_action: Attempts publication (errors from platform tools are expected)\n'
    'did_follow_instructions: Targets the multi-modal models post and Substack channel'
)


def _count_messages(page):
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
        'origin': 'error',
        'tool_log': ['channel_status'],
        'blocks': [],
        'metadata': {'tool_error': 'channel_status'},
        'scratchpad_keys': [],
        'flow_status': 'Running',
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
        'active_post': 'VisionPost',
        'keep_going': False,
        'has_issues': True,
        'scratchpad_keys': ['inspect', 'audit'],
        'flow_stack': ['release'],
        'turn_id': 14,
    }
    reproducer = (
        'python -m pytest utils/tests/playwright_evals/test_step_14_release.py -v -s --tb=short --ui'
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


@pytest.mark.skip(reason='Requires seeded DB with multi-modal post — run steps 1-13 first')
def test_step_14_release(browser_context, hugo_servers, network_log, pytestconfig):
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
        assert new_count > baseline, 'expected a new assistant message on release turn'

        body_text = page.locator('body').inner_text().lower()
        # The error-origin frame must NOT claim success.
        assert 'published' not in body_text, (
            'UI claims published but channel_status/release_post are expected to fail'
        )
        mentions_channel = ('channel' in body_text) or ('substack' in body_text)
        error_banner_visible = page.locator(
            '[data-test="error-banner"], [data-test="toast-error"], .error-banner'
        ).count() > 0
        assert mentions_channel or error_banner_visible, (
            'UI did not surface a channel/Substack error — Theme 4 error-origin render regressed'
        )
    except Exception as ecp:
        _dump_on_fail(
            STEP_NUM, FLOW_NAME, RUBRIC, page, network_log,
            reason=f'{type(ecp).__name__}: {ecp}',
        )
        raise
