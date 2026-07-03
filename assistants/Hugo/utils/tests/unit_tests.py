"""Unit tests — pure code logic, mocked LLM, no API keys needed.

Covers:
  - PromptEngineer: model resolution, provider dispatch
  - Ensemble voting: config invariants, _tally_votes, _detect_flow (mocked)
  - NLU react(): DAX routing, slot parsing, utterance fill
  - Template fill: artifact.thoughts / data fallback
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
from backend.components.context_coordinator import ContextCoordinator, Turn
from backend.components.memory_manager import MemoryManager
from backend.components.session_scratchpad import SessionScratchpad
from backend.components.user_preferences import UserPreferences
from backend.components.business_context import BusinessContext
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

class TestEnsembleVoting:
    """Tally + dispatch math for the NLU ensemble voter. Config invariants and
    bare-routing dispatch tests removed — they pass on typos, not behavior."""

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
        def mock_call(prompt, task='skill', model='med', max_tokens=1024, schema=None):
            if model == 'high':
                raise RuntimeError('voter down')
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
        def mock_call(prompt, task='skill', model='med', max_tokens=1024, schema=None):
            if model == 'low':
                return {'flow_name': 'chat'}
            return {'flow_name': 'brainstorm'}

        real_engineer = nlu.engineer
        stub = MagicMock(side_effect=mock_call)
        stub.apply_guardrails = real_engineer.apply_guardrails
        nlu.engineer = stub
        result = nlu._detect_flow('give me ideas', intent='Draft')

        assert result['flow_name'] == 'brainstorm'
        assert result['confidence'] == pytest.approx(0.70)   # med voter alone (D6 two-voter ensemble)


# ═══════════════════════════════════════════════════════════════════
# NLU react()
# ═══════════════════════════════════════════════════════════════════

class TestNLUSpecificRegressions:
    """NLU regressions kept here separately from the module-level table in
    test_nlu_module.py — these test specific historical bugs, not module contracts."""

    def test_all_action_dax_codes_resolve(self):
        """FLOW_CATALOG dax codes must round-trip through dax2flow. Catches catalog
        drift where a flow's dax doesn't match the dax2flow lookup."""
        from utils.helper import dax2flow
        for flow_name, cat in FLOW_CATALOG.items():
            dax = cat['dax']
            resolved = dax2flow(dax)
            assert resolved == flow_name, \
                f'dax2flow({dax!r}) returned {resolved!r}, expected {flow_name!r}'

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

# TestAgent removed — its legacy take_turn keep_going loop (res.start / res.respond) was retired
# by the orchestrator-only cutover, and the 'create' flow it drove became a tool. The orchestrator
# loop is covered by TestOrchestratorLoop / TestOrchestratorClickBypass.

# ═══════════════════════════════════════════════════════════════════
# SessionScratchpad — file-backed scratchpad JSONL (changes.md §5.3)
# ═══════════════════════════════════════════════════════════════════

class TestSessionScratchpad:
    """The scratchpad in both modes: the in-memory dict (no path) and the append-only JSONL file
    (path set — orchestrator substrate). Covers writer stamping, filtering, clear/truncate, and the
    completion-record shape."""

    @pytest.fixture
    def file_memory(self, minimal_config, tmp_path):
        return SessionScratchpad(minimal_config, scratchpad_path=str(tmp_path / 'scratchpad.jsonl'))

    # ── in-memory mode ───────────────────────────────────────────────

    def test_inmemory_mode_unchanged(self, minimal_config):
        memory = SessionScratchpad(minimal_config)
        memory.write('repair', 'bad outline')
        assert memory.read('repair') == 'bad outline'
        assert memory.read() == {'repair': 'bad outline'}
        assert memory.size == 1
        memory.clear()
        assert memory.size == 0
        assert memory.read('repair') == ''

    # ── file mode: append / read / clear ─────────────────────────────

    def test_append_and_read_newest_last(self, file_memory):
        file_memory.write({'finding': 'first'})
        file_memory.write({'finding': 'second'})
        entries = file_memory.read()
        assert [entry['finding'] for entry in entries] == ['first', 'second']
        assert file_memory.size == 2

    def test_read_before_first_write_is_empty(self, file_memory):
        assert file_memory.read() == []
        assert file_memory.size == 0

    def test_key_value_call_wraps_into_entry(self, file_memory):
        file_memory.write('repair', 'bad outline')
        entries = file_memory.read()
        assert entries == [{'repair': 'bad outline', 'writer': 'orchestrator'}]

    def test_clear_truncates_file(self, file_memory):
        file_memory.write({'finding': 'gone soon'})
        file_memory.clear()
        assert file_memory.read() == []
        assert file_memory.size == 0

    def test_entries_persist_on_disk(self, minimal_config, tmp_path):
        path = tmp_path / 'scratchpad.jsonl'
        SessionScratchpad(minimal_config, scratchpad_path=str(path)).write({'note': 'kept'})
        reopened = SessionScratchpad(minimal_config, scratchpad_path=str(path))
        assert reopened.read() == [{'note': 'kept', 'writer': 'orchestrator'}]

    # ── writer stamping (decision 17) ────────────────────────────────

    def test_writer_defaults_to_orchestrator(self, file_memory):
        file_memory.write({'finding': 'x'})
        assert file_memory.read()[0]['writer'] == 'orchestrator'

    def test_writer_takes_flow_name(self, file_memory):
        file_memory.write({'finding': 'x'}, writer='compose')
        assert file_memory.read()[0]['writer'] == 'compose'

    def test_forged_writer_is_overwritten(self, file_memory):
        file_memory.write({'finding': 'x', 'writer': 'forged'}, writer='audit')
        assert file_memory.read()[0]['writer'] == 'audit'

    # ── read filters ─────────────────────────────────────────────────

    def test_filter_by_writer(self, file_memory):
        file_memory.write({'finding': 'a'}, writer='compose')
        file_memory.write({'finding': 'b'})
        file_memory.write({'finding': 'c'}, writer='compose')
        entries = file_memory.read(writer='compose')
        assert [entry['finding'] for entry in entries] == ['a', 'c']

    def test_filter_by_keys_present(self, file_memory):
        file_memory.write({'flow': 'compose', 'summary': 's', 'metadata': {}})
        file_memory.write({'finding': 'loose note'})
        entries = file_memory.read(keys=['flow', 'summary'])
        assert len(entries) == 1
        assert entries[0]['flow'] == 'compose'

    def test_filters_combine(self, file_memory):
        file_memory.write({'flow': 'compose', 'summary': 's'}, writer='compose')
        file_memory.write({'flow': 'audit', 'summary': 's'}, writer='audit')
        file_memory.write({'finding': 'x'}, writer='compose')
        entries = file_memory.read(writer='compose', keys=['flow'])
        assert entries == [{'flow': 'compose', 'summary': 's', 'writer': 'compose'}]

    # ── completion record (decision 7) ───────────────────────────────

    def test_completion_record_shape(self, file_memory):
        record = file_memory.write_completion('compose', 'Drafted the intro.', {'post': 'cafe01'})
        expected = {'flow': 'compose', 'summary': 'Drafted the intro.',
                    'metadata': {'post': 'cafe01'}, 'writer': 'compose'}
        assert record == expected
        assert file_memory.read() == [expected]

    def test_completion_record_default_metadata(self, file_memory):
        record = file_memory.write_completion('audit', 'No issues found.')
        assert record['metadata'] == {}
        assert file_memory.read(keys=['flow', 'summary', 'metadata']) == [record]


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
# TaskArtifact + Part (A2A v1.0)
# ═══════════════════════════════════════════════════════════════════

class TestArtifactParts:
    """A2A v1.0 Part oneof contract + TaskArtifact helper-property surface."""

    def test_part_rejects_zero_set(self):
        from backend.components.task_artifact import Part
        with pytest.raises(ValueError):
            Part()

    def test_part_rejects_multiple_set(self):
        from backend.components.task_artifact import Part
        with pytest.raises(ValueError):
            Part(text='x', data={})

    def test_part_data_serializes(self):
        from backend.components.task_artifact import Part
        assert Part(data={'a': 1}).to_dict() == {'data': {'a': 1}}

    def test_part_raw_serializes_base64(self):
        from backend.components.task_artifact import Part
        out = Part(raw=b'\x00\x01\xff').to_dict()
        assert out == {'raw': 'AAH/'}

    def test_part_metadata_round_trips(self):
        from backend.components.task_artifact import Part
        out = Part(text='hi', metadata={'kind': 'thoughts'}).to_dict()
        assert out == {'text': 'hi', 'metadata': {'kind': 'thoughts'}}

    def test_artifact_wraps_parts_dict_as_data_part(self):
        from backend.components.task_artifact import TaskArtifact
        artifact = TaskArtifact(parts={'violation': 'tool_error'})
        assert isinstance(artifact.parts, list)
        assert len(artifact.parts) == 1
        assert artifact.parts[0].data == {'violation': 'tool_error'}
        assert artifact.data['violation'] == 'tool_error'

    def test_thoughts_setter_is_idempotent(self):
        from backend.components.task_artifact import TaskArtifact
        artifact = TaskArtifact()
        artifact.thoughts = 'first'
        artifact.thoughts = 'second'
        text_parts = [p for p in artifact.parts if p.text is not None]
        assert len(text_parts) == 1
        assert artifact.thoughts == 'second'

    def test_code_setter_is_idempotent(self):
        from backend.components.task_artifact import TaskArtifact
        artifact = TaskArtifact()
        artifact.code = 'a'
        artifact.code = 'b'
        code_parts = [p for p in artifact.parts
                      if p.text is not None and (p.metadata or {}).get('kind') == 'code']
        assert len(code_parts) == 1
        assert artifact.code == 'b'

    def test_thoughts_and_code_are_distinct_parts(self):
        from backend.components.task_artifact import TaskArtifact
        artifact = TaskArtifact(thoughts='t', code='c')
        kinds = sorted((p.metadata or {}).get('kind') for p in artifact.parts if p.text is not None)
        assert kinds == ['code', 'thoughts']
        assert artifact.thoughts == 't'
        assert artifact.code == 'c'

    def test_add_part_appends_independent_parts(self):
        from backend.components.task_artifact import TaskArtifact
        artifact = TaskArtifact(parts={'v': 1}, thoughts='t', code='c')
        artifact.add_part(raw=b'\x00', metadata={'mime': 'image/png'})
        assert len(artifact.parts) == 4
        assert artifact.data == {'v': 1}
        assert artifact.thoughts == 't'
        assert artifact.code == 'c'

    def test_update_data_merges_into_existing_data_part(self):
        from backend.components.task_artifact import TaskArtifact
        artifact = TaskArtifact(parts={'a': 1})
        artifact.update_data(b=2)
        assert artifact.data == {'a': 1, 'b': 2}
        data_parts = [p for p in artifact.parts if p.data is not None]
        assert len(data_parts) == 1

    def test_to_dict_emits_a2a_parts_list(self):
        from backend.components.task_artifact import TaskArtifact
        artifact = TaskArtifact(origin='compose', parts={'v': 1}, thoughts='t', code='c')
        out = artifact.to_dict()
        assert out['origin'] == 'compose'
        assert isinstance(out['parts'], list)
        kinds = [(p.get('metadata') or {}).get('kind') for p in out['parts']]
        assert 'thoughts' in kinds and 'code' in kinds


# ═══════════════════════════════════════════════════════════════════
# Template fill functions
# ═══════════════════════════════════════════════════════════════════

class TestTemplateFill:
    """Verify fill_*_template functions and RES.display() block assembly."""

    def _make_frame(self, minimal_config, block_type='default',
                    thoughts='', content='', origin=None):
        from backend.components.task_artifact import TaskArtifact
        artifact = TaskArtifact(minimal_config)
        artifact.origin = origin or ''
        artifact.thoughts = thoughts
        if block_type != 'default' or content:
            data = {'content': content} if content else {}
            artifact.add_block({'type': block_type, 'data': data})
        return artifact

    def test_build_payload_serializes_frame(self, minimal_config):
        from backend.agent import Agent
        artifact = self._make_frame(minimal_config, block_type='card',
                                 content='Hello', origin='compose')
        payload = Agent._build_payload(None, 'Some text', artifact)
        assert 'panel' not in payload
        assert payload['artifact']['blocks'][0]['type'] == 'card'
        assert payload['artifact']['blocks'][0]['panel'] == 'bottom'
        assert payload['artifact']['blocks'][0]['data']['content'] == 'Hello'

    # The audit-message formatting tests were removed with RES — `_format_audit_message` lived in
    # the deleted backend/modules/templates; PEX now narrates audit results directly.


# ═══════════════════════════════════════════════════════════════════
# RES.respond_tool — the orchestrator `respond` tool surface (changes.md §4.1)
# ═══════════════════════════════════════════════════════════════════

# TestRespondTool removed — the RES `respond` tool surface was retired (PEX composes the reply
# directly; the orchestrator's final no-tool text IS the reply). The class also exercised the
# now-removed 'create' and 'inspect' flows.


# ═══════════════════════════════════════════════════════════════════
# PostService
# ═══════════════════════════════════════════════════════════════════

class TestPostService:
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
        svc.take_snapshot(post_id=post_id, turn_id=1, flow_name='polish',
            summary='polish on intro', sections=[{'sec_id': 'intro', 'lines': ['old']}])
        assert any(svc._snap_root.glob('snap_*.json'))
        svc.delete_post(post_id)
        # Snapshots referencing the deleted post are cleaned up.
        for path in svc._snap_root.glob('snap_*.json'):
            bundle = json.loads(path.read_text(encoding='utf-8'))
            assert bundle['post_id'] != post_id

    def test_summarize_text_empty_error(self, tmp_db):
        svc = PostService()
        result = svc.summarize_text()
        assert result['_success'] is False
        assert result['_error'] == 'validation'

    def test_rollback_post_no_snapshots(self, tmp_db):
        _seed_test_post(tmp_db, title='No Snaps')
        svc = PostService()
        result = svc.rollback_post('snap_999')
        assert result['_success'] is False
        assert result['_error'] == 'not_found'


# ═══════════════════════════════════════════════════════════════════
# ContentService
# ═══════════════════════════════════════════════════════════════════

class TestContentService:
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
        snap_id = svc.take_snapshot(post_id=post_id, turn_id=1, flow_name='polish',
            summary='polish on intro',
            sections=[{'sec_id': 'intro', 'lines': ['Original text.']}])
        svc.revise_content(post_id, 'intro', 'Updated text.')
        result = svc.diff_section(post_id, 'intro', snapshot_id=snap_id)
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
        result = svc.insert_media('post_x', 'sec_x', 'hero', 'a cat')
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

    def test_editor_review_loads_guide(self, tmp_db):
        svc = AnalysisService()
        guide_path = svc._guides_dir / 'editor_guide.md'
        guide_path.write_text('# Editor Guide\n\nCheck for clarity.')
        result = svc.editor_review('some content to review')
        assert result['_success'] is True
        assert 'Check for clarity' in result['guide']



# ═══════════════════════════════════════════════════════════════════
# PlatformService
# ═══════════════════════════════════════════════════════════════════

class TestPlatformService:
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
# BusinessContext (FAQs)
# ═══════════════════════════════════════════════════════════════════

class _FakeEngineer:
    """Minimal engineer stub: returns a canned schema-shaped dict for any call."""
    def __init__(self, response):
        self.response = response
        self.last_prompt = None

    def __call__(self, prompt, task='skill', schema=None, model='med', max_tokens=1024):
        self.last_prompt = prompt
        return self.response


@pytest.fixture
def tmp_faq_db(tmp_db):
    """Extends tmp_db with a tmp faq_data dir. tmp_db already patches services._DB_DIR;
    BusinessContext reads `services._DB_DIR / 'faq_data' / 'faqs.json'` at construction."""
    faq_dir = tmp_db / 'faq_data'
    faq_dir.mkdir()
    return faq_dir


class TestBusinessContext:
    def test_search_returns_top_matches(self, tmp_faq_db):
        (tmp_faq_db / 'faqs.json').write_text(json.dumps([
            {'question': 'What can Hugo do?', 'answer': 'Help write blog posts.', 'tags': ['cap']},
            {'question': 'Who built Hugo?', 'answer': 'Soleda.', 'tags': ['origin']},
        ]))
        from backend.components.business_context import BusinessContext
        engineer = _FakeEngineer({'matches': [{'idx': 0, 'score': 0.92}]})
        svc = BusinessContext(engineer)
        result = svc.search_faqs(query='what can it do', top_k=3)
        assert result['_success'] is True
        assert len(result['matches']) == 1
        assert result['matches'][0]['question'] == 'What can Hugo do?'
        assert result['matches'][0]['score'] == 0.92

    def test_search_empty_corpus(self, tmp_faq_db):
        # No faqs.json written — corpus loads empty.
        from backend.components.business_context import BusinessContext
        svc = BusinessContext(_FakeEngineer({'matches': []}))
        result = svc.search_faqs(query='anything')
        assert result['_success'] is False
        assert result['_error'] == 'empty_corpus'

    def test_search_drops_out_of_range_indices(self, tmp_faq_db):
        (tmp_faq_db / 'faqs.json').write_text(json.dumps([
            {'question': 'Q1', 'answer': 'A1', 'tags': []},
        ]))
        from backend.components.business_context import BusinessContext
        engineer = _FakeEngineer({'matches': [{'idx': 0, 'score': 0.8},
            {'idx': 99, 'score': 0.2}]})
        svc = BusinessContext(engineer)
        result = svc.search_faqs(query='q')
        # Out-of-range idx (99) silently dropped; valid one kept.
        assert len(result['matches']) == 1
        assert result['matches'][0]['question'] == 'Q1'


class TestMemoryManagerFacade:
    """The MEM facade delegates each read skill to its tier (recap→L1, recall→L2, retrieve→L3)."""

    def test_recall_returns_stored_preferences(self, minimal_config):
        prefs = UserPreferences(minimal_config)
        prefs.store_preference('tone', 'casual')
        memory = MemoryManager(None, prefs, None)
        assert memory.recall('tone') == {'tone': 'casual'}

    def test_retrieve_faq_shortcut(self, minimal_config):
        business = BusinessContext(_FakeEngineer({'matches': [{'idx': 0, 'score': 0.9}]}))
        business._corpus = [{'question': 'What is X?', 'answer': 'X is Y.'}]
        memory = MemoryManager(None, None, business)
        result = memory.retrieve('what is x', documents=['faq'])
        assert result['_success'] is True
        assert result['matches'][0]['question'] == 'What is X?'

    def test_recap_returns_recent_history(self, minimal_config):
        world = World(minimal_config)
        world.context.add_turn('User', 'draft a post about otters', 'utterance')
        memory = MemoryManager(world.context, None, None)
        assert 'otters' in memory.recap()


# ═══════════════════════════════════════════════════════════════════
# Snapshot infrastructure
# ═══════════════════════════════════════════════════════════════════

class TestSnapshotInfra:
    def test_take_snapshot_creates_file(self, tmp_db):
        svc = ToolService()
        snap_id = svc.take_snapshot(post_id='test_post', turn_id=1, flow_name='polish',
            summary='polish on intro',
            sections=[{'sec_id': 'intro', 'lines': ['line 1', 'line 2']}])
        bundle = svc.read_snapshot(snap_id)
        assert bundle is not None
        assert bundle['post_id'] == 'test_post'
        assert bundle['content'][0]['lines'] == ['line 1', 'line 2']

    def test_take_snapshot_caps_at_max(self, tmp_db):
        svc = ToolService()
        overflow = svc.max_snapshots + 2
        for idx in range(overflow):
            svc.take_snapshot(post_id='test_post', turn_id=idx, flow_name='polish',
                summary=f'turn {idx}',
                sections=[{'sec_id': 'intro', 'lines': [f'version {idx}']}])
        ids = svc.list_snapshots()
        assert len(ids) == svc.max_snapshots
        # Most recent first; the last call is at the head.
        head = svc.read_snapshot(ids[0])
        assert head['content'][0]['lines'] == [f'version {overflow - 1}']

    def test_cross_post_clears_history(self, tmp_db):
        svc = ToolService()
        svc.take_snapshot(post_id='post_a', turn_id=1, flow_name='polish',
            summary='polish A', sections=[{'sec_id': 'intro', 'lines': ['A1']}])
        svc.take_snapshot(post_id='post_a', turn_id=2, flow_name='polish',
            summary='polish A', sections=[{'sec_id': 'intro', 'lines': ['A2']}])
        svc.take_snapshot(post_id='post_b', turn_id=3, flow_name='polish',
            summary='polish B', sections=[{'sec_id': 'intro', 'lines': ['B1']}])
        ids = svc.list_snapshots()
        # Cross-post write wiped post_a snapshots; only the post_b snapshot remains.
        assert len(ids) == 1
        bundle = svc.read_snapshot(ids[0])
        assert bundle['post_id'] == 'post_b'

    def test_record_snapshot_section_scoped(self, tmp_db):
        # `record_snapshot` expects canonical slugs (normalized upstream by
        # `_resolve_source_ids`). Section-scoped bundle captures only the named slug.
        from backend.utilities.services import ContentService
        from backend.modules.policies.base import BasePolicy

        body = '## Hungry for Power\n\nOriginal prose about power.\n\n## Other\n\nOther.\n'
        post_id, _ = _seed_test_post(tmp_db, title='Slug Test', body=body)
        content = ContentService()

        class FakeFlow:
            def name(self): return 'simplify'
        class FakeContext:
            turn_id = 1

        policy = BasePolicy.__new__(BasePolicy)  # bypass __init__
        snap_id = policy.record_snapshot(content, FakeFlow(), FakeContext(),
            post_id, sec_ids=['hungry-for-power'])
        bundle = content.read_snapshot(snap_id)
        assert len(bundle['content']) == 1
        assert bundle['content'][0]['sec_id'] == 'hungry-for-power'
        assert any('Original prose about power' in line for line in bundle['content'][0]['lines'])


# ═══════════════════════════════════════════════════════════════════
# Pillar 1 snapshot harness — DIY helper smoke tests
# ═══════════════════════════════════════════════════════════════════

class TestSnapshotHarness:
    """Smoke tests for utils/tests/_snapshot.py — ensure the harness itself works."""

    def test_volatile_keys_masked(self):
        from utils._snapshot import _mask_volatile
        result = _mask_volatile({
            'flow_id': 'abc-123', 'post_id': 'xyz', 'value_count': 3,
            'nested': {'turn_id': 't1', 'real_data': 'kept'},
        })
        assert result['flow_id'] == '<masked>'
        assert result['post_id'] == '<masked>'
        assert result['value_count'] == 3  # non-volatile shape stays
        assert result['nested']['turn_id'] == '<masked>'
        assert result['nested']['real_data'] == 'kept'

    def test_record_then_match(self, tmp_path, monkeypatch):
        from utils import _snapshot
        monkeypatch.setattr(_snapshot, 'SNAPSHOT_DIR', tmp_path)
        # Record
        monkeypatch.setenv('UPDATE_SNAPSHOTS', '1')
        _snapshot.assert_snapshot({'a': 1, 'b': [2, 3]}, 'sample')
        assert (tmp_path / 'sample.json').exists()
        # Compare — same value passes
        monkeypatch.delenv('UPDATE_SNAPSHOTS')
        _snapshot.assert_snapshot({'a': 1, 'b': [2, 3]}, 'sample')

    def test_mismatch_raises(self, tmp_path, monkeypatch):
        from utils import _snapshot
        monkeypatch.setattr(_snapshot, 'SNAPSHOT_DIR', tmp_path)
        monkeypatch.setenv('UPDATE_SNAPSHOTS', '1')
        _snapshot.assert_snapshot({'a': 1}, 'sample')
        monkeypatch.delenv('UPDATE_SNAPSHOTS')
        with pytest.raises(AssertionError, match='Snapshot mismatch'):
            _snapshot.assert_snapshot({'a': 2}, 'sample')

    def test_missing_snapshot_raises(self, tmp_path, monkeypatch):
        from utils import _snapshot
        monkeypatch.setattr(_snapshot, 'SNAPSHOT_DIR', tmp_path)
        with pytest.raises(AssertionError, match='No snapshot at'):
            _snapshot.assert_snapshot({'a': 1}, 'never_recorded')


# ═══════════════════════════════════════════════════════════════════
# Session substrate — file-backed DialogueState + World session dirs
# ═══════════════════════════════════════════════════════════════════

from backend.components.dialogue_state import DialogueState
from backend.components.world import World


@pytest.fixture
def sessions_dir(tmp_path, monkeypatch):
    """Redirect the module-level sessions root to a tmp dir (same pattern as tmp_db)."""
    from backend.components import world as world_mod
    path = tmp_path / 'sessions'
    monkeypatch.setattr(world_mod, '_SESSIONS_DIR', path)
    return path


@pytest.fixture
def session_config(minimal_config):
    config = dict(minimal_config)
    config['session'] = {'persistence': {'max_sessions': 2}}
    return MappingProxyType(config)


def _session_state() -> DialogueState:
    state = DialogueState(intent='Draft', dax=None, turn_count=12)
    state.conversation_id = 'convo-42'
    state.username = 'derek'
    state.goal = 'draft the agents post'
    state.confirmed = ['title']
    state.rejected = ['listicle format']
    state.workflow_step = 4
    state.grounding = {'post': 'p1', 'sec': 'intro', 'snip': '', 'chl': 'substack', 'ver': True}
    state.flow_stack = [{'name': 'compose', 'status': 'Active', 'stage': 'writing',
                         'plan_id': None, 'slots': {'source': {'post': 'p1'}}}]
    state.has_plan = True
    return state


class TestSessionStateFile:
    """File-backed DialogueState (changes.md §5.2): the five-block state.json document."""

    def test_round_trip_identical_dict(self, tmp_path):
        state = _session_state()
        state_file = tmp_path / 'state.json'
        state.save(state_file)
        reloaded = DialogueState.load(state_file)
        assert reloaded.serialize_session() == state.serialize_session()

    def test_document_blocks_and_grounding_parts(self):
        document = _session_state().serialize_session()
        assert list(document) == ['session', 'user_beliefs', 'grounding', 'flow_stack', 'flags']
        assert list(document['grounding']) == ['post', 'sec', 'snip', 'chl', 'ver']
        assert document['session']['turn_count'] == 12
        assert document['user_beliefs']['intent'] == 'Draft'
        assert document['flags'] == {'has_issues': False, 'has_plan': True}

    def test_load_rehydrates_fields(self, tmp_path):
        state_file = tmp_path / 'state.json'
        _session_state().save(state_file)
        reloaded = DialogueState.load(state_file)
        assert reloaded.conversation_id == 'convo-42'
        assert reloaded.username == 'derek'
        assert reloaded.workflow_step == 4
        assert reloaded.grounding['ver'] is True
        assert reloaded.flow_stack[0]['name'] == 'compose'
        assert reloaded.has_plan is True

    def test_old_per_turn_form_unchanged(self):
        state = DialogueState(intent='Revise', dax='3AB', turn_count=2, confidence=0.9)
        serialized = state.serialize()
        assert serialized['pred_intent'] == 'Revise'
        assert serialized['flow_name'] == '3AB'
        assert DialogueState.from_dict(serialized).serialize() == serialized


class TestWorldSessions:
    """World as session container (changes.md §5.4, decisions 10, 11, 15)."""

    def test_fresh_session_is_lazy(self, sessions_dir, minimal_config):
        world = World(minimal_config)
        assert world.open_session('fresh-id') is None
        assert not (sessions_dir / 'fresh-id').exists()  # nothing on disk until first use
        assert world.session_dir() == sessions_dir / 'fresh-id'
        assert (sessions_dir / 'fresh-id').is_dir()

    def test_open_session_rehydrates(self, sessions_dir, minimal_config):
        (sessions_dir / 'convo-42').mkdir(parents=True)
        _session_state().save(sessions_dir / 'convo-42' / 'state.json')
        world = World(minimal_config)
        state = world.open_session('convo-42')
        assert world.current_state() is state
        assert state.serialize_session() == _session_state().serialize_session()

    def test_reset_deletes_and_recreates_session_dir(self, sessions_dir, minimal_config):
        world = World(minimal_config)
        world.open_session('convo-42')
        world.current_state().save(world.state_file())
        world.reset()
        assert (sessions_dir / 'convo-42').is_dir()
        assert list((sessions_dir / 'convo-42').iterdir()) == []
        # In-memory reset still re-seeds the old pipeline's substrate.
        assert world.current_state().turn_count == 0
        assert world.latest_artifact() is not None

    def test_reset_without_session_still_works(self, sessions_dir, minimal_config):
        world = World(minimal_config)
        world.reset()
        assert not sessions_dir.exists()
        assert world.current_state().turn_count == 0

    def test_close_prunes_to_most_recent_n(self, sessions_dir, session_config):
        import os
        sessions_dir.mkdir(parents=True)
        for idx, convo in enumerate(['oldest', 'middle', 'newest']):
            (sessions_dir / convo).mkdir()
            stamp = 1_700_000_000 + idx * 1000
            os.utime(sessions_dir / convo, (stamp, stamp))
        world = World(session_config)
        world.close()
        survivors = sorted(path.name for path in sessions_dir.iterdir())
        assert survivors == ['middle', 'newest']

    def test_close_with_no_sessions_dir(self, sessions_dir, session_config):
        World(session_config).close()  # nothing on disk yet — must not crash
        assert not sessions_dir.exists()


# ═══════════════════════════════════════════════════════════════════
# ContextCoordinator — persistent message list (changes.md §5.5)
# ═══════════════════════════════════════════════════════════════════

def _tool_call_messages() -> list[dict]:
    """A user turn, an assistant tool call, and its paired tool result (API-shaped)."""
    return [
        {'role': 'user', 'content': 'Draft a post about cheetahs'},
        {'role': 'assistant', 'content': [{'type': 'tool_use', 'id': 'toolu_01',
                                           'name': 'read_state', 'input': {}}]},
        {'role': 'user', 'content': [{'type': 'tool_result', 'tool_use_id': 'toolu_01',
                                      'content': '{"flow_name": "compose"}'}]},
        {'role': 'assistant', 'content': 'Started a draft about cheetahs.'},
    ]


class TestMessageList:
    """The API-shaped orchestrator transcript (decisions 6, 12): appended as the loop runs,
    mirrored to messages.jsonl, reloaded on session rehydrate. Turn records and
    compile_history remain the human-readable view and are untouched by this list."""

    @pytest.fixture
    def coordinator(self, minimal_config, tmp_path):
        coordinator = ContextCoordinator(minimal_config)
        coordinator.attach_messages(tmp_path / 'messages.jsonl')
        return coordinator

    def test_append_reload_round_trip(self, coordinator, minimal_config, tmp_path):
        for message in _tool_call_messages():
            coordinator.append_message(message)
        reopened = ContextCoordinator(minimal_config)
        reopened.attach_messages(tmp_path / 'messages.jsonl')
        assert reopened.messages == _tool_call_messages()

    def test_ordering_survives_reload(self, coordinator, minimal_config, tmp_path):
        for message in _tool_call_messages():
            coordinator.append_message(message)
        reopened = ContextCoordinator(minimal_config)
        reopened.attach_messages(tmp_path / 'messages.jsonl')
        assert [message['role'] for message in reopened.messages] == \
            ['user', 'assistant', 'user', 'assistant']

    def test_tool_result_pairing_preserved(self, coordinator, minimal_config, tmp_path):
        for message in _tool_call_messages():
            coordinator.append_message(message)
        reopened = ContextCoordinator(minimal_config)
        reopened.attach_messages(tmp_path / 'messages.jsonl')
        call, result = reopened.messages[1], reopened.messages[2]
        assert call['content'][0]['type'] == 'tool_use'
        assert result['content'][0]['tool_use_id'] == call['content'][0]['id']

    def test_attach_fresh_path_starts_empty(self, coordinator, tmp_path):
        assert coordinator.messages == []
        assert not (tmp_path / 'messages.jsonl').exists()  # reads never create the file

    def test_append_without_path_is_memory_only(self, minimal_config):
        coordinator = ContextCoordinator(minimal_config)
        coordinator.append_message({'role': 'user', 'content': 'hello'})
        assert coordinator.messages == [{'role': 'user', 'content': 'hello'}]

    def test_append_creates_session_dir_lazily(self, minimal_config, tmp_path):
        coordinator = ContextCoordinator(minimal_config)
        coordinator.attach_messages(tmp_path / 'convo-9' / 'messages.jsonl')
        coordinator.append_message({'role': 'user', 'content': 'hello'})
        assert (tmp_path / 'convo-9' / 'messages.jsonl').exists()

    def test_reset_clears_list_and_file(self, coordinator, tmp_path):
        coordinator.append_message({'role': 'user', 'content': 'gone soon'})
        coordinator.reset()
        assert coordinator.messages == []
        assert (tmp_path / 'messages.jsonl').read_text() == ''

    def test_turn_records_stay_independent(self, coordinator):
        coordinator.add_turn('User', 'Draft a post about cheetahs', 'utterance')
        coordinator.append_message({'role': 'user', 'content': 'Draft a post about cheetahs'})
        assert coordinator.turn_count == 1  # append_message never touches Turn records
        assert 'cheetahs' in coordinator.compile_history()

    def test_open_session_rehydrates_messages(self, sessions_dir, minimal_config):
        (sessions_dir / 'convo-42').mkdir(parents=True)
        lines = [json.dumps(message) for message in _tool_call_messages()]
        (sessions_dir / 'convo-42' / 'messages.jsonl').write_text('\n'.join(lines) + '\n')
        world = World(minimal_config)
        world.open_session('convo-42')
        assert world.context.messages == _tool_call_messages()


# ═══════════════════════════════════════════════════════════════════
# write_state ops + flow rehydration (changes.md §4.1, §5.2, §6)
# ═══════════════════════════════════════════════════════════════════

from backend.components.dialogue_state import rehydrate_flow
from backend.components.flow_stack import FlowStack


def _without_ids(entries:list) -> list:
    """Stack entries minus the random flow_id, for cross-implementation comparison."""
    return [{key: val for key, val in entry.items() if key != 'flow_id'} for entry in entries]


def _ops_state() -> DialogueState:
    state = DialogueState(intent='Draft', dax=None, turn_count=1)
    state.conversation_id = 'convo-ops'
    return state


class TestWriteStateOps:
    """write_state is the only writer of state.json; flow-stack ops are write_state ops."""

    def test_read_state_returns_document(self):
        document = _ops_state().read_state()
        assert list(document) == ['session', 'user_beliefs', 'grounding', 'flow_stack', 'flags']

    def test_update_op_mutates_and_saves(self, tmp_path):
        state = _ops_state()
        path = tmp_path / 'state.json'
        document = state.write_state(path, 'update', goal='ship the agents post',
                                     workflow_step=3, grounding={'post': 'p1', 'ver': True})
        assert document['user_beliefs']['goal'] == 'ship the agents post'
        reloaded = DialogueState.load(path)
        assert reloaded.workflow_step == 3
        assert reloaded.grounding == {'post': 'p1', 'sec': '', 'snip': '', 'chl': '', 'ver': True}

    def test_unknown_op_and_unknown_fields_raise(self, tmp_path):
        state = _ops_state()
        path = tmp_path / 'state.json'
        with pytest.raises(ValueError, match='Unknown write_state op'):
            state.write_state(path, 'merge')
        with pytest.raises(KeyError):
            state.write_state(path, 'update', vibe='good')
        with pytest.raises(KeyError):
            state.write_state(path, 'update', grounding={'version': 2})
        assert not path.exists()  # rejected ops never reach save()

    def test_op_sequence_matches_in_memory_flowstack(self, tmp_path):
        """Equivalence: the same stackon/fill/fallback/complete/pop sequence on the
        in-memory FlowStack and on the file-backed write_state yields the same stack."""
        path = tmp_path / 'state.json'
        state = _ops_state()
        stack = FlowStack({}, flow_classes=flow_classes)

        state.write_state(path, 'stackon', flow_name='outline')
        stack.stackon('outline')
        state.write_state(path, 'update_flow', slots={'source': [{'post': 'p1'}]},
                          stage='discovery')
        top = stack.get_flow()
        top.fill_slot_values({'source': [{'post': 'p1'}]})
        top.is_filled()
        top.stage = 'discovery'
        state.write_state(path, 'stackon', flow_name='brainstorm', plan_id='plan-7')
        stack.stackon('brainstorm', plan_id='plan-7')
        state.write_state(path, 'fallback', flow_name='refine')
        stack.fallback('refine')
        state.write_state(path, 'update', grounding={'post': 'p1'})
        state.write_state(path, 'update_flow', status='Completed')
        stack.get_flow().status = 'Completed'
        state.write_state(path, 'pop_completed')
        stack.pop_completed()

        assert _without_ids(state.flow_stack) == _without_ids(stack.to_list())
        assert _without_ids(DialogueState.load(path).flow_stack) == _without_ids(stack.to_list())

    def test_grounding_validation_raises_on_ungrounded_completion(self, tmp_path):
        path = tmp_path / 'state.json'
        state = _ops_state()
        state.write_state(path, 'stackon', flow_name='outline')
        with pytest.raises(ValueError, match='grounding.post is empty'):
            state.write_state(path, 'update_flow', status='Completed')
        assert state.flow_stack[0]['status'] == 'Active'  # rejected write left no trace
        assert DialogueState.load(path).flow_stack[0]['status'] == 'Active'

    def test_grounding_validation_passes_once_post_is_set(self, tmp_path):
        path = tmp_path / 'state.json'
        state = _ops_state()
        state.write_state(path, 'stackon', flow_name='outline')
        state.write_state(path, 'update', grounding={'post': 'p1'})
        state.write_state(path, 'update_flow', status='Completed')
        assert state.flow_stack[0]['status'] == 'Completed'

    def test_update_flow_normalizes_llm_shaped_slot_values(self, tmp_path):
        """Orchestrator-authored slot values: bare strings for checklist items and source
        entities, and a bare item in place of a list, all coerce instead of crashing."""
        path = tmp_path / 'state.json'
        state = _ops_state()
        state.write_state(path, 'stackon', flow_name='outline')
        state.write_state(path, 'update_flow',
                          slots={'sections': ['Motivation', 'Process'], 'source': 'p1',
                                 'topic': 'agents'})
        slots = state.flow_stack[0]['slots']
        assert [step['name'] for step in slots['sections']] == ['Motivation', 'Process']
        assert slots['source'][0]['post'] == 'p1'
        assert slots['topic'] == 'agents'

    def test_grounding_validation_skips_topic_grounded_flows(self, tmp_path):
        """Converse flows and exact-grounded flows (create's title) complete without a post,
        mirroring the old PEX post-hook's slot-type filter."""
        path = tmp_path / 'state.json'
        state = _ops_state()
        state.write_state(path, 'stackon', flow_name='chat')
        state.write_state(path, 'update_flow', status='Completed')
        state.write_state(path, 'pop_completed')
        state.write_state(path, 'stackon', flow_name='find')
        state.write_state(path, 'update_flow', status='Completed')
        assert state.flow_stack[0]['status'] == 'Completed'


class TestFlowRehydration:
    """Flows rehydrate from flow_classes + saved slot values (to_dict / fill vocabulary)."""

    def test_every_flow_round_trips_empty(self):
        for name, cls in flow_classes.items():
            flow = cls()
            flow.flow_id = 'abc12345'
            flow.status = 'Active'
            clone = rehydrate_flow(flow.to_dict())
            assert clone.to_dict() == flow.to_dict(), f'{name} did not round-trip'

    def test_slot_fidelity_survives_round_trip(self):
        flow = flow_classes['refine']()
        flow.flow_id = 'abc12345'
        flow.status = 'Active'
        flow.stage = 'delegation'
        flow.fill_slot_values({
            'source': [{'post': 'p1', 'sec': 'intro', 'ver': True}],
            'steps': [{'name': 'hook', 'description': 'opening line', 'checked': True}],
            'feedback': ['keep it short'],
        })
        flow.is_filled()
        clone = rehydrate_flow(flow.to_dict())
        assert clone.to_dict() == flow.to_dict()
        assert clone.stage == 'delegation'
        assert clone.slots['source'].filled is True
        assert clone.slots['source'].values == [
            {'post': 'p1', 'sec': 'intro', 'snip': '', 'chl': '', 'ver': True}]
        assert clone.slots['steps'].steps[0]['checked'] is True
        assert clone.slots['feedback'].values == ['keep it short']

    def test_range_slot_round_trips(self):
        flow = flow_classes['schedule']()
        flow.flow_id = 'abc12345'
        flow.status = 'Active'
        flow.fill_slot_values({'source': [{'post': 'p1'}], 'channel': ['substack'],
                               'datetime': {'time_len': 2, 'unit': 'day'}})
        flow.is_filled()
        clone = rehydrate_flow(flow.to_dict())
        assert clone.to_dict() == flow.to_dict()
        assert clone.slots['datetime'].filled is True
        assert clone.slots['datetime'].get_details() == flow.slots['datetime'].get_details()

    def test_image_slot_round_trips(self):
        flow = flow_classes['write']()
        flow.flow_id = 'abc12345'
        flow.status = 'Active'
        flow.fill_slot_values({'source': [{'post': 'p1'}],
                               'image': {'img_type': 'diagram', 'src': 'arch.png',
                                         'alt': 'architecture', 'position': 2}})
        flow.is_filled()
        clone = rehydrate_flow(flow.to_dict())
        assert clone.to_dict() == flow.to_dict()
        assert clone.slots['image'].filled is True
        assert clone.slots['image'].image_type == 'diagram'
        assert clone.slots['image'].position == 2


# ═══════════════════════════════════════════════════════════════════
# Pillar 3 — Hypothesis stateful test for FlowStack
# Drives the in-memory FlowStack AND the file-backed write_state ops
# through the same random-but-valid op sequence (changes.md Phase 1
# gate). Catches FSM-discipline regressions (depth bounds, status
# transitions, pop_completed semantics, get_flow filtering) and any
# divergence between the two implementations, including serialization
# round-trip loss. Recorded counter-examples become permanent
# regression tests via @reproduce_failure.
# ═══════════════════════════════════════════════════════════════════

class TestFlowStackStateful:
    """Wrapper namespace for the auto-generated Hypothesis TestCase."""


def _build_flowstack_machine():
    """Build the RuleBasedStateMachine class. Done in a helper so the imports
    only execute when Hypothesis is collected — avoids slowing free-tier import."""
    from hypothesis import settings
    from hypothesis.stateful import RuleBasedStateMachine, rule, invariant
    from hypothesis import strategies as st
    from backend.components.flow_stack import FlowStack
    from backend.components.flow_stack import flow_classes as _all_classes

    _NAMES = tuple(sorted(_all_classes))
    _STATUSES = (None, 'Active', 'Pending', 'Completed', 'Invalid')

    class FlowStackMachine(RuleBasedStateMachine):
        def __init__(self):
            super().__init__()
            config = MappingProxyType({'session': {'max_flow_depth': 8}})
            self.stack = FlowStack(config, flow_classes=_all_classes)
            # File-backed twin: the same ops run as write_state ops on a
            # DialogueState whose stack lives in the state file's flow_stack block.
            self.state = DialogueState(intent='Draft', dax=None, turn_count=0)
            self.state.conversation_id = 'machine'
            self.state.grounding['post'] = 'p1'  # keep completions grounded; the §6
            # raise has its own dedicated tests in TestWriteStateOps.
            self.tmp_dir = Path(tempfile.mkdtemp())
            self.state_file = self.tmp_dir / 'state.json'

        def teardown(self):
            shutil.rmtree(self.tmp_dir, ignore_errors=True)

        @rule(name=st.sampled_from(_NAMES))
        def stackon(self, name):
            if len(self.stack._stack) < self.stack._max_depth:
                top_before = self.stack._stack[-1] if self.stack._stack else None
                new_flow = self.stack.stackon(name)
                self.state.write_state(self.state_file, 'stackon', flow_name=name)
                # Two valid outcomes: pushed a new Active flow, OR returned the
                # existing in-flight top because no-consecutive-same-type kicked in.
                assert new_flow.flow_id and len(new_flow.flow_id) >= 6
                assert self.stack._stack[-1] is new_flow
                if new_flow is not top_before:
                    assert new_flow.status == 'Active'

        @rule(name=st.sampled_from(_NAMES))
        def fallback(self, name):
            # fallback() implements "replace top" by push-then-mark-invalid, which
            # grows the stack by 1. Skip when at the depth limit. (This shape —
            # fallback grows but is documented as "replace" — is a real surprise
            # the test surfaced; flagging here, not fixing.)
            if not self.stack._stack:
                return
            if len(self.stack._stack) >= self.stack._max_depth:
                return
            old_top = self.stack._stack[-1]
            self.stack.fallback(name)
            self.state.write_state(self.state_file, 'fallback', flow_name=name)
            assert old_top.status == 'Invalid'
            assert self.stack._stack[-1].status == 'Active'
            assert self.stack._stack[-1].flow_type == name

        @rule(post=st.sampled_from(['p1', 'p2']))
        def fill_source(self, post):
            # Exercises slot round-trip fidelity: flows without a 'source' slot
            # ignore the fill on both implementations.
            if self.stack._stack:
                top = self.stack._stack[-1]
                top.fill_slot_values({'source': [{'post': post}]})
                top.is_filled()
                self.state.write_state(self.state_file, 'update_flow',
                                       slots={'source': [{'post': post}]})

        @rule()
        def complete_top(self):
            if self.stack._stack:
                self.stack._stack[-1].status = 'Completed'
                self.state.write_state(self.state_file, 'update_flow', status='Completed')

        @rule()
        def mark_pending(self):
            # Some flows are pushed Pending by plans; simulate that state by
            # marking top Pending. Then pop_completed should activate it.
            if self.stack._stack:
                self.stack._stack[-1].status = 'Pending'
                self.state.write_state(self.state_file, 'update_flow', status='Pending')

        @rule()
        def pop_completed(self):
            before_completed = [e for e in self.stack._stack if e.status == 'Completed']
            self.stack.pop_completed()
            self.state.write_state(self.state_file, 'pop_completed')
            for entry in self.stack._stack:
                assert entry.status not in ('Completed', 'Invalid'), \
                    f'pop_completed left a {entry.status} flow on the stack'
            # Pending top auto-activates after pop_completed.
            if self.stack._stack and self.stack._stack[-1].status == 'Pending':
                pytest.fail('pop_completed did not activate the new top Pending flow')

        @rule(status=st.sampled_from(_STATUSES))
        def get_flow(self, status):
            result = self.stack.get_flow(status=status)
            if status is not None and result is not None:
                assert result.status == status, \
                    f'get_flow(status={status!r}) returned a {result.status!r} flow'

        @invariant()
        def depth_within_limit(self):
            assert 0 <= len(self.stack._stack) <= self.stack._max_depth

        @invariant()
        def all_flows_have_id(self):
            for entry in self.stack._stack:
                assert entry.flow_id, f'Flow {entry.flow_type} on stack without flow_id'

        @invariant()
        def statuses_in_vocabulary(self):
            valid = {'Pending', 'Active', 'Completed', 'Invalid'}
            for entry in self.stack._stack:
                assert entry.status in valid, f'unknown status {entry.status!r}'

        @invariant()
        def file_backed_stack_matches_in_memory(self):
            # The Phase-1 equivalence gate: same op sequence → same stack, both in
            # the live state object and in the saved state.json.
            in_memory = _without_ids(self.stack.to_list())
            assert _without_ids(self.state.flow_stack) == in_memory
            if self.state_file.exists():
                saved = DialogueState.load(self.state_file).flow_stack
                assert _without_ids(saved) == in_memory

    FlowStackMachine.TestCase.settings = settings(max_examples=50, deadline=2000)
    return FlowStackMachine


TestFlowStackMachine = _build_flowstack_machine().TestCase


# ═══════════════════════════════════════════════════════════════════
# Orchestrator tool catalog wiring (changes.md §4.1–4.3, decision 16)
# ═══════════════════════════════════════════════════════════════════

from backend.modules.pex import READ_ONLY_DOMAIN_TOOLS
from backend.components.task_artifact import TaskArtifact

_HOT_PATH_TOOLS = ('read_state', 'write_state', 'activate_flow',
                   'append_to_scratchpad', 'store_preference', 'read_scratchpad')


class TestOrchestratorToolDefs:
    """Hot-path tool definitions and the orchestrator's tool list (decision 16 allowlist)."""

    def test_defs_cover_dispatch_registry_exactly(self, mock_agent):
        pex = mock_agent.pex
        names = [tool['name'] for tool in pex._orchestrator_tool_definitions()]
        assert names == list(_HOT_PATH_TOOLS)
        assert set(pex._orchestrator_dispatch) == set(names)

    def test_defs_are_valid_tool_shapes(self, mock_agent):
        for tool in mock_agent.pex._orchestrator_tool_definitions():
            assert tool['description'].strip(), f"{tool['name']} has no description"
            schema = tool['input_schema']
            assert schema['type'] == 'object'
            assert set(schema['required']) <= set(schema['properties'])

    def test_orchestrator_tool_list_composition(self, mock_agent):
        names = [tool['name'] for tool in mock_agent.pex.get_tools_for_orchestrator()]
        for name in _HOT_PATH_TOOLS:
            assert name in names
        for name in ('handle_ambiguity', 'coordinate_context', 'manage_memory'):
            assert name in names
        for name in READ_ONLY_DOMAIN_TOOLS:
            assert name in names, f'allowlisted read-only tool {name} missing'
        assert 'call_flow_stack' not in names  # retired on the orchestrator path
        writes = {'create_post', 'update_post', 'delete_post', 'revise_content', 'release_post'}
        assert not writes & set(names)  # domain writes only via activate_flow

    def test_allowlist_is_decision_16(self):
        assert READ_ONLY_DOMAIN_TOOLS == ('find_posts', 'read_metadata', 'read_section',
                                          'search_notes', 'list_channels', 'channel_status')


class TestOrchestratorDispatch:
    """_dispatch_tool routes the hot-path names onto the Phase 1/2 surfaces."""

    def test_read_state_returns_document(self, mock_agent):
        result = mock_agent.pex._dispatch_tool('read_state', {})
        assert result['_success'] is True
        assert list(result['state']) == ['session', 'user_beliefs', 'grounding',
                                         'flow_stack', 'flags']

    def test_write_state_stacks_and_saves(self, sessions_dir, mock_agent):
        mock_agent.world.open_session('wire-test')
        result = mock_agent.pex._dispatch_tool('write_state',
                                               {'op': 'stackon', 'flow_name': 'outline'})
        assert result['_success'] is True
        assert result['state']['flow_stack'][0]['flow_name'] == 'outline'
        assert (sessions_dir / 'wire-test' / 'state.json').exists()

    def test_write_state_pop_completed_mirrors_live_stack(self, sessions_dir, mock_agent):
        """A write_state pop must also pop the live PEX stack — activate_flow's epilogue
        re-syncs state.flow_stack from it, so a stale Completed live entry would resurrect
        the popped flow on the next dispatch."""
        mock_agent.world.open_session('wire-test')
        pex = mock_agent.pex
        flow = pex.flow_stack.stackon('chat')
        flow.status = 'Completed'
        state = mock_agent.world.current_state()
        state.flow_stack = pex.flow_stack.to_list()
        result = pex._dispatch_tool('write_state', {'op': 'pop_completed'})
        assert result['_success'] is True
        assert result['state']['flow_stack'] == []
        assert pex.flow_stack.to_list() == []  # live stack mirrored — no resurrection

    def test_write_state_bad_op_returns_corrective_error(self, sessions_dir, mock_agent):
        mock_agent.world.open_session('wire-test')
        result = mock_agent.pex._dispatch_tool('write_state', {'op': 'merge'})
        assert result['_success'] is False
        assert 'Unknown write_state op' in result['_message']

    def test_write_state_unknown_slot_returns_corrective_error(self, sessions_dir, mock_agent):
        """LLM-invented slot names (e.g. create's `type` reread as genre) get a corrective
        error naming the valid slots, instead of fill_slot_values dropping them silently."""
        mock_agent.world.open_session('wire-test')
        mock_agent.pex._dispatch_tool('write_state', {'op': 'stackon', 'flow_name': 'outline'})
        result = mock_agent.pex._dispatch_tool(
            'write_state', {'op': 'update_flow', 'fields': {'slots': {'genre': 'tutorial'}}})
        assert result['_success'] is False
        assert result['_error'] == 'invalid_input'
        assert "'source'" in result['_message']  # valid slots are listed for the retry

    def test_scratchpad_tools_route_to_memory(self, mock_agent, tmp_path):
        pex = mock_agent.pex
        pex.scratchpad = SessionScratchpad(pex.config, scratchpad_path=str(tmp_path / 'scratch.jsonl'))
        appended = pex._dispatch_tool('append_to_scratchpad',
                                      {'entry': {'finding': 'intro is weak'}})
        assert appended == {'_success': True, 'size': 1}
        result = pex._dispatch_tool('read_scratchpad', {'writer': 'orchestrator'})
        assert result['entries'] == [{'finding': 'intro is weak', 'writer': 'orchestrator'}]


class _StubPolicy:
    """Happy-path policy stand-in: marks the staged flow and returns a minimal artifact."""

    def __init__(self, flow_stack, status='Completed', thoughts='Drafted the intro.'):
        self.flow_stack = flow_stack
        self.status = status
        self.thoughts = thoughts

    def execute(self, state, context, tools):
        flow = self.flow_stack.get_flow()
        flow.status = self.status
        return TaskArtifact(origin=flow.name(), thoughts=self.thoughts)

    def pop_completion(self):
        """Unmigrated-policy shape: no complete_flow call, activate_flow writes the record."""
        return None


class TestDispatchFlow:
    """activate_flow runs the policy inline and returns the completion record (decision 7)."""

    @pytest.fixture
    def wired(self, sessions_dir, mock_agent, tmp_path):
        pex = mock_agent.pex
        mock_agent.world.open_session('wire-test')
        pex.scratchpad = SessionScratchpad(pex.config, scratchpad_path=str(tmp_path / 'scratch.jsonl'))
        return mock_agent

    def test_completion_record_is_the_tool_result(self, wired):
        pex = wired.pex
        state = wired.world.current_state()
        state.grounding['post'] = 'cafe01'
        pex._policies['Draft'] = _StubPolicy(pex.flow_stack)
        result = pex._dispatch_tool('activate_flow', {'flow_name': 'outline'})
        assert result['_success'] is True
        assert result['status'] == 'Completed'
        assert result['completion'] == {'flow': 'outline', 'summary': 'Drafted the intro.',
                                        'metadata': {}, 'writer': 'outline'}
        assert pex.scratchpad.read(keys=['flow', 'summary']) == [result['completion']]
        # The run is reflected back into the state's flow_stack block, grounding applied.
        assert state.flow_stack[-1]['flow_name'] == 'outline'
        assert state.flow_stack[-1]['status'] == 'Completed'
        assert state.active_post == 'cafe01'

    def test_rehydrates_flow_from_state_file_entry(self, wired):
        pex = wired.pex
        state = wired.world.current_state()
        state.write_state(wired.world.state_file(), 'stackon', flow_name='outline')
        state.write_state(wired.world.state_file(), 'update_flow',
                          slots={'source': [{'post': 'cafe01'}]})
        state.grounding['post'] = 'cafe01'
        captured = {}

        class _CapturingPolicy(_StubPolicy):
            def execute(self, policy_state, context, tools):
                captured['slots'] = self.flow_stack.get_flow().slot_values_dict()
                return super().execute(policy_state, context, tools)

        pex._policies['Draft'] = _CapturingPolicy(pex.flow_stack)
        assert pex.flow_stack.find_by_name('outline') is None  # lives only in the state file
        result = pex._dispatch_tool('activate_flow', {'flow_name': 'outline'})
        assert result['status'] == 'Completed'
        assert captured['slots']['source'][0]['post'] == 'cafe01'

    def test_non_completed_returns_status_and_question(self, wired):
        pex = wired.pex
        pex._policies['Draft'] = _StubPolicy(pex.flow_stack, status='Active',
                                             thoughts='Need a post first.')
        pex.ambiguity.declare('partial', metadata={'missing': 'source', 'entity': 'post'},
                              observation='Which post should I work on?')
        result = pex._dispatch_tool('activate_flow', {'flow_name': 'outline'})
        assert result['_success'] is True
        assert result['status'] == 'Active'
        assert result['question'] == 'Which post should I work on?'
        assert 'completion' not in result

    def test_empty_artifact_fails_validation(self, wired):
        pex = wired.pex
        pex._policies['Draft'] = _StubPolicy(pex.flow_stack, status='Active', thoughts='')
        result = pex._dispatch_tool('activate_flow', {'flow_name': 'outline'})
        assert result['_success'] is False
        assert result['_error'] == 'validation'


class TestPolicyCompletion:
    """BasePolicy.complete_flow / pop_completion — the single completion call under the
    orchestrator substrate (changes.md §8 policies row): status via write_state (so the §6
    grounding validation fires) + the §5.3 completion record, deduped against
    activate_flow's transitional fallback. Plus the grounding-block entity access (§6)."""

    @pytest.fixture
    def wired(self, sessions_dir, mock_agent, tmp_path):
        pex = mock_agent.pex
        mock_agent.world.open_session('completion-test')
        pex.scratchpad = SessionScratchpad(pex.config, scratchpad_path=str(tmp_path / 'scratch.jsonl'))
        return mock_agent

    def _migrated_policy(self, agent, summary, metadata=None):
        """A policy already rewired to the complete_flow contract."""
        from backend.modules.policies.base import BasePolicy
        pex = agent.pex

        class _MigratedPolicy(BasePolicy):
            def execute(self, state, context, tools):
                flow = self.flow_stack.get_flow()
                self.complete_flow(flow, state, summary, metadata=metadata)
                return TaskArtifact(origin=flow.name(), thoughts=summary)

        components = {'engineer': pex.engineer, 'memory': pex.memory, 'config': pex.config,
                      'ambiguity': pex.ambiguity, 'get_tools': pex.get_tools_for_flow,
                      'flow_stack': pex.flow_stack, 'content_service': pex._content_service,
                      'scratchpad': pex.scratchpad, 'state_file': agent.world.state_file}
        return _MigratedPolicy(components)

    def test_complete_flow_writes_record_once(self, wired):
        pex = wired.pex
        state = wired.world.current_state()
        state.grounding['post'] = 'cafe01'
        pex._policies['Draft'] = self._migrated_policy(wired, 'Wrote the intro.',
                                                       metadata={'sec': 'intro'})
        result = pex._dispatch_tool('activate_flow', {'flow_name': 'outline'})
        assert result['_success'] is True
        assert result['completion'] == {'flow': 'outline', 'summary': 'Wrote the intro.',
                                        'metadata': {'sec': 'intro'}, 'writer': 'outline'}
        # The policy's record IS the tool result — no fallback duplicate from activate_flow.
        assert pex.scratchpad.read(keys=['flow', 'summary']) == [result['completion']]
        assert state.flow_stack[-1]['status'] == 'Completed'

    def test_complete_flow_blocks_ungrounded_completion(self, wired):
        pex = wired.pex
        pex._policies['Draft'] = self._migrated_policy(wired, 'Done.')
        result = pex._dispatch_tool('activate_flow', {'flow_name': 'outline'})
        assert result['_success'] is False
        assert 'grounding.post is empty' in result['_message']
        assert pex.scratchpad.read(keys=['flow', 'summary']) == []  # no record written

    def test_grounded_source_ids_continuity(self, wired):
        """Empty entity slot + filled grounding block: the active entity carries over."""
        pex = wired.pex
        state = wired.world.current_state()
        state.grounding['post'] = 'cafe0001'
        flow = pex.flow_stack.stackon('outline')
        policy = pex._policies['Draft']

        def tools(name, params):
            assert name == 'read_metadata'
            return {'_success': True, 'title': 'Cafe', 'status': 'draft', 'section_ids': []}

        post_id, sec_id, error = policy.resolve_source_ids(flow, state, tools)
        assert (post_id, sec_id, error) == ('cafe0001', None, None)
        assert state.active_post == 'cafe0001'  # old-path mirror until cutover


class TestProposeTwoPhase:
    """propose's generate→pick split (mirrors audit). Phase 1 writes 2-3 candidates itself and
    presents a selection WITHOUT completing; phase 2 (the click, with choices populated) fills the
    placeholder gap via revise_content and completes the flow."""

    @pytest.fixture
    def ready(self, sessions_dir, mock_agent, tmp_path, monkeypatch):
        pex = mock_agent.pex
        mock_agent.world.open_session('propose-test')
        pex.scratchpad = SessionScratchpad(pex.config, scratchpad_path=str(tmp_path / 'scratch.jsonl'))
        policy = pex._policies['Revise']
        policy.scratchpad = pex.scratchpad
        mock_agent.world.current_state().grounding['post'] = 'p1'   # grounding gate for complete_flow
        flow = pex.flow_stack.stackon('propose')
        flow.fill_slot_values({'source': [{'post': 'p1', 'sec': 'tradeoffs'}]})
        # Stub the helpers that reach the LLM / content service; the new branching is what we test.
        monkeypatch.setattr(policy, 'resolve_source_ids', lambda f, s, t: ('p1', 'tradeoffs', None))
        monkeypatch.setattr(policy, 'record_snapshot', lambda *a, **k: 'snap1')
        monkeypatch.setattr(policy, '_read_post_content', lambda pid, t: {'post_id': pid})
        monkeypatch.setattr(policy, 'llm_execute',
                            lambda *a, **k: ('1. Alpha option\n2. Beta option\n3. Gamma option', []))
        return mock_agent, policy, flow

    def test_generate_presents_selection_without_completing(self, ready):
        agent, policy, flow = ready
        state, context = agent.world.current_state(), agent.world.context
        artifact = policy.propose_policy(flow, state, context,
            lambda name, params: {'_success': True, 'content': 'Intro. <fill in here> Tail.'})

        selection = [b for b in artifact.blocks if b.block_type == 'selection'][0]
        assert [opt['body'] for opt in selection.data['options']] == \
            ['Alpha option', 'Beta option', 'Gamma option']
        assert selection.data['submit_dax'] == '{39B}'
        assert flow.stage == 'discovery'
        assert flow.status != 'Completed'                          # left active for the pick turn
        assert policy._read_scratch_value('propose')['candidates'][1] == 'Beta option'

    def test_pick_fills_placeholder_and_completes(self, ready):
        agent, policy, flow = ready
        state, context = agent.world.current_state(), agent.world.context
        calls = []
        def tools(name, params):
            calls.append((name, params))
            if name == 'read_section':
                return {'_success': True, 'content': 'Intro. <fill in here> Tail.'}
            return {'_success': True}

        policy.propose_policy(flow, state, context, tools)         # phase 1 — fills the scratchpad
        state.slices['choices'].append(1)                          # the click selects "Beta option"
        policy.propose_policy(flow, state, context, tools)         # phase 2 — inserts the pick

        revise = [params for name, params in calls if name == 'revise_content'][0]
        assert revise['content'] == 'Intro. Beta option Tail.'
        assert revise['sec_id'] == 'tradeoffs'
        assert flow.status == 'Completed'


# ═══════════════════════════════════════════════════════════════════
# Orchestrator system prompt — three tiers, frozen per session (changes.md §7)
# ═══════════════════════════════════════════════════════════════════

from backend.prompts.for_orchestrator import build_orchestrator_prompt


class TestOrchestratorPrompt:
    """Built once per session, byte-stable given the same inputs (Hermes prefix-caching
    pattern); the L2 preferences snapshot and intent taxonomy are baked into the string."""

    @pytest.fixture
    def prompt_inputs(self, minimal_config):
        engineer = PromptEngineer(minimal_config)
        prefs = UserPreferences(minimal_config)
        prefs.store_preference('paragraph_length', 'shorter paragraphs')
        memory = MemoryManager(None, prefs, None)
        return engineer, memory

    def _build(self, prompt_inputs):
        engineer, memory = prompt_inputs
        return build_orchestrator_prompt(engineer, memory, 'conv-42', 'derek', '2026-06-11')

    def test_byte_stable_across_builds(self, prompt_inputs):
        assert self._build(prompt_inputs) == self._build(prompt_inputs)

    def test_preferences_snapshot_appears(self, prompt_inputs):
        prompt = self._build(prompt_inputs)
        assert '- Remember, the user wants shorter paragraphs.' in prompt
        # Snapshot semantics: a write AFTER the build only enters the next session's prompt.
        prompt_inputs[1].preferences.store_preference('tone', 'casual')
        assert 'casual' not in prompt

    def test_taxonomy_names_all_seven_intents(self, prompt_inputs):
        prompt = self._build(prompt_inputs)
        for intent in ('Research', 'Draft', 'Revise', 'Publish', 'Converse', 'Plan', 'Clarify'):
            assert f'- **{intent}' in prompt, f'intent {intent} missing from taxonomy'

    def test_three_tier_sections_present(self, prompt_inputs):
        prompt = self._build(prompt_inputs)
        for tag in ('persona', 'intents', 'tool_policy', 'workflow', 'flow_catalog',
                    'outline_levels', 'preferences', 'session'):
            assert f'<{tag}>' in prompt and f'</{tag}>' in prompt
        assert 'Session: conversation_id=conv-42 | user=derek | date=2026-06-11' in prompt
        assert '10. **Release and syndicate**' in prompt  # README workflow ported
        assert f'## Flow Catalog ({len(FLOW_CATALOG)} flows)' in prompt


# ═══════════════════════════════════════════════════════════════════
# Orchestrator loop v1 (changes.md §3, decisions 3, 6, 13)
# ═══════════════════════════════════════════════════════════════════

from types import SimpleNamespace

from schemas.config import load_config
from backend.agent import Agent, _FALLBACK_MESSAGE, _NUDGE_MESSAGE, _WRAP_UP_MESSAGE


def _text_block(text):
    return SimpleNamespace(type='text', text=text)


def _tool_block(name, tool_input, block_id='toolu_01'):
    return SimpleNamespace(type='tool_use', name=name, input=tool_input, id=block_id)


def _response(*blocks):
    return SimpleNamespace(content=list(blocks), stop_reason='end_turn', usage=None)


def _script(agent, responses):
    """Replace the loop's LLM call with a scripted response queue."""
    queue = list(responses)
    agent.engineer._call_claude = (
        lambda system, messages, model_id, *, tools=None, max_tokens=4096: queue.pop(0))
    return queue


@pytest.fixture
def orch_agent(sessions_dir, monkeypatch):
    """Agent with a tmp sessions root and scripted LLM calls. NLU.understand is stubbed to a
    no-op so the Flow gate stays hermetic — these tests exercise PEX.execute (the acting loop),
    not ensemble detection; the belief stays at its session defaults."""
    monkeypatch.setattr('backend.agent.load_config', lambda: load_config(
        overrides={'debug': True}))
    agent = Agent(username='test_user')
    agent.nlu.understand = lambda *args, **kwargs: None
    yield agent
    agent.close()


class TestOrchestratorLoop:
    """The bounded loop: termination signal, message-list bookkeeping, §3.3 guardrails."""

    def test_plain_text_ends_turn_and_is_the_utterance(self, orch_agent):
        _script(orch_agent, [_response(_text_block('You have three posts in progress.'))])
        result = orch_agent.take_turn('what posts do I have?')
        assert result['message'] == 'You have three posts in progress.'
        assert sorted(result) == ['actions', 'artifact', 'message']
        messages = orch_agent.world.context.messages
        assert messages[0] == {'role': 'user', 'content': 'what posts do I have?'}
        assert messages[1] == {'role': 'assistant',
                               'content': 'You have three posts in progress.'}

    def test_tool_round_dispatches_and_appends_results(self, orch_agent):
        _script(orch_agent, [_response(_tool_block('read_state', {})),
                             _response(_text_block('All caught up.'))])
        result = orch_agent.take_turn('where were we?')
        assert result['message'] == 'All caught up.'
        messages = orch_agent.world.context.messages
        assert [msg['role'] for msg in messages] == ['user', 'assistant', 'user', 'assistant']
        tool_use = messages[1]['content'][0]
        assert tool_use['type'] == 'tool_use' and tool_use['name'] == 'read_state'
        tool_result = messages[2]['content'][0]
        assert tool_result['tool_use_id'] == 'toolu_01'
        assert json.loads(tool_result['content'])['_success'] is True

    def test_unknown_tool_returns_corrective_error(self, orch_agent):
        _script(orch_agent, [_response(_tool_block('make_coffee', {})),
                             _response(_text_block('Sorry, no coffee.'))])
        result = orch_agent.take_turn('brew something')
        assert result['message'] == 'Sorry, no coffee.'
        tool_result = json.loads(orch_agent.world.context.messages[2]['content'][0]['content'])
        assert tool_result['_success'] is False
        assert 'Unknown tool' in tool_result['_message']

    def test_identical_consecutive_call_is_deduped(self, orch_agent):
        _script(orch_agent, [_response(_tool_block('read_state', {}, block_id='t1')),
                             _response(_tool_block('read_state', {}, block_id='t2')),
                             _response(_text_block('done'))])
        orch_agent.take_turn('check state twice')
        second = json.loads(orch_agent.world.context.messages[4]['content'][0]['content'])
        assert second['_error'] == 'duplicate_call'

    def test_identical_retry_after_error_is_dispatched(self, orch_agent):
        """Dedupe only fires after a SUCCESSFUL identical call — retrying the same call
        after a transient tool error is legitimate recovery, not a loop."""
        bad_call = _tool_block('write_state', {'op': 'bogus'}, block_id='t1')
        _script(orch_agent, [_response(bad_call),
                             _response(_tool_block('write_state', {'op': 'bogus'}, block_id='t2')),
                             _response(_text_block('gave up'))])
        orch_agent.take_turn('do the thing')
        second = json.loads(orch_agent.world.context.messages[4]['content'][0]['content'])
        assert second['_error'] != 'duplicate_call'  # re-dispatched, not skipped

    def test_thinking_only_gets_one_nudge_then_text(self, orch_agent):
        _script(orch_agent, [_response(), _response(_text_block('after the nudge'))])
        result = orch_agent.take_turn('hello?')
        assert result['message'] == 'after the nudge'
        assert orch_agent.world.context.messages[1] == {'role': 'user',
                                                        'content': _NUDGE_MESSAGE}

    def test_thinking_only_twice_falls_back(self, orch_agent):
        _script(orch_agent, [_response(), _response()])
        result = orch_agent.take_turn('hello?')
        assert result['message'] == _FALLBACK_MESSAGE
        assert orch_agent.world.context.messages[-1]['content'] == _FALLBACK_MESSAGE

    def test_consecutive_failures_cap_breaks_to_wrap_up(self, orch_agent):
        queue = _script(orch_agent, [_response(_tool_block('bogus_one', {})),
                                     _response(_tool_block('bogus_two', {})),
                                     _response(_tool_block('bogus_three', {})),
                                     _response(_text_block('I could not find that tool.'))])
        result = orch_agent.take_turn('try something weird')
        assert result['message'] == 'I could not find that tool.'
        assert queue == []  # three rounds + the forced no-tools wrap-up, nothing more
        assert orch_agent.world.context.messages[-2] == {'role': 'user',
                                                         'content': _WRAP_UP_MESSAGE}

    def test_wrap_up_with_no_text_falls_back(self, orch_agent):
        responses = [_response(_tool_block(f'bogus_{idx}', {})) for idx in range(3)]
        _script(orch_agent, responses + [_response()])
        result = orch_agent.take_turn('try something weird')
        assert result['message'] == _FALLBACK_MESSAGE

    def test_agent_turn_recorded_in_context(self, orch_agent):
        _script(orch_agent, [_response(_text_block('Recorded.'))])
        orch_agent.take_turn('say something')
        turns = orch_agent.world.context.full_conversation(keep_system=False)
        assert turns[-1] == 'Agent: Recorded.'

    def test_epilogue_persists_session_files(self, orch_agent, sessions_dir):
        _script(orch_agent, [_response(_text_block('Saved.'))])
        orch_agent.take_turn('persist please')
        session = sessions_dir / orch_agent.world.conversation_id
        assert json.loads((session / 'state.json').read_text())['session']['turn_count'] == 1
        lines = (session / 'messages.jsonl').read_text().splitlines()
        assert len(lines) == 2  # user message + assistant text, mirrored to disk


class TestOrchestratorClickBypass:
    """Decision 13: pure clicks never reach the loop; action+text injects the flow."""

    def test_pure_click_skips_the_loop(self, orch_agent):
        def _boom(*args, **kwargs):
            raise AssertionError('pure click must not call the LLM loop')
        orch_agent.engineer._call_claude = _boom
        orch_agent.pex._policies['Converse'] = _StubPolicy(orch_agent.pex.flow_stack,
                                                           thoughts='Hi! What shall we write?')
        result = orch_agent.take_turn('', dax='{000}', payload={})
        assert result['message'] == 'Hi! What shall we write?'
        messages = orch_agent.world.context.messages
        assert messages[0]['content'].startswith('[click] dax={000} flow=chat')
        assert messages[1] == {'role': 'assistant', 'content': 'Hi! What shall we write?'}

    def test_action_with_text_runs_loop_with_flow_injected(self, orch_agent):
        _script(orch_agent, [_response(_text_block('Building on your pick.'))])
        result = orch_agent.take_turn('make it punchier', dax='{000}', payload={})
        assert result['message'] == 'Building on your pick.'
        injected = orch_agent.world.context.messages[0]['content']
        assert injected.startswith("[action] This turn arrived with a resolved flow: 'chat'")
        assert injected.endswith('make it punchier')

    # test_flag_off_routes_to_old_path removed — the legacy _take_turn path and the
    # orchestrator feature flag are gone; take_turn always runs the orchestrator loop.


class TestTurnCheckpoint:
    """PEX records a backward-looking 'System' checkpoint turn at the end of every turn:
    which flows completed, which flow is still active, and the grounded entity."""

    @staticmethod
    def _checkpoints(agent):
        return [turn for turn in agent.world.context.full_conversation(keep_system=True)
                if turn.startswith('System:') and '[checkpoint]' in turn]

    def test_plain_turn_records_checkpoint(self, orch_agent):
        _script(orch_agent, [_response(_text_block('All set.'))])
        orch_agent.take_turn('anything new?')
        checkpoints = self._checkpoints(orch_agent)
        assert checkpoints, 'no System checkpoint turn was recorded'
        assert 'completed: none' in checkpoints[-1] and 'active: none' in checkpoints[-1]

    def test_checkpoint_notes_completed_flow(self, orch_agent):
        orch_agent.pex._policies['Converse'] = _StubPolicy(orch_agent.pex.flow_stack,
                                                           thoughts='Hi there.')
        orch_agent.take_turn('', dax='{000}', payload={})  # click → completes the chat flow
        assert 'completed: chat' in self._checkpoints(orch_agent)[-1]


# ═══════════════════════════════════════════════════════════════════
# Context compression — the Hermes compactor port (changes.md §5.6, decision 9)
# ═══════════════════════════════════════════════════════════════════

from backend.prompts.for_compressor import SUMMARY_PREFIX


def _transcript(turns:int) -> list[dict]:
    """`turns` orchestrator rounds, 4 messages each: user utterance, assistant tool_use,
    paired tool results, assistant wrap-up text."""
    messages = []
    for idx in range(turns):
        messages.append({'role': 'user', 'content': f'user turn {idx}: ' + 'x' * 80})
        messages.append({'role': 'assistant', 'content': [
            {'type': 'text', 'text': f'working on {idx}'},
            {'type': 'tool_use', 'id': f'toolu_{idx}', 'name': 'read_state',
             'input': {'turn': idx}}]})
        messages.append({'role': 'user', 'content': [
            {'type': 'tool_result', 'tool_use_id': f'toolu_{idx}',
             'content': json.dumps({'_success': True, 'filler': 'y' * 300})}]})
        messages.append({'role': 'assistant', 'content': f'done with turn {idx}'})
    return messages


def _stub_summarizer(record:list):
    """Mock auxiliary summarizer: records its inputs, returns a numbered summary."""
    def summarize(middle, previous_summary, budget):
        record.append({'middle': list(middle), 'previous': previous_summary, 'budget': budget})
        return f'summary #{len(record)}'
    return summarize


class TestCompression:
    """Head/tail protection, tool-pair integrity, handoff shape, pruning placeholder, and
    messages.jsonl consistency — all with a mocked summarizer (no LLM)."""

    @pytest.fixture
    def loaded(self, minimal_config, tmp_path):
        coordinator = ContextCoordinator(minimal_config)
        coordinator.attach_messages(tmp_path / 'messages.jsonl')
        for message in _transcript(10):  # 40 messages
            coordinator.append_message(message)
        return coordinator

    def test_too_short_list_is_not_compacted(self, minimal_config):
        coordinator = ContextCoordinator(minimal_config)
        for message in _transcript(2):  # 8 messages <= head(3) + tail(20) + 1
            coordinator.append_message(message)
        assert coordinator.compress_messages(_stub_summarizer([]), protect_tail=20) is False
        assert coordinator.previous_summary is None

    def test_head_and_tail_are_protected(self, loaded):
        before = [json.dumps(message, default=str) for message in loaded.messages]
        assert loaded.compress_messages(_stub_summarizer([]), protect_tail=20) is True
        after = loaded.messages
        assert len(after) == 3 + 1 + 20  # head + one handoff + tail
        assert [json.dumps(msg, default=str) for msg in after[:2]] == before[:2]
        assert [json.dumps(msg, default=str) for msg in after[-20:]] == before[20:]

    def test_handoff_message_shape(self, loaded):
        loaded.compress_messages(_stub_summarizer([]), protect_tail=20)
        handoff = loaded.messages[3]
        assert handoff['role'] == 'user'
        assert handoff['content'].startswith(SUMMARY_PREFIX)
        assert 'summary #1' in handoff['content']
        assert handoff['content'].rstrip().endswith(
            'respond to the message below, not the summary above ---')

    def test_tail_cut_never_splits_a_tool_pair(self, loaded):
        # protect_tail=18 puts the raw cut on turn 5's tool results; alignment pulls the cut
        # back so the parent assistant tool_use travels into the tail with its results.
        assert loaded.compress_messages(_stub_summarizer([]), protect_tail=18) is True
        handoff_idx = next(idx for idx, msg in enumerate(loaded.messages)
                           if isinstance(msg['content'], str)
                           and msg['content'].startswith(SUMMARY_PREFIX))
        first_tail = loaded.messages[handoff_idx + 1]
        assert first_tail['role'] == 'assistant'
        assert first_tail['content'][1]['type'] == 'tool_use'
        result_block = loaded.messages[handoff_idx + 2]['content'][0]
        assert result_block['tool_use_id'] == first_tail['content'][1]['id']

    def test_summarizer_sees_only_the_middle(self, loaded):
        record = []
        loaded.compress_messages(_stub_summarizer(record), protect_tail=20)
        middle = record[0]['middle']
        assert len(middle) == 17  # messages 3..19 — nothing from the head or tail
        assert middle[0]['content'] == 'done with turn 0'
        assert middle[-1]['content'] == 'done with turn 4'
        assert record[0]['budget'] == 2000  # small middle clamps to the Hermes floor

    def test_old_tool_results_pruned_tail_results_kept(self, loaded):
        loaded.compress_messages(_stub_summarizer([]), protect_tail=20)
        head_result = loaded.messages[2]['content'][0]['content']
        assert head_result == '[Old tool output cleared to save context space]'
        tail_result = loaded.messages[-2]['content'][0]['content']
        assert 'filler' in tail_result  # inside the protected tail — untouched

    def test_messages_jsonl_matches_memory_after_compression(self, loaded, minimal_config,
                                                             tmp_path):
        loaded.compress_messages(_stub_summarizer([]), protect_tail=20)
        reopened = ContextCoordinator(minimal_config)
        reopened.attach_messages(tmp_path / 'messages.jsonl')
        assert reopened.messages == loaded.messages

    def test_checkpoint_records_the_compression_event(self, loaded):
        loaded.compress_messages(_stub_summarizer([]), protect_tail=20, prompt_tokens=70000)
        checkpoint = loaded.get_checkpoint('compression')
        assert checkpoint['data'] == {'messages_before': 40, 'messages_after': 24,
                                      'pruned_tool_results': 5, 'prompt_tokens': 70000}

    def test_second_compaction_updates_the_previous_summary(self, loaded):
        record = []
        loaded.compress_messages(_stub_summarizer(record), protect_tail=20)
        for message in _transcript(5):  # the conversation keeps going
            loaded.append_message(message)
        assert loaded.compress_messages(_stub_summarizer(record), protect_tail=20) is True
        assert record[0]['previous'] is None
        assert record[1]['previous'] == 'summary #1'
        # the old handoff sits in the window and is never re-summarized as a turn
        assert all(not (isinstance(msg['content'], str)
                        and msg['content'].startswith(SUMMARY_PREFIX))
                   for msg in record[1]['middle'])

    def test_rehydrated_session_seeds_previous_summary_from_handoff(self, loaded,
                                                                    minimal_config, tmp_path):
        loaded.compress_messages(_stub_summarizer([]), protect_tail=20)
        reopened = ContextCoordinator(minimal_config)  # fresh process — no in-memory summary
        reopened.attach_messages(tmp_path / 'messages.jsonl')
        for message in _transcript(5):
            reopened.append_message(message)
        record = []
        assert reopened.compress_messages(_stub_summarizer(record), protect_tail=20) is True
        assert record[0]['previous'] == 'summary #1'


# ═══════════════════════════════════════════════════════════════════
# Eval system — P1 completion gate + scorer (step_1_evals.md)
# Red-green spine: the folded-baseline gate logic and the completion detector, both pure (no LLM).
# ═══════════════════════════════════════════════════════════════════

from utils.evals.gates import gate, grade


def _metric(expected_fail, value=None, target=0.90):
    """A folded baseline record (the P0-1 decision): intent + measurement in one dict."""
    return {'target': target, 'direction': 'higher', 'expected_fail': expected_fail, 'value': value}


class TestCompletionGate:
    """The folded-baseline red-green gate (eval/gates.py): xfail keeps CI green while a feature is
    unbuilt; once flipped on, an under-target value is red and a met-target value is green."""

    def test_xfail_keeps_gate_green(self):
        assert gate({'completion_rate': 0.0}, {'completion_rate': _metric(True)}) == 0

    def test_flip_on_under_target_is_red(self):
        assert gate({'completion_rate': 0.40}, {'completion_rate': _metric(False)}) == 1

    def test_flip_on_meets_target_is_green(self):
        assert gate({'completion_rate': 0.95}, {'completion_rate': _metric(False)}) == 0

    def test_no_target_no_baseline_is_red(self):
        record = {'direction': 'higher', 'expected_fail': False, 'value': None}
        assert grade('completion_rate', 0.95, record).failed is True  # nothing to assert against

    def test_regression_below_baseline_is_red(self):
        record = {'direction': 'higher', 'expected_fail': False, 'value': 0.90, 'max_drop': 0.02}
        assert grade('completion_rate', 0.80, record).failed is True   # dropped past the tolerance

    def test_within_tolerance_of_baseline_is_green(self):
        record = {'direction': 'higher', 'expected_fail': False, 'value': 0.90, 'max_drop': 0.02}
        assert grade('completion_rate', 0.89, record).failed is False


class TestCompressionTrigger:
    """The post-hook trigger (changes.md §5.6): real usage off response.usage against the
    configured threshold; the protected tail size rides in from config."""

    @staticmethod
    def _usage_response(text, prompt_tokens, cached=0):
        response = _response(_text_block(text))
        response.usage = SimpleNamespace(input_tokens=prompt_tokens,
                                         cache_creation_input_tokens=0,
                                         cache_read_input_tokens=cached)
        return response

    def test_usage_recorded_including_cache_tokens(self, orch_agent):
        _script(orch_agent, [self._usage_response('hi', 1500, cached=4500)])
        orch_agent.take_turn('hello')
        assert orch_agent.pex.last_prompt_tokens == 6000

    def test_below_threshold_never_compacts(self, orch_agent, monkeypatch):
        calls = []
        monkeypatch.setattr(orch_agent.world.context, 'compress_messages',
                            lambda *args: calls.append(args) or True)
        _script(orch_agent, [self._usage_response('small turn', 63999)])
        orch_agent.take_turn('hello')
        assert calls == []

    def test_at_threshold_compacts_with_config_tail(self, orch_agent, monkeypatch):
        calls = []
        monkeypatch.setattr(orch_agent.world.context, 'compress_messages',
                            lambda *args: calls.append(args) or True)
        _script(orch_agent, [self._usage_response('big turn', 64000)])
        orch_agent.take_turn('hello')
        summarize, protect_tail, prompt_tokens = calls[0]
        assert summarize == orch_agent._summarize_middle
        assert protect_tail == 20  # schemas/tools.yaml compression.protect_tail
        assert prompt_tokens == 64000

    def test_summarizer_failure_does_not_eat_the_reply(self, orch_agent, monkeypatch):
        def boom(*args):
            raise RuntimeError('aux model down')
        monkeypatch.setattr(orch_agent.world.context, 'compress_messages', boom)
        _script(orch_agent, [self._usage_response('still replies', 200000)])
        assert orch_agent.take_turn('hello')['message'] == 'still replies'
