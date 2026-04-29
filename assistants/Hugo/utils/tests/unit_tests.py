"""Unit tests — pure code logic, mocked LLM, no API keys needed.

Covers:
  - PromptEngineer: model resolution, provider dispatch
  - Ensemble voting: config invariants, _tally_votes, _detect_flow (mocked)
  - NLU react(): DAX routing, slot parsing, utterance fill
  - Template fill: frame.thoughts / data fallback
  - Services: PostService, ContentService, AnalysisService, PlatformService
  - Snapshot infrastructure
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path
from types import MappingProxyType
from unittest.mock import MagicMock, patch

import pytest

_HUGO_ROOT = Path(__file__).resolve().parents[2]
if str(_HUGO_ROOT) not in sys.path:
    sys.path.insert(0, str(_HUGO_ROOT))

from backend.modules.nlu import NLU, _ENSEMBLE_VOTERS
from backend.components.prompt_engineer import PromptEngineer
from backend.components.context_coordinator import Turn
from backend.components.flow_stack import flow_classes
from backend.utilities.services import (
    ToolService, PostService, ContentService, AnalysisService, PlatformService,
    split_sentences, join_sentences, _DB_DIR,
)
from schemas.ontology import FLOW_CATALOG


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def minimal_config():
    return MappingProxyType({
        'models': {
            'default': {
                'provider': 'anthropic',
                'model_id': 'claude-sonnet-4-5-20250929',
                'temperature': 0.0,
            },
            'overrides': {},
        },
        'resilience': {},
    })


@pytest.fixture
def engineer(minimal_config):
    return PromptEngineer(minimal_config)


@pytest.fixture
def nlu(minimal_config):
    """Live World, ContextCoordinator, FlowStack, AmbiguityHandler — only the LLM call
    sites in PromptEngineer get mocked per-test. This keeps every conditional branch in
    NLU reachable. The fixture seeds a User action turn so Phase 1c (last_user_turn.turn_type
    == 'action') is exercisable by default; tests that need an utterance turn override it."""
    from backend.components.world import World
    from backend.components.ambiguity_handler import AmbiguityHandler
    engineer = PromptEngineer(minimal_config)
    ambiguity = AmbiguityHandler(minimal_config, engineer=engineer)
    world = World(minimal_config)
    world.context.add_turn('User', '', turn_type='action')
    return NLU(minimal_config, ambiguity, engineer, world)


def _make_context(turn_type='action'):
    ctx = MagicMock()
    ctx.last_user_turn = Turn('User', '', turn_type=turn_type, turn_id=0)
    return ctx


# ═══════════════════════════════════════════════════════════════════
# PromptEngineer: model resolution and provider dispatch
# ═══════════════════════════════════════════════════════════════════

class TestPromptEngineer:
    def test_unknown_raises(self, engineer):
        with pytest.raises(ValueError):
            engineer._resolve_model('unknown')

    def test_claude_dispatch(self, engineer):
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.type = 'text'
        mock_block.text = '{"flow_name": "chat"}'
        mock_response.content = [mock_block]

        with patch.object(engineer, '_call_claude', return_value=mock_response):
            result = engineer('hi', task='detect_flow', model='haiku')
        assert result == '{"flow_name": "chat"}'

    def test_gemini_dispatch(self, engineer):
        with patch.object(engineer, '_call_gemini', return_value='{"flow_name": "chat"}'):
            result = engineer('hi', task='detect_flow', model='flash')
        assert result == '{"flow_name": "chat"}'


# ═══════════════════════════════════════════════════════════════════
# Ensemble voting: _tally_votes
# ═══════════════════════════════════════════════════════════════════

class TestEnsembleVoting:
    # -- Config invariants --------------------------------------------------

    def test_weights_sum_to_one(self):
        total = sum(v['weight'] for v in _ENSEMBLE_VOTERS)
        assert total == pytest.approx(1.0)

    def test_unique_labels(self):
        labels = [v['label'] for v in _ENSEMBLE_VOTERS]
        assert len(labels) == len(set(labels))

    # -- _tally_votes -------------------------------------------------------

    def test_two_agree_one_dissents(self, nlu):
        votes = [
            {'flow_name': 'chat', '_model': 'haiku', '_weight': 0.20},
            {'flow_name': 'brainstorm', '_model': 'sonnet', '_weight': 0.45},
            {'flow_name': 'brainstorm', '_model': 'gemini_flash', '_weight': 0.35},
        ]
        result = nlu._tally_votes(votes)
        assert result['flow_name'] == 'brainstorm'
        assert result['confidence'] == pytest.approx(0.80)

    def test_graceful_two_voter_degradation(self, nlu):
        votes = [
            {'flow_name': 'chat', '_model': 'haiku', '_weight': 0.20},
            {'flow_name': 'chat', '_model': 'sonnet', '_weight': 0.45},
        ]
        result = nlu._tally_votes(votes)
        assert result['flow_name'] == 'chat'
        assert result['confidence'] == pytest.approx(1.0)

    # -- _detect_flow (mocked LLM) -----------------------------------------

    def test_one_voter_fails(self, nlu):
        def mock_call(prompt, task='skill', model='sonnet', max_tokens=1024, schema=None):
            if model == 'flash':
                raise RuntimeError('Gemini down')
            return {'flow_name': 'chat', 'confidence': 0.8}

        real_engineer = nlu.engineer
        stub = MagicMock(side_effect=mock_call)
        stub.apply_guardrails = real_engineer.apply_guardrails
        nlu.engineer = stub
        result = nlu._detect_flow('hello', intent='Converse')

        assert result['flow_name'] == 'chat'
        assert result['confidence'] == pytest.approx(1.0)

    def test_all_voters_fail(self, nlu):
        def mock_call(prompt, task='skill', model='sonnet', max_tokens=1024, schema=None):
            raise RuntimeError('All down')

        real_engineer = nlu.engineer
        stub = MagicMock(side_effect=mock_call)
        stub.apply_guardrails = real_engineer.apply_guardrails
        nlu.engineer = stub
        result = nlu._detect_flow('hello', intent='Converse')

        assert result['flow_name'] == 'chat'
        assert result['confidence'] == 0.3

    def test_disagreement_weighted(self, nlu):
        def mock_call(prompt, task='skill', model='sonnet', max_tokens=1024, schema=None):
            if model == 'haiku':
                return {'flow_name': 'chat'}
            return {'flow_name': 'brainstorm'}

        real_engineer = nlu.engineer
        stub = MagicMock(side_effect=mock_call)
        stub.apply_guardrails = real_engineer.apply_guardrails
        nlu.engineer = stub
        result = nlu._detect_flow('give me ideas', intent='Draft')

        assert result['flow_name'] == 'brainstorm'
        assert result['confidence'] == pytest.approx(0.80)


# ═══════════════════════════════════════════════════════════════════
# NLU react()
# ═══════════════════════════════════════════════════════════════════

class TestReact:
    def test_action_turn_routes_flow(self, nlu):
        state = nlu.react('{05A}', {'type': 'draft'})
        assert state.flow_name(string=True) == 'create'
        assert state.confidence == 0.99

    def test_action_turn_different_dax(self, nlu):
        state = nlu.react('{19A}', {'post': 'post_abc123'})
        assert state.flow_name(string=True) == 'summarize'
        assert state.confidence == 0.99

    def test_utterance_calls_fill_slots(self, nlu):
        with patch.object(nlu, '_fill_slots') as mock_fill:
            state = nlu.react('{05A}', {'topic': 'SEO'})
        mock_fill.assert_called_once()
        assert state.flow_name(string=True) == 'create'

    def test_snippet_payload_fills_entity_slot(self, nlu):
        # Phase 1a: snippet + post + section land in SourceSlot entity dict.
        nlu.react('{02B}', {'snippet': 'matrix mult', 'post': 'post_abc', 'section': 'sec_xyz'})
        flow = nlu.flow_stack.get_flow()
        assert flow.name() == 'refine'
        entity = flow.slots['source'].values[0]
        assert entity['snip'] == 'matrix mult'
        assert entity['post'] == 'post_abc'
        assert entity['sec'] == 'sec_xyz'

    def test_snippet_payload_fills_exact_slot(self, nlu):
        # Phase 1b: snippet lands in find.query via SNIPPET_EXACT_SLOTS registry.
        nlu.react('{001}', {'snippet': 'matrix mult'})
        flow = nlu.flow_stack.get_flow()
        assert flow.name() == 'find'
        assert flow.slots['query'].value == 'matrix mult'

    def test_all_action_dax_codes_resolve(self):
        from utils.helper import dax2flow
        for flow_name, cat in FLOW_CATALOG.items():
            dax = cat['dax']
            resolved = dax2flow(dax)
            assert resolved == flow_name, \
                f'dax2flow({dax!r}) returned {resolved!r}, expected {flow_name!r}'

    def test_context_only_payload_skips_per_flow_dispatch(self, nlu):
        """FE attaches active post/section as context to every action. _fill_slots must
        skip unpack_user_actions when the payload is purely entity-context or slice keys —
        per-flow dispatch is for real click data only."""
        with patch.object(nlu, 'unpack_user_actions') as mock_dispatch:
            nlu.react('{05A}', {'post': '17be00f6'})  # create has no source/target slot
        mock_dispatch.assert_not_called()

    def test_refine_steps_unpacks_dict_kwargs(self):
        """Regression: under the old generic dispatch, slot.add_one(item) bound the whole
        {name, description} dict to the positional `name` arg, producing nested
        {name: {name: '...'}}. The per-flow refactor uses slot.add_one(**item)."""
        flow = flow_classes['refine']()
        flow.fill_slot_values({
            'source': [{'post': 'abc12345'}],
            'steps': [{'name': "Remove X", 'description': 'why'}],
        })
        assert flow.slots['steps'].steps[0] == {'name': "Remove X", 'description': 'why', 'checked': False}


# ═══════════════════════════════════════════════════════════════════
# Agent.take_turn — full keep_going loop integration
# ═══════════════════════════════════════════════════════════════════

class TestAgent:
    """End-to-end coverage of the agent.take_turn round trip with mocked LLM calls and
    stubbed PostService. Exercises the keep_going loop's interaction with res.start /
    res.respond — the agent-level orchestration that policy_evals and unit-NLU tests skip."""

    def test_create_action_completes_round_one_without_crash(self, mock_agent, monkeypatch):
        """A flow that completes in round 1 with keep_going=False must leave its just-completed
        flow on the stack so res.respond's `completed_flows[-1]` can render it. Regression for
        the bug where agent.py popped flows mid-loop and crashed at `flow.intent` on None."""
        from backend.utilities.services import PostService
        monkeypatch.setattr(PostService, 'create_post',
            lambda self, **kw: {'_success': True, 'post_id': 'cafef00d',
                                'title': kw.get('title', ''), 'status': kw.get('type', 'draft')})

        # Stub fill_slots to populate CreateFlow's required slots without invoking the LLM.
        from backend.modules.nlu import NLU
        def stub_fill(self, flow, payload=None):
            flow.fill_slot_values({'title': 'Cute Cheetahs', 'type': 'draft', 'topic': 'cheetahs'})
        monkeypatch.setattr(NLU, '_fill_slots', stub_fill)

        result = mock_agent.take_turn(
            'Make a post about cheetahs', dax='{05A}', payload={'post': '17be00f6'})
        assert result['frame'] is not None, 'agent.py must not return the fallback payload'
        assert result['frame']['origin'] == 'create'
        block_types = [b['type'] for b in result['frame']['blocks']]
        assert block_types == ['card']

@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """Set up a temporary database directory for service tests."""
    db = tmp_path / 'database'
    content = db / 'content'
    (content / 'drafts').mkdir(parents=True)
    (content / 'notes').mkdir(parents=True)
    (content / 'posts').mkdir(parents=True)
    snapshots = db / '.snapshots'
    snapshots.mkdir(parents=True)
    guides = db / 'guides'
    guides.mkdir(parents=True)
    # Write a minimal metadata.json
    meta = content / 'metadata.json'
    meta.write_text(json.dumps({'entries': []}))
    # Monkeypatch the module-level _DB_DIR; ToolService.__init__ derives the rest
    import backend.utilities.services as svc
    monkeypatch.setattr(svc, '_DB_DIR', db)
    return db


def _seed_test_post(tmp_db, title='Test Post', status='draft', body=None):
    """Create a post with known sections for consistent testing."""
    import backend.utilities.services as svc
    svc_inst = PostService()
    if body is None:
        result = svc_inst.create_post(title=title, type=status)
    else:
        result = svc_inst.create_post(title=title, type=status, topic=body if status == 'note' else None)
    post_id = result['post_id']
    if body and status != 'note':
        # Write body content to the file
        content_dir = svc._DB_DIR / 'content'
        meta_file = content_dir / 'metadata.json'
        entries = json.loads(meta_file.read_text())['entries']
        for entry in entries:
            if entry['post_id'] == post_id:
                filepath = content_dir / entry['filename']
                filepath.write_text(f'---\ntitle: {title}\n---\n\n{body}', encoding='utf-8')
                break
    return post_id, result


# ═══════════════════════════════════════════════════════════════════
# Template fill functions
# ═══════════════════════════════════════════════════════════════════

class TestTemplateFill:
    """Verify fill_*_template functions and RES.display() block assembly."""

    def _make_frame(self, minimal_config, block_type='default',
                    thoughts='', content='', origin=None):
        from backend.components.display_frame import DisplayFrame
        frame = DisplayFrame(minimal_config)
        frame.origin = origin or ''
        frame.thoughts = thoughts
        if block_type != 'default' or content:
            data = {'content': content} if content else {}
            frame.add_block({'type': block_type, 'data': data})
        return frame

    def test_thoughts_used_when_set(self, minimal_config):
        from backend.modules.templates.draft import fill_draft_template
        flow = flow_classes['brainstorm']()
        frame = self._make_frame(minimal_config, thoughts='My outline ideas')
        result = fill_draft_template('{message}', flow, frame)
        assert 'My outline ideas' in result

    def test_research_template_uses_thoughts(self, minimal_config):
        from backend.modules.templates.research import fill_research_template
        flow = flow_classes['browse']()
        frame = self._make_frame(minimal_config, thoughts='Found 5 items')
        result = fill_research_template('', flow, frame)
        assert 'Found 5 items' in result

    def test_create_uses_slot_title(self, minimal_config):
        from backend.modules.templates.draft import fill_draft_template
        flow = flow_classes['create']()
        flow.fill_slot_values({'title': 'My New Post'})
        frame = self._make_frame(minimal_config)
        result = fill_draft_template('', flow, frame)
        assert 'My New Post' in result

    def test_build_payload_frame_sets_panel(self, minimal_config):
        from backend.agent import Agent
        frame = self._make_frame(minimal_config, block_type='card',
                                 content='Hello', origin='compose')
        payload = Agent._build_payload(None, 'Some text', frame)
        assert payload['panel'] == 'bottom'
        assert payload['frame']['blocks'][0]['type'] == 'card'
        assert payload['frame']['blocks'][0]['data']['content'] == 'Hello'

    def test_audit_message_groups_findings_by_severity(self, minimal_config):
        from backend.modules.templates.revise import _format_audit_message
        from backend.components.display_frame import DisplayFrame
        findings = [
            {'sec_id': None, 'issue': 'sentence structure', 'severity': 'high',
             'note': 'Average sentence length 23.1 vs reference 13.5.'},
            {'sec_id': 'mechanics', 'issue': 'composition', 'severity': 'medium',
             'note': 'Negative parallelism overuse.'},
            {'sec_id': 'kitty-hawk', 'issue': 'word choice', 'severity': 'low',
             'note': 'False range construction.'},
        ]
        frame = DisplayFrame(origin='audit',
            metadata={'findings': findings, 'summary': 'Three findings.'})
        result = _format_audit_message(frame)
        assert 'Found 3 finding(s)' in result
        assert '1 high, 1 medium, 1 low' in result
        assert 'Three findings.' in result
        assert '[high] sentence structure (whole post)' in result
        # High-severity finding's note must be present (sorts first).
        assert 'Average sentence length 23.1' in result
        # `sec_id=None` renders as `whole post`, not literal None.
        assert 'None' not in result.split('Three findings.')[1]

    def test_audit_message_empty_findings_uses_summary(self, minimal_config):
        from backend.modules.templates.revise import _format_audit_message
        from backend.components.display_frame import DisplayFrame
        frame = DisplayFrame(origin='audit',
            metadata={'findings': [], 'summary': 'Reads on-voice.'})
        assert _format_audit_message(frame) == 'Reads on-voice.'

    def test_audit_message_empty_no_summary_falls_back(self, minimal_config):
        from backend.modules.templates.revise import _format_audit_message
        from backend.components.display_frame import DisplayFrame
        frame = DisplayFrame(origin='audit', metadata={'findings': [], 'summary': ''})
        assert 'No findings' in _format_audit_message(frame)

    def test_audit_message_dispatch_announces_groups(self, minimal_config):
        from backend.modules.templates.revise import _format_audit_message
        from backend.components.display_frame import DisplayFrame
        frame = DisplayFrame(origin='audit',
            metadata={'group_count': 2, 'flow_names': ['rework', 'polish']})
        result = _format_audit_message(frame)
        assert 'Working on it' in result
        assert '2 fix' in result
        assert 'rework' in result
        assert 'polish' in result

    def test_audit_message_completed_rolls_up_reports(self, minimal_config):
        from backend.modules.templates.revise import _format_audit_message
        from backend.components.display_frame import DisplayFrame
        frame = DisplayFrame(origin='audit',
            metadata={'reports': {'rework': 'rewrote intro', 'polish': 'tightened phrasing'}})
        result = _format_audit_message(frame)
        assert 'Audit complete' in result
        assert 'rework: rewrote intro' in result
        assert 'polish: tightened phrasing' in result


# ═══════════════════════════════════════════════════════════════════
# PostService
# ═══════════════════════════════════════════════════════════════════

class TestPostService:
    # -- Return format invariants -------------------------------------------

    def test_error_has_three_keys(self, tmp_db):
        # Section-not-found still returns an error dict (post-not-found
        # raises PostNotFoundError instead). This guards the dict shape
        # for the cases that haven't been converted to exceptions.
        post_id, _ = _seed_test_post(tmp_db, title='Shape Test')
        svc = PostService()
        result = svc.read_section(post_id, 'nonexistent-section')
        assert result['_success'] is False
        assert '_error' in result
        assert '_message' in result

    def test_success_data_at_top_level(self, tmp_db):
        svc = PostService()
        result = svc.find_posts()
        assert 'items' in result
        assert 'count' in result
        assert result['_success'] is True

    # -- CRUD ---------------------------------------------------------------

    def test_find_posts_returns_items(self, tmp_db):
        post_id, _ = _seed_test_post(tmp_db)
        svc = PostService()
        result = svc.find_posts()
        assert result['_success'] is True
        assert result['count'] >= 1

    def test_find_posts_with_tags_filter(self, tmp_db):
        post_id, _ = _seed_test_post(tmp_db, title='Tagged Post')
        svc = PostService()
        svc.update_post(post_id, {'tags': ['python', 'tutorial']})
        result = svc.find_posts(tags=['python'])
        assert result['_success'] is True
        assert result['count'] >= 1

    def test_find_posts_status_filter(self, tmp_db):
        _seed_test_post(tmp_db, title='Draft One')
        _seed_test_post(tmp_db, title='Note One', status='note', body='a quick note')
        svc = PostService()
        result = svc.find_posts(status='draft')
        assert result['_success'] is True
        for item in result['items']:
            assert item['status'] == 'draft'

    def test_search_notes_only_notes(self, tmp_db):
        _seed_test_post(tmp_db, title='Draft Post')
        _seed_test_post(tmp_db, title='', status='note', body='my test note content')
        svc = PostService()
        result = svc.search_notes()
        assert result['_success'] is True
        # All returned items should have note content
        assert result['count'] >= 1

    def test_read_metadata_success(self, tmp_db):
        post_id, _ = _seed_test_post(tmp_db, title='Meta Test')
        svc = PostService()
        result = svc.read_metadata(post_id)
        assert result['_success'] is True
        assert result['title'] == 'Meta Test'
        assert 'section_ids' in result

    def test_read_metadata_not_found(self, tmp_db):
        from backend.utilities.services import PostNotFoundError
        svc = PostService()
        with pytest.raises(PostNotFoundError):
            svc.read_metadata('nonexistent')

    def test_read_metadata_with_preview(self, tmp_db):
        body = '## Intro\n\nSome content here.\n\n## Body\n\nMore content.\n'
        post_id, _ = _seed_test_post(tmp_db, title='Preview Test', body=body)
        svc = PostService()
        result = svc.read_metadata(post_id, include_preview=True)
        assert result['_success'] is True
        assert 'preview' in result

    def test_read_section_success(self, tmp_db):
        body = '## Intro\n\nHello world.\n\n## Body\n\nMore text.\n'
        post_id, _ = _seed_test_post(tmp_db, title='Section Test', body=body)
        svc = PostService()
        result = svc.read_section(post_id, 'intro')
        assert result['_success'] is True
        assert 'sentence_count' in result
        assert 'content' in result

    def test_read_section_with_sentence_ids(self, tmp_db):
        body = '## Intro\n\nFirst sentence. Second sentence. Third sentence.\n'
        post_id, _ = _seed_test_post(tmp_db, title='Sentence IDs', body=body)
        svc = PostService()
        result = svc.read_section(post_id, 'intro', include_sentence_ids=True)
        assert result['_success'] is True
        assert '[0]' in result['content']
        assert '[1]' in result['content']

    def test_read_section_single_snippet(self, tmp_db):
        body = '## Intro\n\nFirst sentence. Second sentence. Third sentence.\n'
        post_id, _ = _seed_test_post(tmp_db, title='Snip Single', body=body)
        svc = PostService()
        result = svc.read_section(post_id, 'intro', snip_id=1)
        assert result['_success'] is True
        assert result['content'].startswith('Second')

    def test_read_section_not_found(self, tmp_db):
        post_id, _ = _seed_test_post(tmp_db)
        svc = PostService()
        result = svc.read_section(post_id, 'nonexistent-section')
        assert result['_success'] is False
        assert result['_error'] == 'not_found'

    def test_read_section_preserves_bullet_newlines(self, tmp_db):
        # Regression: read_section used to ' '.join sentences, producing
        # '- a - b - c' for bulleted sections. The display card (frontend) renders
        # that as a single line. Must keep bullets on separate lines.
        body = '## Intro\n\n- alpha\n- beta\n- gamma\n'
        post_id, _ = _seed_test_post(tmp_db, title='Bullet Display', body=body)
        svc = PostService()
        result = svc.read_section(post_id, 'intro')
        assert result['_success'] is True
        assert result['content'] == '- alpha\n- beta\n- gamma'

    def test_read_section_preserves_h3_subsections_with_bullets(self, tmp_db):
        # Regression: H3 subsections + bullets in one section collapsed to
        # '### Heading - bullet - bullet ### Other Heading - ...'. The display
        # card rendered it as one very long H3. Display path hands back raw
        # content verbatim — blank lines between H3 blocks preserved.
        body = (
            '## Dealing with Ambiguity\n\n'
            '### Catching Ambiguity Early\n'
            '- Introduce detection layer\n'
            '- Outline pipeline\n\n'
            '### Designing for Uncertainty\n'
            '- Reframe the goal\n'
            '- Introduce patterns\n'
        )
        post_id, _ = _seed_test_post(tmp_db, title='H3 Display', body=body)
        svc = PostService()
        result = svc.read_section(post_id, 'dealing-with-ambiguity')
        assert result['_success'] is True
        expected = (
            '### Catching Ambiguity Early\n'
            '- Introduce detection layer\n'
            '- Outline pipeline\n\n'
            '### Designing for Uncertainty\n'
            '- Reframe the goal\n'
            '- Introduce patterns'
        )
        assert result['content'] == expected

    def test_create_post_draft(self, tmp_db):
        svc = PostService()
        result = svc.create_post(title='My New Draft', type='draft')
        assert result['_success'] is True
        assert result['post_id']
        assert result['status'] == 'draft'

    def test_create_post_note(self, tmp_db):
        svc = PostService()
        result = svc.create_post(title='', type='note', topic='quick thought')
        assert result['_success'] is True
        assert result['status'] == 'note'

    def test_create_post_duplicate(self, tmp_db):
        svc = PostService()
        svc.create_post(title='Unique Title', type='draft')
        result = svc.create_post(title='Unique Title', type='draft')
        assert result['_success'] is False
        assert result['_error'] == 'duplicate'

    def test_create_post_placeholder_sections(self, tmp_db):
        svc = PostService()
        result = svc.create_post(title='Sections Test', type='draft')
        assert result['_success'] is True
        assert len(result['section_ids']) == 3

    def test_update_post_metadata_only(self, tmp_db):
        post_id, _ = _seed_test_post(tmp_db, title='Update Me')
        svc = PostService()
        result = svc.update_post(post_id, {'title': 'Updated Title', 'tags': ['ai']})
        assert result['_success'] is True
        assert result['title'] == 'Updated Title'
        assert 'ai' in result['tags']

    def test_update_post_rejects_content(self, tmp_db):
        post_id, _ = _seed_test_post(tmp_db)
        svc = PostService()
        result = svc.update_post(post_id, {'content': 'should fail'})
        assert result['_success'] is False
        assert result['_error'] == 'validation'

    def test_update_post_status_moves_file(self, tmp_db):
        post_id, _ = _seed_test_post(tmp_db, title='Move Me')
        svc = PostService()

        result = svc.update_post(post_id, {'status': 'published'})
        assert result['_success'] is True
        assert result['status'] == 'published'

    def test_delete_post_removes_file(self, tmp_db):
        from backend.utilities.services import PostNotFoundError
        post_id, _ = _seed_test_post(tmp_db, title='Delete Me')
        svc = PostService()
        result = svc.delete_post(post_id)
        assert result['_success'] is True
        # Verify it's gone — read_metadata now raises on missing posts.
        with pytest.raises(PostNotFoundError):
            svc.read_metadata(post_id)

    def test_delete_post_cleans_snapshots(self, tmp_db):
        post_id, _ = _seed_test_post(tmp_db, title='Snap Delete')

        svc = PostService()
        snap_dir = svc._snap_root / post_id / 'intro'
        snap_dir.mkdir(parents=True)
        (snap_dir / 'snapshot-1.txt').write_text('old content')
        svc.delete_post(post_id)
        assert not (svc._snap_root / post_id).exists()

    def test_summarize_text_raw(self, tmp_db):
        svc = PostService()
        result = svc.summarize_text(raw_text='This is some raw text to summarize.')
        assert result['_success'] is True
        assert result['text_to_summarize'] == 'This is some raw text to summarize.'

    def test_summarize_text_empty_error(self, tmp_db):
        svc = PostService()
        result = svc.summarize_text()
        assert result['_success'] is False
        assert result['_error'] == 'validation'

    def test_rollback_post_no_snapshots(self, tmp_db):
        post_id, _ = _seed_test_post(tmp_db, title='No Snaps')
        svc = PostService()
        result = svc.rollback_post(post_id)
        assert result['_success'] is False
        assert result['_error'] == 'not_found'


# ═══════════════════════════════════════════════════════════════════
# ContentService
# ═══════════════════════════════════════════════════════════════════

class TestContentService:
    def test_generate_outline_valid(self, tmp_db):
        post_id, _ = _seed_test_post(tmp_db, title='Outline Post')
        svc = ContentService()
        content = '## Section A\n\n- point 1\n- point 2\n\n## Section B\n\n- point 3\n'
        result = svc.generate_outline(post_id, content)
        assert result['_success'] is True

    def test_generate_outline_rejects_bullet_without_section(self, tmp_db):
        from backend.utilities.services import OutlineValidationError
        post_id, _ = _seed_test_post(tmp_db)
        svc = ContentService()
        content = '- orphan bullet\n- another orphan\n'
        with pytest.raises(OutlineValidationError):
            svc.generate_outline(post_id, content)

    def test_generate_outline_rejects_duplicates(self, tmp_db):
        from backend.utilities.services import OutlineValidationError
        post_id, _ = _seed_test_post(tmp_db)
        svc = ContentService()
        content = '## Intro\n\ntext\n\n## Intro\n\nmore text\n'
        with pytest.raises(OutlineValidationError, match='Duplicate'):
            svc.generate_outline(post_id, content)

    def test_revise_content_replaces_existing_outline_section(self, tmp_db):
        body = '## Process\n\n- gather data\n- train model\n'
        post_id, _ = _seed_test_post(tmp_db, title='Section Replace', body=body)
        svc = ContentService()
        revised = '- gather data\n- train model\n- evaluate model'
        result = svc.revise_content(post_id, 'process', revised)
        assert result['_success'] is True
        entry = svc._find_entry(svc._load_metadata(), post_id)
        saved = svc._read_content(entry['filename'])
        assert '- evaluate model' in saved

    def test_insert_section_appends_new_section_after_anchor(self, tmp_db):
        body = '## Motivation\n\n- pain point\n'
        post_id, _ = _seed_test_post(tmp_db, title='Section Append', body=body)
        svc = ContentService()
        result = svc.insert_section(post_id, 'motivation', 'Takeaways',
            content='- key insight')
        assert result['_success'] is True
        assert result['sec_id'] == 'takeaways'
        entry = svc._find_entry(svc._load_metadata(), post_id)
        saved = svc._read_content(entry['filename'])
        assert '## Takeaways' in saved
        assert '- key insight' in saved

    def test_insert_section_preserves_blank_separator(self, tmp_db):
        body = '## Motivation\n- pain point'
        post_id, _ = _seed_test_post(tmp_db, title='Append Spacing', body=body)
        svc = ContentService()
        result = svc.insert_section(post_id, 'motivation', 'Takeaways',
            content='- key insight')
        assert result['_success'] is True
        entry = svc._find_entry(svc._load_metadata(), post_id)
        saved = svc._read_content(entry['filename'])
        assert '- pain point\n\n## Takeaways' in saved

    def test_rebuild_content_inserts_blank_between_sections(self):
        from backend.utilities.services import ToolService
        sections = [
            {'sec_id': 'a', 'title': 'A', 'lines': ['- one', '- two']},
            {'sec_id': 'b', 'title': 'B', 'lines': ['- three']},
        ]
        out = ToolService._rebuild_content(sections)
        assert out == '## A\n- one\n- two\n\n## B\n- three'

    def test_rebuild_content_does_not_double_blank(self):
        from backend.utilities.services import ToolService
        sections = [
            {'sec_id': 'a', 'title': 'A', 'lines': ['- one', '']},
            {'sec_id': 'b', 'title': 'B', 'lines': ['- two']},
        ]
        out = ToolService._rebuild_content(sections)
        assert out == '## A\n- one\n\n## B\n- two'

    def test_split_sentences_bullets_stay_separate(self):
        # Regression: bullets used to collapse into '- a - b - c' because
        # split_sentences flattened newlines and join_sentences ' '-joined.
        snips = split_sentences('- alpha\n- beta\n- gamma')
        assert snips == ['- alpha', '- beta', '- gamma']

    def test_split_sentences_prose_still_flattens(self):
        snips = split_sentences('Sentence one.\nSentence two. Sentence three.')
        assert snips == ['Sentence one.', 'Sentence two.', 'Sentence three.']

    def test_split_sentences_mixed_paragraphs(self):
        text = 'Opening sentence. Another sentence.\n\n- bullet one\n- bullet two\n\nClosing.'
        snips = split_sentences(text)
        assert snips == ['Opening sentence.', 'Another sentence.',
                         '- bullet one', '- bullet two', 'Closing.']

    def test_split_sentences_h3_with_bullets(self):
        # Regression: H3 heading + bullets in one paragraph used to flatten to
        # '### Heading - bullet1 - bullet2' because the paragraph wasn't all-bullet.
        text = '### Catching Ambiguity Early\n- Introduce detection\n- Outline pipeline'
        snips = split_sentences(text)
        assert snips == ['### Catching Ambiguity Early',
                         '- Introduce detection', '- Outline pipeline']

    def test_split_join_h3_and_bullets_roundtrip(self):
        original = '### Heading A\n- a1\n- a2\n\n### Heading B\n- b1\n- b2'
        assert join_sentences(split_sentences(original)) == original

    def test_split_sentences_sub_bullets_stay_separate(self):
        # Per OUTLINE_LEVELS (flows.py): Level 3 is `- bullet`, Level 4 is
        # `   * sub-bullet`. Both should be treated as structural.
        text = '- parent one\n  * sub a\n  * sub b\n- parent two'
        snips = split_sentences(text)
        assert snips == ['- parent one', '  * sub a', '  * sub b', '- parent two']

    def test_join_sentences_sub_bullets_preserve_indent(self):
        snips = ['- parent', '  * sub a', '  * sub b']
        assert join_sentences(snips) == '- parent\n  * sub a\n  * sub b'

    def test_split_join_nested_bullets_roundtrip(self):
        original = '### Heading\n- parent a\n  * sub a1\n  * sub a2\n- parent b\n  * sub b1'
        assert join_sentences(split_sentences(original)) == original

    def test_join_sentences_bullets_get_newlines(self):
        out = join_sentences(['- alpha', '- beta', '- gamma'])
        assert out == '- alpha\n- beta\n- gamma'

    def test_join_sentences_prose_space_joined(self):
        out = join_sentences(['Sentence one.', 'Sentence two.'])
        assert out == 'Sentence one. Sentence two.'

    def test_split_join_roundtrip_preserves_bullets(self):
        original = '- alpha\n- beta\n- gamma'
        assert join_sentences(split_sentences(original)) == original

    def test_remove_content_by_snip_preserves_other_bullets(self, tmp_db):
        # The scenario that surfaced the bug: remove one bullet, expect the
        # remaining bullets to stay on their own lines.
        body = '## Intro\n\n- alpha\n- beta\n- gamma\n'
        post_id, _ = _seed_test_post(tmp_db, title='Bullet Remove', body=body)
        svc = ContentService()
        result = svc.remove_content(post_id, 'intro', snip_id=1)
        assert result['_success'] is True
        entry = svc._find_entry(svc._load_metadata(), post_id)
        saved = svc._read_content(entry['filename'])
        assert '- alpha\n- gamma' in saved
        assert '- alpha - gamma' not in saved

    def test_revise_content_insert_bullet_preserves_neighbors(self, tmp_db):
        body = '## Intro\n\n- alpha\n- gamma\n'
        post_id, _ = _seed_test_post(tmp_db, title='Bullet Revise', body=body)
        svc = ContentService()
        # Integer snip_id inserts at index; tuple replaces a range.
        result = svc.revise_content(post_id, 'intro', '- beta', snip_id=1)
        assert result['_success'] is True
        entry = svc._find_entry(svc._load_metadata(), post_id)
        saved = svc._read_content(entry['filename'])
        assert '- alpha\n- beta\n- gamma' in saved

    def test_update_post_renames_section_via_sections_list(self, tmp_db):
        body = '## Ideas\n\n- early thoughts\n\n## Process\n\n- alpha\n'
        post_id, _ = _seed_test_post(tmp_db, title='Section Rename', body=body)
        svc = PostService()
        result = svc.update_post(post_id,
            updates={'sections': ['Breakthrough Ideas', 'Process']})
        assert result['_success'] is True
        entry = svc._find_entry(svc._load_metadata(), post_id)
        saved = svc._read_content(entry['filename'])
        assert '## Breakthrough Ideas' in saved
        assert '- early thoughts' in saved
        assert '## Process' in saved

    def test_update_post_renames_multiple_sections_at_once(self, tmp_db):
        body = '## Alpha\n- a1\n\n## Beta\n- b1\n\n## Gamma\n- g1\n'
        post_id, _ = _seed_test_post(tmp_db, title='Multi Rename', body=body)
        svc = PostService()
        result = svc.update_post(post_id,
            updates={'sections': ['Alpha One', 'Beta Two', 'Gamma Three']})
        assert result['_success'] is True
        entry = svc._find_entry(svc._load_metadata(), post_id)
        saved = svc._read_content(entry['filename'])
        assert '## Alpha One' in saved
        assert '## Beta Two' in saved
        assert '## Gamma Three' in saved

    def test_update_post_sections_length_mismatch_returns_validation(self, tmp_db):
        body = '## Ideas\n\n- early thoughts\n'
        post_id, _ = _seed_test_post(tmp_db, title='Mismatch', body=body)
        svc = PostService()
        result = svc.update_post(post_id,
            updates={'sections': ['Ideas', 'Extra']})
        assert result['_success'] is False
        assert result['_error'] == 'validation'

    def test_save_section_content_validates_duplicate_h2(self, tmp_db):
        # _validate_outline now runs on every section write, regardless of
        # which tool initiated it. Renaming a section to a name that already
        # exists should raise OutlineValidationError; PEX dispatch maps that
        # to {'_error': 'validation'} for the LLM.
        from backend.utilities.services import OutlineValidationError
        body = '## Ideas\n- early\n\n## Process\n- alpha\n'
        post_id, _ = _seed_test_post(tmp_db, title='Dup Guard', body=body)
        svc = PostService()
        with pytest.raises(OutlineValidationError, match='Duplicate H2'):
            svc.update_post(post_id, updates={'sections': ['Process', 'Process']})

    def test_convert_to_prose(self, tmp_db):
        body = '## Method\n\n- step one\n- step two\n- step three\n'
        post_id, _ = _seed_test_post(tmp_db, title='Prose Test', body=body)
        svc = ContentService()
        result = svc.convert_to_prose(post_id, sec_id='method')
        assert result['_success'] is True

    def test_insert_section_after(self, tmp_db):
        body = '## Alpha\n\nContent A.\n\n## Beta\n\nContent B.\n'
        post_id, _ = _seed_test_post(tmp_db, title='Insert Sec', body=body)
        svc = ContentService()
        result = svc.insert_section(post_id, 'alpha', 'Gamma', 'New content')
        assert result['_success'] is True

    def test_revise_content_insert_at_index(self, tmp_db):
        body = '## Intro\n\nFirst sentence. Second sentence. Third sentence.\n'
        post_id, _ = _seed_test_post(tmp_db, title='Insert Sentence', body=body)
        svc = ContentService()
        result = svc.revise_content(post_id, 'intro', 'Inserted sentence.', snip_id=1)
        assert result['_success'] is True

    def test_revise_content_takes_snapshot(self, tmp_db):
        body = '## Intro\n\nOriginal content.\n'
        post_id, _ = _seed_test_post(tmp_db, title='Revise Snap', body=body)
        svc = ContentService()
        result = svc.revise_content(post_id, 'intro', 'Revised content.')
        assert result['_success'] is True

        snapshot = ToolService()._read_snapshot(post_id, 'intro', 1)
        assert snapshot is not None

    def test_revise_content_replace_snippet_range(self, tmp_db):
        body = '## Intro\n\nSentence A. Sentence B. Sentence C.\n'
        post_id, _ = _seed_test_post(tmp_db, title='Sentence Range', body=body)
        svc = ContentService()
        result = svc.revise_content(post_id, 'intro', 'Replaced.', snip_id=(1, 3))
        assert result['_success'] is True

    def test_write_text_rejects_long_content(self, tmp_db):
        svc = ContentService()
        long_text = ' '.join(['word'] * 2049)
        result = svc.write_text('instructions', long_text)
        assert result['_success'] is False
        assert result['_error'] == 'validation'

    def test_write_text_loads_guide(self, tmp_db):
        svc = ContentService()
        guide_path = svc._guides_dir / 'writing_guide.md'
        guide_path.write_text('# Writing Guide\n\nBe concise.')
        result = svc.write_text('make it better', 'some seed content')
        assert result['_success'] is True
        assert 'Be concise' in result['writing_guide']

    def test_remove_content_snippet_range(self, tmp_db):
        body = '## Intro\n\nSentence A. Sentence B. Sentence C.\n'
        post_id, _ = _seed_test_post(tmp_db, title='Remove Range', body=body)
        svc = ContentService()
        result = svc.remove_content(post_id, 'intro', snip_id=(1, 2))
        assert result['_success'] is True

    def test_remove_content_section(self, tmp_db):
        body = '## Intro\n\nKeep.\n\n## ToRemove\n\nDelete me.\n'
        post_id, _ = _seed_test_post(tmp_db, title='Remove Sec', body=body)
        svc = ContentService()
        result = svc.remove_content(post_id, 'toremove')
        assert result['_success'] is True

    def test_cut_and_paste_moves_lines(self, tmp_db):
        body = '## Source\n\nSentence A. Sentence B.\n\n## Target\n\nSentence C.\n'
        post_id, _ = _seed_test_post(tmp_db, title='CnP Test', body=body)
        svc = ContentService()
        result = svc.cut_and_paste(post_id, 'source', 'target', source_snip_id=(0, 1))
        assert result['_success'] is True

    def test_cut_and_paste_self_error(self, tmp_db):
        body = '## Only\n\nContent.\n'
        post_id, _ = _seed_test_post(tmp_db, title='Self CnP', body=body)
        svc = ContentService()
        result = svc.cut_and_paste(post_id, 'only', 'only')
        assert result['_success'] is False
        assert result['_error'] == 'validation'

    def test_diff_section_against_snapshot(self, tmp_db):
        body = '## Intro\n\nOriginal text.\n'
        post_id, _ = _seed_test_post(tmp_db, title='Diff Snap', body=body)
        svc = ContentService()
        # Create a snapshot by revising
        svc.revise_content(post_id, 'intro', 'Updated text.')
        result = svc.diff_section(post_id, 'intro', version=1)
        assert result['_success'] is True
        assert 'diff' in result

    def test_diff_section_between_sections(self, tmp_db):
        body = '## Alpha\n\nSome text.\n\n## Beta\n\nDifferent text.\n'
        post_id, _ = _seed_test_post(tmp_db, title='Diff Secs', body=body)
        svc = ContentService()
        result = svc.diff_section(post_id, 'alpha', target_section='beta')
        assert result['_success'] is True
        assert 'additions' in result
        assert 'deletions' in result

    def test_web_search_no_key(self, tmp_db, monkeypatch):
        monkeypatch.delenv('TAVILY_API_KEY', raising=False)
        svc = ContentService()
        result = svc.web_search('test query')
        assert result['_success'] is False
        assert result['_error'] == 'auth_error'

    def test_insert_media_no_key(self, tmp_db, monkeypatch):
        monkeypatch.delenv('GOOGLE_API_KEY', raising=False)
        svc = ContentService()
        result = svc.insert_media('a cat')
        assert result['_success'] is False
        assert result['_error'] == 'auth_error'


# ═══════════════════════════════════════════════════════════════════
# AnalysisService
# ═══════════════════════════════════════════════════════════════════

class TestAnalysisService:
    def test_brainstorm_ideas_aggregates(self, tmp_db):
        _seed_test_post(tmp_db, title='ML Basics')
        _seed_test_post(tmp_db, title='', status='note', body='ideas about ML training')
        svc = AnalysisService()
        result = svc.brainstorm_ideas(topic='ML')
        assert result['_success'] is True
        assert result['count'] >= 1

    def test_inspect_post_metrics(self, tmp_db):
        body = '## Intro\n\nSome words here for testing metrics.\n\n## Body\n\nMore content.\n'
        post_id, _ = _seed_test_post(tmp_db, title='Inspect Test', body=body)
        svc = AnalysisService()
        result = svc.inspect_post(post_id)
        assert result['_success'] is True
        assert 'word_count' in result
        assert 'section_count' in result
        assert 'estimated_read_time' in result

    def test_inspect_post_empty_sections(self, tmp_db):
        body = '## Filled\n\nHas content.\n\n## Empty\n\n'
        post_id, _ = _seed_test_post(tmp_db, title='Empty Sec', body=body)
        svc = AnalysisService()
        result = svc.inspect_post(post_id)
        assert result['_success'] is True
        assert 'empty' in result['empty_sections']

    def test_check_readability_easy(self, tmp_db):
        svc = AnalysisService()
        text = 'The cat sat. The dog ran. It was fun. I like it.'
        result = svc.check_readability(text)
        assert result['_success'] is True
        assert result['score_label'] == 'easy'

    def test_check_readability_difficult(self, tmp_db):
        svc = AnalysisService()
        text = ('The epistemological ramifications of hermeneutic phenomenology '
                'vis-a-vis the ontological presuppositions of transcendental '
                'idealism necessitate a comprehensive reevaluation of the '
                'methodological frameworks employed in contemporary philosophical '
                'discourse and interdisciplinary academic investigations.')
        result = svc.check_readability(text)
        assert result['_success'] is True
        assert result['score_label'] in ('advanced', 'difficult')

    def test_check_links_inline(self, tmp_db):
        svc = AnalysisService()
        content = 'Check [this link](https://example.com) for more info.'
        result = svc.check_links(content)
        assert result['_success'] is True
        assert result['count'] >= 1
        assert any(l['type'] == 'inline' for l in result['links'])

    def test_check_links_images(self, tmp_db):
        svc = AnalysisService()
        content = '![alt text](image.png)\n\nSome text.'
        result = svc.check_links(content)
        assert result['_success'] is True
        assert result['image_count'] >= 1

    def test_compare_style_deltas(self, tmp_db):
        body1 = '## Intro\n\nShort post.\n'
        body2 = '## Intro\n\nA much longer post with more words and sentences to compare.\n'
        pid1, _ = _seed_test_post(tmp_db, title='Style A', body=body1)
        pid2, _ = _seed_test_post(tmp_db, title='Style B', body=body2)
        svc = AnalysisService()
        result = svc.compare_style(pid1, reference_ids=[pid2])
        assert result['_success'] is True
        assert 'deltas' in result

    def test_editor_review_loads_guide(self, tmp_db):
        svc = AnalysisService()
        guide_path = svc._guides_dir / 'editor_guide.md'
        guide_path.write_text('# Editor Guide\n\nCheck for clarity.')
        result = svc.editor_review('some content to review')
        assert result['_success'] is True
        assert 'Check for clarity' in result['guide']

    def test_analyze_seo_keyword_density(self, tmp_db):
        body = '## ML Guide\n\nMachine learning is great. Machine learning helps everyone.\n'
        post_id, _ = _seed_test_post(tmp_db, title='SEO Test', body=body)
        svc = AnalysisService()
        result = svc.analyze_seo(post_id, target_keyword='machine learning')
        assert result['_success'] is True
        assert result['keyword_density'] > 0

    def test_analyze_seo_suggestions(self, tmp_db):
        body = '## Overview\n\nGeneric content without keywords.\n'
        post_id, _ = _seed_test_post(tmp_db, title='A', body=body)
        svc = AnalysisService()
        result = svc.analyze_seo(post_id, target_keyword='blockchain')
        assert result['_success'] is True
        assert len(result['suggestions']) > 0


# ═══════════════════════════════════════════════════════════════════
# PlatformService
# ═══════════════════════════════════════════════════════════════════

class TestPlatformService:
    def test_list_channels(self, tmp_db):
        svc = PlatformService()
        result = svc.list_channels()
        assert result['_success'] is True
        assert len(result['channels']) == 4

    def test_channel_status_unknown_platform(self, tmp_db):
        svc = PlatformService()
        result = svc.channel_status('some_id', 'wordpress')
        assert result['_success'] is False
        assert result['_error'] == 'invalid_input'

    def test_release_post_unknown_platform(self, tmp_db):
        svc = PlatformService()
        result = svc.release_post('some_id', 'wordpress')
        assert result['_success'] is False
        assert result['_error'] == 'invalid_input'

    def test_cancel_release_delegates(self, tmp_db):
        post_id, _ = _seed_test_post(tmp_db, title='Cancel Test')
        svc = PlatformService()
        result = svc.cancel_release(post_id, 'substack')
        # Substack's unpublish returns platform_error (not supported)
        assert result['_success'] is False


# ═══════════════════════════════════════════════════════════════════
# Snapshot infrastructure
# ═══════════════════════════════════════════════════════════════════

class TestSnapshotInfra:
    def test_take_snapshot_creates_file(self, tmp_db):

        ToolService()._take_snapshot('test_post', 'intro', ['line 1', 'line 2'])
        snapshot = ToolService()._read_snapshot('test_post', 'intro', 1)
        assert snapshot is not None
        assert 'line 1' in snapshot

    def test_take_snapshot_rotates(self, tmp_db):

        for i in range(6):
            ToolService()._take_snapshot('test_post', 'intro', [f'version {i}'])
        # Version 1 should be most recent (version 5)
        snapshot1 = ToolService()._read_snapshot('test_post', 'intro', 1)
        assert 'version 5' in snapshot1
        # Version 4 should be version 2
        snapshot4 = ToolService()._read_snapshot('test_post', 'intro', 4)
        assert 'version 2' in snapshot4

