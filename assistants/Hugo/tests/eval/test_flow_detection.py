import json
from pathlib import Path

import pytest

EVAL_PATH = Path(__file__).parent / 'flow_detection.json'
CONVERSATIONS = json.loads(EVAL_PATH.read_text())

ACCURACY_THRESHOLD = 0.60
CONFIDENCE_FLOOR = 0.3


def _agent_turns(convo):
    return [t for t in convo['turns'] if t['role'] == 'agent']


def _user_turns(convo):
    return [t for t in convo['turns'] if t['role'] == 'user']


def _detect_flow(agent, utterance):
    agent.world.context.add_turn('User', utterance)
    state = agent.nlu.understand(utterance)
    agent.world.insert_state(state)
    return state


class TestFirstTurnFlowAccuracy:

    def test_first_turn_flow_accuracy(self, agent):
        correct = 0
        total = len(CONVERSATIONS)

        for convo in CONVERSATIONS:
            agent.reset()
            first_utterance = convo['turns'][0]['utterance']
            expected_flow = _agent_turns(convo)[0]['actions'][0]['flow']

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


class TestMultiTurnFlowAccuracy:

    def test_multi_turn_flow_accuracy(self, agent):
        correct = 0
        total = 0

        for convo in CONVERSATIONS:
            agent.reset()
            user_turns = _user_turns(convo)
            agent_turns_list = _agent_turns(convo)

            for i, user_turn in enumerate(user_turns):
                state = _detect_flow(agent, user_turn['utterance'])

                expected_flow = agent_turns_list[i]['actions'][0]['flow']
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
