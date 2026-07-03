"""MEM model unit tests (the Head) — one of the three model-unit-test modules.

Deterministic half only for now (the probabilistic half is empty): the recap/recall/retrieve
skills facade and the L1 Context-Coordinator compaction + its post-hook trigger.
Shared fixtures (minimal_config, sessions_dir, orch_agent) live in conftest.py.
"""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from backend.components.world import World
from backend.components.user_preferences import UserPreferences
from backend.components.business_context import BusinessContext
from backend.components.memory_manager import MemoryManager
from backend.components.context_coordinator import ContextCoordinator
from backend.prompts.for_compressor import SUMMARY_PREFIX


class _FakeEngineer:
    """Minimal engineer stub: returns a canned schema-shaped dict for any call."""
    def __init__(self, response):
        self.response = response
        self.last_prompt = None

    def __call__(self, prompt, task='skill', schema=None, model='med', max_tokens=1024):
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
        lambda system, messages, model_id, *, tools=None, max_tokens=4096: queue.pop(0))
    return queue




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




from types import MappingProxyType
from backend.components.dialogue_state import DialogueState

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



# MEM-owned components: Context Coordinator (L1) + sessions + Business Context (L3) --------

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




@pytest.fixture
def session_config(minimal_config):
    config = dict(minimal_config)
    config['session'] = {'persistence': {'max_sessions': 2}}
    return MappingProxyType(config)




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




# ==============================================================================
# MEM L2 — User Preferences (the single preference store). Was untested; these check the
# typed-record behavior and the endorsed-vs-guessed prompt rendering (actual output vs expected).
# ==============================================================================

from backend.components.user_preferences import Preference


class TestUserPreferences:
    """MEM L2 store: bare-string degenerate records, typed records, endorsed-vs-guessed render."""

    def test_bare_string_stores_endorsed_full_confidence(self, minimal_config):
        prefs = UserPreferences(minimal_config)
        prefs.store_preference('verbosity', 'terse')
        assert prefs.get_preference('verbosity') == 'terse'
        record = prefs.read_all()['verbosity']
        assert record.endorsed is True and record.confidence == 1.0

    def test_dict_stores_typed_record(self, minimal_config):
        prefs = UserPreferences(minimal_config)
        prefs.store_preference('tone', {'value': 'wry', 'endorsed': False,
                                        'confidence': 0.6, 'triggers': ['humor']})
        record = prefs.read_all()['tone']
        assert record.value == 'wry' and record.endorsed is False
        assert record.confidence == 0.6 and record.triggers == ['humor']

    def test_get_preference_missing_returns_default(self, minimal_config):
        prefs = UserPreferences(minimal_config)
        assert prefs.get_preference('nope', 'fallback') == 'fallback'

    def test_read_returns_flat_key_value_view(self, minimal_config):
        prefs = UserPreferences(minimal_config)
        prefs.store_preference('a', 'one')
        prefs.store_preference('b', {'value': 'two', 'endorsed': False})
        assert prefs.read() == {'a': 'one', 'b': 'two'}

    def test_render_distinguishes_endorsed_from_guessed(self, minimal_config):
        prefs = UserPreferences(minimal_config)
        prefs.store_preference('a_endorsed', 'short posts')
        prefs.store_preference('b_guessed', {'value': 'a casual tone', 'endorsed': False})
        assert prefs.render() == (
            '- Remember, the user wants short posts.\n'
            "- If the user hasn't said otherwise, assume a casual tone — but confirm if it matters.")
