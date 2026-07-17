"""NLU deterministic unit tests (the Heart). No live model calls — the free tier.

Covers NLU-owned components: ensemble tally/routing, the react() slot-fill contract, historical
regressions, the Session Scratchpad, the Dialogue State (state.json serialization + belief/grounding
write ops). The probabilistic (model-prediction) half lives in model_tests.py.
Shared fixtures (minimal_config, engineer) live in conftest.py; `nlu` is NLU-only, below.
"""
from unittest.mock import MagicMock

import pytest

from backend.modules.nlu import NLU
from backend.modules.pex import PEX
from backend.modules.mem import MEM
from backend.components.flow_stack import flow_classes, FlowStack
from backend.components.prompt_engineer import PromptEngineer
from backend.components.world import World
from backend.components.session_scratchpad import SessionScratchpad
from backend.components.dialogue_state import DialogueState
from schemas.ontology import FLOW_ONTOLOGY
from utils.helper import flow2dax


# ==============================================================================
# (a) DETERMINISTIC — no live LLM
# ==============================================================================

@pytest.fixture
def nlu(minimal_config, tmp_path):
    """Real module wiring (mirrors Assistant.__init__): NLU/PEX/MEM each build their own
    components, the World holds the shared references. Only the LLM call sites on nlu.engineer
    get mocked per-test, so every conditional branch in NLU stays reachable. The fixture seeds
    a User action turn so Phase 1c (last_user_turn.turn_type == 'action') is exercisable by
    default, and attaches a tmp scratchpad since validate writes an entry every turn."""
    engineer = PromptEngineer(minimal_config)
    nlu = NLU(minimal_config, engineer)
    pex = PEX(minimal_config, engineer)
    mem = MEM(minimal_config, engineer, 'test_user')
    world = World(minimal_config, nlu, pex, mem)
    nlu.world = world
    pex.world = world
    mem.world = world
    world.context.add_turn('User', '', 'action')
    world.scratchpad.attach(tmp_path / 'scratchpad.jsonl')
    return nlu




class TestAmbiguityHandler:
    """The Ambiguity Handler surface: `present` is a bool attribute, get_level() reports the
    greatest recognized level, resolve() takes an explanation, and NLU.recover drives
    recover(prefs, scratchpad) and records the attempt on the scratchpad."""

    def test_recognize_sets_present_and_level(self, nlu):
        nlu.ambiguity_handler.recognize('specific', {'missing': 'x'})
        assert nlu.ambiguity_handler.is_present is True
        assert nlu.ambiguity_handler.get_level() == 'specific'
        nlu.ambiguity_handler.resolve()
        assert nlu.ambiguity_handler.is_present is False

    def test_resolve_takes_explanation(self, nlu):
        nlu.ambiguity_handler.recognize('partial', {'missing': 'source'}, observation='which post?')
        nlu.ambiguity_handler.resolve('found in prefs')
        assert nlu.ambiguity_handler.is_present is False
        assert nlu.ambiguity_handler.metadata == {}
        assert nlu.ambiguity_handler.observation == ''

    def test_recover_resolves_from_preference(self, nlu, tmp_path):
        nlu.world.scratchpad.attach(tmp_path / 'scratchpad.jsonl')
        nlu.world.prefs.store_preference('channel', 'substack')
        nlu.ambiguity_handler.recognize('partial', {'missing': 'channel'})
        result = nlu.recover()
        assert result == {'recovery': 'substack'}
        assert nlu.ambiguity_handler.is_present is False  # resolved from memory, no user escalation
        recovery = nlu.world.scratchpad.read(origin='recovery')
        assert recovery[-1]['found'] == 'substack' and recovery[-1]['version'] == 1

    def test_recover_stays_pending_when_nothing_found(self, nlu, tmp_path):
        nlu.world.scratchpad.attach(tmp_path / 'scratchpad.jsonl')
        nlu.ambiguity_handler.recognize('partial', {'missing': 'channel'})
        result = nlu.recover()
        assert result == {'recovery': 'channel'}  # the missing slot name comes back unresolved
        assert nlu.ambiguity_handler.is_present is True  # nothing found — still pending
        recovery = nlu.world.scratchpad.read(origin='recovery')
        assert recovery[-1]['missing'] == 'channel'  # the attempt is recorded either way


class TestEnsembleVoting:
    """Tally + routing math for the NLU ensemble voter. Config invariants and
    bare-routing tests removed — they pass on typos, not behavior."""

    def test_two_agree_one_dissents(self, nlu):
        votes = [
            {'flows': ['chat'], '_model': 'claude', '_tier': 'med'},
            {'flows': ['brainstorm'], '_model': 'gemini', '_tier': 'med'},
            {'flows': ['brainstorm'], '_model': 'gpt', '_tier': 'med'},
        ]
        result = nlu.dialogue_state._tally_votes(votes)
        assert result['flows'] == ['brainstorm']    # chat at 1/3 drops from the survivors
        assert result['confidence'] == pytest.approx(0.7)    # majority, not unanimous

    def test_graceful_two_voter_degradation(self, nlu):
        votes = [
            {'flows': ['chat'], '_model': 'claude', '_tier': 'med'},
            {'flows': ['chat'], '_model': 'gemini', '_tier': 'med'},
        ]
        result = nlu.dialogue_state._tally_votes(votes)
        assert result['flows'] == ['chat']
        assert result['confidence'] == pytest.approx(0.9)    # all remaining voters agree

    # -- _detect_flow (mocked LLM) -----------------------------------------

    def test_one_voter_fails(self, nlu):
        def mock_call(prompt, task='skill', family='', tier='med', max_tokens=1024, schema=None):
            if family == 'claude':
                raise RuntimeError('voter down')
            return {'flows': ['chat']}

        nlu.engineer = MagicMock(side_effect=mock_call)
        nlu.dialogue_state.pred_intent = 'Converse'
        result = nlu.dialogue_state.detect_flows(nlu.engineer, nlu.world.context, 'hello')

        assert result['flows'] == ['chat']
        assert result['confidence'] == pytest.approx(0.9)

    def test_all_voters_fail(self, nlu):
        def mock_call(prompt, task='skill', family='', tier='med', max_tokens=1024, schema=None):
            raise RuntimeError('All down')

        nlu.engineer = MagicMock(side_effect=mock_call)
        nlu.dialogue_state.pred_intent = 'Converse'
        result = nlu.dialogue_state.detect_flows(nlu.engineer, nlu.world.context, 'hello')

        assert result['flows'] == ['chat']
        assert result['confidence'] == 0.3

    def test_split_escalates_to_high_voters(self, nlu):
        """The three mediums all disagree → round 2 fires and the tally reruns over 5 votes."""
        flows = {('claude', 'med'): 'chat', ('gemini', 'med'): 'brainstorm',
                 ('gpt', 'med'): 'outline',
                 ('gemini', 'high'): 'brainstorm', ('claude', 'high'): 'brainstorm'}

        def mock_call(prompt, task='skill', family='', tier='med', max_tokens=1024, schema=None):
            return {'flows': [flows[(family, tier)]]}

        nlu.engineer = MagicMock(side_effect=mock_call)
        nlu.dialogue_state.pred_intent = 'Draft'
        result = nlu.dialogue_state.detect_flows(nlu.engineer, nlu.world.context, 'give me ideas')

        assert result['flows'][0] == 'brainstorm'
        # 3 of 5 across 2 intents (Converse/Draft) = 0.7, +0.1 for the high pair agreeing.
        assert result['confidence'] == pytest.approx(0.8)


def _detection(pairs, confidence):
    """Build a detection dict from (flow_name, weight) pairs at a given top-1 confidence.
    `flows` carries the single survivor — multi-survivor plan detections build their dict
    by hand."""
    pred_flows = [{'name': name, 'dax': flow2dax(name), 'confidence': w} for name, w in pairs]
    return {'flows': [pairs[0][0]], 'confidence': confidence, 'pred_flows': pred_flows}


def _stub_think_internals(nlu, detection):
    """Stub everything think() touches besides detection, so the routing logic runs alone."""
    nlu.dialogue_state.detect_flows = MagicMock(**detection)
    def _classify(*args, **kwargs):
        nlu.dialogue_state.pred_intent = 'Draft'
        return 'Draft'
    nlu.dialogue_state.classify_intent = MagicMock(side_effect=_classify)
    nlu.dialogue_state.fill_slots = MagicMock()
    nlu._repair_slots = MagicMock()


class TestThinkDispatch:
    """think() detects first and only pays for a classify + narrowed re-detect on a low-confidence
    cross-intent tie (§3.1.1; predict() was folded into think 2026-07-08). _intent_split is the
    boolean that governs that escalation; the working intent is read off
    `dialogue_state.pred_intent`, never passed as a parameter (round 3.4)."""

    def test_think_skips_classify_on_confident_detection(self, nlu):
        _stub_think_internals(nlu, {'return_value': _detection([('outline', 0.9)], 0.9)})
        state = nlu.think('draft me an outline')
        nlu.dialogue_state.classify_intent.assert_not_called()
        assert state.pred_flows[0]['name'] == 'outline'

    def test_think_escalates_on_low_conf_cross_intent(self, nlu):
        low = _detection([('outline', 0.5), ('find', 0.5)], 0.4)
        high = _detection([('compose', 0.8)], 0.8)
        _stub_think_internals(nlu, {'side_effect': [low, high]})
        state = nlu.think('do the thing')
        nlu.dialogue_state.classify_intent.assert_called_once()
        assert nlu.dialogue_state.detect_flows.call_count == 2
        assert nlu.dialogue_state.pred_intent == 'Draft'    # the tie-break writes the belief
        assert 'Draft' in nlu.dialogue_state.detect_flows.call_args.args[3]  # re-detect snippet
        assert state.pred_flows[0]['name'] == 'compose'

    def test_think_reads_pred_intent_for_detection(self, nlu):
        _stub_think_internals(nlu, {'return_value': _detection([('rework', 0.9)], 0.9)})
        nlu.dialogue_state.pred_intent = 'Revise'
        nlu.think('polish the intro')
        assert nlu.dialogue_state.detect_flows.call_args.args[2] == 'polish the intro'
        assert 'Revise' in nlu.dialogue_state.detect_flows.call_args.args[3]  # check's snippet

    def test_intent_split_true_when_flows_span_intents_and_low_conf(self, nlu):
        assert nlu._intent_split(_detection([('outline', 0.5), ('find', 0.5)], 0.4)) is True

    def test_intent_split_false_when_confident(self, nlu):
        assert nlu._intent_split(_detection([('outline', 0.5), ('find', 0.5)], 0.9)) is False

    def test_intent_split_false_when_single_intent(self, nlu):
        assert nlu._intent_split(_detection([('outline', 0.6), ('compose', 0.4)], 0.4)) is False

    def test_classify_intent_still_callable(self, nlu):
        engineer = MagicMock()
        engineer.typesafe.return_value = {
            'intent': {'choice': 'Revise', 'confidence': 0.91},
            'has_plan': {'noul': 0.1}, 'needs_clarify': {'noul': 0.2}}
        state = nlu.dialogue_state
        assert state.classify_intent(engineer, nlu.world.context, 'polish the intro') == 'Revise'
        assert state.pred_intent == 'Revise'

    def test_candidate_names_empty_hint_is_full_ontology(self, nlu):
        assert nlu.dialogue_state._candidate_names('') == list(FLOW_ONTOLOGY)

    def test_candidate_names_hint_narrows_to_intent(self, nlu):
        names = set(nlu.dialogue_state._candidate_names('Draft'))
        assert {'outline', 'compose', 'refine', 'brainstorm'} <= names
        assert 'release' not in names

    def test_abstention_declares_ambiguity_without_stacking(self, nlu):
        """Every voter abstained (the Clarify path) — think stacks nothing, the belief stays
        empty, and the general ambiguity raises the clarification downstream."""
        abstain = {'flows': [], 'confidence': 0.0, 'pred_flows': []}
        _stub_think_internals(nlu, {'return_value': abstain})
        state = nlu.think('that thing')
        assert state.pred_flows == []              # a deliberate abstention stays empty
        assert nlu.world.flows.get_flow() is None  # nothing stacked
        assert nlu.ambiguity_handler.is_present is True
        assert nlu.ambiguity_handler.get_level() == 'general'

    def test_generic_flow_prompt_used_when_no_hint(self):
        from backend.prompts.for_experts import build_flow_prompt
        prompt = build_flow_prompt('publish it', '', 'history', 'ontology')
        assert 'across ALL' in prompt


# ═══════════════════════════════════════════════════════════════════
# NLU react()
# ═══════════════════════════════════════════════════════════════════



class TestNLUSpecificRegressions:
    """NLU regressions kept here separately from the module-level table in
    test_nlu_module.py — these test specific historical bugs, not module contracts."""

    def test_all_action_dax_codes_resolve(self):
        """FLOW_ONTOLOGY dax codes must round-trip through dax2flow. Catches ontology
        drift where a flow's dax doesn't match the dax2flow lookup."""
        from utils.helper import dax2flow
        for flow_name, cat in FLOW_ONTOLOGY.items():
            dax = cat['dax']
            resolved = dax2flow(dax)
            assert resolved == flow_name, \
                f'dax2flow({dax!r}) returned {resolved!r}, expected {flow_name!r}'

    def test_refine_steps_unpacks_dict_kwargs(self):
        """Regression: under the old generic fill path, slot.add_one(item) bound the whole
        {name, description} dict to the positional `name` arg, producing nested
        {name: {name: '...'}}. The per-flow refactor uses slot.add_one(**item)."""
        flow = flow_classes['refine']()
        flow.fill_slot_values({
            'source': [{'post': 'abc12345'}],
            'steps': [{'name': "Remove X", 'description': 'why'}],
        })
        assert flow.slots['steps'].steps[0] == {'name': "Remove X", 'description': 'why', 'checked': False}

    def test_fill_slots_retries_after_parse_failure(self, nlu):
        """Round 3.7: a truncated response makes the engineer raise ValueError; _fill_slots
        retries once and keeps the second, well-formed fill."""
        flow = flow_classes['refine']()
        good = {'reasoning': 'r', 'slots': {'source': [{'post': 'abc12345'}]}}
        mock = MagicMock(side_effect=[ValueError('unparseable'), good])
        mock._strip_nulls = nlu.engineer._strip_nulls
        nlu.engineer = mock
        nlu.dialogue_state.fill_slots(nlu.engineer, nlu.world.context, flow, {}, nlu.ambiguity_handler)
        assert flow.slots['source'].values
        assert mock.call_count == 2

    def test_fill_slots_gives_up_after_two_parse_failures(self, nlu):
        """Round 3.7: two consecutive parse failures hit the final-resort path — the flow
        stays unfilled, no exception escapes."""
        flow = flow_classes['refine']()
        mock = MagicMock(side_effect=ValueError('unparseable'))
        mock._strip_nulls = nlu.engineer._strip_nulls
        nlu.engineer = mock
        nlu.dialogue_state.fill_slots(nlu.engineer, nlu.world.context, flow, {}, nlu.ambiguity_handler)
        assert not flow.slots['source'].values
        assert mock.call_count == 2


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
    real_strip = nlu.engineer._strip_nulls
    if phase3_slots is None:
        mock = MagicMock(side_effect=AssertionError(
            'Phase 3 LLM was called when it should have been skipped'))
    else:
        mock = MagicMock(return_value={'slots': phase3_slots})
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
# - extras: optional dict with post-react checks (e.g. a tool was not called)

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
        'name': 'phase2_grounding_uses_grounded_post',
        'gold_dax': '{02B}',  # refine
        'payload': {},
        'phase3_slots': {'feedback': ['x'], 'steps': [{'name': 'X', 'description': 'y'}]},
        'expected_flow': 'refine',
        'is_filled': True,
        'slots': {},  # source backfilled from grounding — checked via extras
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
    # Set grounding for the Phase 2 row. react mutates the ONE session state in place, so
    # Phase 2's `prev = self.world.state` sees it.
    if case['name'] == 'phase2_grounding_uses_grounded_post':
        nlu.world.state.set_active_entity(post='active-post-id', ver=True)
    extras = case.get('extras', {})

    _stub_engineer(nlu, monkeypatch, case['phase3_slots'])
    nlu.react(case['gold_dax'], case['payload'])

    # react stacks the detected flow with the filled slots — inspect it straight off the stack.
    state = nlu.world.state
    assert state.pred_flows[0]['name'] == case['expected_flow'], (
        f"pred_flow expected {case['expected_flow']!r} got {state.pred_flows[0]['name']!r}")
    flow = nlu.world.flows.get_flow()

    assert flow.flow_type == case['expected_flow'], (
        f"flow_type expected {case['expected_flow']!r} got {flow.flow_type!r}")
    assert flow.is_filled() == case['is_filled'], (
        f"is_filled expected {case['is_filled']} got {flow.is_filled()}")

    for slot_name, expected in case['slots'].items():
        actual = _slot_observable(flow.slots[slot_name])
        assert _matches(actual, expected), (
            f"slot {slot_name!r} expected {expected!r} got {actual!r}")

    # Extras
    if 'sections_count' in extras:
        assert len(flow.slots['sections'].steps) == extras['sections_count']
    if 'source_post_id' in extras:
        src = flow.slots['source'].values
        assert any(v.get('post') == extras['source_post_id'] for v in src), (
            f'source slot missing post={extras["source_post_id"]!r}; got {src!r}')




# NLU-owned components: Session Scratchpad + Dialogue State ------------------------

class TestSessionScratchpad:
    """The scratchpad — one storage mode: the append-only JSONL file in the session dir. Covers
    origin stamping, filtering, clear/truncate, and the completion-record shape."""

    @pytest.fixture
    def file_memory(self, tmp_path):
        return SessionScratchpad(scratchpad_path=str(tmp_path / 'scratchpad.jsonl'))

    def test_append_and_read_newest_last(self, file_memory):
        file_memory.append_entry('orchestrator', {'finding': 'first'})
        file_memory.append_entry('orchestrator', {'finding': 'second'})
        entries = file_memory.read()
        assert [entry['finding'] for entry in entries] == ['first', 'second']
        assert file_memory.size == 2

    def test_entry_dict_is_stamped_and_appended(self, file_memory):
        file_memory.append_entry('repair', {'note': 'bad outline'})
        entries = file_memory.read()
        assert entries == [{'note': 'bad outline', 'origin': 'repair'}]

    def test_clear_truncates_file(self, file_memory):
        file_memory.append_entry('orchestrator', {'finding': 'gone soon'})
        file_memory.clear()
        assert file_memory.read() == []
        assert file_memory.size == 0

    def test_entries_persist_on_disk(self, tmp_path):
        path = tmp_path / 'scratchpad.jsonl'
        SessionScratchpad(scratchpad_path=str(path)).append_entry('orchestrator', {'note': 'kept'})
        reopened = SessionScratchpad(scratchpad_path=str(path))
        assert reopened.read() == [{'note': 'kept', 'origin': 'orchestrator'}]

    # ── origin stamping (decision 17) ────────────────────────────────

    def test_forged_origin_is_overwritten(self, file_memory):
        file_memory.append_entry('audit', {'finding': 'x', 'origin': 'forged'})
        assert file_memory.read()[0]['origin'] == 'audit'

    # ── read filters ─────────────────────────────────────────────────

    def test_filter_by_origin(self, file_memory):
        file_memory.append_entry('compose', {'finding': 'a'})
        file_memory.append_entry('orchestrator', {'finding': 'b'})
        file_memory.append_entry('compose', {'finding': 'c'})
        entries = file_memory.read(origin='compose')
        assert [entry['finding'] for entry in entries] == ['a', 'c']

    def test_filter_by_keys_present(self, file_memory):
        file_memory.append_entry('compose', {'summary': 's', 'metadata': {}})
        file_memory.append_entry('orchestrator', {'finding': 'loose note'})
        entries = file_memory.read(keys=['summary', 'metadata'])
        assert len(entries) == 1
        assert entries[0]['origin'] == 'compose'

    def test_filters_combine(self, file_memory):
        file_memory.append_entry('compose', {'summary': 's'})
        file_memory.append_entry('audit', {'summary': 's'})
        file_memory.append_entry('compose', {'finding': 'x'})
        entries = file_memory.read(origin='compose', keys=['summary'])
        assert entries == [{'summary': 's', 'origin': 'compose'}]

    # ── NLU-only mutation: origin + turn_number is the unique ID ─────

    def test_amend_entry_modifies_in_place(self, file_memory):
        file_memory.append_entry('audit', {'version': 1, 'turn_number': 3, 'used_count': 0,
                                           'note': 'v1'})
        file_memory.append_entry('find', {'version': 1, 'turn_number': 5, 'used_count': 0})
        entry = file_memory.read(origin='audit')[-1]
        file_memory.amend_entry('audit', 3, {**entry, 'note': 'v2'})
        assert file_memory.size == 2  # modified in place — no extra line
        assert file_memory.read(origin='audit') == [{'origin': 'audit', 'version': 1,
                                                     'turn_number': 3, 'used_count': 0, 'note': 'v2'}]

    def test_prune_entry_removes_by_id(self, file_memory):
        file_memory.append_entry('audit', {'version': 1, 'turn_number': 3, 'used_count': 0})
        file_memory.append_entry('find', {'version': 1, 'turn_number': 5, 'used_count': 0})
        file_memory.prune_entry('audit', 3)
        assert file_memory.read(origin='audit') == [] and file_memory.size == 1

    def test_amend_entry_unknown_id_raises(self, file_memory):
        file_memory.append_entry('audit', {'version': 1, 'turn_number': 3, 'used_count': 0})
        with pytest.raises(KeyError):
            file_memory.amend_entry('audit', 7, {'note': 'x'})


class TestScratchpadReview:
    """NLU.review_scratchpad — the synchronous review pass at NLU's turn point: repairs entries
    missing the contract fields (version / turn_number / used_count) losslessly and reports
    diagnostics; semantic review stays designed-not-built."""

    def test_review_repairs_nonconforming_entry(self, nlu, tmp_path):
        nlu.world.scratchpad.attach(tmp_path / 'scratchpad.jsonl')
        nlu.world.scratchpad.append_entry('legacy', {'note': 'predates the contract'})
        report = nlu.review_scratchpad()
        assert report['reviewed'] is True and report['repaired'] == 1
        newest = nlu.world.scratchpad.read(origin='legacy')[-1]
        assert newest['version'] == 1 and newest['used_count'] == 0
        assert newest['note'] == 'predates the contract'  # lossless repair

    def test_review_leaves_conforming_pad_alone(self, nlu, tmp_path):
        nlu.world.scratchpad.attach(tmp_path / 'scratchpad.jsonl')
        nlu.world.scratchpad.append_entry('find', {'version': 1, 'turn_number': 1, 'used_count': 0})
        report = nlu.review_scratchpad()
        assert report == {'reviewed': True, 'size': 1, 'repaired': 0}




def _session_state() -> DialogueState:
    state = DialogueState({})
    state.pred_intent = 'Draft'
    state.pred_flows = [{'name': 'compose', 'dax': flow2dax('compose'), 'confidence': 0.9}]
    state.turn_count = 12
    state.conversation_id = 'convo-42'
    state.username = 'writer'
    state.set_active_entity(post='p1', sec='intro', chl='substack', ver=True)
    return state




class TestSessionStateFile:
    """File-backed DialogueState: the state.json document (session / beliefs / grounding)
    and its save/load round trip. The flow stack lives on pex.flow_stack only — PEX attaches
    it to tool documents at read time; it is never stored or saved on the state."""

    def test_round_trip_identical_dict(self, tmp_path):
        state = _session_state()
        state_file = tmp_path / 'state.json'
        state.save(state_file)
        reloaded = DialogueState.load(state_file)
        assert reloaded.read_state() == state.read_state()

    def test_document_blocks_and_grounding_parts(self):
        document = _session_state().read_state()
        assert list(document) == ['session', 'beliefs', 'grounding']
        assert list(document['grounding']) == ['choices', 'notes', 'entities']
        assert document['session']['turn_count'] == 12
        assert document['beliefs']['intent'] == 'Draft'

    def test_load_rehydrates_fields(self, tmp_path):
        state_file = tmp_path / 'state.json'
        _session_state().save(state_file)
        reloaded = DialogueState.load(state_file)
        assert reloaded.conversation_id == 'convo-42'
        assert reloaded.username == 'writer'
        assert reloaded.turn_count == 12
        assert reloaded.flow_name() == 'compose'
        assert reloaded.get_active_entity()['ver'] is True


# ==============================================================================
# NLU schema + slot-declaration lints (offline, no LLM) — folded from test_artifacts.py.
# Consolidated from per-flow parametrization into single looping checks (same drift coverage,
# far fewer test instances). These catch config drift, not function outputs.
# ==============================================================================

import inspect
import json
import re

from backend.components.flow_stack.slots import ExactSlot
from backend.components.dialogue_state import _flow_detection_schema, _fill_slots_schema
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
    """The NLU belief schemas obey the offline Anthropic structured-output rules (intent runs
    on TypeSafe now — no schema to lint). Rules are flow-set-agnostic, so all-flows detect + a
    representative slot-family spread covers every branch."""
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
