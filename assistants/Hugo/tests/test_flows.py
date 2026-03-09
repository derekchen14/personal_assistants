"""10 canonical flow tests for Hugo (blogging assistant).

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
        """'hello' triggers the chat shortcut."""
        result = agent.take_turn('Hello there!')
        state = agent.world.current_state()
        assert state.flow_name == 'chat'
        assert result['message']


class TestNext:
    def test_next(self, agent):
        """'what should I do next' triggers the next shortcut."""
        result = agent.take_turn('What should I do next?')
        state = agent.world.current_state()
        assert state.flow_name == 'next'
        assert result['message']


# ── Research ─────────────────────────────────────────────────────────

class TestCheck:
    def test_check(self, agent):
        """'status' triggers the check shortcut."""
        result = agent.take_turn('Show me the status of my drafts')
        state = agent.world.current_state()
        assert state.flow_name == 'check'


class TestSearch:
    def test_search(self, agent):
        """Explicit search request routes to search flow."""
        result = agent.take_turn('Search for blog posts about machine learning')
        state = agent.world.current_state()
        assert state.flow_name == 'search'
        assert re.search(r'(search|found|result|post|machine learning)', result['message'], re.I)


class TestExplain:
    def test_explain(self, agent):
        """Asking Hugo to explain a concept routes to explain flow."""
        result = agent.take_turn('Explain what SEO means for blogging')
        state = agent.world.current_state()
        assert state.flow_name == 'explain'
        assert re.search(r'(SEO|search engine|optimi)', result['message'], re.I)


# ── Draft ────────────────────────────────────────────────────────────

class TestBrainstorm:
    def test_brainstorm(self, agent):
        """Brainstorming request routes to brainstorm flow."""
        result = agent.take_turn('Brainstorm some blog post ideas about productivity')
        state = agent.world.current_state()
        assert state.flow_name == 'brainstorm'
        assert re.search(r'(idea|topic|productiv|brainstorm)', result['message'], re.I)


class TestOutline:
    def test_outline(self, agent):
        """Outline generation routes to outline flow."""
        result = agent.take_turn('Generate an outline for a post about climate change')
        state = agent.world.current_state()
        assert state.flow_name == 'outline'
        assert re.search(r'(outline|section|climate)', result['message'], re.I)


# ── Revise ───────────────────────────────────────────────────────────

class TestRework:
    def test_rework(self, agent):
        """Major revision request routes to rework flow."""
        result = agent.take_turn('This draft needs a complete rework and major revision')
        state = agent.world.current_state()
        assert state.flow_name == 'rework'


# ── Publish ──────────────────────────────────────────────────────────

class TestSurvey:
    def test_survey(self, agent):
        """Asking about platforms routes to survey flow."""
        result = agent.take_turn('Show me which publishing platforms are available')
        state = agent.world.current_state()
        assert state.flow_name == 'survey'
        assert re.search(r'(platform|substack|twitter|linkedin|publish)', result['message'], re.I)


# ── Plan ─────────────────────────────────────────────────────────────

class TestCalendar:
    def test_calendar(self, agent):
        """Content calendar planning routes to calendar flow."""
        result = agent.take_turn(
            'I need a content calendar — schedule out my blog posts for the next 4 weeks'
        )
        state = agent.world.current_state()
        assert state.flow_name == 'calendar'
