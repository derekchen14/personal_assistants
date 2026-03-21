import sys
from pathlib import Path

import pytest

# Ensure the Dana assistant root is on sys.path so bare imports work
# (e.g. `from config import load_config`, `from backend.modules.nlu import NLU`)
_DANA_ROOT = Path(__file__).resolve().parent.parent
if str(_DANA_ROOT) not in sys.path:
    sys.path.insert(0, str(_DANA_ROOT))

from schemas.config import load_config
from backend.agent import Agent


@pytest.fixture
def config():
    return load_config(overrides={'debug': True})


@pytest.fixture
def agent(monkeypatch):
    """Create an Agent with debug=True so RES skips naturalize."""
    monkeypatch.setattr(
        'schemas.config.load_config',
        lambda: load_config(overrides={'debug': True}),
    )
    a = Agent(username='test_user')
    yield a
    a.close()
