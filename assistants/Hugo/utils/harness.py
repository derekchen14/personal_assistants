"""Shared test/eval harness — build an orchestrator-path Agent and seed/clean posts.

Used by the Observability Traces recorder (utils/traces/parity/record_traces.py) and the E2E Agent
Evaluations runner (utils/evals/run_evals.py). Importing this flips schemas.config.EVAL_HARNESS
and loads .env, matching the recorder's environment. This is the canonical copy those two
share; the parity CLI scripts (run_parity / smoke_openings / capture_oracle) keep their own
_build_agent variants.
"""
import sys
from pathlib import Path

_HUGO_ROOT = Path(__file__).resolve().parents[1]
if str(_HUGO_ROOT) not in sys.path:
    sys.path.insert(0, str(_HUGO_ROOT))

from dotenv import load_dotenv
load_dotenv(_HUGO_ROOT / '.env')

import schemas.config
schemas.config.EVAL_HARNESS = True

from utils.traces.parity.capture_oracle import _clean_leftovers   # canonical cleanup helper

_CRASH_FALLBACK = 'Something went wrong on my end. Please try again.'
_LOOP_FALLBACK = "I wasn't able to finish that. Could you try rephrasing?"
_TURN_TIMEOUT_SEC = 240.0


def _build_agent():
    """Orchestrator-path Agent with debug=True (matches the parity runners)."""
    from schemas.config import load_config
    import backend.agent as agent_mod
    orig_load = agent_mod.load_config
    agent_mod.load_config = lambda: load_config(overrides={'debug': True})
    agent = agent_mod.Agent(username='trace_user')
    agent_mod.load_config = orig_load
    return agent


def _seed_post(post_id:str, title:str, sections:dict):
    """Create a draft with real prose in every section (idempotent across re-runs)."""
    from backend.utilities.services import PostService, ContentService
    _clean_leftovers(post_id, title)
    service = PostService()
    # A crashed run can leave the draft file on disk with no metadata entry; the orphan would
    # make create_post refuse with 'duplicate', so remove it before seeding.
    orphan = service._content_dir / 'drafts' / (service._slugify(title) + '.md')
    orphan.unlink(missing_ok=True)
    created = service.create_post(title, sections=list(sections), post_id=post_id)
    if not created['_success']:
        raise RuntimeError(f"seeding {post_id} failed: {created['_message']}")
    content = ContentService()
    for sec_id, prose in zip(created['section_ids'], sections.values()):
        content.revise_content(post_id, sec_id, prose)
