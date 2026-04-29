"""Policy-in-isolation tests for the `simplify` flow.

Simplify has a source-or-image guard (both slots elective), and the skill owns section persistence.
The policy only calls `_persist_section` as a secret backup when the skill skipped the
revise_content tool. See `utils/policy_builder/fixes/simplify.md` and
`utils/policy_builder/inventory/simplify.md` for the expected shape.

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
    """Seed a post with one section. Returns (post_id, sec_id)."""
    from backend.utilities.services import PostService, ContentService
    post_id = PostService().create_post(title=title, type='draft')['post_id']
    ContentService().generate_outline(post_id, f'## {sec_title}\n\n{body}\n')
    meta = PostService().read_metadata(post_id)
    sec_id = meta['section_ids'][0] if meta['section_ids'] else 'intro'
    return post_id, sec_id


def test_simplify_source_or_image_guard(monkeypatch, tmp_path):
    """Per inventory/simplify.md § Guard clauses — both source and image
    empty declares partial ambiguity with
    {'missing_slot': 'source_or_image'} and returns an empty frame; no
    llm_execute call."""
    tools = real_tools(monkeypatch, tmp_path)
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

    frame = policy.execute(state, context, tools)

    assert called == []
    assert_frame(frame, origin='simplify')
    amb = comps['ambiguity']
    assert amb.present()
    assert amb.level == 'partial'
    assert amb.metadata == {'missing_entity': 'post_or_image'}


def test_simplify_skill_owns_persistence(monkeypatch, tmp_path):
    """Per fixes/simplify.md § Skill owns persistence, with a policy-level
    backup — when the skill's tool_log contains a successful revise_content,
    `_persist_section` is NOT called by the policy."""
    tools = real_tools(monkeypatch, tmp_path)
    post_id, sec_id = _seed_post_with_section()

    policy, comps = build_policy('simplify')
    comps['flow_stack'].stackon('simplify')
    top = comps['flow_stack'].get_flow()
    top.slots['source'].add_one(post=post_id, sec=sec_id)

    state = make_state(active_post=post_id)
    context = make_context('simplify the intro')

    tool_log = [{'tool': 'revise_content', 'input': {}, 'result': {'_success': True}}]
    monkeypatch.setattr(BasePolicy, 'llm_execute',
        _stub_llm_execute('simplified text', tool_log=tool_log))

    persist_calls:list = []
    def fake_persist(self, post_id, sec_id, text, tools):
        persist_calls.append((post_id, sec_id, text))
    monkeypatch.setattr(BasePolicy, '_persist_section', fake_persist)

    frame = policy.execute(state, context, tools)

    assert persist_calls == [], 'skill already persisted — policy must not'
    assert_frame(frame, origin='simplify', block_types=('card',))
    assert top.status == 'Completed'


def test_simplify_backup_persist_when_skill_skipped(monkeypatch, tmp_path):
    """Per fixes/simplify.md § Skill owns persistence, with a policy-level
    backup — when the tool_log has NO revise_content call, the policy
    falls back to `_persist_section`."""
    tools = real_tools(monkeypatch, tmp_path)
    post_id, sec_id = _seed_post_with_section()

    policy, comps = build_policy('simplify')
    comps['flow_stack'].stackon('simplify')
    top = comps['flow_stack'].get_flow()
    top.slots['source'].add_one(post=post_id, sec=sec_id)

    state = make_state(active_post=post_id)
    context = make_context('simplify it')

    # tool_log deliberately empty — skill replied with text only.
    monkeypatch.setattr(BasePolicy, 'llm_execute',
        _stub_llm_execute('simplified fallback text', tool_log=[]))

    persist_calls:list = []
    def fake_persist(self, post_id, sec_id, text, tools):
        persist_calls.append((post_id, sec_id, text))
    monkeypatch.setattr(BasePolicy, '_persist_section', fake_persist)

    frame = policy.execute(state, context, tools)

    assert len(persist_calls) == 1, 'backup persistence must fire once'
    assert persist_calls[0] == (post_id, sec_id, 'simplified fallback text')
    assert_frame(frame, origin='simplify', block_types=('card',))
