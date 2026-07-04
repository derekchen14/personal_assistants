"""Unified evaluation-suite entry point (evaluation_suite.md — the three levels).

Three levels, selectable per module, via argparse. **By default only the free deterministic Model
Unit Tests run** (no model calls, no cost); every probabilistic / live level is opt-in.

  Level 1 — Tests
     (a) deterministic  free   `--tests [MODULES]`   pytest nlu/pex/mem_unit_tests.py  -m "not llm"
     (b) probabilistic  paid   `--model [MODULES]`   python utils/tests/model_tests.py --module ...
  Level 2 — Traces      paid   `--traces`            utils/evals/run_evals.py
  Level 3 — Evals       paid   `--evals`             pytest utils/evals/e2e_*_evals.py -m llm

MODULES is an optional comma list (nlu, pex, mem) or 'all' (the default when the flag is bare).

  python utils/evals/run_evaluation_suite.py                   # free deterministic tests, all modules
  python utils/evals/run_evaluation_suite.py --tests nlu       # just NLU deterministic
  python utils/evals/run_evaluation_suite.py --model nlu       # NLU probabilistic (paid)
  python utils/evals/run_evaluation_suite.py --tests --model   # both halves of the Tests level
  python utils/evals/run_evaluation_suite.py --traces --evals  # the two live upper levels
  python utils/evals/run_evaluation_suite.py --all             # everything (all levels, all modules)
"""
import argparse
import subprocess
import sys
from pathlib import Path

_EVAL_DIR = Path(__file__).resolve().parent
_HUGO_ROOT = _EVAL_DIR.parents[1]
_MODULES = ('nlu', 'pex', 'mem')
_PY = sys.executable
# Tests are found by naming the files explicitly (below) — no python_files pattern, no directory scan.


def _modules(value:str) -> list:
    """Resolve a flag value ('all' / bare / 'nlu,pex') to a module list."""
    if value in (None, 'all'):
        return list(_MODULES)
    return [name.strip() for name in value.split(',') if name.strip()]


def _commands(args) -> list:
    """Build the (label, argv) list for the requested levels, in ladder order."""
    cmds = []
    if args.tests is not False:
        files = [f'utils/tests/{name}_unit_tests.py' for name in _modules(args.tests)]
        cmds.append(('tests (deterministic)',
                     [_PY, '-m', 'pytest', *files, '-m', 'not llm', '-q']))
    if args.model is not False:
        mods = ','.join(_modules(args.model))
        cmds.append((f'model ({mods})', [_PY, 'utils/tests/model_tests.py', '--module', mods]))
    if args.traces:
        cmds.append(('traces', [_PY, 'utils/evals/run_evals.py']))
    if args.evals:
        cmds.append(('evals', [_PY, '-m', 'pytest', 'utils/evals/e2e_agent_evals.py',
                               'utils/evals/e2e_multiturn_evals.py', '-m', 'llm', '-q']))
    return cmds


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
    parser.add_argument('--all', action='store_true', help='every level, every module')
    args = parser.parse_args()

    if args.all:
        args.tests = args.model = 'all'
        args.traces = args.evals = True
    if args.tests is False and args.model is False and not args.traces and not args.evals:
        args.tests = 'all'   # default: free deterministic tests only

    failures = []
    for label, argv in _commands(args):
        print(f'\n===== {label} =====', flush=True)
        code = subprocess.call(argv, cwd=_HUGO_ROOT)
        print(f'----- {label}: {"PASS" if code == 0 else "FAIL"} (exit {code}) -----')
        if code != 0:
            failures.append(label)

    if failures:
        print(f'\nFAILED: {", ".join(failures)}')
        sys.exit(1)
    print('\nall requested levels passed')


if __name__ == '__main__':
    main()
