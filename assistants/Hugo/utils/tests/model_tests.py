"""Probabilistic model unit tests — the (b) half of the Model Unit Tests level, one file for all
three modules (NLU / PEX / MEM), selected by `--module`.

Unlike the deterministic `*_unit_tests.py` files, this one **stores no cases inline**: the labels
already live in the eval corpus (`utils/evals/datasets/scenarios/*.json`), so this code just loads
that data and scores each module's single-decision model predictions — one model call per decision,
no full PEX loop (that trajectory view is the Traces tier's job, `run_evals.py`).

  python utils/tests/model_tests.py --module nlu          # NLU flow-detection accuracy
  python utils/tests/model_tests.py --module nlu,pex      # several
  python utils/tests/model_tests.py --module all

Reports accuracy per module; makes live model calls (paid), so it is not part of the free default
run. NLU is scored today; PEX/MEM are declared with their scoring still to be defined.
"""
import argparse
import json
import sys
from pathlib import Path

_HUGO_ROOT = Path(__file__).resolve().parents[2]
if str(_HUGO_ROOT) not in sys.path:
    sys.path.insert(0, str(_HUGO_ROOT))

# utils.harness flips schemas.config.EVAL_HARNESS + loads .env at import.
from utils.harness import _build_agent
from utils.evals.run_evals import SCENARIOS


def _load_cases(limit:int=0) -> list:
    cases = [json.loads(path.read_text()) for path in sorted(SCENARIOS.glob('*.json'))]
    return cases[:limit] if limit else cases


def _single_flow(turn:dict):
    """The labeled flow for a turn we can score for flow-detection: a one-item stack. Returns the
    flow name, or None for plan turns (multi-item stack = planning axis) and general-ambiguity turns
    (empty stack = the ambiguity axis), which flow-detection accuracy does not cover."""
    stack = turn['labels']['stack']
    return stack[0]['flow'] if len(stack) == 1 and stack[0].get('flow') else None


def score_nlu(limit:int=0) -> tuple:
    """Teacher-forced NLU flow detection: replay each conversation, feeding the corpus's own agent
    replies back as context, and on every user turn run NLU alone (`understand(op=think)`) and compare
    its top predicted flow to the labeled one. Isolates the detection decision from the acting loop."""
    correct = total = 0
    misses = []
    for case in _load_cases(limit):
        agent = _build_agent()
        agent._ensure_session()
        for turn in case['turns']:
            if turn.get('role') != 'user':
                agent.world.context.add_turn('Agent', turn['utterance'], turn_type='utterance')
                continue
            agent.world.context.add_turn('User', turn['utterance'], turn_type='utterance')
            if agent.ambiguity.present():
                agent.ambiguity.resolve()
            agent.nlu.understand(op='think', user_text=turn['utterance'])
            expected = _single_flow(turn)
            if expected is None:
                continue                                  # plan / general-ambiguity turn — not scored here
            pred_flows = agent.world.current_state().pred_flows
            predicted = pred_flows[0]['flow_name'] if pred_flows else None
            total += 1
            if predicted == expected:
                correct += 1
            else:
                misses.append(f"{case['convo_id']}: {expected!r} != {predicted!r}")
        agent.close()
    for miss in misses:
        print(f'  miss {miss}')
    return correct, total


def score_pex() -> tuple:
    """PEX single-decision scoring (e.g. tool selection) — scope TBD; tool trajectories are the
    Traces tier's job today. No model-prediction checks defined yet."""
    return 0, 0


def score_mem() -> tuple:
    """MEM single-decision scoring (e.g. retrieval relevance) — scope TBD. No checks defined yet."""
    return 0, 0


SCORERS = {'nlu': score_nlu, 'pex': score_pex, 'mem': score_mem}


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--module', default='nlu',
                        help='comma-separated: nlu, pex, mem, or all')
    parser.add_argument('--limit', type=int, default=0,
                        help='score only the first N scenarios (0 = the whole corpus)')
    args = parser.parse_args()

    picked = list(SCORERS) if 'all' in args.module else \
        [name.strip() for name in args.module.split(',') if name.strip()]

    failed = False
    for name in picked:
        correct, total = SCORERS[name](args.limit) if name == 'nlu' else SCORERS[name]()
        if total:
            print(f'{name}: {correct}/{total} = {correct / total:.1%} flow-detection accuracy')
        else:
            print(f'{name}: no model-prediction checks defined yet (scope TBD)')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
