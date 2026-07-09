"""Eval scoring + gate (evaluation_suite) — per-turn scorers and the red-green baseline gate.

Merges the former `scorers/completion.py`, `scorers/tools.py`, and `gates.py` into one module — all
"how we score and gate an eval run":
  * is_completed   — did the turn finish in the right MODE for its label (completion scorer).
  * tool_similarity— did the dispatched domain tools match the label, by token Levenshtein (tools scorer).
  * grade / gate / evaluate / record — the folded-baseline red-green gate. Each tier keeps its own
    baseline under its folder: `_traces/traces.json`, `_evals/evals.json`.

  python utils/evaluation_suite/scoring.py --level traces            # grade report/<level>_metrics.json
  python utils/evaluation_suite/scoring.py --level traces --record   # stamp the run into the baseline
"""
import argparse
import json
import subprocess
import sys
from collections import namedtuple
from datetime import datetime
from pathlib import Path

_SUITE_DIR = Path(__file__).resolve().parent          # utils/evaluation_suite
_HUGO_ROOT = _SUITE_DIR.parent.parent                 # Hugo assistant root
if str(_HUGO_ROOT) not in sys.path:
    sys.path.insert(0, str(_HUGO_ROOT))

from backend.modules.pex import _FALLBACK_MESSAGE

# ── Completion scorer ─────────────────────────────────────────────────
# A turn completes iff a real reply came back AND the agent behaved in the right MODE for the label
# `{intent, stack:[{flow,dax},...]}` + a flat `ambiguity` (a level or null). The "didn't finish"
# sentinels: the loop give-up (_FALLBACK_MESSAGE), the crash literal (agent.py), the runner timeout.
_CRASH_FALLBACK = 'Something went wrong on my end. Please try again.'   # mirrors agent.py
_TIMEOUT = '(turn timed out)'
FALLBACKS = (_CRASH_FALLBACK, _FALLBACK_MESSAGE, _TIMEOUT)


def is_completed(result:dict, turn:dict, declared_level:str='') -> tuple:
    """Returns (completed, reason). Order matters: the fallback/empty checks run before reading the
    artifact, because the crash path returns artifact=None. `declared_level` is the live handler's
    `agent.ambiguity.level` (`''` when no ambiguity was declared)."""
    message = result['message']
    if message in FALLBACKS:
        return False, f'fallback: {message[:40]!r}'
    if not message.strip():
        return False, 'empty reply'

    level = turn['ambiguity']                     # a level string, or None (not ambiguous)
    if level is not None:                         # ambiguous turn: the agent must ask, not guess
        if not declared_level:
            return False, f'expected {level!r} ambiguity, none declared'
        if declared_level != level:
            return True, f'ok (declared {declared_level!r}, expected {level!r})'
        return True, 'ok'

    stack = turn['labels']['stack']
    if len(stack) > 1:                            # plan turn: coarse pass — the agent proposes/decomposes
        return True, 'ok (plan)'
    origin = result['artifact']['origin']         # normal turn: primary flow must match
    expected_flow = stack[0]['flow']
    if origin != expected_flow:
        return False, f'expected {expected_flow!r}, got {origin!r}'
    return True, 'ok'


# ── Tool scorer ───────────────────────────────────────────────────────
def _levenshtein(a:list, b:list) -> int:
    """Token-level edit distance between two tool-name sequences (each tool is one token)."""
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for idx, tool_a in enumerate(a, 1):
        cur = [idx]
        for jdx, tool_b in enumerate(b, 1):
            cur.append(min(prev[jdx] + 1, cur[jdx - 1] + 1, prev[jdx - 1] + (tool_a != tool_b)))
        prev = cur
    return prev[-1]


def tool_similarity(actual_tools:list, expected_tools:list) -> float:
    """Per-turn similarity in [0, 1]: 1 - normalized Levenshtein distance over the two tool sequences.
    Both empty -> 1.0 (the agent correctly ran no domain tool). One empty and the other not -> 0.0."""
    denom = max(len(actual_tools), len(expected_tools))
    if denom == 0:
        return 1.0
    return 1.0 - _levenshtein(actual_tools, expected_tools) / denom


# ── Response scorer — criterion 3, two modes ──────────────────────────
def semantic_similarity(actual:str, reference:str) -> float:
    """DEFAULT (cheap, offline): cosine similarity between the actual reply and the corpus's
    ground-truth reply via the shared local embedding model (backend.utilities.embeddings). No LLM
    or API call — the same small model business context uses, so nothing extra is downloaded."""
    from backend.utilities.embeddings import similarity
    return similarity(actual, reference)


def judge_response(engineer, history:str, user_text:str, reference:str, actual:str) -> bool:
    """Criterion 3 (response): does the agent's actual reply accomplish the same thing as the
    corpus's ground-truth agent reply? A cheap low-tier judge — the reference IS the labelled answer
    (each `role:agent` turn), so no rubric authoring is needed. The lead-up `history` is passed in
    because context often decides what a good reply is (anaphora, a prior proposal, a correction)."""
    lead_up = f"Conversation so far:\n{history}\n\n" if history else ''
    prompt = (f"Grade an assistant reply for a blog-writing assistant.\n\n{lead_up}"
              f"Latest user turn:\n{user_text}\n\nReference (good) reply:\n{reference}\n\n"
              f"Assistant's actual reply:\n{actual}\n\n"
              "Given the conversation so far, does the actual reply convey the same substance and "
              "serve the user as well as the reference? Ignore wording differences; judge the "
              "substance. Answer exactly 'pass' or 'fail: <short reason>'.")
    verdict = engineer(prompt, task='quality_check', tier='low', max_tokens=64).strip().lower()
    return verdict.startswith('pass')


# ── Red-green gate (folded-baseline model) ────────────────────────────
# One self-describing baseline file per tier, under that tier's folder: each metric record carries the
# hand-set intent (target / direction / max_drop / expected_fail) and the machine-written measurement
# (value / commit / date). `--record` is the only writer of baseline values.
REPORT = _SUITE_DIR / 'report'
Verdict = namedtuple('Verdict', 'metric status failed')


def _baseline_path(level:str) -> Path:
    """Each tier keeps its baseline inside its own folder — traces -> _traces/traces.json."""
    return _SUITE_DIR / f'_{level}' / f'{level}.json'


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
    baselines = _load(_baseline_path(level))
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
    path = _baseline_path(level)
    baselines = _load(path)
    today = datetime.now().strftime('%Y-%m-%d')
    commit = _git_commit()
    for name, value in run.items():
        baselines[name].update({'value': value, 'commit': commit, 'date': today})
    path.write_text(json.dumps(baselines, indent=2) + '\n')


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
