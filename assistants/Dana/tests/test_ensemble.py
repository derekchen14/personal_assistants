"""Unit tests for the cross-model ensemble voting system.

Tests cover:
  - _tally_votes weighted aggregation
  - _detect_flow with mocked call_text
  - PromptEngineer._get_provider routing
  - PromptEngineer.call_text provider dispatch
"""

import sys
from pathlib import Path
from types import MappingProxyType
from unittest.mock import MagicMock, patch

import pytest

_DANA_ROOT = Path(__file__).resolve().parent.parent
if str(_DANA_ROOT) not in sys.path:
    sys.path.insert(0, str(_DANA_ROOT))

from backend.modules.nlu import NLU, _ENSEMBLE_VOTERS
from backend.components.prompt_engineer import PromptEngineer
from schemas.ontology import FLOW_CATALOG


# -- Fixtures ------------------------------------------------------------------

@pytest.fixture
def minimal_config():
    return MappingProxyType({
        'models': {
            'default': {
                'provider': 'anthropic',
                'model_id': 'claude-sonnet-4-5-20250929',
                'temperature': 0.0,
            },
            'overrides': {
                'nlu_vote_haiku': {
                    'provider': 'anthropic',
                    'model_id': 'claude-haiku-4-5-20251001',
                },
                'nlu_vote_sonnet': {
                    'provider': 'anthropic',
                    'model_id': 'claude-sonnet-4-5-20250929',
                },
                'nlu_vote_gemini': {
                    'provider': 'google',
                    'model_id': 'gemini-2.0-flash',
                },
            },
        },
        'resilience': {},
    })


@pytest.fixture
def engineer(minimal_config):
    return PromptEngineer(minimal_config)


@pytest.fixture
def nlu(minimal_config):
    ambiguity = MagicMock()
    engineer = PromptEngineer(minimal_config)
    world = MagicMock()
    world.context.compile_history.return_value = []
    return NLU(minimal_config, ambiguity, engineer, world)


# -- _get_provider tests -------------------------------------------------------

class TestGetProvider:
    def test_anthropic_default(self, engineer):
        assert engineer._get_provider('default') == 'anthropic'

    def test_override_anthropic(self, engineer):
        assert engineer._get_provider('nlu_vote_haiku') == 'anthropic'

    def test_override_google(self, engineer):
        assert engineer._get_provider('nlu_vote_gemini') == 'google'

    def test_unknown_falls_back(self, engineer):
        assert engineer._get_provider('unknown_site') == 'anthropic'


# -- call_text dispatch tests --------------------------------------------------

class TestCallText:
    def test_anthropic_dispatch(self, engineer):
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.type = 'text'
        mock_block.text = '{"flow_name": "chat"}'
        mock_response.content = [mock_block]

        with patch.object(engineer, 'call', return_value=mock_response):
            result = engineer.call_text(
                system='test', messages=[{'role': 'user', 'content': 'hi'}],
                call_site='nlu_vote_haiku',
            )
        assert result == '{"flow_name": "chat"}'

    def test_google_dispatch(self, engineer):
        with patch.object(engineer, '_call_gemini', return_value='{"flow_name": "chat"}'):
            result = engineer.call_text(
                system='test', messages=[{'role': 'user', 'content': 'hi'}],
                call_site='nlu_vote_gemini',
            )
        assert result == '{"flow_name": "chat"}'


# -- _tally_votes tests --------------------------------------------------------

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
            {'flow_name': 'query', '_model': 'sonnet', '_weight': 0.45},
            {'flow_name': 'query', '_model': 'gemini_flash', '_weight': 0.35},
        ]
        result = nlu._tally_votes(votes)
        assert result['flow_name'] == 'query'
        assert result['confidence'] == pytest.approx(0.80)

    def test_sonnet_wins_alone(self, nlu):
        votes = [
            {'flow_name': 'chat', '_model': 'haiku', '_weight': 0.20},
            {'flow_name': 'schema', '_model': 'sonnet', '_weight': 0.45},
            {'flow_name': 'chat', '_model': 'gemini_flash', '_weight': 0.35},
        ]
        result = nlu._tally_votes(votes)
        assert result['flow_name'] == 'chat'
        assert result['confidence'] == pytest.approx(0.55)

    def test_slots_from_heaviest_voter(self, nlu):
        votes = [
            {
                'flow_name': 'query', '_model': 'haiku', '_weight': 0.20,
                'slots': {'dataset': 'haiku_ds'},
            },
            {
                'flow_name': 'query', '_model': 'sonnet', '_weight': 0.45,
                'slots': {'dataset': 'sonnet_ds'},
            },
        ]
        result = nlu._tally_votes(votes)
        assert result['flow_name'] == 'query'
        assert result['slots'] == {'dataset': 'sonnet_ds'}

    def test_single_voter_fallback(self, nlu):
        votes = [
            {'flow_name': 'filter', '_model': 'sonnet', '_weight': 0.45},
        ]
        result = nlu._tally_votes(votes)
        assert result['flow_name'] == 'filter'
        assert result['confidence'] == pytest.approx(1.0)

    def test_graceful_two_voter_degradation(self, nlu):
        votes = [
            {'flow_name': 'chat', '_model': 'haiku', '_weight': 0.20},
            {'flow_name': 'chat', '_model': 'sonnet', '_weight': 0.45},
        ]
        result = nlu._tally_votes(votes)
        assert result['flow_name'] == 'chat'
        assert result['confidence'] == pytest.approx(1.0)


# -- _detect_flow integration tests (mocked LLM) ------------------------------

class TestDetectFlow:
    def test_all_voters_agree(self, nlu):
        call_count = {'n': 0}

        def mock_call_text(system, messages, call_site, max_tokens=512):
            call_count['n'] += 1
            return '{"flow_name": "chat", "confidence": 0.9}'

        with patch.object(nlu.engineer, 'call_text', side_effect=mock_call_text):
            with patch.object(nlu.engineer, 'build_flow_prompt',
                              return_value=('sys', [{'role': 'user', 'content': 'hi'}])):
                result = nlu._detect_flow('hello')

        assert call_count['n'] == 3
        assert result['flow_name'] == 'chat'
        assert result['confidence'] == pytest.approx(1.0)

    def test_one_voter_fails(self, nlu):
        calls = {'n': 0}

        def mock_call_text(system, messages, call_site, max_tokens=512):
            calls['n'] += 1
            if call_site == 'nlu_vote_gemini':
                raise RuntimeError('Gemini down')
            return '{"flow_name": "chat", "confidence": 0.8}'

        with patch.object(nlu.engineer, 'call_text', side_effect=mock_call_text):
            with patch.object(nlu.engineer, 'build_flow_prompt',
                              return_value=('sys', [{'role': 'user', 'content': 'hi'}])):
                result = nlu._detect_flow('hello')

        assert result['flow_name'] == 'chat'
        assert result['confidence'] == pytest.approx(1.0)

    def test_all_voters_fail(self, nlu):
        def mock_call_text(system, messages, call_site, max_tokens=512):
            raise RuntimeError('All down')

        with patch.object(nlu.engineer, 'call_text', side_effect=mock_call_text):
            with patch.object(nlu.engineer, 'build_flow_prompt',
                              return_value=('sys', [{'role': 'user', 'content': 'hi'}])):
                result = nlu._detect_flow('hello')

        assert result['flow_name'] == 'chat'
        assert result['confidence'] == 0.3

    def test_disagreement_weighted(self, nlu):
        def mock_call_text(system, messages, call_site, max_tokens=512):
            if call_site == 'nlu_vote_haiku':
                return '{"flow_name": "chat"}'
            return '{"flow_name": "query"}'

        with patch.object(nlu.engineer, 'call_text', side_effect=mock_call_text):
            with patch.object(nlu.engineer, 'build_flow_prompt',
                              return_value=('sys', [{'role': 'user', 'content': 'data'}])):
                result = nlu._detect_flow('show me the data')

        assert result['flow_name'] == 'query'
        assert result['confidence'] == pytest.approx(0.80)


# -- Ensemble voter config tests -----------------------------------------------

class TestEnsembleConfig:
    def test_weights_sum_to_one(self):
        total = sum(v['weight'] for v in _ENSEMBLE_VOTERS)
        assert total == pytest.approx(1.0)

    def test_three_voters(self):
        assert len(_ENSEMBLE_VOTERS) == 3

    def test_unique_labels(self):
        labels = [v['label'] for v in _ENSEMBLE_VOTERS]
        assert len(labels) == len(set(labels))

    def test_unique_call_sites(self):
        sites = [v['call_site'] for v in _ENSEMBLE_VOTERS]
        assert len(sites) == len(set(sites))
