"""NLU tool-entry isolated tests — detect_and_fill with real LLM calls.

Exercises the orchestrator tool entry (changes.md §4.1, decision 18) on recorded
utterances from the parity oracle fixtures (utils/tests/parity/fixtures/*.json).
NLU is built in isolation (no Agent, no PEX/RES); each row adds the user turn to
context (the orchestrator pre-hook contract), calls detect_and_fill, and asserts
on the returned data — plus that the tool mutated neither the flow stack nor the
state list (the orchestrator persists via write_state, not the tool).

Requires API keys. Run with: pytest utils/tests/test_nlu_tool.py -m llm -v -s
Not part of the free tier (unit_tests.py + test_artifacts.py).
"""

from __future__ import annotations

import pytest

from backend.modules.nlu import NLU
from backend.components.ambiguity_handler import AmbiguityHandler
from backend.components.prompt_engineer import PromptEngineer
from backend.components.world import World
from schemas.config import load_config

llm = pytest.mark.llm


@pytest.fixture
def nlu():
    # Non-debug config: a single truncated ensemble voter degrades gracefully
    # (warn + skip) as in production, instead of re-raising and flaking the test.
    config = load_config()
    engineer = PromptEngineer(config)
    ambiguity = AmbiguityHandler(config, engineer=engineer)
    world = World(config)
    return NLU(config, ambiguity, engineer, world)


# ── Test cases ──────────────────────────────────────────────────────────────
# Utterances recorded by the parity oracle (scenario + step noted per row).
# - intent: the orchestrator's hint; None exercises the no-hint default (active
#   flow's intent on a continuing turn — `stacked` names the flow pushed first)
# - filled_slots: slot names that must appear in result['slots']
# - entity: subset-match against result['entities'][0] (payload extraction path)

TOOL_CASES = [
    {
        'name': 'create_with_draft_hint',  # observability step 1
        'utterance': 'Create a new post about Observability for Long-Running AI Agents',
        'intent': 'Draft',
        'payload': None,
        'expected_flow': 'create',
        'filled_slots': ['title'],
        'entity': None,
    },
    {
        'name': 'polish_no_hint_continuing_turn',  # voice step 13
        'utterance': ('Give the Takeaways section another polish pass — lean on the findings '
                      'from the earlier check'),
        'intent': None,
        'stacked': 'polish',  # no hint → intent defaults from the active flow
        'payload': None,
        'expected_flow': 'polish',
        'filled_slots': [],
        'entity': None,
    },
    {
        'name': 'refine_payload_entity_extraction',  # voice step 4
        'utterance': ('Add bullets to the outline. Under Process, add: pick a speech-to-text '
                      'frontend, wire it to the planner, and evaluate latency budgets.'),
        'intent': 'Revise',
        'payload': {'post': 'post_abc', 'section': 'sec_one'},
        'expected_flow': 'refine',
        'filled_slots': ['source'],
        'entity': {'post': 'post_abc', 'sec': 'sec_one'},
    },
    {
        'name': 'release_with_publish_hint',  # voice step 14
        'utterance': 'Publish the voice capabilities post',
        'intent': 'Publish',
        'payload': None,
        'expected_flow': 'release',
        'filled_slots': [],
        'entity': None,
    },
]


@llm
@pytest.mark.parametrize('case', TOOL_CASES, ids=lambda c: c['name'])
def test_detect_and_fill(nlu, case):
    if case.get('stacked'):
        nlu.flow_stack.stackon(case['stacked'])
    nlu.world.context.add_turn('User', case['utterance'], 'utterance')
    stack_before = nlu.flow_stack.stack_size()
    states_before = len(nlu.world.states)
    top_slots_before = nlu.flow_stack.get_flow().slot_values_dict() if stack_before else None

    result = nlu.detect_and_fill(case['utterance'], intent=case['intent'],
                                 payload=case['payload'])
    print(f"  [{case['name']}] flow={result['flow_name']} "
          f"confidence={result['confidence']:.2f} slots={list(result['slots'])}")

    # Data shape: predicted flow, confidence, ranked candidates, slots, entities.
    assert result['flow_name'] == case['expected_flow'], (
        f"expected {case['expected_flow']!r} got {result['flow_name']!r}")
    assert 0.0 < result['confidence'] <= 1.0

    candidates = result['candidates']
    assert candidates and candidates[0]['flow_name'] == result['flow_name']
    scores = [cand['confidence'] for cand in candidates]
    assert scores == sorted(scores, reverse=True), f'candidates not ranked: {scores}'

    for slot_name in case['filled_slots']:
        assert slot_name in result['slots'], (
            f"slot {slot_name!r} missing from {list(result['slots'])}")
    if case['entity']:
        first = result['entities'][0]
        for key, val in case['entity'].items():
            assert first[key] == val, f'entity {key!r}: expected {val!r} got {first[key]!r}'

    # Data only — the tool must not push flows, insert states, or fill live flows.
    assert nlu.flow_stack.stack_size() == stack_before
    assert len(nlu.world.states) == states_before
    if stack_before:
        assert nlu.flow_stack.get_flow().slot_values_dict() == top_slots_before
