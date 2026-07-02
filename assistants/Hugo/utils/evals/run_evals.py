"""P1 completion eval runner (step_1_evals.md Phase 1).

Runs each scenario's user turns through a live orchestrator Agent, scores every turn with the
completion detector, aggregates completion_rate, writes report/<level>_metrics.json, and calls the
gate. Red-green: the gate stays green while completion_rate.expected_fail is true (feature unbuilt);
flip it off once the agent reliably completes, and a drop below target turns the gate red.

  python utils/evals/run_evals.py --level evals --metric completion
  python utils/evals/run_evals.py --level evals --metric completion --record   # stamp baseline
"""
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from pathlib import Path

_HUGO_ROOT = Path(__file__).resolve().parents[2]
if str(_HUGO_ROOT) not in sys.path:
    sys.path.insert(0, str(_HUGO_ROOT))

# utils.harness sets HUGO_EVAL_MODE + loads .env at import — wanted here (this is a live runner).
from utils.harness import _build_agent, _seed_post, _clean_leftovers, _TURN_TIMEOUT_SEC
from utils.evals.scorers.completion import is_completed
from utils.evals import gates

_EVAL_DIR = Path(__file__).resolve().parent
SCENARIOS = _EVAL_DIR / 'datasets' / 'scenarios'


def _run_turn(agent, utterance:str) -> dict:
    """Run one user turn with the trace recorder's timeout guard, but keep the FULL result dict —
    completion needs result['artifact']['origin'], not just the message."""
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(agent.take_turn, utterance)
        try:
            return future.result(timeout=_TURN_TIMEOUT_SEC)
        except FuturesTimeoutError:
            return {'message': '(turn timed out)', 'artifact': None}


def _run_case(case:dict) -> tuple[int, int]:
    """Seed any posts the case declares, run its user turns, score is_completed. Returns
    (completed_user_turns, total_user_turns)."""
    seeded = []
    for post in case.get('available_data', {}).get('posts', []):
        if post.get('sections'):
            _seed_post(post['post_id'], post['title'], post['sections'])
            seeded.append((post['post_id'], post['title']))

    agent = _build_agent()
    completed = total = 0
    for turn in case['turns']:
        if turn.get('role') != 'user':
            continue
        total += 1
        result = _run_turn(agent, turn['utterance'])
        ok, reason = is_completed(result, turn['labels']['flow'])
        completed += ok
        print(f"  {case['convo_id']} turn {total}: {'ok' if ok else reason}")
    agent.close()

    for post_id, title in seeded:
        _clean_leftovers(post_id, title)
    return completed, total


def _completion_rate() -> float:
    cases = [json.loads(path.read_text()) for path in sorted(SCENARIOS.glob('*.json'))]
    done = total = 0
    for case in cases:
        case_done, case_total = _run_case(case)
        done += case_done
        total += case_total
    return round(done / total, 4) if total else 0.0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--level', default='evals')
    parser.add_argument('--metric', default='completion')
    parser.add_argument('--record', action='store_true', help='stamp the run into the baseline')
    args = parser.parse_args()

    rate = _completion_rate()
    gates.REPORT.mkdir(exist_ok=True)
    (gates.REPORT / f'{args.level}_metrics.json').write_text(
        json.dumps({'completion_rate': rate}, indent=2) + '\n')
    print(f'completion_rate = {rate}')

    if args.record:
        gates.record(args.level)
        print(f'recorded {args.level} baseline')
        return
    sys.exit(gates.evaluate(args.level))


if __name__ == '__main__':
    main()
