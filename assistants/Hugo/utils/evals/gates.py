"""Red-green gate for the eval system (step_1_evals.md — folded-baseline gate model).

Folded baseline model: one self-describing file per level under baselines/ — each metric record
carries the hand-set intent (target / direction / max_drop / expected_fail) and the machine-written
measurement (value / commit / date). The gate grades a run blob against these records and returns a
process exit code (1 = any metric failed). `--record` is the only writer of baseline values, and it
touches value/commit/date only — never the hand-set intent.

  python utils/evals/gates.py --level evals            # grade report/<level>_metrics.json
  python utils/evals/gates.py --level evals --record   # stamp the run into the baseline
"""
import argparse
import json
import subprocess
import sys
from collections import namedtuple
from datetime import datetime
from pathlib import Path

_EVAL_DIR = Path(__file__).resolve().parent
BASELINES = _EVAL_DIR / 'baselines'
REPORT = _EVAL_DIR / 'report'

Verdict = namedtuple('Verdict', 'metric status failed')


def _meets(value, target, direction):
    return value >= target if direction == 'higher' else value <= target


def _regressed(value, baseline, record):
    direction = record['direction']
    if 'max_drop_pct' in record:
        limit = baseline * (1 + record['max_drop_pct']) if direction == 'lower' \
            else baseline * (1 - record['max_drop_pct'])
    else:
        drop = record.get('max_drop') or 0.0
        limit = baseline + drop if direction == 'lower' else baseline - drop
    return value > limit if direction == 'lower' else value < limit


def grade(metric, value, record) -> Verdict:
    """Grade one metric's run value against its folded baseline record.
    Order: expected_fail (known-red) → absolute target → regression vs baseline."""
    if record.get('expected_fail'):
        return Verdict(metric, 'xfail', False)
    target, direction = record.get('target'), record['direction']
    if target is not None and not _meets(value, target, direction):
        return Verdict(metric, 'red:target', True)
    baseline = record.get('value')
    if baseline is None:
        if target is not None:
            return Verdict(metric, 'green:target', False)   # first red→green: target met, no baseline yet
        return Verdict(metric, 'red:no-baseline', True)      # nothing to assert against — declare one
    if _regressed(value, baseline, record):
        return Verdict(metric, 'red:regressed', True)
    return Verdict(metric, 'green', False)


def gate(run:dict, baselines:dict) -> int:
    """Exit code for a whole run: 1 if any metric fails its folded baseline, else 0. Pure (no IO)."""
    return 1 if any(grade(name, run[name], baselines[name]).failed for name in run) else 0


def _load(path:Path) -> dict:
    return json.loads(path.read_text())


def _write_report(level:str, verdicts:list):
    REPORT.mkdir(exist_ok=True)
    lines = [f'# {level} gate', '']
    lines += [f'- {v.metric}: {v.status}' + ('  <- FAIL' if v.failed else '') for v in verdicts]
    (REPORT / f'{level}_report.md').write_text('\n'.join(lines) + '\n')


def evaluate(level:str) -> int:
    """Disk path: grade the level's run blob against its baselines, write a report, return the exit
    code. The runner writes report/<level>_metrics.json before calling this."""
    run = _load(REPORT / f'{level}_metrics.json')
    baselines = _load(BASELINES / f'{level}.json')
    verdicts = [grade(name, run[name], baselines[name]) for name in run]
    _write_report(level, verdicts)
    return gate(run, baselines)


def _git_commit() -> str:
    done = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True)
    return done.stdout.strip() or 'unknown'


def record(level:str):
    """Stamp the latest run's values into the folded baselines — the only writer of baseline values.
    Updates value/commit/date only; the hand-set intent keys are left untouched."""
    run = _load(REPORT / f'{level}_metrics.json')
    baselines = _load(BASELINES / f'{level}.json')
    today = datetime.now().strftime('%Y-%m-%d')
    commit = _git_commit()
    for name, value in run.items():
        baselines[name].update({'value': value, 'commit': commit, 'date': today})
    (BASELINES / f'{level}.json').write_text(json.dumps(baselines, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description='Eval gate: grade a run blob -> exit code.')
    parser.add_argument('--level', default='traces')
    parser.add_argument('--record', action='store_true', help='stamp the run into the baseline')
    args = parser.parse_args()
    if args.record:
        record(args.level)
        print(f'recorded {args.level} baseline')
        return
    sys.exit(evaluate(args.level))


if __name__ == '__main__':
    main()
