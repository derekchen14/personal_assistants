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
from backend.prompts.for_experts import build_intent_prompt, build_flow_prompt, render_flow_catalog
from backend.prompts.for_nlu import build_slot_filling_prompt
from backend.prompts.for_contemplate import build_contemplate_prompt as _build_contemplate_prompt_text
from backend.utilities.services import PostService
from schemas.ontology import FLOW_CATALOG, Intent
from utils.helper import _DAX_LOOKUP, edge_flows_for, dax2flow, flow2dax

if TYPE_CHECKING:
    from backend.components.world import World


_SHORTCUTS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'^(hi|hello|hey)\b', re.I), 'chat'),
    (re.compile(r'^(help|what can you do)\b', re.I), 'chat'),
    (re.compile(r'^(bye|goodbye|exit|quit)\b', re.I), 'chat'),
    (re.compile(r'\bwhat.*(next|now)\b', re.I), 'next'),
    (re.compile(r'\bstatus\b', re.I), 'check'),
]

_ENSEMBLE_VOTERS = [
    {'model': 'haiku', 'label': 'haiku', 'weight': 0.20},
    {'model': 'sonnet', 'label': 'sonnet', 'weight': 0.45},
    {'model': 'flash', 'label': 'gemini_flash', 'weight': 0.35},
]

def _get_edge_flows_for_intent(intent:str) -> set[str]:
    edge = set()
    for name, cat in FLOW_CATALOG.items():
        if cat['intent'] == intent:
            for ef in cat.get('edge_flows', []):
                edge.add(ef)
    return edge


_VALID_INTENTS = ('Research', 'Draft', 'Revise', 'Publish', 'Converse', 'Plan')


def _intent_schema() -> dict:
    return {
        'type': 'object',
        'properties': {
            'reasoning': {'type': 'string'},
            'intent': {'type': 'string', 'enum': list(_VALID_INTENTS)},
        },
        'required': ['reasoning', 'intent'],
        'additionalProperties': False,
    }


def _flow_detection_schema(candidate_flow_names:list[str]) -> dict:
    return {
        'type': 'object',
        'properties': {
            'reasoning': {
                'type': 'string',
                'description': 'Terse rationale (<100 tokens) naming the key signals that separate the top candidates.',
            },
            'flow_name': {'type': 'string', 'enum': list(candidate_flow_names)},
            'confidence': {'type': 'number'},
        },
        'required': ['reasoning', 'flow_name', 'confidence'],
        'additionalProperties': False,
    }


def _fill_slots_schema(flow) -> dict:
    """Only ask the LLM for slots that aren't already filled. Filled slots are final —
    re-asking risks the LLM substituting worse data (e.g. post title for post_id) and
    appending a duplicate entry on the slot."""
    unfilled = {name: slot for name, slot in flow.slots.items() if not slot.filled}
    return {
        'type': 'object',
        'properties': {
            'reasoning': {'type': 'string'},
            'slots': {
                'type': 'object',
                'properties': {name: slot.json_schema() for name, slot in unfilled.items()},
                'required': list(unfilled),
                'additionalProperties': False,
            },
        },
        'required': ['reasoning', 'slots'],
        'additionalProperties': False,
    }


def _strip_nulls(obj):
    """Recursively drop None values before handing slots to fill_slot_values. Models now emit
    `null` (schema-enforced) rather than a string sentinel."""
    if isinstance(obj, dict):
        return {k: _strip_nulls(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_strip_nulls(x) for x in obj if x is not None]
    return obj


class NLU:

    def __init__(self, config:MappingProxyType, ambiguity:AmbiguityHandler,
                 engineer:PromptEngineer, world:'World'):
        self.config = config
        self.ambiguity = ambiguity
        self.engineer = engineer
        self.world = world
        self.flow_stack = world.flow_stack
        self._posts = PostService()

    def understand(self, user_text:str, context, dax:str|None=None, payload:dict|None=None) -> DialogueState:
        gold_dax = dax or self.prepare(user_text)
        if gold_dax:
            state = self.react(gold_dax, payload or {})
        elif self.requires_contemplation():
            state = self.contemplate(user_text)
        else:
            state = self.think(user_text, payload or {})
        return self.validate(state)

    # ── Public operational modes ──────────────────────────────────────

    def prepare(self, user_text:str) -> str | None:
        text = user_text.strip()
        if len(text) < 2:
            raise ValueError('User text is too short')
        for pattern, flow_name in _SHORTCUTS:
            if pattern.search(text):
                return '{000}'
        return None

    def think(self, user_text:str, payload:dict={}) -> DialogueState:
        result = self.predict(user_text)
        flow_name = result['flow_name']

        flow = self._push_or_get(flow_name)
        self._fill_slots(flow, payload)
        state = self._build_state(flow_name=flow_name, confidence=result['confidence'])
        state.pred_flows = result.get('pred_flows', [])

        if self.ambiguity.needs_clarification(state.confidence):
            self.ambiguity.declare(
                'general',
                metadata={'top_detection': state.flow_name()},
                observation=f'Low confidence ({state.confidence:.2f}) on flow "{state.flow_name()}"',
            )
        return state

    def contemplate(self, user_text:str) -> DialogueState:
        prev = self.world.current_state()
        failed_flow = prev.flow_name() if prev else None
        failure_reason = self.ambiguity.observation or ''

        detection = self._check_routing(user_text, failed_flow, failure_reason)
        flow_name = detection['flow_name']
        new_flow = self._push_or_get(flow_name)
        self._fill_slots(new_flow, payload={})

        return self._build_state(flow_name=flow_name, confidence=detection['confidence'])

    def react(self, gold_dax:str, payload:dict={}) -> DialogueState:
        """Automatically create the flow since we know the correct DAX."""
        flow_name = dax2flow(gold_dax)
        flow = self._push_or_get(flow_name)
        state = self._build_state(flow_name, confidence=0.99)
        state, payload = self._fill_slices(state, payload)
        self._fill_slots(flow, payload)
        return state

    def validate(self, state:DialogueState) -> DialogueState:
        cat = FLOW_CATALOG.get(state.flow_name(string=True))
        if not cat:
            state.pred_intent = 'Converse'
            state.pred_flow = flow2dax('chat')
            state.confidence = 0.3
            return state

        catalog_intent = cat['intent']
        if state.pred_intent != catalog_intent:
            state.pred_intent = catalog_intent

        flow = self.flow_stack.find_by_name(state.flow_name(string=True))
        if flow:
            state = self._repair_entities(state, flow)

        return state

    # ── Entity repair ──────────────────────────────────────────────────

    def _repair_entities(self, state:DialogueState, flow) -> DialogueState:
        from backend.components.flow_stack.slots import FreeTextSlot

        valid_values = self._get_valid_values()
        slot_vals = flow.slot_values_dict()

        for slot_name, value in list(slot_vals.items()):
            slot = flow.slots.get(slot_name)
            if not slot or isinstance(slot, FreeTextSlot):
                continue
            # Entity repair only handles single-string slots. Group slots
            # (source/target/removal/channel/proposals/checklist) carry list
            # or dict values that don't go through case-normalization.
            if not isinstance(value, str):
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
                        self._declare_slot_failure(slot, slot_name, value)
        return state

    def _declare_slot_failure(self, slot, slot_name:str, value:str) -> None:
        self.ambiguity.declare(
            'partial', metadata={'slot': slot_name, 'invalid_value': value},
        )
        slot.reset()

    def _llm_repair_slot(self, value:str, candidates:list[str],
                         slot_name:str, max_attempts:int=3) -> str | None:
        for attempt in range(max_attempts):
            prompt = (
                f'The user said "{value}" for the slot "{slot_name}". '
                f'Valid options are: {candidates}.'
            )
            try:
                raw_output = self.engineer(prompt, 'repair_slot', max_tokens=32)
                repaired = raw_output.strip()
                if repaired in candidates:
                    return repaired
                if repaired == 'NONE':
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

    def predict(self, user_text:str) -> dict:
        intent = self._classify_intent(user_text)
        detection = self._detect_flow(user_text, intent)
        return {
            'flow_name': detection['flow_name'],
            'confidence': detection['confidence'],
            'pred_flows': detection.get('pred_flows', []),
        }

    def _detect_flow_prompt(self, user_text:str, intent:str, convo_history:str) -> str:
        candidate_names = self._flow_candidate_names(intent)
        catalog = render_flow_catalog(candidate_names, FLOW_CATALOG, flow_classes)
        active_post = self._active_post_dict()
        return build_flow_prompt(user_text, intent, convo_history,
                                 catalog, active_post=active_post)

    def _active_post_dict(self) -> dict | None:
        state = self.world.current_state()
        if not state.active_post:
            return None
        title = self._posts.get_title(state.active_post)
        if not title:
            return None
        return {'id': state.active_post, 'title': title}

    def _fill_slices(self, state, payload):
        filtered = {}
        for key, val in payload.items():
            if key in ['choices', 'channels', 'campaigns']:
                for slice_value in val:
                    # if value > 0: // can add guardrails in this line if desired
                    state.slices[key].append(slice_value)
            else:
                filtered[key] = val
        return state, filtered

    def _contemplate_prompt(self, user_text:str, failed_flow:str, failure_reason:str,
                             candidates:list[str], convo_history:str) -> str:
        candidate_lines = []
        for name in candidates:
            cat = FLOW_CATALOG.get(name, {})
            candidate_lines.append(f'- {name}: {cat.get("description", "")}')
        candidates_text = '\n'.join(candidate_lines)
        return _build_contemplate_prompt_text(
            user_text, failed_flow, failure_reason, candidates_text, convo_history,
        )

    def _raise_if_debug(self, ecp:Exception):
        if self.config.get('debug', False):
            raise ecp

    def _classify_intent(self, user_text:str) -> str:
        convo_history = self.world.context.compile_history()
        prompt = build_intent_prompt(user_text, convo_history, self._active_post_dict())
        try:
            parsed = self.engineer(prompt, 'classify_intent', max_tokens=512, schema=_intent_schema())
            return parsed['intent']
        except Exception as ecp:
            log.warning('intent classification failed: %s', ecp)
            self._raise_if_debug(ecp)
            return 'Converse'

    def _detect_flow(self, user_text:str, intent:str|None=None) -> dict:
        convo_history = self.world.context.compile_history()
        prompt = self._detect_flow_prompt(user_text, intent, convo_history)
        candidate_names = self._flow_candidate_names(intent)
        schema = _flow_detection_schema(candidate_names)

        def _call_voter(voter:dict) -> dict | None:
            try:
                parsed = self.engineer(prompt, 'detect_flow', model=voter['model'],
                                       max_tokens=1024, schema=schema)
                parsed['_model'] = voter['label']
                parsed['_weight'] = voter['weight']
                return parsed
            except Exception as ecp:
                log.warning('NLU vote error (%s): %s', voter['label'], ecp)
                self._raise_if_debug(ecp)
                return None

        votes: list[dict] = []
        with ThreadPoolExecutor(max_workers=len(_ENSEMBLE_VOTERS)) as pool:
            futures = [
                pool.submit(_call_voter, voter) for voter in _ENSEMBLE_VOTERS
            ]
            for future in as_completed(futures):
                result = future.result()
                if result and result.get('flow_name') in FLOW_CATALOG:
                    votes.append(result)

        if not votes:
            return {
                'flow_name': 'chat', 'confidence': 0.3,
                'pred_flows': [{'flow_name': 'chat', 'confidence': 0.3}],
            }

        return self._tally_votes(votes)

    def _flow_candidate_names(self, intent:str|None) -> list[str]:
        if intent is None:
            return [name for name, cat in FLOW_CATALOG.items() if cat['intent'] != Intent.INTERNAL]
        edges = _get_edge_flows_for_intent(intent)
        return [name for name, cat in FLOW_CATALOG.items() if cat['intent'] == intent or name in edges]

    def _fill_slots(self, flow, payload:dict={}):
        snippet_exact_map = {'find': 'query', 'reference': 'word'}
        last_turn = self.world.context.last_user_turn

        if payload:
            entity_slots = [s for s in flow.slots.values() if s.slot_type in ('source', 'target', 'removal')]
            entity_dict, filtered_payload = self._split_payload(payload)

            # Phase 1a: Fill entity slots
            if entity_dict and entity_slots:
                for slot in entity_slots:
                    slot.add_one(**entity_dict)
            # Phase 1b: Fill ExactSlot with snippets. Only for FindFLow and ReferenceFlow.
            elif 'snip' in entity_dict and flow.name() in snippet_exact_map:
                target_name = snippet_exact_map[flow.name()]
                slot = flow.slots.get(target_name)
                if not slot.filled:
                    slot.add_one(entity_dict['snip'])
            # Phase 1c: Capture slot-values when a user clicks on a button or interacts with UI.
            elif last_turn.turn_type == 'action' and filtered_payload:
                self.unpack_user_actions(flow, filtered_payload)

        # Phase 2: Ground remaining source/target slots against the active post.
        prev = self.world.current_state()
        if prev and prev.active_post:
            for slot_name, slot in flow.slots.items():
                if slot.slot_type in ('source', 'target') and not slot.filled:
                    slot.add_one(post=prev.active_post)

        # Phase 3: LLM slot-filling for anything still unfilled
        if not flow.is_filled():
            convo_history = self.world.context.compile_history()
            prompt = build_slot_filling_prompt(flow, convo_history, self._active_post_dict())
            pred_slots = self.engineer(prompt, 'fill_slots', schema=_fill_slots_schema(flow))
            cleaned = _strip_nulls(pred_slots['slots'])
            flow.fill_slot_values(cleaned)

    def unpack_user_actions(self, flow, payload:dict):
        """Transfer a frontend action payload into flow slots. Default is a generic
        slot-name → value fill, which covers any click whose payload keys map directly to
        slots (e.g. {type: 'draft'} → CreateFlow.type). Flows with nested/structured payloads
        need an explicit case (currently only outline)."""
        match flow.name():
            case 'outline':
                chosen = payload['proposals'][0]
                for sec in chosen:
                    flow.slots['sections'].add_one(sec['name'], sec['description'])
                flow.slots['proposals'].values = [chosen]
            case _:
                flow.fill_slot_values(payload)

    def _split_payload(self, payload):
        entity_mapper = {'snippet': 'snip', 'post': 'post', 'section': 'sec', 'channel': 'chl'}

        entity_dict, filtered_payload = {}, {}
        for key, val in payload.items():
            if key in entity_mapper:
                mapped_key = entity_mapper[key]
                entity_dict[mapped_key] = val
            else:
                filtered_payload[key] = val
        return entity_dict, filtered_payload

    def _check_routing(self, user_text:str, failed_flow:str|None,
                       failure_reason:str) -> dict:
        candidates = self._get_contemplate_candidates(failed_flow)
        if not candidates:
            return {'flow_name': 'chat', 'confidence': 0.5}

        convo_history = self.world.context.compile_history()
        prompt = self._contemplate_prompt(
            user_text, failed_flow or 'unknown', failure_reason, candidates, convo_history,
        )
        try:
            parsed = self.engineer(prompt, 'contemplate', max_tokens=512,
                                   schema=_flow_detection_schema(candidates))
            if parsed['flow_name'] in FLOW_CATALOG:
                return {'flow_name': parsed['flow_name'], 'confidence': float(parsed['confidence'])}
        except Exception as ecp:
            log.warning('contemplate routing failed: %s', ecp)
            self._raise_if_debug(ecp)
        return {'flow_name': 'chat', 'confidence': 0.5}

    def _get_contemplate_candidates(self, failed_flow:str|None) -> list[str]:
        candidates = set()
        if failed_flow:
            for ef in edge_flows_for(failed_flow):
                candidates.add(ef)
        flow = self.flow_stack.get_flow()
        if flow and flow.name() != failed_flow:
            candidates.add(flow.name())
        candidates.add('chat')
        candidates.discard(failed_flow)
        return sorted(candidates)

    def requires_contemplation(self) -> bool:
        if len(self.flow_stack._stack) == 0:
            return False
        prev = self.world.current_state()
        if not prev:
            return False
        return prev.has_issues or prev.keep_going

    # ── Support (private) ─────────────────────────────────────────────

    @staticmethod
    def _slot_preview(slot):
        """Short preview of a slot's payload — handles both value-style and steps-style slots."""
        if hasattr(slot, 'steps') and slot.steps:
            return [step.get('name', '?') for step in slot.steps]
        if hasattr(slot, 'values') and slot.values:
            return [str(v)[:80] for v in slot.values]
        return None

    def _push_or_get(self, flow_name:str):
        """Push a new flow or return existing one on the stack."""
        existing = self.flow_stack.find_by_name(flow_name)
        if existing:
            return existing
        try:
            return self.flow_stack.stackon(flow_name)
        except (ValueError, RuntimeError):
            return None

    def _build_state(self, flow_name:str, confidence:float) -> DialogueState:
        prev = self.world.current_state()
        cat = FLOW_CATALOG.get(flow_name, {})
        pred_intent = cat.get('intent', Intent.CONVERSE)

        state = DialogueState(intent=pred_intent, dax=flow2dax(flow_name),
            turn_count=prev.turn_count + 1, confidence=confidence)
        state.has_plan = prev.has_plan
        state.natural_birth = prev.natural_birth
        state.active_post = prev.active_post

        self.world.insert_state(state)
        return state

    def _tally_votes(self, votes:list[dict]) -> dict:
        flow_weights: dict[str, float] = {}
        for vote in votes:
            name = vote['flow_name']
            weight = vote.get('_weight', 1.0 / len(votes))
            flow_weights[name] = flow_weights.get(name, 0.0) + weight

        total_weight = sum(flow_weights.values())
        best_flow = max(flow_weights, key=flow_weights.get)
        final_confidence = flow_weights[best_flow] / total_weight

        ranked = sorted(flow_weights.items(), key=lambda x: x[1], reverse=True)
        pred_flows = [
            {'flow_name': name, 'confidence': weight / total_weight}
            for name, weight in ranked
        ]

        return {
            'flow_name': best_flow,
            'confidence': final_confidence,
            'pred_flows': pred_flows,
        }