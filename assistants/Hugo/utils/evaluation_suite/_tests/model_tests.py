"""Probabilistic model unit tests — the (b) half of the Model Unit Tests level, one file for all
three modules (NLU / PEX / MEM), selected by `--module`.

Unlike the deterministic `*_unit_tests.py` files, this one **stores no cases inline**: the labels
already live in the eval corpus (`utils/evaluation_suite/datasets/train.jsonl`), so this code
just loads that data and scores each module's single-decision model predictions — one model call per
decision, no full PEX loop (that trajectory view is the Traces tier's job, `_traces/run_traces.py`).

  python utils/evaluation_suite/_tests/model_tests.py --module nlu                     # 8-convo dev sample
  python utils/evaluation_suite/_tests/model_tests.py --module nlu --labels 100        # ~100 labels
  python utils/evaluation_suite/_tests/model_tests.py --module nlu --provider gpt      # score OpenAI
  python utils/evaluation_suite/_tests/model_tests.py --module nlu --provider typesafe # score TypeSafe
  python utils/evaluation_suite/_tests/model_tests.py --module all

Reports accuracy per module; makes live model calls (paid), so it is not part of the free default
run. NLU is scored today; PEX/MEM are declared with their scoring still to be defined.
"""
import argparse
import statistics
import sys
from functools import lru_cache
from pathlib import Path

_HUGO_ROOT = Path(__file__).resolve().parents[3]
if str(_HUGO_ROOT) not in sys.path:
    sys.path.insert(0, str(_HUGO_ROOT))

# harness flips schemas.config.EVAL_HARNESS + loads .env at import.
from utils.evaluation_suite.harness import _build_agent, load_cases, sample
from utils.evaluation_suite._tests.typesafe_helpers import predict_flow as typesafe_predict_flow


def _set_family(family:str):
    """Repoint the whole model stack at one provider family, so NLU's flow-detection call resolves
    to that family's tiers. Mirrors PromptEngineer.ACTIVE_FAMILY set at import (gemini / gpt / …)."""
    import backend.components.prompt_engineer as pe
    if family not in pe.FAMILY_TIERS:
        raise SystemExit(f'unknown provider {family!r}; pick from {list(pe.FAMILY_TIERS)}')
    pe.ACTIVE_FAMILY = family


def _sample_cases(labels:int, seed=None) -> list:
    """A shuffled slice of the corpus. `--labels` caps by label count (score_nlu stops mid-run once
    it hits the cap); with no cap, a fresh dev sample of 8 conversations."""
    return load_cases(sample(96, seed)) if labels else load_cases(sample())


def _single_flow(turn:dict):
    """The labeled flow for a turn we can score: a one-item stack (including single-item plan/clarify
    turns). Returns the flow name, or None for multi-item stacks (a plan decomposition) and empty
    stacks (a general-ambiguity turn), which single-flow accuracy does not cover."""
    stack = turn['labels']['stack']
    return stack[0]['flow'] if len(stack) == 1 and stack[0].get('flow') else None


@lru_cache(maxsize=1)
def _flow_menu() -> tuple:
    """The static flow-detection grounding shared by every provider, so the comparison is fair: the 16
    candidate names, the full rendered ontology (each flow's dax + description + slots — the definitions
    the LLM reads), and the authored exemplars aggregated across intents (the production flow-detection
    examples, not the scored corpus — no leakage). Built once per run."""
    from schemas.ontology import FLOW_ONTOLOGY
    from backend.components.flow_stack import flow_classes
    from backend.prompts.for_experts import render_flow_ontology
    from backend.prompts.experts import PROMPTS
    names = list(FLOW_ONTOLOGY)                                    # the 16 runtime candidates
    ontology = render_flow_ontology(names, FLOW_ONTOLOGY, flow_classes)
    examples = '\n\n'.join(fields['examples'].strip() for fields in PROMPTS.values()
                           if fields.get('examples'))
    return names, ontology, examples


def _predict_flow(agent, user_text:str, provider:str|None=None) -> tuple[str, float]:
    """Single-hop flow detection — no intent classification. The runtime ontology holds exactly 16
    flows (round 3.5); plan {29D} and clarify {09F} survive as label-only vocabulary in the corpus,
    so each provider maps its native output onto them: TypeSafe keeps the two as explicit Choice
    options, the LLM's list output reads multi-flow as `plan` and an empty list (abstention) as
    `clarify`. Returns `(flow_name, confidence)`. Both providers get the SAME grounding (full
    ontology + exemplars, `_flow_menu`)."""
    convo_history = agent.world.context.compile_history()         # default look_back=5
    active_post = agent.nlu._active_post_dict()
    names, ontology, examples = _flow_menu()
    if provider == 'typesafe':
        return typesafe_predict_flow(convo_history, user_text, active_post, ontology, examples)
    from backend.prompts.for_experts import (BACKGROUND_STATIC, PRECEDENCE_NOTE, JSON_ONLY_REMINDER,
                                             _render_current_scenario)
    from backend.modules.nlu import _flow_detection_schema
    role = ('You are the flow-detection component of a blog-writing assistant (named Hugo). Choose the '
            'single flow that best captures what the user wants on their latest turn.')
    task = (f'{BACKGROUND_STATIC}\n\n## Instructions\n\n'
            'Pick the flow from ## Candidate Flows that fits the latest turn — usually one. When the '
            'user lays out a multi-step request, output every step as its own flow in execution '
            'order; when the turn is too ambiguous to commit to any flow, output an empty list.'
            f'\n\n## Rules\n\n{PRECEDENCE_NOTE}')
    current = _render_current_scenario(user_text, convo_history, active_post)
    prompt = '\n\n'.join([f'<role>{role}</role>', f'<task>\n{task}\n</task>',
                          f'<flow_ontology>\n{ontology}\n</flow_ontology>',
                          f'<example_scenarios>\n{examples}\n</example_scenarios>', JSON_ONLY_REMINDER,
                          f'<current_scenario>\n{current}\n</current_scenario>'])
    # Production detection dropped self-reported confidence (ensemble agreement replaced it), but
    # this scorer's calibration report still probes it — re-add the field on a local schema copy.
    schema = _flow_detection_schema(names)
    schema['properties']['confidence'] = {'type': 'string',
                                          'enum': ['0.1', '0.3', '0.5', '0.7', '0.9']}
    schema['required'] = schema['required'] + ['confidence']
    parsed = agent.engineer(prompt, 'detect_flow', schema=schema)
    flows = parsed['flows']
    label = 'clarify' if not flows else ('plan' if len(flows) > 1 else flows[0])
    return label, float(parsed['confidence'])


def score_nlu(labels:int=0, seed=None, provider:str|None=None) -> tuple:
    """Teacher-forced NLU flow detection: replay each conversation, feeding the corpus's own agent
    replies back as context, and on every user turn predict the flow from the full history so far,
    comparing it to the labeled flow. `--labels N` stops once N labels have been scored. Also returns
    the per-prediction `(confidence, is_correct)` records for the confidence-calibration report."""
    correct = total = 0
    misses = []
    records = []
    for case in _sample_cases(labels, seed):
        agent = _build_agent()
        agent._ensure_session()
        for turn in case['turns']:
            if turn.get('role') != 'user':
                if turn.get('utterance'):                  # some agent turns are action-only, no text
                    agent.world.context.add_turn('agent', {'text': turn['utterance']})
                continue
            agent.world.context.add_turn('user', {'text': turn['utterance']})
            expected = _single_flow(turn)
            if expected is None:
                continue                                  # plan / general-ambiguity turn — not scored here
            predicted, confidence = _predict_flow(agent, turn['utterance'], provider)
            total += 1
            is_correct = predicted == expected
            records.append((confidence, is_correct))
            if is_correct:
                correct += 1
            else:
                misses.append(f"{case['convo_id']}: Expected {expected!r}, but got {predicted!r}")
            if total % 10 == 0:
                print(f'  ... {total} predictions, {correct} correct', flush=True)
        agent.close()
        if labels and total >= labels:
            break
    for miss in misses:
        print(f'  miss {miss}')
    return correct, total, records


def _whis_for_one_outlier(groups:list) -> float:
    """Smallest whisker length (in IQR units) that leaves at most ONE outlier in every box. Starts at
    matplotlib's default 1.5*IQR and widens until no box flags more than a single point. Quartiles use
    the same linear ('inclusive') method matplotlib does, so the count matches what it draws."""
    def outlier_count(data, whis):
        q1, _, q3 = statistics.quantiles(data, n=4, method='inclusive')
        iqr = q3 - q1
        lo, hi = q1 - whis * iqr, q3 + whis * iqr
        return sum(1 for val in data if val < lo or val > hi)
    whis = 1.5
    while any(outlier_count(data, whis) > 1 for data in groups if len(data) >= 2) and whis < 100:
        whis += 0.5
    return whis


def _report_confidence(records:list):
    """Split the per-prediction confidences by correctness, print each group's quartiles (p25 / median
    / p75), and save a box-and-whisker plot (correct vs wrong) — so we can see whether the model lowers
    its confidence on the answers it gets wrong."""
    right = [conf for conf, ok in records if ok]
    wrong = [conf for conf, ok in records if not ok]
    print(f'\nconfidence by outcome (n_right={len(right)}, n_wrong={len(wrong)}):')
    for label, data in (('correct', right), ('wrong', wrong)):
        if len(data) >= 2:
            p25, median, p75 = statistics.quantiles(data, n=4, method='inclusive')
            print(f'  {label:7} p25={p25:.3f}  median={median:.3f}  p75={p75:.3f}')
        elif data:
            print(f'  {label:7} single value={data[0]:.3f}')
        else:
            print(f'  {label:7} (none)')
    if not right or not wrong:
        print('  need both a correct and a wrong group to plot; skipping chart.')
        return
    import matplotlib
    matplotlib.use('Agg')                                         # headless: write a PNG, open no window
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.boxplot([right, wrong], tick_labels=[f'correct (n={len(right)})', f'wrong (n={len(wrong)})'],
               whis=_whis_for_one_outlier([right, wrong]), showmeans=True)
    ax.set_ylabel('confidence')
    ax.set_title('Flow-detection confidence: correct vs wrong')
    ax.set_ylim(0, 1)
    out = Path(__file__).parent / 'detection_confidence.png'
    fig.savefig(out, dpi=120, bbox_inches='tight')
    print(f'  saved box plot -> {out}')


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
    parser.add_argument('--provider', default=None,
                        help='override the model family for the run: gemini, gpt, claude, together')
    parser.add_argument('--labels', type=int, default=0,
                        help='score ~N labels from a shuffled corpus sample (0 = an 8-convo dev sample)')
    parser.add_argument('--seed', type=int, default=None,
                        help='seed the shuffle for a reproducible sample')
    args = parser.parse_args()

    if args.provider:
        _set_family(args.provider)
    import backend.components.prompt_engineer as pe
    tier = 'high' if pe.ACTIVE_FAMILY == 'typesafe' else 'med'   # typesafe scores with choice (high)
    print(f'provider={pe.ACTIVE_FAMILY}  detect-flow model={pe.PromptEngineer._resolve_model(tier)}')

    picked = list(SCORERS) if 'all' in args.module else \
        [name.strip() for name in args.module.split(',') if name.strip()]

    failed = False
    for name in picked:
        records = []
        if name == 'nlu':
            correct, total, records = score_nlu(args.labels, args.seed, args.provider)
        else:
            correct, total = SCORERS[name]()
        if total:
            print(f'{name}: {correct}/{total} = {correct / total:.1%} flow-detection accuracy')
        else:
            print(f'{name}: no model-prediction checks defined yet (scope TBD)')
        if records:
            _report_confidence(records)
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
