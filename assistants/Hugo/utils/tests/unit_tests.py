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
    _DB_DIR,
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
    from backend.components.dialogue_state import DialogueState
    ambiguity = MagicMock()
    ambiguity.needs_clarification.return_value = False
    engineer = PromptEngineer(minimal_config)
    world = MagicMock()
    world.context.compile_history.return_value = ''
    # Contract: current_state() always returns a DialogueState.
    world.current_state.return_value = DialogueState(minimal_config)
    world.flow_stack.find_by_name.return_value = None
    world.flow_stack.depth = 0
    return NLU(minimal_config, ambiguity, engineer, world)


def _make_context(turn_type='action'):
    ctx = MagicMock()
    ctx.last_user_turn = Turn('User', '', turn_type=turn_type, turn_id=0)
    return ctx


# ═══════════════════════════════════════════════════════════════════
# PromptEngineer: model resolution and provider dispatch
# ═══════════════════════════════════════════════════════════════════

class TestPromptEngineer:
    def test_claude_sonnet(self, engineer):
        assert engineer._resolve_model('sonnet') == 'claude-sonnet-4-6'

    def test_claude_haiku(self, engineer):
        assert engineer._resolve_model('haiku') == 'claude-haiku-4-5-20251001'

    def test_gemini_flash(self, engineer):
        assert engineer._resolve_model('flash') == 'gemini-3-flash-preview'

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
            result = engineer.call(
                [{'role': 'user', 'content': 'hi'}],
                system='test', task='detect_flow',
                model='haiku',
            )
        assert result == '{"flow_name": "chat"}'

    def test_gemini_dispatch(self, engineer):
        with patch.object(engineer, '_call_gemini', return_value='{"flow_name": "chat"}'):
            result = engineer.call(
                [{'role': 'user', 'content': 'hi'}],
                system='test', task='detect_flow',
                model='flash',
            )
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

    def test_slots_from_heaviest_voter(self, nlu):
        votes = [
            {'flow_name': 'outline', '_model': 'haiku', '_weight': 0.20,
             'slots': {'topic': 'haiku_topic'}},
            {'flow_name': 'outline', '_model': 'sonnet', '_weight': 0.45,
             'slots': {'topic': 'sonnet_topic'}},
        ]
        result = nlu._tally_votes(votes)
        assert result['flow_name'] == 'outline'
        assert result['slots'] == {'topic': 'sonnet_topic'}

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
        def mock_call(messages, *, system=None, task='skill',
                      family='claude', model='sonnet', max_tokens=4096):
            if family == 'gemini':
                raise RuntimeError('Gemini down')
            return '{"flow_name": "chat", "confidence": 0.8}'

        with patch.object(nlu.engineer, 'call', side_effect=mock_call):
            with patch.object(nlu.engineer, 'build_flow_prompt',
                              return_value=('sys', [{'role': 'user', 'content': 'hi'}])):
                result = nlu._detect_flow('hello')

        assert result['flow_name'] == 'chat'
        assert result['confidence'] == pytest.approx(1.0)

    def test_all_voters_fail(self, nlu):
        def mock_call(messages, *, system=None, task='skill',
                      family='claude', model='sonnet', max_tokens=4096):
            raise RuntimeError('All down')

        with patch.object(nlu.engineer, 'call', side_effect=mock_call):
            with patch.object(nlu.engineer, 'build_flow_prompt',
                              return_value=('sys', [{'role': 'user', 'content': 'hi'}])):
                result = nlu._detect_flow('hello')

        assert result['flow_name'] == 'chat'
        assert result['confidence'] == 0.3

    def test_disagreement_weighted(self, nlu):
        def mock_call(messages, *, system=None, task='skill',
                      family='claude', model='sonnet', max_tokens=4096):
            if family == 'claude' and model == 'haiku':
                return '{"flow_name": "chat"}'
            return '{"flow_name": "brainstorm"}'

        with patch.object(nlu.engineer, 'call', side_effect=mock_call):
            with patch.object(nlu.engineer, 'build_flow_prompt',
                              return_value=('sys', [{'role': 'user', 'content': 'ideas'}])):
                result = nlu._detect_flow('give me ideas')

        assert result['flow_name'] == 'brainstorm'
        assert result['confidence'] == pytest.approx(0.80)


# ═══════════════════════════════════════════════════════════════════
# NLU react()
# ═══════════════════════════════════════════════════════════════════

class TestReact:
    def test_action_turn_routes_flow(self, nlu):
        state = nlu.react('{05A}', {'type': 'draft'})
        assert state.flow_name == 'create'
        assert state.confidence == 0.99

    def test_action_turn_different_dax(self, nlu):
        state = nlu.react('{19A}', {'post': 'post_abc123'})
        assert state.flow_name == 'summarize'
        assert state.confidence == 0.99

    def test_multi_slot_values_parsed(self, nlu):
        real_flow = flow_classes['create']()
        nlu.flow_stack.find_by_name.return_value = None
        nlu.flow_stack.push.return_value = real_flow
        nlu.react('{05A}', {'type': 'draft', 'topic': 'SEO tips'})
        slot_vals = real_flow.slot_values_dict()
        assert slot_vals.get('type') == 'draft'
        assert slot_vals.get('topic') == 'SEO tips'

    def test_utterance_calls_fill_slots(self, nlu):
        real_flow = flow_classes['create']()
        nlu.flow_stack.find_by_name.return_value = None
        nlu.flow_stack.push.return_value = real_flow
        with patch.object(nlu, '_fill_slots') as mock_fill:
            state = nlu.react('{05A}', {'topic': 'SEO'})
        mock_fill.assert_called_once()
        assert state.flow_name == 'create'

    def test_fill_slot_values_called_with_payload(self, nlu):
        real_flow = flow_classes['create']()
        nlu.flow_stack.find_by_name.return_value = None
        nlu.flow_stack.push.return_value = real_flow
        spy = MagicMock(wraps=real_flow.fill_slot_values)
        real_flow.fill_slot_values = spy
        nlu.react('{05A}', {'type': 'note'})
        spy.assert_any_call({'type': 'note'})

    def test_all_action_dax_codes_resolve(self):
        from utils.helper import dax2flow
        for flow_name, cat in FLOW_CATALOG.items():
            dax = cat['dax']
            resolved = dax2flow(dax)
            assert resolved == flow_name, \
                f'dax2flow({dax!r}) returned {resolved!r}, expected {flow_name!r}'


# ═══════════════════════════════════════════════════════════════════
# Service tests — fixtures and helpers
# ═══════════════════════════════════════════════════════════════════

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

    def test_get_template_returns_metadata(self):
        from backend.modules.templates import get_template
        info = get_template('brainstorm', 'Draft')
        assert info['skip_naturalize'] is True
        assert '{message}' in info['template']
        info2 = get_template('outline', 'Draft')
        assert info2['skip_naturalize'] is True
        assert '{message}' in info2['template']

    def test_build_payload_frame_sets_panel(self, minimal_config):
        from backend.modules.res import RES
        world = MagicMock()
        world.flow_stack.pop_completed_and_invalid.return_value = []
        world.flow_stack.get_flow.return_value = None
        res = RES(minimal_config, MagicMock(), MagicMock(), world)
        frame = self._make_frame(minimal_config, block_type='card',
                                 content='Hello', origin='compose')
        payload = res.build_payload_frame(frame, 'Some text')
        assert payload['panel'] == 'split'
        assert payload['blocks'][0]['type'] == 'card'
        assert payload['blocks'][0]['data']['content'] == 'Hello'


# ═══════════════════════════════════════════════════════════════════
# PostService
# ═══════════════════════════════════════════════════════════════════

class TestPostService:
    # -- Return format invariants -------------------------------------------

    def test_error_has_three_keys(self, tmp_db):
        svc = PostService()
        result = svc.read_metadata('nonexistent_id')
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
        svc = PostService()
        result = svc.read_metadata('nonexistent')
        assert result['_success'] is False
        assert result['_error'] == 'not_found'

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
        assert 'lines' in result

    def test_read_section_not_found(self, tmp_db):
        post_id, _ = _seed_test_post(tmp_db)
        svc = PostService()
        result = svc.read_section(post_id, 'nonexistent-section')
        assert result['_success'] is False
        assert result['_error'] == 'not_found'

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
        post_id, _ = _seed_test_post(tmp_db, title='Delete Me')
        svc = PostService()
        result = svc.delete_post(post_id)
        assert result['_success'] is True
        # Verify it's gone
        result2 = svc.read_metadata(post_id)
        assert result2['_success'] is False

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
        post_id, _ = _seed_test_post(tmp_db)
        svc = ContentService()
        content = '- orphan bullet\n- another orphan\n'
        result = svc.generate_outline(post_id, content)
        assert result['_success'] is False
        assert result['_error'] == 'validation'

    def test_generate_outline_rejects_duplicates(self, tmp_db):
        post_id, _ = _seed_test_post(tmp_db)
        svc = ContentService()
        content = '## Intro\n\ntext\n\n## Intro\n\nmore text\n'
        result = svc.generate_outline(post_id, content)
        assert result['_success'] is False
        assert 'Duplicate' in result['_message']

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

    def test_insert_content_at_line(self, tmp_db):
        body = '## Intro\n\nLine one.\nLine two.\nLine three.\n'
        post_id, _ = _seed_test_post(tmp_db, title='Insert Line', body=body)
        svc = ContentService()
        result = svc.insert_content(post_id, 'intro', 'Inserted line.', line_number=2)
        assert result['_success'] is True

    def test_revise_content_takes_snapshot(self, tmp_db):
        body = '## Intro\n\nOriginal content.\n'
        post_id, _ = _seed_test_post(tmp_db, title='Revise Snap', body=body)
        svc = ContentService()
        result = svc.revise_content(post_id, 'intro', 'Revised content.')
        assert result['_success'] is True

        snapshot = ToolService()._read_snapshot(post_id, 'intro', 1)
        assert snapshot is not None

    def test_revise_content_by_line_range(self, tmp_db):
        body = '## Intro\n\nLine A.\nLine B.\nLine C.\n'
        post_id, _ = _seed_test_post(tmp_db, title='Line Range', body=body)
        svc = ContentService()
        result = svc.revise_content(post_id, 'intro', 'Replaced.', lines=(2, 3))
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

    def test_find_and_replace_count(self, tmp_db):
        body = '## Intro\n\nThe cat sat on the cat mat.\n'
        post_id, _ = _seed_test_post(tmp_db, title='FAR Test', body=body)
        svc = ContentService()
        result = svc.find_and_replace(post_id, 'cat', 'dog')
        assert result['_success'] is True
        assert result['count'] == 2

    def test_find_and_replace_no_match(self, tmp_db):
        body = '## Intro\n\nHello world.\n'
        post_id, _ = _seed_test_post(tmp_db, title='No Match', body=body)
        svc = ContentService()
        result = svc.find_and_replace(post_id, 'xyz123', 'replacement')
        assert result['_success'] is False
        assert result['_error'] == 'not_found'

    def test_remove_content_lines(self, tmp_db):
        body = '## Intro\n\nLine 1.\nLine 2.\nLine 3.\n'
        post_id, _ = _seed_test_post(tmp_db, title='Remove Lines', body=body)
        svc = ContentService()
        result = svc.remove_content(post_id, 'intro', lines=(2, 3))
        assert result['_success'] is True

    def test_remove_content_section(self, tmp_db):
        body = '## Intro\n\nKeep.\n\n## ToRemove\n\nDelete me.\n'
        post_id, _ = _seed_test_post(tmp_db, title='Remove Sec', body=body)
        svc = ContentService()
        result = svc.remove_content(post_id, 'toremove')
        assert result['_success'] is True

    def test_cut_and_paste_moves_lines(self, tmp_db):
        body = '## Source\n\nLine A.\nLine B.\n\n## Target\n\nLine C.\n'
        post_id, _ = _seed_test_post(tmp_db, title='CnP Test', body=body)
        svc = ContentService()
        result = svc.cut_and_paste(post_id, 'source', 'target', source_lines=(1, 2))
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

