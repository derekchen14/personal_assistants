"""Shared fixtures for the deterministic module test files (nlu_unit_tests / pex_unit_tests /
mem_unit_tests). Home for fixtures used by more than one file: the minimal config, a PromptEngineer,
the tmp sessions root, the tmp database, and the scripted acting-loop agent. Per-file fixtures stay
in their own file. (utils/conftest.py above adds mock_agent / agent / config / sys.path.)
"""
import json
from types import MappingProxyType

import pytest

from backend.components.prompt_engineer import PromptEngineer
from schemas.config import load_config
from backend.agent import Agent


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
    monkeypatch.setattr('backend.agent.load_config', lambda: load_config(
        overrides={'debug': True}))
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
    # Write a minimal metadata.json
    meta = content / 'metadata.json'
    meta.write_text(json.dumps({'entries': []}))
    # Monkeypatch the module-level _DB_DIR; ToolService.__init__ derives the rest
    import backend.utilities.services as svc
    monkeypatch.setattr(svc, '_DB_DIR', db)
    return db


