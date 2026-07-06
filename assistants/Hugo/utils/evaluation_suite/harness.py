"""Shared eval harness (evaluation_suite) — build an orchestrator-path Agent, seed/clean posts, and
locate/sample the scenario corpus. Importing this flips schemas.config.EVAL_HARNESS and loads .env,
matching the eval environment. Used by the Traces runner (_traces/run_traces.py) and the model-tests
scorer (_tests/model_tests.py). Merges the former `corpus.py` locator/sampler — the shared basics
every tier needs sit in one place.
"""
import json
import random
import sys
from pathlib import Path

_SUITE_DIR = Path(__file__).resolve().parent          # utils/evaluation_suite
_HUGO_ROOT = _SUITE_DIR.parent.parent                 # Hugo assistant root
if str(_HUGO_ROOT) not in sys.path:
    sys.path.insert(0, str(_HUGO_ROOT))

from dotenv import load_dotenv
load_dotenv(_HUGO_ROOT / '.env')

import schemas.config
schemas.config.EVAL_HARNESS = True

_CRASH_FALLBACK = 'Something went wrong on my end. Please try again.'
_LOOP_FALLBACK = "I wasn't able to finish that. Could you try rephrasing?"
_TURN_TIMEOUT_SEC = 240.0


# ── Scenario corpus (formerly corpus.py) ──────────────────────────────
# The corpus is three JSONL splits under datasets/: train.jsonl (the 96 labelled conversations, one
# JSON object per line), dev.jsonl and test.jsonl (placeholders for now). We almost never run all of
# train: the DEV set is a FRESH random sample of ~8 conversations, drawn per build — not a fixed list.
# Pass feature-relevant ids explicitly with `--ids`, or take any n with `sample()`.
_DATASETS = _SUITE_DIR / 'datasets'
TRAIN = _DATASETS / 'train.jsonl'
DEV = _DATASETS / 'dev.jsonl'
TEST = _DATASETS / 'test.jsonl'
SAMPLE_SIZE = 8   # dev-set size doctrine (~8 per judgement round) — a COUNT, not a fixed set


def load_split(path:Path=TRAIN) -> dict:
    """Load a .jsonl split into an ordered {convo_id: case} dict (empty for the dev/test placeholders)."""
    cases = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            case = json.loads(line)
            cases[case['convo_id']] = case
    return cases


def all_ids() -> list:
    """Every convo_id in train, sorted (e.g. 'B01.C01')."""
    return sorted(load_split())


def sample(n:int=SAMPLE_SIZE, seed=None) -> list:
    """A fresh dev set: `n` random train ids. Prefer feature-relevant ids via `--ids`; use this when
    any `n` will do. Pass `seed` to make one build's run reproducible."""
    ids = all_ids()
    return random.Random(seed).sample(ids, min(n, len(ids)))


def load_cases(ids=None) -> list:
    """The case objects for `ids` (in that order), or the whole train split when `ids` is None."""
    split = load_split()
    return [split[cid] for cid in (ids if ids is not None else sorted(split))]


# ── Agent build / seed / clean ────────────────────────────────────────
def _clean_leftovers(post_id:str, title:str):
    """Delete leftover eval posts by id and by title (idempotent across re-runs)."""
    from backend.utilities.services import PostService
    svc = PostService()
    svc.delete_post(post_id)
    for entry in svc.list_preview().get('items', []):
        if entry.get('title', '').lower() == title.lower():
            svc.delete_post(entry['post_id'])


def _build_agent(session_id:str|None=None):
    """Orchestrator-path Agent with debug=True. Pass a `session_id` (the convo_id) to name the
    session dir after the scenario, so its transcript persists at a findable
    database/sessions/<session_id>/messages.jsonl instead of an anonymous timestamp — that file is
    the per-turn observability trace (NLU belief, tool calls, flow dispatch) read back for diagnosis."""
    from schemas.config import load_config
    import backend.agent as agent_mod
    orig_load = agent_mod.load_config
    agent_mod.load_config = lambda: load_config(overrides={'debug': True})
    agent = agent_mod.Agent(username='trace_user')
    agent_mod.load_config = orig_load
    if session_id:
        agent.world.open_session(session_id)   # bind the scenario-named dir
        agent.world.reset()                     # clear any stale run so the transcript starts fresh
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


# Flows that edit a specific existing post — a scenario opening on one assumes the post is already
# selected (grounded), the way the UI grounds a post the user clicked before NLU ever runs.
_EXISTING_CONTENT_FLOWS = {'refine', 'compose', 'rework', 'write', 'audit', 'propose',
                          'summarize', 'compare', 'release', 'schedule', 'cite'}


def seed_active_post(agent, case:dict, seeded:list):
    """Mirror a UI post selection: when a scenario opens on an existing-content flow, ground the
    seeded post it targets BEFORE the first turn, so NLU/the policy see an active post instead of a
    missing reference. Picks the seeded post matching the first turn's source, else the only one."""
    if not seeded:
        return
    first = case['turns'][0]
    stack = first['labels']['stack']
    if not stack or stack[0].get('flow') not in _EXISTING_CONTENT_FLOWS:
        return
    source = (first.get('slots') or {}).get('source') or {}
    want = source.get('post', '').lower() if isinstance(source, dict) else ''
    post_id = next((pid for pid, title in seeded if title.lower() == want), seeded[0][0])
    state = agent.world.current_state()
    state.active_post = post_id
    state.grounding['post'] = post_id
