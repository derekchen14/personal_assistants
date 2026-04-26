"""Model tests — measure NLU flow detection accuracy with real LLM calls.

Covers:
  - First-turn flow accuracy from eval dataset (5 conversations)
  - Multi-turn flow accuracy from eval dataset
  - Confidence score validation
  - Canonical flow detection across all 7 intents (10 representative utterances)

Requires API keys. Mark all tests with @pytest.mark.llm. Run with: pytest tests/model_tests.py -m
llm -v Skip with: pytest -m "not llm"
"""

import json
import re
from pathlib import Path
import pytest

EVAL_PATH = Path(__file__).parent / 'test_cases.json'
CONVERSATIONS = json.loads(EVAL_PATH.read_text())

ACCURACY_THRESHOLD = 0.60
CONFIDENCE_FLOOR = 0.3

llm = pytest.mark.llm


def _user_turns(convo):
    return [t for t in convo['turns'] if t['role'] == 'user']


def _detect_flow(agent, utterance):
    agent.world.context.add_turn('User', utterance, 'utterance')
    state = agent.nlu.understand(utterance, agent.world.context)
    agent.world.insert_state(state)
    return state


# ═══════════════════════════════════════════════════════════════════
# Eval dataset: flow detection accuracy
# ═══════════════════════════════════════════════════════════════════

@llm
class TestFirstTurnFlowAccuracy:

    def test_first_turn_flow_accuracy(self, agent):
        correct = 0
        total = len(CONVERSATIONS)

        for convo in CONVERSATIONS:
            agent.reset()
            first_utterance = convo['turns'][0]['utterance']
            expected_flow = _user_turns(convo)[0]['labels']['flow']

            state = _detect_flow(agent, first_utterance)
            detected = state.flow_name
            confidence = state.confidence

            hit = detected == expected_flow
            correct += int(hit)
            mark = 'PASS' if hit else 'FAIL'
            print(
                f"  [{mark}] convo={convo['convo_id']} "
                f"expected={expected_flow} detected={detected} "
                f"confidence={confidence:.2f}"
            )

        accuracy = correct / total
        print(f"\n  First-turn accuracy: {correct}/{total} = {accuracy:.0%}")
        assert accuracy >= ACCURACY_THRESHOLD, (
            f"First-turn accuracy {accuracy:.0%} below {ACCURACY_THRESHOLD:.0%}"
        )


@llm
class TestConfidenceScoresMeaningful:

    def test_confidence_above_floor(self, agent):
        below_floor = []

        for convo in CONVERSATIONS:
            agent.reset()
            first_utterance = convo['turns'][0]['utterance']

            state = _detect_flow(agent, first_utterance)
            confidence = state.confidence

            if confidence <= CONFIDENCE_FLOOR:
                below_floor.append((convo['convo_id'], confidence))

            print(
                f"  convo={convo['convo_id']} "
                f"flow={state.flow_name} confidence={confidence:.2f}"
            )

        assert not below_floor, (
            f"Conversations with confidence <= {CONFIDENCE_FLOOR}: "
            + ", ".join(f"{cid} ({c:.2f})" for cid, c in below_floor)
        )


@llm
class TestMultiTurnFlowAccuracy:

    def test_multi_turn_flow_accuracy(self, agent):
        correct = 0
        total = 0

        for convo in CONVERSATIONS:
            agent.reset()
            user_turns = _user_turns(convo)

            for i, user_turn in enumerate(user_turns):
                state = _detect_flow(agent, user_turn['utterance'])

                expected_flow = user_turn['labels']['flow']
                detected = state.flow_name
                confidence = state.confidence

                hit = detected == expected_flow
                correct += int(hit)
                total += 1
                mark = 'PASS' if hit else 'FAIL'
                print(
                    f"  [{mark}] convo={convo['convo_id']} "
                    f"turn={user_turn['turn_count']} "
                    f"expected={expected_flow} detected={detected} "
                    f"confidence={confidence:.2f}"
                )

        accuracy = correct / total
        print(f"\n  Multi-turn accuracy: {correct}/{total} = {accuracy:.0%}")
        assert accuracy >= ACCURACY_THRESHOLD, (
            f"Multi-turn accuracy {accuracy:.0%} below {ACCURACY_THRESHOLD:.0%}"
        )


# ═══════════════════════════════════════════════════════════════════
# Canonical flow detection: 10 utterances across 7 intents
# ═══════════════════════════════════════════════════════════════════

@llm
class TestCanonicalFlowDetection:
    """Full NLU → PEX → RES pipeline with real LLM. One test per intent minimum."""

    def test_chat(self, agent):
        result = agent.take_turn('Hello there!')
        state = agent.world.current_state()
        assert state.flow_name == 'chat'
        assert result['message']

    def test_suggest(self, agent):
        result = agent.take_turn('What should I do next?')
        state = agent.world.current_state()
        assert state.flow_name == 'suggest'
        assert result['message']

    def test_check(self, agent):
        agent.take_turn('Show me the status of my drafts')
        state = agent.world.current_state()
        assert state.flow_name == 'check'

    def test_find(self, agent):
        result = agent.take_turn('Search for blog posts about machine learning')
        state = agent.world.current_state()
        assert state.flow_name == 'find'
        assert re.search(r'(search|found|result|post|machine learning)', result['message'], re.I)

    def test_explain(self, agent):
        result = agent.take_turn('Why did you restructure the outline that way?')
        state = agent.world.current_state()
        assert state.flow_name == 'explain'
        assert result['message']

    def test_brainstorm(self, agent):
        result = agent.take_turn('Brainstorm some blog post ideas about productivity')
        state = agent.world.current_state()
        assert state.flow_name == 'brainstorm'
        assert re.search(r'(idea|topic|productiv|brainstorm)', result['message'], re.I)

    def test_outline(self, agent):
        result = agent.take_turn('Generate an outline for a post about climate change')
        state = agent.world.current_state()
        assert state.flow_name == 'outline'
        assert re.search(r'(outline|section|climate)', result['message'], re.I)

    def test_rework(self, agent):
        agent.take_turn('This draft needs a complete rework and major revision')
        state = agent.world.current_state()
        assert state.flow_name == 'rework'

    def test_survey(self, agent):
        result = agent.take_turn('Show me which publishing platforms are available')
        state = agent.world.current_state()
        assert state.flow_name == 'survey'
        assert re.search(r'(platform|channel|substack|twitter|linkedin|publish)', result['message'], re.I)

    def test_calendar(self, agent):
        agent.take_turn(
            'I need a content calendar — schedule out my blog posts for the next 4 weeks'
        )
        state = agent.world.current_state()
        assert state.flow_name == 'calendar'
