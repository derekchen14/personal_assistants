from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from types import MappingProxyType
from typing import TYPE_CHECKING

log = logging.getLogger(__name__)

from backend.components.dialogue_state import DialogueState
from backend.components.ambiguity_handler import AmbiguityHandler
from backend.components.prompt_engineer import PromptEngineer
from backend.components.flow_stack import flow_classes
from schemas.ontology import FLOW_CATALOG, Intent
from utils.helper import _DAX_LOOKUP, edge_flows_for, dax2flow

if TYPE_CHECKING:
    from backend.components.world import World


_SHORTCUTS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'^(hi|hello|hey)\b', re.I), 'chat'),
    (re.compile(r'^(help|what can you do)\b', re.I), 'chat'),
    (re.compile(r'^(bye|goodbye|exit|quit)\b', re.I), 'chat'),
    (re.compile(r'\bwhat.*(next|now)\b', re.I), 'next'),
    (re.compile(r'\bstatus\b', re.I), 'check'),
]

_DEV_PATTERN = re.compile(r'^/([0-9A-Fa-f]{3})\b\s*(.*)', re.DOTALL)

_ENSEMBLE_VOTERS = [
    {'family': 'claude', 'model': 'haiku', 'label': 'haiku', 'weight': 0.20},
    {'family': 'claude', 'model': 'sonnet', 'label': 'sonnet', 'weight': 0.45},
    {'family': 'gemini', 'model': 'flash', 'label': 'gemini_flash', 'weight': 0.35},
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
        self.flow_stack = world.flow_stack

    # ── Entry point ───────────────────────────────────────────────────

    def understand(self, user_text:str, context, gold_dax:str|None=None) -> DialogueState:
        gold_dax = gold_dax or self.prepare(user_text)

        if gold_dax:
            state = self.react(user_text, gold_dax, context)
        elif self.requires_contemplation():
            state = self.contemplate(user_text)
        else:
            state = self.think(user_text)

        return self.validate(state)

    # ── Public operational modes ──────────────────────────────────────

    def prepare(self, user_text:str) -> str | None:
        text = user_text.strip()

        if len(text) < 2:
            raise ValueError('User text is too short')

        match = _DEV_PATTERN.match(text)
        if match:
            return '{' + match.group(1).upper() + '}'
        for pattern, flow_name in _SHORTCUTS:
            if pattern.search(text):
                return '{000}'
        return None

    def think(self, user_text: str) -> DialogueState:
        result = self.predict(user_text)
        flow_name = result['flow_name']

        flow = self._push_or_get(flow_name)
        if flow and result.get('slots'):
            flow.fill_slot_values(result['slots'])

        state = self._build_state(
            flow_name=flow_name, confidence=result['confidence'],
        )
        state.pred_flows = result.get('pred_flows', [])

        if self.ambiguity.needs_clarification(state.confidence):
            self.ambiguity.declare(
                'general',
                metadata={'top_detection': state.flow_name},
                observation=f'Low confidence ({state.confidence:.2f}) on flow "{state.flow_name}"',
            )
        return state

    def contemplate(self, user_text: str) -> DialogueState:
        prev = self.world.current_state()
        failed_flow = prev.flow_name if prev else None
        failure_reason = self.ambiguity.observation or ''

        detection = self._check_routing(user_text, failed_flow, failure_reason)
        flow_name = detection['flow_name']
        flow_intent = FLOW_CATALOG.get(flow_name, {}).get('intent', Intent.CONVERSE)

        if flow_intent not in (Intent.CONVERSE, Intent.PLAN):
            cls = flow_classes.get(flow_name)
            if cls and cls().slots:
                slots = self._fill_slots(user_text, flow_name)
            else:
                slots = detection.get('slots', {})
        else:
            slots = detection.get('slots', {})

        flow = self._push_or_get(flow_name)
        if flow and slots:
            flow.fill_slot_values(slots)

        return self._build_state(
            flow_name=flow_name, confidence=detection['confidence'],
        )

    def react(self, user_text:str, gold_dax:str, context) -> DialogueState:
        """
        Automatically create the flow since we know it is the correct one.
        We can skip over flow detection and slot filling if the turn type is 'action'
        since we already have the slot values.
        """
        flow_name = dax2flow(gold_dax)
        flow = self._push_or_get(flow_name)

        user_turn = context.last_user_turn
        if user_turn and user_turn.turn_type == 'action':
            # then we know that the slot values are also filled
            gold_slot_values = user_text.split(",")
            final_slots = {}
            for gsv in gold_slot_values:
                slot_name, slot_value = gsv.split("=")
                final_slots[slot_name] = slot_value
            confidence = 1.0
        else:
            # we need to fill the slots
            final_slots = self._fill_slots(user_text, flow_name)
            confidence = 0.99

        flow.fill_slot_values(final_slots)
        return self._build_state(flow_name, confidence)

    def validate(self, state: DialogueState) -> DialogueState:
        cat = FLOW_CATALOG.get(state.flow_name)
        if not cat:
            state.pred_intent = 'Converse'
            state.flow_name = 'chat'
            state.confidence = 0.3
            return state

        catalog_intent = cat['intent']
        if state.pred_intent != catalog_intent:
            state.pred_intent = catalog_intent

        flow = self.flow_stack.find_by_name(state.flow_name)
        if flow:
            state = self._repair_entities(state, flow)

        return state

    # ── Entity repair ──────────────────────────────────────────────────

    def _repair_entities(self, state: DialogueState,
                         flow) -> DialogueState:
        from backend.components.flow_stack.slots import FreeTextSlot

        valid_values = self._get_valid_values()
        slot_vals = flow.slot_values_dict()

        for slot_name, value in list(slot_vals.items()):
            slot = flow.slots.get(slot_name)
            if not slot or isinstance(slot, FreeTextSlot):
                continue

            slot_type = type(slot).__name__
            candidates = valid_values.get(slot_type, [])
            if not candidates or value in candidates:
                continue

            repaired = False
            for transform in (str.lower, str.upper, str.title):
                if transform(value) in candidates:
                    slot.value = transform(value)
                    repaired = True
                    break

            if not repaired:
                from difflib import get_close_matches
                matches = get_close_matches(value, candidates, n=1, cutoff=0.6)
                if matches:
                    slot.value = matches[0]
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
                        slot.value = llm_result
                        self.ambiguity.declare(
                            'confirmation',
                            metadata={'slot': slot_name, 'candidate': llm_result},
                        )
                    else:
                        self.ambiguity.declare(
                            'partial',
                            metadata={'slot': slot_name, 'invalid_value': value},
                        )
                        slot.reset()
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
            try:
                text = self.engineer.call(value, system=system, task='repair_slot', max_tokens=64).strip()
                if text in candidates:
                    return text
                if text == 'NONE':
                    return None
            except Exception:
                continue
        return None

    def _get_valid_values(self) -> dict[str, list[str]]:
        from backend.components.flow_stack.slots import CategorySlot, ChannelSlot

        values: dict[str, list[str]] = {}
        values['ChannelSlot'] = ['substack', 'twitter', 'linkedin', 'mt1t']

        for name, cls in flow_classes.items():
            inst = cls()
            for slot in inst.slots.values():
                if isinstance(slot, CategorySlot):
                    values.setdefault('CategorySlot', [])
                    for opt in slot.options:
                        if opt not in values['CategorySlot']:
                            values['CategorySlot'].append(opt)
        return values

    # ── Prediction ────────────────────────────────────────────────────

    def predict(self, user_text: str) -> dict:
        intent = self._classify_intent(user_text)
        detection = self._detect_flow(user_text, intent)
        flow_name = detection['flow_name']

        flow_intent = FLOW_CATALOG.get(flow_name, {}).get('intent', Intent.CONVERSE)
        skip_slots = flow_intent in (Intent.CONVERSE, Intent.PLAN)

        cls = flow_classes.get(flow_name)
        has_slots = bool(cls and cls().slots) if cls else False

        if skip_slots or not has_slots:
            slots = detection.get('slots', {})
        else:
            slots = self._fill_slots(user_text, flow_name)

        return {
            'flow_name': flow_name,
            'confidence': detection['confidence'],
            'slots': slots,
            'pred_flows': detection.get('pred_flows', []),
        }

    def _classify_intent(self, user_text: str) -> str:
        convo_history = self.world.context.compile_history()
        system, messages = self.engineer.build_nlu_prompt(user_text, convo_history)
        text = self.engineer.call(messages, system=system, task='classify_intent', max_tokens=256)
        parsed = self.engineer.apply_guardrails(text)
        if parsed and parsed.get('intent'):
            return parsed['intent']
        return 'Converse'

    def _detect_flow(self, user_text: str, intent: str | None = None) -> dict:
        convo_history = self.world.context.compile_history()
        system, messages = self.engineer.build_flow_prompt(user_text, intent, convo_history)

        def _call_voter(voter: dict) -> dict | None:
            try:
                text = self.engineer.call(
                    messages, system=system, task='detect_flow',
                    family=voter['family'], model=voter['model'], max_tokens=512,
                )
                parsed = self.engineer.apply_guardrails(text)
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
                'flow_name': 'chat', 'confidence': 0.3, 'slots': {},
                'pred_flows': [{'flow_name': 'chat', 'confidence': 0.3}],
            }

        return self._tally_votes(votes)

    def _fill_slots(self, user_text: str, flow_name: str) -> dict:
        convo_history = self.world.context.compile_history()
        system, messages = self.engineer.build_slot_filling_prompt(user_text, flow_name, convo_history)
        text = self.engineer.call(messages, system=system, task='fill_slots', max_tokens=512)
        parsed = self.engineer.apply_guardrails(text)
        if parsed and isinstance(parsed.get('slots'), dict):
            return parsed['slots']
        return {}

    def _check_routing(self, user_text: str, failed_flow: str | None,
                       failure_reason: str) -> dict:
        candidates = self._get_contemplate_candidates(failed_flow)
        if not candidates:
            return {'flow_name': 'chat', 'confidence': 0.5, 'slots': {}}

        convo_history = self.world.context.compile_history()
        system, messages = self.engineer.build_contemplate_prompt(
            user_text, failed_flow or 'unknown', failure_reason, candidates, convo_history,
        )
        text = self.engineer.call(messages, system=system, task='contemplate', max_tokens=512)
        parsed = self.engineer.apply_guardrails(text)
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
            for ef in edge_flows_for(failed_flow):
                candidates.add(ef)
        flow = self.flow_stack.get_active_flow()
        if flow and flow.name() != failed_flow:
            candidates.add(flow.name())
        candidates.add('chat')
        candidates.discard(failed_flow)
        return sorted(candidates)

    def requires_contemplation(self) -> bool:
        if self.flow_stack.depth == 0:
            return False
        prev = self.world.current_state()
        if not prev:
            return False
        return prev.has_issues or prev.keep_going

    def _is_user_action(self, user_text: str) -> bool:
        return bool(_ACTION_PATTERN.match(user_text.strip()))

    # ── Support (private) ─────────────────────────────────────────────

    def _push_or_get(self, flow_name: str):
        """Push a new flow or return existing one on the stack."""
        existing = self.flow_stack.find_by_name(flow_name)
        if existing:
            return existing
        try:
            return self.flow_stack.push(flow_name)
        except (ValueError, RuntimeError):
            return None

    def _build_state(self, flow_name: str,
                     confidence: float) -> DialogueState:
        prev = self.world.current_state()
        cat = FLOW_CATALOG.get(flow_name, {})
        pred_intent = cat.get('intent', Intent.CONVERSE)

        state = DialogueState(self.config)
        state.update(
            pred_intent=pred_intent, flow_name=flow_name,
            confidence=confidence,
        )

        if prev:
            state.has_plan = prev.has_plan
            state.natural_birth = prev.natural_birth
            state.active_post = prev.active_post

        # Update active_post from the flow's source slot if filled
        flow = self.flow_stack.find_by_name(flow_name)
        if flow:
            source_slot = flow.slots.get('source')
            if source_slot and source_slot.filled:
                val = source_slot.to_dict()
                post = val[0].get('post', '') if isinstance(val, list) and val else str(val)
                if post:
                    state.active_post = post

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

        ranked = sorted(flow_weights.items(), key=lambda x: x[1], reverse=True)
        pred_flows = [
            {'flow_name': fn, 'confidence': w / total_weight}
            for fn, w in ranked
        ]

        best_vote = max(
            flow_votes[best_flow],
            key=lambda v: v.get('_weight', 0),
        )
        slots = best_vote.get('slots', {})

        return {
            'flow_name': best_flow,
            'confidence': final_confidence,
            'slots': slots,
            'pred_flows': pred_flows,
        }