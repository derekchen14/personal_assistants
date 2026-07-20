"""MEM model unit tests (the Head) — one of the three model-unit-test modules.

Deterministic half only for now (the probabilistic half is empty): the recap/recall/retrieve
skills facade and the L1 Context-Coordinator compaction + its post-hook trigger.
Shared fixtures (minimal_config, sessions_dir, orch_agent) live in conftest.py.
"""
import json
from types import MappingProxyType, SimpleNamespace

import pytest

from backend.components.world import World
from backend.components.user_preferences import UserPreferences
from backend.components.prompt_engineer import PromptEngineer
from backend.modules.nlu import NLU
from backend.modules.pex import PEX
from backend.modules.mem import MEM
from backend.components.context_coordinator import ContextCoordinator
from backend.prompts.for_compactor import SUMMARY_PREFIX


def _make_world(config):
    """Mirror backend/assistant.py's wiring: modules construct their components, the World
    holds the shared references, and each module gets the world attached afterwards."""
    engineer = PromptEngineer(config)
    nlu = NLU(config, engineer)
    pex = PEX(config, engineer)
    mem = MEM(config, engineer, 'test_user')
    world = World(config, nlu, pex, mem)
    nlu.world = world
    pex.world = world
    mem.world = world
    return world, mem


class _FakeEngineer:
    """Minimal engineer stub: returns a canned schema-shaped dict for any call."""
    def __init__(self, response):
        self.response = response
        self.last_prompt = None

    def __call__(self, prompt, task='skill', schema=None, tier='med', max_tokens=1024, family=''):
        self.last_prompt = prompt
        return self.response


# ==============================================================================
# (a) DETERMINISTIC — no live LLM
# ==============================================================================

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
        lambda system, messages, model_id, *, tools=None, max_tokens=4096,
               schema_dict=None: queue.pop(0))
    return queue




class TestMEMFacade:
    """The MEM module delegates each read skill to its tier (recap→L1, recall→L2, retrieve→L3).
    MEM constructs and owns its three components, so the tests reach them through the module."""

    def test_recall_returns_stored_preferences(self, minimal_config):
        memory = MEM(minimal_config, None, 'test_user')
        memory.user_preferences.store_preference('tone', 'casual')
        assert memory.recall('tone') == {'tone': 'casual'}

    def test_retrieve_faq_shortcut(self, minimal_config):
        memory = MEM(minimal_config, _FakeEngineer({'matches': [{'idx': 0, 'score': 0.9}]}),
                     'test_user')
        memory.business_knowledge._corpus = [{'question': 'What is X?', 'answer': 'X is Y.'}]
        result = memory.retrieve('what is x', documents=['faq'])
        assert result['_success'] is True
        assert result['matches'][0]['question'] == 'What is X?'

    def test_recent_history_reads_through_the_component(self, minimal_config):
        """T20: the L1 read is the Context Coordinator's — `recap` is the turn wrap now."""
        memory = MEM(minimal_config, None, 'test_user')
        memory.context_coordinator.add_turn('user', {'text': 'draft a post about otters'})
        assert 'otters' in memory.context_coordinator.compile_history(keep_system=True)


# ═══════════════════════════════════════════════════════════════════
# Snapshot infrastructure
# ═══════════════════════════════════════════════════════════════════



def _seed_transcript(coordinator, turns:int):
    """`turns` orchestrator rounds, 3 turns each (4 projected messages): user utterance, one
    kind-4 loop round (tool_use + paired result), agent wrap-up utterance."""
    for idx in range(turns):
        coordinator.add_turn('user', {'text': f'user turn {idx}: ' + 'x' * 80})
        coordinator.add_turn('agent', {'text': f'working on {idx}',
            'tool_uses': [{'type': 'tool_use', 'id': f'toolu_{idx}', 'name': 'read_state',
                           'input': {'turn': idx}}],
            'tool_results': [{'type': 'tool_result', 'tool_use_id': f'toolu_{idx}',
                              'content': json.dumps({'_success': True, 'filler': 'y' * 300})}]},
            turn_type='action')
        coordinator.add_turn('agent', {'text': f'done with turn {idx}'})




def _stub_summarizer(record:list):
    """Mock auxiliary summarizer: records its inputs, returns a numbered summary."""
    def summarize(middle, previous_summary, budget):
        record.append({'middle': list(middle), 'previous': previous_summary, 'budget': budget})
        return f'summary #{len(record)}'
    return summarize




class TestCompression:
    """Head/tail protection, structural tool-pair integrity, handoff shape, the pruning
    rendering rule, and history.jsonl consistency — all with a mocked summarizer (no LLM).
    Sizes count TURNS (round 6.1): the fixture holds 30 turns projecting to 40 messages."""

    @pytest.fixture
    def loaded(self, minimal_config, tmp_path):
        coordinator = ContextCoordinator(minimal_config)
        coordinator.load_history(tmp_path / 'history.jsonl')
        _seed_transcript(coordinator, 10)  # 30 turns → 40 projected messages
        return coordinator

    def test_too_short_list_is_not_compacted(self, minimal_config):
        coordinator = ContextCoordinator(minimal_config)
        _seed_transcript(coordinator, 2)  # 6 turns <= head(3) + tail(20) + 1
        assert coordinator.compact_messages(_stub_summarizer([]), protect_tail=20) is False
        assert coordinator.previous_summary is None

    def test_head_and_tail_are_protected(self, loaded):
        before = loaded.compile_messages()
        assert loaded.compact_messages(_stub_summarizer([]), protect_tail=20) is True
        after = loaded.compile_messages()
        # head turns 0-2 (4 messages) + the handoff + the visible tail (turns 10..29)
        assert after[:4] == before[:4]
        assert after[4]['content'].startswith(SUMMARY_PREFIX)
        assert after[-24:] == before[-24:]  # rounds 4-9 render identically on both sides

    def test_handoff_message_shape(self, loaded):
        loaded.compact_messages(_stub_summarizer([]), protect_tail=20)
        handoff = loaded.compile_messages()[4]
        assert handoff['role'] == 'user'
        assert handoff['content'].startswith(SUMMARY_PREFIX)
        assert 'summary #1' in handoff['content']
        assert handoff['content'].rstrip().endswith(
            'respond to the message below, not the summary above ---')

    def test_tool_pairs_stay_intact_across_the_cut(self, loaded):
        # Pairing is structural now — a kind-4 turn holds its calls and results together, so
        # every projected tool_use is immediately followed by its results whatever the cut.
        assert loaded.compact_messages(_stub_summarizer([]), protect_tail=19) is True
        messages = loaded.compile_messages()
        for idx, message in enumerate(messages):
            content = message['content']
            if isinstance(content, list) and content and content[-1]['type'] == 'tool_use':
                results = messages[idx + 1]['content']
                assert results[0]['tool_use_id'] == content[-1]['id']

    def test_summarizer_sees_only_the_middle(self, loaded):
        record = []
        loaded.compact_messages(_stub_summarizer(record), protect_tail=20)
        middle = record[0]['middle']
        assert len(middle) == 9  # turns 3..9 rendered — nothing from the head or tail
        assert middle[0]['content'].startswith('user turn 1')
        assert middle[-1]['content'].startswith('user turn 3')
        assert record[0]['budget'] == 2000  # small middle clamps to the Hermes floor

    def test_old_tool_results_render_pruned_store_keeps_them(self, loaded):
        # Pruning is a rendering rule: turns older than protect_tail render the placeholder,
        # while the stored turn (and history.jsonl) keeps the full result.
        messages = loaded.compile_messages()
        assert messages[2]['content'][0]['content'] == \
            '[Old tool output cleared to save context space]'
        assert 'filler' in messages[-2]['content'][0]['content']  # recent — untouched
        assert 'filler' in loaded._history[1].content['tool_results'][0]['content']

    def test_history_jsonl_round_trips_after_compaction(self, loaded, minimal_config,
                                                        tmp_path):
        loaded.compact_messages(_stub_summarizer([]), protect_tail=20)
        reopened = ContextCoordinator(minimal_config)
        reopened.load_history(tmp_path / 'history.jsonl')
        assert reopened.compile_messages() == loaded.compile_messages()

    def test_event_turn_records_the_compaction(self, loaded):
        loaded.compact_messages(_stub_summarizer([]), protect_tail=20, prompt_tokens=70000)
        event = loaded.full_conversation(as_turns=True)[-1]
        assert event.content['activity'] == 'compaction'
        assert event.content['result'] == {'start': 3, 'cut': 10, 'summary_index': 30,
                                           'prompt_tokens': 70000}

    def test_second_compaction_updates_the_previous_summary(self, loaded):
        record = []
        loaded.compact_messages(_stub_summarizer(record), protect_tail=20)
        _seed_transcript(loaded, 5)  # the conversation keeps going
        assert loaded.compact_messages(_stub_summarizer(record), protect_tail=20) is True
        assert record[0]['previous'] is None
        assert record[1]['previous'] == 'summary #1'
        # the old summary turn is skipped and is never re-summarized as content
        assert all(not (isinstance(msg['content'], str)
                        and msg['content'].startswith(SUMMARY_PREFIX))
                   for msg in record[1]['middle'])

    def test_reloaded_session_seeds_previous_summary_from_history(self, loaded,
                                                                  minimal_config, tmp_path):
        loaded.compact_messages(_stub_summarizer([]), protect_tail=20)
        reopened = ContextCoordinator(minimal_config)  # fresh process — no in-memory summary
        reopened.load_history(tmp_path / 'history.jsonl')
        _seed_transcript(reopened, 5)
        record = []
        assert reopened.compact_messages(_stub_summarizer(record), protect_tail=20) is True
        assert record[0]['previous'] == 'summary #1'


class TestCompressionTrigger:
    """The end-of-turn trigger (MEM._compaction_check, run by recap): real usage off
    response.usage against the configured threshold; the protected tail size rides in from
    config."""

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
        monkeypatch.setattr(orch_agent.world.context, 'compact_messages',
                            lambda *args: calls.append(args) or True)
        _script(orch_agent, [self._usage_response('small turn', 63999)])
        orch_agent.take_turn('hello')
        assert calls == []

    def test_at_threshold_compacts_with_config_tail(self, orch_agent, monkeypatch):
        calls = []
        monkeypatch.setattr(orch_agent.world.context, 'compact_messages',
                            lambda *args: calls.append(args) or True)
        _script(orch_agent, [self._usage_response('big turn', 64000)])
        orch_agent.take_turn('hello')
        summarize, protect_tail, prompt_tokens = calls[0]
        assert summarize == orch_agent.mem._summarize_middle
        assert protect_tail == 20  # schemas/tools.yaml compaction.protect_tail
        assert prompt_tokens == 64000

    def test_summarizer_failure_does_not_eat_the_reply(self, orch_agent, monkeypatch):
        def boom(*args):
            raise RuntimeError('aux model down')
        monkeypatch.setattr(orch_agent.world.context, 'compact_messages', boom)
        _script(orch_agent, [self._usage_response('still replies', 200000)])
        assert orch_agent.take_turn('hello')['message'] == 'still replies'




class TestRecap:
    """MEM.recap — the turn wrap (T20: store_turn renamed): records the agent turn to L1,
    bumps the turn count, and saves state.json to the session dir."""

    def test_recap_records_bumps_and_saves(self, sessions_dir, minimal_config):
        config = dict(minimal_config)
        config['compaction'] = {'threshold_tokens': 64000, 'protect_tail': 20}
        world, memory = _make_world(MappingProxyType(config))
        world.open_session('convo-store')
        before = world.context.num_utterances
        memory.recap('Drafted the otter post.')
        assert world.context.num_utterances == before + 1   # recap appended the agent utterance
        assert world.state.turn_id == world.context.num_utterances   # snapshot recorded from Context
        assert 'Drafted the otter post.' in memory.context_coordinator.compile_history(keep_system=True)
        saved = json.loads((world.session_dir() / 'state.json').read_text())
        assert saved['session']['turn_id'] == world.context.num_utterances



# MEM-owned components: Context Coordinator (L1) + sessions + Business Context (L3) --------

@pytest.fixture
def tmp_faq_db(tmp_db):
    """Extends tmp_db with a tmp faq_data dir. tmp_db already patches services._DB_DIR;
    BusinessContext reads `services._DB_DIR / 'faq_data' / 'faqs.json'` at construction."""
    faq_dir = tmp_db / 'faq_data'
    faq_dir.mkdir()
    return faq_dir




class TestBusinessKnowledge:
    def test_search_returns_top_matches(self, tmp_faq_db):
        (tmp_faq_db / 'faqs.json').write_text(json.dumps([
            {'question': 'What can Hugo do?', 'answer': 'Help write blog posts.', 'tags': ['cap']},
            {'question': 'Who built Hugo?', 'answer': 'Soleda.', 'tags': ['origin']},
        ]))
        from backend.components.business_knowledge import BusinessKnowledge
        engineer = _FakeEngineer({'matches': [{'idx': 0, 'score': 0.92}]})
        svc = BusinessKnowledge(engineer)
        result = svc.search_documents(query='what can it do', top_k=3)
        assert result['_success'] is True
        assert len(result['matches']) == 1
        assert result['matches'][0]['question'] == 'What can Hugo do?'
        assert result['matches'][0]['score'] == 0.92

    def test_search_empty_corpus(self, tmp_faq_db):
        # No faqs.json written — corpus loads empty.
        from backend.components.business_knowledge import BusinessKnowledge
        svc = BusinessKnowledge(_FakeEngineer({'matches': []}))
        result = svc.search_documents(query='anything')
        assert result['_success'] is False
        assert result['_error'] == 'empty_corpus'

    def test_search_drops_out_of_range_indices(self, tmp_faq_db):
        (tmp_faq_db / 'faqs.json').write_text(json.dumps([
            {'question': 'Q1', 'answer': 'A1', 'tags': []},
        ]))
        from backend.components.business_knowledge import BusinessKnowledge
        engineer = _FakeEngineer({'matches': [{'idx': 0, 'score': 0.8},
            {'idx': 99, 'score': 0.2}]})
        svc = BusinessKnowledge(engineer)
        result = svc.search_documents(query='q')
        # Out-of-range idx (99) silently dropped; valid one kept.
        assert len(result['matches']) == 1
        assert result['matches'][0]['question'] == 'Q1'




@pytest.fixture
def session_config(minimal_config):
    config = dict(minimal_config)
    config['session'] = {'max_flow_depth': 16, 'persistence': {'max_sessions': 2}}
    return MappingProxyType(config)




class TestWorldSessions:
    """World as session container: lazy dirs, in-place reset, close-time pruning."""

    def test_fresh_session_is_lazy(self, sessions_dir, minimal_config):
        world, memory = _make_world(minimal_config)
        assert world.open_session('fresh-id') is None
        assert not (sessions_dir / 'fresh-id').exists()  # nothing on disk until first use
        assert world.session_dir() == sessions_dir / 'fresh-id'
        assert (sessions_dir / 'fresh-id').is_dir()

    def test_reset_deletes_and_recreates_session_dir(self, sessions_dir, minimal_config):
        world, memory = _make_world(minimal_config)
        world.open_session('convo-42')
        world.state.save(world.session_dir() / 'state.json')
        world.reset()
        assert (sessions_dir / 'convo-42').is_dir()
        assert list((sessions_dir / 'convo-42').iterdir()) == []
        # In-place reset re-seeds the session substrate.
        assert world.state.turn_id == 0
        assert world.artifacts[-1] is not None

    def test_reset_without_session_still_works(self, sessions_dir, minimal_config):
        world, memory = _make_world(minimal_config)
        world.reset()
        assert not sessions_dir.exists()
        assert world.state.turn_id == 0


# ═══════════════════════════════════════════════════════════════════
# ContextCoordinator — the history store and its projection (round 6.1)
# ═══════════════════════════════════════════════════════════════════



def _seed_tool_round(coordinator):
    """A user utterance, one kind-4 loop round (call + paired result), the agent reply."""
    coordinator.add_turn('user', {'text': 'Draft a post about cheetahs'})
    coordinator.add_turn('agent', {'text': '',
        'tool_uses': [{'type': 'tool_use', 'id': 'toolu_01', 'name': 'read_state',
                       'input': {}}],
        'tool_results': [{'type': 'tool_result', 'tool_use_id': 'toolu_01',
                          'content': '{"flow_name": "compose"}'}]}, turn_type='action')
    coordinator.add_turn('agent', {'text': 'Started a draft about cheetahs.'})




class TestHistoryStore:
    """The single store (round 6.1): turns appended as the loop runs, mirrored to
    history.jsonl, reloaded on session resume; compile_messages() is the derived API view."""

    @pytest.fixture
    def coordinator(self, minimal_config, tmp_path):
        coordinator = ContextCoordinator(minimal_config)
        coordinator.load_history(tmp_path / 'history.jsonl')
        return coordinator

    def test_append_reload_round_trip(self, coordinator, minimal_config, tmp_path):
        _seed_tool_round(coordinator)
        reopened = ContextCoordinator(minimal_config)
        reopened.load_history(tmp_path / 'history.jsonl')
        assert reopened.compile_messages() == coordinator.compile_messages()

    def test_projection_shape_and_ordering(self, coordinator):
        _seed_tool_round(coordinator)
        messages = coordinator.compile_messages()
        assert [message['role'] for message in messages] == \
            ['user', 'assistant', 'user', 'assistant']
        assert messages[0]['content'] == 'Draft a post about cheetahs'
        assert messages[-1]['content'] == 'Started a draft about cheetahs.'

    def test_tool_result_pairing_preserved(self, coordinator, minimal_config, tmp_path):
        _seed_tool_round(coordinator)
        reopened = ContextCoordinator(minimal_config)
        reopened.load_history(tmp_path / 'history.jsonl')
        messages = reopened.compile_messages()
        call, result = messages[1], messages[2]
        assert call['content'][0]['type'] == 'tool_use'
        assert result['content'][0]['tool_use_id'] == call['content'][0]['id']

    def test_load_fresh_path_starts_empty(self, coordinator, tmp_path):
        assert coordinator.compile_messages() == []
        assert not (tmp_path / 'history.jsonl').exists()  # reads never create the file

    def test_add_turn_without_path_is_memory_only(self, minimal_config):
        coordinator = ContextCoordinator(minimal_config)
        coordinator.add_turn('user', {'text': 'hello'})
        assert coordinator.compile_messages() == [{'role': 'user', 'content': 'hello'}]

    def test_add_turn_creates_session_dir_lazily(self, minimal_config, tmp_path):
        coordinator = ContextCoordinator(minimal_config)
        coordinator.load_history(tmp_path / 'convo-9' / 'history.jsonl')
        coordinator.add_turn('user', {'text': 'hello'})
        assert (tmp_path / 'convo-9' / 'history.jsonl').exists()

    def test_reset_clears_store_and_file(self, coordinator, tmp_path):
        coordinator.add_turn('user', {'text': 'gone soon'})
        coordinator.reset()
        assert coordinator.compile_messages() == []
        assert (tmp_path / 'history.jsonl').read_text() == ''

    def test_open_session_reloads_history(self, sessions_dir, minimal_config):
        seeded = ContextCoordinator(minimal_config)
        seeded.load_history(sessions_dir / 'convo-42' / 'history.jsonl')
        _seed_tool_round(seeded)
        world, memory = _make_world(minimal_config)
        world.open_session('convo-42')
        assert world.context.compile_messages() == seeded.compile_messages()
        assert world.context.turn_count == 3  # the recorded session replaces the seed turn


# ==============================================================================
# MEM L2 — User Preferences (the single preference store). Was untested; these check the
# typed-record behavior and the endorsed-vs-guessed prompt rendering (actual output vs expected).
# ==============================================================================

from backend.components.user_preferences import Preference


class TestUserPreferences:
    """MEM L2 store: bare-string degenerate records, typed records, endorsed-vs-guessed render,
    and the per-account disk round trip (conftest patches _MEMORY_DIR to a tmp dir)."""

    def test_bare_string_stores_endorsed_full_confidence(self, minimal_config):
        prefs = UserPreferences(minimal_config, 'test_user')
        prefs.store_preference('verbosity', 'terse')
        assert prefs.read()['verbosity'] == 'terse'
        record = prefs._preferences['verbosity']
        assert record.endorsed is True and record.confidence == 1.0

    def test_dict_stores_typed_record(self, minimal_config):
        prefs = UserPreferences(minimal_config, 'test_user')
        prefs.store_preference('tone', {'value': 'wry', 'endorsed': False,
                                        'confidence': 0.6, 'triggers': ['humor']})
        record = prefs._preferences['tone']
        assert record.value == 'wry' and record.endorsed is False
        assert record.confidence == 0.6 and record.triggers == ['humor']

    def test_read_returns_flat_key_value_view(self, minimal_config):
        prefs = UserPreferences(minimal_config, 'test_user')
        prefs.store_preference('a', 'one')
        prefs.store_preference('b', {'value': 'two', 'endorsed': False})
        assert prefs.read() == {'a': 'one', 'b': 'two'}

    def test_render_distinguishes_endorsed_from_guessed(self, minimal_config):
        prefs = UserPreferences(minimal_config, 'test_user')
        prefs.store_preference('a_endorsed', 'short posts')
        prefs.store_preference('b_guessed', {'value': 'a casual tone', 'endorsed': False})
        assert prefs.render() == (
            '- Remember, the user wants short posts.\n'
            "- If the user hasn't said otherwise, assume a casual tone — but confirm if it matters.")

    def test_persistence_round_trip(self, minimal_config):
        first = UserPreferences(minimal_config, 'writer')
        first.store_preference('tone', {'value': 'wry', 'endorsed': False,
                                        'confidence': 0.6, 'triggers': ['humor']})
        second = UserPreferences(minimal_config, 'writer')
        record = second._preferences['tone']
        assert record.value == 'wry' and record.endorsed is False
        assert record.confidence == 0.6 and record.triggers == ['humor']
