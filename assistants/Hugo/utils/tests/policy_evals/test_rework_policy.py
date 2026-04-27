"""Policy-in-isolation tests for the `rework` flow.

Rework is section-scoped by default but enters a per-section loop when the source lacks a sec_id
(whole-post scope). The policy also inspects the skill's JSON reply to check off completed
ChecklistSlot suggestions. See `utils/policy_builder/fixes/rework.md` and
`utils/policy_builder/inventory/rework.md` for the expected shape.
"""

from __future__ import annotations

from backend.modules.policies.base import BasePolicy

from utils.tests.policy_evals.fixtures import (
    assert_frame,
    build_policy,
    make_context,
    make_flow,
    make_state,
    make_tool_stub,
)


_POST_ID = 'abcd1234'


def _stub_llm_execute(return_text:str, tool_log:list|None=None, captured:list|None=None):
    log = list(tool_log or [])

    def stub(self, flow, state, context, tools, include_preview:bool=False,
            extra_resolved:dict|None=None, exclude_tools:tuple=()):
        if captured is not None:
            captured.append({'extra_resolved': dict(extra_resolved or {})})
        return return_text, log

    return stub


def test_rework_section_scoped_single_call(monkeypatch):
    """Per fixes/rework.md § Changes that landed #2 — when source has a
    sec_id, rework runs a single llm_execute pass (no per-section loop)
    and returns a card frame."""
    policy, comps = build_policy('rework')
    comps['flow_stack'].stackon('rework')
    top = comps['flow_stack'].get_flow()
    top.slots['source'].add_one(post=_POST_ID, sec='sec_one')
    top.slots['changes'].add_one('tighten the transitions')

    state = make_state(active_post=_POST_ID)
    context = make_context('rework this section')
    captured:list = []
    tool_log = [{'tool': 'revise_content', 'input': {}, 'result': {'_success': True}}]
    monkeypatch.setattr(BasePolicy, 'llm_execute',
        _stub_llm_execute('{"done": []}', tool_log=tool_log, captured=captured))

    tools = make_tool_stub({
        'read_metadata': [
            # resolve_post_id
            {'_success': True, 'post_id': _POST_ID, 'title': 'T',
             'section_ids': ['sec_one']},
            # _read_post_content
            {'_success': True, 'post_id': _POST_ID, 'title': 'T',
             'status': 'draft', 'section_ids': ['sec_one']},
        ],
        'read_section': [
            {'_success': True, 'title': 'Intro', 'content': 'text'},
        ],
    })

    frame = policy.execute(state, context, tools)

    assert len(captured) == 1, 'section-scoped rework is one pass'
    assert_frame(frame, origin='rework', block_types=('card',))
    assert top.status == 'Completed'


def test_rework_whole_post_single_call_with_preview(monkeypatch):
    """When source has no sec_id, the policy makes a single llm_execute call
    with `include_preview=True` so the skill can handle whole-post operations
    (swap two sections, reorder, cross-section rewrite) in one pass instead
    of looping per section."""
    policy, comps = build_policy('rework')
    comps['flow_stack'].stackon('rework')
    top = comps['flow_stack'].get_flow()
    top.slots['source'].add_one(post=_POST_ID)  # no sec_id
    top.slots['changes'].add_one('restructure arguments')

    state = make_state(active_post=_POST_ID)
    context = make_context('rework the whole post')
    captured:list = []
    tool_log = [{'tool': 'revise_content', 'input': {}, 'result': {'_success': True}}]
    monkeypatch.setattr(BasePolicy, 'llm_execute',
        _stub_llm_execute('{"done": []}', tool_log=tool_log, captured=captured))

    tools = make_tool_stub({
        'read_metadata': [
            # _resolve_source_ids
            {'_success': True, 'post_id': _POST_ID, 'title': 'T',
             'section_ids': ['sec_a', 'sec_b', 'sec_c']},
            # _read_post_content (include_outline=True)
            {'_success': True, 'post_id': _POST_ID, 'title': 'T',
             'status': 'draft', 'outline': '## A\nalpha\n\n## B\nbeta\n\n## C\ngamma',
             'section_ids': ['sec_a', 'sec_b', 'sec_c']},
        ],
    })

    frame = policy.execute(state, context, tools)

    assert len(captured) == 1, 'rework should make a single whole-post call'
    assert_frame(frame, origin='rework', block_types=('card',))
    assert top.status == 'Completed'


def test_rework_mark_suggestions_done_checks_off_names(monkeypatch):
    """Per fixes/rework.md § Changes that landed #3 — when the skill
    returns `{"done": ["sug_one", "sug_two"]}` alongside a successful
    revise_content, `_mark_suggestions_done` checks those ChecklistSlot
    items."""
    policy, comps = build_policy('rework')
    comps['flow_stack'].stackon('rework')
    top = comps['flow_stack'].get_flow()
    top.slots['source'].add_one(post=_POST_ID, sec='sec_one')
    top.slots['suggestions'].add_one('sug_one', 'do A')
    top.slots['suggestions'].add_one('sug_two', 'do B')
    top.slots['suggestions'].add_one('sug_three', 'do C')

    state = make_state(active_post=_POST_ID)
    context = make_context('rework')

    tool_log = [
        {'tool': 'revise_content', 'input': {}, 'result': {'_success': True}},
    ]
    skill_reply = '{"done": ["sug_one", "sug_two"]}'
    monkeypatch.setattr(BasePolicy, 'llm_execute',
        _stub_llm_execute(skill_reply, tool_log=tool_log))

    tools = make_tool_stub({
        'read_metadata': [
            {'_success': True, 'post_id': _POST_ID, 'title': 'T',
             'section_ids': ['sec_one']},
            {'_success': True, 'post_id': _POST_ID, 'title': 'T',
             'status': 'draft', 'section_ids': ['sec_one']},
        ],
        'read_section': [{'_success': True, 'title': 'Intro', 'content': 'x'}],
    })

    frame = policy.execute(state, context, tools)

    steps = {s['name']: s['checked'] for s in top.slots['suggestions'].steps}
    assert steps == {'sug_one': True, 'sug_two': True, 'sug_three': False}
    assert_frame(frame, origin='rework', block_types=('card',))
