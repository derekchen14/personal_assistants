"""Policy-in-isolation tests for the `inspect` flow.

Inspect is fully deterministic after Theme 3 — the policy calls `inspect_post` directly, writes the
metrics to scratchpad under the standard envelope (version / turn_number / used_count / payload),
and returns a metrics-bearing frame. See `utils/policy_builder/fixes/inspect.md` and
`utils/policy_builder/inventory/inspect.md` for the expected shape.

Pillar 2b: tools dispatch to real services on a tmp_path-isolated DB. The
synthetic-failure test keeps make_tool_stub since real inspect_post on a valid
post won't naturally produce `{_success: False, _message: 'file not found'}`.
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


def _seed_post(title='Expectation Maximization', body=None):
    from backend.utilities.services import PostService, ContentService
    post_id = PostService().create_post(title=title, type='draft')['post_id']
    if body:
        ContentService().generate_outline(post_id, body)
    return post_id


def test_inspect_happy_path_writes_scratchpad(monkeypatch, tmp_path):
    """Per fixes/inspect.md § Changes that landed — happy path returns
    origin='inspect' with metrics in metadata, marks flow Completed, and
    writes the standard scratchpad envelope (version/turn_number/used_count)
    plus post_id and metrics."""
    tools = real_tools(monkeypatch, tmp_path)
    post_id = _seed_post(body='## Intro\n\nSome text here for word counting.\n')

    policy, comps = build_policy('inspect')
    comps['flow_stack'].stackon('inspect')
    top = comps['flow_stack'].get_flow()
    top.slots['source'].add_one(post=post_id)
    top.slots['aspect'].assign_one('word_count')

    state = make_state()
    context = make_context('how long is this draft', turn_id=3)

    frame = policy.execute(state, context, tools)

    # Frame invariants — origin + metadata.metrics. Inspect narrates in
    # chat and does not emit a block.
    assert_frame(frame, origin='inspect')
    metrics = frame.metadata['metrics']
    assert 'word_count' in metrics
    assert metrics['word_count'] >= 0

    active_flow = comps['flow_stack'].get_flow()
    assert active_flow.status == 'Completed'

    # Scratchpad envelope
    pad = comps['memory'].read_scratchpad('inspect')
    assert pad['version'] == '1'
    assert pad['turn_number'] == context.turn_id
    assert pad['used_count'] == 0
    assert pad['post_id'] == post_id
    assert 'word_count' in pad['metrics']

    # inspect_post should have been called with the aspect as the metrics filter
    inspect_calls = [entry for entry in tools.log if entry['name'] == 'inspect_post']
    assert len(inspect_calls) == 1
    assert inspect_calls[0]['params']['metrics'] == ['word_count']


def test_inspect_missing_source_declares_ambiguity(monkeypatch, tmp_path):
    """Per inventory/inspect.md § Guard clauses — missing source slot declares
    specific ambiguity with missing_slot=<entity_slot> and returns a default
    DisplayFrame (no origin, no metrics)."""
    tools = real_tools(monkeypatch, tmp_path)
    policy, comps = build_policy('inspect')
    comps['flow_stack'].stackon('inspect')
    top = comps['flow_stack'].get_flow()
    top.slots['aspect'].assign_one('word_count')
    # source intentionally left empty

    state = make_state()
    context = make_context('how long is it')

    frame = policy.execute(state, context, tools)

    assert_frame(frame, origin='inspect')
    assert not frame.blocks
    assert not frame.metadata

    amb = comps['ambiguity']
    assert amb.present()
    assert amb.level == 'partial'
    assert amb.metadata == {'missing_entity': 'post'}

    active_flow = comps['flow_stack'].get_flow()
    assert active_flow.status != 'Completed', (
        'flow must not be marked Completed when guard returns early'
    )


def test_inspect_tool_failure_returns_error_frame():
    """A failing inspect_post call returns an error frame with
    origin=flow.name() and metadata['violation']='tool_error'. No
    scratchpad write, no ambiguity declared, flow is not marked Completed.

    Synthetic-failure case: real inspect_post on a valid post doesn't naturally
    produce `_success: False`. Keep make_tool_stub for this one branch.
    """
    _POST_ID = 'abcd1234'
    policy, comps = build_policy('inspect')
    comps['flow_stack'].stackon('inspect')
    top = comps['flow_stack'].get_flow()
    top.slots['source'].add_one(post=_POST_ID)
    top.slots['aspect'].assign_one('word_count')

    state = make_state()
    context = make_context('how long is this', turn_id=4)
    tools = make_tool_stub({
        'read_metadata': [{
            '_success': True, 'post_id': _POST_ID,
            'title': 'Expectation Maximization', 'status': 'draft', 'section_ids': [],
        }],
        'inspect_post': [{
            '_success': False,
            '_message': 'post file not found on disk',
        }],
    })

    frame = policy.execute(state, context, tools)

    assert_frame(frame, origin='inspect',
                 thoughts_contains='post file not found on disk',
                 metadata={'violation': 'tool_error', 'failed_tool': 'inspect_post'})
    assert not frame.blocks

    assert comps['memory'].read_scratchpad('inspect') == '', (
        'no scratchpad write on tool failure'
    )
    assert not comps['ambiguity'].present(), (
        'tool failure surfaces as an error frame, not ambiguity'
    )
    active_flow = comps['flow_stack'].get_flow()
    assert active_flow.status != 'Completed'
