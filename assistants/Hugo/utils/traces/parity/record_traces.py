"""Record the §9.2 tool-call trace dev set — 10 trajectories on the NEW orchestrator path.

Each trajectory is a scripted turn (or short sequence) run through a fresh orchestrator-path
Agent. Afterwards the session dir is parsed by trace_recorder.extract_trace and two files are
written under utils/tests/traces/: the raw trace (<nn>_<name>.json) and the human-readable
markdown sidecar (<nn>_<name>.md) with the `APPROVED: [ ]` header Derek checks off. Approval
is the ground-truth event (§9.2 item 3); approved sidecars are committed and frozen.

The 10 trajectories span the space named in changes.md §9.2 item 1: one clean single-flow turn
per major intent (Draft, Revise, Publish, Research), a slot-missing clarification round, an
ambiguity escalation, a plan with chained sub-flows, a pure-click action turn (the decision-13
bypass), a memory recall, and a grounding switch between two posts.

Run from the Hugo root (LLM-heavy, ~1-3 min per trajectory):
  python utils/tests/parity/record_traces.py            # all 10
  python utils/tests/parity/record_traces.py --only click_bypass grounding_switch
Set HUGO_TRACE_KEEP=1 to keep the seeded posts and session dirs for debugging.
"""

import argparse
import json
import os
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime
from pathlib import Path

_HUGO_ROOT = Path(__file__).resolve().parents[3]
if str(_HUGO_ROOT) not in sys.path:
    sys.path.insert(0, str(_HUGO_ROOT))

from dotenv import load_dotenv

load_dotenv(_HUGO_ROOT / '.env')

import schemas.config
schemas.config.EVAL_HARNESS = True

from utils.harness import (_build_agent, _seed_post, _clean_leftovers,
                           _CRASH_FALLBACK, _LOOP_FALLBACK, _TURN_TIMEOUT_SEC)
from utils.traces.parity.trace_recorder import extract_trace, render_sidecar

TRACES_DIR = _HUGO_ROOT / 'utils' / 'traces'

# Static outline proposal for the pure-click turn — mirrors SelectionBlock.svelte's payload
# shape (and e2e's _VISION_STATIC_PROPOSAL pattern) with this trajectory's own topic.
_CLICK_PROPOSAL = [
    {'name': 'Motivation', 'description': 'Why onboarding emails decide activation.'},
    {'name': 'Structure', 'description': 'The three-email arc that converts.'},
    {'name': 'Examples', 'description': 'Annotated emails that worked and why.'},
    {'name': 'Takeaways', 'description': 'A checklist to reuse on the next launch.'},
]

# Seeded section prose, keyed by trajectory. Short, plain paragraphs — enough body for
# revise/preview/triage/inspect to operate on without bloating the seed step.
_SECTIONS_CACHING = {
    'Motivation': ('LLM apps pay for the same tokens over and over. Most production prompts '
                   'share a long stable prefix across requests. Caching that prefix cuts both '
                   'latency and cost without changing model behavior.'),
    'Approach': ('We started by auditing every call site and measuring how many input tokens '
                 'were identical across consecutive requests in the same session. Then we '
                 'restructured prompts so the stable parts came first and the volatile parts '
                 'came last, because cache hits require an exact prefix match. After that we '
                 'froze the system prompt at session start so it never changed between turns. '
                 'Finally we added a dashboard that tracked the cache hit rate per endpoint so '
                 'regressions showed up within a day instead of on the monthly bill.'),
    'Results': ('Cache hit rates settled around eighty percent on chat endpoints. Median '
                'latency dropped by a third and the token bill fell with it. The biggest wins '
                'came from the longest prompts.'),
}
_SECTIONS_WEBHOOK = {
    'Motivation': ('Webhooks look trivial until you run them at scale. Retries, ordering, and '
                   'verification each hide real design decisions. We learned most of them the '
                   'hard way.'),
    'Design': ('Every delivery gets an idempotency key and a signed payload. Consumers verify '
               'the signature and ignore duplicates. A dead-letter queue catches endpoints '
               'that stay down past the retry budget.'),
    'Takeaways': ('Make retries boring and observable. Sign everything. Let consumers replay '
                  'from the dead-letter queue themselves instead of filing tickets.'),
}
_SECTIONS_MIGRATION = {
    'Motivation': ('Our document store was fine until reporting queries arrived. Joins were '
                   'emulated in application code and every dashboard was a special case. '
                   'Postgres was the boring answer we kept avoiding.'),
    'Process': ('We ran dual writes for six weeks with a nightly diff job comparing both '
                'stores. Read traffic moved over table by table behind a flag. The cutover '
                'itself was a non-event because the diff job had been green for a month.'),
    'Lessons': ('Boring technology pays compound interest. Dual writes are cheap insurance. '
                'The diff job found three bugs that code review had missed.'),
}
_SECTIONS_TRACING = {
    'Motivation': ('When a request crosses nine services, a log line is an alibi, not an '
                   'explanation. We needed causality, not grep. Distributed tracing was the '
                   'only tool that showed the whole story.'),
    'Setup': ('We instrumented the ingress first so every request got a trace id at the edge. '
              'Then each service propagated context through headers and queues. Sampling '
              'stayed at one hundred percent in staging and one percent in production.'),
    'Pitfalls': ('Async boundaries drop context unless you carry it explicitly. Clock skew '
                 'makes spans lie. Cardinality on span attributes can melt the collector.'),
    'Takeaways': ('Start at the edge and work inward. Budget for the collector early. Traces '
                  'replaced half of our debugging meetings.'),
}
_SECTIONS_EVALS = {
    'Motivation': ('Shipping prompt changes without evals is gambling with the product. We '
                   'wanted regressions caught before users found them. Building the eval '
                   'harness taught us more than the model docs ever did.'),
    'Approach': ('We keep a golden set of real transcripts and score every prompt change '
                 'against it nightly. Failures block the deploy. The set grows whenever a '
                 'user reports a miss.'),
    'Takeaways': ('Small honest eval sets beat big synthetic ones. Make failures block '
                  'deploys or nobody looks. Review the golden set monthly.'),
}
_SECTIONS_REGRESSION = {
    'Motivation': ('Golden outputs rot the moment the model improves. We needed regression '
                   'testing that judged behavior, not strings. Property checks were the '
                   'answer.'),
    'Method': ('Each test asserts properties of the answer: cites a source, stays under a '
               'length cap, never names a competitor. An LLM judge scores the fuzzy ones. '
               'Property failures are debuggable in a way string diffs never were.'),
    'Takeaways': ('Test properties, not strings. Keep the judge rubric in the repo. Budget '
                  'judge cost like any other CI expense.'),
}
_SECTIONS_EMBEDDING = {
    'Motivation': ('Search quality lives or dies on the embedding model. Benchmarks rarely '
                   'match your corpus. We needed a way to choose without guessing.'),
    'Method': ('We built a golden set of two hundred query-document pairs from real search '
               'logs. Each candidate model was scored on recall at ten over that set. Price '
               'and latency went into the same spreadsheet as quality.'),
    'Takeaways': ('Evaluate on your own corpus, not on leaderboards. A smaller model with '
                  'domain-matched training data beat two larger ones. Re-run the golden set '
                  'quarterly because corpora drift.'),
}
_SECTIONS_RATELIMIT = {
    'Motivation': ('One noisy client can starve everyone else. Rate limiting is the polite '
                   'way to say no. Doing it well is harder than the blog posts admit.'),
    'Algorithms': ('Token buckets handle bursts gracefully and are easy to reason about. '
                   'Sliding windows give smoother limits at the cost of more state. We use '
                   'buckets at the edge and windows on expensive endpoints.'),
    'Takeaways': ('Return the retry-after header every time. Budget limits per API key, not '
                  'per IP. Publish the limits so clients can design around them.'),
}

# ── The 10 trajectories (changes.md §9.2 item 1) ─────────────────────────
# seed_posts: [(post_id, title, sections dict)] created before the session; cleaned up after.
# turns: take_turn kwargs — text / dax / payload. prefs: L2 writes BEFORE the session starts
# (frozen into the system prompt, decision 8).

TRAJECTORIES = [
    {
        'name': 'draft_create',
        'description': ('Clean single-flow **Draft** turn: start a new post from a topic. '
                        'Expected shape: read_state (NLU wrote the detection to belief), stack + '
                        'fill the outline flow via write_state, activate_flow(outline) with a '
                        'completion record, then a direct reply.'),
        'turns': [{'text': 'Create a new post about Evaluating RAG Pipelines in Production'}],
        'cleanup_titles': ['Evaluating RAG Pipelines in Production'],
    },
    {
        'name': 'revise_simplify',
        'description': ('Clean single-flow **Revise** turn: trim a wordy section of a seeded '
                        'post (simplify). The grounded post comes from the utterance; the flow '
                        'must read the section before persisting the trimmed version.'),
        'seed_posts': [('TraceRv1', 'Prompt Caching Strategies for LLM Apps',
                        _SECTIONS_CACHING)],
        'turns': [{'text': 'The Approach section of the prompt caching post is too wordy. '
                           'Cut it down by a sentence or two.'}],
    },
    {
        'name': 'publish_preview',
        'description': ('Clean single-flow **Publish** turn: preview how a seeded post will '
                        'render when published. Read-only on the post; no channel writes.'),
        'seed_posts': [('TracePb1', 'Field Notes from Building a Webhook Service',
                        _SECTIONS_WEBHOOK)],
        'turns': [{'text': 'Show me a preview of how the webhook service post will look '
                           'when published.'}],
    },
    {
        'name': 'research_compare',
        'description': ('Clean single-flow **Research** turn: compare two seeded posts. The '
                        'compare flow needs analysis tools outside the read-only allowlist, '
                        'so the orchestrator MUST dispatch the flow rather than answer from '
                        'direct lookups. Read-only on the corpus.'),
        'seed_posts': [('TraceFnA', 'Hard-Won Lessons Shipping LLM Evals', _SECTIONS_EVALS),
                       ('TraceFnB', 'Regression Testing Prompts Without Golden Outputs',
                        _SECTIONS_REGRESSION)],
        'turns': [{'text': 'Compare my hard-won lessons post about shipping evals with the '
                           'regression testing post. Which one is stronger?'}],
    },
    {
        'name': 'slot_clarify',
        'description': ('Slot-missing clarification round: the tone flow needs a target tone '
                        'the first utterance does not name — the agent must ask (not guess), '
                        'then complete on the follow-up answer. No domain writes on turn 1.'),
        'seed_posts': [('TraceTn1', 'Lessons from Our Postgres Migration',
                        _SECTIONS_MIGRATION)],
        'turns': [{'text': 'Change the tone of the Postgres migration post.'},
                  {'text': 'Make it more conversational and a little playful.'}],
    },
    {
        'name': 'ambiguity_escalation',
        'description': ('Ambiguity escalation: two similarly-titled posts make the revise '
                        'request ambiguous (which post?), and the follow-up answer stays '
                        'ambiguous. The agent should ask via handle_ambiguity on turn 1 and '
                        'escalate on turn 2 (concrete options, e.g. the two titles) — never '
                        'dispatch a domain write while the ambiguity is open.'),
        'seed_posts': [('TraceAmA', 'Migrating Marketplaces to Event Sourcing',
                        _SECTIONS_EVALS),
                       ('TraceAmB', 'Migrating Marketplaces to GraphQL',
                        _SECTIONS_REGRESSION)],
        'turns': [{'text': 'Make the intro of my marketplaces post punchier.'},
                  {'text': 'The marketplace migration one, I just told you.'}],
    },
    {
        'name': 'plan_chain',
        'description': ('Plan with chained sub-flows: a revision plan (triage) followed '
                        'immediately by running its first step. The completion-record handoff '
                        'between the plan flow and the chained sub-flow must be visible.'),
        'seed_posts': [('TracePl1', 'Notes on Distributed Tracing for Microservices',
                        _SECTIONS_TRACING)],
        'turns': [{'text': 'Put together a revision plan for the distributed tracing post, '
                           'then go ahead and run the first step of it.'},
                  {'text': 'Yes, run the first step now, start with the Motivation section.'},
                  {'text': 'Go with the first option you suggested.'}],
        'timeout_sec': 420.0,
    },
    {
        'name': 'click_bypass',
        'description': ('Pure-click action turn (decision 13 bypass): turn 1 creates a post; '
                        'turn 2 is a button click (dax only, no text) picking an outline '
                        'proposal. The click never enters the loop — activate_flow + respond '
                        'run deterministically (bypass-flagged in the trace).'),
        'turns': [{'text': 'Create a new post about Designing Onboarding Emails That Convert'},
                  {'text': '', 'dax': '{002}', 'payload': {'proposals': [_CLICK_PROPOSAL]}}],
        'cleanup_titles': ['Designing Onboarding Emails That Convert'],
    },
    {
        'name': 'memory_recall',
        'description': ('Memory recall: turn 1 stores a preference mid-session (after the '
                        'system-prompt L2 snapshot froze), so turn 2 must actually read L2 '
                        'via manage_memory / the recall flow rather than answer from the '
                        'frozen prompt. The pre-seeded tone preference IS in the snapshot.'),
        'prefs': {'tone': 'conversational, first-person, no buzzwords'},
        'turns': [{'text': 'Remember this as a preference: I want my posts to target '
                           'around 900 words.'},
                  {'text': 'What writing preferences do you have saved for me?'}],
    },
    {
        'name': 'grounding_switch',
        'description': ('Grounding switch between two posts: turn 1 inspects post A (grounds '
                        'it), turn 2 redirects to post B — the grounding block must follow. '
                        "Watch the second turn's write_state/grounding for the switch."),
        'seed_posts': [('TraceSwA', 'Choosing an Embedding Model for Search',
                        _SECTIONS_EMBEDDING),
                       ('TraceSwB', 'A Practical Guide to Rate Limiting',
                        _SECTIONS_RATELIMIT)],
        'turns': [{'text': 'What are the metrics on the embedding model post?'},
                  {'text': 'Now check the rate limiting post instead.'}],
    },
]


# _build_agent / _seed_post / _clean_leftovers now live in utils/harness.py (shared with the
# eval runner) and are imported at the top of this module.


def _run_turn(agent, turn:dict, timeout_sec:float) -> dict:
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(agent.take_turn, turn.get('text', ''),
                                 turn.get('dax'), turn.get('payload'))
        try:
            result = future.result(timeout=timeout_sec)
        except FuturesTimeoutError:
            result = {'message': '(turn timed out)'}
    duration = round(time.perf_counter() - start, 1)
    return {'message': result['message'], 'duration_sec': duration,
            'crashed': result['message'] in (_CRASH_FALLBACK, _LOOP_FALLBACK, '(turn timed out)')}


def _record(spec:dict, idx:int) -> dict:
    print(f"=== [{idx:02d}] {spec['name']} ===")
    for post_id, title, sections in spec.get('seed_posts', []):
        _seed_post(post_id, title, sections)
    agent = _build_agent()
    for key, value in spec.get('prefs', {}).items():
        agent.memory.preferences.store_preference(key, value)  # pre-session → frozen into the prompt

    timeout_sec = spec.get('timeout_sec', _TURN_TIMEOUT_SEC)
    crashes = 0
    for num, turn in enumerate(spec['turns'], 1):
        outcome = _run_turn(agent, turn, timeout_sec)
        if outcome['crashed']:
            print(f"  turn {num} failed ({outcome['message'][:40]!r}) — retrying once")
            outcome = _run_turn(agent, turn, timeout_sec)
        crashes += outcome['crashed']
        print(f"  turn {num} {outcome['duration_sec']:>6.1f}s crashed={outcome['crashed']}")
        print(f"     agent: {outcome['message'][:140]!r}")

    session_dir = agent.world.session_dir()
    trace = extract_trace(session_dir)
    agent.close()

    recorded_at = datetime.now().strftime('%Y-%m-%d')
    stem = f"{idx:02d}_{spec['name']}"
    (TRACES_DIR / f'{stem}.json').write_text(json.dumps(trace, indent=2) + '\n')
    sidecar = render_sidecar(trace, spec['name'], spec['description'], recorded_at)
    (TRACES_DIR / f'{stem}.md').write_text(sidecar)
    print(f'  wrote {stem}.json / {stem}.md '
          f"({sum(len(t['tool_calls']) for t in trace['turns'])} tool calls)")

    if os.getenv('HUGO_TRACE_KEEP') == '1':
        print(f'  kept session {session_dir}')
    else:
        for post_id, title, _ in spec.get('seed_posts', []):
            _clean_leftovers(post_id, title)
        for title in spec.get('cleanup_titles', []):
            _clean_leftovers('', title)
        shutil.rmtree(session_dir, ignore_errors=True)
    return {'name': spec['name'], 'crashes': crashes,
            'tool_calls': sum(len(t['tool_calls']) for t in trace['turns'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only', nargs='*', help='trajectory names to record (default: all)')
    args = parser.parse_args()

    names = {spec['name'] for spec in TRAJECTORIES}
    if args.only:
        unknown = set(args.only) - names
        if unknown:
            sys.exit(f'unknown trajectories: {sorted(unknown)} (valid: {sorted(names)})')

    TRACES_DIR.mkdir(exist_ok=True)
    results = []
    for idx, spec in enumerate(TRAJECTORIES, 1):
        if args.only and spec['name'] not in args.only:
            continue
        results.append(_record(spec, idx))

    print('\nSUMMARY')
    for res in results:
        print(f"  {res['name']:<22} crashes={res['crashes']} tool_calls={res['tool_calls']}")


if __name__ == '__main__':
    main()
