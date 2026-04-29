"""Policy-in-isolation tests for the `refine` flow.

Refine merges user feedback into an existing outline by delegating to the LLM with the current
outline injected as extra_resolved. It has a contract backstop that checks the post-merge bullet
count and an OutlineFlow stack-on when the existing outline has no bullets. See
`utils/policy_builder/fixes/refine.md` and `utils/policy_builder/inventory/refine.md` for the
expected shape.

Pillar 2b: tools dispatch to real services on a tmp_path-isolated DB. The
bullet-shrink contract test keeps make_tool_stub since it specifically needs
DIFFERENT outline values from pre-save and post-save reads — a synthetic
divergence the real tools cannot produce when the skill is itself stubbed.
"""

from __future__ import annotations

from backend.modules.policies.base import BasePolicy

from utils.tests.policy_evals.fixtures import (
    assert_frame,
    build_policy,
    make_context,
    make_state,
    make_tool_stub,
    real_tools,
)


_POST_ID = 'abcd1234'

_OUTLINE_WITH_BULLETS = (
    '## Intro\n- First point\n- Second point\n## Body\n- Third point\n'
)
_OUTLINE_NO_BULLETS = '## Intro\nOpening paragraph.\n## Body\nExposition.\n'


def _stub_llm_execute(return_text:str, tool_log:list|None=None, captured:list|None=None):
    log = list(tool_log or [])

    def stub(self, flow, state, context, tools, include_preview:bool=False,
            extra_resolved:dict|None=None, exclude_tools:tuple=()):
        if captured is not None:
            captured.append({'extra_resolved': dict(extra_resolved or {})})
        return return_text, log

    return stub


def _seed_post_with_outline(outline_md, title='T'):
    from backend.utilities.services import PostService, ContentService
    post_id = PostService().create_post(title=title, type='draft')['post_id']
    ContentService().generate_outline(post_id, outline_md)
    return post_id


def test_refine_happy_path_saves_section(monkeypatch, tmp_path):
    """Happy path: source + feedback + steps filled with an existing
    bulleted outline calls llm_execute with extra_resolved=
    {'current_outline': <outline>}, confirms revise_content succeeded,
    marks flow Completed and returns a card."""
    tools = real_tools(monkeypatch, tmp_path)
    post_id = _seed_post_with_outline(_OUTLINE_WITH_BULLETS)

    policy, comps = build_policy('refine')
    comps['flow_stack'].stackon('refine')
    top = comps['flow_stack'].get_flow()
    top.slots['source'].add_one(post=post_id)
    top.slots['feedback'].add_one('tighten the body')
    top.slots['steps'].add_one('tighten', 'cut filler words')

    state = make_state(active_post=post_id)
    context = make_context('refine the outline')
    captured:list = []
    tool_log = [
        {'tool': 'revise_content', 'input': {}, 'result': {'_success': True}},
    ]
    monkeypatch.setattr(BasePolicy, 'llm_execute',
        _stub_llm_execute('saved section', tool_log=tool_log, captured=captured))

    frame = policy.execute(state, context, tools)

    assert len(captured) == 1
    # current_outline should be present and reflect the bulleted form.
    assert 'current_outline' in captured[0]['extra_resolved']
    assert '- First point' in captured[0]['extra_resolved']['current_outline']

    assert_frame(frame, origin='refine', block_types=('card',))
    assert top.status == 'Completed'


def test_refine_bullet_shrink_contract_violation(monkeypatch):
    """Contract backstop — when the post-save outline has strictly
    fewer bullets than the prior outline AND the user did not request
    removal, the policy returns DisplayFrame(origin=flow.name(),
    metadata['violation']='failed_to_save') with a descriptive thoughts
    line. Flow is not Completed and no ambiguity is declared.

    Synthetic test: the pre/post outline divergence requires controlled
    multi-call returns. Keep make_tool_stub.
    """
    policy, comps = build_policy('refine')
    comps['flow_stack'].stackon('refine')
    top = comps['flow_stack'].get_flow()
    top.slots['source'].add_one(post=_POST_ID)
    top.slots['feedback'].add_one('make it clearer')
    top.slots['steps'].add_one('clarify', 'sharper wording')

    state = make_state(active_post=_POST_ID)
    context = make_context('refine')
    tool_log = [{'tool': 'revise_content', 'input': {}, 'result': {'_success': True}}]
    monkeypatch.setattr(BasePolicy, 'llm_execute',
        _stub_llm_execute('done', tool_log=tool_log))

    shrunk = '## Intro\n- only one\n'  # 1 bullet; prior had 3
    tools = make_tool_stub({
        'read_metadata': [
            {'_success': True, 'post_id': _POST_ID, 'title': 'T',
             'section_ids': []},
            {'_success': True, 'post_id': _POST_ID, 'title': 'T',
             'outline': _OUTLINE_WITH_BULLETS, 'section_ids': []},
            {'_success': True, 'post_id': _POST_ID, 'title': 'T',
             'outline': shrunk, 'section_ids': []},
        ],
    })

    frame = policy.execute(state, context, tools)

    assert_frame(frame, origin='refine',
                 metadata={'violation': 'failed_to_save'})
    assert 'shrunk' in frame.thoughts.lower()
    assert top.status != 'Completed'
    assert not comps['ambiguity'].present()


def test_refine_no_bullets_stacks_on_outline(monkeypatch, tmp_path):
    """Per fixes/refine.md § Stack-on to OutlineFlow — when the existing
    outline has no bullets, the policy stacks on 'outline', sets
    state.keep_going=True, and surfaces the reason in frame.thoughts."""
    tools = real_tools(monkeypatch, tmp_path)
    post_id = _seed_post_with_outline(_OUTLINE_NO_BULLETS)

    policy, comps = build_policy('refine')
    comps['flow_stack'].stackon('refine')
    top = comps['flow_stack'].get_flow()
    top.slots['source'].add_one(post=post_id)
    top.slots['feedback'].add_one('punch it up')
    top.slots['steps'].add_one('punch', 'make punchier')

    state = make_state(active_post=post_id)
    context = make_context('refine')

    called:list = []
    monkeypatch.setattr(BasePolicy, 'llm_execute',
        _stub_llm_execute('', captured=called))

    frame = policy.execute(state, context, tools)

    assert called == [], 'no bullets → stack-on, not llm_execute'
    assert state.keep_going is True
    stacked = comps['flow_stack'].get_flow()
    assert stacked.name() == 'outline'
    assert_frame(frame, thoughts_contains='bullets in the outline yet')
