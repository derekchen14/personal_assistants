"""Shared fixtures for the deterministic module test files (nlu_unit_tests / pex_unit_tests /
mem_unit_tests). Merges the former top-level utils/conftest.py in, so all test setup lives here:
sys.path + .env + EVAL_HARNESS, the llm marker, the config/agent/mock_agent/cleanup fixtures, and the
tier fixtures (minimal config, PromptEngineer, tmp sessions root, tmp database, scripted acting-loop
agent). Per-file fixtures stay in their own file.
"""
import json
import os
import sys
from pathlib import Path
from types import MappingProxyType
from unittest.mock import MagicMock

import pytest
from dotenv import load_dotenv

# This file lives at utils/evaluation_suite/_tests/conftest.py — Hugo root is 3 up.
_HUGO_ROOT = Path(__file__).resolve().parents[3]
if str(_HUGO_ROOT) not in sys.path:
    sys.path.insert(0, str(_HUGO_ROOT))

load_dotenv(_HUGO_ROOT / '.env')

# Marker for downstream services to tag artifacts produced during evals.
import schemas.config
schemas.config.EVAL_HARNESS = True


def pytest_configure(config):
    config.addinivalue_line('markers', 'llm: requires real LLM API calls (slow, costs money)')


from schemas.config import load_config
from backend.agent import Agent
from backend.components.prompt_engineer import PromptEngineer
from backend.utilities.post_service import PostService


# ── Agent fixtures (formerly utils/conftest.py) ───────────────────────
@pytest.fixture
def config():
    return load_config(overrides={'debug': True})


@pytest.fixture
def agent(monkeypatch):
    """Create an Agent with debug=True so RES skips naturalize."""
    monkeypatch.setattr('backend.agent.load_config', lambda: load_config(overrides={'debug': True}))
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
    monkeypatch.setattr('backend.agent.load_config', lambda: load_config(overrides={'debug': True}))
    a = Agent(username='test_user')
    a.engineer.tool_call = _stub_tool_call
    a.engineer._call_claude = _stub_call_claude
    yield a
    a.close()


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


# ── Tier fixtures ─────────────────────────────────────────────────────
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
        'limits': {'max_rounds': 8, 'max_corrective': 3, 'max_tool_calls': 8,
                   'extended_tool_calls': 16,
                   'extended_call_flows': ['audit', 'refine', 'rework', 'compose']},
    })


@pytest.fixture
def engineer(minimal_config):
    return PromptEngineer(minimal_config)


@pytest.fixture
def sessions_dir(tmp_path, monkeypatch):
    """Redirect the module-level sessions root to a tmp dir (same pattern as tmp_db)."""
    from backend.components import world as world_mod
    path = tmp_path / 'sessions'
    monkeypatch.setattr(world_mod, '_SESSIONS_DIR', path)
    return path


@pytest.fixture
def orch_agent(sessions_dir, monkeypatch):
    """Agent with a tmp sessions root and scripted LLM calls. NLU.understand is stubbed to a
    no-op so the Flow gate stays hermetic — these tests exercise PEX.execute (the acting loop),
    not ensemble detection; the belief stays at its session defaults."""
    monkeypatch.setattr('backend.agent.load_config', lambda: load_config(overrides={'debug': True}))
    agent = Agent(username='test_user')
    agent.nlu.understand = lambda *args, **kwargs: None
    yield agent
    agent.close()


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """Set up a temporary database directory for service tests."""
    db = tmp_path / 'database'
    content = db / 'content'
    (content / 'drafts').mkdir(parents=True)
    (content / 'notes').mkdir(parents=True)
    (content / 'posts').mkdir(parents=True)
    snapshots = db / '.snapshots'
    snapshots.mkdir(parents=True)
    guides = db / 'guides'
    guides.mkdir(parents=True)
    meta = content / 'metadata.json'
    meta.write_text(json.dumps({'entries': []}))
    import backend.utilities.services as svc
    monkeypatch.setattr(svc, '_DB_DIR', db)
    return db
