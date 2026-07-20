"""Traces-tier runner (step_1_evals.md — Observability Traces, tier 2 of the suite).

Runs each scenario's user turns through a live orchestrator Agent and scores two metrics from the
SAME pass (one live run, no double LLM cost):
  * completion_rate  — did the turn finish in the right mode (completion scorer).
  * tool_match_rate  — did the domain tools called match the following agent turn's `actions`,
                       by mean per-turn Levenshtein similarity (tools scorer). Drift shows as red.

Writes report/<level>_metrics.json and calls the folded-baseline gate. Red-green: the gate stays
green while a metric's `expected_fail` is true (feature unbuilt); flip it off once the agent reliably
hits the target, and a drop below it turns the gate red.

  python utils/evaluation_suite/_traces/run_traces.py                 # score corpus, grade vs baselines
  python utils/evaluation_suite/_traces/run_traces.py --record        # stamp the run into the baseline
  python utils/evaluation_suite/_traces/run_traces.py --ids B01.C01,B01.C08   # subset (human-read)

Wall times (per turn, per conversation, total) are printed in every run and read against the
latency ideals in evaluation_suite.md (TTFT <= 5s | turn <= 10s | convo <= 60s | 8-scenario gate
<= 10 min) — measured, never gated. TTFT prints n/a until streaming lands (step 6). The one gated
latency metric is mean_turn_seconds (red past baseline +20%).
"""
import argparse
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from pathlib import Path

_HUGO_ROOT = Path(__file__).resolve().parents[3]
if str(_HUGO_ROOT) not in sys.path:
    sys.path.insert(0, str(_HUGO_ROOT))

# harness flips schemas.config.EVAL_HARNESS + loads .env at import — wanted here.
from utils.evaluation_suite.harness import (
    _build_agent, _seed_post, _clean_leftovers, _TURN_TIMEOUT_SEC, load_cases, sample,
    seed_active_post, snapshot_post_ids, clean_created_posts)
from utils.evaluation_suite.scoring import is_completed, tool_similarity
from utils.evaluation_suite import scoring as gates
from utils.evaluation_suite.trace_writer import (
    ambiguity_snapshot, belief_snapshot, diagnosis_counts, diagnose_turn, flow_stack_snapshot,
    grounding_snapshot, make_report_path, trace_record, write_record)


def _domain_tools() -> set:
    """The domain tool IDs (keys under `tools:` in schemas/tools.yaml). Everything else the
    orchestrator calls (coordinate_context, call_flow_stack, ...) is plumbing, filtered out."""
    import yaml
    return set(yaml.safe_load((_HUGO_ROOT / 'schemas' / 'tools.yaml').read_text())['tools'])


def _install_tool_logger(agent) -> list:
    """Record every tool call by wrapping pex.call_tool. Returns the shared log."""
    log = []
    original = agent.pex.call_tool

    def logging_tool(tool_name, tool_input):
        entry = {'name': tool_name, 'input': tool_input}
        log.append(entry)
        try:
            result = original(tool_name, tool_input)
        except Exception as exc:
            entry['result_success'] = False
            entry['result_error'] = type(exc).__name__
            entry['result_message'] = str(exc)
            raise
        entry['result_success'] = result.get('_success') if isinstance(result, dict) else None
        entry['result_error'] = result.get('_error') if isinstance(result, dict) else ''
        entry['result_message'] = result.get('_message') if isinstance(result, dict) else ''
        return result

    agent.pex.call_tool = logging_tool
    return log


def _run_turn(agent, utterance:str) -> dict:
    """Run one user turn with a timeout guard, keeping the FULL result dict — completion needs
    result['artifact']['origin'], not just the message."""
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(agent.take_turn, utterance)
        try:
            return future.result(timeout=_TURN_TIMEOUT_SEC)
        except FuturesTimeoutError:
            return {'message': '(turn timed out)', 'artifact': None}


def _normalize_post(post) -> dict:
    """Upgrade the three legacy corpus shapes to the canonical
    {post_id, title, status, sections:{name: prose}} form declared in data_aug_guide.md.
    Temporary until the next regeneration batch rewrites the corpus to emit it directly."""
    if isinstance(post, str):
        post = {'title': post}
    slug = re.sub(r'[^a-z0-9]+', '-', post['title'].lower()).strip('-')
    post_id = post.get('post_id') or post.get('id') or slug
    sections = post.get('sections') or {}
    if isinstance(sections, list):
        sections = {name: f'Placeholder prose for the {name} section.' for name in sections}
    return {'post_id': post_id, 'title': post['title'],
            'status': post.get('status', 'draft'), 'sections': sections}


def _reference_turn(turns:list, idx:int) -> dict:
    for turn in turns[idx + 1:]:
        if turn.get('role') == 'agent':
            return turn
        if turn.get('role') == 'user':
            break
    return {}


def _single_flow(turn:dict):
    stack = turn['labels']['stack']
    return stack[0]['flow'] if len(stack) == 1 and stack[0].get('flow') else None


def _top_pred_flow(agent):
    pred = agent.world.state.pred_flows
    return pred[0]['name'] if pred else None


def _run_case(case:dict, domain_tools:set, report_path:Path) -> tuple[int, int, list, list, list]:
    """Run one scenario inside a content-library boundary that is restored even on failure."""
    before = snapshot_post_ids()
    try:
        return _run_case_inner(case, domain_tools, report_path)
    finally:
        clean_created_posts(before)


def _run_case_inner(case:dict, domain_tools:set, report_path:Path) -> tuple[int, int, list, list, list]:
    """Seed declared posts, run the user turns, score completion + tool similarity per turn. Returns
    (completed_user_turns, total_user_turns, per_turn_tool_similarities, per_turn_seconds,
    trace_records)."""
    seeded = []
    for entry in case.get('available_data', {}).get('posts', []):
        post = _normalize_post(entry)
        _seed_post(post['post_id'], post['title'], post['sections'])
        seeded.append((post['post_id'], post['title']))

    agent = _build_agent(case['convo_id'])
    seed_active_post(agent, case, seeded)
    tool_log = _install_tool_logger(agent)
    completed = total = 0
    sims, turn_secs, records = [], [], []
    for idx, turn in enumerate(case['turns']):
        if turn.get('role') != 'user':
            continue
        total += 1
        mark = len(tool_log)
        belief_before = belief_snapshot(agent)
        start = time.time()
        result = _run_turn(agent, turn['utterance'])
        elapsed = time.time() - start
        turn_secs.append(elapsed)
        turn_tools = tool_log[mark:]
        all_tools = [entry['name'] for entry in turn_tools]
        actual = [entry['name'] for entry in turn_tools if entry['name'] in domain_tools]
        expected = _reference_turn(case['turns'], idx).get('actions', [])
        ambiguity_after = ambiguity_snapshot(agent)
        ambiguity_level = ambiguity_after['level']
        ok, reason = is_completed(result, turn, ambiguity_level)
        sim = tool_similarity(actual, expected)
        completed += ok
        sims.append(sim)
        belief_after = belief_snapshot(agent)
        stack_after = flow_stack_snapshot(agent)
        diagnosis = diagnose_turn(
            ok, result, _single_flow(turn), _top_pred_flow(agent), ambiguity_after, expected,
            actual, sim, stack_after)
        record = trace_record(
            case, idx, total, turn, result, expected, actual, all_tools, ok, reason, sim, elapsed,
            belief_before, belief_after, stack_after, grounding_snapshot(agent), ambiguity_after,
            diagnosis)
        write_record(report_path, record)
        records.append(record)
        belief_label = f"{_top_pred_flow(agent) or '-'} / {agent.world.state.confidence:.2f}"
        print(f"  {case['convo_id']} t{total}: {diagnosis} | complete={'yes' if ok else 'no'} "
              f"| tools={sim:.2f} | belief={belief_label} | {elapsed:.1f}s")
    agent.close()

    for post_id, title in seeded:
        _clean_leftovers(post_id, title)
    return completed, total, sims, turn_secs, records


def _score_corpus(ids:list|None=None, report_path:Path|None=None) -> dict:
    domain_tools = _domain_tools()
    cases = load_cases(ids)
    report_path = report_path or make_report_path('traces')
    sweep_start = time.time()
    results = [_run_case(case, domain_tools, report_path) for case in cases]
    done = sum(r[0] for r in results)
    total = sum(r[1] for r in results)
    sims = [sim for r in results for sim in r[2]]
    turn_secs = [sec for r in results for sec in r[3]]
    records = [record for r in results for record in r[4]]
    for case, result in zip(cases, results):
        transcript = f"database/sessions/{case['convo_id']}/history.jsonl"
        print(f"{case['convo_id']}: {result[0]}/{result[1]} completed in "
              f"{sum(result[3]):.0f}s | transcript {transcript}")
    sweep_secs = time.time() - sweep_start
    # Latency ideals are measured, never gated (evaluation_suite.md: TTFT <= 5s, turn <= 10s,
    # convo <= 60s, 8-scenario gate <= 10 min). mean_turn_seconds alone gates, at baseline +20%.
    worst_convo = max(sum(r[3]) for r in results) if results else 0.0
    worst_turn = max(turn_secs) if turn_secs else 0.0
    print(f'wall time: total {sweep_secs:.0f}s | worst convo {worst_convo:.0f}s | '
          f'worst turn {worst_turn:.1f}s | TTFT n/a (no streaming) | {len(cases)} scenarios')
    return {
        'completion_rate': round(done / total, 4) if total else 0.0,
        'tool_match_rate': round(sum(sims) / len(sims), 4) if sims else 0.0,
        'mean_turn_seconds': round(sum(turn_secs) / len(turn_secs), 2) if turn_secs else 0.0,
        '_diagnoses': diagnosis_counts(records),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--level', default='traces')
    parser.add_argument('--record', action='store_true', help='stamp the run into the baseline')
    parser.add_argument('--ids', default='', help='comma-separated convo_ids (a chosen set)')
    parser.add_argument('--all', action='store_true', help='the whole train split (gated); default is a dev sample of 8')
    parser.add_argument('--sample', type=int, default=8, help='fresh sample size when no --ids given')
    parser.add_argument('--seed', default=None, help='seed for reproducible samples')
    parser.add_argument('--jsonl', action='store_true', help='accepted for compatibility; JSONL is always written')
    args = parser.parse_args()

    explicit = [cid.strip() for cid in args.ids.split(',') if cid.strip()]
    if explicit:
        ids, subset = explicit, True
    elif args.all:
        ids, subset = None, False                 # whole train split → gated
    else:
        ids, subset = sample(args.sample, seed=args.seed), True
    report_path = make_report_path(args.level)
    print(f"trace ids: {','.join(ids) if ids is not None else 'ALL'}")
    print(f"trace report: {report_path.relative_to(_HUGO_ROOT)}")
    metrics = _score_corpus(ids, report_path)
    diagnoses = metrics.pop('_diagnoses')
    print(f"completion_rate={metrics['completion_rate']} "
          f"tool_match_rate={metrics['tool_match_rate']} "
          f"mean_turn_seconds={metrics['mean_turn_seconds']}")
    if diagnoses:
        print(f"diagnoses: {diagnoses}")
    if subset:
        return  # dev / chosen subsets are read by a human, not graded against the train baseline

    gates.REPORT.mkdir(exist_ok=True)
    (gates.REPORT / f'{args.level}_metrics.json').write_text(json.dumps(metrics, indent=2) + '\n')
    if args.record:
        gates.record(args.level)
        print(f'recorded {args.level} baseline')
        return
    sys.exit(gates.evaluate(args.level))


if __name__ == '__main__':
    main()
