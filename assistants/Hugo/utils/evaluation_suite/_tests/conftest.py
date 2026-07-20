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
from backend.assistant import Assistant
from backend.components.prompt_engineer import PromptEngineer
from backend.utilities.post_service import PostService


# ── Agent fixtures (formerly utils/conftest.py) ───────────────────────
@pytest.fixture
def config():
    return load_config(overrides={'debug': True})


@pytest.fixture
def agent(monkeypatch):
    """Create an Agent with debug=True so RES skips naturalize."""
    monkeypatch.setattr('backend.assistant.load_config', lambda: load_config(overrides={'debug': True}))
    a = Assistant(username='test_user')
    yield a
    a.close()


def _stub_tool_call(messages, tools, call_tool, *,
                    system=None, task='skill', max_rounds=10, max_tokens=4096):
    """Return a stub text response with no tool calls."""
    return '[stub] LLM response for testing.', []


def _stub_call_claude(system, messages, model_id, *, tools=None, max_tokens=4096, schema_dict=None):
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
    monkeypatch.setattr('backend.assistant.load_config', lambda: load_config(overrides={'debug': True}))
    a = Assistant(username='test_user')
    a.engineer.flow_execute = _stub_tool_call
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
        'limits': {'max_rounds': 8, 'max_corrective': 3, 'max_reads': 3, 'max_tool_calls': 8,
                   'extended_tool_calls': 16,
                   'extended_call_flows': ['audit', 'refine', 'rework', 'compose']},
        'session': {'max_flow_depth': 16},
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


@pytest.fixture(autouse=True)
def memory_dir(tmp_path, monkeypatch):
    """Redirect the per-account L2 store root to a tmp dir so no test (or Assistant construction)
    reads or writes the real database/memory/."""
    from backend.components import user_preferences as prefs_mod
    path = tmp_path / 'memory'
    monkeypatch.setattr(prefs_mod, '_MEMORY_DIR', path)
    return path


@pytest.fixture
def orch_agent(sessions_dir, monkeypatch):
    """Agent with a tmp sessions root and scripted LLM calls. NLU think/react are stubbed to
    no-ops so the Flow gate stays hermetic — these tests exercise the PEX-Agent rounds
    (orchestrate), not ensemble detection. classify_intent is stubbed to write the same belief
    the real one writes (round 2.16): prepare() reads pred_flows for the prediction note."""
    monkeypatch.setattr('backend.assistant.load_config', lambda: load_config(overrides={'debug': True}))
    agent = Assistant(username='test_user')
    agent.nlu.think = lambda *args, **kwargs: None

    from utils.helper import dax2flow, flow2dax
    from schemas.ontology import FLOW_ONTOLOGY

    def _classify(*args, **kwargs):  # NLU 1 stays hermetic — a fixed Converse hint
        state = agent.nlu.dialogue_state
        state.pred_intent = 'Converse'
        state.pred_flows = [{'name': 'chat', 'dax': flow2dax('chat'), 'confidence': 0.5}]
        return 'Converse'
    agent.nlu.dialogue_state.classify_intent = _classify

    def _react(dax, payload={}):  # the real react minus the LLM slot fill: stack + belief
        name = dax2flow(dax)
        stack = agent.pex.flow_stack
        curr_flow = stack.get_flow()
        if not (curr_flow and curr_flow.status == 'Active' and curr_flow.name() == name):
            stack.stackon(name)
        state = agent.nlu.dialogue_state
        state.pred_intent = FLOW_ONTOLOGY[name]['intent']
        state.pred_flows = [{'name': name, 'dax': dax, 'confidence': 0.99}]
    agent.nlu.react = _react
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
