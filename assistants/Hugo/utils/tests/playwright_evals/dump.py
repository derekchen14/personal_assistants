"""Failure-dump writer shared by CLI and Playwright eval tiers.

Every failed assertion in any tier writes a Markdown dump to
``utils/policy_builder/failures/<run_id>/step_<N>.md``. The schema is fixed
by ``utils/policy_builder/eval_design.md § Failure-dump format`` so that a
fresh Claude Code session can parse it without conversation context.

This module MUST NOT import Playwright — the CLI harness calls it too.
"""

import os
from datetime import datetime
from pathlib import Path


_FAILURES_ROOT = Path(__file__).resolve().parents[2] / 'policy_builder' / 'failures'

_SECTIONS = (
    'Expected',
    'Actual',
    'Diff',
    'State snapshot',
    'Rubric',
    'Reproducer',
)


def _new_run_id():
    return datetime.now().strftime('%Y%m%d_%H%M%S')


def _fmt_line(label, value):
    return f'- {label}: {value}'


def _fmt_expected_actual(section):
    origin = section.get('origin', '')
    tool_log = section.get('tool_log', [])
    blocks = section.get('blocks', [])
    metadata = section.get('metadata', {})
    scratchpad_keys = section.get('scratchpad_keys', [])
    flow_status = section.get('flow_status', '')
    meta_keys = list(metadata.keys()) if isinstance(metadata, dict) else metadata
    lines = [
        _fmt_line('origin', origin),
        _fmt_line('tool_log', list(tool_log)),
        _fmt_line('blocks', list(blocks)),
        _fmt_line('metadata', meta_keys),
        _fmt_line('scratchpad_keys', list(scratchpad_keys)),
        _fmt_line('flow_status', flow_status),
    ]
    return '\n'.join(lines)


def _fmt_diff(expected, actual):
    keys = ['origin', 'tool_log', 'blocks', 'metadata', 'scratchpad_keys', 'flow_status']
    rows = []
    for key in keys:
        exp = expected.get(key)
        act = actual.get(key)
        if key == 'metadata' and isinstance(exp, dict) and isinstance(act, dict):
            exp_disp = sorted(exp.keys())
            act_disp = sorted(act.keys())
        else:
            exp_disp = exp
            act_disp = act
        if exp_disp != act_disp:
            rows.append(f'- {key}: expected={exp_disp!r} actual={act_disp!r}')
    if not rows:
        rows.append('- (no field-level diffs detected; see Expected/Actual)')
    return '\n'.join(rows)


def _fmt_state(snapshot):
    active_post = snapshot.get('active_post')
    keep_going = snapshot.get('keep_going', False)
    has_issues = snapshot.get('has_issues', False)
    scratchpad_keys = snapshot.get('scratchpad_keys', [])
    flow_stack = snapshot.get('flow_stack', [])
    turn_id = snapshot.get('turn_id', 0)
    lines = [
        _fmt_line('active_post', active_post),
        _fmt_line('keep_going', keep_going),
        _fmt_line('has_issues', has_issues),
        _fmt_line('scratchpad keys', list(scratchpad_keys)),
        _fmt_line('flow stack', list(flow_stack)),
        _fmt_line('turn_id', turn_id),
    ]
    return '\n'.join(lines)


def _fmt_network(network_log):
    if not network_log:
        return None
    rows = ['| timestamp | method | url | status |', '| --- | --- | --- | --- |']
    for entry in network_log[-20:]:
        ts = entry.get('timestamp', '')
        method = entry.get('method', '')
        url = entry.get('url', '')
        status = entry.get('status', '')
        rows.append(f'| {ts} | {method} | {url} | {status} |')
    return '\n'.join(rows)


def _default_reproducer(step_num):
    return (
        f'pytest utils/tests/e2e_agent_evals.py'
        f'::TestSyntheticDataPostE2E::test_step_{step_num:02d} -v -s --tb=short'
    )


def write_failure_dump(
    step_num,
    flow_name,
    expected,
    actual,
    rubric,
    state_snapshot,
    screenshot_path=None,
    network_log=None,
    reproducer='',
    run_id=None,
):
    """Write a markdown failure dump.

    Returns the dump file path. Parent directories are created if absent.
    ``run_id`` defaults to the current ``YYYYMMDD_HHMMSS`` timestamp.
    """
    run_id = run_id or _new_run_id()
    dump_dir = _FAILURES_ROOT / run_id
    os.makedirs(dump_dir, exist_ok=True)

    label = str(step_num)
    try:
        numeric = int(step_num)
        filename = f'step_{numeric:02d}.md'
    except (TypeError, ValueError):
        filename = f'step_{label}.md'
    dump_path = dump_dir / filename

    title = f'# Step {label} failure — {flow_name}'

    parts = [title, '']
    parts.append('## Expected')
    parts.append(_fmt_expected_actual(expected))
    parts.append('')
    parts.append('## Actual')
    parts.append(_fmt_expected_actual(actual))
    parts.append('')
    parts.append('## Diff')
    parts.append(_fmt_diff(expected, actual))
    parts.append('')
    parts.append('## State snapshot')
    parts.append(_fmt_state(state_snapshot))
    parts.append('')
    parts.append('## Rubric')
    parts.append(rubric.strip() if isinstance(rubric, str) else str(rubric))
    parts.append('')

    if screenshot_path:
        parts.append('## (Playwright only) Screenshot')
        parts.append(str(screenshot_path))
        parts.append('')
    net_table = _fmt_network(network_log)
    if net_table:
        parts.append('## (Playwright only) Network log (last 20 requests)')
        parts.append(net_table)
        parts.append('')

    parts.append('## Reproducer')
    if not reproducer:
        try:
            reproducer = _default_reproducer(int(step_num))
        except (TypeError, ValueError):
            reproducer = (
                f'pytest utils/tests/playwright_evals/test_step_{label}*.py -v -s --tb=short --ui'
            )
    parts.append(reproducer.strip())
    parts.append('')

    dump_path.write_text('\n'.join(parts), encoding='utf-8')
    return str(dump_path)


# ── Self-test ─────────────────────────────────────────────────────────

def _self_test():
    """Minimal self-test: write a dummy dump and verify all headers land."""
    expected = {
        'origin': 'release',
        'tool_log': ['channel_status', 'release_post'],
        'blocks': ['toast'],
        'metadata': {'tool_error': None},
        'scratchpad_keys': [],
        'flow_status': 'Completed',
    }
    actual = {
        'origin': 'error',
        'tool_log': ['channel_status'],
        'blocks': [],
        'metadata': {'tool_error': 'channel_status'},
        'scratchpad_keys': [],
        'flow_status': 'Running',
    }
    state_snapshot = {
        'active_post': 'TestPost',
        'keep_going': False,
        'has_issues': True,
        'scratchpad_keys': ['inspect', 'audit'],
        'flow_stack': ['release'],
        'turn_id': 14,
    }
    rubric = 'did_action: Attempts publication; did_follow_instructions: Targets Substack.'
    network_log = [
        {'timestamp': '12:00:00', 'method': 'POST', 'url': '/api/chat', 'status': 200},
        {'timestamp': '12:00:05', 'method': 'GET', 'url': '/api/posts/TestPost', 'status': 200},
    ]

    run_id = _new_run_id() + '_selftest'
    path = write_failure_dump(
        step_num=14,
        flow_name='release',
        expected=expected,
        actual=actual,
        rubric=rubric,
        state_snapshot=state_snapshot,
        screenshot_path='./step_14.png',
        network_log=network_log,
        run_id=run_id,
    )

    text = Path(path).read_text(encoding='utf-8')
    missing = [section for section in _SECTIONS if f'## {section}' not in text]
    if missing:
        raise AssertionError(f'self-test missing sections: {missing}')
    if '## (Playwright only) Screenshot' not in text:
        raise AssertionError('self-test missing screenshot section')
    if '## (Playwright only) Network log (last 20 requests)' not in text:
        raise AssertionError('self-test missing network log section')
    if '# Step 14 failure — release' not in text:
        raise AssertionError('self-test missing title header')
    print(f'dump.py self-test: OK  -> {path}')
    return path


if __name__ == '__main__':
    _self_test()
