"""Policy-in-isolation tests for the `create` flow.

Create is a deterministic flow (no `llm_execute`); the policy calls
`create_post` directly and returns a card frame on success or an error
frame on duplicate / failure. See `utils/policy_builder/fixes/create.md`
and `utils/policy_builder/inventory/create.md` for the expected shape.
"""

from __future__ import annotations

from utils.tests.policy_evals.fixtures import (
    assert_frame,
    build_policy,
    capture_tool_log,
    make_context,
    make_flow,
    make_state,
    make_tool_stub,
)


def test_create_filled_slots_happy_path():
    """Per fixes/create.md § Changes that landed — success path sets origin='create',
    adds a card block, marks flow Completed, and syncs state.active_post."""
    policy, comps = build_policy('create')
    flow = make_flow('create', title='The Wright Brothers Diary', type='draft')
    comps['flow_stack'].stackon('create')
    top = comps['flow_stack'].get_flow()
    top.slots['title'].add_one('The Wright Brothers Diary')
    top.slots['type'].assign_one('draft')

    state = make_state()
    context = make_context('create a new draft about the Wright brothers')
    tools = capture_tool_log(make_tool_stub({
        'create_post': [{
            '_success': True,
            'post_id': 'wr1ght00',
            'title': 'The Wright Brothers Diary',
            'status': 'draft',
        }],
    }))

    frame = policy.execute(state, context, tools)

    assert_frame(frame, origin='create', block_types=('card',))
    card = frame.blocks[0]
    assert card.data['post_id'] == 'wr1ght00'
    assert card.data['title'] == 'The Wright Brothers Diary'
    assert card.data['status'] == 'draft'

    active_flow = comps['flow_stack'].get_flow()
    assert active_flow.name() == 'create'
    assert active_flow.status == 'Completed'
    assert state.active_post == 'wr1ght00'
    assert len(tools.log) == 1 and tools.log[0]['name'] == 'create_post'


def test_create_with_topic_stacks_outline():
    """Per fixes/create.md § Topic-provided path — a topic triggers an inline
    stackon('outline') with source + topic pre-filled, keep_going=True, and a
    transition thought. Theme 6 convention (no helper)."""
    policy, comps = build_policy('create')
    comps['flow_stack'].stackon('create')
    top = comps['flow_stack'].get_flow()
    top.slots['title'].add_one('The Wright Brothers Diary')
    top.slots['type'].assign_one('draft')
    top.slots['topic'].add_one('early aviation experiments')

    state = make_state()
    context = make_context('create a draft about early aviation')
    tools = make_tool_stub({
        'create_post': [{
            '_success': True,
            'post_id': 'wr1ght00',
            'title': 'The Wright Brothers Diary',
            'status': 'draft',
        }],
    })

    frame = policy.execute(state, context, tools)

    assert_frame(frame, origin='create', block_types=('card',),
                 thoughts_contains='outline')
    assert state.keep_going is True

    stacked = comps['flow_stack'].get_flow()
    assert stacked.name() == 'outline'
    assert stacked.status == 'Active'
    assert stacked.slots['source'].values[0]['post'] == 'wr1ght00'
    assert stacked.slots['topic'].value == 'early aviation experiments'


def test_create_missing_title_declares_specific_ambiguity():
    """Per fixes/create.md / inventory/create.md § Guard clauses — missing
    title triggers declare('specific', metadata={'missing_slot': 'title'}) and
    an early-return DisplayFrame('error')."""
    policy, comps = build_policy('create')
    comps['flow_stack'].stackon('create')
    top = comps['flow_stack'].get_flow()
    top.slots['type'].assign_one('draft')

    state = make_state()
    context = make_context('make me something')
    tools = make_tool_stub({})  # create_post must not be called

    frame = policy.execute(state, context, tools)

    assert_frame(frame, origin='create')
    assert comps['ambiguity'].present()
    assert comps['ambiguity'].level == 'specific'
    assert comps['ambiguity'].metadata == {'missing_slot': 'title'}


def test_create_duplicate_title_confirmation():
    """Duplicate title declares 'confirmation' with
    duplicate_title metadata and an observation carrying the human-readable
    question, and returns origin=flow.name() carrying the same metadata."""
    policy, comps = build_policy('create')
    comps['flow_stack'].stackon('create')
    top = comps['flow_stack'].get_flow()
    top.slots['title'].add_one('Kitty Hawk')
    top.slots['type'].assign_one('draft')

    state = make_state()
    context = make_context('create a draft called Kitty Hawk')
    tools = make_tool_stub({
        'create_post': [{'_success': False, '_error': 'duplicate'}],
    })

    frame = policy.execute(state, context, tools)

    assert_frame(frame, origin='create',
                 metadata={'duplicate_title': 'Kitty Hawk'})

    amb = comps['ambiguity']
    assert amb.present()
    assert amb.level == 'confirmation', (
        "duplicate-title must be classified as 'confirmation', not 'specific'"
    )
    assert amb.metadata == {'duplicate_title': 'Kitty Hawk'}


def test_create_tool_failure_returns_error_frame():
    """Per fixes/create.md / inventory/create.md § Frame shape — the generic
    (non-duplicate) tool failure path keeps origin='create' with a thoughts
    message built from `_message` (or a fallback), no card block, and no
    ambiguity declared."""
    policy, comps = build_policy('create')
    comps['flow_stack'].stackon('create')
    top = comps['flow_stack'].get_flow()
    top.slots['title'].add_one('Kitty Hawk')
    top.slots['type'].assign_one('draft')

    state = make_state()
    context = make_context('create a draft called Kitty Hawk')
    tools = make_tool_stub({
        'create_post': [{'_success': False, '_message': 'db error'}],
    })

    frame = policy.execute(state, context, tools)

    assert_frame(frame, origin='create', thoughts_contains='db error')
    assert not frame.blocks, 'no card block on failure path'
    assert not comps['ambiguity'].present(), (
        'generic failure path must not declare ambiguity'
    )
    assert state.active_post is None
