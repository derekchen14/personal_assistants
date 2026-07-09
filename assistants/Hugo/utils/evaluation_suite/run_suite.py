"""Unified evaluation-suite entry point (evaluation_suite.md — the three levels).

Three levels, selectable per module, via argparse. By default the suite runs deterministic Model
Unit Tests, then a sampled E2E eval pass that records trace JSONL during the same live run.
`--evals` and `--traces` narrow the live run to only that tier.

  Level 1 — Tests
     (a) deterministic  free   `--tests [MODULES]`   pytest _tests/{nlu,pex,mem}_unit_tests.py
     (b) probabilistic  paid   `--model [MODULES]`   python _tests/model_tests.py --module ...
  Level 2 — Traces      paid   `--traces`            python _traces/run_traces.py
  Level 3 — Evals       paid   `--evals`             python _evals/run_evals.py  (not built yet)

Everything lives under `utils/evaluation_suite/`: this entry point, the three tier folders
(`_tests/`, `_traces/`, `_evals/`), and the shared infrastructure — the corpus (`datasets/`) plus
the sampler (`harness.py`), the scorers + gate (`scoring.py`), the snapshot helper (`_snapshot.py`),
and the seed-review app (`review_app/`).

MODULES is an optional comma list (nlu, pex, mem) or 'all' (the default when the flag is bare).

  python utils/evaluation_suite/run_suite.py                   # tests + sampled evals with traces
  python utils/evaluation_suite/run_suite.py --tests nlu       # just NLU deterministic
  python utils/evaluation_suite/run_suite.py --model nlu       # NLU probabilistic (paid)
  python utils/evaluation_suite/run_suite.py --tests --model   # both halves of the Tests level
  python utils/evaluation_suite/run_suite.py --traces          # trace-replay tier only
  python utils/evaluation_suite/run_suite.py --evals           # E2E eval tier only
  python utils/evaluation_suite/run_suite.py --all             # everything (all levels, all modules)
"""
import argparse
import subprocess
import sys
from pathlib import Path

_SUITE_DIR = Path(__file__).resolve().parent          # utils/evaluation_suite
_HUGO_ROOT = _SUITE_DIR.parents[1]                    # -> Hugo assistant root
if str(_HUGO_ROOT) not in sys.path:
    sys.path.insert(0, str(_HUGO_ROOT))
_TESTS = 'utils/evaluation_suite/_tests'              # tier-folder path prefixes (root-relative)
_TRACES = 'utils/evaluation_suite/_traces'
_EVALS = 'utils/evaluation_suite/_evals'
_MODULES = ('nlu', 'pex', 'mem')
_PY = sys.executable
# Tests are found by naming the files explicitly (below) — no python_files pattern, no directory scan.
_REPORT = _SUITE_DIR / 'report'


def _modules(value:str) -> list:
    """Resolve a flag value ('all' / bare / 'nlu,pex') to a module list."""
    if value in (None, 'all'):
        return list(_MODULES)
    return [name.strip() for name in value.split(',') if name.strip()]


def _selection_args(args) -> list:
    """Resolve suite-level live-tier selection once so traces and evals inspect the same cases."""
    if args.ids:
        ids = [cid.strip() for cid in args.ids.split(',') if cid.strip()]
    else:
        from utils.evaluation_suite.harness import sample
        ids = sample(args.sample, seed=args.seed)
    print(f"suite live ids: {','.join(ids)}", flush=True)
    return ['--ids', ','.join(ids)]


def _commands(args) -> list:
    """Build the (label, argv) list for the requested levels, in ladder order."""
    cmds = []
    run_live = args.traces or args.evals or args.combined_live
    live_selection = _selection_args(args) if run_live else []
    if args.tests is not False:
        files = [f'{_TESTS}/{name}_unit_tests.py' for name in _modules(args.tests)]
        cmds.append(('tests (deterministic)',
                     [_PY, '-m', 'pytest', *files, '-m', 'not llm', '-q']))
    if args.model is not False:
        mods = ','.join(_modules(args.model))
        cmds.append((f'model ({mods})', [_PY, f'{_TESTS}/model_tests.py', '--module', mods]))
    if args.traces:
        cmds.append(('traces', [_PY, f'{_TRACES}/run_traces.py', *live_selection]))
    if args.evals:
        cmds.append(('evals', [_PY, f'{_EVALS}/run_evals.py', *live_selection]))
    if args.combined_live:
        cmds.append(('evals+traces', [_PY, f'{_EVALS}/run_evals.py', *live_selection,
                                      '--trace-report', 'evals_trace']))
    return cmds


def _prune_trace_reports(keep:int):
    if keep < 0:
        return
    trace_files = sorted(
        [*_REPORT.glob('traces_*.jsonl'), *_REPORT.glob('evals_trace_*.jsonl')],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    stale = trace_files[keep:]
    for path in stale:
        path.unlink()
    print(f'trace retention: kept {min(len(trace_files), keep)} of {len(trace_files)} trace files')


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    # nargs='?' → bare flag means 'all'; `False` default means the flag was absent.
    parser.add_argument('--tests', nargs='?', const='all', default=False,
                        help='deterministic unit tests (free); optional module list, default all')
    parser.add_argument('--model', nargs='?', const='all', default=False,
                        help='probabilistic model tests (paid); optional module list, default all')
    parser.add_argument('--traces', action='store_true', help='trace-replay tier (paid)')
    parser.add_argument('--evals', action='store_true', help='end-to-end agent evals (paid)')
    parser.add_argument('--ids', default='', help='comma-separated convo_ids for traces/evals')
    parser.add_argument('--sample', type=int, default=8, help='fresh traces/evals sample size')
    parser.add_argument('--seed', default=None, help='seed for reproducible traces/evals samples')
    parser.add_argument('--keep-traces', type=int, default=128,
                        help='keep only the most recent N trace JSONL files after the suite run')
    parser.add_argument('--all', action='store_true', help='every level, every module')
    args = parser.parse_args()

    if args.all:
        args.tests = args.model = 'all'
        args.combined_live = True
    else:
        args.combined_live = (
            args.tests is False and args.model is False and not args.traces and not args.evals
        )
    if args.tests is False and args.model is False and not args.traces and not args.evals:
        args.tests = 'all'
        args.combined_live = True

    failures = []
    for label, argv in _commands(args):
        print(f'\n===== {label} =====', flush=True)
        code = subprocess.call(argv, cwd=_HUGO_ROOT)
        print(f'----- {label}: {"PASS" if code == 0 else "FAIL"} (exit {code}) -----')
        if code != 0:
            failures.append(label)

    _prune_trace_reports(args.keep_traces)

    if failures:
        print(f'\nFAILED: {", ".join(failures)}')
        sys.exit(1)
    print('\nall requested levels passed')


if __name__ == '__main__':
    main()
