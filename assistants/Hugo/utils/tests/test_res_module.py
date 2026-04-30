"""RES module-level golden tests.

One parameterized test exercises RES.respond(frame) across the distinct template
variants and early-return branches. config['debug']=True suppresses naturalize
so no LLM call fires.

Each row constructs a state + flow + frame, calls respond, and asserts on the
returned (utterance, frame) tuple."""

from __future__ import annotations

from types import MappingProxyType

import pytest

from backend.modules.res import RES
from backend.components.world import World
from backend.components.ambiguity_handler import AmbiguityHandler
from backend.components.prompt_engineer import PromptEngineer
from backend.components.display_frame import DisplayFrame


@pytest.fixture
def res_config():
    return MappingProxyType({
        'debug': True,  # suppresses naturalize
        'models': {
            'default': {
                'provider': 'anthropic',
                'model_id': 'claude-sonnet-4-5-20250929',
                'temperature': 0.0,
            },
            'overrides': {},
        },
        'resilience': {},
        'session': {'max_flow_depth': 8},
    })


def _build_res(config):
    engineer = PromptEngineer(config)
    ambiguity = AmbiguityHandler(config, engineer=engineer)
    world = World(config)
    res = RES(config, ambiguity, engineer, world)
    return res, world, ambiguity


def _push_flow(world, flow_name:str):
    """Push a flow onto the stack and mark it Completed (so respond's start()
    pop yields it as completed_flows[-1])."""
    flow = world.flow_stack.stackon(flow_name)
    flow.status = 'Completed'
    return flow


# ── Test cases ──────────────────────────────────────────────────────────────


RES_CASES = [
    {
        'name': 'create_card_renders_title_from_slot',
        'flow_name': 'create',
        'frame_origin': 'create',
        'frame_blocks': [
            {'type': 'card', 'data': {'post_id': 'p1', 'title': 'My Post', 'status': 'draft'}},
        ],
        'frame_thoughts': '',
        'ambiguity': None,
        'state_kwargs': {},
        # create template reads `flow.slots['title'].value` directly (not frame.thoughts).
        'slot_setup': lambda flow: flow.slots['title'].add_one('My Post'),
        'utterance_contains': 'My Post',
    },
    {
        'name': 'release_toast_renders_thoughts',
        'flow_name': 'release',
        'frame_origin': 'release',
        'frame_blocks': [
            {'type': 'toast', 'data': {'message': 'Published to Medium.', 'level': 'success'}},
        ],
        'frame_thoughts': 'Published.',
        'ambiguity': None,
        'state_kwargs': {},
        'utterance_contains': 'Published',
    },
    {
        'name': 'find_list_renders_items',
        'flow_name': 'find',
        'frame_origin': 'find',
        'frame_blocks': [
            {'type': 'list', 'data': {'items': [
                {'post_id': 'p1', 'title': 'X', 'status': 'draft', 'preview': '...'},
            ]}},
        ],
        'frame_thoughts': 'Found 1 result.',
        'ambiguity': None,
        'state_kwargs': {},
        'utterance_contains': '1',
    },
    {
        'name': 'refine_template_uses_thoughts_passthrough',
        'flow_name': 'refine',
        'frame_origin': 'refine',
        'frame_blocks': [
            {'type': 'card', 'data': {'post_id': 'p1', 'title': 'X'}},
        ],
        'frame_thoughts': 'My refine thoughts',
        'ambiguity': None,
        'state_kwargs': {},
        # refine template is "{message}" → frame.thoughts passes through;
        # config.debug=True suppresses naturalize.
        'utterance_equals': 'My refine thoughts',
    },
    {
        'name': 'inspect_narrates_metrics',
        'flow_name': 'inspect',
        'frame_origin': 'inspect',
        'frame_blocks': [],
        'frame_thoughts': '',
        # inspect template reads metrics from frame.metadata
        'frame_metadata': {'metrics': {'word_count': 1234, 'num_sections': 5,
                                        'time_to_read': 6, 'image_count': 2,
                                        'num_links': 4, 'post_size': 12}},
        'ambiguity': None,
        'state_kwargs': {},
        'utterance_contains': '1,234',  # template formats with comma separator
    },
    {
        'name': 'partial_ambiguity_invokes_clarify',
        'flow_name': 'create',
        'frame_origin': '',
        'frame_blocks': [],
        'frame_thoughts': '',
        'ambiguity': ('partial', {'missing_entity': 'post'}),
        'state_kwargs': {},
        # _clarify path renders a clarification question; we just assert non-empty.
        'utterance_nonempty': True,
    },
    {
        'name': 'specific_ambiguity_lists_missing_slot',
        'flow_name': 'create',
        'frame_origin': 'create',
        'frame_blocks': [],
        'frame_thoughts': '',
        'ambiguity': ('specific', {'missing_slot': 'title'}),
        'state_kwargs': {},
        'utterance_contains': 'title',
    },
    {
        'name': 'internal_intent_returns_empty',
        'flow_name': 'recap',
        'frame_origin': 'recap',
        'frame_blocks': [],
        'frame_thoughts': '',
        'ambiguity': None,
        'state_kwargs': {},
        # Internal intent → respond returns ('', frame) early
        'utterance_equals': '',
    },
    {
        'name': 'plan_with_keep_going_returns_empty',
        'flow_name': 'blueprint',
        'frame_origin': 'blueprint',
        'frame_blocks': [],
        'frame_thoughts': '',
        'ambiguity': None,
        'state_kwargs': {'keep_going': True},
        # Plan + keep_going → respond returns ('', frame) early
        'utterance_equals': '',
    },
    {
        'name': 'syndicate_skip_naturalize_template_prefix',
        'flow_name': 'syndicate',
        'frame_origin': 'syndicate',
        'frame_blocks': [],
        'frame_thoughts': 'on Medium and Dev.to',
        'ambiguity': None,
        'state_kwargs': {},
        # template: "Cross-posted! {message}"
        'utterance_contains': 'Cross-posted',
    },
    {
        'name': 'audit_card_renders_completion',
        'flow_name': 'audit',
        'frame_origin': 'audit',
        'frame_blocks': [
            {'type': 'card', 'data': {'post_id': 'p1', 'title': 'X', 'content': 'updated'}},
        ],
        'frame_thoughts': 'Audit completed.',
        'ambiguity': None,
        'state_kwargs': {},
        'frame_metadata': {'reports': {'rework': 'rewrote intro'}},
        'utterance_contains': 'Audit',
    },
]


@pytest.mark.parametrize('case', RES_CASES, ids=lambda c: c['name'])
def test_res_respond(case, res_config):
    res, world, ambiguity = _build_res(res_config)

    flow = _push_flow(world, case['flow_name'])

    # Optional slot setup (e.g., create reads flow.slots['title'].value)
    slot_setup = case.get('slot_setup')
    if slot_setup is not None:
        slot_setup(flow)

    # State setup
    state = world.current_state()
    for k, v in case['state_kwargs'].items():
        setattr(state, k, v)

    # Frame setup
    frame = DisplayFrame(
        origin=case['frame_origin'],
        thoughts=case['frame_thoughts'],
        metadata=case.get('frame_metadata', {}),
    )
    for block in case['frame_blocks']:
        frame.add_block(block)

    # Ambiguity
    if case['ambiguity']:
        level, metadata = case['ambiguity']
        ambiguity.declare(level, metadata=metadata)

    utterance, frame_out = res.respond(frame)

    if 'utterance_equals' in case:
        assert utterance == case['utterance_equals'], (
            f'utterance expected {case["utterance_equals"]!r} got {utterance!r}')
    if 'utterance_contains' in case:
        assert case['utterance_contains'] in utterance, (
            f'utterance {utterance!r} does not contain {case["utterance_contains"]!r}')
    if case.get('utterance_nonempty'):
        assert utterance, 'expected non-empty utterance'
