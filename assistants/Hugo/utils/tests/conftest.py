import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from dotenv import load_dotenv

# Ensure the Hugo assistant root is on sys.path so bare imports work
_HUGO_ROOT = Path(__file__).resolve().parents[2]
if str(_HUGO_ROOT) not in sys.path:
    sys.path.insert(0, str(_HUGO_ROOT))

load_dotenv(_HUGO_ROOT / '.env')


def pytest_configure(config):
    config.addinivalue_line('markers', 'llm: requires real LLM API calls (slow, costs money)')

from schemas.config import load_config
from backend.agent import Agent


@pytest.fixture
def config():
    return load_config(overrides={'debug': True})


@pytest.fixture
def agent(monkeypatch):
    """Create an Agent with debug=True so RES skips naturalize."""
    monkeypatch.setattr(
        'backend.agent.load_config',
        lambda: load_config(overrides={'debug': True}),
    )
    a = Agent(username='test_user')
    yield a
    a.close()


def _stub_tool_call(messages, tools, tool_dispatcher, *,
                    system=None, task='skill', max_rounds=10, max_tokens=4096):
    """Return a stub text response with no tool calls."""
    return '[stub] LLM response for testing.', []


def _stub_call_claude(system, messages, model_id, *, tools=None, max_tokens=4096):
    """Return a stub anthropic-like Message."""
    text_block = MagicMock()
    text_block.type = 'text'
    text_block.text = '[stub] LLM response for testing.'
    msg = MagicMock()
    msg.content = [text_block]
    msg.stop_reason = 'end_turn'
    return msg


@pytest.fixture
def mock_agent(monkeypatch):
    """Agent with LLM calls stubbed out — tests routing without API keys."""
    monkeypatch.setattr(
        'backend.agent.load_config',
        lambda: load_config(overrides={'debug': True}),
    )
    a = Agent(username='test_user')
    a.engineer.tool_call = _stub_tool_call
    a.engineer._call_claude = _stub_call_claude
    yield a
    a.close()


from backend.utilities.post_service import PostService

_SYNTH_TITLE = 'Synthetic Data Generation for Classification'


@pytest.fixture(scope='module')
def cleanup_synth_post():
    """Teardown-only fixture: deletes the synthetic data post after the eval module."""
    yield
    svc = PostService()
    result = svc.find_posts(query='synthetic data generation')
    if result.get('_success'):
        for item in result.get('items', []):
            if item.get('title') == _SYNTH_TITLE:
                svc.delete_post(item['post_id'])
