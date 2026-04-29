"""Policy-in-isolation tests for the `polish` flow.

Polish covers small in-paragraph revisions; the policy persists the revised text, inspects the
skill's JSON for consumed scratchpad findings (bumping used_count), and escalates to `rework` when
inspect_post flags structural issues. See `utils/policy_builder/fixes/polish.md` and
`utils/policy_builder/inventory/polish.md` for the expected shape.

Pillar 2b: tools dispatch to real services on a tmp_path-isolated DB.
"""

from __future__ import annotations

from backend.modules.policies.base import BasePolicy

from utils.tests.policy_evals.fixtures import (
    assert_frame,
    build_policy,
    make_context,
    make_state,
    real_tools,
)


def _stub_llm_execute(return_text:str, tool_log:list|None=None):
    log = list(tool_log or [])

    def stub(self, flow, state, context, tools, include_preview:bool=False,
            extra_resolved:dict|None=None, exclude_tools:tuple=()):
        return return_text, log

    return stub


def _seed_post_with_section(title='T', sec_title='Intro', body='Some text.'):
    from backend.utilities.services import PostService, ContentService
    post_id = PostService().create_post(title=title, type='draft')['post_id']
    ContentService().generate_outline(post_id, f'## {sec_title}\n\n{body}\n')
    meta = PostService().read_metadata(post_id)
    sec_id = meta['section_ids'][0] if meta['section_ids'] else 'intro'
    return post_id, sec_id


def test_polish_missing_source_declares_partial(monkeypatch, tmp_path):
    """Entity-missing guard: polish's entity_slot (source) unset declares
    `partial` ambiguity with {'missing_entity': 'post'} per Lesson 2;
    llm_execute is not called."""
    tools = real_tools(monkeypatch, tmp_path)
    policy, comps = build_policy('polish')
    comps['flow_stack'].stackon('polish')

    called:list = []
    def stub(self, *args, **kwargs):
        called.append(1)
        return '', []
    monkeypatch.setattr(BasePolicy, 'llm_execute', stub)

    state = make_state()
    context = make_context('polish')

    frame = policy.execute(state, context, tools)

    assert called == []
    amb = comps['ambiguity']
    assert amb.present()
    assert amb.level == 'partial'
    assert amb.metadata == {'missing_entity': 'post'}


def test_polish_used_count_increments_on_consumed_findings(monkeypatch, tmp_path):
    """Per fixes/polish.md § Policy increments used_count on consumed
    findings — when the skill's JSON reply has `{"used": ["audit",
    "inspect"]}`, the policy bumps those scratchpad entries' used_count
    by 1."""
    tools = real_tools(monkeypatch, tmp_path)
    post_id, sec_id = _seed_post_with_section()

    policy, comps = build_policy('polish')
    comps['flow_stack'].stackon('polish')
    top = comps['flow_stack'].get_flow()
    top.slots['source'].add_one(post=post_id, sec=sec_id)

    # Pre-populate scratchpad with the standard envelope.
    comps['memory'].write_scratchpad('audit', {
        'version': '1', 'turn_number': 1, 'used_count': 0,
        'findings': ['some finding'],
    })
    comps['memory'].write_scratchpad('inspect', {
        'version': '1', 'turn_number': 1, 'used_count': 2,
        'metrics': {'word_count': 100},
    })

    state = make_state(active_post=post_id)
    context = make_context('polish the intro')

    skill_reply = '{"used": ["audit", "inspect"]}'
    monkeypatch.setattr(BasePolicy, 'llm_execute',
        _stub_llm_execute(skill_reply, tool_log=[]))

    monkeypatch.setattr(BasePolicy, '_persist_section',
        lambda self, post_id, sec_id, text, tools: None)

    frame = policy.execute(state, context, tools)

    audit_entry = comps['memory'].read_scratchpad('audit')
    inspect_entry = comps['memory'].read_scratchpad('inspect')
    assert audit_entry['used_count'] == 1
    assert inspect_entry['used_count'] == 3
    assert_frame(frame, origin='polish', block_types=('card',))
    assert top.status == 'Completed'


def test_polish_structural_issues_falls_back_to_rework(monkeypatch, tmp_path):
    """Per fixes/polish.md § Two usage contexts, one code path — when the
    skill's tool_log has an `inspect_post` result with `structural_issues`,
    the policy calls `flow_stack.fallback('rework')`, sets
    state.keep_going=True, and returns an empty frame (no origin/card)."""
    tools = real_tools(monkeypatch, tmp_path)
    post_id, sec_id = _seed_post_with_section()

    policy, comps = build_policy('polish')
    comps['flow_stack'].stackon('polish')
    top = comps['flow_stack'].get_flow()
    top.slots['source'].add_one(post=post_id, sec=sec_id)

    state = make_state(active_post=post_id)
    context = make_context('polish it')

    tool_log = [{
        'tool': 'inspect_post',
        'input': {},
        'result': {
            '_success': True,
            'structural_issues': ['heading_hierarchy_off', 'missing_transition'],
        },
    }]
    monkeypatch.setattr(BasePolicy, 'llm_execute',
        _stub_llm_execute('polished text', tool_log=tool_log))
    monkeypatch.setattr(BasePolicy, '_persist_section',
        lambda self, post_id, sec_id, text, tools: None)

    frame = policy.execute(state, context, tools)

    assert state.keep_going is True
    stacked = comps['flow_stack'].get_flow()
    assert stacked.name() == 'rework'
    assert_frame(frame, origin='polish')
    assert not frame.blocks
