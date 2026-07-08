import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

log = logging.getLogger(__name__)

from backend.components.flow_stack import flow_classes
from backend.prompts.for_experts import build_intent_prompt, build_flow_prompt, render_flow_catalog
from backend.prompts.for_nlu import build_slot_filling_prompt
from backend.prompts.for_contemplate import build_contemplate_prompt as _build_contemplate_prompt_text
from backend.utilities.services import PostService
from schemas.ontology import FLOW_CATALOG, Intent
from utils.helper import _DAX_LOOKUP, edge_flows_for, dax2flow, flow2dax


# D6 trim (round E1): the high voter (Gemini Pro, auto thinking budget) was the ensemble's
# latency floor and truncated its JSON at max_tokens often enough to crash turns in debug mode.
_ENSEMBLE_VOTERS = [
    {'model': 'low',  'label': 'low',  'weight': 0.30},
    {'model': 'med',  'label': 'med',  'weight': 0.70},
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
    """Build the JSON schema for slot-fill. Only includes unfilled slots since filled values are considered correct"""
    unfilled_slots = {name: slot.json_schema() for name, slot in flow.slots.items() if not slot.filled}
    return {
        'type': 'object',
        'properties': {
            'reasoning': {'type': 'string'},
            'slots': {'type': 'object', 'properties': unfilled_slots,
                'required': list(unfilled_slots.keys()), 'additionalProperties': False,
            },
        },
        'required': ['reasoning', 'slots'],
        'additionalProperties': False,
    }

class NLU:

    def __init__(self, config, ambiguity, engineer, world):
        self.config = config
        self.ambiguity = ambiguity
        self.engineer = engineer
        self.world = world
        self.flow_stack = world.flow_stack
        self.scratchpad = world.scratchpad
        self._posts = PostService()

    def understand(self, op:str, user_text:str='', dax:str|None=None, payload:dict|None=None):
        """The single NLU entry the Assistant calls. The Assistant picks the op — `react` (a
        click; the dax names the flow), `think` (an utterance; ensemble detection), or
        `contemplate` (a failed-flow re-route). Each mode detects + fills a TRANSIENT flow and
        writes the detection onto the session state's belief (pred_intent / pred_flows /
        confidence / pred_slots). NLU never touches the flow stack — PEX stages and activates."""
        if op == 'react':
            state = self.react(dax, payload or {})
        elif op == 'contemplate':
            state = self.contemplate(user_text)
        else:
            state = self.think(user_text, payload or {})
        return self.validate(state)

    # ── Public operational modes ──────────────────────────────────────

    def think(self, user_text:str, payload:dict={}):
        result = self.predict(user_text)
        flow_name = result['flow_name']

        flow = flow_classes[flow_name]()            # transient — detection writes belief, no push
        self._fill_slots(flow, payload)
        self._repair_entities(self.world.current_state(), flow)
        state = self._write_belief(flow_name, result['confidence'], result['pred_flows'], flow)

        if self.ambiguity.needs_clarification(state.confidence):
            self.ambiguity.declare(
                'general',
                metadata={'top_detection': flow_name},
                observation=f'Low confidence ({state.confidence:.2f}) on flow "{flow_name}"',
            )
        return state

    def contemplate(self, user_text:str):
        state = self.world.current_state()
        failed_flow = state.flow_name(string=True)
        detection = self._check_routing(user_text, failed_flow, self.ambiguity.observation)
        flow_name = detection['flow_name']

        flow = flow_classes[flow_name]()            # transient — belief-only, no push
        self._fill_slots(flow, {})
        return self._write_belief(flow_name, detection['confidence'],
            [{'flow_name': flow_name, 'confidence': detection['confidence'], 'votes': 1}], flow)

    def react(self, gold_dax:str, payload:dict={}):
        """A click resolved the flow via its dax — fill a transient flow and write belief."""
        flow_name = dax2flow(gold_dax)
        flow = flow_classes[flow_name]()            # transient — belief-only, no push
        _, payload = self._fill_slices(self.world.current_state(), payload)
        self._fill_slots(flow, payload)
        self._repair_entities(self.world.current_state(), flow)
        return self._write_belief(flow_name, 0.99,
                                  [{'flow_name': flow_name, 'confidence': 0.99, 'votes': 1}], flow)

    def validate(self, state):
        cat = FLOW_CATALOG.get(state.flow_name(string=True))
        if not cat:
            state.pred_intent = 'Converse'
            state.pred_flow = flow2dax('chat')
            state.pred_flows = [{'flow_name': 'chat', 'confidence': 0.3, 'votes': 0}]
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

    def _repair_entities(self, state, flow):
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
                        metadata={
                            'missing': slot_name,
                            'question': f'Did you mean "{matches[0]}" for {slot_name}?',
                            'candidate': matches[0],
                        },
                    )
                else:
                    llm_result = self._llm_repair_slot(
                        value, candidates, slot_name,
                    )
                    if llm_result:
                        slot.value = llm_result
                        self.ambiguity.declare(
                            'confirmation',
                            metadata={
                                'missing': slot_name,
                                'question': f'Did you mean "{llm_result}" for {slot_name}?',
                                'candidate': llm_result,
                            },
                        )
                    else:
                        self._declare_slot_failure(slot, slot_name, value)
        return state

    def _declare_slot_failure(self, slot, slot_name:str, value:str) -> None:
        self.ambiguity.declare(
            'specific', metadata={'missing': slot_name, 'reason': 'invalid_value'},
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

    def predict(self, user_text:str, hint:str='') -> dict:
        detection = self._detect_flow(user_text, hint)      # hint='' on the pre-hook first pass
        if self._intent_split(detection):                   # low-confidence AND spans >1 intent
            intent = self._classify_intent(user_text)       # the retained tie-break call
            detection = self._detect_flow(user_text, hint=intent)
        return {
            'flow_name': detection['flow_name'],
            'confidence': detection['confidence'],
            'pred_flows': detection.get('pred_flows', []),
        }

    def _intent_split(self, detection:dict) -> bool:
        """True only when the ranked flows span >1 intent AND top-1 is under the confidence floor —
        the one case a coarse-intent tie-break is worth a call. Under D1-A the span clause is almost
        always true, so the confidence clause is the real trigger. At most one extra classify + one
        extra detect per turn."""
        intents = {FLOW_CATALOG[f['flow_name']]['intent'] for f in detection['pred_flows']}
        return len(intents) > 1 and detection['confidence'] < self.ambiguity.confidence_min

    def _detect_flow_prompt(self, user_text:str, hint:str, convo_history:str) -> str:
        candidate_names = self._flow_candidate_names(hint)
        catalog = render_flow_catalog(candidate_names, FLOW_CATALOG, flow_classes)
        active_post = self._active_post_dict()
        return build_flow_prompt(user_text, hint, convo_history,
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

    def _detect_flow(self, user_text:str, hint:str='') -> dict:
        convo_history = self.world.context.compile_history()
        prompt = self._detect_flow_prompt(user_text, hint, convo_history)
        candidate_names = self._flow_candidate_names(hint)
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
                # Provider quota/rate-limit loss (e.g. Gemini 429 RESOURCE_EXHAUSTED) degrades
                # the ensemble by design — debug re-raise is for schema/code bugs, not outages.
                if 'RESOURCE_EXHAUSTED' not in str(ecp) and '429' not in str(ecp):
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
                'pred_flows': [{'flow_name': 'chat', 'confidence': 0.3, 'votes': 0}],
            }

        return self._tally_votes(votes)

    def _flow_candidate_names(self, hint:str='') -> list[str]:
        if not hint:
            return list(FLOW_CATALOG)
        edges = _get_edge_flows_for_intent(hint)
        return [name for name, cat in FLOW_CATALOG.items() if cat['intent'] == hint or name in edges]

    def _fill_slots(self, flow, payload:dict={}):
        last_turn = self.world.context.last_user_turn

        if payload:
            entity_dict, filtered_payload = self._split_payload(payload)

            # Sub-task of slot filling: entity extraction from payload (Phase 1a + 1b).
            extracted = self._extract_entities(flow, entity_dict)
            # Phase 1c: Capture slot-values when a user clicks on a button or interacts with UI.
            if not extracted and last_turn.turn_type == 'action' and filtered_payload:
                self.unpack_user_actions(flow, filtered_payload)

        # Phase 2: Transfer entity grounding from previous flow to active flow. Gate on `slot.values` (not `slot.filled`)
        # so a slot already partially populated from a prior turn isn't double-grounded into a duplicate entity.
        prev = self.world.current_state()
        if prev.active_post:
            for slot in flow.slots.values():
                if slot.slot_type in ('source', 'target') and not slot.values:
                    slot.add_one(post=prev.active_post)

        # Phase 3: Standard LLM slot-filling. Only targets unfilled slots, enforced by `_fill_slots_schema`
        if not flow.is_filled():
            convo_history = self.world.context.compile_history()
            prompt = build_slot_filling_prompt(flow, convo_history, self._active_post_dict())
            for attempt in (1, 2):
                try:
                    pred_slots = self.engineer(prompt, 'fill_slots', max_tokens=2048, schema=_fill_slots_schema(flow))
                except ValueError:
                    pred_slots = {}
                if 'slots' in pred_slots:
                    break
                log.warning('[fill_slots] schema violation flow=%s attempt=%s payload=%s', flow.name(), attempt, pred_slots)
            if 'slots' not in pred_slots:
                log.warning('[fill_slots] convo_history=\n%s', convo_history)
                log.warning('[fill_slots] filled-state: %s', {n: s.filled for n, s in flow.slots.items()})
                return
            cleaned = self.engineer._strip_nulls(pred_slots['slots'])
            flow.fill_slot_values(cleaned)

    def _extract_entities(self, flow, entity_dict:dict) -> bool:
        """Entity extraction (sub-task of slot filling): write entities from the payload
        into the flow's grounding slots. Covers two cases:
          - Phase 1a: entity_dict maps directly into source/target/removal slots.
          - Phase 1b: a snippet entity routes into the flow's ExactSlot for FindFlow / ReferenceFlow.
        Returns True if the payload was consumed (caller should skip Phase 1c)."""
        snippet_exact_map = {'find': 'query', 'reference': 'word'}
        entity_slots = [s for s in flow.slots.values() if s.slot_type in ('source', 'target', 'removal')]

        if entity_dict and entity_slots:
            for slot in entity_slots:
                slot.add_one(**entity_dict)
            return True
        if 'snip' in entity_dict and flow.name() in snippet_exact_map:
            slot_name = snippet_exact_map[flow.name()]
            if not flow.slots[slot_name].filled:
                flow.slots[slot_name].add_one(entity_dict['snip'])
            return True
        return False

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

    # ── Support (private) ─────────────────────────────────────────────

    @staticmethod
    def _slot_preview(slot):
        """Short preview of a slot's payload — handles both value-style and steps-style slots."""
        if hasattr(slot, 'steps') and slot.steps:
            return [step.get('name', '?') for step in slot.steps]
        if hasattr(slot, 'values') and slot.values:
            return [str(v)[:80] for v in slot.values]
        return None

    def _write_belief(self, flow_name:str, confidence:float, pred_flows:list, flow):
        """Write the detection onto the session state's belief IN PLACE — the single source of
        truth for predictions. Mutates current_state; never inserts a new per-turn state and
        never pushes a flow (PEX stages and activates)."""
        state = self.world.current_state()
        cat = FLOW_CATALOG.get(flow_name, {})
        state.pred_intent = cat.get('intent', Intent.CONVERSE)
        state.pred_flow = flow2dax(flow_name)
        state.confidence = confidence
        state.pred_flows = pred_flows
        state.pred_slots = flow.slot_values_dict()
        return state

    def _tally_votes(self, votes:list[dict]) -> dict:
        flow_weights: dict[str, float] = {}
        flow_votes: dict[str, int] = {}
        for vote in votes:
            name = vote['flow_name']
            weight = vote.get('_weight', 1.0 / len(votes))
            flow_weights[name] = flow_weights.get(name, 0.0) + weight
            flow_votes[name] = flow_votes.get(name, 0) + 1

        total_weight = sum(flow_weights.values())
        best_flow = max(flow_weights, key=flow_weights.get)
        final_confidence = flow_weights[best_flow] / total_weight

        ranked = sorted(flow_weights.items(), key=lambda x: x[1], reverse=True)
        pred_flows = [
            {'flow_name': name, 'confidence': weight / total_weight, 'votes': flow_votes[name]}
            for name, weight in ranked
        ]

        return {
            'flow_name': best_flow,
            'confidence': final_confidence,
            'pred_flows': pred_flows,
        }