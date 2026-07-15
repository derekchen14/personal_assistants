import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

log = logging.getLogger(__name__)


from backend.components.flow_stack import flow_classes
from backend.components.ambiguity_handler import AmbiguityHandler
from backend.components.dialogue_state import DialogueState

from backend.prompts.for_experts import build_intent_prompt, build_flow_prompt, render_flow_ontology
from backend.prompts.for_nlu import build_slot_filling_prompt, build_pending_question
from backend.prompts.for_contemplate import build_contemplate_prompt as _build_contemplate_prompt_text
from backend.utilities.services import PostService
from schemas.ontology import FLOW_ONTOLOGY, Intent
from utils.helper import _DAX_LOOKUP, edge_flows_for, dax2flow, flow2dax

def _get_edge_flows_for_intent(intent:str) -> set[str]:
    edge = set()
    for name, cat in FLOW_ONTOLOGY.items():
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
            'flow_name': {'type': 'string', 'enum': list(candidate_flow_names)}
        },
        'required': ['reasoning', 'flow_name'],
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

class NaturalLanguageUnderstanding:

    def __init__(self, config, prompt_engineer):
        self.config = config
        self.ambiguity_handler = AmbiguityHandler(config)
        self.dialogue_state = DialogueState(config)
        self.engineer = prompt_engineer
        self.world = None
        self._posts = PostService()

    def understand(self, op:str, user_text:str='', dax:str|None=None, payload:dict|None=None,
                   hint:str=''):
        """The single NLU entry the Assistant and PEX call. The caller picks the op — `react` (a
        click; the dax names the flow), `think` (an utterance; ensemble detection), or
        `contemplate` (a failed-flow re-route). Each mode detects + fills a TRANSIENT flow and
        writes the detection onto the session state's belief (pred_intent / pred_flows /
        confidence / pred_slots). `hint` is derived deterministically by the Assistant: the Active
        flow's name when one is on the stack (the Continue signal — candidates narrow to it + its
        edge flows and PEX's selection seeds the vote), a domain intent from PEX's first pass, or
        blank (detect over the full ontology). For real policy flows, NLU also ensures the detected
        flow is on the shared stack with the filled slots; PEX still owns responses."""
        if op == 'react':
            state = self.react(dax, payload or {})
        elif op == 'contemplate':
            state = self.contemplate(user_text)
        else:
            state = self.think(user_text, payload or {}, hint)
        self.review_scratchpad()      # NLU's turn point — reviews last turn's appends too
        return self.validate(state)

    # ── Public operational modes ──────────────────────────────────────

    def think(self, user_text:str, payload:dict={}, hint:str=''):
        # One uniform process on every turn: flow detection, then slot-filling (round 2.12).
        # `hint` is either an intent (narrows candidates to that intent's flows) or the Active
        # flow's name (the Continue signal — candidates narrow to it + its edge flows, and PEX's
        # selection seeds the vote).
        detection = self._detect_flow(user_text, hint)
        if self._intent_split(detection):                   # low-confidence AND spans >1 intent
            intent = self._classify_intent(user_text)       # the retained tie-break call
            detection = self._detect_flow(user_text, hint=intent)

        flow_name = detection['flow_name']
        predicted_flows = detection.get('pred_flows', [])
        if flow_name not in flow_classes:
            return self._write_non_policy_belief(flow_name, detection['confidence'], predicted_flows)

        curr_flow = self.world.flows.get_flow()
        active_flow = curr_flow if curr_flow and curr_flow.status == 'Active' else None
        if active_flow:
            if active_flow.name() == flow_name:
                return self._fill_active_flow(active_flow, payload, detection)
            else:
                prev_flow_name = active_flow.name()
                new_entry = {
                    'version': 1, 'turn_number': self.world.context.turn_id, 'used_count': 0,
                    'prev_flow': prev_flow_name, 'new_flow': flow_name,
                    'summary': f'added {flow_name} to stack before completing {prev_flow_name}',
                    'question': self.ambiguity_handler.observation}
                self.world.scratchpad.append_entry('nlu', new_entry)

        flow = flow_classes[flow_name]()
        self._fill_slots(flow, payload)
        self._repair_entities(self.world.state, flow)
        state = self._write_belief(flow_name, detection['confidence'], predicted_flows, flow)
        self._stack_detected_flow(flow, state)

        if self.ambiguity_handler.needs_clarification(state.confidence):
            self.ambiguity_handler.recognize('general', metadata={'top_detection': flow_name},
                observation=f'Low confidence ({state.confidence:.2f}) on flow "{flow_name}"')
        return state

    def _fill_active_flow(self, flow, payload:dict, detection:dict):
        """Detection landed on the flow already Active on the stack: slot-filling applies to THAT
        flow in place — no new stackon — and PEX resumes it. Belief is written from the detection
        tally as on any other turn; a fill that readies the flow resolves the open ambiguity."""
        self._fill_slots(flow, payload, incomplete=True)
        self._repair_entities(self.world.state, flow)
        if flow.is_filled() and self.ambiguity_handler.is_present:
            self.ambiguity_handler.resolve(explanation=f'answer filled {flow.name()}')
            flow.is_uncertain = False
        state = self._write_belief(flow.name(), detection['confidence'],
                                   detection['pred_flows'], flow)
        state.flow_stack = self.world.flows.to_list()
        return state

    def _write_non_policy_belief(self, flow_name:str, confidence:float, pred_flows:list):
        state = self._write_belief(flow_name, confidence, pred_flows, flow=None)
        if flow_name == 'clarify':
            self.ambiguity_handler.recognize(
                'general',
                metadata={'missing': 'intent', 'top_detection': flow_name},
                observation="I'm not sure what you'd like to do yet — could you clarify the task?",
            )
        return state

    def contemplate(self, user_text:str):
        state = self.world.state
        failed_flow = state.flow_name(string=True)
        detection = self._check_routing(user_text, failed_flow, self.ambiguity_handler.observation)
        flow_name = detection['flow_name']

        flow = flow_classes[flow_name]()
        self._fill_slots(flow, {})
        state = self._write_belief(flow_name, detection['confidence'],
            [{'flow_name': flow_name, 'confidence': detection['confidence'], 'votes': 1}], flow)
        self._stack_detected_flow(flow, state)
        return state

    def react(self, gold_dax:str, payload:dict={}):
        """A click resolved the flow via its dax — fill a transient flow and write belief."""
        flow_name = dax2flow(gold_dax)
        flow = flow_classes[flow_name]()
        _, payload = self._fill_slices(self.world.state, payload)
        self._fill_slots(flow, payload)
        self._repair_entities(self.world.state, flow)
        state = self._write_belief(flow_name, 0.99,
                                  [{'flow_name': flow_name, 'confidence': 0.99, 'votes': 1}], flow)
        self._stack_detected_flow(flow, state)
        return state

    def validate(self, state):
        cat = FLOW_ONTOLOGY.get(state.flow_name(string=True))
        if not cat:
            state.pred_intent = 'Converse'
            state.pred_flow = flow2dax('chat')
            state.pred_flows = [{'flow_name': 'chat', 'confidence': 0.3, 'votes': 0}]
            state.confidence = 0.3
            return state

        ontology_intent = cat['intent']
        if state.pred_intent != ontology_intent:
            state.pred_intent = ontology_intent

        flow = self.world.flows.find_by_name(state.flow_name(string=True))
        if flow:
            state = self._repair_entities(state, flow)

        return state

    def _stack_detected_flow(self, flow, state):
        """Make the NLU detection visible as a real flow-stack entry, without activating it.

        PEX reads this stack and decides whether to activate, continue, pop, or respond. Slot values
        are copied from NLU's transient flow into the shared FlowStack entry so the policy sees the
        same belief NLU wrote to DialogueState.
        """
        if flow.name() not in flow_classes:
            return None
        # A push over an in-flight flow reverts it to Pending (FlowStack.stackon owns that), and
        # slot hand-over is skipped while an ambiguity is open — those values are in question.
        stacked = self.world.flows.stackon(flow.name(),
                                           transfer=not self.ambiguity_handler.is_present)
        values = flow.slot_values_dict()
        if values:
            stacked.fill_slot_values(values)
            stacked.is_filled()
        state.flow_stack = self.world.flows.to_list()
        return stacked

    def recover(self):
        result, success = self.ambiguity_handler.recover(self.world.prefs, self.world.scratchpad)
        entry = {'version': 1, 'turn_number': self.world.context.turn_id,
                 'used_count': 0, 'found' if success else 'missing': result}
        self.world.scratchpad.append_entry('recovery', entry)
        return {'recovery': result}

    def review_scratchpad(self) -> dict:
        """Synchronous review pass at NLU's turn point. Conservative for now: repair entries
        missing the contract fields (version / turn_number / used_count) losslessly via the
        NLU-only `amend_entry`; semantic review — merging contradictions, pruning stale notes
        via `prune_entry`, maintaining used_count — is designed-not-built."""
        repaired = 0
        for entry in self.world.scratchpad.read():
            if all(field in entry for field in ('version', 'turn_number', 'used_count')):
                continue
            amended = {'version': 1, 'used_count': 0,
                       'turn_number': self.world.context.turn_id, **entry}
            self.world.scratchpad.amend_entry(entry['origin'], entry.get('turn_number'), amended)
            repaired += 1
        return {'reviewed': True, 'size': self.world.scratchpad.size, 'repaired': repaired}

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
                    self.ambiguity_handler.recognize(
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
                        self.ambiguity_handler.recognize(
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
        self.ambiguity_handler.recognize(
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

    def _intent_split(self, detection:dict) -> bool:
        """True only when the ranked flows span >1 intent AND top-1 is under the confidence floor —
        the one case a coarse-intent tie-break is worth a call. Under D1-A the span clause is almost
        always true, so the confidence clause is the real trigger. At most one extra classify + one
        extra detect per turn."""
        intents = {FLOW_ONTOLOGY[f['flow_name']]['intent'] for f in detection['pred_flows']}
        return len(intents) > 1 and detection['confidence'] < self.ambiguity_handler.confidence_min

    def _detect_flow_prompt(self, user_text:str, hint:str, convo_history:str) -> str:
        candidate_names = self._flow_candidate_names(hint)
        ontology = render_flow_ontology(candidate_names, FLOW_ONTOLOGY, flow_classes)
        active_post = self._active_post_dict()
        # A flow-name hint (Continue) borrows its flow's intent for the prompt content; the
        # candidate narrowing above already carries the flow-level signal.
        intent = FLOW_ONTOLOGY[hint]['intent'] if hint in FLOW_ONTOLOGY else hint
        return build_flow_prompt(user_text, intent, convo_history,
                                 ontology, active_post=active_post)

    def _active_post_dict(self) -> dict | None:
        state = self.world.state
        post_id = state.get_active_post()
        if not post_id:
            return None
        title = self._posts.get_title(post_id)
        if not title:
            return None
        return {'id': post_id, 'title': title}

    def _fill_slices(self, state, payload):
        filtered = {}
        for key, val in payload.items():
            if key in ['choices', 'channels', 'campaigns']:
                for slice_value in val:
                    # if value > 0: // can add guardrails in this line if desired
                    state.grounding.setdefault(key, []).append(slice_value)
            else:
                filtered[key] = val
        return state, filtered

    def _contemplate_prompt(self, user_text:str, failed_flow:str, failure_reason:str,
                             candidates:list[str], convo_history:str) -> str:
        candidate_lines = []
        for name in candidates:
            cat = FLOW_ONTOLOGY.get(name, {})
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

        votes: list[dict] = []
        med_families = ('claude', 'gemini', 'gpt')
        if hint in FLOW_ONTOLOGY:
            # Continue: PEX already offered a flow-level vote for the Active flow — seed it and
            # poll only the two families PEX is NOT running on. The tally runs over three votes
            # exactly as on any other turn.
            pex_family = self._orchestrator_family()
            votes.append({'flow_name': hint, '_model': pex_family, '_tier': 'med'})
            med_families = tuple(fam for fam in med_families if fam != pex_family)
        votes += self._collect_votes(med_families, 'med', prompt, schema)
        if not votes:
            return {
                'flow_name': 'chat', 'confidence': 0.3,
                'pred_flows': [{'flow_name': 'chat', 'confidence': 0.3, 'votes': 0}],
            }
        detection = self._tally_votes(votes)
        if detection['confidence'] < self.ambiguity_handler.confidence_min:
            votes += self._collect_votes(('gemini', 'claude'), 'high', prompt, schema)
            detection = self._tally_votes(votes)
        return detection

    def _orchestrator_family(self) -> str:
        """The model family PEX runs on — its voters are the OTHER two families. Prefix match,
        since the orchestrator model id need not appear in the voter tier table."""
        model_id = self.config['models']['overrides']['orchestrator']['model_id']
        for family in ('claude', 'gemini', 'gpt'):
            if model_id.startswith(family):
                return family
        raise ValueError(f'orchestrator model {model_id!r} maps to no voter family')

    def _collect_votes(self, families:tuple, level:str, prompt:str, schema:dict) -> list[dict]:
        def _call_voter(family:str) -> dict | None:
            try:
                parsed = self.engineer(prompt, 'detect_flow', family=family, tier=level,
                                       max_tokens=1024, schema=schema)
                parsed['_model'] = family
                parsed['_tier'] = level
                return parsed
            except Exception as ecp:
                log.warning('NLU vote error (%s %s): %s', family, level, ecp)
                # Provider-side losses degrade the ensemble by design — debug re-raise is for
                # schema/code bugs, not outages: quota loss (429 RESOURCE_EXHAUSTED) or output
                # the provider truncated/mangled into unparseable JSON.
                recoverable = ('RESOURCE_EXHAUSTED' in str(ecp) or '429' in str(ecp)
                               or 'unparseable JSON' in str(ecp))
                if not recoverable:
                    self._raise_if_debug(ecp)
                return None

        votes: list[dict] = []
        with ThreadPoolExecutor(max_workers=len(families)) as pool:
            futures = [pool.submit(_call_voter, family) for family in families]
            for future in as_completed(futures):
                result = future.result()
                if result and result.get('flow_name') in FLOW_ONTOLOGY:
                    votes.append(result)
        return votes

    def _flow_candidate_names(self, hint:str='') -> list[str]:
        if not hint:
            return list(FLOW_ONTOLOGY)
        if hint in FLOW_ONTOLOGY:   # Continue: the Active flow's name narrows to it + its edges
            return [hint, *FLOW_ONTOLOGY[hint]['edge_flows']]
        edges = _get_edge_flows_for_intent(hint)
        return [name for name, cat in FLOW_ONTOLOGY.items() if cat['intent'] == hint or name in edges]

    def _fill_slots(self, flow, payload:dict={}, incomplete:bool=False):
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
        prev = self.world.state
        active_post = prev.get_active_post()
        if active_post:
            for slot in flow.slots.values():
                if slot.slot_type in ('source', 'target') and not slot.values:
                    slot.add_one(post=active_post)

        # Phase 3: Standard LLM slot-filling. Only targets unfilled slots, enforced by `_fill_slots_schema`
        if not flow.is_filled():
            convo_history = self.world.context.compile_history()
            prompt = build_slot_filling_prompt(flow, convo_history, self._active_post_dict())
            if incomplete:  # the open question + shown candidates, with conservative-fill guidance
                prompt += '\n\n' + build_pending_question(self.ambiguity_handler.observation,
                                                          self.world.state.grounding['choices'])
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
            if parsed['flow_name'] in FLOW_ONTOLOGY:
                # Single re-route call, no ensemble to agree — score it as a majority vote (0.7).
                return {'flow_name': parsed['flow_name'], 'confidence': 0.7}
        except Exception as ecp:
            log.warning('contemplate routing failed: %s', ecp)
            self._raise_if_debug(ecp)
        return {'flow_name': 'chat', 'confidence': 0.5}

    def _get_contemplate_candidates(self, failed_flow:str|None) -> list[str]:
        candidates = set()
        if failed_flow:
            for ef in edge_flows_for(failed_flow):
                candidates.add(ef)
        flow = self.world.flows.get_flow()
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

    def _write_belief(self, flow_name:str, confidence:float, pred_flows:list, flow=None):
        """Write the detection onto the session state's belief IN PLACE — the single source of
        truth for predictions. Mutates current_state; never inserts a new per-turn state and
        never pushes a flow (PEX stages and activates)."""
        state = self.world.state
        cat = FLOW_ONTOLOGY.get(flow_name, {})
        state.pred_intent = cat.get('intent', Intent.CONVERSE)
        state.pred_flow = flow2dax(flow_name)
        state.confidence = confidence
        state.pred_flows = pred_flows
        state.pred_slots = flow.slot_values_dict() if flow else {}
        return state

    def _tally_votes(self, votes:list[dict]) -> dict:
        counts: dict[str, int] = {}
        for vote in votes:
            counts[vote['flow_name']] = counts.get(vote['flow_name'], 0) + 1

        best_flow = max(counts, key=counts.get)
        ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        pred_flows = [{'flow_name': name, 'confidence': count / len(votes), 'votes': count}
                      for name, count in ranked]
        return {'flow_name': best_flow, 'confidence': self._score_votes(votes, best_flow),
                'pred_flows': pred_flows}

    def _score_votes(self, votes:list[dict], best_flow:str) -> float:
        """Confidence is voter AGREEMENT, never a self-reported score (models can't calibrate
        their own confidence). Round 1 (the 3 medium voters): all agree 0.9, majority 0.7, full
        split 0.5/0.3 by whether the split stays within one intent. Round 2 (5 votes): the
        (agreement, intent-spread) ladder, +0.1 when the two high voters agree with each other.
        4-of-5 can't happen — round 2 only fires after the mediums all split."""
        agree = sum(1 for vote in votes if vote['flow_name'] == best_flow)
        intents = len({FLOW_ONTOLOGY[vote['flow_name']]['intent'] for vote in votes})

        if len(votes) <= 3:   # round 1: only the medium voters have voted
            if agree == len(votes):
                return 0.9
            return 0.7 if agree > 1 else (0.5 if intents == 1 else 0.3)

        ladder = {(3, 1): 0.8, (3, 2): 0.7, (3, 3): 0.5,
                  (2, 1): 0.6, (2, 2): 0.4, (2, 3): 0.3,
                  (1, 1): 0.2, (1, 2): 0.2, (1, 3): 0.1}
        confidence = ladder[(agree, min(intents, 3))]
        high = [vote['flow_name'] for vote in votes if vote['_tier'] == 'high']
        if len(high) == 2 and high[0] == high[1]:
            confidence += 0.1
        return confidence

# Module alias — the module is NLU; the class name spells it out.
NLU = NaturalLanguageUnderstanding
