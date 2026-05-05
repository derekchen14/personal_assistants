"""End-to-end multi-turn ambiguity evals.

Three 2-turn scenarios that exercise the declare → ask → resolve loop end-to-end with
the real LLM. Each scenario seeds a minimal post via service-layer calls, runs two
agent turns, and asserts the post-resolve state — including side-effects: tool calls
recorded in context history and section content actually mutated on disk.

Run:
    pytest utils/tests/e2e_multiturn_evals.py -v -s --tb=short
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_HUGO_ROOT = Path(__file__).resolve().parents[2]
if str(_HUGO_ROOT) not in sys.path:
    sys.path.insert(0, str(_HUGO_ROOT))

from schemas.config import load_config
from backend.agent import Agent
from backend.utilities.services import PostService, ContentService

llm = pytest.mark.llm

_SIMPLIFY_POST_ID = 'mtsimp01'
_POLISH_POST_ID = 'mtpol01a'
_COMPARE_POST_A = 'mtcmpA01'
_COMPARE_POST_B = 'mtcmpB01'

_PROSE_INTRO = (
    'Multi-modal AI agents combine vision, text, and action in a single planning loop. '
    'They are notably more capable than text-only agents on workflow tasks. '
    'Practical deployments still wrestle with cost, latency, and grounding errors.'
)
_PROSE_METHODS = (
    'We started with a vision encoder, a planner, and a tool-use harness. '
    'The encoder produced screenshot embeddings, which the planner consumed alongside the goal. '
    'We logged each tool call with its arguments and result for offline analysis.'
)
_PROSE_RESULTS = (
    'On a held-out workflow set, the multi-modal agent completed 62% of tasks. '
    'The text-only baseline finished 38% on the same set. '
    'Latency averaged 14 seconds per turn, dominated by the vision encoder.'
)


def _make_agent():
    """Spin up an Agent in debug mode (RES skips naturalize)."""
    import backend.agent as agent_mod
    orig = agent_mod.load_config
    agent_mod.load_config = lambda: load_config(overrides={'debug': True})
    try:
        return Agent(username='test_multiturn')
    finally:
        agent_mod.load_config = orig


def _seed_post(post_id:str, title:str, sections:list[tuple[str,str]]) -> None:
    """Create a multi-section post with prose body via service-layer calls.

    `sections` is a list of (section_name, prose_body) pairs.
    """
    psvc = PostService()
    csvc = ContentService()
    psvc.delete_post(post_id)  # idempotent — no-op if missing
    section_names = [name for name, _ in sections]
    create_result = psvc.create_post(
        title=title, sections=section_names, post_id=post_id,
    )
    assert create_result.get('_success'), f'seed create_post failed: {create_result}'
    for sec_name, prose in sections:
        sec_id = sec_name.lower().replace(' ', '-')
        rev_result = csvc.revise_content(post_id, sec_id, prose)
        assert rev_result.get('_success'), f'seed revise_content failed: {rev_result}'


def _set_active_post(agent:Agent, post_id:str) -> None:
    state = agent.world.current_state()
    state.active_post = post_id


def _cleanup(post_ids:list[str]) -> None:
    psvc = PostService()
    for pid in post_ids:
        psvc.delete_post(pid)


def _frame_origin(result:dict) -> str:
    return (result.get('frame') or {}).get('origin', '')


def _block_types(result:dict) -> list[str]:
    blocks = (result.get('frame') or {}).get('blocks') or []
    return [b.get('type') for b in blocks]


def _called(agent:Agent, tool_name:str) -> bool:
    """True if `tool_name` appears in any action turn recorded by pex._dispatch_tool.
    Action turns are written as `[tool:<name>] {json…}` so substring match is fine."""
    return agent.world.context.find_action_by_name(tool_name) is not None


def _read_section_content(post_id:str, sec_id:str) -> str:
    result = PostService().read_section(post_id, sec_id)
    assert result.get('_success'), f'read_section failed for {post_id}/{sec_id}: {result}'
    return result['content']


# ─────────────────────────────────────────────────────────────────────
# Scenario 1: simplify — specific ambiguity on missing suggestions
# ─────────────────────────────────────────────────────────────────────

@llm
def test_simplify_multiturn_resolves_suggestions():
    """Turn 1 names the section but no specific direction → policy declares
    specific(missing='suggestions'). Turn 2 the user provides a directive that
    refers anaphorically back to the section ("shorten *it*") → simplify runs and
    methods section content actually changes on disk."""
    _seed_post(_SIMPLIFY_POST_ID, 'Test Simplify Post', [
        ('Introduction', _PROSE_INTRO),
        ('Methods', _PROSE_METHODS),
        ('Results', _PROSE_RESULTS),
    ])
    methods_before = _read_section_content(_SIMPLIFY_POST_ID, 'methods')
    agent = _make_agent()
    try:
        _set_active_post(agent, _SIMPLIFY_POST_ID)

        # Turn 1: section named, no direction.
        result1 = agent.take_turn('simplify the methods section')
        assert _frame_origin(result1) == 'simplify', \
            f'turn 1 frame origin: {_frame_origin(result1)!r}'
        assert agent.ambiguity.present(), \
            f'expected ambiguity declared on turn 1; result.message={result1.get("message")!r}'
        assert agent.ambiguity.level == 'specific', \
            f'expected specific ambiguity, got level={agent.ambiguity.level!r}'
        meta = agent.ambiguity.metadata
        assert meta.get('missing') == 'suggestions', \
            f'expected missing=suggestions, got metadata={meta!r}'

        # Turn 2: anaphoric directive — `it` refers back to the methods section.
        result2 = agent.take_turn('shorten it to remove fluff words')
        assert not agent.ambiguity.present(), \
            f'expected ambiguity resolved on turn 2; level={agent.ambiguity.level!r} ' \
            f'observation={agent.ambiguity.observation!r} ' \
            f'message={result2.get("message")!r}'
        assert _frame_origin(result2) == 'simplify', \
            f'turn 2 frame origin: {_frame_origin(result2)!r}'

        # Side-effect checks: simplify must call revise_content and the section content must change.
        assert _called(agent, 'revise_content'), \
            'expected revise_content to be called on turn 2'
        methods_after = _read_section_content(_SIMPLIFY_POST_ID, 'methods')
        assert methods_after != methods_before, \
            'expected methods section content to change after simplify ran'
    finally:
        agent.close()
        _cleanup([_SIMPLIFY_POST_ID])


# ─────────────────────────────────────────────────────────────────────
# Scenario 2: polish — confirmation ambiguity on vague direction
# ─────────────────────────────────────────────────────────────────────

@llm
@pytest.mark.parametrize('turn2_utterance', ['yes, go ahead', 'do option 2'])
def test_polish_multiturn_confirms_direction(turn2_utterance):
    """Turn 1 names a real paragraph but with a vague direction → polish skill
    declares confirmation, proposing 2-3 concrete options (per polish.md:34).
    Turn 2 user accepts (full or partial) → polish runs revise_content and the
    methods section content actually changes on disk."""
    _seed_post(_POLISH_POST_ID, 'Test Polish Post', [
        ('Introduction', _PROSE_INTRO),
        ('Methods', _PROSE_METHODS),
    ])
    methods_before = _read_section_content(_POLISH_POST_ID, 'methods')
    agent = _make_agent()
    try:
        _set_active_post(agent, _POLISH_POST_ID)

        # Turn 1: real paragraph reference, vague direction.
        result1 = agent.take_turn(
            'Please clean up the first paragraph in the Methods section to flow better'
        )
        assert _frame_origin(result1) == 'polish', \
            f'turn 1 frame origin: {_frame_origin(result1)!r}'
        assert agent.ambiguity.present(), \
            f'expected ambiguity declared on turn 1; result.message={result1.get("message")!r}'
        assert agent.ambiguity.level == 'confirmation', \
            f'expected confirmation ambiguity, got level={agent.ambiguity.level!r}'
        meta = agent.ambiguity.metadata
        assert 'question' in meta, \
            f'expected metadata.question (clarification utterance), got metadata={meta!r}'

        # Turn 2: accept the proposal (full "yes" or partial "option 2").
        result2 = agent.take_turn(turn2_utterance)
        assert not agent.ambiguity.present(), \
            f'expected ambiguity resolved on turn 2 (utt={turn2_utterance!r}); ' \
            f'level={agent.ambiguity.level!r} ' \
            f'observation={agent.ambiguity.observation!r} message={result2.get("message")!r}'
        assert _frame_origin(result2) == 'polish', \
            f'turn 2 frame origin: {_frame_origin(result2)!r}'

        # Side-effect checks: polish must call revise_content and content must change.
        assert _called(agent, 'revise_content'), \
            f'expected revise_content to be called on turn 2 (utt={turn2_utterance!r})'
        methods_after = _read_section_content(_POLISH_POST_ID, 'methods')
        assert methods_after != methods_before, \
            f'expected methods section content to change after polish ran (utt={turn2_utterance!r})'
    finally:
        agent.close()
        _cleanup([_POLISH_POST_ID])


# ─────────────────────────────────────────────────────────────────────
# Scenario 3: compare — specific ambiguity on missing category
# ─────────────────────────────────────────────────────────────────────

@llm
def test_compare_multiturn_resolves_category():
    """Turn 1 names two posts but no comparison kind → policy declares specific
    ambiguity on missing=category. Turn 2 'tone' → category fills, compare runs.
    Tone-category routes the skill to call `read_section` per post (not `inspect_post`
    or `read_metadata` — those are the inspect/check branches)."""
    _seed_post(_COMPARE_POST_A, 'Multiturn Alpha Test', [
        ('Introduction', _PROSE_INTRO),
        ('Methods', _PROSE_METHODS),
    ])
    _seed_post(_COMPARE_POST_B, 'Multiturn Beta Test', [
        ('Introduction', _PROSE_INTRO),
        ('Results', _PROSE_RESULTS),
    ])
    agent = _make_agent()
    try:
        # No active_post — let NLU resolve both posts from the utterance.

        # Turn 1: name two posts but no comparison kind.
        result1 = agent.take_turn(
            'compare my Multiturn Alpha Test post and my Multiturn Beta Test post'
        )
        assert _frame_origin(result1) == 'compare', \
            f'turn 1 frame origin: {_frame_origin(result1)!r}'
        assert agent.ambiguity.present(), \
            f'expected ambiguity declared on turn 1; message={result1.get("message")!r}'
        assert agent.ambiguity.level == 'specific', \
            f'expected specific ambiguity, got level={agent.ambiguity.level!r}'
        meta = agent.ambiguity.metadata
        assert meta.get('missing') == 'category', \
            f'expected missing=category, got metadata={meta!r}'

        # Turn 2: choose tone category.
        result2 = agent.take_turn('tone')
        assert not agent.ambiguity.present(), \
            f'expected ambiguity resolved on turn 2; level={agent.ambiguity.level!r} ' \
            f'observation={agent.ambiguity.observation!r} ' \
            f'message={result2.get("message")!r}'
        assert _frame_origin(result2) == 'compare', \
            f'turn 2 frame origin: {_frame_origin(result2)!r}'

        # Side-effect checks: tone-category must route to read_section per post and
        # NOT to the inspect/check branches.
        assert _called(agent, 'read_section'), \
            'expected read_section to be called for tone-category compare'
        assert not _called(agent, 'inspect_post'), \
            'inspect_post was called — that is the inspect branch, not tone'
        # The frame should carry a compare block with both post payloads.
        assert 'compare' in _block_types(result2), \
            f'expected compare block in frame; got {_block_types(result2)!r}'
    finally:
        agent.close()
        _cleanup([_COMPARE_POST_A, _COMPARE_POST_B])
