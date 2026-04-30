"""NLU module-level golden tests.

One parameterized test exercises NLU.react(gold_dax, payload) across the distinct
slot-fill contracts in the codebase. Each row supplies the input plus a Phase 3
LLM mock value and asserts on the post-react flow state.

phase3_slots semantics:
  - dict (e.g. {'title': 'X'}): mock engineer returns {'slots': dict} for fill_slots.
  - {} (empty dict): mock engineer returns empty (failure-mode case).
  - None: Phase 3 LLM must NOT fire — engineer raises if called.

This file replaces the per-test routing in TestReact for the NLU.react contract.
"""

from __future__ import annotations

from types import MappingProxyType
from unittest.mock import MagicMock

import pytest

from backend.modules.nlu import NLU
from backend.components.prompt_engineer import PromptEngineer
from backend.components.ambiguity_handler import AmbiguityHandler
from backend.components.world import World


@pytest.fixture
def minimal_config():
    return MappingProxyType({
        'models': {
            'default': {
                'provider': 'anthropic',
                'model_id': 'claude-sonnet-4-5-20250929',
                'temperature': 0.0,
            },
            'overrides': {},
        },
        'resilience': {},
    })


@pytest.fixture
def nlu(minimal_config):
    """Live World + NLU with a real PromptEngineer that we then replace per-test
    via _stub_engineer. Seeds the context with a User action turn so Phase 1c
    (last_user_turn.turn_type == 'action') is exercisable by default."""
    engineer = PromptEngineer(minimal_config)
    ambiguity = AmbiguityHandler(minimal_config, engineer=engineer)
    world = World(minimal_config)
    world.context.add_turn('User', '', turn_type='action')
    return NLU(minimal_config, ambiguity, engineer, world)


def _stub_engineer(nlu, monkeypatch, phase3_slots):
    """Replace nlu.engineer. dict → mock returns {'slots': dict}; None → raises."""
    real_apply = nlu.engineer.apply_guardrails
    if phase3_slots is None:
        mock = MagicMock(side_effect=AssertionError(
            'Phase 3 LLM was called when it should have been skipped'))
    else:
        mock = MagicMock(return_value={'slots': phase3_slots})
    mock.apply_guardrails = real_apply
    monkeypatch.setattr(nlu, 'engineer', mock)


def _slot_observable(slot):
    """Canonical observable value of a slot, regardless of slot type.
    Used to compare against the row's `slots` expectation."""
    if hasattr(slot, 'level') and slot.level is not None:
        return slot.level
    if slot.criteria == 'multiple':
        return slot.values
    return slot.value


def _matches(actual, expected) -> bool:
    """List-of-dicts: expected items are subset matches of actual at same index.
    SourceSlot stores all 5 keys (post/sec/snip/chl/ver) per entry; the test row
    only specifies the ones it cares about."""
    if isinstance(expected, list) and expected and isinstance(expected[0], dict):
        if not isinstance(actual, list) or len(actual) != len(expected):
            return False
        return all(
            all(a.get(k) == v for k, v in e.items())
            for a, e in zip(actual, expected)
        )
    return actual == expected


# ── Test cases ──────────────────────────────────────────────────────────────
# (name, gold_dax, payload, phase3_slots, expected_flow, is_filled, slots, extras)
# - slots: dict of slot_name → expected observable value (omit slots not asserted)
# - extras: optional dict with post-react checks (e.g. dispatch-not-called)

NLU_REACT_CASES = [
    {
        'name': 'create_action_full_payload',
        'gold_dax': '{05A}',
        'payload': {'type': 'draft', 'title': 'My Post'},
        'phase3_slots': None,  # Phase 3 must not fire
        'expected_flow': 'create',
        'is_filled': True,
        'slots': {'title': 'My Post', 'type': 'draft'},
    },
    {
        'name': 'create_action_partial_phase3_completes',
        'gold_dax': '{05A}',
        'payload': {'type': 'draft'},
        'phase3_slots': {'title': 'LLM-Provided'},
        'expected_flow': 'create',
        'is_filled': True,
        'slots': {'title': 'LLM-Provided', 'type': 'draft'},
    },
    {
        'name': 'create_action_partial_phase3_empty_failure_mode',
        'gold_dax': '{05A}',
        'payload': {'type': 'draft'},
        'phase3_slots': {},  # LLM returns empty — title stays unfilled
        'expected_flow': 'create',
        'is_filled': False,
        'slots': {'type': 'draft'},
    },
    {
        'name': 'create_context_only_payload_skips_dispatch',
        'gold_dax': '{05A}',
        'payload': {'post': '17be00f6'},  # entity-only key, no slots to fill
        'phase3_slots': {'title': 'L', 'type': 'draft'},  # Phase 3 will fire
        'expected_flow': 'create',
        'is_filled': True,
        'slots': {'title': 'L'},
        'extras': {'dispatch_not_called': True},  # Phase 1c skipped
    },
    {
        'name': 'refine_snippet_payload_phase1a',
        'gold_dax': '{02B}',
        'payload': {'snippet': 'matrix mult', 'post': 'post_abc', 'section': 'sec_xyz'},
        'phase3_slots': {'feedback': ['tighten the prose']},
        'expected_flow': 'refine',
        'is_filled': True,
        'slots': {'source': [{'post': 'post_abc', 'sec': 'sec_xyz', 'snip': 'matrix mult'}]},
    },
    {
        'name': 'find_snippet_payload_phase1b',
        'gold_dax': '{001}',
        'payload': {'snippet': 'matrix mult'},
        'phase3_slots': None,  # query filled by Phase 1b, find has no other required
        'expected_flow': 'find',
        'is_filled': True,
        'slots': {'query': 'matrix mult'},
    },
    {
        'name': 'outline_proposal_payload_custom_unpack',
        'gold_dax': '{002}',
        'payload': {'proposals': [[
            {'name': 'Intro', 'description': 'open cold'},
            {'name': 'Body', 'description': 'key argument'},
        ]]},
        # Phase 1c fills sections via outline-specific unpack. Source still
        # required → Phase 3 fires to provide it.
        'phase3_slots': {'source': [{'post': 'post_abc'}]},
        'expected_flow': 'outline',
        'is_filled': True,
        'slots': {},
        'extras': {'sections_count': 2},
    },
    {
        'name': 'release_no_payload_partial_phase3',
        'gold_dax': '{04A}',
        'payload': {},
        'phase3_slots': {},  # no entity → Phase 3 fires but returns empty
        'expected_flow': 'release',
        'is_filled': False,
        'slots': {},
    },
    {
        'name': 'chat_no_slots_no_payload',
        'gold_dax': '{000}',
        'payload': {},
        'phase3_slots': None,  # ChatFlow has empty self.slots — is_filled True, no LLM
        'expected_flow': 'chat',
        'is_filled': True,
        'slots': {},
    },
    {
        'name': 'inspect_action_phase1a_then_phase3_for_aspect',
        'gold_dax': '{1BD}',
        # Phase 1a/1c are mutually exclusive (elif chain): with both entity AND
        # non-entity keys, Phase 1a wins and aspect is left for Phase 3.
        'payload': {'post': 'post_abc', 'aspect': 'word_count'},
        'phase3_slots': {'aspect': 'word_count'},
        'expected_flow': 'inspect',
        'is_filled': True,
        'slots': {'aspect': 'word_count', 'source': [{'post': 'post_abc'}]},
    },
    {
        'name': 'audit_action_with_post',
        'gold_dax': '{13A}',
        'payload': {'post': 'post_abc'},
        'phase3_slots': None,  # audit.source filled, other slots optional
        'expected_flow': 'audit',
        'is_filled': True,
        'slots': {'source': [{'post': 'post_abc'}]},
    },
    {
        'name': 'phase2_grounding_uses_active_post',
        'gold_dax': '{02B}',  # refine
        'payload': {},
        'phase3_slots': {'feedback': ['x'], 'steps': [{'name': 'X', 'description': 'y'}]},
        'expected_flow': 'refine',
        'is_filled': True,
        'slots': {},  # source backfilled from active_post — checked via extras
        'extras': {'source_post_id': 'active-post-id'},
    },
    {
        'name': 'polish_action_with_section_partial',
        'gold_dax': '{3BD}',
        'payload': {'post': 'post_abc', 'section': 'sec_one'},
        'phase3_slots': {},  # polish has more than just source required; stays unfilled
        'expected_flow': 'polish',
        'is_filled': False,
        'slots': {'source': [{'post': 'post_abc', 'sec': 'sec_one'}]},
    },
]


@pytest.mark.parametrize('case', NLU_REACT_CASES, ids=lambda c: c['name'])
def test_nlu_react(nlu, monkeypatch, case):
    # Set active_post for the Phase 2 row. _build_state copies it forward to the
    # new state, so Phase 2's `prev = self.world.current_state()` sees it.
    if case['name'] == 'phase2_grounding_uses_active_post':
        nlu.world.current_state().active_post = 'active-post-id'

    # Optional dispatch-skip assertion needs to wrap unpack_user_actions BEFORE react.
    extras = case.get('extras', {})
    if extras.get('dispatch_not_called'):
        dispatch_mock = MagicMock(wraps=nlu.unpack_user_actions)
        monkeypatch.setattr(nlu, 'unpack_user_actions', dispatch_mock)
    else:
        dispatch_mock = None

    _stub_engineer(nlu, monkeypatch, case['phase3_slots'])
    nlu.react(case['gold_dax'], case['payload'])
    flow = nlu.flow_stack.get_flow()

    assert flow.flow_type == case['expected_flow'], (
        f"flow_type expected {case['expected_flow']!r} got {flow.flow_type!r}")
    assert flow.is_filled() == case['is_filled'], (
        f"is_filled expected {case['is_filled']} got {flow.is_filled()}")

    for slot_name, expected in case['slots'].items():
        actual = _slot_observable(flow.slots[slot_name])
        assert _matches(actual, expected), (
            f"slot {slot_name!r} expected {expected!r} got {actual!r}")

    # Extras
    if dispatch_mock is not None:
        dispatch_mock.assert_not_called()
    if 'sections_count' in extras:
        assert len(flow.slots['sections'].steps) == extras['sections_count']
    if 'source_post_id' in extras:
        src = flow.slots['source'].values
        assert any(v.get('post') == extras['source_post_id'] for v in src), (
            f'source slot missing post={extras["source_post_id"]!r}; got {src!r}')
