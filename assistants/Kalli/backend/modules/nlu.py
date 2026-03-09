from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from types import MappingProxyType
from typing import TYPE_CHECKING

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

    def __init__(self, config: MappingProxyType, ambiguity: AmbiguityHandler,
                 engineer: PromptEngineer, world: 'World'):
        self.config = config
        self.ambiguity = ambiguity
        self.engineer = engineer
        self.world = world

    # ── Entry point ───────────────────────────────────────────────────

    def understand(self, user_text: str, gold_dax: str | None = None) -> DialogueState:
        prep = self.prepare(user_text)
        if prep is not None:
            return self.validate(prep)

        if gold_dax or self._is_user_action(user_text):
            state = self.react(user_text, gold_dax)
        elif self._should_contemplate():
            state = self.contemplate(user_text)
        else:
            state = self.think(user_text)

        return self.validate(state)

    # ── Public operational modes ──────────────────────────────────────

    def prepare(self, user_text: str) -> DialogueState | None:
        text = user_text.strip()

        if not text:
            return self._build_state('Converse', '{000}', 'chat', 1.0)

        if len(text) < 2:
            return self._build_state('Converse', '{000}', 'chat', 0.8)

        match = _DEV_PATTERN.match(text)
        if match:
            dax_code = match.group(1).upper()
            flow_name = _DAX_LOOKUP.get(dax_code)
            if flow_name:
                flow = FLOW_CATALOG[flow_name]
                return self._build_state(
                    intent=flow['intent'].value,
                    dax=flow['dax'],
                    flow_name=flow_name,
                    confidence=0.99,
                    slots={},
                )

        for pattern, flow_name in _SHORTCUTS:
            if pattern.search(text):
                flow = FLOW_CATALOG.get(flow_name)
                if flow:
                    return self._build_state(
                        intent=flow['intent'].value,
                        dax=flow['dax'],
                        flow_name=flow_name,
                        confidence=1.0,
                    )
        return None

    def think(self, user_text: str) -> DialogueState:
        result = self.predict(user_text)
        state = self._build_state(
            intent=result['intent'], dax=result['dax'],
            flow_name=result['flow_name'], confidence=result['confidence'],
            slots=result.get('slots', {}),
        )
        if self.ambiguity.needs_clarification(state.confidence):
            self.ambiguity.declare(
                'general',
                metadata={'top_detection': state.flow_name},
                observation=f'Low confidence ({state.confidence:.2f}) on '
                            f'flow "{state.flow_name}"',
            )
        return state

    def contemplate(self, user_text: str) -> DialogueState:
        prev = self.world.current_state()
        failed_flow = prev.flow_name if prev else None
        failure_reason = self.ambiguity.observation or ''

        detection = self._check_routing(user_text, failed_flow, failure_reason)
        flow_name = detection['flow_name']

        flow = FLOW_CATALOG.get(flow_name, {})
        flow_intent = flow.get('intent', Intent.CONVERSE).value

        if flow_intent not in ('Converse', 'Plan') and flow.get('slots'):
            slots = self._fill_slots(user_text, flow_name)
        else:
            slots = detection.get('slots', {})

        return self._build_state(
            intent=flow_intent, dax=flow.get('dax', '{000}'),
            flow_name=flow_name, confidence=detection['confidence'],
            slots=slots,
        )

    def react(self, user_text: str, gold_dax: str | None = None) -> DialogueState:
        if gold_dax:
            return self._resolve_gold_dax(gold_dax, user_text)
        result = self._process_action(user_text)
        return self._build_state(
            intent=result['intent'], dax=result['dax'],
            flow_name=result['flow_name'], confidence=result.get('confidence', 1.0),
            slots=result.get('slots', {}),
        )

    def validate(self, state: DialogueState) -> DialogueState:
        flow = FLOW_CATALOG.get(state.flow_name)
        if not flow:
            state.intent = 'Converse'
            state.dax = '{000}'
            state.flow_name = 'chat'
            state.confidence = 0.3
            state.slots = {}
            return state

        catalog_intent = flow['intent'].value
        if state.intent != catalog_intent:
            state.intent = catalog_intent

        state.dax = flow['dax']

        valid_slot_names = set(flow.get('slots', {}).keys())
        state.slots = {
            k: v for k, v in state.slots.items()
            if k in valid_slot_names
        }

        return state

    def predict(self, user_text: str) -> dict:
        intent = self._classify_intent(user_text)
        detection = self._detect_flow(user_text, intent)
        flow_name = detection['flow_name']

        flow = FLOW_CATALOG.get(flow_name, {})
        flow_intent = flow.get('intent', Intent.CONVERSE).value
        skip_slots = flow_intent in ('Converse', 'Plan')

        if skip_slots or not flow.get('slots'):
            slots = detection.get('slots', {})
        else:
            slots = self._fill_slots(user_text, flow_name)

        return {
            'intent': flow_intent,
            'dax': flow.get('dax', '{000}'),
            'flow_name': flow_name,
            'confidence': detection['confidence'],
            'slots': slots,
        }

    # ── Prediction sub-tasks (private) ────────────────────────────────

    def _classify_intent(self, user_text: str) -> str:
        history = self.world.context.compile_history(turns=5)
        system, messages = self.engineer.build_nlu_prompt(user_text, history)
        response = self.engineer.call(
            system=system, messages=messages,
            call_site='nlu_intent', max_tokens=256,
        )
        parsed = self._parse_json(self._extract_text(response))
        if parsed and parsed.get('intent'):
            return parsed['intent']
        return 'Converse'

    def _detect_flow(self, user_text: str, intent: str | None = None) -> dict:
        history = self.world.context.compile_history(turns=5)
        system, messages = self.engineer.build_flow_prompt(
            user_text, intent, history,
        )

        def _call_voter() -> dict | None:
            try:
                response = self.engineer.call(
                    system=system, messages=messages,
                    call_site='nlu_vote', max_tokens=512,
                )
                text = self._extract_text(response)
                return self._parse_json(text)
            except Exception as e:
                print(f'NLU vote error: {e}')
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
                'intent': 'Converse', 'dax': '{000}',
                'flow_name': 'chat', 'confidence': 0.3, 'slots': {},
            }

        return self._tally_votes(votes)

    def _fill_slots(self, user_text: str, flow_name: str) -> dict:
        history = self.world.context.compile_history(turns=5)
        system, messages = self.engineer.build_slot_filling_prompt(
            user_text, flow_name, history,
        )
        response = self.engineer.call(
            system=system, messages=messages,
            call_site='nlu_slots', max_tokens=512,
        )
        parsed = self._parse_json(self._extract_text(response))
        if parsed and isinstance(parsed.get('slots'), dict):
            return parsed['slots']
        return {}

    # ── Contemplate/React support (private) ───────────────────────────

    def _check_routing(self, user_text: str, failed_flow: str | None,
                       failure_reason: str) -> dict:
        candidates = self._get_contemplate_candidates(failed_flow)
        if not candidates:
            return {'flow_name': 'chat', 'confidence': 0.5, 'slots': {}}

        history = self.world.context.compile_history(turns=5)
        system, messages = self.engineer.build_contemplate_prompt(
            user_text, failed_flow or 'unknown', failure_reason,
            candidates, history,
        )
        response = self.engineer.call(
            system=system, messages=messages,
            call_site='nlu_contemplate', max_tokens=512,
        )
        parsed = self._parse_json(self._extract_text(response))
        if parsed and parsed.get('flow_name') in FLOW_CATALOG:
            return {
                'flow_name': parsed['flow_name'],
                'confidence': float(parsed.get('confidence', 0.5)),
                'slots': parsed.get('slots', {}),
            }
        return {'flow_name': 'chat', 'confidence': 0.5, 'slots': {}}

    def _get_contemplate_candidates(self, failed_flow: str | None) -> list[str]:
        candidates = set()
        if failed_flow:
            flow = FLOW_CATALOG.get(failed_flow, {})
            for ef in flow.get('edge_flows', []):
                candidates.add(ef)
        active = self.world.flow_stack.get_active_flow()
        if active and active.flow_name != failed_flow:
            candidates.add(active.flow_name)
        candidates.add('chat')
        candidates.discard(failed_flow)
        return sorted(candidates)

    def _process_action(self, user_text: str) -> dict:
        active = self.world.flow_stack.get_active_flow()
        if active:
            flow = FLOW_CATALOG.get(active.flow_name, {})
            return {
                'intent': flow.get('intent', Intent.CONVERSE).value,
                'dax': flow.get('dax', '{000}'),
                'flow_name': active.flow_name,
                'confidence': 1.0,
                'slots': active.slots,
            }
        return {
            'intent': 'Converse', 'dax': '{000}',
            'flow_name': 'chat', 'confidence': 0.8,
        }

    def _should_contemplate(self) -> bool:
        if self.world.flow_stack.depth == 0:
            return False
        prev = self.world.current_state()
        if not prev:
            return False
        return prev.has_issues or prev.keep_going

    def _is_user_action(self, user_text: str) -> bool:
        return bool(_ACTION_PATTERN.match(user_text.strip()))

    # ── Support (private) ─────────────────────────────────────────────

    def _build_state(self, intent: str, dax: str, flow_name: str,
                     confidence: float, slots: dict | None = None) -> DialogueState:
        prev = self.world.current_state()

        state = DialogueState(self.config)
        state.update(
            intent=intent, dax=dax, flow_name=flow_name,
            confidence=confidence, slots=slots,
        )

        if prev:
            state.has_plan = prev.has_plan
            state.natural_birth = prev.natural_birth

        self.world.insert_state(state)
        return state

    def _tally_votes(self, votes: list[dict]) -> dict:
        flow_counts: dict[str, list[dict]] = {}
        for v in votes:
            fn = v['flow_name']
            flow_counts.setdefault(fn, []).append(v)

        best_flow = max(flow_counts, key=lambda f: len(flow_counts[f]))
        best_votes = flow_counts[best_flow]
        agreement = len(best_votes) / len(votes)

        avg_confidence = sum(
            float(v.get('confidence', 0.5)) for v in best_votes
        ) / len(best_votes)

        if agreement == 1.0 and len(votes) >= 2:
            final_confidence = min(avg_confidence + 0.15, 1.0)
        elif agreement >= 0.5:
            final_confidence = avg_confidence
        else:
            final_confidence = avg_confidence * 0.7

        best_vote = max(best_votes, key=lambda v: float(v.get('confidence', 0)))
        slots = best_vote.get('slots', {})

        flow = FLOW_CATALOG[best_flow]
        return {
            'intent': flow['intent'].value,
            'dax': flow['dax'],
            'flow_name': best_flow,
            'confidence': final_confidence,
            'slots': slots,
        }

    def _resolve_gold_dax(self, gold_dax: str, user_text: str) -> DialogueState:
        for flow_name, flow in FLOW_CATALOG.items():
            if flow['dax'] == gold_dax:
                return self._build_state(
                    intent=flow['intent'].value,
                    dax=gold_dax,
                    flow_name=flow_name,
                    confidence=1.0,
                )
        return self._build_state('Converse', '{000}', 'chat', 0.5)

    @staticmethod
    def _extract_text(response) -> str:
        text = ''
        for block in response.content:
            if block.type == 'text':
                text += block.text
        return text

    @staticmethod
    def _parse_json(text: str) -> dict | None:
        text = text.strip()
        if text.startswith('```'):
            lines = text.split('\n')
            lines = [l for l in lines if not l.strip().startswith('```')]
            text = '\n'.join(lines)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
        return None
