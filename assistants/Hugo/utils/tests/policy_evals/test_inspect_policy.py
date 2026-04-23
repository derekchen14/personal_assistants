"""Policy-in-isolation tests for the `inspect` flow.

Inspect is fully deterministic after Theme 3 — the policy calls
`inspect_post` directly, writes the metrics to scratchpad under the
standard envelope (version / turn_number / used_count / payload), and
returns a metrics-bearing frame. See `utils/policy_builder/fixes/inspect.md`
and `utils/policy_builder/inventory/inspect.md` for the expected shape.
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


# `resolve_post_id` takes the 8-char shortcut when len(identifier) == 8,
# verifying the id via a read_metadata call before returning.
_POST_ID = 'abcd1234'


def _read_metadata_ok(post_id:str=_POST_ID) -> dict:
    return {
        '_success': True,
        'post_id': post_id,
        'title': 'Expectation Maximization',
        'status': 'draft',
        'section_ids': [],
    }


def test_inspect_happy_path_writes_scratchpad():
    """Per fixes/inspect.md § Changes that landed — happy path returns
    origin='inspect' with metrics in metadata, marks flow Completed, and
    writes the standard scratchpad envelope (version/turn_number/used_count)
    plus post_id and metrics."""
    policy, comps = build_policy('inspect')
    comps['flow_stack'].stackon('inspect')
    top = comps['flow_stack'].get_flow()
    top.slots['source'].add_one(post=_POST_ID)
    top.slots['aspect'].assign_one('word_count')

    state = make_state()
    context = make_context('how long is this draft', turn_id=3)
    tool_responses = {
        'read_metadata': [_read_metadata_ok()],
        'inspect_post': [{
            '_success': True,
            'word_count': 1234,
            'section_count': 5,
            'estimated_read_time': 6,
            'image_count': 2,
            'link_count': 4,
        }],
    }
    tools = capture_tool_log(make_tool_stub(tool_responses))

    frame = policy.execute(state, context, tools)

    # Frame invariants — origin + metadata.metrics. Inspect narrates in
    # chat and does not emit a block.
    assert_frame(frame, origin='inspect')
    metrics = frame.metadata['metrics']
    for key in ('word_count', 'section_count', 'estimated_read_time',
                'image_count', 'link_count'):
        assert key in metrics, f'metrics missing {key!r}'
    assert metrics['word_count'] == 1234
    assert metrics['section_count'] == 5

    active_flow = comps['flow_stack'].get_flow()
    assert active_flow.status == 'Completed'

    # Scratchpad envelope
    pad = comps['memory'].read_scratchpad('inspect')
    assert pad['version'] == '1'
    assert pad['turn_number'] == context.turn_id
    assert pad['used_count'] == 0
    assert pad['post_id'] == _POST_ID
    assert pad['metrics']['word_count'] == 1234

    # inspect_post should have been called with the aspect as the metrics filter
    inspect_calls = [entry for entry in tools.log if entry['name'] == 'inspect_post']
    assert len(inspect_calls) == 1
    assert inspect_calls[0]['params']['metrics'] == ['word_count']


def test_inspect_missing_source_declares_ambiguity():
    """Per inventory/inspect.md § Guard clauses — missing source slot declares
    specific ambiguity with missing_slot=<entity_slot> and returns a default
    DisplayFrame (no origin, no metrics)."""
    policy, comps = build_policy('inspect')
    comps['flow_stack'].stackon('inspect')
    top = comps['flow_stack'].get_flow()
    top.slots['aspect'].assign_one('word_count')
    # source intentionally left empty

    state = make_state()
    context = make_context('how long is it')
    tools = make_tool_stub({})  # no tool should be called

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
    scratchpad write, no ambiguity declared, flow is not marked Completed."""
    policy, comps = build_policy('inspect')
    comps['flow_stack'].stackon('inspect')
    top = comps['flow_stack'].get_flow()
    top.slots['source'].add_one(post=_POST_ID)
    top.slots['aspect'].assign_one('word_count')

    state = make_state()
    context = make_context('how long is this', turn_id=4)
    tools = make_tool_stub({
        'read_metadata': [_read_metadata_ok()],
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
