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
    (re.compile(r'\bshow\s+(me\s+)?(the\s+)?columns\b', re.I), 'describe'),
    (re.compile(r'\bdescribe\b', re.I), 'describe'),
    (re.compile(r'\bwhat.*(next|now)\b', re.I), 'recommend'),
    (re.compile(r'\bstatus\b', re.I), 'describe'),
]

_DAX_LOOKUP: dict[str, str] = {}
for _fn, _flow in FLOW_CATALOG.items():
    _dax_raw = _flow['dax'].strip('{}').upper()
    _DAX_LOOKUP[_dax_raw] = _fn

_DEV_PATTERN = re.compile(r'^/([0-9A-Fa-f]{3})\b\s*(.*)', re.DOTALL)

_ENSEMBLE_VOTERS = [
    {'call_site': 'nlu_vote_haiku', 'label': 'haiku', 'weight': 0.20},
    {'call_site': 'nlu_vote_sonnet', 'label': 'sonnet', 'weight': 0.45},
    {'call_site': 'nlu_vote_gemini', 'label': 'gemini_flash', 'weight': 0.35},
]

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

        state = self._repair_entities(state, flow)

        return state

    # ── Entity repair ──────────────────────────────────────────────────

    def _repair_entities(self, state: DialogueState,
                         flow_info: dict) -> DialogueState:
        slot_schema = flow_info.get('slots', {})
        valid_values = self._get_valid_values()

        for slot_name, value in list(state.slots.items()):
            schema = slot_schema.get(slot_name, {})
            slot_type = schema.get('type', 'FreeTextSlot')

            if slot_type == 'FreeTextSlot':
                continue

            candidates = valid_values.get(slot_type, [])
            if not candidates or value in candidates:
                continue

            repaired = False
            for transform in (str.lower, str.upper, str.title):
                if transform(value) in candidates:
                    state.slots[slot_name] = transform(value)
                    repaired = True
                    break

            if not repaired:
                from difflib import get_close_matches
                matches = get_close_matches(value, candidates, n=1, cutoff=0.6)
                if matches:
                    state.slots[slot_name] = matches[0]
                    self.ambiguity.declare(
                        'confirmation',
                        metadata={'slot': slot_name, 'candidate': matches[0]},
                        observation=f'Did you mean "{matches[0]}" for {slot_name}?',
                    )
                else:
                    llm_result = self._llm_repair_slot(
                        value, candidates, slot_name,
                    )
                    if llm_result:
                        state.slots[slot_name] = llm_result
                        self.ambiguity.declare(
                            'confirmation',
                            metadata={'slot': slot_name, 'candidate': llm_result},
                        )
                    else:
                        self.ambiguity.declare(
                            'partial',
                            metadata={'slot': slot_name, 'invalid_value': value},
                        )
                        del state.slots[slot_name]
        return state

    def _llm_repair_slot(self, value: str, candidates: list[str],
                         slot_name: str, max_attempts: int = 3) -> str | None:
        for attempt in range(max_attempts):
            system = (
                f'The user said "{value}" for the slot "{slot_name}". '
                f'Valid options are: {candidates}. '
                f'Reply with ONLY the best matching valid option, '
                f'or "NONE" if no match is reasonable.'
            )
            messages = [{'role': 'user', 'content': value}]
            try:
                response = self.engineer.call(
                    system=system, messages=messages,
                    call_site='nlu_repair_slot', max_tokens=64,
                )
                text = self._extract_text(response).strip()
                if text in candidates:
                    return text
                if text == 'NONE':
                    return None
            except Exception:
                continue
        return None

    def _get_valid_values(self) -> dict[str, list[str]]:
        values: dict[str, list[str]] = {}
        values['CategorySlot'] = [
            'inner', 'left', 'right', 'outer',
            'melt', 'transpose',
            'bar', 'line', 'pie', 'scatter', 'histogram',
            'count', 'sum', 'mean', 'median', 'min', 'max',
            'drop', 'fill_mean', 'fill_zero', 'fill_forward',
        ]

        for flow_info in FLOW_CATALOG.values():
            for slot_info in flow_info.get('slots', {}).values():
                slot_type = slot_info.get('type', 'FreeTextSlot')
                if slot_type == 'CategorySlot' and 'options' in slot_info:
                    values.setdefault(slot_type, [])
                    for opt in slot_info['options']:
                        if opt not in values[slot_type]:
                            values[slot_type].append(opt)
        return values

    # ── Prediction ────────────────────────────────────────────────────

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

        def _call_voter(voter: dict) -> dict | None:
            try:
                text = self.engineer.call_text(
                    system=system, messages=messages,
                    call_site=voter['call_site'], max_tokens=512,
                )
                parsed = self._parse_json(text)
                if parsed:
                    parsed['_model'] = voter['label']
                    parsed['_weight'] = voter['weight']
                return parsed
            except Exception as e:
                print(f'NLU vote error ({voter["label"]}): {e}')
                return None

        votes: list[dict] = []
        with ThreadPoolExecutor(max_workers=len(_ENSEMBLE_VOTERS)) as pool:
            futures = [
                pool.submit(_call_voter, v) for v in _ENSEMBLE_VOTERS
            ]
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
        flow_weights: dict[str, float] = {}
        flow_votes: dict[str, list[dict]] = {}
        for v in votes:
            fn = v['flow_name']
            w = v.get('_weight', 1.0 / len(votes))
            flow_weights[fn] = flow_weights.get(fn, 0.0) + w
            flow_votes.setdefault(fn, []).append(v)

        total_weight = sum(flow_weights.values())
        best_flow = max(flow_weights, key=flow_weights.get)
        final_confidence = flow_weights[best_flow] / total_weight

        best_vote = max(
            flow_votes[best_flow],
            key=lambda v: v.get('_weight', 0),
        )
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
                return self._build_state(intent=flow['intent'].value, dax=gold_dax,
                    flow_name=flow_name, confidence=0.99
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
