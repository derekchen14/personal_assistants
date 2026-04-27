"""Policy-in-isolation tests for the `audit` flow.

Audit is a 3-branch flow:
  A. Discovery — runs the audit skill, reads `save_findings`, surfaces a ChecklistBlock
     with one row per finding (severity / issue / sec_id label, note as body).
  B. Dispatch — on the next turn the user's picks land in `state.slices['choices']`.
     Policy reads scratchpad findings, runs `_route_findings` (subset case) or
     short-circuits (all-selected case), then `stackon`s each chosen child flow with
     its grouped findings as `suggestions`. Sets `state.has_plan = True`.
  C. Finalize — re-entry after all children popped: marks every `delegates` step
     checked, gathers per-child scratchpad summaries, sets has_plan/keep_going false,
     completes.

See `backend/prompts/pex/skills/audit.md` for the expected save_findings shape.
"""

from __future__ import annotations

from backend.components.prompt_engineer import PromptEngineer
from backend.modules.policies.base import BasePolicy

from utils.tests.policy_evals.fixtures import (
    assert_frame,
    build_policy,
    make_context,
    make_state,
    make_tool_stub,
)


_POST_ID = 'abcd1234'


def _stub_llm_execute(return_text:str, tool_log:list|None=None):
    log = list(tool_log or [])

    def stub(self, flow, state, context, tools, include_preview:bool=False,
            extra_resolved:dict|None=None, exclude_tools:tuple=()):
        return return_text, log

    return stub


def _seed_audit_flow(comps):
    comps['flow_stack'].stackon('audit')
    top = comps['flow_stack'].get_flow()
    top.slots['source'].add_one(post=_POST_ID)
    return top


def _findings_fixture():
    return [
        {'sec_id': None, 'issue': 'sentence structure', 'severity': 'high',
         'note': 'Average sentence length 23.1 vs reference 13.5.', 'reference_posts': []},
        {'sec_id': 'mechanics', 'issue': 'composition', 'severity': 'medium',
         'note': 'Negative parallelism overuse.', 'reference_posts': []},
        {'sec_id': 'kitty-hawk', 'issue': 'word choice', 'severity': 'low',
         'note': 'False range construction.', 'reference_posts': []},
    ]


def test_discovery_emits_checklist_with_per_finding_options(monkeypatch):
    """Branch A: skill emits save_findings → policy puts findings in frame.metadata
    and renders a ChecklistBlock with one option per finding."""
    policy, comps = build_policy('audit')
    top = _seed_audit_flow(comps)

    findings = _findings_fixture()
    tool_result = {'_success': True, 'findings': findings,
                   'summary': 'Three findings spanning voice and structure.', 'references_used': []}
    tool_log = [{'tool': 'save_findings', 'input': tool_result, 'result': tool_result}]
    monkeypatch.setattr(BasePolicy, 'llm_execute',
        _stub_llm_execute('Saved 3 findings.', tool_log=tool_log))

    state = make_state(active_post=_POST_ID)
    context = make_context('audit this post', turn_id=2)
    tools = make_tool_stub({'read_metadata': [
        {'_success': True, 'post_id': _POST_ID, 'title': 'Aviation', 'section_ids': []},
    ]})

    frame = policy.execute(state, context, tools)

    assert_frame(frame, origin='audit', block_types=('checklist',),
                 metadata={'findings': findings,
                           'summary': 'Three findings spanning voice and structure.'})
    block = frame.blocks[0].data
    assert block['submit_dax'] == '{13A}'
    assert block['submit_label'] == 'Send to fix'
    assert len(block['options']) == 3
    assert block['options'][0]['payload'] == 0
    assert block['options'][0]['body'] == findings[0]['note']
    assert '[high]' in block['options'][0]['label']
    assert '(whole post)' in block['options'][0]['label']
    assert '(mechanics)' in block['options'][1]['label']

    assert top.status != 'Completed'
    assert top.stage == 'discovery'


def test_audit_discovery_no_findings_completes_immediately(monkeypatch):
    policy, comps = build_policy('audit')
    top = _seed_audit_flow(comps)

    tool_result = {'_success': True, 'findings': [], 'summary': 'Reads on-voice.', 'references_used': []}
    tool_log = [{'tool': 'save_findings', 'input': tool_result, 'result': tool_result}]
    monkeypatch.setattr(BasePolicy, 'llm_execute',
        _stub_llm_execute('No findings.', tool_log=tool_log))

    state = make_state(active_post=_POST_ID)
    context = make_context('audit this post')
    tools = make_tool_stub({'read_metadata': [
        {'_success': True, 'post_id': _POST_ID, 'title': 'X', 'section_ids': []},
    ]})

    frame = policy.execute(state, context, tools)

    assert_frame(frame, origin='audit', block_types=())
    assert frame.metadata['findings'] == []
    assert top.status == 'Completed'


def test_audit_missing_save_findings_returns_error_frame(monkeypatch):
    policy, comps = build_policy('audit')
    top = _seed_audit_flow(comps)

    monkeypatch.setattr(BasePolicy, 'llm_execute',
        _stub_llm_execute('The post reads well.', tool_log=[]))

    state = make_state(active_post=_POST_ID)
    context = make_context('audit')
    tools = make_tool_stub({'read_metadata': [
        {'_success': True, 'post_id': _POST_ID, 'title': 'T', 'section_ids': []},
    ]})

    frame = policy.execute(state, context, tools)

    assert_frame(frame, origin='audit', metadata={'violation': 'parse_failure'})
    assert comps['memory'].read_scratchpad('audit') == ''
    assert top.status != 'Completed'


def test_dispatch_all_selected_short_circuits_to_rework(monkeypatch):
    """Branch B, all-picked variant: every finding selected → no routing LLM call,
    single Rework stacked with all findings as suggestions."""
    policy, comps = build_policy('audit')
    top = _seed_audit_flow(comps)
    findings = _findings_fixture()
    comps['memory'].write_scratchpad('audit', {
        'version': '1', 'turn_number': 1, 'used_count': 0,
        'findings': findings, 'summary': 's', 'references_used': [],
    })

    # Engineer must NOT be called — the all-selected short-circuit skips routing entirely.
    def fail_engineer(self, *a, **kw):
        raise AssertionError('engineer should not be called when all findings are selected')
    monkeypatch.setattr(PromptEngineer, '__call__', fail_engineer)

    state = make_state(active_post=_POST_ID)
    state.slices['choices'] = [0, 1, 2]
    state.has_plan = False  # discovery filled flow.stage; manually set since we skipped that turn
    top.stage = 'discovery'
    context = make_context('submit picks')
    tools = make_tool_stub({})

    frame = policy.execute(state, context, tools)

    assert top.status != 'Completed'  # audit stays Pending until children pop
    assert top.stage == 'delegation'
    assert state.has_plan is True
    assert state.keep_going is True
    assert len(top.slots['delegates'].steps) == 1
    assert top.slots['delegates'].steps[0]['name'] == 'rework'

    rework = comps['flow_stack'].get_flow()
    assert rework.name() == 'rework'
    assert len(rework.slots['suggestions'].steps) == 3
    src_values = rework.slots['source'].values
    assert any(v.get('post') == _POST_ID for v in src_values), src_values
    assert_frame(frame, origin='audit', thoughts_contains='Routing 3')


def test_dispatch_subset_runs_routing_and_stacks_groups(monkeypatch):
    """Branch B, subset variant: routing returns 2 groups → 2 children stacked,
    delegates slot has 2 entries, has_plan is True."""
    policy, comps = build_policy('audit')
    top = _seed_audit_flow(comps)
    findings = _findings_fixture()
    comps['memory'].write_scratchpad('audit', {
        'version': '1', 'turn_number': 1, 'used_count': 0,
        'findings': findings, 'summary': '', 'references_used': [],
    })

    def stub_engineer(self, prompt, task='skill', model='sonnet', max_tokens=1024, schema=None):
        return {'groups': [
            {'flow_name': 'rework', 'finding_idxs': [0]},
            {'flow_name': 'polish', 'finding_idxs': [1]},
        ]}
    monkeypatch.setattr(PromptEngineer, '__call__', stub_engineer)

    state = make_state(active_post=_POST_ID)
    state.slices['choices'] = [0, 1]  # subset (not all 3)
    top.stage = 'discovery'
    context = make_context('submit')
    tools = make_tool_stub({})

    frame = policy.execute(state, context, tools)

    assert top.stage == 'delegation'
    assert state.has_plan is True
    delegate_names = [s['name'] for s in top.slots['delegates'].steps]
    assert delegate_names == ['rework', 'polish']

    # Top of stack should be the most-recently-stacked child (polish, LIFO).
    top_after = comps['flow_stack'].get_flow()
    assert top_after.name() == 'polish'
    assert len(top_after.slots['suggestions'].steps) == 1
    assert 'composition' in top_after.slots['suggestions'].steps[0]['name']
    assert_frame(frame, origin='audit', thoughts_contains='2 flow')


def test_dispatch_unknown_flow_falls_back_to_polish(monkeypatch):
    """Routing LLM returns a flow_name outside ALLOWED set → coerced to 'polish'."""
    policy, comps = build_policy('audit')
    top = _seed_audit_flow(comps)
    findings = _findings_fixture()
    comps['memory'].write_scratchpad('audit', {
        'version': '1', 'turn_number': 1, 'used_count': 0,
        'findings': findings, 'summary': '', 'references_used': [],
    })

    def stub_engineer(self, prompt, task='skill', model='sonnet', max_tokens=1024, schema=None):
        return {'groups': [{'flow_name': 'rewrite_everything', 'finding_idxs': [0]}]}  # bogus
    monkeypatch.setattr(PromptEngineer, '__call__', stub_engineer)

    state = make_state(active_post=_POST_ID)
    state.slices['choices'] = [0]  # subset to trigger routing
    top.stage = 'discovery'
    context = make_context('submit')
    tools = make_tool_stub({})

    policy.execute(state, context, tools)

    delegate_names = [s['name'] for s in top.slots['delegates'].steps]
    assert delegate_names == ['polish']
    assert comps['flow_stack'].get_flow().name() == 'polish'


def test_finalize_completes_when_all_delegates_verified():
    """Audit re-enters at top after all children have checked themselves off
    in the `delegates` slot. is_verified() trips → status=Completed, has_plan/
    keep_going cleared, scratchpad reports rolled up into metadata."""
    policy, comps = build_policy('audit')
    top = _seed_audit_flow(comps)
    top.stage = 'delegation'
    top.slots['delegates'].add_one(name='rework', description='did rework')
    top.slots['delegates'].add_one(name='polish', description='did polish')
    # Each child is responsible for marking itself complete on success — pre-mark to mimic
    # the post-children state.
    top.slots['delegates'].mark_as_complete('rework')
    top.slots['delegates'].mark_as_complete('polish')

    comps['memory'].write_scratchpad('rework',
        {'version': '1', 'turn_number': 2, 'summary': 'rewrote intro'})
    comps['memory'].write_scratchpad('polish',
        {'version': '1', 'turn_number': 3, 'summary': 'tightened phrasing'})

    state = make_state(active_post=_POST_ID, has_plan=True)
    context = make_context('finalize')
    tools = make_tool_stub({})

    frame = policy.execute(state, context, tools)

    assert top.status == 'Completed'
    assert state.has_plan is False
    assert state.keep_going is False
    reports = frame.metadata['reports']
    assert reports == {'rework': 'rewrote intro', 'polish': 'tightened phrasing'}
    assert_frame(frame, origin='audit', thoughts_contains='Audit completed')
