"""Policy-in-isolation tests for the `release` flow.

Release delegates the pre-publish handshake (channel_status, release_post)
to a skill via llm_execute, then the policy gates `update_post` on those
tools having succeeded. A tool-level failure surfaces as a frame with
metadata['violation']='tool_error' plus failed_tool. See
`utils/policy_builder/fixes/release.md` and
`utils/policy_builder/inventory/release.md` for the expected shape.
"""

from __future__ import annotations

from backend.modules.policies.base import BasePolicy

from utils.tests.policy_evals.fixtures import (
    assert_frame,
    build_policy,
    capture_tool_log,
    make_context,
    make_flow,
    make_state,
    make_tool_stub,
)


_POST_ID = 'abcd1234'


def _stub_llm_execute(return_text:str, tool_log:list|None=None):
    log = list(tool_log or [])

    def stub(self, flow, state, context, tools, include_preview:bool=False,
            extra_resolved:dict|None=None, exclude_tools:tuple=()):
        return return_text, log

    return stub


def test_release_happy_path_calls_update_post(monkeypatch):
    """Per fixes/release.md § update_post gated on tool success — when
    channel_status and release_post both succeed, the policy calls
    update_post(status='published'), marks the flow Completed, and returns
    a toast block with level='success'."""
    policy, comps = build_policy('release')
    comps['flow_stack'].stackon('release')
    top = comps['flow_stack'].get_flow()
    top.slots['source'].add_one(post=_POST_ID)
    top.slots['channel'].add_one(chl='medium')

    tool_log = [
        {'tool': 'channel_status', 'input': {}, 'result': {'_success': True, 'status': 'ready'}},
        {'tool': 'release_post', 'input': {}, 'result': {'_success': True, 'url': 'https://example.com/p'}},
    ]
    monkeypatch.setattr(BasePolicy, 'llm_execute',
        _stub_llm_execute('Published to Medium.', tool_log=tool_log))

    state = make_state(active_post=_POST_ID)
    context = make_context('publish to medium')
    tools = capture_tool_log(make_tool_stub({
        'read_metadata': [
            {'_success': True, 'post_id': _POST_ID, 'title': 'T',
             'section_ids': []},
        ],
        'update_post': [{'_success': True}],
    }))

    frame = policy.execute(state, context, tools)

    update_calls = [e for e in tools.log if e['name'] == 'update_post']
    assert len(update_calls) == 1
    assert update_calls[0]['params']['updates'] == {'status': 'published'}

    assert_frame(frame, origin='release', block_types=('toast',))
    toast = frame.blocks[0]
    assert toast.data['level'] == 'success'
    assert top.status == 'Completed'


def test_release_tool_failure_returns_error_frame(monkeypatch):
    """When channel_status fails, the policy returns
    origin=flow.name() with metadata['violation']='tool_error' +
    metadata['failed_tool']='channel_status', non-empty code, does NOT
    call update_post, and does NOT mark the flow Completed."""
    policy, comps = build_policy('release')
    comps['flow_stack'].stackon('release')
    top = comps['flow_stack'].get_flow()
    top.slots['source'].add_one(post=_POST_ID)
    top.slots['channel'].add_one(chl='medium')

    tool_log = [
        {'tool': 'channel_status', 'input': {},
         'result': {'_success': False, '_message': 'OAuth token expired',
                    '_error': 'auth'}},
    ]
    monkeypatch.setattr(BasePolicy, 'llm_execute',
        _stub_llm_execute('channel check failed', tool_log=tool_log))

    state = make_state(active_post=_POST_ID)
    context = make_context('publish')
    tools = capture_tool_log(make_tool_stub({
        'read_metadata': [
            {'_success': True, 'post_id': _POST_ID, 'title': 'T',
             'section_ids': []},
        ],
    }))

    frame = policy.execute(state, context, tools)

    update_calls = [e for e in tools.log if e['name'] == 'update_post']
    assert update_calls == [], 'update_post must not fire when gating tool fails'
    assert top.status != 'Completed'
    # Per convention #6, metadata is classification only. Channel / reason /
    # post_id detail moved into thoughts + code after the Phase-4 sweep.
    assert_frame(frame, origin='release',
                 metadata={'violation': 'tool_error', 'failed_tool': 'channel_status'},
                 has_code=True)
    assert 'channel_status' in frame.thoughts
