"""Policy-in-isolation tests for the `simplify` flow.

Simplify has a source-or-image guard (both slots elective), and the skill
owns section persistence. The policy only calls `_persist_section` as a
secret backup when the skill skipped the revise_content tool. See
`utils/policy_builder/fixes/simplify.md` and
`utils/policy_builder/inventory/simplify.md` for the expected shape.
"""

from __future__ import annotations

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


def test_simplify_source_or_image_guard(monkeypatch):
    """Per inventory/simplify.md § Guard clauses — both source and image
    empty declares partial ambiguity with
    {'missing_slot': 'source_or_image'} and returns an empty frame; no
    llm_execute call."""
    policy, comps = build_policy('simplify')
    comps['flow_stack'].stackon('simplify')
    # source + image intentionally empty

    called:list = []
    def stub(self, *args, **kwargs):
        called.append(1)
        return '', []
    monkeypatch.setattr(BasePolicy, 'llm_execute', stub)

    state = make_state()
    context = make_context('simplify it')
    tools = make_tool_stub({})

    frame = policy.execute(state, context, tools)

    assert called == []
    assert_frame(frame, origin='simplify')
    amb = comps['ambiguity']
    assert amb.present()
    assert amb.level == 'partial'
    assert amb.metadata == {'missing_entity': 'post_or_image'}


def test_simplify_skill_owns_persistence(monkeypatch):
    """Per fixes/simplify.md § Skill owns persistence, with a policy-level
    backup — when the skill's tool_log contains a successful revise_content,
    `_persist_section` is NOT called by the policy."""
    policy, comps = build_policy('simplify')
    comps['flow_stack'].stackon('simplify')
    top = comps['flow_stack'].get_flow()
    top.slots['source'].add_one(post=_POST_ID, sec='sec_one')

    state = make_state(active_post=_POST_ID)
    context = make_context('simplify the intro')

    tool_log = [{'tool': 'revise_content', 'input': {}, 'result': {'_success': True}}]
    monkeypatch.setattr(BasePolicy, 'llm_execute',
        _stub_llm_execute('simplified text', tool_log=tool_log))

    persist_calls:list = []
    def fake_persist(self, post_id, sec_id, text, tools):
        persist_calls.append((post_id, sec_id, text))
    monkeypatch.setattr(BasePolicy, '_persist_section', fake_persist)

    tools = make_tool_stub({
        'read_metadata': [
            {'_success': True, 'post_id': _POST_ID, 'title': 'T',
             'section_ids': ['sec_one']},
            {'_success': True, 'post_id': _POST_ID, 'title': 'T',
             'status': 'draft', 'section_ids': ['sec_one']},
        ],
        # Two read_section calls: (1) preload target section via extra_resolved,
        # (2) card-building in _read_post_content at the tail.
        'read_section': [
            {'_success': True, 'title': 'Intro', 'content': 'x'},
            {'_success': True, 'title': 'Intro', 'content': 'x'},
        ],
    })

    frame = policy.execute(state, context, tools)

    assert persist_calls == [], 'skill already persisted — policy must not'
    assert_frame(frame, origin='simplify', block_types=('card',))
    assert top.status == 'Completed'


def test_simplify_backup_persist_when_skill_skipped(monkeypatch):
    """Per fixes/simplify.md § Skill owns persistence, with a policy-level
    backup — when the tool_log has NO revise_content call, the policy
    falls back to `_persist_section`."""
    policy, comps = build_policy('simplify')
    comps['flow_stack'].stackon('simplify')
    top = comps['flow_stack'].get_flow()
    top.slots['source'].add_one(post=_POST_ID, sec='sec_one')

    state = make_state(active_post=_POST_ID)
    context = make_context('simplify it')

    # tool_log deliberately empty — skill replied with text only.
    monkeypatch.setattr(BasePolicy, 'llm_execute',
        _stub_llm_execute('simplified fallback text', tool_log=[]))

    persist_calls:list = []
    def fake_persist(self, post_id, sec_id, text, tools):
        persist_calls.append((post_id, sec_id, text))
    monkeypatch.setattr(BasePolicy, '_persist_section', fake_persist)

    tools = make_tool_stub({
        'read_metadata': [
            {'_success': True, 'post_id': _POST_ID, 'title': 'T',
             'section_ids': ['sec_one']},
            {'_success': True, 'post_id': _POST_ID, 'title': 'T',
             'status': 'draft', 'section_ids': ['sec_one']},
        ],
        # Two read_section calls: (1) preload target section, (2) card build.
        'read_section': [
            {'_success': True, 'title': 'Intro', 'content': 'x'},
            {'_success': True, 'title': 'Intro', 'content': 'x'},
        ],
    })

    frame = policy.execute(state, context, tools)

    assert len(persist_calls) == 1, 'backup persistence must fire once'
    assert persist_calls[0] == (_POST_ID, 'sec_one', 'simplified fallback text')
    assert_frame(frame, origin='simplify', block_types=('card',))
