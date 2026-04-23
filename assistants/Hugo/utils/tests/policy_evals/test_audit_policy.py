"""Policy-in-isolation tests for the `audit` flow.

Audit parses a structured JSON report ({findings, summary, references_used})
from the skill, writes it to scratchpad under the standard envelope, and
escalates via confirmation ambiguity when any finding has severity='high'.
Parse failure surfaces as a frame with metadata['violation']='parse_failure'.
See `backend/prompts/pex/skills/audit.md` for the expected output shape.
"""

from __future__ import annotations

import json

from backend.modules.policies.base import BasePolicy

from utils.tests.policy_evals.fixtures import (
    assert_frame,
    build_policy,
    make_context,
    make_flow,
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


def test_audit_happy_path_writes_scratchpad(monkeypatch):
    """A valid JSON audit reply with no high-severity findings produces
    origin='audit' with a card block carrying findings + summary, and writes
    the standard envelope (version, turn_number, used_count, summary,
    findings, references_used) to the scratchpad under key 'audit'."""
    policy, comps = build_policy('audit')
    comps['flow_stack'].stackon('audit')
    top = comps['flow_stack'].get_flow()
    top.slots['source'].add_one(post=_POST_ID)

    findings = [
        {'sec_id': 'motivation', 'issue': 'word choice', 'severity': 'low',
         'note': 'one small slip', 'reference_posts': []},
        {'sec_id': 'process', 'issue': 'formatting', 'severity': 'medium',
         'note': 'two em-dashes', 'reference_posts': []},
    ]
    payload = {
        'findings': findings,
        'summary': 'Style mostly on-voice.',
        'references_used': ['post0001'],
    }
    monkeypatch.setattr(BasePolicy, 'llm_execute',
        _stub_llm_execute(json.dumps(payload), tool_log=[]))

    state = make_state(active_post=_POST_ID)
    context = make_context('audit this post', turn_id=2)
    tools = make_tool_stub({
        'read_metadata': [
            {'_success': True, 'post_id': _POST_ID, 'title': 'Aviation',
             'section_ids': []},
        ],
    })

    frame = policy.execute(state, context, tools)

    assert_frame(frame, origin='audit', block_types=('card',))
    card = frame.blocks[0]
    assert card.data['findings'] == findings
    assert card.data['summary'] == 'Style mostly on-voice.'
    assert card.data['post_id'] == _POST_ID

    pad = comps['memory'].read_scratchpad('audit')
    assert pad['version'] == '1'
    assert pad['turn_number'] == context.turn_id
    assert pad['used_count'] == 0
    assert pad['findings'] == findings
    assert pad['summary'] == 'Style mostly on-voice.'
    assert pad['references_used'] == ['post0001']
    assert top.status == 'Completed'


def test_audit_high_severity_declares_confirmation(monkeypatch):
    """When any finding carries severity='high', the policy declares
    confirmation ambiguity with a human-readable observation that names
    the high-severity count and previews the top notes. Frame stays empty
    (no card block), and the flow is not Completed."""
    policy, comps = build_policy('audit')
    comps['flow_stack'].stackon('audit')
    top = comps['flow_stack'].get_flow()
    top.slots['source'].add_one(post=_POST_ID)

    findings = [
        {'sec_id': 'recent-innovations', 'issue': 'sentence structure',
         'severity': 'high', 'note': 'fragment stacking', 'reference_posts': []},
        {'sec_id': None, 'issue': 'formatting', 'severity': 'high',
         'note': '14 em-dashes post-wide', 'reference_posts': []},
        {'sec_id': 'process', 'issue': 'composition', 'severity': 'low',
         'note': 'minor wordiness', 'reference_posts': []},
    ]
    payload = {
        'findings': findings,
        'summary': 'Two high-severity issues.',
        'references_used': [],
    }
    monkeypatch.setattr(BasePolicy, 'llm_execute',
        _stub_llm_execute(json.dumps(payload), tool_log=[]))

    state = make_state(active_post=_POST_ID)
    context = make_context('audit')
    tools = make_tool_stub({
        'read_metadata': [
            {'_success': True, 'post_id': _POST_ID, 'title': 'T',
             'section_ids': []},
        ],
    })

    frame = policy.execute(state, context, tools)

    # Convention #7: human-readable text lives in observation, not metadata.
    assert_frame(frame, origin='audit')
    assert not frame.blocks
    amb = comps['ambiguity']
    assert amb.present()
    assert amb.level == 'confirmation'
    assert '2 high-severity' in amb.observation
    assert 'fragment stacking' in amb.observation
    assert top.status != 'Completed'


def test_audit_parse_error_returns_error_frame(monkeypatch):
    """Parse-failure path — when the skill returns non-JSON
    text, the policy returns DisplayFrame(origin=flow.name(),
    metadata['violation']='parse_failure') with the offending raw text
    in frame.code. No scratchpad write."""
    policy, comps = build_policy('audit')
    comps['flow_stack'].stackon('audit')
    top = comps['flow_stack'].get_flow()
    top.slots['source'].add_one(post=_POST_ID)

    bad_text = 'The post reads well, no formal findings.'
    monkeypatch.setattr(BasePolicy, 'llm_execute',
        _stub_llm_execute(bad_text, tool_log=[]))

    state = make_state(active_post=_POST_ID)
    context = make_context('audit')
    tools = make_tool_stub({
        'read_metadata': [
            {'_success': True, 'post_id': _POST_ID, 'title': 'T',
             'section_ids': []},
        ],
    })

    frame = policy.execute(state, context, tools)

    assert_frame(frame, origin='audit',
                 metadata={'violation': 'parse_failure'},
                 has_code=True)
    assert bad_text in frame.code
    assert comps['memory'].read_scratchpad('audit') == '', 'no scratchpad on parse failure'
    assert top.status != 'Completed'
