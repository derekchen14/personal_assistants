"""E2E Agent Evaluations tier (evaluation_suite) — the conversation-level, 7-criteria view.

Runs each scenario end-to-end through the live orchestrator Agent and scores the WHOLE conversation
against the 7 Eval criteria from `_specs/utilities/evaluation_suite.md`. Unlike Traces (per-turn
trajectory, order matters), Evals cares about the FINAL result. All seven are wired — the ground
truth already lives in the corpus (96 examples):
  1 completion  — the turn finished in the right mode                     (is_completed)
  2 correctness — the dispatched tools match the labelled actions          (tool_similarity vs the
                  next agent turn's `actions`)
  3 response    — the reply matches the ground-truth agent turn            (embedding sim by default)
  4 state       — NLU belief detected the labelled flow                    (pred_flows vs labels.stack)
  5 latency     — conversation wall-time vs the 60s budget (measure-only)
  6 ambiguity   — declared when the label says the turn is ambiguous
  7 planning    — plan turns (multi-flow stack) complete

All six non-response criteria are deterministic. Criterion 3 defaults to a cheap OFFLINE embedding
similarity (a small local model, no API) — so scoring adds no model cost beyond running the agent.
`--judge-response` swaps in the LLM-as-judge for a stricter read (a low-tier call; cheap, but opt-in).

  python utils/evaluation_suite/_evals/run_evals.py                 # a fresh sample of 8 (embedding response)
  python utils/evaluation_suite/_evals/run_evals.py --ids B01.C01,B02.C04
  python utils/evaluation_suite/_evals/run_evals.py --judge-response # score criterion 3 with the LLM judge
  python utils/evaluation_suite/_evals/run_evals.py --all           # the whole corpus
"""
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime
from pathlib import Path

_HUGO_ROOT = Path(__file__).resolve().parents[3]
if str(_HUGO_ROOT) not in sys.path:
    sys.path.insert(0, str(_HUGO_ROOT))

from utils.evaluation_suite.harness import (
    _build_agent, _seed_post, _clean_leftovers, _TURN_TIMEOUT_SEC, sample, all_ids, load_cases,
    seed_active_post)
from utils.evaluation_suite.scoring import (
    is_completed, tool_similarity, semantic_similarity, judge_response)
from utils.evaluation_suite._traces.run_traces import _normalize_post, _install_tool_logger, _domain_tools
from utils.evaluation_suite.trace_writer import (
    ambiguity_snapshot, belief_snapshot, diagnose_turn, flow_stack_snapshot, grounding_snapshot,
    make_report_path, REPORT, trace_record, write_record)


def _run_turn(agent, utterance:str) -> dict:
    with ThreadPoolExecutor(max_workers=1) as executor:
        try:
            return executor.submit(agent.take_turn, utterance).result(timeout=_TURN_TIMEOUT_SEC)
        except FuturesTimeoutError:
            return {'message': '(turn timed out)', 'artifact': None}


def _reference_turn(turns:list, idx:int) -> dict:
    """The corpus's ground-truth agent turn for the user turn at `idx` — the next agent turn.
    Every user turn has one (the corpus alternates user/agent), and it carries both the labelled
    `actions` (criterion 2) and the reference `utterance` (criterion 3)."""
    for turn in turns[idx + 1:]:
        if turn.get('role') == 'agent':
            return turn
        if turn.get('role') == 'user':
            break
    return {}


def _history_text(turns:list, idx:int) -> str:
    """The canonical lead-up before the user turn at `idx`, formatted for the response judge."""
    lines = [f"{'User' if turn.get('role') == 'user' else 'Agent'}: {turn['utterance']}"
             for turn in turns[:idx]]
    return '\n'.join(lines)


def _single_flow(turn:dict):
    stack = turn['labels']['stack']
    return stack[0]['flow'] if len(stack) == 1 and stack[0].get('flow') else None


def _top_pred_flow(agent):
    pred = agent.world.state.pred_flows
    return pred[0]['flow_name'] if pred else None


def _score_convo(case:dict, domain_tools:set, judge:bool=False, trace_path:Path|None=None) -> dict:
    """Run one conversation end-to-end and score the criteria at the CONVERSATION level. The response
    judge (criterion 3, the only LLM cost) runs only when `judge` is set."""
    seeded = []
    for entry in case.get('available_data', {}).get('posts', []):
        post = _normalize_post(entry)
        _seed_post(post['post_id'], post['title'], post['sections'])
        seeded.append((post['post_id'], post['title']))

    agent = _build_agent(case['convo_id'])
    seed_active_post(agent, case, seeded)
    tool_log = _install_tool_logger(agent)
    turns = case['turns']
    completion, correctness, response, state, ambiguity, planning = [], [], [], [], [], []
    start = time.time()
    user_turn_number = 0
    for idx, turn in enumerate(turns):
        if turn.get('role') != 'user':
            continue
        user_turn_number += 1
        mark = len(tool_log)
        belief_before = belief_snapshot(agent) if trace_path else {}
        turn_start = time.time()
        result = _run_turn(agent, turn['utterance'])
        latency = time.time() - turn_start
        turn_tools = tool_log[mark:]
        all_tools = [entry['name'] for entry in turn_tools]
        actual = [entry['name'] for entry in turn_tools if entry['name'] in domain_tools]

        ambiguity_after = ambiguity_snapshot(agent)
        ambiguity_level = ambiguity_after['level']
        ok, completion_reason = is_completed(result, turn, ambiguity_level)
        completion.append(1.0 if ok else 0.0)
        reference = _reference_turn(turns, idx)           # the labelled agent turn (actions + reply)
        expected_actions = reference.get('actions', [])
        similarity = tool_similarity(actual, expected_actions)
        correctness.append(similarity)

        if reference.get('utterance'):                    # 3: response — embedding by default, judge
                                                          # opt-in; the final agent turn is action-only
            if judge:
                history = _history_text(turns, idx)
                response.append(1.0 if judge_response(
                    agent.engineer, history, turn['utterance'], reference['utterance'],
                    result['message']) else 0.0)
            else:
                response.append(semantic_similarity(result['message'], reference['utterance']))

        expected_flow = _single_flow(turn)                # 4: belief detected the right flow
        if expected_flow is not None:
            pred = agent.world.state.pred_flows
            state.append(1.0 if pred and pred[0]['flow_name'] == expected_flow else 0.0)
        if turn['ambiguity'] is not None:                 # 6: declare when present
            ambiguity.append(1.0 if ambiguity_level else 0.0)
        if len(turn['labels']['stack']) > 1:              # 7: plan turn completes
            planning.append(1.0 if ok else 0.0)
        if trace_path:
            stack_after = flow_stack_snapshot(agent)
            expected_flow = _single_flow(turn)
            diagnosis = diagnose_turn(
                ok, result, expected_flow, _top_pred_flow(agent), ambiguity_after,
                expected_actions, actual, similarity, stack_after)
            record = trace_record(
                case, idx, user_turn_number, turn, result, expected_actions, actual, all_tools,
                ok, completion_reason, similarity, latency, belief_before,
                belief_snapshot(agent), stack_after, grounding_snapshot(agent), ambiguity_after,
                diagnosis)
            write_record(trace_path, record)
    agent.close()
    for post_id, title in seeded:
        _clean_leftovers(post_id, title)

    return {
        'completion': _mean(completion), 'correctness': _mean(correctness),
        'response': _mean(response), 'state': _mean(state),
        'ambiguity': _mean(ambiguity), 'planning': _mean(planning),
        'latency_secs': round(time.time() - start, 1),
    }


def _mean(values:list):
    return round(sum(values) / len(values), 3) if values else None


_CRITERIA = ('completion', 'correctness', 'response', 'state', 'ambiguity', 'planning')


def _write_eval_report(ids:list, results:list[dict], aggregate:dict) -> Path:
    REPORT.mkdir(exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    path = REPORT / f'evals_{stamp}.json'
    payload = {
        'ids': ids,
        'results': {cid: result for cid, result in zip(ids, results)},
        'aggregate': aggregate,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--ids', default='', help='comma-separated convo_ids (feature-relevant set)')
    parser.add_argument('--all', action='store_true', help='the whole corpus (slow, paid)')
    parser.add_argument('--sample', type=int, default=8, help='fresh sample size when no --ids given')
    parser.add_argument('--seed', default=None, help='seed for reproducible samples')
    parser.add_argument('--judge-response', action='store_true',
                        help='score criterion 3 with the LLM judge instead of offline embedding similarity')
    parser.add_argument('--trace-report', nargs='?', const='evals_trace', default='',
                        help='write trace JSONL during this eval pass using the optional prefix')
    args = parser.parse_args()

    if args.ids:
        ids = [cid.strip() for cid in args.ids.split(',') if cid.strip()]
    elif args.all:
        ids = all_ids()                                   # the whole train split
    else:
        ids = sample(args.sample, seed=args.seed)          # dev = a fresh random sample
    cases = load_cases(ids)
    print(f"eval ids: {','.join(ids)}")
    trace_path = make_report_path(args.trace_report) if args.trace_report else None
    if trace_path:
        print(f"eval trace report: {trace_path.relative_to(_HUGO_ROOT)}")

    domain_tools = _domain_tools()
    results = [_score_convo(case, domain_tools, args.judge_response, trace_path) for case in cases]
    for cid, res in zip(ids, results):
        line = ' '.join(f'{name}={res[name]}' for name in _CRITERIA)
        print(f"{cid}: {line} | {res['latency_secs']}s")
    aggregate = {
        **{name: _mean([r[name] for r in results if r[name] is not None]) for name in _CRITERIA},
        'latency_mean': _mean([r['latency_secs'] for r in results]),
    }
    eval_report = _write_eval_report(ids, results, aggregate)
    print(f"eval report: {eval_report.relative_to(_HUGO_ROOT)}")
    print(f"\n== {len(cases)} convos ==")
    print(' '.join(f'{name}={aggregate[name]}' for name in _CRITERIA)
          + f" latency_mean={aggregate['latency_mean']}s")


if __name__ == '__main__':
    main()
