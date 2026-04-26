"""Policy-in-isolation tests for the `add` flow.

Add delegates to the skill for detail-into-existing-section operations. It accepts any of (points,
additions, image) via elective slots; the policy asserts only that entity_slot (source) is present
before calling the LLM. See `utils/policy_builder/fixes/add.md` and
`utils/policy_builder/inventory/add.md` for the expected shape.
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


def _stub_llm_execute(return_text:str, captured:list|None=None):
    def stub(self, flow, state, context, tools, include_preview:bool=False,
            extra_resolved:dict|None=None, exclude_tools:tuple=()):
        if captured is not None:
            captured.append({'exclude_tools': tuple(exclude_tools)})
        return return_text, []

    return stub


def _card_tools():
    """Tools stub returning enough read_metadata / read_section responses
    for _resolve_source_ids + _read_post_content."""
    return make_tool_stub({
        'read_metadata': [
            # resolve_post_id
            {'_success': True, 'post_id': _POST_ID, 'title': 'Aviation',
             'section_ids': ['sec_one']},
            # _read_post_content
            {'_success': True, 'post_id': _POST_ID, 'title': 'Aviation',
             'status': 'draft', 'section_ids': ['sec_one']},
        ],
        'read_section': [
            {'_success': True, 'title': 'Intro', 'content': 'text'},
        ],
    })


def test_add_points_happy_path(monkeypatch):
    """Per fixes/add.md § Changes that landed — source + points filled
    delegates to llm_execute and returns origin='add' with a card block."""
    policy, comps = build_policy('add')
    comps['flow_stack'].stackon('add')
    top = comps['flow_stack'].get_flow()
    top.slots['source'].add_one(post=_POST_ID, sec='sec_one')
    top.slots['points'].add_one('p1', 'add an example')
    top.slots['points'].add_one('p2', 'add a caveat')

    state = make_state(active_post=_POST_ID)
    context = make_context('add a couple of points')
    captured:list = []
    monkeypatch.setattr(BasePolicy, 'llm_execute',
        _stub_llm_execute('added points', captured=captured))

    frame = policy.execute(state, context, _card_tools())

    assert len(captured) == 1
    assert_frame(frame, origin='add', block_types=('card',))
    assert top.status == 'Completed'


def test_add_additions_dictionary(monkeypatch):
    """Per inventory/add.md § Slot shapes — source + additions (section →
    bullet dict) also delegates to llm_execute and marks the flow Completed."""
    policy, comps = build_policy('add')
    comps['flow_stack'].stackon('add')
    top = comps['flow_stack'].get_flow()
    top.slots['source'].add_one(post=_POST_ID)
    top.slots['additions'].add_one(key='intro', val='add an anecdote')

    state = make_state(active_post=_POST_ID)
    context = make_context('add something to the intro')
    captured:list = []
    monkeypatch.setattr(BasePolicy, 'llm_execute',
        _stub_llm_execute('additions applied', captured=captured))

    frame = policy.execute(state, context, _card_tools())

    assert len(captured) == 1
    assert_frame(frame, origin='add', block_types=('card',))
    assert top.status == 'Completed'


def test_add_image_keeps_insert_media_available(monkeypatch):
    """Per fixes/add.md § Changes that landed — image-based add does not
    strip `insert_media`; the exclude_tools tuple stays empty so the skill
    can call insert_media."""
    policy, comps = build_policy('add')
    comps['flow_stack'].stackon('add')
    top = comps['flow_stack'].get_flow()
    top.slots['source'].add_one(post=_POST_ID)
    top.slots['image'].assign_one('diagram', src='/tmp/wright.png')

    state = make_state(active_post=_POST_ID)
    context = make_context('add a hero image')
    captured:list = []
    monkeypatch.setattr(BasePolicy, 'llm_execute',
        _stub_llm_execute('image inserted', captured=captured))

    frame = policy.execute(state, context, _card_tools())

    assert captured[0]['exclude_tools'] == (), 'insert_media must remain available'
    assert_frame(frame, origin='add', block_types=('card',))


def test_add_missing_source_declares_specific_ambiguity(monkeypatch):
    """Per inventory/add.md § Guard clauses — missing entity_slot (source)
    declares specific ambiguity with {'missing_slot': <entity_slot>} and
    returns DisplayFrame('error'). llm_execute is not called."""
    policy, comps = build_policy('add')
    comps['flow_stack'].stackon('add')
    top = comps['flow_stack'].get_flow()
    top.slots['points'].add_one('p1', 'add something')
    # source intentionally left empty

    state = make_state()
    context = make_context('add a paragraph')
    called:list = []
    monkeypatch.setattr(BasePolicy, 'llm_execute',
        _stub_llm_execute('', captured=called))

    tools = make_tool_stub({})
    frame = policy.execute(state, context, tools)

    assert called == []
    assert_frame(frame, origin='add')
    amb = comps['ambiguity']
    assert amb.present()
    assert amb.level == 'specific'
    assert amb.metadata == {'missing_slot': top.entity_slot}
