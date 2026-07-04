"""NLU deterministic unit tests (the Heart). No live model calls — the free tier.

Covers NLU-owned components: ensemble tally/dispatch, the react() slot-fill contract, historical
regressions, the Session Scratchpad, the Dialogue State (state.json serialization + belief/grounding
write ops). The probabilistic (model-prediction) half lives in model_tests.py.
Shared fixtures (minimal_config, engineer) live in conftest.py; `nlu` is NLU-only, below.
"""
from types import MappingProxyType
from unittest.mock import MagicMock

import pytest

from backend.modules.nlu import NLU, _ENSEMBLE_VOTERS
from backend.components.flow_stack import flow_classes, FlowStack
from backend.components.prompt_engineer import PromptEngineer
from backend.components.ambiguity_handler import AmbiguityHandler
from backend.components.world import World
from backend.components.session_scratchpad import SessionScratchpad
from backend.components.dialogue_state import DialogueState, rehydrate_flow
from schemas.ontology import FLOW_CATALOG

from schemas.ontology import FLOW_CATALOG


# ==============================================================================
# (a) DETERMINISTIC — no live LLM
# ==============================================================================

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



# react() slot-fill contract across the distinct fill paths (folded from test_nlu_module.py).
def _stub_engineer(nlu, monkeypatch, phase3_slots):
    """Replace nlu.engineer. dict → mock returns {'slots': dict}; None → raises."""
    real_apply = nlu.engineer.apply_guardrails
    real_strip = nlu.engineer._strip_nulls
    if phase3_slots is None:
        mock = MagicMock(side_effect=AssertionError(
            'Phase 3 LLM was called when it should have been skipped'))
    else:
        mock = MagicMock(return_value={'slots': phase3_slots})
    mock.apply_guardrails = real_apply
    mock._strip_nulls = real_strip
    monkeypatch.setattr(nlu, 'engineer', mock)


def _slot_observable(slot):
    """Canonical observable value of a slot, regardless of slot type.
    Used to compare against the row's `slots` expectation."""
    if hasattr(slot, 'level') and slot.level is not None:
        return slot.level
    if slot.criteria == 'multiple':
        return slot.values
    return slot.value


def _matches(actual, expected) -> bool:
    """List-of-dicts: expected items are subset matches of actual at same index.
    SourceSlot stores all 5 keys (post/sec/snip/chl/ver) per entry; the test row
    only specifies the ones it cares about."""
    if isinstance(expected, list) and expected and isinstance(expected[0], dict):
        if not isinstance(actual, list) or len(actual) != len(expected):
            return False
        return all(
            all(a.get(k) == v for k, v in e.items())
            for a, e in zip(actual, expected)
        )
    return actual == expected


# ── Test cases ──────────────────────────────────────────────────────────────
# (name, gold_dax, payload, phase3_slots, expected_flow, is_filled, slots, extras)
# - slots: dict of slot_name → expected observable value (omit slots not asserted)
# - extras: optional dict with post-react checks (e.g. dispatch-not-called)

NLU_REACT_CASES = [
    {
        'name': 'refine_snippet_payload_phase1a',
        'gold_dax': '{02B}',
        'payload': {'snippet': 'matrix mult', 'post': 'post_abc', 'section': 'sec_xyz'},
        'phase3_slots': {'feedback': ['tighten the prose']},
        'expected_flow': 'refine',
        'is_filled': True,
        'slots': {'source': [{'post': 'post_abc', 'sec': 'sec_xyz', 'snip': 'matrix mult'}]},
    },
    {
        'name': 'find_snippet_payload_phase1b',
        'gold_dax': '{001}',
        'payload': {'snippet': 'matrix mult'},
        'phase3_slots': None,  # query filled by Phase 1b, find has no other required
        'expected_flow': 'find',
        'is_filled': True,
        'slots': {'query': 'matrix mult'},
    },
    {
        'name': 'outline_proposal_payload_custom_unpack',
        'gold_dax': '{002}',
        'payload': {'proposals': [[
            {'name': 'Intro', 'description': 'open cold'},
            {'name': 'Body', 'description': 'key argument'},
        ]]},
        # Phase 1c fills sections via outline-specific unpack. Source still
        # required → Phase 3 fires to provide it.
        'phase3_slots': {'source': [{'post': 'post_abc'}]},
        'expected_flow': 'outline',
        'is_filled': True,
        'slots': {},
        'extras': {'sections_count': 2},
    },
    {
        'name': 'release_no_payload_partial_phase3',
        'gold_dax': '{004}',
        'payload': {},
        'phase3_slots': {},  # no entity → Phase 3 fires but returns empty
        'expected_flow': 'release',
        'is_filled': False,
        'slots': {},
    },
    {
        'name': 'chat_no_slots_no_payload',
        'gold_dax': '{000}',
        'payload': {},
        'phase3_slots': None,  # ChatFlow has empty self.slots — is_filled True, no LLM
        'expected_flow': 'chat',
        'is_filled': True,
        'slots': {},
    },
    {
        'name': 'audit_action_with_post',
        'gold_dax': '{13A}',
        'payload': {'post': 'post_abc'},
        'phase3_slots': None,  # audit.source filled, other slots optional
        'expected_flow': 'audit',
        'is_filled': True,
        'slots': {'source': [{'post': 'post_abc'}]},
    },
    {
        'name': 'phase2_grounding_uses_active_post',
        'gold_dax': '{02B}',  # refine
        'payload': {},
        'phase3_slots': {'feedback': ['x'], 'steps': [{'name': 'X', 'description': 'y'}]},
        'expected_flow': 'refine',
        'is_filled': True,
        'slots': {},  # source backfilled from active_post — checked via extras
        'extras': {'source_post_id': 'active-post-id'},
    },
    {
        'name': 'write_action_with_section_partial',
        'gold_dax': '{003}',
        'payload': {'post': 'post_abc', 'section': 'sec_one'},
        'phase3_slots': {},  # write has more than just source required; stays unfilled
        'expected_flow': 'write',
        'is_filled': False,
        'slots': {'source': [{'post': 'post_abc', 'sec': 'sec_one'}]},
    },
]


@pytest.mark.parametrize('case', NLU_REACT_CASES, ids=lambda c: c['name'])
def test_nlu_react(nlu, monkeypatch, case):
    # Set active_post for the Phase 2 row. react mutates the session state in place, so
    # Phase 2's `prev = self.world.current_state()` sees it.
    if case['name'] == 'phase2_grounding_uses_active_post':
        nlu.world.current_state().active_post = 'active-post-id'

    # Optional dispatch-skip assertion needs to wrap unpack_user_actions BEFORE react.
    extras = case.get('extras', {})
    if extras.get('dispatch_not_called'):
        dispatch_mock = MagicMock(wraps=nlu.unpack_user_actions)
        monkeypatch.setattr(nlu, 'unpack_user_actions', dispatch_mock)
    else:
        dispatch_mock = None

    _stub_engineer(nlu, monkeypatch, case['phase3_slots'])
    nlu.react(case['gold_dax'], case['payload'])

    # react writes belief only (no flow stacked). Reconstruct the flow from pred_slots —
    # slot_values_dict round-trips through fill_slot_values — to inspect the filled slots.
    state = nlu.world.current_state()
    assert state.pred_flows[0]['flow_name'] == case['expected_flow'], (
        f"pred_flow expected {case['expected_flow']!r} got {state.pred_flows[0]['flow_name']!r}")
    flow = flow_classes[case['expected_flow']]()
    flow.fill_slot_values(state.pred_slots)
    flow.is_filled()

    assert flow.flow_type == case['expected_flow'], (
        f"flow_type expected {case['expected_flow']!r} got {flow.flow_type!r}")
    assert flow.is_filled() == case['is_filled'], (
        f"is_filled expected {case['is_filled']} got {flow.is_filled()}")

    for slot_name, expected in case['slots'].items():
        actual = _slot_observable(flow.slots[slot_name])
        assert _matches(actual, expected), (
            f"slot {slot_name!r} expected {expected!r} got {actual!r}")

    # Extras
    if dispatch_mock is not None:
        dispatch_mock.assert_not_called()
    if 'sections_count' in extras:
        assert len(flow.slots['sections'].steps) == extras['sections_count']
    if 'source_post_id' in extras:
        src = flow.slots['source'].values
        assert any(v.get('post') == extras['source_post_id'] for v in src), (
            f'source slot missing post={extras["source_post_id"]!r}; got {src!r}')




# NLU-owned components: Session Scratchpad + Dialogue State ------------------------

class TestSessionScratchpad:
    """The scratchpad in both modes: the in-memory dict (no path) and the append-only JSONL file
    (path set — orchestrator substrate). Covers writer stamping, filtering, clear/truncate, and the
    completion-record shape."""

    @pytest.fixture
    def file_memory(self, minimal_config, tmp_path):
        return SessionScratchpad(minimal_config, scratchpad_path=str(tmp_path / 'scratchpad.jsonl'))

    # ── in-memory mode ───────────────────────────────────────────────

    def test_append_and_read_newest_last(self, file_memory):
        file_memory.write({'finding': 'first'})
        file_memory.write({'finding': 'second'})
        entries = file_memory.read()
        assert [entry['finding'] for entry in entries] == ['first', 'second']
        assert file_memory.size == 2

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




def _session_state() -> DialogueState:
    state = DialogueState(intent='Draft', dax=None, turn_count=12)
    state.conversation_id = 'convo-42'
    state.username = 'writer'
    state.goal = 'draft the agents post'
    state.confirmed = ['title']
    state.rejected = ['listicle format']
    state.workflow_step = 4
    state.grounding = {'post': 'p1', 'sec': 'intro', 'snip': '', 'chl': 'substack', 'ver': True}
    state.flow_stack = [{'name': 'compose', 'status': 'Active', 'stage': 'writing',
                         'slots': {'source': {'post': 'p1'}}}]
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
        assert document['flags'] == {'has_issues': False}

    def test_load_rehydrates_fields(self, tmp_path):
        state_file = tmp_path / 'state.json'
        _session_state().save(state_file)
        reloaded = DialogueState.load(state_file)
        assert reloaded.conversation_id == 'convo-42'
        assert reloaded.username == 'writer'
        assert reloaded.workflow_step == 4
        assert reloaded.grounding['ver'] is True
        assert reloaded.flow_stack[0]['name'] == 'compose'

    def test_old_per_turn_form_unchanged(self):
        state = DialogueState(intent='Revise', dax='3AB', turn_count=2, confidence=0.9)
        serialized = state.serialize()
        assert serialized['pred_intent'] == 'Revise'
        assert serialized['flow_name'] == '3AB'
        assert DialogueState.from_dict(serialized).serialize() == serialized




def _ops_state() -> DialogueState:
    state = DialogueState(intent='Draft', dax=None, turn_count=1)
    state.conversation_id = 'convo-ops'
    return state




class TestWriteStateOps:
    """write_state is the only writer of state.json; stack ops mutate the FlowStack passed in as
    `stack` and refresh the saved copy."""

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

    def test_op_sequence_keeps_saved_copy_current(self, tmp_path):
        """The stackon/fill/fallback/complete/pop sequence run through write_state keeps the
        saved copy and the file in step with the one flow stack."""
        path = tmp_path / 'state.json'
        state = _ops_state()
        stack = FlowStack({}, flow_classes=flow_classes)

        state.write_state(path, 'stackon', stack=stack, flow_name='outline')
        state.write_state(path, 'update_flow', stack=stack, slots={'source': [{'post': 'p1'}]},
                          stage='discovery')
        state.write_state(path, 'stackon', stack=stack, flow_name='brainstorm')
        state.write_state(path, 'fallback', stack=stack, flow_name='refine')
        state.write_state(path, 'update', grounding={'post': 'p1'})
        state.write_state(path, 'update_flow', stack=stack, status='Completed')
        state.write_state(path, 'pop_completed', stack=stack)

        assert state.flow_stack == stack.to_list()
        assert DialogueState.load(path).flow_stack == state.flow_stack

    def test_grounding_validation_raises_on_ungrounded_completion(self, tmp_path):
        path = tmp_path / 'state.json'
        state = _ops_state()
        stack = FlowStack({}, flow_classes=flow_classes)
        state.write_state(path, 'stackon', stack=stack, flow_name='outline')
        with pytest.raises(ValueError, match='grounding.post is empty'):
            state.write_state(path, 'update_flow', stack=stack, status='Completed')
        assert state.flow_stack[0]['status'] == 'Pending'  # rejected write left no trace
        assert DialogueState.load(path).flow_stack[0]['status'] == 'Pending'

    def test_grounding_validation_passes_once_post_is_set(self, tmp_path):
        path = tmp_path / 'state.json'
        state = _ops_state()
        stack = FlowStack({}, flow_classes=flow_classes)
        state.write_state(path, 'stackon', stack=stack, flow_name='outline')
        state.write_state(path, 'update', grounding={'post': 'p1'})
        state.write_state(path, 'update_flow', stack=stack, status='Completed')
        assert state.flow_stack[0]['status'] == 'Completed'

    def test_update_flow_normalizes_llm_shaped_slot_values(self, tmp_path):
        """Orchestrator-authored slot values: bare strings for checklist items and source
        entities, and a bare item in place of a list, all coerce instead of crashing."""
        path = tmp_path / 'state.json'
        state = _ops_state()
        stack = FlowStack({}, flow_classes=flow_classes)
        state.write_state(path, 'stackon', stack=stack, flow_name='outline')
        state.write_state(path, 'update_flow', stack=stack,
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
        stack = FlowStack({}, flow_classes=flow_classes)
        state.write_state(path, 'stackon', stack=stack, flow_name='chat')
        state.write_state(path, 'update_flow', stack=stack, status='Completed')
        state.write_state(path, 'pop_completed', stack=stack)
        state.write_state(path, 'stackon', stack=stack, flow_name='find')
        state.write_state(path, 'update_flow', stack=stack, status='Completed')
        assert state.flow_stack[0]['status'] == 'Completed'


# ==============================================================================
# NLU schema + slot-declaration lints (offline, no LLM) — folded from test_artifacts.py.
# Consolidated from per-flow parametrization into single looping checks (same drift coverage,
# far fewer test instances). These catch config drift, not function outputs.
# ==============================================================================

import inspect
import json
import re

from backend.components.flow_stack.slots import ExactSlot
from backend.modules.nlu import _intent_schema, _flow_detection_schema, _fill_slots_schema
from backend.prompts.nlu import PROMPTS as _SLOT_FILL_PROMPTS

_BANNED_NUMBER_KEYS = ('minimum', 'maximum', 'exclusiveMinimum', 'exclusiveMaximum')


def _walk_schema(node, path=''):
    if not isinstance(node, dict):
        return
    yield path, node
    for key, val in node.items():
        if key == 'properties' and isinstance(val, dict):
            for prop, sub in val.items():
                yield from _walk_schema(sub, f'{path}.properties.{prop}')
        elif key == 'items':
            yield from _walk_schema(val, f'{path}.items')
        elif key == 'additionalProperties' and isinstance(val, dict):
            yield from _walk_schema(val, f'{path}.additionalProperties')
        elif key in ('anyOf', 'oneOf', 'allOf') and isinstance(val, list):
            for idx, sub in enumerate(val):
                yield from _walk_schema(sub, f'{path}.{key}[{idx}]')


def _lint_schema(schema):
    violations = []
    for path, node in _walk_schema(schema):
        if node.get('type') == 'number':
            for bad in _BANNED_NUMBER_KEYS:
                if bad in node:
                    violations.append((path, 'A', f'`{bad}` not supported on number type'))
        if 'enum' in node and isinstance(node.get('type'), list):
            violations.append((path, 'B', f'enum + list-valued type {node["type"]!r}'))
        if isinstance(node.get('additionalProperties'), dict):
            violations.append((path, 'C', 'additionalProperties is a schema object'))
    return violations


_SCHEMA_REPRESENTATIVES = ['outline', 'audit', 'release', 'compare', 'schedule']


def test_belief_schemas_valid():
    """The three NLU belief schemas obey the offline Anthropic structured-output rules. Rules are
    flow-set-agnostic, so all-flows detect + a representative slot-family spread covers every branch."""
    assert _lint_schema(_intent_schema()) == []
    assert _lint_schema(_flow_detection_schema(list(flow_classes))) == []
    for name in _SCHEMA_REPRESENTATIVES:
        assert _lint_schema(_fill_slots_schema(flow_classes[name]())) == [], name


def test_schema_linter_detects_its_own_rules():
    """The linter must flag each rule it enforces — a silent linter passes broken schemas."""
    a = {'type': 'object', 'properties': {'n': {'type': 'number', 'minimum': 0}}}
    b = {'type': 'object', 'properties': {'x': {'type': ['string', 'null'], 'enum': ['a', None]}}}
    c = {'type': 'object', 'additionalProperties': {'type': 'string'}}
    assert any(r == 'A' for _, r, _ in _lint_schema(a))
    assert any(r == 'B' for _, r, _ in _lint_schema(b))
    assert any(r == 'C' for _, r, _ in _lint_schema(c))


def test_entity_slot_is_a_declared_slot():
    """Every non-Internal flow's entity_slot names a real key in flow.slots (drift found after a
    RemoveFlow crash where entity_slot='source' but the slot dict declared 'target')."""
    bad = []
    for name, cls in flow_classes.items():
        flow = cls()
        if flow.parent_type == 'Internal':
            continue
        if flow.entity_slot not in flow.slots:
            bad.append((name, flow.entity_slot, sorted(flow.slots)))
    assert not bad, f'entity_slot not in flow.slots: {bad}'


def test_target_slot_is_never_an_exact_slot():
    """The 'target' slot key must never be an ExactSlot — it carries an entity-grounding role that
    needs a shape-explicit class (TargetSlot / RemovalSlot / DictionarySlot)."""
    bad = []
    for name, cls in flow_classes.items():
        slots = cls().slots
        if 'target' in slots and isinstance(slots['target'], ExactSlot):
            bad.append(name)
    assert not bad, f"slots['target'] is ExactSlot in: {bad}"


_VALUES_PATTERNS = (
    re.compile(r"values\.get\(\s*['\"]([a-z_]+)['\"]"),
    re.compile(r"values\[\s*['\"]([a-z_]+)['\"]\s*\]"),
    re.compile(r"['\"]([a-z_]+)['\"]\s+in\s+values"),
)


def test_fill_slot_values_reads_only_declared_keys():
    """No flow.fill_slot_values reads a `values[...]` key absent from flow.slots (else NLU output
    for that key is silently dropped)."""
    bad = []
    for name, cls in flow_classes.items():
        flow = cls()
        read = set()
        for pat in _VALUES_PATTERNS:
            read.update(pat.findall(inspect.getsource(flow.fill_slot_values)))
        bogus = read - set(flow.slots)
        if bogus:
            bad.append((name, sorted(bogus)))
    assert not bad, f'fill_slot_values reads undeclared keys: {bad}'


_HEADING_PATTERN = re.compile(r'^###\s+([a-z_]+)\s+\(', re.MULTILINE)
_FENCED_JSON = re.compile(r'```json\s*(\{.*?\})\s*```', re.DOTALL)


def test_prompt_slot_headings_match_flow_slots():
    """For flows whose NLU slot-fill prompt hand-authors `### name (priority)` headings, the headings
    and flow.slots keys match exactly (procedural-rendering flows can't drift, so are skipped)."""
    bad = []
    for name, prompt in _SLOT_FILL_PROMPTS.items():
        slots_md = (prompt.get('slots') or '').strip()
        if not slots_md or name not in flow_classes:
            continue
        headings = set(_HEADING_PATTERN.findall(slots_md))
        declared = set(flow_classes[name]().slots)
        if headings != declared:
            bad.append((name, {'bogus': sorted(headings - declared),
                               'missing': sorted(declared - headings)}))
    assert not bad, f'prompt headings vs flow.slots mismatch: {bad}'


def test_few_shot_example_keys_match_flow_slots():
    """Top-level `slots` keys in fenced ```json``` example blocks must be declared in flow.slots
    (catches prose examples naming a stale slot key)."""
    bad = []
    for name, cls in flow_classes.items():
        examples = (_SLOT_FILL_PROMPTS.get(name) or {}).get('examples', '') or ''
        declared = set(cls().slots)
        for block in _FENCED_JSON.findall(examples):
            try:
                slots_obj = json.loads(block).get('slots') or {}
            except json.JSONDecodeError:
                continue
            if isinstance(slots_obj, dict) and set(slots_obj) - declared:
                bad.append((name, sorted(set(slots_obj) - declared)))
    assert not bad, f'example slot keys not in flow.slots: {bad}'
