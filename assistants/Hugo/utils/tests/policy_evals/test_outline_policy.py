"""Policy-in-isolation tests for the `outline` flow.

Outline has two modes (propose vs. direct) plus a recursive proposals-filled branch. The policy
delegates to `llm_execute` in every LLM-bound branch, so most tests mock the base `llm_execute` via
`monkeypatch` and assert on the policy's orchestration (depth injection, exclude_tools,
tool_succeeded gating). See `utils/policy_builder/fixes/outline.md` and
`utils/policy_builder/inventory/outline.md` for the expected shape.
"""

from __future__ import annotations

from backend.modules.policies.base import BasePolicy
from backend.components.display_frame import DisplayFrame

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


def _stub_llm_execute(return_text:str, tool_log:list|None=None, captured:list|None=None):
    """Build a `llm_execute` replacement that records its call args."""
    log = list(tool_log or [])

    def stub(self, flow, state, context, tools, include_preview:bool=False,
            extra_resolved:dict|None=None, exclude_tools:tuple=()):
        if captured is not None:
            captured.append({
                'flow': flow, 'include_preview': include_preview,
                'extra_resolved': dict(extra_resolved or {}),
                'exclude_tools': tuple(exclude_tools),
            })
        return return_text, log

    return stub


def test_outline_direct_mode_happy_path(monkeypatch):
    """Per fixes/outline.md § Changes that landed — direct mode (sections
    filled) calls llm_execute with depth in extra_resolved, checks
    `tool_succeeded(tool_log, 'generate_outline')`, marks the flow Completed
    and returns a card frame."""
    policy, comps = build_policy('outline')
    comps['flow_stack'].stackon('outline')
    top = comps['flow_stack'].get_flow()
    top.slots['source'].add_one(post=_POST_ID)
    top.slots['sections'].add_one('intro', 'open cold')
    top.slots['sections'].add_one('body', 'key argument')
    top.slots['depth'].level = 3

    state = make_state(active_post=_POST_ID)
    context = make_context('draft an outline')
    captured:list = []
    tool_log = [{'tool': 'generate_outline', 'input': {}, 'result': {'_success': True}}]
    monkeypatch.setattr(BasePolicy, 'llm_execute',
        _stub_llm_execute('## Intro\n- line\n', tool_log=tool_log, captured=captured))

    tools = capture_tool_log(make_tool_stub({
        'read_metadata': [{
            '_success': True, 'post_id': _POST_ID,
            'title': 'Aviation', 'status': 'draft', 'section_ids': [],
        }],
    }))

    frame = policy.execute(state, context, tools)

    assert len(captured) == 1, 'llm_execute should be called exactly once'
    assert captured[0]['extra_resolved'] == {'depth': 3}
    assert captured[0]['exclude_tools'] == ()

    assert_frame(frame, origin='outline', block_types=('card',))
    assert top.status == 'Completed'


def test_outline_propose_mode_excludes_generate_outline(monkeypatch):
    """Per fixes/outline.md § Tool stripping in propose mode — topic-only
    path calls llm_execute with propose_mode=True and
    exclude_tools=('generate_outline', 'merge_outline'). Parsed candidates
    land in a selection block. depth defaults to 2 when not filled."""
    policy, comps = build_policy('outline')
    comps['flow_stack'].stackon('outline')
    top = comps['flow_stack'].get_flow()
    top.slots['source'].add_one(post=_POST_ID)
    top.slots['topic'].add_one('early aviation')

    state = make_state(active_post=_POST_ID)
    context = make_context('outline a post about early aviation')
    captured:list = []
    # Two candidate options, each with two sections — hits ProposalSlot.size=2.
    proposed_text = (
        '### Option 1\n## Intro\nOpening\n## Conclusion\nWrap-up\n'
        '### Option 2\n## Historical\nContext\n## Modern\nToday\n'
    )
    monkeypatch.setattr(BasePolicy, 'llm_execute',
        _stub_llm_execute(proposed_text, tool_log=[], captured=captured))

    tools = make_tool_stub({})

    frame = policy.execute(state, context, tools)

    assert len(captured) == 1
    call = captured[0]
    assert call['extra_resolved'] == {'depth': 2, 'propose_mode': True}
    assert call['exclude_tools'] == ('generate_outline',)

    assert_frame(frame, origin='outline', block_types=('selection',))
    selection = frame.blocks[0]
    assert 'options' in selection.data
    options = selection.data['options']
    assert len(options) == 2
    for opt in options:
        assert opt['dax'] == '{002}'
        assert 'proposals' in opt['payload']
        assert isinstance(opt['payload']['proposals'], list)
        assert opt['payload']['proposals'][0]
        assert opt.get('body')
        assert opt.get('label')


def test_outline_missing_source_declares_partial_ambiguity(monkeypatch):
    """Per inventory/outline.md § Guard clauses — missing source slot
    declares partial ambiguity and returns an empty frame without calling
    llm_execute."""
    policy, comps = build_policy('outline')
    comps['flow_stack'].stackon('outline')

    called:list = []
    monkeypatch.setattr(BasePolicy, 'llm_execute',
        _stub_llm_execute('', captured=called))

    state = make_state()
    context = make_context('outline something')
    tools = make_tool_stub({})

    frame = policy.execute(state, context, tools)

    assert called == [], 'llm_execute must not be called when source is missing'
    assert_frame(frame, origin='')
    assert comps['ambiguity'].present()
    assert comps['ambiguity'].level == 'partial'
