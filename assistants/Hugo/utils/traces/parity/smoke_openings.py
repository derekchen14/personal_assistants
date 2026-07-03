"""Decision-14 smoke runner — scenario OPENINGS through the NEW orchestrator path, per tier.

Runs the first 4 turns of each E2E scenario (create → outline propose → outline pick/direct →
refine) on the orchestrator path with the loop model set to one tier, then scores
the run against the Phase-0 oracle fixtures on the comparator axes adapted to an opening:

  1. End-state DB — post exists, title matches the oracle, sections in the opening's expected
     order, h2_count matches (the fixture's db_end_state is post-14-turn, so section ORDER comes
     from the scenario's step-3 expectations; title comes from the oracle).
  2. Grounding — per-turn state.active_post vs the oracle turn (comparator.compare_grounding).
  3. Utterance judge — comparator.judge_utterance on each scenario's FINAL turn (task adequacy
     vs the oracle reply, changes.md §9.1 axis 3).

Latency and both utterances (new + oracle) are recorded per turn for the judge notes.
The smoke posts and the orchestrator session dir are deleted afterwards.

Run from the Hugo root, one tier per invocation (tiers share pinned post ids — never parallel):
  python utils/traces/parity/smoke_openings.py --tier mid
  python utils/traces/parity/smoke_openings.py --tier high
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from types import MappingProxyType

_HUGO_ROOT = Path(__file__).resolve().parents[3]
if str(_HUGO_ROOT) not in sys.path:
    sys.path.insert(0, str(_HUGO_ROOT))

import utils.traces.parity.capture_oracle as oracle_mod
from utils.traces.parity.capture_oracle import SCENARIOS, _clean_leftovers, _run_step, _CRASH_FALLBACK
from utils.traces.parity.comparator import (load_fixture, capture_db_state, compare_grounding,
                                           judge_utterance)

# Anthropic tier ladder (MEMORY.md): mid = Sonnet, high = Opus. HIGH reuses the repo's pinned
# Opus id (the `skill` override in tools.yaml) so no other call site changes.
TIER_MODELS = {'mid': 'claude-sonnet-4-6', 'high': 'claude-opus-4-6'}
# Section order after the opening (from each scenario's step-3 expected_post_content).
OPENING_SECTIONS = {
    'vision': ['motivation', 'process', 'ideas', 'takeaways'],
    'observability': ['motivation', 'cost-modeling', 'dashboards'],
    'voice': ['motivation', 'process', 'ideas', 'takeaways'],
}
_LOOP_FALLBACK = "I wasn't able to finish that. Could you try rephrasing?"
oracle_mod._TURN_TIMEOUT_SEC = 180.0  # orchestrator turns run multiple LLM rounds


def _thaw(obj):
    if isinstance(obj, (dict, MappingProxyType)):
        return {key: _thaw(val) for key, val in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_thaw(item) for item in obj]
    return obj


def _build_agent(tier:str):
    """Orchestrator-path Agent: flag on, loop model set to the tier, debug like the oracle."""
    from schemas.config import load_config
    import backend.agent as agent_mod
    base = load_config()
    models = _thaw(base['models'])
    models['overrides']['orchestrator']['model_id'] = TIER_MODELS[tier]
    overrides = {'debug': True, 'models': models}
    orig_load = agent_mod.load_config
    agent_mod.load_config = lambda: load_config(overrides=overrides)
    agent = agent_mod.Agent(username='smoke_user')
    agent_mod.load_config = orig_load
    return agent


def _check_end_state(scenario:str, oracle:dict, post_id:str) -> list:
    """Axis 1 adapted to an opening: existence + oracle title + step-3 section expectations."""
    actual = capture_db_state(post_id)
    if not actual['exists']:
        return [f'post {post_id} missing on disk']
    expected = OPENING_SECTIONS[scenario]
    issues = []
    if actual['title'] != oracle['db_end_state']['title']:
        issues.append(f"title {actual['title']!r} != oracle {oracle['db_end_state']['title']!r}")
    if actual['section_ids'] != expected:
        issues.append(f"section_ids {actual['section_ids']} != expected {expected}")
    if actual['outline_shape']['h2_count'] != len(expected):
        issues.append(f"h2_count {actual['outline_shape']['h2_count']} != {len(expected)}")
    return issues


def _run_scenario(tier:str, scenario:str) -> dict:
    steps, post_id, title = SCENARIOS[scenario]
    oracle = load_fixture(scenario)
    agent = _build_agent(tier)
    _clean_leftovers(post_id, title)

    turns = []
    for step_def in steps[:4]:
        turn = _run_step(agent, step_def, post_id)
        if turn['utterance'] in (_CRASH_FALLBACK, _LOOP_FALLBACK) or turn['timed_out']:
            print(f"  step {step_def['step']:02d} failed ({turn['utterance'][:40]!r}) — retrying once")
            turn = _run_step(agent, step_def, post_id)
        turn['crashed'] = turn['utterance'] in (_CRASH_FALLBACK, _LOOP_FALLBACK) or turn['timed_out']
        turn['oracle_utterance'] = oracle['turns'][len(turns)]['utterance']
        turn['grounding_issues'] = compare_grounding(oracle['turns'][len(turns)], turn['active_post'])
        turns.append(turn)
        print(f"  step {turn['step']:02d} [{turn['flow']}] {turn['duration_sec']:>6.1f}s "
              f"crashed={turn['crashed']} grounding={turn['grounding_issues'] or 'ok'}")
        print(f"     new: {turn['utterance'][:140]!r}")

    actual_id = turns[0]['active_post'] or post_id
    end_state = _check_end_state(scenario, oracle, actual_id)
    db_snapshot = capture_db_state(actual_id)
    judge = judge_utterance(oracle['turns'][len(turns) - 1], turns[-1]['utterance'])
    print(f"  end_state={end_state or 'ok'} judge={judge or 'pass'}")
    session_path = agent.world.session_dir()
    agent.close()
    if os.getenv('HUGO_E2E_KEEP_POSTS') == '1':  # keep post + session dir for debugging
        print(f'  kept post {actual_id} and session {session_path}')
    else:
        _clean_leftovers(actual_id, title)
        shutil.rmtree(session_path, ignore_errors=True)

    return {'scenario': scenario, 'turns': turns, 'end_state_issues': end_state,
            'judge_issues': judge, 'db_status': db_snapshot.get('status'),
            'avg_turn_sec': round(sum(t['duration_sec'] for t in turns) / len(turns), 1)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tier', required=True, choices=sorted(TIER_MODELS))
    parser.add_argument('--scenario', choices=sorted(OPENING_SECTIONS),
                        help='run one scenario only (debugging; skips the summary file)')
    args = parser.parse_args()

    from dotenv import load_dotenv
    load_dotenv(_HUGO_ROOT / '.env')

    import schemas.config
    schemas.config.EVAL_HARNESS = True

    results = []
    for scenario in (args.scenario,) if args.scenario else ('vision', 'observability', 'voice'):
        print(f"=== tier={args.tier} model={TIER_MODELS[args.tier]} scenario={scenario} ===")
        results.append(_run_scenario(args.tier, scenario))

    all_turns = [turn for res in results for turn in res['turns']]
    summary = {
        'tier': args.tier, 'model': TIER_MODELS[args.tier],
        'crashes': sum(1 for t in all_turns if t['crashed']),
        'grounding_issues': sum(len(t['grounding_issues']) for t in all_turns),
        'end_state_issues': {res['scenario']: res['end_state_issues'] for res in results},
        'judge_issues': {res['scenario']: res['judge_issues'] for res in results},
        'avg_turn_sec': round(sum(t['duration_sec'] for t in all_turns) / len(all_turns), 1),
        'scenarios': results,
    }
    suffix = f'_{args.scenario}' if args.scenario else ''
    out_path = Path(f'/tmp/smoke_openings_{args.tier}{suffix}.json')
    out_path.write_text(json.dumps(summary, indent=2) + '\n')
    judge_fails = sum(1 for res in results if res['judge_issues'])
    print(f"\nSUMMARY tier={args.tier}: crashes={summary['crashes']} "
          f"grounding_issues={summary['grounding_issues']} judge_fails={judge_fails} "
          f"avg={summary['avg_turn_sec']}s")
    print(f'Wrote {out_path}')


if __name__ == '__main__':
    main()
