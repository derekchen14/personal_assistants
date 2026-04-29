"""Policy-in-isolation tests for the `create` flow.

Create is a deterministic flow (no `llm_execute`); the policy calls
`create_post` directly and returns a card frame on success or an error
frame on duplicate / failure. See `utils/policy_builder/fixes/create.md`
and `utils/policy_builder/inventory/create.md` for the expected shape.

Pillar 2b: tools dispatch to real services on a tmp_path-isolated DB.
The synthetic-failure test below keeps make_tool_stub because real services
won't naturally produce a generic `{'_success': False, '_message': 'db error'}`.
"""

from __future__ import annotations

from utils.tests.policy_evals.fixtures import (
    assert_frame,
    build_policy,
    make_context,
    make_state,
    make_tool_stub,
    real_tools,
)


def test_create_filled_slots_happy_path(monkeypatch, tmp_path):
    """Per fixes/create.md § Changes that landed — success path sets origin='create',
    adds a card block, marks flow Completed, and syncs state.active_post."""
    tools = real_tools(monkeypatch, tmp_path)
    policy, comps = build_policy('create')
    comps['flow_stack'].stackon('create')
    top = comps['flow_stack'].get_flow()
    top.slots['title'].add_one('The Wright Brothers Diary')
    top.slots['type'].assign_one('draft')

    state = make_state()
    context = make_context('create a new draft about the Wright brothers')

    frame = policy.execute(state, context, tools)

    assert_frame(frame, origin='create', block_types=('card',))
    card = frame.blocks[0]
    assert card.data['title'] == 'The Wright Brothers Diary'
    assert card.data['status'] == 'draft'
    # Real service generates the post_id; just assert it is set + non-empty.
    assert card.data['post_id'] and len(card.data['post_id']) >= 6

    active_flow = comps['flow_stack'].get_flow()
    assert active_flow.name() == 'create'
    assert active_flow.status == 'Completed'
    assert state.active_post == card.data['post_id']
    assert len(tools.log) == 1 and tools.log[0]['name'] == 'create_post'


def test_create_with_topic_does_not_auto_chain_outline(monkeypatch, tmp_path):
    """A topic on create_policy does NOT auto-stackon('outline'). The user
    must explicitly request an outline as the next turn."""
    tools = real_tools(monkeypatch, tmp_path)
    policy, comps = build_policy('create')
    comps['flow_stack'].stackon('create')
    top = comps['flow_stack'].get_flow()
    top.slots['title'].add_one('The Wright Brothers Diary')
    top.slots['type'].assign_one('draft')
    top.slots['topic'].add_one('early aviation experiments')

    state = make_state()
    context = make_context('create a draft about early aviation')

    frame = policy.execute(state, context, tools)

    assert_frame(frame, origin='create', block_types=('card',))
    assert state.keep_going is False

    active = comps['flow_stack'].get_flow()
    assert active.name() == 'create', 'create_policy should not stack outline'
    assert active.status == 'Completed'


def test_create_missing_title_declares_specific_ambiguity(monkeypatch, tmp_path):
    """Per fixes/create.md / inventory/create.md § Guard clauses — missing
    title triggers declare('specific', metadata={'missing_slot': 'title'}) and
    an early-return DisplayFrame('error')."""
    tools = real_tools(monkeypatch, tmp_path)
    policy, comps = build_policy('create')
    comps['flow_stack'].stackon('create')
    top = comps['flow_stack'].get_flow()
    top.slots['type'].assign_one('draft')

    state = make_state()
    context = make_context('make me something')

    frame = policy.execute(state, context, tools)

    assert_frame(frame, origin='create')
    assert comps['ambiguity'].present()
    assert comps['ambiguity'].level == 'specific'
    assert comps['ambiguity'].metadata == {'missing_slot': 'title'}
    # No tool calls must fire on early-return guard.
    assert tools.log == []


def test_create_duplicate_title_confirmation(monkeypatch, tmp_path):
    """Duplicate title declares 'confirmation' with duplicate_title metadata.
    Real services enforce uniqueness — a second create with the same title
    naturally returns the duplicate error the policy handles."""
    tools = real_tools(monkeypatch, tmp_path)
    # Pre-seed: a real post already exists with this title, so the second
    # create_post call will hit the duplicate path.
    from backend.utilities.services import PostService
    PostService().create_post(title='Kitty Hawk', type='draft')

    policy, comps = build_policy('create')
    comps['flow_stack'].stackon('create')
    top = comps['flow_stack'].get_flow()
    top.slots['title'].add_one('Kitty Hawk')
    top.slots['type'].assign_one('draft')

    state = make_state()
    context = make_context('create a draft called Kitty Hawk')

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
    ambiguity declared.

    Synthetic-failure case: the real PostService doesn't naturally produce a
    generic `db error` so this test keeps `make_tool_stub` for that one branch.
    """
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
