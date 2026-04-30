"""PEX module-level golden tests.

Two parameterized tables cover the policy execution surface:

  test_pex_deterministic_policy: policies that don't call any LLM (only tools).
  test_pex_agentic_policy: policies that call llm_execute, skill_call, or engineer().

Both use real_tools for the tool boundary. Agentic tests stub all engineer
methods so no API calls fire. Each row exercises one unique policy contract;
adding a new flow path = add one row.
"""

from __future__ import annotations

from collections.abc import Callable
from unittest.mock import MagicMock

import pytest

from backend.modules.policies.base import BasePolicy

from utils.tests.policy_evals.fixtures import (
    build_policy,
    make_context,
    make_state,
    real_tools,
)


# ── Helpers ────────────────────────────────────────────────────────────────


def _stub_engineer_for_pex(policy, monkeypatch, *, llm_text:str='', tool_log:list|None=None,
                           skill_text:str=''):
    """Stub every LLM call site a policy might use.
      - BasePolicy.llm_execute → (llm_text, tool_log)
      - engineer.tool_call → same
      - engineer.skill_call → skill_text
      - engineer(prompt, ...) → skill_text
    apply_guardrails, load_skill_template, tool_succeeded, extract_tool_result
    are preserved (pure Python helpers, not LLM calls)."""
    log = list(tool_log or [])

    monkeypatch.setattr(BasePolicy, 'llm_execute',
        lambda self, flow, state, context, tools, **kw: (llm_text, log))

    real = policy.engineer
    mock = MagicMock(return_value=skill_text)
    mock.apply_guardrails = real.apply_guardrails
    mock.load_skill_template = real.load_skill_template
    mock.tool_succeeded = real.tool_succeeded
    mock.extract_tool_result = real.extract_tool_result
    mock.skill_call = MagicMock(return_value=skill_text)
    mock.tool_call = MagicMock(return_value=(llm_text, log))
    monkeypatch.setattr(policy, 'engineer', mock)


def _seed_post(title:str='T', type:str='draft', body:str|None=None) -> str:
    """Seed one post on the (already-monkeypatched) tmp DB. Returns post_id."""
    from backend.utilities.services import PostService, ContentService
    post_id = PostService().create_post(title=title, type=type)['post_id']
    if body:
        ContentService().generate_outline(post_id, body)
    return post_id


def _block_types(frame) -> tuple:
    return tuple(b.block_type for b in frame.blocks)


def _check_ambiguity(comps, expected:tuple|None) -> None:
    """expected: None means no ambiguity; (level, metadata_subset) checks both."""
    amb = comps['ambiguity']
    if expected is None:
        assert not amb.present(), f'unexpected ambiguity: level={amb.level} metadata={amb.metadata}'
        return
    level, meta_subset = expected
    assert amb.present(), 'expected ambiguity declared but none was present'
    assert amb.level == level, f'ambiguity level expected {level!r} got {amb.level!r}'
    for key, val in meta_subset.items():
        assert amb.metadata.get(key) == val, (
            f'ambiguity metadata[{key!r}] expected {val!r} got {amb.metadata.get(key)!r}')


# ── Setup callables (each row references one) ─────────────────────────────


def _setup_create_filled(flow):
    flow.slots['title'].add_one('My Post')
    flow.slots['type'].assign_one('draft')


def _setup_create_missing_title(flow):
    flow.slots['type'].assign_one('draft')


def _setup_inspect_filled(flow, post_id):
    flow.slots['source'].add_one(post=post_id)
    flow.slots['aspect'].assign_one('word_count')


def _setup_inspect_no_source(flow):
    flow.slots['aspect'].assign_one('word_count')


def _setup_explain_with_turn(flow):
    flow.slots['turn_id'].level = 1
    flow.slots['turn_id'].check_if_filled()


def _setup_undo_no_slots(flow):
    pass  # state.active_post controls the path


def _setup_cancel_with_source(flow, post_id):
    # CancelFlow's entity_slot is 'remove' (RemovalSlot, SourceSlot subclass)
    flow.slots['remove'].add_one(post=post_id)


def _setup_cancel_no_source(flow):
    pass


# ── Deterministic table ────────────────────────────────────────────────────


DETERMINISTIC_CASES = [
    {
        'name': 'create_happy_persists_post',
        'flow': 'create',
        'pre_seed': None,  # empty DB
        'setup': _setup_create_filled,
        'state_kwargs': {},
        'expected_origin': 'create',
        'expected_blocks': ('card',),
        'expected_metadata': {},
        'ambiguity': None,
        'flow_status': 'Completed',
        'extras': lambda frame, comps, tools, post_id: (
            # The card carries the new post_id and title from the real create_post call.
            frame.blocks[0].data.get('title') == 'My Post'
            and frame.blocks[0].data.get('status') == 'draft'
            and frame.blocks[0].data.get('post_id')
        ),
    },
    {
        'name': 'create_missing_title_declares_specific',
        'flow': 'create',
        'pre_seed': None,
        'setup': _setup_create_missing_title,
        'state_kwargs': {},
        'expected_origin': 'create',
        'expected_blocks': (),
        'expected_metadata': {},
        'ambiguity': ('specific', {'missing_slot': 'title'}),
        'flow_status': None,  # not Completed; flow stays Active
        'extras': None,
    },
    {
        'name': 'create_duplicate_declares_confirmation',
        'flow': 'create',
        'pre_seed': lambda: _seed_post(title='Dup', type='draft'),
        'setup': lambda flow: (
            flow.slots['title'].add_one('Dup'),
            flow.slots['type'].assign_one('draft'),
        ),
        'state_kwargs': {},
        'expected_origin': 'create',
        'expected_blocks': (),
        'expected_metadata': {'duplicate_title': 'Dup'},
        'ambiguity': ('confirmation', {'duplicate_title': 'Dup'}),
        'flow_status': None,
        'extras': None,
    },
    {
        'name': 'inspect_happy_writes_scratchpad',
        'flow': 'inspect',
        'pre_seed': lambda: _seed_post(title='IT', body='## Intro\n\nA short body.\n'),
        'setup': _setup_inspect_filled,  # gets post_id
        'setup_takes_post_id': True,
        'state_kwargs': {},
        'expected_origin': 'inspect',
        'expected_blocks': (),
        'expected_metadata': {},  # metrics key checked in extras
        'ambiguity': None,
        'flow_status': 'Completed',
        'extras': lambda frame, comps, tools, post_id: (
            'metrics' in frame.metadata
            and 'word_count' in frame.metadata['metrics']
            and comps['memory'].read_scratchpad('inspect') != ''
        ),
    },
    {
        'name': 'inspect_missing_source_declares_partial',
        'flow': 'inspect',
        'pre_seed': None,
        'setup': _setup_inspect_no_source,
        'state_kwargs': {},
        'expected_origin': 'inspect',
        'expected_blocks': (),
        'expected_metadata': {},
        'ambiguity': ('partial', {'missing_entity': 'post'}),
        'flow_status': None,
        'extras': None,
    },
    {
        'name': 'explain_with_turn_id',
        'flow': 'explain',
        'pre_seed': None,
        'setup': _setup_explain_with_turn,
        'state_kwargs': {},
        'expected_origin': 'explain',
        'expected_blocks': (),
        'expected_metadata': {},
        'ambiguity': None,
        'flow_status': 'Completed',
        'extras': None,
    },
    {
        'name': 'undo_no_active_post_declares_partial',
        'flow': 'undo',
        'pre_seed': None,
        'setup': _setup_undo_no_slots,
        'state_kwargs': {},  # active_post stays None
        'expected_origin': 'undo',
        'expected_blocks': (),
        'expected_metadata': {},
        'ambiguity': ('partial', {'missing_entity': 'post'}),
        'flow_status': None,
        'extras': None,
    },
    {
        'name': 'undo_with_active_post_no_snapshots_returns_error',
        'flow': 'undo',
        'pre_seed': lambda: _seed_post(title='U'),
        'setup': _setup_undo_no_slots,
        'pass_post_id_via_state': True,
        'state_kwargs': {},
        'expected_origin': 'undo',
        'expected_blocks': (),
        'expected_metadata': {'violation': 'tool_error', 'failed_tool': 'rollback_post'},
        'ambiguity': None,
        'flow_status': 'Completed',
        'extras': None,
    },
    {
        'name': 'cancel_happy_resets_to_draft',
        'flow': 'cancel',
        'pre_seed': lambda: _seed_post(title='C'),
        'setup': _setup_cancel_with_source,
        'setup_takes_post_id': True,
        'state_kwargs': {},
        'expected_origin': 'cancel',
        'expected_blocks': ('toast',),
        'expected_metadata': {},
        'ambiguity': None,
        'flow_status': 'Completed',
        'extras': lambda frame, comps, tools, post_id: (
            frame.blocks[0].data.get('message') == 'Publication cancelled.'
        ),
    },
    {
        'name': 'cancel_missing_source_declares_partial',
        'flow': 'cancel',
        'pre_seed': None,
        'setup': _setup_cancel_no_source,
        'state_kwargs': {},
        'expected_origin': 'cancel',
        'expected_blocks': (),
        'expected_metadata': {},
        'ambiguity': ('partial', {'missing_entity': 'post'}),
        'flow_status': None,
        'extras': None,
    },
]


@pytest.mark.parametrize('case', DETERMINISTIC_CASES, ids=lambda c: c['name'])
def test_pex_deterministic_policy(case, monkeypatch, tmp_path):
    tools = real_tools(monkeypatch, tmp_path)
    post_id = case['pre_seed']() if case['pre_seed'] else None

    policy, comps = build_policy(case['flow'])
    flow = comps['flow_stack'].stackon(case['flow'])

    if case.get('setup_takes_post_id'):
        case['setup'](flow, post_id)
    else:
        case['setup'](flow)

    state_kwargs = dict(case['state_kwargs'])
    if case.get('pass_post_id_via_state') and post_id:
        state_kwargs['active_post'] = post_id
    state = make_state(**state_kwargs)
    context = make_context(f'test {case["name"]}')

    frame = policy.execute(state, context, tools)

    assert frame.origin == case['expected_origin']
    assert _block_types(frame) == case['expected_blocks']
    for k, v in case['expected_metadata'].items():
        assert frame.metadata.get(k) == v, (
            f'metadata[{k!r}] expected {v!r} got {frame.metadata.get(k)!r}')
    _check_ambiguity(comps, case['ambiguity'])
    if case['flow_status'] is not None:
        assert flow.status == case['flow_status']

    if case['extras']:
        assert case['extras'](frame, comps, tools, post_id), (
            f"row-specific extras assertion failed for {case['name']!r}")


# ── Agentic table ──────────────────────────────────────────────────────────


def _setup_outline_direct(flow, post_id):
    flow.slots['source'].add_one(post=post_id)
    flow.slots['sections'].add_one('intro', 'open')
    flow.slots['sections'].add_one('body', 'argument')
    flow.slots['depth'].level = 3


def _setup_outline_propose(flow, post_id):
    flow.slots['source'].add_one(post=post_id)
    flow.slots['topic'].add_one('early aviation')


def _setup_outline_no_source(flow):
    pass


def _setup_refine_happy(flow, post_id):
    flow.slots['source'].add_one(post=post_id)
    flow.slots['feedback'].add_one('tighten the body')
    flow.slots['steps'].add_one('tighten', 'cut filler')


def _setup_compose_happy(flow, post_id):
    flow.slots['source'].add_one(post=post_id)


def _setup_polish_happy(flow, post_id, sec_id):
    flow.slots['source'].add_one(post=post_id, sec=sec_id)


def _setup_rework_with_suggestions(flow, post_id, sec_id):
    flow.slots['source'].add_one(post=post_id, sec=sec_id)
    flow.slots['suggestions'].add_one('sug_one', 'do A')
    flow.slots['suggestions'].add_one('sug_two', 'do B')
    flow.slots['suggestions'].add_one('sug_three', 'do C')


def _setup_rework_swap(flow, post_id, sec_a, sec_b):
    flow.slots['source'].add_one(post=post_id, sec=sec_a)
    flow.slots['source'].add_one(post=post_id, sec=sec_b)
    flow.slots['category'].assign_one('swap')


def _setup_rework_to_top(flow, post_id, sec_id):
    flow.slots['source'].add_one(post=post_id, sec=sec_id)
    flow.slots['category'].assign_one('to_top')


def _setup_rework_trim_fallback(flow, post_id, sec_id):
    flow.slots['source'].add_one(post=post_id, sec=sec_id)
    flow.slots['category'].assign_one('trim')


def _setup_rework_reframe(flow, post_id, sec_id):
    flow.slots['source'].add_one(post=post_id, sec=sec_id)
    flow.slots['category'].assign_one('reframe')


def _setup_rework_no_directive(flow, post_id, sec_id):
    flow.slots['source'].add_one(post=post_id, sec=sec_id)
    # neither category nor suggestions/remove → specific ambiguity


def _setup_simplify_with_section(flow, post_id, sec_id):
    flow.slots['source'].add_one(post=post_id, sec=sec_id)
    flow.slots['guidance'].add_one('shorten and clarify')


def _setup_simplify_no_source(flow):
    pass  # source AND image both empty → partial ambiguity


def _setup_add_points(flow, post_id, sec_id):
    flow.slots['source'].add_one(post=post_id, sec=sec_id)
    flow.slots['points'].add_one('p1', 'add example')


def _setup_audit_with_post(flow, post_id):
    flow.slots['source'].add_one(post=post_id)


def _setup_release_happy(flow, post_id):
    flow.slots['source'].add_one(post=post_id)
    flow.slots['channel'].add_one('medium')


def _setup_syndicate_no_channel(flow, post_id):
    flow.slots['source'].add_one(post=post_id)
    # channel intentionally empty


def _setup_promote_with_post(flow, post_id):
    flow.slots['source'].add_one(post=post_id)


def _setup_survey_no_slots(flow):
    pass  # SurveyFlow has only `channel` (optional); policy doesn't gate on slots


# Helper: seed a post with one named section. Returns (post_id, sec_id).
def _seed_post_with_section(title='T', sec_title='Intro', body='Some text.'):
    from backend.utilities.services import PostService, ContentService
    post_id = PostService().create_post(title=title, type='draft')['post_id']
    ContentService().generate_outline(post_id, f'## {sec_title}\n\n{body}\n')
    sec_ids = PostService().read_metadata(post_id)['section_ids']
    return post_id, sec_ids[0] if sec_ids else 'intro'


# Helper: seed a post with three named sections. Returns (post_id, [sec_a, sec_b, sec_c]).
def _seed_post_with_three_sections(title='T'):
    from backend.utilities.services import PostService, ContentService
    post_id = PostService().create_post(title=title, type='draft')['post_id']
    body = '## Alpha\n\nAlpha body.\n\n## Beta\n\nBeta body.\n\n## Gamma\n\nGamma body.\n'
    ContentService().generate_outline(post_id, body)
    sec_ids = PostService().read_metadata(post_id)['section_ids']
    return post_id, sec_ids


def _ok(tool_name:str) -> dict:
    return {'tool': tool_name, 'input': {}, 'result': {'_success': True}}


def _fail(tool_name:str, msg:str='failed') -> dict:
    return {'tool': tool_name, 'input': {},
            'result': {'_success': False, '_message': msg, '_error': 'auth'}}


AGENTIC_CASES = [
    # ── Outline ──────────────────────────────────────────────────────
    {
        'name': 'outline_direct_mode_happy',
        'flow': 'outline',
        'pre_seed': lambda: (_seed_post(title='Av'),),  # tuple → unpacked
        'setup': lambda flow, post_id: _setup_outline_direct(flow, post_id),
        'llm_text': '## Intro\n- bullet\n',
        'tool_log': [_ok('generate_outline')],
        'expected_origin': 'outline',
        'expected_blocks': ('card',),
        'expected_metadata': {},
        'ambiguity': None,
        'flow_status': 'Completed',
    },
    {
        'name': 'outline_missing_source_declares_partial',
        'flow': 'outline',
        'pre_seed': None,
        'setup': lambda flow: _setup_outline_no_source(flow),
        'llm_text': '',
        'tool_log': [],
        'expected_origin': '',  # bare DisplayFrame()
        'expected_blocks': (),
        'expected_metadata': {},
        'ambiguity': ('partial', {}),
        'flow_status': None,
    },
    # ── Refine ───────────────────────────────────────────────────────
    {
        'name': 'refine_happy_with_bullets',
        'flow': 'refine',
        'pre_seed': lambda: (_seed_post(
            title='Av', body='## Intro\n- a\n- b\n- c\n'),),
        'setup': lambda flow, post_id: _setup_refine_happy(flow, post_id),
        'llm_text': 'saved',
        'tool_log': [_ok('revise_content')],
        'expected_origin': 'refine',
        'expected_blocks': ('card',),
        'expected_metadata': {},
        'ambiguity': None,
        'flow_status': 'Completed',
    },
    # ── Compose ──────────────────────────────────────────────────────
    {
        'name': 'compose_happy_includes_preview',
        'flow': 'compose',
        'pre_seed': lambda: _seed_post_with_section(),
        'setup': lambda flow, post_id, sec_id: _setup_compose_happy(flow, post_id),
        'setup_takes_sec_id': True,
        'llm_text': 'composed',
        'tool_log': [_ok('revise_content')],
        'expected_origin': 'compose',
        'expected_blocks': ('card',),
        'expected_metadata': {},
        'ambiguity': None,
        'flow_status': 'Completed',
    },
    # ── Polish ───────────────────────────────────────────────────────
    {
        'name': 'polish_happy_completes',
        'flow': 'polish',
        'pre_seed': lambda: _seed_post_with_section(),
        'setup': lambda flow, post_id, sec_id: _setup_polish_happy(flow, post_id, sec_id),
        'setup_takes_sec_id': True,
        'llm_text': '{"used":[]}',
        'tool_log': [_ok('revise_content')],
        'expected_origin': 'polish',
        'expected_blocks': ('card',),
        'expected_metadata': {},
        'ambiguity': None,
        'flow_status': 'Completed',
    },
    # ── Rework ───────────────────────────────────────────────────────
    {
        # Agentic path: category is null, suggestions drives the skill. Skill emits the uniform
        # JSON shape every turn — `done` is always present, so the policy reads it unconditionally.
        'name': 'rework_agentic_marks_suggestions_done',
        'flow': 'rework',
        'pre_seed': lambda: _seed_post_with_section(),
        'setup': lambda flow, post_id, sec_id: _setup_rework_with_suggestions(flow, post_id, sec_id),
        'setup_takes_sec_id': True,
        'llm_text': '{"summary":"reworked","changes":["x"],"done":["sug_one","sug_two"]}',
        'tool_log': [_ok('revise_content')],
        'expected_origin': 'rework',
        'expected_blocks': ('card',),
        'expected_metadata': {},
        'ambiguity': None,
        'flow_status': 'Completed',
        'extras': lambda frame, comps, tools, post_id, sec_id: (
            sum(1 for s in comps['flow_stack'].get_flow().slots['suggestions'].steps
                if s['checked']) == 2
        ),
    },
    {
        # No category and no itemized changes → specific ambiguity (clarify).
        'name': 'rework_no_directive_specific_ambiguity',
        'flow': 'rework',
        'pre_seed': lambda: _seed_post_with_section(),
        'setup': lambda flow, post_id, sec_id: _setup_rework_no_directive(flow, post_id, sec_id),
        'setup_takes_sec_id': True,
        'llm_text': '',
        'tool_log': [],
        'expected_origin': 'rework',
        'expected_blocks': (),
        'expected_metadata': {},
        'ambiguity': ('specific', {'missing_slot': 'category_or_suggestions'}),
        'flow_status': None,
    },
    {
        # Deterministic dispatch: category=swap with two sec values triggers an outline reorder.
        # No LLM call; verify section_ids order swapped after the policy runs.
        'name': 'rework_swap_reorders_outline',
        'flow': 'rework',
        'pre_seed': lambda: _seed_post_with_three_sections(),
        'setup': lambda flow, post_id, sec_ids: _setup_rework_swap(flow, post_id, sec_ids[0], sec_ids[2]),
        'setup_takes_sec_id': True,
        'llm_text': '',
        'tool_log': [],
        'expected_origin': 'rework',
        'expected_blocks': ('card',),
        'expected_metadata': {},
        'ambiguity': None,
        'flow_status': 'Completed',
        'extras': lambda frame, comps, tools, post_id, sec_ids: (
            tools('read_metadata', {'post_id': post_id})['section_ids']
            == [sec_ids[2], sec_ids[1], sec_ids[0]]
        ),
    },
    {
        # Deterministic dispatch: category=to_top moves the named section to the front.
        'name': 'rework_to_top_moves_section',
        'flow': 'rework',
        'pre_seed': lambda: _seed_post_with_three_sections(),
        'setup': lambda flow, post_id, sec_ids: _setup_rework_to_top(flow, post_id, sec_ids[2]),
        'setup_takes_sec_id': True,
        'llm_text': '',
        'tool_log': [],
        'expected_origin': 'rework',
        'expected_blocks': ('card',),
        'expected_metadata': {},
        'ambiguity': None,
        'flow_status': 'Completed',
        'extras': lambda frame, comps, tools, post_id, sec_ids: (
            tools('read_metadata', {'post_id': post_id})['section_ids'][0] == sec_ids[2]
        ),
    },
    {
        # Deterministic dispatch: category=trim falls back to Simplify; rework flow is invalidated.
        'name': 'rework_trim_falls_back_to_simplify',
        'flow': 'rework',
        'pre_seed': lambda: _seed_post_with_section(),
        'setup': lambda flow, post_id, sec_id: _setup_rework_trim_fallback(flow, post_id, sec_id),
        'setup_takes_sec_id': True,
        'llm_text': '',
        'tool_log': [],
        'expected_origin': 'rework',
        'expected_blocks': (),
        'expected_metadata': {},
        'ambiguity': None,
        'flow_status': None,  # status not set on the rework flow; flow_stack manages the swap
        'extras': lambda frame, comps, tools, post_id, sec_id: (
            comps['flow_stack'].get_flow().flow_type == 'simplify'
        ),
    },
    {
        # Deterministic dispatch: category=reframe declares confirmation ambiguity, resets the
        # category slot, and waits for the user to provide bullets next turn.
        'name': 'rework_reframe_declares_confirmation',
        'flow': 'rework',
        'pre_seed': lambda: _seed_post_with_section(),
        'setup': lambda flow, post_id, sec_id: _setup_rework_reframe(flow, post_id, sec_id),
        'setup_takes_sec_id': True,
        'llm_text': '',
        'tool_log': [],
        'expected_origin': 'rework',
        'expected_blocks': (),
        'expected_metadata': {},
        'ambiguity': ('confirmation', {'category': 'reframe'}),
        'flow_status': None,
        'extras': lambda frame, comps, tools, post_id, sec_id: (
            not comps['flow_stack'].get_flow().slots['category'].filled
        ),
    },
    # ── Simplify ─────────────────────────────────────────────────────
    {
        'name': 'simplify_no_source_or_image_partial',
        'flow': 'simplify',
        'pre_seed': None,
        'setup': lambda flow: _setup_simplify_no_source(flow),
        'llm_text': '',
        'tool_log': [],
        'expected_origin': 'simplify',
        'expected_blocks': (),
        'expected_metadata': {},
        'ambiguity': ('partial', {'missing_entity': 'post_or_image'}),
        'flow_status': None,
    },
    {
        'name': 'simplify_skill_owns_persistence',
        'flow': 'simplify',
        'pre_seed': lambda: _seed_post_with_section(),
        'setup': lambda flow, post_id, sec_id: _setup_simplify_with_section(flow, post_id, sec_id),
        'setup_takes_sec_id': True,
        'llm_text': 'simplified',
        'tool_log': [_ok('revise_content')],
        'expected_origin': 'simplify',
        'expected_blocks': ('card',),
        'expected_metadata': {},
        'ambiguity': None,
        'flow_status': 'Completed',
    },
    # ── Add ──────────────────────────────────────────────────────────
    {
        'name': 'add_points_happy',
        'flow': 'add',
        'pre_seed': lambda: _seed_post_with_section(),
        'setup': lambda flow, post_id, sec_id: _setup_add_points(flow, post_id, sec_id),
        'setup_takes_sec_id': True,
        'llm_text': 'added points',
        'tool_log': [],
        'expected_origin': 'add',
        'expected_blocks': ('card',),
        'expected_metadata': {},
        'ambiguity': None,
        'flow_status': 'Completed',
    },
    # ── Audit ────────────────────────────────────────────────────────
    {
        'name': 'audit_discovery_emits_checklist',
        'flow': 'audit',
        'pre_seed': lambda: (_seed_post(title='Av'),),
        'setup': lambda flow, post_id: _setup_audit_with_post(flow, post_id),
        'llm_text': 'Saved 3 findings.',
        'tool_log': [{'tool': 'save_findings', 'input': {}, 'result': {
            '_success': True,
            'findings': [
                {'sec_id': None, 'issue': 'voice', 'severity': 'high',
                 'note': 'Average sentence length high.', 'reference_posts': []},
                {'sec_id': 'mech', 'issue': 'comp', 'severity': 'medium',
                 'note': 'Negative parallelism.', 'reference_posts': []},
                {'sec_id': 'kh', 'issue': 'wc', 'severity': 'low',
                 'note': 'False range.', 'reference_posts': []},
            ],
            'summary': 'Three findings.', 'references_used': [],
        }}],
        'expected_origin': 'audit',
        'expected_blocks': ('checklist',),
        'expected_metadata': {'summary': 'Three findings.'},
        'ambiguity': None,
        'flow_status': None,  # audit stays Pending until children pop
    },
    # ── Release / Publish ────────────────────────────────────────────
    {
        'name': 'release_happy_publishes',
        'flow': 'release',
        'pre_seed': lambda: (_seed_post(title='ReleaseMe'),),
        'setup': lambda flow, post_id: _setup_release_happy(flow, post_id),
        'llm_text': 'Published.',
        'tool_log': [_ok('channel_status'), _ok('release_post')],
        'expected_origin': 'release',
        'expected_blocks': ('toast',),
        'expected_metadata': {},
        'ambiguity': None,
        'flow_status': 'Completed',
        'extras': lambda frame, comps, tools, post_id: (
            frame.blocks[0].data.get('level') == 'success'
        ),
    },
    {
        'name': 'release_tool_failure_surfaces',
        'flow': 'release',
        'pre_seed': lambda: (_seed_post(title='ReleaseFail'),),
        'setup': lambda flow, post_id: _setup_release_happy(flow, post_id),
        'llm_text': 'failed',
        'tool_log': [_fail('channel_status', 'OAuth')],
        'expected_origin': 'release',
        'expected_blocks': ('toast',),
        'expected_metadata': {},
        'ambiguity': None,
        'flow_status': 'Completed',
        'extras': lambda frame, comps, tools, post_id: (
            'channel_status' in frame.blocks[0].data['message']
            and 'OAuth' in frame.blocks[0].data['message']
        ),
    },
    {
        'name': 'syndicate_missing_channel_specific_ambiguity',
        'flow': 'syndicate',
        'pre_seed': lambda: (_seed_post(title='Syndicate'),),
        'setup': lambda flow, post_id: _setup_syndicate_no_channel(flow, post_id),
        'llm_text': '',
        'tool_log': [],
        'expected_origin': 'syndicate',
        # syndicate's _clarify_with_steps emits a toast block carrying the steps
        'expected_blocks': ('toast',),
        'expected_metadata': {},
        'ambiguity': ('specific', {'missing_slot': 'channel'}),
        'flow_status': None,
    },
    {
        'name': 'promote_with_post_renders_card',
        'flow': 'promote',
        'pre_seed': lambda: (_seed_post(title='Promo'),),
        'setup': lambda flow, post_id: _setup_promote_with_post(flow, post_id),
        'llm_text': 'Promoted.',
        'tool_log': [_ok('promote_post')],
        'expected_origin': 'promote',
        'expected_blocks': ('card',),
        'expected_metadata': {},
        'ambiguity': None,
        'flow_status': 'Completed',
    },
    {
        'name': 'survey_skips_ambiguity_check',
        'flow': 'survey',
        'pre_seed': None,
        'setup': lambda flow: _setup_survey_no_slots(flow),
        'llm_text': 'Survey complete.',
        'tool_log': [],
        'expected_origin': 'survey',
        'expected_blocks': (),  # survey emits no block
        'expected_metadata': {},
        'ambiguity': None,
        'flow_status': 'Completed',
    },
]


@pytest.mark.parametrize('case', AGENTIC_CASES, ids=lambda c: c['name'])
def test_pex_agentic_policy(case, monkeypatch, tmp_path):
    tools = real_tools(monkeypatch, tmp_path)

    # Pre-seed and unpack: pre_seed may return a single value (post_id) or a tuple.
    seed = case['pre_seed']() if case['pre_seed'] else None
    if seed is None:
        post_id, sec_id = None, None
    elif isinstance(seed, tuple):
        if len(seed) == 1:
            post_id, sec_id = seed[0], None
        else:
            post_id, sec_id = seed[0], seed[1]
    else:
        post_id, sec_id = seed, None

    policy, comps = build_policy(case['flow'])
    flow = comps['flow_stack'].stackon(case['flow'])

    if case.get('setup_takes_sec_id'):
        case['setup'](flow, post_id, sec_id)
    elif post_id is not None:
        case['setup'](flow, post_id)
    else:
        case['setup'](flow)

    _stub_engineer_for_pex(policy, monkeypatch,
        llm_text=case['llm_text'], tool_log=case['tool_log'],
        skill_text=case['llm_text'])

    state = make_state(active_post=post_id) if post_id else make_state()
    context = make_context(f'test {case["name"]}')

    frame = policy.execute(state, context, tools)

    assert frame.origin == case['expected_origin'], (
        f'origin expected {case["expected_origin"]!r} got {frame.origin!r}')
    assert _block_types(frame) == case['expected_blocks'], (
        f'blocks expected {case["expected_blocks"]!r} got {_block_types(frame)!r}')
    for k, v in case['expected_metadata'].items():
        assert frame.metadata.get(k) == v, (
            f'metadata[{k!r}] expected {v!r} got {frame.metadata.get(k)!r}')
    _check_ambiguity(comps, case['ambiguity'])
    if case['flow_status'] is not None:
        assert flow.status == case['flow_status']

    extras_fn = case.get('extras')
    if extras_fn is not None:
        if case.get('setup_takes_sec_id'):
            assert extras_fn(frame, comps, tools, post_id, sec_id), (
                f"row-specific extras failed for {case['name']!r}")
        else:
            assert extras_fn(frame, comps, tools, post_id), (
                f"row-specific extras failed for {case['name']!r}")

