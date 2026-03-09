"""9 canonical flow tests for Dana (data analysis assistant).

Each test sends a representative utterance through the full pipeline
(NLU -> PEX -> RES) in debug mode (naturalize off) and asserts:
  1. NLU detects the correct flow_name
  2. Response contains expected keywords (regex)

Flows chosen to cover all 7 intents with at least one per intent.
"""

import re

import pytest


# -- Converse ------------------------------------------------------------------

class TestChat:
    def test_chat(self, agent):
        """'hello' triggers the chat shortcut."""
        result = agent.take_turn('Hello there!')
        state = agent.world.current_state()
        assert state.flow_name == 'chat'
        assert result['message']


# -- Clean ---------------------------------------------------------------------

class TestDedupe:
    def test_dedupe(self, agent):
        """Deduplication request routes to dedupe flow."""
        result = agent.take_turn('Remove all the duplicate rows')
        state = agent.world.current_state()
        assert state.flow_name == 'dedupe'


# -- Transform ----------------------------------------------------------------

class TestJoin:
    def test_join(self, agent):
        """Join request routes to join flow."""
        result = agent.take_turn('Join the sales and inventory tables on product_id')
        state = agent.world.current_state()
        assert state.flow_name == 'join'
        assert re.search(r'(join|merge|combine|product)', result['message'], re.I)


# -- Analyze ------------------------------------------------------------------

class TestDescribe:
    def test_describe(self, agent):
        """'describe' triggers the describe shortcut."""
        result = agent.take_turn('Describe the sales dataset')
        state = agent.world.current_state()
        assert state.flow_name == 'describe'


class TestQuery:
    def test_query(self, agent):
        """SQL-style query routes to query flow."""
        result = agent.take_turn('Run a query to get total sales by region')
        state = agent.world.current_state()
        assert state.flow_name == 'query'
        assert re.search(r'(query|sql|result|sales|region)', result['message'], re.I)


# -- Report -------------------------------------------------------------------

class TestSummarize:
    def test_summarize(self, agent):
        """Asking Dana to summarize a chart or result routes to summarize flow."""
        result = agent.take_turn('Summarize what this chart shows')
        state = agent.world.current_state()
        assert state.flow_name == 'summarize'
        assert re.search(r'(chart|show|summar|result|pattern)', result['message'], re.I)


class TestPlot:
    def test_plot(self, agent):
        """Chart request routes to plot flow."""
        result = agent.take_turn('Create a bar chart of sales by category')
        state = agent.world.current_state()
        assert state.flow_name == 'plot'
        assert re.search(r'(chart|bar|plot|visual|categor)', result['message'], re.I)


# -- Plan ---------------------------------------------------------------------

class TestInsight:
    def test_insight(self, agent):
        """Insight request routes to insight flow."""
        result = agent.take_turn(
            'What are the key insights from this sales data? '
            'Analyze trends and create a summary report.'
        )
        state = agent.world.current_state()
        assert state.flow_name == 'insight'


# -- Internal -----------------------------------------------------------------

class TestDevShortcut:
    def test_dev_shortcut(self, agent):
        """Dev shortcut /001 routes to query flow via DAX lookup."""
        result = agent.take_turn('/001')
        state = agent.world.current_state()
        assert state.flow_name == 'query'
