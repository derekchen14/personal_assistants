"""Policy-in-isolation tests for the `add` flow.

Add delegates to the skill for detail-into-existing-section operations. It accepts any of (points,
additions, image) via elective slots; the policy asserts only that entity_slot (source) is present
before calling the LLM. See `utils/policy_builder/fixes/add.md` and
`utils/policy_builder/inventory/add.md` for the expected shape.

Pillar 2b: tools dispatch to real services on a tmp_path-isolated DB.
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


def _stub_llm_execute(return_text:str, captured:list|None=None):
    def stub(self, flow, state, context, tools, include_preview:bool=False,
            extra_resolved:dict|None=None, exclude_tools:tuple=()):
        if captured is not None:
            captured.append({'exclude_tools': tuple(exclude_tools)})
        return return_text, []

    return stub


def _seed_post_with_section(title='Aviation', sec_title='Intro', body='text'):
    from backend.utilities.services import PostService, ContentService
    post_id = PostService().create_post(title=title, type='draft')['post_id']
    ContentService().generate_outline(post_id, f'## {sec_title}\n\n{body}\n')
    meta = PostService().read_metadata(post_id)
    sec_id = meta['section_ids'][0] if meta['section_ids'] else 'intro'
    return post_id, sec_id


def test_add_points_happy_path(monkeypatch, tmp_path):
    """Per fixes/add.md § Changes that landed — source + points filled
    delegates to llm_execute and returns origin='add' with a card block."""
    tools = real_tools(monkeypatch, tmp_path)
    post_id, sec_id = _seed_post_with_section()

    policy, comps = build_policy('add')
    comps['flow_stack'].stackon('add')
    top = comps['flow_stack'].get_flow()
    top.slots['source'].add_one(post=post_id, sec=sec_id)
    top.slots['points'].add_one('p1', 'add an example')
    top.slots['points'].add_one('p2', 'add a caveat')

    state = make_state(active_post=post_id)
    context = make_context('add a couple of points')
    captured:list = []
    monkeypatch.setattr(BasePolicy, 'llm_execute',
        _stub_llm_execute('added points', captured=captured))

    frame = policy.execute(state, context, tools)

    assert len(captured) == 1
    assert_frame(frame, origin='add', block_types=('card',))
    assert top.status == 'Completed'


def test_add_additions_dictionary(monkeypatch, tmp_path):
    """Per inventory/add.md § Slot shapes — source + additions (section →
    bullet dict) also delegates to llm_execute and marks the flow Completed."""
    tools = real_tools(monkeypatch, tmp_path)
    post_id, sec_id = _seed_post_with_section()

    policy, comps = build_policy('add')
    comps['flow_stack'].stackon('add')
    top = comps['flow_stack'].get_flow()
    top.slots['source'].add_one(post=post_id)
    top.slots['additions'].add_one(key=sec_id, val='add an anecdote')

    state = make_state(active_post=post_id)
    context = make_context('add something to the intro')
    captured:list = []
    monkeypatch.setattr(BasePolicy, 'llm_execute',
        _stub_llm_execute('additions applied', captured=captured))

    frame = policy.execute(state, context, tools)

    assert len(captured) == 1
    assert_frame(frame, origin='add', block_types=('card',))
    assert top.status == 'Completed'


def test_add_image_keeps_insert_media_available(monkeypatch, tmp_path):
    """Per fixes/add.md § Changes that landed — image-based add does not
    strip `insert_media`; the exclude_tools tuple stays empty so the skill
    can call insert_media."""
    tools = real_tools(monkeypatch, tmp_path)
    post_id, _ = _seed_post_with_section()

    policy, comps = build_policy('add')
    comps['flow_stack'].stackon('add')
    top = comps['flow_stack'].get_flow()
    top.slots['source'].add_one(post=post_id)
    top.slots['image'].assign_one('diagram', src='/tmp/wright.png')

    state = make_state(active_post=post_id)
    context = make_context('add a hero image')
    captured:list = []
    monkeypatch.setattr(BasePolicy, 'llm_execute',
        _stub_llm_execute('image inserted', captured=captured))

    frame = policy.execute(state, context, tools)

    assert captured[0]['exclude_tools'] == (), 'insert_media must remain available'
    assert_frame(frame, origin='add', block_types=('card',))


def test_add_missing_source_declares_specific_ambiguity(monkeypatch, tmp_path):
    """Per inventory/add.md § Guard clauses — missing entity_slot (source)
    declares specific ambiguity with {'missing_slot': <entity_slot>} and
    returns DisplayFrame('error'). llm_execute is not called."""
    tools = real_tools(monkeypatch, tmp_path)
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

    frame = policy.execute(state, context, tools)

    assert called == []
    assert_frame(frame, origin='add')
    amb = comps['ambiguity']
    assert amb.present()
    assert amb.level == 'specific'
    assert amb.metadata == {'missing_slot': top.entity_slot}
