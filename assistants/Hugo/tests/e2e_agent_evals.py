"""E2E agent evals — test that the agent completes turns without crashing
and produces semantically correct responses.

Two sections:
  1. Single-turn routing (mock_agent, no API keys): 46 flows × 2 utterances each.
     Tests gold_dax → PEX → RES pipeline produces correct flow/intent/output.
  2. Multi-turn conversations (real LLM, @pytest.mark.llm): 32 two-turn dialogues.
     Tests context carryover, frame types, and response quality.

Run all:       pytest tests/e2e_agent_evals.py -v
Skip LLM:     pytest tests/e2e_agent_evals.py -m "not llm" -v
Only LLM:     pytest tests/e2e_agent_evals.py -m llm -v
"""

import json
from pathlib import Path

import pytest


llm = pytest.mark.llm


# ── Helpers ──────────────────────────────────────────────────────────

def _assert_flow(mock_agent, text, gold_dax, expected_flow, expected_intent):
    """Run a turn and assert flow/intent routing + response existence."""
    result = mock_agent.take_turn(text, gold_dax=gold_dax)
    state = mock_agent.world.current_state()
    assert state.flow_name == expected_flow, (
        f"Expected flow '{expected_flow}', got '{state.flow_name}'"
    )
    assert state.pred_intent == expected_intent, (
        f"Expected intent '{expected_intent}', got '{state.pred_intent}'"
    )
    if expected_intent not in ('Internal', 'Plan'):
        assert result.get('message') or result.get('frame'), (
            f"No message or frame in result for {expected_flow}"
        )
    return result


# ═══════════════════════════════════════════════════════════════════
# Section 1: Single-turn routing (mock_agent, no API keys)
# ═══════════════════════════════════════════════════════════════════

# ── Research (6 flows) ────────────────────────────────────────────

class TestBrowse:
    def test_browse_topics(self, mock_agent):
        _assert_flow(mock_agent, "Show me trending blog topics",
                     '{012}', 'browse', 'Research')

    def test_browse_by_category(self, mock_agent):
        _assert_flow(mock_agent, "What topics do I have in the AI category?",
                     '{012}', 'browse', 'Research')


class TestView:
    def test_view_full_post(self, mock_agent):
        _assert_flow(mock_agent, "Let me see the full post",
                     '{1AD}', 'view', 'Research')

    def test_view_by_title(self, mock_agent):
        _assert_flow(mock_agent, "Open up that article about ambiguity",
                     '{1AD}', 'view', 'Research')


class TestCheck:
    def test_check_draft_status(self, mock_agent):
        _assert_flow(mock_agent, "What's the status of my latest draft?",
                     '{0AD}', 'check', 'Research')

    def test_check_metadata(self, mock_agent):
        _assert_flow(mock_agent, "Show me the metadata for this post",
                     '{0AD}', 'check', 'Research')


class TestInspect:
    def test_inspect_word_count(self, mock_agent):
        _assert_flow(mock_agent, "How many words is this post?",
                     '{1BD}', 'inspect', 'Research')

    def test_inspect_reading_time(self, mock_agent):
        _assert_flow(mock_agent, "What's the reading time for my draft?",
                     '{1BD}', 'inspect', 'Research')


class TestFind:
    def test_find_by_topic(self, mock_agent):
        _assert_flow(mock_agent, "Search for posts about machine learning",
                     '{001}', 'find', 'Research')

    def test_find_by_keyword(self, mock_agent):
        _assert_flow(mock_agent, "Find my articles on productivity",
                     '{001}', 'find', 'Research')


class TestCompare:
    def test_compare_style(self, mock_agent):
        _assert_flow(mock_agent, "Compare the style of my last two posts",
                     '{18A}', 'compare', 'Research')

    def test_compare_with_published(self, mock_agent):
        _assert_flow(mock_agent, "How does this draft differ from my published posts?",
                     '{18A}', 'compare', 'Research')


# ── Draft (7 flows) ──────────────────────────────────────────────

class TestOutline:
    def test_outline_remote_work(self, mock_agent):
        _assert_flow(mock_agent, "Generate an outline for a post about remote work",
                     '{002}', 'outline', 'Draft')

    def test_outline_ai_ethics(self, mock_agent):
        _assert_flow(mock_agent, "Create a structure for an article on AI ethics",
                     '{002}', 'outline', 'Draft')


class TestRefine:
    def test_refine_heading(self, mock_agent):
        _assert_flow(mock_agent, "Adjust the second section heading",
                     '{02B}', 'refine', 'Draft')

    def test_refine_reorder(self, mock_agent):
        _assert_flow(mock_agent, "Reorder the points in my outline",
                     '{02B}', 'refine', 'Draft')


class TestExpand:
    def test_expand_bullets(self, mock_agent):
        _assert_flow(mock_agent, "Flesh out the bullet points in section 2",
                     '{03A}', 'expand', 'Draft')

    def test_expand_notes(self, mock_agent):
        _assert_flow(mock_agent, "Expand my notes into full paragraphs",
                     '{03A}', 'expand', 'Draft')


class TestCompose:
    def test_compose_intro(self, mock_agent):
        _assert_flow(mock_agent, "Write the introduction section about climate change",
                     '{003}', 'compose', 'Draft')

    def test_compose_conclusion(self, mock_agent):
        _assert_flow(mock_agent, "Draft a conclusion for this post",
                     '{003}', 'compose', 'Draft')


class TestAdd:
    def test_add_section(self, mock_agent):
        _assert_flow(mock_agent, "Add a new section called Key Takeaways",
                     '{005}', 'add', 'Draft')

    def test_add_questions_section(self, mock_agent):
        _assert_flow(mock_agent, "Insert a section for reader questions",
                     '{005}', 'add', 'Draft')


class TestCreate:
    def test_create_new_post(self, mock_agent):
        _assert_flow(mock_agent, "Start a new blog post about morning routines",
                     '{05A}', 'create', 'Draft')

    def test_create_titled_post(self, mock_agent):
        _assert_flow(mock_agent, "Create a fresh post titled Lessons from Failure",
                     '{05A}', 'create', 'Draft')


class TestBrainstorm:
    def test_brainstorm_leadership(self, mock_agent):
        _assert_flow(mock_agent, "Brainstorm ideas for a post about leadership",
                     '{29A}', 'brainstorm', 'Draft')

    def test_brainstorm_angles(self, mock_agent):
        _assert_flow(mock_agent, "Give me some angles on writing about habits",
                     '{29A}', 'brainstorm', 'Draft')


# ── Revise (8 flows) ─────────────────────────────────────────────

class TestRework:
    def test_rework_restructure(self, mock_agent):
        _assert_flow(mock_agent, "This draft needs a complete restructure",
                     '{006}', 'rework', 'Revise')

    def test_rework_section(self, mock_agent):
        _assert_flow(mock_agent, "Rewrite the argument in section 3",
                     '{006}', 'rework', 'Revise')


class TestPolish:
    def test_polish_transitions(self, mock_agent):
        _assert_flow(mock_agent, "Clean up the transitions between paragraphs",
                     '{3BD}', 'polish', 'Revise')

    def test_polish_intro(self, mock_agent):
        _assert_flow(mock_agent, "Tighten the prose in the intro",
                     '{3BD}', 'polish', 'Revise')


class TestTone:
    def test_tone_conversational(self, mock_agent):
        _assert_flow(mock_agent, "Make this post more conversational",
                     '{38A}', 'tone', 'Revise')

    def test_tone_formal(self, mock_agent):
        _assert_flow(mock_agent, "Shift the tone to be more formal and academic",
                     '{38A}', 'tone', 'Revise')


class TestAudit:
    def test_audit_style_match(self, mock_agent):
        _assert_flow(mock_agent, "Check if this matches my usual writing style",
                     '{13A}', 'audit', 'Revise')

    def test_audit_voice_compare(self, mock_agent):
        _assert_flow(mock_agent, "Compare this draft's voice to my published posts",
                     '{13A}', 'audit', 'Revise')


class TestFormat:
    def test_format_substack(self, mock_agent):
        _assert_flow(mock_agent, "Format this for Substack publication",
                     '{3AD}', 'format', 'Revise')

    def test_format_blog(self, mock_agent):
        _assert_flow(mock_agent, "Apply blog formatting with proper headings",
                     '{3AD}', 'format', 'Revise')


class TestRemove:
    def test_remove_section(self, mock_agent):
        _assert_flow(mock_agent, "Remove the FAQ section from the post",
                     '{007}', 'remove', 'Revise')

    def test_remove_draft(self, mock_agent):
        _assert_flow(mock_agent, "Delete my old draft about productivity",
                     '{007}', 'remove', 'Revise')


class TestTidy:
    """tidy is in PEX._UNSUPPORTED — verify it returns without error."""

    def test_tidy_no_crash(self, mock_agent):
        result = mock_agent.take_turn("Normalize the heading hierarchy",
                                      gold_dax='{3AB}')
        state = mock_agent.world.current_state()
        assert state.flow_name == 'tidy'
        assert result.get('message') or result.get('frame') is not None


# ── Publish (7 flows) ────────────────────────────────────────────

class TestRelease:
    def test_release_now(self, mock_agent):
        _assert_flow(mock_agent, "Publish this post now",
                     '{04A}', 'release', 'Publish')

    def test_release_live(self, mock_agent):
        _assert_flow(mock_agent, "Make this article live on the blog",
                     '{04A}', 'release', 'Publish')


class TestSyndicate:
    def test_syndicate_linkedin(self, mock_agent):
        _assert_flow(mock_agent, "Cross-post this to LinkedIn",
                     '{04C}', 'syndicate', 'Publish')

    def test_syndicate_twitter(self, mock_agent):
        _assert_flow(mock_agent, "Share this article on Twitter as a thread",
                     '{04C}', 'syndicate', 'Publish')


class TestSchedule:
    def test_schedule_monday(self, mock_agent):
        _assert_flow(mock_agent, "Schedule this post for next Monday at 9am",
                     '{4AC}', 'schedule', 'Publish')

    def test_schedule_date(self, mock_agent):
        _assert_flow(mock_agent, "Set this to publish on March 20th",
                     '{4AC}', 'schedule', 'Publish')


class TestPreview:
    def test_preview_published(self, mock_agent):
        _assert_flow(mock_agent, "Show me how this will look when published",
                     '{4AD}', 'preview', 'Publish')

    def test_preview_substack(self, mock_agent):
        _assert_flow(mock_agent, "Preview the Substack version",
                     '{4AD}', 'preview', 'Publish')


class TestPromote:
    def test_promote_pin(self, mock_agent):
        _assert_flow(mock_agent, "Pin this post to the top of my blog",
                     '{004}', 'promote', 'Publish')

    def test_promote_feature(self, mock_agent):
        _assert_flow(mock_agent, "Feature this article for subscribers",
                     '{004}', 'promote', 'Publish')


class TestCancel:
    def test_cancel_scheduled(self, mock_agent):
        _assert_flow(mock_agent, "Cancel the scheduled publication",
                     '{04F}', 'cancel', 'Publish')

    def test_cancel_unpublish(self, mock_agent):
        _assert_flow(mock_agent, "Unpublish this post",
                     '{04F}', 'cancel', 'Publish')


class TestSurvey:
    def test_survey_platforms(self, mock_agent):
        _assert_flow(mock_agent, "Which publishing platforms are connected?",
                     '{01C}', 'survey', 'Publish')

    def test_survey_health(self, mock_agent):
        _assert_flow(mock_agent, "Show me the health of my publishing platforms",
                     '{01C}', 'survey', 'Publish')


# ── Converse (7 flows) ───────────────────────────────────────────

class TestChatFlow:
    def test_chat_question(self, mock_agent):
        _assert_flow(mock_agent, "What makes a good blog introduction?",
                     '{000}', 'chat', 'Converse')

    def test_chat_seo(self, mock_agent):
        _assert_flow(mock_agent, "Tell me about SEO best practices",
                     '{000}', 'chat', 'Converse')


class TestExplainFlow:
    def test_explain_why(self, mock_agent):
        _assert_flow(mock_agent, "Why did you restructure the outline that way?",
                     '{009}', 'explain', 'Converse')

    def test_explain_what(self, mock_agent):
        _assert_flow(mock_agent, "Explain what you just changed",
                     '{009}', 'explain', 'Converse')


class TestPreference:
    def test_preference_tone(self, mock_agent):
        _assert_flow(mock_agent, "I prefer a casual tone in my posts",
                     '{08A}', 'preference', 'Converse')

    def test_preference_word_count(self, mock_agent):
        _assert_flow(mock_agent, "Set my default word count to 1500",
                     '{08A}', 'preference', 'Converse')


class TestSuggestFlow:
    """suggest is in PEX._UNSUPPORTED — verify it returns without error."""

    def test_suggest_no_crash(self, mock_agent):
        result = mock_agent.take_turn("What should I work on next?",
                                      gold_dax='{29B}')
        state = mock_agent.world.current_state()
        assert state.flow_name == 'suggest'
        assert result.get('message') or result.get('frame') is not None

    def test_suggest_improvements(self, mock_agent):
        result = mock_agent.take_turn("Any suggestions for improving this draft?",
                                      gold_dax='{29B}')
        state = mock_agent.world.current_state()
        assert state.flow_name == 'suggest'


class TestUndo:
    def test_undo_last_edit(self, mock_agent):
        _assert_flow(mock_agent, "Undo the last edit",
                     '{08F}', 'undo', 'Converse')

    def test_undo_revert(self, mock_agent):
        _assert_flow(mock_agent, "Revert what you just did",
                     '{08F}', 'undo', 'Converse')


class TestEndorse:
    def test_endorse_go_ahead(self, mock_agent):
        _assert_flow(mock_agent, "Yes, go ahead with that suggestion",
                     '{09E}', 'endorse', 'Converse')

    def test_endorse_sounds_good(self, mock_agent):
        _assert_flow(mock_agent, "That sounds good, do it",
                     '{09E}', 'endorse', 'Converse')


class TestDismiss:
    def test_dismiss_skip(self, mock_agent):
        _assert_flow(mock_agent, "No thanks, skip that suggestion",
                     '{09F}', 'dismiss', 'Converse')

    def test_dismiss_move_on(self, mock_agent):
        _assert_flow(mock_agent, "Never mind, move on",
                     '{09F}', 'dismiss', 'Converse')


# ── Plan (6 flows) ───────────────────────────────────────────────

class TestBlueprint:
    def test_blueprint_workflow(self, mock_agent):
        _assert_flow(mock_agent, "Plan the full workflow for my AI ethics post",
                     '{25A}', 'blueprint', 'Plan')

    def test_blueprint_steps(self, mock_agent):
        _assert_flow(mock_agent, "Map out the steps from idea to publication",
                     '{25A}', 'blueprint', 'Plan')


class TestTriage:
    def test_triage_revisions(self, mock_agent):
        _assert_flow(mock_agent, "What sections need the most revision?",
                     '{23A}', 'triage', 'Plan')

    def test_triage_prioritize(self, mock_agent):
        _assert_flow(mock_agent, "Prioritize the edits for this draft",
                     '{23A}', 'triage', 'Plan')


class TestCalendarFlow:
    def test_calendar_month(self, mock_agent):
        _assert_flow(mock_agent, "Create a content calendar for the next month",
                     '{24A}', 'calendar', 'Plan')

    def test_calendar_weeks(self, mock_agent):
        _assert_flow(mock_agent, "Schedule out my blog posts for 4 weeks",
                     '{24A}', 'calendar', 'Plan')


class TestScope:
    def test_scope_research(self, mock_agent):
        _assert_flow(mock_agent, "What research do I need before writing about quantum computing?",
                     '{12A}', 'scope', 'Plan')

    def test_scope_define(self, mock_agent):
        _assert_flow(mock_agent, "Define what to gather for the AI ethics post",
                     '{12A}', 'scope', 'Plan')


class TestDigest:
    def test_digest_series(self, mock_agent):
        _assert_flow(mock_agent, "Plan a three-part series on startup lessons",
                     '{25B}', 'digest', 'Plan')

    def test_digest_multi_part(self, mock_agent):
        _assert_flow(mock_agent, "Split this topic into a multi-part blog series",
                     '{25B}', 'digest', 'Plan')


class TestRemember:
    def test_remember_preference(self, mock_agent):
        _assert_flow(mock_agent, "Remember that I prefer Oxford commas",
                     '{19B}', 'remember', 'Plan')

    def test_remember_style(self, mock_agent):
        _assert_flow(mock_agent, "Save this style preference for later",
                     '{19B}', 'remember', 'Plan')


# ── Internal (7 flows) ───────────────────────────────────────────

class TestRecap:
    def test_recap_session(self, mock_agent):
        _assert_flow(mock_agent, "What did we discuss earlier?",
                     '{018}', 'recap', 'Internal')

    def test_recap_topic(self, mock_agent):
        _assert_flow(mock_agent, "Remind me of the topic we picked",
                     '{018}', 'recap', 'Internal')


class TestStore:
    def test_store_tone(self, mock_agent):
        _assert_flow(mock_agent, "Note that the user wants informal tone",
                     '{058}', 'store', 'Internal')

    def test_store_decision(self, mock_agent):
        _assert_flow(mock_agent, "Save this decision for later",
                     '{058}', 'store', 'Internal')


class TestRecall:
    def test_recall_preferences(self, mock_agent):
        _assert_flow(mock_agent, "What are my writing preferences?",
                     '{289}', 'recall', 'Internal')

    def test_recall_tone(self, mock_agent):
        _assert_flow(mock_agent, "Look up my default tone",
                     '{289}', 'recall', 'Internal')


class TestRetrieve:
    def test_retrieve_style_guide(self, mock_agent):
        _assert_flow(mock_agent, "Pull up our style guide",
                     '{049}', 'retrieve', 'Internal')

    def test_retrieve_guidelines(self, mock_agent):
        _assert_flow(mock_agent, "Fetch the editorial guidelines",
                     '{049}', 'retrieve', 'Internal')


class TestSearchInternal:
    def test_search_faq(self, mock_agent):
        _assert_flow(mock_agent, "Look up FAQ about heading conventions",
                     '{189}', 'search', 'Internal')

    def test_search_manual(self, mock_agent):
        _assert_flow(mock_agent, "Search the style manual for citation rules",
                     '{189}', 'search', 'Internal')


class TestReference:
    def test_reference_synonym(self, mock_agent):
        _assert_flow(mock_agent, "What's a synonym for important?",
                     '{139}', 'reference', 'Internal')

    def test_reference_define(self, mock_agent):
        _assert_flow(mock_agent, "Define the word ephemeral",
                     '{139}', 'reference', 'Internal')


class TestStudy:
    def test_study_last_post(self, mock_agent):
        _assert_flow(mock_agent, "Load my last published post for reference",
                     '{1AC}', 'study', 'Internal')

    def test_study_structure(self, mock_agent):
        _assert_flow(mock_agent, "Study the structure of my AI article",
                     '{1AC}', 'study', 'Internal')


# ── Unsupported flow edge case ───────────────────────────────────

class TestDiff:
    def test_diff_no_crash(self, mock_agent):
        result = mock_agent.take_turn("Show me what changed in the intro",
                                      gold_dax='{0BD}')
        state = mock_agent.world.current_state()
        assert state.flow_name == 'diff'
        assert result.get('message') or result.get('frame')


# ═══════════════════════════════════════════════════════════════════
# Section 2: Multi-turn conversations (real LLM, requires API keys)
# ═══════════════════════════════════════════════════════════════════

_EVAL_PATH = Path(__file__).parent / 'test_cases.json'
_RAW_CONVOS = json.loads(_EVAL_PATH.read_text())


def _build_conversations():
    """Transform JSON eval data into test-ready conversation dicts.

    Reads labels (intent, flow, dax) from user turns.
    """
    convos = []
    for raw in _RAW_CONVOS:
        user_turns = [t for t in raw['turns'] if t['role'] == 'user']
        turns = []
        for ut in user_turns:
            labels = ut.get('labels', {})
            turns.append({
                'text': ut['utterance'],
                'dax': labels.get('dax', ''),
                'expect': {'source': labels.get('flow', '')},
                'has_slots': bool(ut.get('slots')),
            })
        convos.append({'id': raw['convo_id'], 'turns': turns})
    return convos


CONVERSATIONS = _build_conversations()


def _run_conversation(agent, conv):
    """Run a multi-turn conversation and return per-turn results."""
    results = []
    for i, turn in enumerate(conv['turns'], 1):
        try:
            result = agent.take_turn(turn['text'], gold_dax=turn['dax'])
            frame = result.get('frame') or {}
            ftype = frame.get('type', '')
            fsource = frame.get('source', '')
            frame_content = frame.get('data', {}).get('content', '')
            message = result.get('message', '')
            content = frame_content or message
            has_content = bool(content and len(content) > 10)

            expect = turn['expect']
            issues = []

            if 'source' in expect:
                if ftype and fsource != expect['source']:
                    issues.append(f"source={fsource} expected={expect['source']}")
                elif not ftype and not has_content:
                    issues.append("no frame, no content")

            if not has_content:
                issues.append('no content')

            slot_missing = 'To proceed, I need' in content or 'Could you provide' in content
            if slot_missing and turn.get('has_slots', False):
                issues.append('slot missing prompt')

            results.append({
                'turn': i, 'passed': not issues,
                'type': ftype, 'source': fsource,
                'content_len': len(content), 'issues': issues,
            })
        except Exception as e:
            results.append({
                'turn': i, 'passed': False,
                'issues': [f'{type(e).__name__}: {e}'],
            })
    return results


@llm
class TestMultiTurnConversations:
    """32 two-turn conversations through the full agent pipeline."""

    @pytest.mark.parametrize('conv', CONVERSATIONS, ids=[f"conv_{c['id']:04d}" for c in CONVERSATIONS])
    def test_conversation(self, agent, conv):
        results = _run_conversation(agent, conv)
        failures = [r for r in results if not r['passed']]
        if failures:
            details = '; '.join(
                f"T{r['turn']}: {r['issues']}" for r in failures
            )
            pytest.fail(f"Conversation #{conv['id']} — {details}")
