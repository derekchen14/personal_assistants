"""PEX model unit tests (the Hands) — one of the three model-unit-test modules.

Deterministic half only for now (the probabilistic half is empty): the orchestrator acting loop,
the tool-def registry, flow dispatch / completion, the propose two-phase, and the system prompt.
Shared fixtures (mock_agent, sessions_dir, engineer, orch_agent) live in conftest.py.
"""
from __future__ import annotations
import json
import tempfile
import shutil
from pathlib import Path
from types import SimpleNamespace, MappingProxyType
from unittest.mock import MagicMock

import pytest

from backend.agent import Agent, _FALLBACK_MESSAGE, _NUDGE_MESSAGE, _WRAP_UP_MESSAGE
from backend.modules.pex import READ_ONLY_DOMAIN_TOOLS
from backend.components.task_artifact import TaskArtifact
from backend.components.flow_stack import flow_classes
from backend.components.memory_manager import MemoryManager
from backend.components.user_preferences import UserPreferences
from backend.components.prompt_engineer import PromptEngineer
from backend.components.session_scratchpad import SessionScratchpad
from backend.prompts.for_orchestrator import build_orchestrator_prompt
from schemas.config import load_config
from schemas.ontology import FLOW_ONTOLOGY

_HOT_PATH_TOOLS = ('manage_flows', 'understand', 'scratchpad', 'store_preference')


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


class TestParseJson:
    """Round 3.7 Decision A: the JSON-parse fallback recovers the FULL object or returns None —
    never a nested fragment (the old innermost regex returned slices like {'post': ...})."""

    def test_prose_wrapped_object_returns_full_object(self):
        text = 'Sure! {"reasoning": "x", "slots": {"source": {"post": "T"}}}'
        parsed = PromptEngineer._parse_json(text)
        assert parsed == {'reasoning': 'x', 'slots': {'source': {'post': 'T'}}}

    def test_truncated_object_returns_none_not_fragment(self):
        text = '{"reasoning": "x", "slots": {"source": {"post": "T"}'
        assert PromptEngineer._parse_json(text) is None




class TestOrchestratorToolDefs:
    """Hot-path tool definitions and the orchestrator's tool list (decision 16 allowlist)."""

    def test_defs_cover_dispatch_registry_exactly(self, mock_agent):
        pex = mock_agent.pex
        names = [tool['name'] for tool in pex._orchestrator_tool_definitions()]
        assert names == list(_HOT_PATH_TOOLS)
        assert set(pex._orchestrator_toolset) == set(names)

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

    def test_understand_read_returns_document(self, mock_agent):
        result = mock_agent.pex._dispatch_tool('understand', {'op': 'read'})
        assert result['_success'] is True
        assert list(result['state']) == ['session', 'user_beliefs', 'grounding',
                                         'flow_stack', 'flags']

    def test_manage_flows_stacks_and_saves(self, sessions_dir, mock_agent):
        mock_agent.world.open_session('wire-test')
        result = mock_agent.pex._dispatch_tool('manage_flows',
                                               {'op': 'stackon', 'flow_name': 'outline'})
        assert result['_success'] is True
        assert result['state']['flow_stack'][0]['flow_name'] == 'outline'
        assert (sessions_dir / 'wire-test' / 'state.json').exists()
        assert mock_agent.pex.flow_stack.peek().flow_type == 'outline'

    def test_manage_flows_pop_clears_the_stack(self, sessions_dir, mock_agent):
        """`pop` removes Completed and Invalid flows all at once; the saved document shows it."""
        mock_agent.world.open_session('wire-test')
        pex = mock_agent.pex
        pex.flow_stack.stackon('chat').status = 'Completed'
        result = pex._dispatch_tool('manage_flows', {'op': 'pop'})
        assert result['_success'] is True
        assert result['state']['flow_stack'] == []
        assert pex.flow_stack.to_list() == []

    def test_manage_flows_bad_op_returns_corrective_error(self, sessions_dir, mock_agent):
        mock_agent.world.open_session('wire-test')
        result = mock_agent.pex._dispatch_tool('manage_flows', {'op': 'merge'})
        assert result['_success'] is False
        assert 'Unknown write_state op' in result['_message']

    def test_manage_flows_unknown_slot_returns_corrective_error(self, sessions_dir, mock_agent):
        """LLM-invented slot names (e.g. create's `type` reread as genre) get a corrective
        error naming the valid slots, instead of fill_slot_values dropping them silently."""
        mock_agent.world.open_session('wire-test')
        mock_agent.pex._dispatch_tool('manage_flows', {'op': 'stackon', 'flow_name': 'outline'})
        result = mock_agent.pex._dispatch_tool(
            'manage_flows', {'op': 'update', 'fields': {'slots': {'genre': 'tutorial'}}})
        assert result['_success'] is False
        assert result['_error'] == 'invalid_input'
        assert "'source'" in result['_message']  # valid slots are listed for the retry

    def test_scratchpad_tool_routes_to_memory(self, mock_agent, tmp_path):
        pex = mock_agent.pex
        pex.scratchpad = SessionScratchpad(pex.config, scratchpad_path=str(tmp_path / 'scratch.jsonl'))
        appended = pex._dispatch_tool('scratchpad',
                                      {'op': 'append', 'entry': {'finding': 'intro is weak'}})
        assert appended == {'_success': True, 'size': 1}
        result = pex._dispatch_tool('scratchpad', {'op': 'read', 'writer': 'orchestrator'})
        assert result['entries'] == [{'finding': 'intro is weak', 'writer': 'orchestrator'}]

    def test_understand_hint_is_deterministic_from_stack_top(self, mock_agent):
        """The hint is coordination code, never a tool argument: the flow PEX committed to the
        stack is its first-pass selection — a domain intent on top hints NLU; Converse or an
        empty stack carries no real signal and blanks out."""
        pex = mock_agent.pex
        state = mock_agent.world.current_state()
        state.pred_intent, state.pred_flows = 'Draft', [{'flow_name': 'outline', 'confidence': 0.9}]
        pex.nlu = MagicMock()
        pex.nlu.understand.return_value = state
        pex._dispatch_tool('understand', {'op': 'think'})          # empty stack → blank
        assert pex.nlu.understand.call_args.kwargs['hint'] == ''
        pex.flow_stack.stackon('outline')                          # Draft flow on top → hint
        pex._dispatch_tool('understand', {'op': 'think'})
        assert pex.nlu.understand.call_args.kwargs['hint'] == 'Draft'
        pex.flow_stack.stackon('chat')                             # Converse on top → blank
        pex._dispatch_tool('understand', {'op': 'contemplate'})
        assert pex.nlu.understand.call_args.kwargs['hint'] == ''




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
        result = pex._dispatch_tool('manage_flows', {'op': 'activate', 'flow_name': 'outline'})
        assert result['_success'] is True
        assert result['status'] == 'Completed'
        assert result['completion'] == {'flow': 'outline', 'summary': 'Drafted the intro.',
                                        'metadata': {}, 'writer': 'outline'}
        assert pex.scratchpad.read(keys=['flow', 'summary']) == [result['completion']]
        # The run is reflected back into the state's flow_stack block, grounding applied.
        assert state.flow_stack[-1]['flow_name'] == 'outline'
        assert state.flow_stack[-1]['status'] == 'Completed'
        assert state.active_post == 'cafe01'

    def test_write_state_slots_reach_the_policy_run(self, wired):
        """slots written via write_state land on the live flow that activate_flow runs."""
        pex = wired.pex
        state = wired.world.current_state()
        state.write_state(wired.world.state_file(), 'stackon',
                          stack=pex.flow_stack, flow_name='outline')
        state.write_state(wired.world.state_file(), 'update_flow',
                          stack=pex.flow_stack, slots={'source': [{'post': 'cafe01'}]})
        state.grounding['post'] = 'cafe01'
        captured = {}

        class _CapturingPolicy(_StubPolicy):
            def execute(self, policy_state, context, tools):
                captured['slots'] = self.flow_stack.get_flow().slot_values_dict()
                return super().execute(policy_state, context, tools)

        pex._policies['Draft'] = _CapturingPolicy(pex.flow_stack)
        assert pex.flow_stack.find_by_name('outline') is not None
        result = pex._dispatch_tool('manage_flows', {'op': 'activate', 'flow_name': 'outline'})
        assert result['status'] == 'Completed'
        assert captured['slots']['source'][0]['post'] == 'cafe01'

    def test_non_completed_returns_status_and_question(self, wired):
        pex = wired.pex
        pex._policies['Draft'] = _StubPolicy(pex.flow_stack, status='Active',
                                             thoughts='Need a post first.')
        pex.ambiguity.declare('partial', metadata={'missing': 'source', 'entity': 'post'},
                              observation='Which post should I work on?')
        result = pex._dispatch_tool('manage_flows', {'op': 'activate', 'flow_name': 'outline'})
        assert result['_success'] is True
        assert result['status'] == 'Active'
        assert result['question'] == 'Which post should I work on?'
        assert 'completion' not in result

    def test_empty_artifact_fails_validation(self, wired):
        pex = wired.pex
        pex._policies['Draft'] = _StubPolicy(pex.flow_stack, status='Active', thoughts='')
        result = pex._dispatch_tool('manage_flows', {'op': 'activate', 'flow_name': 'outline'})
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
        result = pex._dispatch_tool('manage_flows', {'op': 'activate', 'flow_name': 'outline'})
        assert result['_success'] is True
        assert result['completion'] == {'flow': 'outline', 'summary': 'Wrote the intro.',
                                        'metadata': {'sec': 'intro'}, 'writer': 'outline'}
        # The policy's record IS the tool result — no fallback duplicate from activate_flow.
        assert pex.scratchpad.read(keys=['flow', 'summary']) == [result['completion']]
        assert state.flow_stack[-1]['status'] == 'Completed'

    def test_complete_flow_blocks_ungrounded_completion(self, wired):
        pex = wired.pex
        pex._policies['Draft'] = self._migrated_policy(wired, 'Done.')
        result = pex._dispatch_tool('manage_flows', {'op': 'activate', 'flow_name': 'outline'})
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
        return build_orchestrator_prompt(engineer, memory, 'conv-42', 'writer', '2026-06-11')

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
        for tag in ('persona', 'intents', 'tool_policy', 'workflow', 'flow_ontology',
                    'outline_levels', 'preferences', 'session'):
            assert f'<{tag}>' in prompt and f'</{tag}>' in prompt
        assert 'Session: conversation_id=conv-42 | user=writer | date=2026-06-11' in prompt
        assert '10. **Release and syndicate**' in prompt  # README workflow ported
        assert f'## Flow Ontology ({len(FLOW_ONTOLOGY)} flows)' in prompt


# ═══════════════════════════════════════════════════════════════════
# Orchestrator loop v1 (changes.md §3, decisions 3, 6, 13)
# ═══════════════════════════════════════════════════════════════════



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
        _script(orch_agent, [_response(_tool_block('understand', {'op': 'read'})),
                             _response(_text_block('All caught up.'))])
        result = orch_agent.take_turn('where were we?')
        assert result['message'] == 'All caught up.'
        messages = orch_agent.world.context.messages
        assert [msg['role'] for msg in messages] == ['user', 'assistant', 'user', 'assistant']
        tool_use = messages[1]['content'][0]
        assert tool_use['type'] == 'tool_use' and tool_use['name'] == 'understand'
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
        _script(orch_agent, [_response(_tool_block('understand', {'op': 'read'}, block_id='t1')),
                             _response(_tool_block('understand', {'op': 'read'}, block_id='t2')),
                             _response(_text_block('done'))])
        orch_agent.take_turn('check state twice')
        second = json.loads(orch_agent.world.context.messages[4]['content'][0]['content'])
        assert second['_error'] == 'duplicate_call'

    def test_identical_retry_after_error_is_dispatched(self, orch_agent):
        """Dedupe only fires after a SUCCESSFUL identical call — retrying the same call
        after a transient tool error is legitimate recovery, not a loop."""
        bad_call = _tool_block('manage_flows', {'op': 'bogus'}, block_id='t1')
        _script(orch_agent, [_response(bad_call),
                             _response(_tool_block('manage_flows', {'op': 'bogus'}, block_id='t2')),
                             _response(_text_block('gave up'))])
        orch_agent.take_turn('do the thing')
        second = json.loads(orch_agent.world.context.messages[4]['content'][0]['content'])
        assert second['_error'] != 'duplicate_call'  # re-dispatched, not skipped

    def test_read_only_calls_capped_per_turn(self, orch_agent):
        """AC-3 (round 4.3): the first read-only lookup past limits.max_reads in one turn returns
        read_cap without dispatching; varied args do not evade the cap."""
        cap = orch_agent.pex.max_reads
        queries = ['bees', 'jazz', 'tea', 'vans', 'oak', 'silk'][:cap + 1]
        calls = [_response(_tool_block('find_posts', {'query': query}, block_id=f't{idx}'))
                 for idx, query in enumerate(queries, start=1)]
        _script(orch_agent, calls + [_response(_text_block('capped'))])
        orch_agent.take_turn('survey everything')
        results = [json.loads(orch_agent.world.context.messages[idx]['content'][0]['content'])
                   for idx in range(2, 2 * (cap + 1) + 1, 2)]
        assert [result['_success'] for result in results[:cap]] == [True] * cap
        assert results[cap]['_error'] == 'read_cap'

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

    def test_max_rounds_read_from_config(self, sessions_dir, monkeypatch):
        """The round budget flows from config: max_rounds=1 stops the loop after one round and
        routes to the wrap-up emit. A dead config wire would silently keep the yaml 8."""
        limits = {'max_rounds': 1, 'max_corrective': 3, 'max_reads': 3, 'max_tool_calls': 8,
                  'extended_tool_calls': 16,
                  'extended_call_flows': ['audit', 'refine', 'rework', 'compose']}
        monkeypatch.setattr('backend.agent.load_config',
                            lambda: load_config(overrides={'debug': True, 'limits': limits}))
        agent = Agent(username='test_user')
        agent.nlu.understand = lambda *args, **kwargs: None
        queue = _script(agent, [_response(_tool_block('understand', {'op': 'read'})),
                                _response(_text_block('Wrapped up after one round.'))])
        result = agent.take_turn('walk the whole backlog')
        agent.close()
        assert result['message'] == 'Wrapped up after one round.'
        assert queue == []  # one tool round + the forced no-tools wrap-up, nothing more
        assert agent.world.context.messages[-2] == {'role': 'user',
                                                    'content': _WRAP_UP_MESSAGE}

    def test_call_cap_read_from_config(self, engineer, monkeypatch):
        """The per-flow call cap flows from config: extended_call_flows get extended_tool_calls,
        every other flow gets max_tool_calls."""
        captured = []

        def fake_call(system, msgs, model_id, tool_defs, tool_dispatcher, max_tokens, max_num_calls):
            captured.append(max_num_calls)
            return ('', [])
        monkeypatch.setattr(engineer, '_model_family', lambda model: 'claude')
        monkeypatch.setattr(engineer, '_call_claude_with_tools', fake_call)
        engineer.flow_execute(flow_classes['audit'](), '', {}, [], None, flow_prompt='')
        engineer.flow_execute(flow_classes['find'](), '', {}, [], None, flow_prompt='')
        assert captured == [16, 8]  # extended cap for audit, base cap for find

    def test_flow_reply_honors_model_tier(self, engineer, monkeypatch):
        """flow_reply routes its per-call model tier to _resolve_model, defaulting to 'med'."""
        seen = []
        monkeypatch.setattr(engineer, '_resolve_model', lambda model: seen.append(model))
        monkeypatch.setattr(engineer, '_model_family', lambda model: 'gemini')
        monkeypatch.setattr(engineer, '_call_gemini', lambda *args, **kwargs: '')
        engineer.flow_reply(flow_classes['find'](), '', {}, flow_prompt='', model='high')
        engineer.flow_reply(flow_classes['find'](), '', {}, flow_prompt='')
        assert seen == ['high', 'med']  # explicit tier honored, then the default

    def test_recovery_keys_collapsed(self):
        """The yaml declares each bound exactly once: no resilience or recovery sections survive,
        and the promoted values sit under limits."""
        cfg = load_config()
        assert 'recovery' not in cfg and 'resilience' not in cfg
        limits = cfg['limits']
        assert limits['max_recovery_attempts'] == 2  # the ONE surviving recovery key
        assert (limits['max_rounds'], limits['max_corrective']) == (8, 3)
        assert (limits['max_tool_calls'], limits['extended_tool_calls']) == (8, 16)
        assert limits['extended_call_flows'] == ('audit', 'refine', 'rework', 'compose')




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




from backend.utilities.services import (
    ToolService, PostService, ContentService, AnalysisService, PlatformService,
    split_sentences, join_sentences, _DB_DIR,
)
from backend.components.dialogue_state import DialogueState, rehydrate_flow
from backend.components.flow_stack import FlowStack
from utils.evaluation_suite.scoring import gate, grade


def _without_ids(entries:list) -> list:
    """Stack entries minus the random flow_id, for cross-implementation comparison."""
    return [{key: val for key, val in entry.items() if key != 'flow_id'} for entry in entries]


# PEX-owned components: Task Artifact + FlowStack + domain services + snapshots + gate ----

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

    def test_part_raw_serializes_base64(self):
        from backend.components.task_artifact import Part
        out = Part(raw=b'\x00\x01\xff').to_dict()
        assert out == {'raw': 'AAH/'}

    def test_part_metadata_round_trips(self):
        from backend.components.task_artifact import Part
        out = Part(text='hi', metadata={'kind': 'thoughts'}).to_dict()
        assert out == {'text': 'hi', 'metadata': {'kind': 'thoughts'}}

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

    def test_split_sentences_sub_bullets_stay_separate(self):
        # Per OUTLINE_LEVELS (flows.py): Level 3 is `- bullet`, Level 4 is
        # `   * sub-bullet`. Both should be treated as structural.
        text = '- parent one\n  * sub a\n  * sub b\n- parent two'
        snips = split_sentences(text)
        assert snips == ['- parent one', '  * sub a', '  * sub b', '- parent two']

    def test_join_sentences_sub_bullets_preserve_indent(self):
        snips = ['- parent', '  * sub a', '  * sub b']
        assert join_sentences(snips) == '- parent\n  * sub a\n  * sub b'

    def test_join_sentences_bullets_get_newlines(self):
        out = join_sentences(['- alpha', '- beta', '- gamma'])
        assert out == '- alpha\n- beta\n- gamma'

    def test_join_sentences_prose_space_joined(self):
        out = join_sentences(['Sentence one.', 'Sentence two.'])
        assert out == 'Sentence one. Sentence two.'

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
    """Smoke tests for evaluation_suite/_snapshot.py — ensure the harness itself works."""

    def test_volatile_keys_masked(self):
        from utils.evaluation_suite._snapshot import _mask_volatile
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
        from utils.evaluation_suite import _snapshot
        monkeypatch.setattr(_snapshot, 'SNAPSHOT_DIR', tmp_path)
        # Record
        monkeypatch.setenv('UPDATE_SNAPSHOTS', '1')
        _snapshot.assert_snapshot({'a': 1, 'b': [2, 3]}, 'sample')
        assert (tmp_path / 'sample.json').exists()
        # Compare — same value passes
        monkeypatch.delenv('UPDATE_SNAPSHOTS')
        _snapshot.assert_snapshot({'a': 1, 'b': [2, 3]}, 'sample')

# ═══════════════════════════════════════════════════════════════════
# Session substrate — file-backed DialogueState + World session dirs
# ═══════════════════════════════════════════════════════════════════

from backend.components.dialogue_state import DialogueState
from backend.components.world import World




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

# ═══════════════════════════════════════════════════════════════════
# Pillar 3 — Hypothesis stateful test for FlowStack
# Drives the FlowStack component through random-but-valid write_state op
# sequences. Catches FSM-discipline regressions (depth bounds, status
# transitions, pop_completed semantics, get_flow filtering) and
# serialization round-trip loss of the saved copy in state.json.
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
            # The DialogueState carries the saved copy of this stack in its flow_stack block.
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
                self.state.write_state(self.state_file, 'stackon', stack=self.stack, flow_name=name)
                new_flow = self.stack._stack[-1]
                # Two valid outcomes: pushed a new Pending flow (activation promotes),
                # OR returned the existing in-flight top (no-consecutive-same-type).
                assert new_flow.flow_id and len(new_flow.flow_id) >= 6
                assert self.stack._stack[-1] is new_flow
                if new_flow is not top_before:
                    assert new_flow.status == 'Pending'

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
            self.state.write_state(self.state_file, 'fallback', stack=self.stack, flow_name=name)
            assert old_top.status == 'Invalid'
            assert self.stack._stack[-1].status == 'Active'
            assert self.stack._stack[-1].flow_type == name

        @rule(post=st.sampled_from(['p1', 'p2']))
        def fill_source(self, post):
            # Exercises slot round-trip fidelity: flows without a 'source' slot
            # ignore the fill on both implementations.
            if self.stack._stack:
                self.state.write_state(self.state_file, 'update_flow',
                                       stack=self.stack, slots={'source': [{'post': post}]})

        @rule()
        def complete_top(self):
            if self.stack._stack:
                self.state.write_state(self.state_file, 'update_flow',
                                       stack=self.stack, status='Completed')

        @rule()
        def mark_pending(self):
            # Some flows are pushed Pending by plans; simulate that state by
            # marking top Pending. Then pop_completed should activate it.
            if self.stack._stack:
                self.state.write_state(self.state_file, 'update_flow',
                                       stack=self.stack, status='Pending')

        @rule()
        def pop_completed(self):
            before_completed = [e for e in self.stack._stack if e.status == 'Completed']
            self.state.write_state(self.state_file, 'pop_completed', stack=self.stack)
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
        def saved_copy_matches_the_stack(self):
            # the saved copy and file track the one stack
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

from utils.evaluation_suite.scoring import gate, grade




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


# ==============================================================================
# PEX skill / prompt artifact lints (offline, no LLM) — folded from test_artifacts.py.
# Consolidated from per-skill parametrization into single looping checks (drift-catchers).
# ==============================================================================

import re as _re
import yaml as _yaml
from pathlib import Path as _Path

from backend.components.prompt_engineer import _TASK_SUFFIXES
from backend.prompts import general
from backend.prompts.for_pex import build_flow_system

_FLOW_DIR = _Path(__file__).resolve().parents[3] / 'backend' / 'prompts' / 'pex' / 'flows'
_TOOLS_YAML = _Path(__file__).resolve().parents[3] / 'schemas' / 'tools.yaml'
_COMPONENT_TOOLS = {'handle_ambiguity', 'coordinate_context', 'manage_memory',
                    'call_flow_stack', 'execution_error', 'save_findings'}


def _flow_files():
    return sorted(p.stem for p in _FLOW_DIR.glob('*.md'))


def _yaml_tools():
    return set((_yaml.safe_load(_TOOLS_YAML.read_text()).get('tools') or {}).keys())


def _few_shot_tool_calls(body):
    idx = body.lower().find('## few-shot')
    return set(_re.findall(r'`([a-z][a-z0-9_]+)\(', body[idx:])) if idx != -1 else set()


def test_few_shot_tools_are_allowlisted():
    """Every tool referenced in a flow's `## Few-shot` block is in that flow.tools or is a
    component tool. Loops all flow files."""
    bad = []
    for flow in _flow_files():
        if flow not in flow_classes:
            continue
        allowed = set(flow_classes[flow]().tools) | _COMPONENT_TOOLS
        unknown = _few_shot_tool_calls(PromptEngineer.load_flow_prompt(flow)) - allowed
        if unknown:
            bad.append((flow, sorted(unknown)))
    assert not bad, f'few-shot tools not in flow.tools/component: {bad}'


def test_flow_tools_are_registered():
    """Every flow.tools entry is defined in schemas/tools.yaml."""
    yaml_tools = _yaml_tools()
    bad = [(name, t) for name, cls in flow_classes.items()
           for t in cls().tools if t not in yaml_tools]
    assert not bad, f'flow.tools with no tools.yaml def: {bad}'


def test_loader_reads_flow_prompt():
    body = PromptEngineer.load_flow_prompt('outline')
    assert body and not body.startswith('---') and '## Process' in body


def test_skill_system_ends_with_reminder():
    """The agentic reminder closes every assembled sub-agent system prompt, with or without a body."""
    flow = flow_classes['outline']()
    for flow_prompt in ('flow body', None):
        assert build_flow_system('base', flow, flow_prompt).endswith(general.SLOT_7_REMINDER)


def test_reminder_is_agentic():
    assert 'valid JSON' not in general.SLOT_7_REMINDER
    assert 'valid JSON' in _TASK_SUFFIXES['classify_intent']


# ═══════════════════════════════════════════════════════════════════
# Single-call stackon (write_state op=stackon active=true)
# ═══════════════════════════════════════════════════════════════════



class TestSingleCallStackon:
    """`write_state op=stackon active=true` stacks on, folds belief slots, and runs the
    policy in one call."""

    def _believe(self, state, flow_name, intent='Draft'):
        state.pred_intent = intent
        state.pred_flows = [{'flow_name': flow_name, 'confidence': 0.9, 'votes': 2}]
        state.pred_slots = {'source': [{'post': 'p1'}]}

    def test_stackon_active_folds_slots_and_activates(self, sessions_dir, mock_agent, monkeypatch):
        mock_agent.world.open_session('wire-test')
        pex = mock_agent.pex
        state = mock_agent.world.current_state()
        self._believe(state, 'outline')
        ran = {}
        monkeypatch.setattr(pex, 'activate_flow',
                            lambda params: ran.update(params) or {'_success': True, 'status': 'Completed'})
        result = pex._dispatch_tool('manage_flows',
                                    {'op': 'stackon', 'flow_name': 'outline', 'active': True})
        assert result['_success'] is True
        assert ran['flow_name'] == 'outline'   # policy ran with no separate activate_flow call
        top = pex.flow_stack.peek()
        assert top.slots['source'].values[0]['post'] == 'p1'   # belief slots folded in

    def test_stackon_without_active_only_stacks(self, sessions_dir, mock_agent, monkeypatch):
        mock_agent.world.open_session('wire-test')
        state = mock_agent.world.current_state()
        self._believe(state, 'outline')
        called = []
        monkeypatch.setattr(mock_agent.pex, 'activate_flow', lambda params: called.append(params))
        result = mock_agent.pex._dispatch_tool('manage_flows',
                                               {'op': 'stackon', 'flow_name': 'outline'})
        assert result['_success'] is True and not called


class TestCheckNlu:
    """The parallel NLU think thread joins at the hooks: a belief read blocks (the Plan/Clarify
    wait); flow execution reaps a landed detection without blocking (the user 2026-07-03)."""

    def test_read_state_joins_slow_nlu_thread(self, sessions_dir, mock_agent):
        import time
        from threading import Thread
        mock_agent.world.open_session('wire-test')
        pex = mock_agent.pex
        state = mock_agent.world.current_state()

        def slow_detect():
            time.sleep(0.05)
            state.pred_flows = [{'flow_name': 'outline', 'confidence': 0.9, 'votes': 3}]
        thread = Thread(target=slow_detect)
        thread.start()
        pex._nlu_thread = thread
        result = pex.read_state({})
        assert result['state']['user_beliefs']['pred_flows'][0]['flow_name'] == 'outline'
        assert pex._nlu_thread is None    # joined and cleared

    def test_settle_without_thread_is_noop(self, sessions_dir, mock_agent):
        mock_agent.world.open_session('wire-test')
        pex = mock_agent.pex
        pex._nlu_thread = None            # the click / awaited-think paths
        result = pex.read_state({})
        assert result['_success'] is True

    def test_flow_execution_never_blocks_on_running_nlu(self, sessions_dir, mock_agent):
        from threading import Event, Thread
        mock_agent.world.open_session('wire-test')
        pex = mock_agent.pex
        gate = Event()
        thread = Thread(target=gate.wait)
        thread.start()
        pex._nlu_thread = thread
        pex._check_nlu(wait=False)       # NLU still running: proceed, keep the handle
        assert pex._nlu_thread is thread
        gate.set()
        thread.join()
        pex._check_nlu(wait=False)       # landed detection: reap and clear
        assert pex._nlu_thread is None

class TestBeliefInjection:
    """NLU belief state injection (round 5.1): once per turn the landed detection becomes a
    [belief] note; intent-differs is forced in code, flow-differs is left to the orchestrator."""

    def _believe(self, state, flow_name, intent='Draft'):
        state.pred_intent = intent
        state.pred_flows = [{'flow_name': flow_name, 'confidence': 0.9, 'votes': 2}]
        state.pred_slots = {'source': [{'post': 'p1'}]}

    def test_injection_fires_once(self, sessions_dir, mock_agent):
        mock_agent.world.open_session('wire-test')
        pex = mock_agent.pex
        self._believe(mock_agent.world.current_state(), 'outline')
        note = pex.inject_belief_state()
        assert note.startswith('[belief]') and 'outline' in note
        assert pex.inject_belief_state() is None      # once per turn

    def test_injection_waits_for_landed_detection(self, sessions_dir, mock_agent):
        from threading import Event, Thread
        mock_agent.world.open_session('wire-test')
        pex = mock_agent.pex
        self._believe(mock_agent.world.current_state(), 'outline')
        gate = Event()
        thread = Thread(target=gate.wait)
        thread.start()
        pex._nlu_thread = thread
        assert pex.inject_belief_state() is None      # still thinking: skip, do not block
        gate.set()
        thread.join()
        assert pex.inject_belief_state() is not None  # landed: inject at the next hook

    def test_intent_differs_forces_fallback(self, sessions_dir, mock_agent):
        mock_agent.world.open_session('wire-test')
        pex = mock_agent.pex
        state = mock_agent.world.current_state()
        pex._dispatch_tool('manage_flows', {'op': 'stackon', 'flow_name': 'outline'})
        live = pex.flow_stack.peek()
        live.status = 'Active'   # stackon lands Pending; model a mid-turn running flow
        self._believe(state, 'release', intent='Publish')
        note = pex.inject_belief_state()
        assert 'Intent changed' in note and 'Invalid' in note
        assert live.status == 'Invalid'               # fallback: not coming back to it
        assert pex.flow_stack.get_flow(status='Active').flow_type == 'release'
        assert state.flow_stack[-1]['flow_name'] == 'release'   # NLU's flow took over

    def test_flow_differs_same_intent_no_forcing(self, sessions_dir, mock_agent):
        mock_agent.world.open_session('wire-test')
        pex = mock_agent.pex
        state = mock_agent.world.current_state()
        pex._dispatch_tool('manage_flows', {'op': 'stackon', 'flow_name': 'outline'})
        live = pex.flow_stack.peek()
        live.status = 'Active'   # stackon lands Pending; model a mid-turn running flow
        self._believe(state, 'refine', intent='Draft')
        note = pex.inject_belief_state()
        assert 'refine' in note and 'Intent changed' not in note
        assert live.status == 'Active'                # the orchestrator decides, not code


class TestPlanLifecycle:
    """A stacked multi-flow plan survives completions: there is exactly one flow stack, so a
    completion can no longer wipe the Pending flows of a plan (code review 2026-07-04,
    Critical 1)."""

    def test_plan_flows_survive_completion(self, sessions_dir, mock_agent, monkeypatch):
        from schemas.ontology import Intent
        mock_agent.world.open_session('wire-test')
        pex = mock_agent.pex
        state = mock_agent.world.current_state()
        for flow_name in ('release', 'compose'):    # reverse execution order: first-to-run last
            result = pex._dispatch_tool('manage_flows', {'op': 'stackon', 'flow_name': flow_name})
            assert result['_success'] is True

        class _CompletingPolicy:
            def execute(self, state, context, dispatch):
                pex.flow_stack.get_flow(status='Active').status = 'Completed'
                return TaskArtifact('outline', thoughts='outline done')
            def pop_completion(self):
                return {'flow': 'outline', 'summary': 'done', 'metadata': {}}
        monkeypatch.setitem(pex._policies, Intent.DRAFT, _CompletingPolicy())

        result = pex._dispatch_tool('manage_flows',
                                    {'op': 'stackon', 'flow_name': 'outline', 'active': True})
        assert result['_success'] is True and result['status'] == 'Completed'
        entries = [(entry['flow_name'], entry['status']) for entry in state.flow_stack]
        assert ('compose', 'Pending') in entries    # the plan survived the completion
        assert ('release', 'Pending') in entries
        pex._dispatch_tool('manage_flows', {'op': 'pop'})
        top = state.flow_stack[-1]
        assert top['flow_name'] == 'compose' and top['status'] == 'Active'   # next flow surfaces
