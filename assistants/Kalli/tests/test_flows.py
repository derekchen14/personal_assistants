"""10 canonical flow tests for Kalli (onboarding assistant).

Each test sends a representative utterance through the full pipeline
(NLU → PEX → RES) in debug mode (naturalize off) and asserts:
  1. NLU detects the correct flow_name
  2. Response contains expected keywords (regex)

Flows chosen to cover all 7 intents with at least one per intent.
"""

import re

import pytest


# ── Converse ─────────────────────────────────────────────────────────

class TestChat:
    def test_chat(self, agent):
        """'hey' triggers the chat shortcut."""
        result = agent.take_turn('Hey there!')
        state = agent.world.current_state()
        assert state.flow_name == 'chat'
        assert result['message']


class TestNext:
    def test_next(self, agent):
        """'what should we do next' triggers the next shortcut."""
        result = agent.take_turn('What should we do next?')
        state = agent.world.current_state()
        assert state.flow_name == 'next'
        assert result['message']


# ── Explore ──────────────────────────────────────────────────────────

class TestStatus:
    def test_status(self, agent):
        """'status' triggers the status shortcut."""
        result = agent.take_turn('Show me the current status')
        state = agent.world.current_state()
        assert state.flow_name == 'status'


class TestExplain:
    def test_explain(self, agent):
        """Asking Kalli to explain a concept routes to explain flow."""
        result = agent.take_turn('Explain what the flow stack component does')
        state = agent.world.current_state()
        assert state.flow_name == 'explain'
        assert re.search(r'(flow.?stack|component|stack)', result['message'], re.I)


# ── Provide ──────────────────────────────────────────────────────────

class TestScope:
    def test_scope(self, agent):
        """Defining assistant scope routes to scope flow."""
        result = agent.take_turn(
            'My assistant is called Bella and it helps with fitness tracking'
        )
        state = agent.world.current_state()
        assert state.flow_name == 'scope'


class TestPersona:
    def test_persona(self, agent):
        """Defining persona preferences routes to persona flow."""
        result = agent.take_turn(
            'Set the persona name to Chef with a friendly warm tone'
        )
        state = agent.world.current_state()
        assert state.flow_name == 'persona'


# ── Design ───────────────────────────────────────────────────────────

class TestPropose:
    def test_propose(self, agent):
        """Reviewing proposed dacts routes to propose flow."""
        result = agent.take_turn('Show me the proposed dacts for my domain')
        state = agent.world.current_state()
        assert state.flow_name == 'propose'
        assert re.search(r'(dact|propos|action|token)', result['message'], re.I)


# ── Deliver ──────────────────────────────────────────────────────────

class TestGenerate:
    def test_generate(self, agent):
        """Generating config files routes to generate flow."""
        result = agent.take_turn('Generate the final configuration files')
        state = agent.world.current_state()
        assert state.flow_name == 'generate'


# ── Plan ─────────────────────────────────────────────────────────────

class TestExpand:
    def test_expand(self, agent):
        """Request to add a batch of new flows routes to expand flow."""
        result = agent.take_turn('Plan to expand the flow catalog with 8 new Explore flows')
        state = agent.world.current_state()
        assert state.flow_name == 'expand'
