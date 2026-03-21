from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from types import MappingProxyType
from typing import TYPE_CHECKING

from backend.components.context_coordinator import ContextCoordinator
from backend.components.dialogue_state import DialogueState
from backend.components.ambiguity_handler import AmbiguityHandler
from backend.components.prompt_engineer import PromptEngineer
from schemas.ontology import FLOW_CATALOG, Intent

if TYPE_CHECKING:
    from backend.components.world import World


_SHORTCUTS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'^(hi|hello|hey)\b', re.I), 'chat'),
    (re.compile(r'^(help|what can you do)\b', re.I), 'chat'),
    (re.compile(r'^(bye|goodbye|exit|quit)\b', re.I), 'chat'),
    (re.compile(r'\bwhat.*(next|now)\b', re.I), 'next'),
    (re.compile(r'\bstatus\b', re.I), 'status'),
]

_DAX_LOOKUP: dict[str, str] = {}
for _fn, _flow in FLOW_CATALOG.items():
    _dax_raw = _flow['dax'].strip('{}').upper()
    _DAX_LOOKUP[_dax_raw] = _fn

_DEV_PATTERN = re.compile(r'^/([0-9A-Fa-f]{3})\b\s*(.*)', re.DOTALL)

_NUM_VOTERS = 2

_ACTION_PATTERN = re.compile(
    r'^(yes|yeah|yep|yup|ok|okay|sure|confirm|approve|accept|go ahead|'
    r'no|nope|nah|cancel|dismiss|decline|reject|skip|nevermind|done|back)\s*[.!?]*$',
    re.I,
)


class NLU:

    def __init__(self, config:MappingProxyType, ambiguity:AmbiguityHandler,
                 engineer:PromptEngineer, world:'World'):
        self.config = config
        self.ambiguity = ambiguity
        self.engineer = engineer
        self.world = world
        self.flow_stack = world.flow_stack

    # ── Entry point ───────────────────────────────────────────────────

    def understand(self, user_text:str, context:ContextCoordinator,
                   gold_dax:str|None=None) -> DialogueState:
        prep = self.prepare(user_text)
        if prep is not None:
            return self.validate(prep)

        if gold_dax or self._is_user_action(user_text):
            state = self.react(user_text, context, gold_dax)
        elif self._should_contemplate():
            state = self.contemplate(user_text, context)
        else:
            state = self.think(user_text, context)

        return self.validate(state)

    # ── Public operational modes ──────────────────────────────────────

    def prepare(self, user_text:str) -> DialogueState|None:
        text = user_text.strip()

        if not text:
            state = self._build_state('chat', 1.0)
            self._push_or_get('chat')
            return state

        if len(text) < 2:
            state = self._build_state('chat', 0.8)
            self._push_or_get('chat')
            return state

        match = _DEV_PATTERN.match(text)
        if match:
            dax_code = match.group(1).upper()
            flow_name = _DAX_LOOKUP.get(dax_code)
            if flow_name:
                state = self._build_state(flow_name, 0.99)
                self._push_or_get(flow_name)
                return state

        for pattern, flow_name in _SHORTCUTS:
            if pattern.search(text):
                flow = FLOW_CATALOG.get(flow_name)
                if flow:
                    state = self._build_state(flow_name, 1.0)
                    self._push_or_get(flow_name)
                    return state
        return None

    def think(self, user_text:str, context:ContextCoordinator) -> DialogueState:
        result = self.predict(user_text, context)
        flow_name = result['flow_name']
        slots = result.get('slots', {})

        state = self._build_state(flow_name, result['confidence'])
        state.pred_flows = [
            {'flow_name': result['flow_name'], 'confidence': result['confidence']},
        ]

        self._push_or_get(flow_name, slots)

        if self.ambiguity.needs_clarification(state.confidence):
            self.ambiguity.declare(
                'general',
                metadata={'top_detection': state.flow_name},
                observation=f'Low confidence ({state.confidence:.2f}) on '
                            f'flow "{state.flow_name}"',
            )
        return state

    def contemplate(self, user_text:str, context:ContextCoordinator) -> DialogueState:
        prev = self.world.current_state()
        failed_flow = prev.flow_name if prev else None
        failure_reason = self.ambiguity.observation or ''

        detection = self._check_routing(user_text, context, failed_flow, failure_reason)
        flow_name = detection['flow_name']

        flow = FLOW_CATALOG.get(flow_name, {})
        flow_intent = flow.get('intent', Intent.CONVERSE).value

        if flow_intent not in ('Converse', 'Plan') and flow.get('slots'):
            slots = self._fill_slots(user_text, context, flow_name)
        else:
            slots = detection.get('slots', {})

        state = self._build_state(flow_name, detection['confidence'])
        self._push_or_get(flow_name, slots)
        return state

    def react(self, user_text:str, context:ContextCoordinator,
              gold_dax:str|None=None) -> DialogueState:
        if gold_dax:
            return self._resolve_gold_dax(gold_dax, user_text)
        result = self._process_action(user_text)
        flow_name = result['flow_name']
        slots = result.get('slots', {})

        state = self._build_state(flow_name, result.get('confidence', 1.0))
        self._push_or_get(flow_name, slots)
        return state

    def validate(self, state:DialogueState) -> DialogueState:
        flow = FLOW_CATALOG.get(state.flow_name)
        if not flow:
            state.pred_intent = 'Converse'
            state.flow_name = 'chat'
            state.confidence = 0.3
            return state

        catalog_intent = flow['intent'].value
        if state.pred_intent != catalog_intent:
            state.pred_intent = catalog_intent

        return state

    def predict(self, user_text:str, context:ContextCoordinator) -> dict:
        intent = self._classify_intent(user_text, context)
        detection = self._detect_flow(user_text, context, intent)
        flow_name = detection['flow_name']

        flow = FLOW_CATALOG.get(flow_name, {})
        flow_intent = flow.get('intent', Intent.CONVERSE).value
        skip_slots = flow_intent in ('Converse', 'Plan')

        if skip_slots or not flow.get('slots'):
            slots = detection.get('slots', {})
        else:
            slots = self._fill_slots(user_text, context, flow_name)

        return {
            'intent': flow_intent,
            'flow_name': flow_name,
            'confidence': detection['confidence'],
            'slots': slots,
        }

    # ── Prediction sub-tasks (private) ────────────────────────────────

    def _classify_intent(self, user_text:str, context:ContextCoordinator) -> str:
        history_text = context.compile_history(look_back=5)
        system, messages = self.engineer.build_nlu_prompt(user_text, history_text)
        raw = self.engineer.call_text(
            system=system, messages=messages,
            call_site='nlu_intent', max_tokens=256,
        )
        parsed = self.engineer.apply_guardrails(raw)
        if parsed and parsed.get('intent'):
            return parsed['intent']
        return 'Converse'

    def _detect_flow(self, user_text:str, context:ContextCoordinator,
                     intent:str|None=None) -> dict:
        history_text = context.compile_history(look_back=5)
        system, messages = self.engineer.build_flow_prompt(
            user_text, intent, history_text,
        )

        def _call_voter() -> dict|None:
            try:
                raw = self.engineer.call_text(
                    system=system, messages=messages,
                    call_site='nlu_vote', max_tokens=512,
                )
                return self.engineer.apply_guardrails(raw)
            except Exception as ecp:
                print(f'NLU vote error: {ecp}')
                return None

        votes: list[dict] = []
        with ThreadPoolExecutor(max_workers=_NUM_VOTERS) as pool:
            futures = [pool.submit(_call_voter) for _ in range(_NUM_VOTERS)]
            for future in as_completed(futures):
                result = future.result()
                if result and result.get('flow_name') in FLOW_CATALOG:
                    votes.append(result)

        if not votes:
            return {
                'flow_name': 'chat', 'confidence': 0.3, 'slots': {},
            }

        return self._tally_votes(votes)

    def _fill_slots(self, user_text:str, context:ContextCoordinator,
                    flow_name:str) -> dict:
        history_text = context.compile_history(look_back=5)
        system, messages = self.engineer.build_slot_filling_prompt(
            user_text, flow_name, history_text,
        )
        raw = self.engineer.call_text(
            system=system, messages=messages,
            call_site='nlu_slots', max_tokens=512,
        )
        parsed = self.engineer.apply_guardrails(raw)
        if parsed and isinstance(parsed.get('slots'), dict):
            return parsed['slots']
        return {}

    # ── Contemplate/React support (private) ───────────────────────────

    def _check_routing(self, user_text:str, context:ContextCoordinator,
                       failed_flow:str|None,
                       failure_reason:str) -> dict:
        candidates = self._get_contemplate_candidates(failed_flow)
        if not candidates:
            return {'flow_name': 'chat', 'confidence': 0.5, 'slots': {}}

        history_text = context.compile_history(look_back=5)
        system, messages = self.engineer.build_contemplate_prompt(
            user_text, failed_flow or 'unknown', failure_reason,
            candidates, history_text,
        )
        raw = self.engineer.call_text(
            system=system, messages=messages,
            call_site='nlu_contemplate', max_tokens=512,
        )
        parsed = self.engineer.apply_guardrails(raw)
        if parsed and parsed.get('flow_name') in FLOW_CATALOG:
            return {
                'flow_name': parsed['flow_name'],
                'confidence': float(parsed.get('confidence', 0.5)),
                'slots': parsed.get('slots', {}),
            }
        return {'flow_name': 'chat', 'confidence': 0.5, 'slots': {}}

    def _get_contemplate_candidates(self, failed_flow:str|None) -> list[str]:
        candidates = set()
        if failed_flow:
            flow = FLOW_CATALOG.get(failed_flow, {})
            for edge in flow.get('edge_flows', []):
                candidates.add(edge)
        active = self.flow_stack.get_active_flow()
        if active and active.flow_name != failed_flow:
            candidates.add(active.flow_name)
        candidates.add('chat')
        candidates.discard(failed_flow)
        return sorted(candidates)

    def _process_action(self, user_text:str) -> dict:
        active = self.flow_stack.get_active_flow()
        if active:
            return {
                'flow_name': active.flow_name,
                'confidence': 1.0,
                'slots': active.slots,
            }
        return {
            'flow_name': 'chat', 'confidence': 0.8,
        }

    def _should_contemplate(self) -> bool:
        if self.flow_stack.depth == 0:
            return False
        prev = self.world.current_state()
        if not prev:
            return False
        return prev.has_issues or prev.keep_going

    def _is_user_action(self, user_text:str) -> bool:
        return bool(_ACTION_PATTERN.match(user_text.strip()))

    # ── Support (private) ─────────────────────────────────────────────

    def _build_state(self, flow_name:str, confidence:float) -> DialogueState:
        flow = FLOW_CATALOG.get(flow_name)
        if flow:
            intent_val = flow['intent'].value
        else:
            intent_val = 'Converse'

        prev = self.world.current_state()

        state = DialogueState(self.config)
        state.update(
            pred_intent=intent_val, flow_name=flow_name,
            confidence=confidence,
        )

        if prev:
            state.has_plan = prev.has_plan
            state.natural_birth = prev.natural_birth

        self.world.insert_state(state)
        return state

    def _push_or_get(self, flow_name:str, slots:dict|None=None):
        existing = self.flow_stack.find_by_name(flow_name)
        if existing:
            if slots:
                existing.fill_slot_values(slots)
            return existing

        flow = self.flow_stack.push(flow_name)
        if slots:
            flow.fill_slot_values(slots)
        return flow

    def _tally_votes(self, votes:list[dict]) -> dict:
        flow_counts: dict[str, list[dict]] = {}
        for vote in votes:
            name = vote['flow_name']
            flow_counts.setdefault(name, []).append(vote)

        best_flow = max(flow_counts, key=lambda flow: len(flow_counts[flow]))
        best_votes = flow_counts[best_flow]
        agreement = len(best_votes) / len(votes)

        avg_confidence = sum(
            float(vote.get('confidence', 0.5)) for vote in best_votes
        ) / len(best_votes)

        if agreement == 1.0 and len(votes) >= 2:
            final_confidence = min(avg_confidence + 0.15, 1.0)
        elif agreement >= 0.5:
            final_confidence = avg_confidence
        else:
            final_confidence = avg_confidence * 0.7

        best_vote = max(best_votes, key=lambda vote: float(vote.get('confidence', 0)))
        slots = best_vote.get('slots', {})

        return {
            'flow_name': best_flow,
            'confidence': final_confidence,
            'slots': slots,
        }

    def _resolve_gold_dax(self, gold_dax:str, user_text:str) -> DialogueState:
        for flow_name, flow in FLOW_CATALOG.items():
            if flow['dax'] == gold_dax:
                state = self._build_state(flow_name, 1.0)
                self._push_or_get(flow_name)
                return state
        return self._build_state('chat', 0.5)
