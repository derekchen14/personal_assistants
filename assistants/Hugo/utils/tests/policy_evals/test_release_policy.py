"""Policy-in-isolation tests for the `release` flow.

Release delegates the pre-publish handshake (channel_status, release_post) to a skill via
llm_execute, then the policy gates `update_post` on those tools having succeeded. A tool-level
failure surfaces as a frame with metadata['violation']='tool_error' plus failed_tool. See
`utils/policy_builder/fixes/release.md` and `utils/policy_builder/inventory/release.md` for the
expected shape.

Pillar 2b: tools dispatch to real services on a tmp_path-isolated DB. The skill
output (text + tool_log) is still stubbed because that IS an LLM contract.
"""

from __future__ import annotations

from backend.modules.policies.base import BasePolicy

from utils.tests.policy_evals.fixtures import (
    assert_frame,
    build_policy,
    make_context,
    make_state,
    real_tools,
)


def _stub_llm_execute(return_text:str, tool_log:list|None=None):
    log = list(tool_log or [])

    def stub(self, flow, state, context, tools, include_preview:bool=False,
            extra_resolved:dict|None=None, exclude_tools:tuple=()):
        return return_text, log

    return stub


def _seed_post(title='T'):
    """Seed one post on the (already-monkeypatched) tmp DB. Returns its post_id."""
    from backend.utilities.services import PostService
    return PostService().create_post(title=title, type='draft')['post_id']


def test_release_happy_path_calls_update_post(monkeypatch, tmp_path):
    """Per fixes/release.md § update_post gated on tool success — when
    channel_status and release_post both succeed, the policy calls
    update_post(status='published'), marks the flow Completed, and returns
    a toast block with level='success'."""
    tools = real_tools(monkeypatch, tmp_path)
    post_id = _seed_post(title='T')

    policy, comps = build_policy('release')
    comps['flow_stack'].stackon('release')
    top = comps['flow_stack'].get_flow()
    top.slots['source'].add_one(post=post_id)
    top.slots['channel'].add_one('medium')

    # Skill output is canned (legitimate LLM mock). Real tools take over for the
    # update_post + read_metadata calls the policy makes.
    tool_log = [
        {'tool': 'channel_status', 'input': {}, 'result': {'_success': True, 'status': 'ready'}},
        {'tool': 'release_post', 'input': {}, 'result': {'_success': True, 'url': 'https://example.com/p'}},
    ]
    monkeypatch.setattr(BasePolicy, 'llm_execute',
        _stub_llm_execute('Published to Medium.', tool_log=tool_log))

    state = make_state(active_post=post_id)
    context = make_context('publish to medium')

    frame = policy.execute(state, context, tools)

    update_calls = [e for e in tools.log if e['name'] == 'update_post']
    assert len(update_calls) == 1
    assert update_calls[0]['params']['updates'] == {'status': 'published'}

    # Disk state confirms persistence — a real-tool win the canned stub couldn't catch.
    from backend.utilities.services import PostService
    meta = PostService().read_metadata(post_id)
    assert meta['status'] == 'published'

    assert_frame(frame, origin='release', block_types=('toast',))
    toast = frame.blocks[0]
    assert toast.data['level'] == 'success'
    assert top.status == 'Completed'


def test_release_tool_failure_returns_error_toast(monkeypatch, tmp_path):
    """When a platform tool (channel_status / release_post) fails, the policy
    surfaces the failure via a toast block carrying the tool name + error
    message, and does NOT call update_post. Flow is still marked Completed
    so the user can retry from a fresh turn."""
    tools = real_tools(monkeypatch, tmp_path)
    post_id = _seed_post(title='T')

    policy, comps = build_policy('release')
    comps['flow_stack'].stackon('release')
    top = comps['flow_stack'].get_flow()
    top.slots['source'].add_one(post=post_id)
    top.slots['channel'].add_one('medium')

    tool_log = [
        {'tool': 'channel_status', 'input': {},
         'result': {'_success': False, '_message': 'OAuth token expired',
                    '_error': 'auth'}},
    ]
    monkeypatch.setattr(BasePolicy, 'llm_execute',
        _stub_llm_execute('channel check failed', tool_log=tool_log))

    state = make_state(active_post=post_id)
    context = make_context('publish')

    frame = policy.execute(state, context, tools)

    update_calls = [e for e in tools.log if e['name'] == 'update_post']
    assert update_calls == [], 'update_post must not fire when a platform tool fails'
    assert_frame(frame, origin='release', block_types=('toast',))
    toast = frame.blocks[0]
    assert 'channel_status' in toast.data['message']
    assert 'OAuth token expired' in toast.data['message']
