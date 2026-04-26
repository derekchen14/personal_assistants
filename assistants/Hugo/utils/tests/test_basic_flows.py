"""E2E spot-check for the 10 basic flows (Finalizing_Flows.md).

Uses the real agent fixture with live LLM + tool calls. Each test verifies:
  1. Correct flow routing (gold DAX ensures this)
  2. PEX policy executes without error
  3. Agent produces a substantive response

Run:  pytest tests/test_basic_flows.py -v --tb=short
"""

import sys
from pathlib import Path

import pytest

_HUGO_ROOT = Path(__file__).resolve().parents[2]
if str(_HUGO_ROOT) not in sys.path:
    sys.path.insert(0, str(_HUGO_ROOT))


def _merge_block_data(frame:dict) -> dict:
    merged = {}
    for block in frame.get('blocks') or []:
        bd = block.get('data') or {}
        if isinstance(bd, dict):
            merged.update(bd)
    return merged


def _assert_turn(agent, text, dax, flow, intent, *, allow_empty=False):
    """Run a full turn and assert routing + content."""
    result = agent.take_turn(text, dax=dax)
    state = agent.world.current_state()

    assert state.flow_name == flow, \
        f"Expected flow '{flow}', got '{state.flow_name}'"
    assert state.pred_intent == intent, \
        f"Expected intent '{intent}', got '{state.pred_intent}'"

    message = result.get('message', '')
    frame = result.get('frame') or {}
    block_data = _merge_block_data(frame)
    content = block_data.get('content', '') or message

    if not allow_empty:
        assert len(content) > 10 or block_data.get('post_id') or block_data.get('items'), \
            f"No substantive response for {flow} (content_len={len(content)})"

    return result, state


# ── 1. find {001} — Research ─────────────────────────────────────

class TestFind:
    def test_find_by_topic(self, agent):
        _assert_turn(agent, "Search for posts about machine learning",
                     '{001}', 'find', 'Research')

    def test_find_with_count(self, agent):
        _assert_turn(agent, "Show me the top 3 posts about dialogue",
                     '{001}', 'find', 'Research')


# ── 2. inspect {1BD} — Research ──────────────────────────────────

class TestInspect:
    def test_inspect_word_count(self, agent):
        _assert_turn(agent, "How many words is the Ambiguity is the Bottleneck post?",
                     '{1BD}', 'inspect', 'Research')

    def test_inspect_reading_time(self, agent):
        _assert_turn(agent, "What's the reading time for my Expectation Maximization draft?",
                     '{1BD}', 'inspect', 'Research')


# ── 3. refine {02B} — Draft ─────────────────────────────────────

class TestRefine:
    def test_refine_section(self, agent):
        _assert_turn(agent, "Adjust the intro section heading of the Insights around Attention Mechanism draft",
                     '{02B}', 'refine', 'Draft')

    def test_refine_reorder(self, agent):
        _assert_turn(agent, "Reorder the points in my ML as Software 2.0 outline",
                     '{02B}', 'refine', 'Draft')


# ── 4. brainstorm {29A} — Draft ─────────────────────────────────

class TestBrainstorm:
    def test_brainstorm_topic(self, agent):
        _assert_turn(agent, "Brainstorm ideas for a post about leadership",
                     '{29A}', 'brainstorm', 'Draft')

    def test_brainstorm_angles(self, agent):
        _assert_turn(agent, "Give me some angles on writing about productivity habits",
                     '{29A}', 'brainstorm', 'Draft')


# ── 5. outline {002} — Draft ────────────────────────────────────

class TestOutline:
    def test_outline_new_topic(self, agent):
        _assert_turn(agent, "Generate an outline for a post about remote work",
                     '{002}', 'outline', 'Draft')

    def test_outline_specific(self, agent):
        _assert_turn(agent, "Create a structure for an article on AI ethics with 4 sections",
                     '{002}', 'outline', 'Draft')

    def test_outline_propose_no_sections(self, agent):
        """Propose path: candidates render in a selection block, chat line stays short."""
        result, _ = _assert_turn(
            agent, "Generate an outline for a post about remote work",
            '{002}', 'outline', 'Draft', allow_empty=True,
        )
        frame = result.get('frame') or {}
        blocks = frame.get('blocks') or []
        selection = next((b for b in blocks if b.get('type') == 'selection'), None)
        message = result.get('message', '')

        assert selection is not None, \
            f"Expected a selection block in propose mode, got {[b.get('type') for b in blocks]}"
        candidates = (selection.get('data') or {}).get('candidates') or []
        assert len(candidates) >= 2, \
            f"Expected multiple candidates; got {len(candidates)}"
        for cand in candidates:
            assert isinstance(cand, list) and cand, \
                f"Each candidate must be a non-empty list of sections; got {cand!r}"
            for sec in cand:
                assert isinstance(sec, dict) and sec.get('name'), \
                    f"Each section must be a dict with a name; got {sec!r}"
        assert len(message) < 200, \
            f"Chat line should be short; got {len(message)} chars — candidates likely leaked into utterance"

    def test_outline_count_does_not_fill_sections_or_depth(self, agent):
        """A bare section count ("with N sections") must not fill the sections
        ChecklistSlot or the depth LevelSlot — otherwise OutlineFlow skips
        propose mode. Regression for the NLU slot-filling bug where 'with 4
        sections' was being mapped to both sections (hallucinated headings)
        and depth=4. Drives NLU directly so the test doesn't depend on PEX
        post-state (the flow may have been popped during recovery)."""
        agent.world.context.add_turn(
            'User', "Let's make a post about the discovery of flight by the Wright Brothers",
            turn_type='utterance',
        )
        agent.world.context.add_turn(
            'Agent', 'Created "The Discovery of Flight" as a draft.',
            turn_type='utterance',
        )
        utt = "Make an outline with 4 sections"
        agent.world.context.add_turn('User', utt, turn_type='utterance')
        agent.nlu.understand(utt, agent.world.context, dax='{002}', payload={})
        flow = agent.world.flow_stack.find_by_name('outline')
        assert flow is not None, \
            f"OutlineFlow should be on the stack after react('{{002}}'); stack={[(f.name(), f.status) for f in agent.world.flow_stack._stack]}"
        assert not flow.slots['sections'].filled, \
            f"sections was filled from a bare count; steps={flow.slots['sections'].steps}"
        assert flow.slots['depth'].level == 0, \
            f"depth was set from a section count; level={flow.slots['depth'].level}"

    def test_outline_enumeration_fills_sections(self, agent):
        """Positive counter-test: an explicit enumeration of section names must
        fill the sections slot. Guards against the prompt tightening in the
        count-based test over-correcting and missing legitimate enumerations."""
        agent.world.context.add_turn(
            'User', "Let's make a post about the discovery of flight by the Wright Brothers",
            turn_type='utterance',
        )
        agent.world.context.add_turn(
            'Agent', 'Created "The Discovery of Flight" as a draft.',
            turn_type='utterance',
        )
        utt = ("Outline the discovery of flight post with sections on early history, "
               "the wright brothers, the first flights, and lasting impact")
        agent.world.context.add_turn('User', utt, turn_type='utterance')
        agent.nlu.understand(utt, agent.world.context, dax='{002}', payload={})
        flow = agent.world.flow_stack.find_by_name('outline')
        assert flow is not None, \
            f"OutlineFlow should be on the stack; stack={[(f.name(), f.status) for f in agent.world.flow_stack._stack]}"
        assert flow.slots['sections'].filled, \
            f"sections should fill from an explicit enumeration; steps={flow.slots['sections'].steps}"
        assert len(flow.slots['sections'].steps) >= 3, \
            f"Expected ≥3 enumerated sections; got {flow.slots['sections'].steps}"


# ── 6. compose {003} — Draft ────────────────────────────────────

class TestCompose:
    def test_compose_section(self, agent):
        _assert_turn(agent, "Write the introduction section for the Expectation Maximization draft",
                     '{003}', 'compose', 'Draft')

    def test_compose_conclusion(self, agent):
        _assert_turn(agent, "Draft a conclusion for the History of Seq2Seq post",
                     '{003}', 'compose', 'Draft')


# ── 7. polish {3BD} — Revise ────────────────────────────────────

class TestPolish:
    def test_polish_transitions(self, agent):
        _assert_turn(agent, "Clean up the transitions in the intro of Building User Simulators",
                     '{3BD}', 'polish', 'Revise')

    def test_polish_tighten(self, agent):
        _assert_turn(agent, "Tighten the prose in the conclusion of ML as Software 2.0",
                     '{3BD}', 'polish', 'Revise')


# ── 8. audit {13A} — Revise ─────────────────────────────────────

class TestAudit:
    def test_audit_style(self, agent):
        _assert_turn(agent, "Check if Components of Dialogue Systems matches my usual writing style",
                     '{13A}', 'audit', 'Revise')

    def test_audit_voice(self, agent):
        _assert_turn(agent, "Audit the Insights around Attention Mechanism draft against my published posts",
                     '{13A}', 'audit', 'Revise')


# ── 9. simplify {7BD} — Revise ──────────────────────────────────

class TestSimplify:
    def test_simplify_paragraphs(self, agent):
        _assert_turn(agent, "Shorten the paragraphs and simplify the language in the ML as Software 2.0 draft",
                     '{7BD}', 'simplify', 'Revise')

    def test_simplify_sentences(self, agent):
        _assert_turn(agent, "Break up the long sentences in Expectation Maximization",
                     '{7BD}', 'simplify', 'Revise')


# ── 10. release {04A} — Publish ─────────────────────────────────

class TestRelease:
    def test_release_publish(self, agent):
        _assert_turn(agent, "Publish the ML as Software 2.0 draft to the blog",
                     '{04A}', 'release', 'Publish')

    def test_release_live(self, agent):
        _assert_turn(agent, "Make the History of Seq2Seq article live on Substack",
                     '{04A}', 'release', 'Publish')
