"""Policy-in-isolation tests for the `find` flow.

Find is fully deterministic after its skill file was deleted: the policy expands the query (via a
small LLM helper that we mock here), calls `find_posts` per term, dedupes by post_id, and always
renders one list block. See `utils/policy_builder/fixes/find.md` and
`utils/policy_builder/inventory/find.md` for the expected shape.

Pillar 2b: tools dispatch to real services on a tmp_path-isolated DB. The dedup
test keeps `make_tool_stub` because it needs three controlled result sets for
three expanded query terms — hard to reproduce with seeded data.
"""

from __future__ import annotations

from backend.modules.policies.research import ResearchPolicy

from utils.tests.policy_evals.fixtures import (
    assert_frame,
    build_policy,
    capture_tool_log,
    make_context,
    make_state,
    make_tool_stub,
    real_tools,
)


def test_find_single_item_emits_list_block_only(monkeypatch, tmp_path):
    """Per fixes/find.md § Single list block — when results include only
    one item, the frame still has exactly one list block and no card
    fallback."""
    tools = real_tools(monkeypatch, tmp_path)
    from backend.utilities.services import PostService
    PostService().create_post(title='Wright Brothers Diary', type='draft')

    policy, comps = build_policy('find')
    comps['flow_stack'].stackon('find')
    top = comps['flow_stack'].get_flow()
    top.slots['query'].add_one('wright brothers')

    monkeypatch.setattr(ResearchPolicy, '_expand_query',
        lambda self, query: ['wright brothers'])

    state = make_state()
    context = make_context('find posts about the Wright brothers')

    frame = policy.execute(state, context, tools)

    assert_frame(frame, origin='find', block_types=('list',))
    block = frame.blocks[0]
    assert len(block.data['items']) >= 1
    assert any('wright' in (it.get('title') or '').lower() for it in block.data['items'])
    assert top.status == 'Completed'


def test_find_scratchpad_write_shape(monkeypatch, tmp_path):
    """Scratchpad write contract — after find completes, scratchpad['find']
    has version/turn_number/used_count/query plus `items` with 4-field
    shape (post_id, title, status, preview)."""
    tools = real_tools(monkeypatch, tmp_path)
    from backend.utilities.services import PostService
    PostService().create_post(title='Flight', type='draft')
    PostService().create_post(title='Gliders', type='draft')

    policy, comps = build_policy('find')
    comps['flow_stack'].stackon('find')
    top = comps['flow_stack'].get_flow()
    top.slots['query'].add_one('flight')

    monkeypatch.setattr(ResearchPolicy, '_expand_query',
        lambda self, query: ['flight'])

    state = make_state()
    context = make_context('find aviation posts', turn_id=5)

    policy.execute(state, context, tools)

    pad = comps['memory'].read_scratchpad('find')
    assert pad['version'] == '1'
    assert pad['turn_number'] == context.turn_id
    assert pad['used_count'] == 0
    assert pad['query'] == 'flight'
    assert len(pad['items']) >= 1
    expected_keys = {'post_id', 'title', 'status', 'preview'}
    for entry in pad['items']:
        assert set(entry.keys()) == expected_keys


def test_find_dedupes_across_expanded_terms(monkeypatch):
    """Per fixes/find.md § Single list block — when expansion produces
    multiple terms that return overlapping items, the policy dedupes by
    post_id. Synthetic test: keeps make_tool_stub for control over the
    three-call return shapes that real find_posts can't easily reproduce."""
    policy, comps = build_policy('find')
    comps['flow_stack'].stackon('find')
    top = comps['flow_stack'].get_flow()
    top.slots['query'].add_one('machine learning')

    monkeypatch.setattr(ResearchPolicy, '_expand_query',
        lambda self, query: ['machine learning', 'ML', 'deep learning'])

    first_call = [
        {'post_id': 'p1', 'title': 'ML Basics', 'status': 'published',
         'preview': 'intro'},
        {'post_id': 'p2', 'title': 'Deep Nets', 'status': 'draft',
         'preview': 'layers'},
    ]
    second_call = [
        {'post_id': 'p1', 'title': 'ML Basics', 'status': 'published',
         'preview': 'intro'},
        {'post_id': 'p3', 'title': 'Regression', 'status': 'published',
         'preview': 'linear'},
    ]
    third_call = [
        {'post_id': 'p2', 'title': 'Deep Nets', 'status': 'draft',
         'preview': 'layers'},
    ]

    state = make_state()
    context = make_context('find ML posts')
    tools = capture_tool_log(make_tool_stub({
        'find_posts': [
            {'_success': True, 'items': first_call},
            {'_success': True, 'items': second_call},
            {'_success': True, 'items': third_call},
        ],
    }))

    frame = policy.execute(state, context, tools)

    assert_frame(frame, origin='find', block_types=('list',))
    ids = [it['post_id'] for it in frame.blocks[0].data['items']]
    assert ids == ['p1', 'p2', 'p3'], 'deduped while preserving first-seen order'
    assert len([e for e in tools.log if e['name'] == 'find_posts']) == 3
