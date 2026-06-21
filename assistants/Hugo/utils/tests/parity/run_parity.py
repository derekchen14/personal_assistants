"""Phase-4 gate runner — full 14-turn scenarios through the NEW orchestrator path.

Runs every turn of one E2E scenario on the orchestrator path and scores the run
against the Phase-0 oracle fixtures on the changes.md §9.1 axes:

  1. End-state DB checks — comparator.compare_db_end_state, after half 2
  2. Grounding           — comparator.compare_grounding, per turn
  3. Utterance judge     — comparator.judge_utterance, per turn (task adequacy vs the oracle)

Half 2 mirrors the e2e part-2 seeding (capture_oracle._seed_part2) and additionally seeds the
orchestrator's persistent message list with the same synthetic history, since the loop reads
context.messages rather than the Turn records.

Run from the Hugo root, one half at a time (E2E two-halves strategy):
  python utils/tests/parity/run_parity.py --scenario vision --half 1
  python utils/tests/parity/run_parity.py --scenario vision --half 2

Results accumulate in /tmp/parity_phase4_<scenario>.json; half 2 adds the end-state axis,
cleans up the eval post, and prunes the run's session dirs.
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

_HUGO_ROOT = Path(__file__).resolve().parents[3]
if str(_HUGO_ROOT) not in sys.path:
    sys.path.insert(0, str(_HUGO_ROOT))

from dotenv import load_dotenv

load_dotenv(_HUGO_ROOT / '.env')
os.environ['HUGO_EVAL_MODE'] = '1'

import utils.tests.parity.capture_oracle as oracle_mod
from utils.tests.parity.capture_oracle import (SCENARIOS, _clean_leftovers, _run_step,
                                               _seed_part2, _CRASH_FALLBACK)
from utils.tests.parity.comparator import (load_fixture, compare_db_end_state,
                                           compare_grounding, judge_utterance)

_LOOP_FALLBACK = "I wasn't able to finish that. Could you try rephrasing?"
oracle_mod._TURN_TIMEOUT_SEC = 180.0  # orchestrator turns run multiple LLM rounds


def _build_agent():
    """Orchestrator-path Agent: debug=True like the oracle capture."""
    from schemas.config import load_config
    import backend.agent as agent_mod
    overrides = {'debug': True}
    orig_load = agent_mod.load_config
    agent_mod.load_config = lambda: load_config(overrides=overrides)
    agent = agent_mod.Agent(username='parity_user')
    agent_mod.load_config = orig_load
    return agent


def _seed_messages(agent, post_id:str, title:str):
    """Mirror _seed_part2's synthetic Turn history onto the persistent message list."""
    from backend.utilities.services import PostService
    meta = PostService().read_metadata(post_id)
    sections = meta.get('section_ids', [])
    context = agent.world.context
    context.append_message({'role': 'user', 'content': f'Create a new post about {title}'})
    context.append_message({'role': 'assistant',
                            'content': f'Created draft "{title}" with post ID {post_id}.'})
    context.append_message({'role': 'user',
                            'content': 'Generate an outline and convert it to prose.'})
    context.append_message({'role': 'assistant', 'content': (
        f'Done. The post has {len(sections)} sections: {", ".join(sections)}. '
        f'All sections have been composed into prose, expanded, and simplified.')})


def _run_half(agent, half_steps:list, post_id:str, oracle_turns:list) -> list:
    turns = []
    for step_def, oracle_turn in zip(half_steps, oracle_turns):
        turn = _run_step(agent, step_def, post_id)
        if turn['utterance'] in (_CRASH_FALLBACK, _LOOP_FALLBACK) or turn['timed_out']:
            print(f"  step {step_def['step']:02d} failed ({turn['utterance'][:40]!r}) — retrying once")
            turn = _run_step(agent, step_def, post_id)
        turn['crashed'] = turn['utterance'] in (_CRASH_FALLBACK, _LOOP_FALLBACK) or turn['timed_out']
        turn['oracle_utterance'] = oracle_turn['utterance']
        turn['grounding_issues'] = compare_grounding(oracle_turn, turn['active_post'])
        turn['judge_issues'] = judge_utterance(oracle_turn, turn['utterance'])
        turns.append(turn)
        print(f"  step {turn['step']:02d} [{turn['flow']}] {turn['duration_sec']:>6.1f}s "
              f"crashed={turn['crashed']} grounding={turn['grounding_issues'] or 'ok'} "
              f"judge={turn['judge_issues'] or 'pass'}")
        print(f"     new: {turn['utterance'][:140]!r}")
    return turns


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario', required=True, choices=sorted(SCENARIOS))
    parser.add_argument('--half', required=True, type=int, choices=(1, 2))
    args = parser.parse_args()

    steps, post_id, title = SCENARIOS[args.scenario]
    oracle = load_fixture(args.scenario)
    result_path = Path(f'/tmp/parity_phase4_{args.scenario}.json')
    print(f'Parity run: scenario={args.scenario} half={args.half} (orchestrator flag ON)')

    agent = _build_agent()
    if args.half == 1:
        _clean_leftovers(post_id, title)
        turns = _run_half(agent, steps[:7], post_id, oracle['turns'][:7])
        result = {'scenario': args.scenario, 'pipeline': 'orchestrator',
                  'post_id': turns[0]['active_post'] or oracle['post_id'], 'turns': turns,
                  'session_dirs': [str(agent.world.session_dir())]}
    else:
        if not result_path.exists():
            sys.exit(f'{result_path} missing — run half 1 first')
        result = json.loads(result_path.read_text())
        actual_id = result['post_id']
        _seed_part2(agent, actual_id, title)
        _seed_messages(agent, actual_id, title)
        result['turns'].extend(_run_half(agent, steps[7:], actual_id, oracle['turns'][7:]))
        result['session_dirs'].append(str(agent.world.session_dir()))
        result['end_state_issues'] = compare_db_end_state(oracle['db_end_state'], actual_id)
        print(f"  end_state={result['end_state_issues'] or 'ok'}")
    agent.close()

    if args.half == 2 and os.getenv('HUGO_E2E_KEEP_POSTS') != '1':
        _clean_leftovers(result['post_id'], title)
        for session_dir in result['session_dirs']:
            shutil.rmtree(session_dir, ignore_errors=True)

    result_path.write_text(json.dumps(result, indent=2) + '\n')
    crashes = sum(1 for turn in result['turns'] if turn['crashed'])
    grounding = sum(len(turn['grounding_issues']) for turn in result['turns'])
    judge_fails = sum(1 for turn in result['turns'] if turn['judge_issues'])
    print(f"\nSUMMARY {args.scenario} (through half {args.half}): crashes={crashes} "
          f"grounding_issues={grounding} judge_fails={judge_fails} "
          f"end_state={result.get('end_state_issues', '(half 2 pending)')}")
    print(f'Wrote {result_path}')


if __name__ == '__main__':
    main()
