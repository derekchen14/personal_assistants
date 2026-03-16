from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from types import MappingProxyType
from typing import TYPE_CHECKING

from backend.components.dialogue_state import DialogueState
from backend.components.ambiguity_handler import AmbiguityHandler
from backend.components.prompt_engineer import PromptEngineer
from backend.components.flow_stack import flow_classes
from schemas.ontology import FLOW_CATALOG, Intent
from utils.helper import _DAX_LOOKUP, edge_flows_for

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
        self.flow_stack = world.flow_stack

    # ── Entry point ───────────────────────────────────────────────────

    def understand(self, user_text, context, gold_dax) -> DialogueState:
        prep = self.prepare(user_text)
        if prep is not None:
            return self.validate(prep)

        user_turn = context.last_user_turn
        if gold_dax or (user_turn and user_turn.get('turn_type') == 'action'):
            state = self.react(user_text, gold_dax)
        elif self._should_contemplate():
            state = self.contemplate(user_text)
        else:
            state = self.think(user_text)

        return self.validate(state)

    # ── Public operational modes ──────────────────────────────────────

    def prepare(self, user_text: str) -> DialogueState | None:
        text = user_text.strip()

        if len(text) < 2:
            return self._build_state('chat', 0.8)

        match = _DEV_PATTERN.match(text)
        if match:
            dax_code = match.group(1).upper()
            flow_name = _DAX_LOOKUP.get(dax_code)
            if flow_name:
                return self._build_state(flow_name=flow_name, confidence=0.99)

        for pattern, flow_name in _SHORTCUTS:
            if pattern.search(text):
                if flow_name in FLOW_CATALOG:
                    return self._build_state(flow_name=flow_name, confidence=1.0)
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

    def react(self, user_text: str, gold_dax: str | None = None) -> DialogueState:
        if gold_dax:
            return self._resolve_gold_dax(gold_dax, user_text)
        result = self._process_action(user_text)
        flow_name = result['flow_name']

        flow = self._push_or_get(flow_name)
        if flow and result.get('slots'):
            flow.fill_slot_values(result['slots'])

        return self._build_state(
            flow_name=flow_name, confidence=result.get('confidence', 1.0),
        )

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
            messages = [{'role': 'user', 'content': value}]
            try:
                text = self.engineer.call_text(
                    system=system, messages=messages,
                    call_site='nlu_repair_slot', max_tokens=64,
                ).strip()
                if text in candidates:
                    return text
                if text == 'NONE':
                    return None
            except Exception:
                continue
        return None

    def _get_valid_values(self) -> dict[str, list[str]]:
        from backend.components.flow_stack.slots import CategorySlot

        values: dict[str, list[str]] = {}
        values['CategorySlot'] = [
            'inner', 'left', 'right', 'outer',
            'melt', 'transpose',
            'bar', 'line', 'pie', 'scatter', 'histogram',
            'count', 'sum', 'mean', 'median', 'min', 'max',
            'drop', 'fill_mean', 'fill_zero', 'fill_forward',
        ]

        for name, cls in flow_classes.items():
            inst = cls()
            for slot in inst.slots.values():
                if isinstance(slot, CategorySlot):
                    existing = values.setdefault('CategorySlot', [])
                    existing.extend(o for o in slot.options if o not in existing)
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

    # ── Prediction sub-tasks (private) ────────────────────────────────

    def _classify_intent(self, user_text: str) -> str:
        history_text = self.world.context.compile_history(look_back=5)
        system, messages = self.engineer.build_nlu_prompt(user_text, history_text)
        text = self.engineer.call_text(
            system=system, messages=messages,
            call_site='nlu_intent', max_tokens=256,
        )
        parsed = self.engineer.apply_guardrails(text)
        if parsed and parsed.get('intent'):
            return parsed['intent']
        return 'Converse'

    def _detect_flow(self, user_text: str, intent: str | None = None) -> dict:
        history_text = self.world.context.compile_history(look_back=5)
        system, messages = self.engineer.build_flow_prompt(
            user_text, intent, history_text,
        )

        def _call_voter(voter: dict) -> dict | None:
            try:
                text = self.engineer.call_text(
                    system=system, messages=messages,
                    call_site=voter['call_site'], max_tokens=512,
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
        history_text = self.world.context.compile_history(look_back=5)
        system, messages = self.engineer.build_slot_filling_prompt(
            user_text, flow_name, history_text,
        )
        text = self.engineer.call_text(
            system=system, messages=messages,
            call_site='nlu_slots', max_tokens=512,
        )
        parsed = self.engineer.apply_guardrails(text)
        if parsed and isinstance(parsed.get('slots'), dict):
            return parsed['slots']
        return {}

    # ── Contemplate/React support (private) ───────────────────────────

    def _check_routing(self, user_text: str, failed_flow: str | None,
                       failure_reason: str) -> dict:
        candidates = self._get_contemplate_candidates(failed_flow)
        if not candidates:
            return {'flow_name': 'chat', 'confidence': 0.5, 'slots': {}}

        history_text = self.world.context.compile_history(look_back=5)
        system, messages = self.engineer.build_contemplate_prompt(
            user_text, failed_flow or 'unknown', failure_reason,
            candidates, history_text,
        )
        text = self.engineer.call_text(
            system=system, messages=messages,
            call_site='nlu_contemplate', max_tokens=512,
        )
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

    def _process_action(self, user_text: str) -> dict:
        flow = self.flow_stack.get_active_flow()
        if flow:
            return {
                'flow_name': flow.name(),
                'confidence': 1.0,
                'slots': flow.slot_values_dict(),
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
            state.active_dataset = prev.active_dataset

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

    def _resolve_gold_dax(self, gold_dax: str, user_text: str) -> DialogueState:
        for flow_name, cat in FLOW_CATALOG.items():
            if cat['dax'] == gold_dax:
                slots = self._extract_gold_slots(flow_name, user_text)
                flow = self._push_or_get(flow_name)
                if flow and slots:
                    flow.fill_slot_values(slots)
                return self._build_state(flow_name=flow_name, confidence=0.99)
        return self._build_state('chat', 0.5)

    @staticmethod
    def _extract_gold_slots(flow_name: str, user_text: str) -> dict:
        result = {}
        text = user_text.strip()
        if not text:
            return result
        cls = flow_classes.get(flow_name)
        if not cls:
            return result
        inst = cls()
        for slot_name, slot in inst.slots.items():
            if slot.priority == 'required':
                result[slot_name] = text
                break
        return result
