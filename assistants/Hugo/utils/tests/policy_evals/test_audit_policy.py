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
    """save_findings tool call surfaces findings + summary on the card.

    The skill's terminal action is `save_findings(findings, summary, references_used)`;
    the tool writes the scratchpad envelope as a side-effect, and the policy reads back the
    tool result for the card. Test stubs both: a save_findings entry in the tool_log AND a
    direct scratchpad write to mirror what the real tool would do.
    """
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
    tool_result = {
        '_success': True,
        'findings': findings,
        'summary': 'Style mostly on-voice.',
        'references_used': ['post0001'],
    }
    tool_log = [{'tool': 'save_findings', 'input': tool_result, 'result': tool_result}]
    monkeypatch.setattr(BasePolicy, 'llm_execute',
        _stub_llm_execute('Saved 2 findings.', tool_log=tool_log))

    state = make_state(active_post=_POST_ID)
    context = make_context('audit this post', turn_id=2)
    comps['memory'].write_scratchpad('audit', {
        'version': '1', 'turn_number': context.turn_id, 'used_count': 0,
        'findings': findings, 'summary': 'Style mostly on-voice.',
        'references_used': ['post0001'],
    })
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
    assert pad['findings'] == findings
    assert pad['summary'] == 'Style mostly on-voice.'
    assert pad['references_used'] == ['post0001']
    assert top.status == 'Completed'


def test_audit_missing_save_findings_returns_error_frame(monkeypatch):
    """When the skill text returns without ever calling save_findings, the
    policy treats it as parse_failure: error_frame, no scratchpad write,
    flow stays Active for retry."""
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

    assert_frame(frame, origin='audit', metadata={'violation': 'parse_failure'})
    assert comps['memory'].read_scratchpad('audit') == '', 'no scratchpad on parse failure'
    assert top.status != 'Completed'
