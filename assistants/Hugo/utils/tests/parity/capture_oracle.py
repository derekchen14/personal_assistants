"""Phase 0 oracle capture for the orchestrator parity harness (changes.md §9.1 / §10).

Runs the OLD NLU→PEX→RES pipeline on the existing 14-step E2E scenarios and records, per
turn: final utterance, artifact block summary (block_type + sorted data keys + panel), and
the grounded entity (state.active_post). At the end of each scenario it records the DB end
state (title / status / section content / outline shape). The recordings are saved as JSON
fixtures under `utils/tests/parity/fixtures/` — the oracle the new orchestrator is compared
against via `comparator.py`. The old pipeline never needs to re-run for comparisons.

Scenario definitions are imported from `e2e_agent_evals.py` — never duplicated here.

Run from the Hugo root, one half at a time (E2E two-halves strategy):
  python utils/tests/parity/capture_oracle.py --scenario vision --half 1
  python utils/tests/parity/capture_oracle.py --scenario vision --half 2
"""

import argparse
import json
import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime
from pathlib import Path

_HUGO_ROOT = Path(__file__).resolve().parents[3]
if str(_HUGO_ROOT) not in sys.path:
    sys.path.insert(0, str(_HUGO_ROOT))

from dotenv import load_dotenv

load_dotenv(_HUGO_ROOT / '.env')
os.environ['HUGO_EVAL_MODE'] = '1'

from utils.tests.e2e_agent_evals import (
    STEPS_VISION, STEPS_OBSERVABILITY, STEPS_VOICE, _BaseScenarioE2E,
    _VISION_POST_ID, _OBS_POST_ID, _VOICE_POST_ID, _drain_orphan_active_flows,
)
from utils.tests.parity.comparator import FIXTURE_DIR, capture_db_state

SCENARIOS = {
    'vision': (STEPS_VISION, _VISION_POST_ID, 'Using Multi-modal Models to Improve AI Agents'),
    'observability': (STEPS_OBSERVABILITY, _OBS_POST_ID, 'Observability for Long-Running AI Agents'),
    'voice': (STEPS_VOICE, _VOICE_POST_ID, 'Adding Voice Capabilities to AI Agents'),
}
_TURN_TIMEOUT_SEC = 60.0
# Agent.take_turn's top-level safety-net message. A turn that returns it crashed (e.g. the
# known fill_slots model-degeneration flake) and gets ONE retry — the e2e
# retry-with-diagnostic discipline. A turn that fails twice stays in the fixture as-is.
_CRASH_FALLBACK = 'Something went wrong on my end. Please try again.'


def _build_agent():
    """Old-pipeline Agent with debug=True, mirroring _BaseScenarioE2E._get_agent."""
    from schemas.config import load_config
    import backend.agent as agent_mod
    orig_load = agent_mod.load_config
    agent_mod.load_config = lambda: load_config(overrides={'debug': True})
    agent = agent_mod.Agent(username='test_user')
    agent_mod.load_config = orig_load
    return agent


def _clean_leftovers(post_id:str, title:str):
    """Delete leftover eval posts by id and by title (see test_step_01_create)."""
    from backend.utilities.services import PostService
    svc = PostService()
    svc.delete_post(post_id)
    for entry in svc.list_preview().get('items', []):
        if entry.get('title', '').lower() == title.lower():
            svc.delete_post(entry['post_id'])


def _seed_part2(agent, post_id:str, title:str):
    """Reuse the e2e part-2 seeding (active_post + synthetic history) via a shim subclass."""
    shim = type('OracleShim', (_BaseScenarioE2E,),
                {'_test_post_id': post_id, '_post_title_default': title, '_agent': agent})
    shim._seed_part2_context()


def _run_turn(agent, step_def:dict) -> dict:
    """Run one scenario turn through the old pipeline; record the oracle axes."""
    _drain_orphan_active_flows(agent, step_def['flow'])
    pre_hook = step_def.get('pre_hook')
    if pre_hook:
        pre_hook(agent)
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(agent.take_turn, step_def['utterance'],
                                 dax=step_def['dax'], payload=step_def.get('payload'))
        try:
            result = future.result(timeout=_TURN_TIMEOUT_SEC)
            timed_out = False
        except FuturesTimeoutError:
            result = {'message': '', 'artifact': None}
            timed_out = True
    duration = round(time.perf_counter() - start, 1)
    artifact = result['artifact'] or {'blocks': []}
    blocks = [{'type': blk['type'], 'data_keys': sorted(blk['data'].keys()), 'panel': blk['panel']}
              for blk in artifact['blocks']]
    state = agent.world.current_state()
    return {'step': step_def['step'], 'flow': step_def['flow'], 'dax': step_def['dax'],
            'user': step_def['utterance'], 'utterance': result['message'], 'blocks': blocks,
            'active_post': state.active_post, 'timed_out': timed_out, 'duration_sec': duration}


def _run_step1(agent, step_def:dict, post_id:str) -> dict:
    """Pin uuid4 so the created post gets the fixed test id (see test_step_01_create)."""
    orig_uuid4 = uuid.uuid4
    uuid.uuid4 = lambda: type('', (), {'__str__': lambda fake: post_id + '-0000-0000'})()
    try:
        return _run_turn(agent, step_def)
    finally:
        uuid.uuid4 = orig_uuid4


def _run_step(agent, step_def:dict, post_id:str) -> dict:
    if step_def['step'] == 1:
        return _run_step1(agent, step_def, post_id)
    if step_def['step'] == 14:
        from backend.utilities.services import PostService
        PostService().update_post(post_id, {'status': 'draft'})
    return _run_turn(agent, step_def)


def _capture_half(agent, half_steps:list, post_id:str) -> list:
    turns = []
    for step_def in half_steps:
        turn = _run_step(agent, step_def, post_id)
        if turn['utterance'] == _CRASH_FALLBACK or turn['timed_out']:
            print(f"  step {step_def['step']:02d} crashed — retrying once")
            turn = _run_step(agent, step_def, post_id)
        turns.append(turn)
        flag = ' [TIMED OUT]' if turn['timed_out'] else ''
        print(f"  step {turn['step']:02d} [{turn['flow']}] {turn['duration_sec']:>6.1f}s{flag} "
              f"blocks={[blk['type'] for blk in turn['blocks']]} active_post={turn['active_post']}")
    return turns


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario', required=True, choices=sorted(SCENARIOS))
    parser.add_argument('--half', required=True, type=int, choices=(1, 2))
    args = parser.parse_args()

    steps, post_id, title = SCENARIOS[args.scenario]
    FIXTURE_DIR.mkdir(exist_ok=True)
    fixture_path = FIXTURE_DIR / f'{args.scenario}.json'
    print(f'Capturing oracle: scenario={args.scenario} half={args.half} post_id={post_id}')

    agent = _build_agent()
    if args.half == 1:
        _clean_leftovers(post_id, title)
        turns = _capture_half(agent, steps[:7], post_id)
        # create_post slices the pinned uuid to 8 chars, so the on-disk id is the create
        # turn's grounded entity (e.g. 'VisionPo'), not the scenario constant ('VisionPost').
        actual_id = turns[0]['active_post'] or post_id
        fixture = {'scenario': args.scenario, 'pipeline': 'old', 'post_id': actual_id,
                   'captured_at': datetime.now().isoformat(timespec='seconds'), 'turns': turns}
    else:
        if not fixture_path.exists():
            sys.exit(f'{fixture_path} missing — run half 1 first')
        fixture = json.loads(fixture_path.read_text())
        actual_id = fixture['post_id']
        _seed_part2(agent, actual_id, title)
        fixture['turns'].extend(_capture_half(agent, steps[7:], actual_id))
        fixture['captured_at'] = datetime.now().isoformat(timespec='seconds')
        fixture['db_end_state'] = capture_db_state(actual_id)
        if os.getenv('HUGO_E2E_KEEP_POSTS') != '1':
            _clean_leftovers(actual_id, title)
    agent.close()

    fixture_path.write_text(json.dumps(fixture, indent=2) + '\n')
    print(f'Wrote {fixture_path} ({len(fixture["turns"])} turns)')


if __name__ == '__main__':
    main()
