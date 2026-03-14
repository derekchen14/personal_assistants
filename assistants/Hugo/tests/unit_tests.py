"""Unit tests — pure code logic, mocked LLM, no API keys needed.

Covers:
  - Ensemble voting: _tally_votes, _detect_flow (mocked)
  - Model resolution: _resolve_model
  - Provider dispatch: call() routing
  - Ensemble config validation
  - NLU react() path: gold DAX slot parsing, utterance slot filling
  - Edge cases: fill_slot_values, DAX code resolution
"""

import sys
from pathlib import Path
from types import MappingProxyType
from unittest.mock import MagicMock, patch

import pytest

_HUGO_ROOT = Path(__file__).resolve().parent.parent
if str(_HUGO_ROOT) not in sys.path:
    sys.path.insert(0, str(_HUGO_ROOT))

from backend.modules.nlu import NLU, _ENSEMBLE_VOTERS
from backend.components.prompt_engineer import PromptEngineer
from backend.components.context_coordinator import Turn
from backend.components.flow_stack import flow_classes
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
    ambiguity = MagicMock()
    ambiguity.needs_clarification.return_value = False
    engineer = PromptEngineer(minimal_config)
    world = MagicMock()
    world.context.compile_history.return_value = ''
    world.current_state.return_value = None
    world.flow_stack.find_by_name.return_value = None
    world.flow_stack.depth = 0
    return NLU(minimal_config, ambiguity, engineer, world)


def _make_context(turn_type='action'):
    ctx = MagicMock()
    ctx.last_user_turn = Turn('User', '', turn_type=turn_type, turn_id=0)
    return ctx


# ═══════════════════════════════════════════════════════════════════
# Model resolution
# ═══════════════════════════════════════════════════════════════════

class TestResolveModel:
    def test_claude_sonnet(self, engineer):
        assert engineer._resolve_model('claude', 'sonnet') == 'claude-sonnet-4-5-20250929'

    def test_claude_haiku(self, engineer):
        assert engineer._resolve_model('claude', 'haiku') == 'claude-haiku-4-5-20251001'

    def test_gemini_flash(self, engineer):
        assert engineer._resolve_model('gemini', 'flash') == 'gemini-2.0-flash'

    def test_unknown_raises(self, engineer):
        with pytest.raises(ValueError):
            engineer._resolve_model('unknown', 'model')


# ═══════════════════════════════════════════════════════════════════
# Provider dispatch
# ═══════════════════════════════════════════════════════════════════

class TestCallDispatch:
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
                family='claude', model='haiku',
            )
        assert result == '{"flow_name": "chat"}'

    def test_gemini_dispatch(self, engineer):
        with patch.object(engineer, '_call_gemini', return_value='{"flow_name": "chat"}'):
            result = engineer.call(
                [{'role': 'user', 'content': 'hi'}],
                system='test', task='detect_flow',
                family='gemini', model='flash',
            )
        assert result == '{"flow_name": "chat"}'


# ═══════════════════════════════════════════════════════════════════
# Ensemble voting: _tally_votes
# ═══════════════════════════════════════════════════════════════════

class TestTallyVotes:
    def test_unanimous_three_voters(self, nlu):
        votes = [
            {'flow_name': 'chat', '_model': 'haiku', '_weight': 0.20},
            {'flow_name': 'chat', '_model': 'sonnet', '_weight': 0.45},
            {'flow_name': 'chat', '_model': 'gemini_flash', '_weight': 0.35},
        ]
        result = nlu._tally_votes(votes)
        assert result['flow_name'] == 'chat'
        assert result['confidence'] == pytest.approx(1.0)

    def test_two_agree_one_dissents(self, nlu):
        votes = [
            {'flow_name': 'chat', '_model': 'haiku', '_weight': 0.20},
            {'flow_name': 'brainstorm', '_model': 'sonnet', '_weight': 0.45},
            {'flow_name': 'brainstorm', '_model': 'gemini_flash', '_weight': 0.35},
        ]
        result = nlu._tally_votes(votes)
        assert result['flow_name'] == 'brainstorm'
        assert result['confidence'] == pytest.approx(0.80)

    def test_sonnet_wins_alone(self, nlu):
        votes = [
            {'flow_name': 'chat', '_model': 'haiku', '_weight': 0.20},
            {'flow_name': 'outline', '_model': 'sonnet', '_weight': 0.45},
            {'flow_name': 'chat', '_model': 'gemini_flash', '_weight': 0.35},
        ]
        result = nlu._tally_votes(votes)
        assert result['flow_name'] == 'chat'
        assert result['confidence'] == pytest.approx(0.55)

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

    def test_single_voter_fallback(self, nlu):
        votes = [
            {'flow_name': 'brainstorm', '_model': 'sonnet', '_weight': 0.45},
        ]
        result = nlu._tally_votes(votes)
        assert result['flow_name'] == 'brainstorm'
        assert result['confidence'] == pytest.approx(1.0)

    def test_graceful_two_voter_degradation(self, nlu):
        votes = [
            {'flow_name': 'chat', '_model': 'haiku', '_weight': 0.20},
            {'flow_name': 'chat', '_model': 'sonnet', '_weight': 0.45},
        ]
        result = nlu._tally_votes(votes)
        assert result['flow_name'] == 'chat'
        assert result['confidence'] == pytest.approx(1.0)


# ═══════════════════════════════════════════════════════════════════
# Ensemble voting: _detect_flow (mocked LLM)
# ═══════════════════════════════════════════════════════════════════

class TestDetectFlow:
    def test_all_voters_agree(self, nlu):
        call_count = {'n': 0}

        def mock_call(messages, *, system=None, task='skill',
                      family='claude', model='sonnet', max_tokens=4096):
            call_count['n'] += 1
            return '{"flow_name": "chat", "confidence": 0.9}'

        with patch.object(nlu.engineer, 'call', side_effect=mock_call):
            with patch.object(nlu.engineer, 'build_flow_prompt',
                              return_value=('sys', [{'role': 'user', 'content': 'hi'}])):
                result = nlu._detect_flow('hello')

        assert call_count['n'] == 3
        assert result['flow_name'] == 'chat'
        assert result['confidence'] == pytest.approx(1.0)

    def test_one_voter_fails(self, nlu):
        calls = {'n': 0}

        def mock_call(messages, *, system=None, task='skill',
                      family='claude', model='sonnet', max_tokens=4096):
            calls['n'] += 1
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
# Ensemble config validation
# ═══════════════════════════════════════════════════════════════════

class TestEnsembleConfig:
    def test_weights_sum_to_one(self):
        total = sum(v['weight'] for v in _ENSEMBLE_VOTERS)
        assert total == pytest.approx(1.0)

    def test_three_voters(self):
        assert len(_ENSEMBLE_VOTERS) == 3

    def test_unique_labels(self):
        labels = [v['label'] for v in _ENSEMBLE_VOTERS]
        assert len(labels) == len(set(labels))

    def test_voters_have_family_and_model(self):
        for v in _ENSEMBLE_VOTERS:
            assert 'family' in v
            assert 'model' in v


# ═══════════════════════════════════════════════════════════════════
# NLU react(): action turn slot parsing
# ═══════════════════════════════════════════════════════════════════

class TestReactActionTurn:
    def test_create_draft_action(self, nlu):
        ctx = _make_context('action')
        state = nlu.react('type=draft', '{05A}', ctx)
        assert state.flow_name == 'create'
        assert state.confidence == 1.0

    def test_create_note_action(self, nlu):
        ctx = _make_context('action')
        state = nlu.react('type=note', '{05A}', ctx)
        assert state.flow_name == 'create'
        assert state.confidence == 1.0

    def test_view_post_action(self, nlu):
        ctx = _make_context('action')
        state = nlu.react('source=post_abc123', '{1AD}', ctx)
        assert state.flow_name == 'view'
        assert state.confidence == 1.0


class TestReactMultiSlot:
    def test_two_slots_comma_separated(self, nlu):
        ctx = _make_context('action')
        state = nlu.react('type=draft,topic=SEO tips', '{05A}', ctx)
        assert state.flow_name == 'create'
        assert state.confidence == 1.0

    def test_slot_values_parsed_correctly(self, nlu):
        ctx = _make_context('action')
        real_flow = flow_classes['create']()
        nlu.flow_stack.find_by_name.return_value = None
        nlu.flow_stack.push.return_value = real_flow
        nlu.react('type=draft,topic=SEO tips', '{05A}', ctx)
        slot_vals = real_flow.slot_values_dict()
        assert slot_vals.get('type') == 'draft'
        assert slot_vals.get('topic') == 'SEO tips'


# ═══════════════════════════════════════════════════════════════════
# NLU react(): utterance turn (LLM slot filling, mocked)
# ═══════════════════════════════════════════════════════════════════

class TestReactUtteranceTurn:
    def test_utterance_calls_fill_slots(self, nlu):
        ctx = _make_context('utterance')
        with patch.object(nlu, '_fill_slots', return_value={'topic': 'SEO'}) as mock_fill:
            state = nlu.react('write about SEO', '{05A}', ctx)
        mock_fill.assert_called_once_with('write about SEO', 'create')
        assert state.flow_name == 'create'
        assert state.confidence == 0.99

    def test_utterance_no_turn_falls_to_fill(self, nlu):
        ctx = MagicMock()
        ctx.last_user_turn = None
        with patch.object(nlu, '_fill_slots', return_value={}) as mock_fill:
            state = nlu.react('hello', '{000}', ctx)
        mock_fill.assert_called_once()
        assert state.confidence == 0.99


# ═══════════════════════════════════════════════════════════════════
# Edge cases
# ═══════════════════════════════════════════════════════════════════

class TestReactEdgeCases:
    def test_flow_receives_fill_slot_values(self, nlu):
        ctx = _make_context('action')
        flow = nlu._push_or_get('create')
        spy = MagicMock(wraps=flow.fill_slot_values)
        flow.fill_slot_values = spy
        nlu.react('type=note', '{05A}', ctx)
        spy.assert_called_once_with({'type': 'note'})

    def test_all_action_dax_codes_resolve(self):
        from utils.helper import dax2flow
        for flow_name, cat in FLOW_CATALOG.items():
            dax = cat['dax']
            resolved = dax2flow(dax)
            assert resolved == flow_name, \
                f'dax2flow({dax!r}) returned {resolved!r}, expected {flow_name!r}'
