"""Policy-in-isolation tests for the `compose` flow.

Compose delegates section writing to a skill that calls `revise_content` itself; the policy passes
`include_preview=True` so the skill has each section's leading lines without an extra read_metadata
call. When the post has no sections yet, the policy stacks on OutlineFlow and surfaces the reason
inline. See `utils/policy_builder/fixes/compose.md` and `utils/policy_builder/inventory/compose.md`
for the expected shape.

Pillar 2b: tools dispatch to real services on a tmp_path-isolated DB.
"""

from __future__ import annotations

from backend.modules.policies.base import BasePolicy

from utils.tests.policy_evals.fixtures import (
    assert_frame,
    build_policy,
    make_context,
    make_state,
    make_tool_stub,
    real_tools,
)


def _stub_llm_execute(return_text:str, captured:list|None=None):
    def stub(self, flow, state, context, tools, include_preview:bool=False,
            extra_resolved:dict|None=None, exclude_tools:tuple=()):
        if captured is not None:
            captured.append({
                'include_preview': include_preview,
                'extra_resolved': dict(extra_resolved or {}),
            })
        return return_text, []

    return stub


def _seed_post_with_section(title='Aviation', sec_title='Intro', content='opening text'):
    """Seed a post with one section already written. Returns post_id."""
    from backend.utilities.services import PostService, ContentService
    post_id = PostService().create_post(title=title, type='draft')['post_id']
    ContentService().generate_outline(post_id, f'## {sec_title}\n\n{content}\n')
    return post_id


def test_compose_happy_path_includes_preview(monkeypatch, tmp_path):
    """Per fixes/compose.md § Skill owns persistence — when source is filled
    and the post has sections, the policy calls llm_execute with
    include_preview=True (skill plans without re-fetching) and does NOT
    call `_persist_section` itself. Returns origin='compose' with a card."""
    tools = real_tools(monkeypatch, tmp_path)
    post_id = _seed_post_with_section()

    policy, comps = build_policy('compose')
    comps['flow_stack'].stackon('compose')
    top = comps['flow_stack'].get_flow()
    top.slots['source'].add_one(post=post_id)

    state = make_state(active_post=post_id)
    context = make_context('write the intro')

    captured:list = []
    monkeypatch.setattr(BasePolicy, 'llm_execute',
        _stub_llm_execute('composed section', captured=captured))

    persist_calls:list = []
    orig_persist = BasePolicy._persist_section
    def fake_persist(self, post_id, sec_id, text, tools):
        persist_calls.append((post_id, sec_id, text))
        return orig_persist(self, post_id, sec_id, text, tools)
    monkeypatch.setattr(BasePolicy, '_persist_section', fake_persist)

    frame = policy.execute(state, context, tools)

    assert len(captured) == 1
    assert captured[0]['include_preview'] is True
    assert persist_calls == [], 'skill owns persistence; policy must not call _persist_section'

    assert_frame(frame, origin='compose', block_types=('card',))
    assert top.status == 'Completed'


def test_compose_no_sections_stacks_on_outline(monkeypatch):
    """Per fixes/compose.md § Stack-on to OutlineFlow — when the post has
    no sections, the policy stacks on 'outline', sets state.keep_going=True,
    and surfaces the reason in frame.thoughts. llm_execute is not called.

    Synthetic-condition test: real `create_post` seeds placeholder sections so
    we can't naturally produce a 0-section post. Keep the canned stub here.
    """
    _POST_ID = 'abcd1234'
    policy, comps = build_policy('compose')
    comps['flow_stack'].stackon('compose')
    top = comps['flow_stack'].get_flow()
    top.slots['source'].add_one(post=_POST_ID)

    state = make_state(active_post=_POST_ID)
    context = make_context('write it')

    called:list = []
    monkeypatch.setattr(BasePolicy, 'llm_execute',
        _stub_llm_execute('', captured=called))

    tools = make_tool_stub({
        'read_metadata': [
            {'_success': True, 'post_id': _POST_ID, 'title': 'Aviation', 'section_ids': []},
            {'_success': True, 'post_id': _POST_ID, 'title': 'Aviation', 'section_ids': []},
        ],
    })

    frame = policy.execute(state, context, tools)

    assert called == [], 'no sections → stack-on, not llm_execute'
    assert state.keep_going is True
    stacked = comps['flow_stack'].get_flow()
    assert stacked.name() == 'outline'
    assert_frame(frame, thoughts_contains='No sections yet')
