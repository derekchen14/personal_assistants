import logging

log = logging.getLogger(__name__)


from backend.components.ambiguity_handler import AmbiguityHandler
from backend.components.dialogue_state import DialogueState, _flow_detection_schema

from backend.prompts.for_experts import detection_snippet
from backend.prompts.for_contemplate import build_contemplate_prompt as _build_contemplate_prompt_text
from schemas.ontology import FLOW_ONTOLOGY
from utils.helper import edge_flows_for, dax2flow, flow2dax, intent2flow

class NaturalLanguageUnderstanding:

    def __init__(self, config, prompt_engineer):
        self.config = config
        self.ambiguity_handler = AmbiguityHandler(config)
        self.dialogue_state = DialogueState(config)
        self.engineer = prompt_engineer
        self.world = None

    # Main methods: react, think, and contemplate
    # The Assistant calls react, think, and contemplate directly; each ends by validating the turn.

    def check(self) -> tuple:
        """Clear prior ambiguity and return the intent-specific detection snippet with the working flow.
        The working flow is the live Active or Pending top when its intent matches the current classification;
        read it from the stack because intent classification has already replaced the belief prediction."""
        if self.ambiguity_handler.is_present:
            self.ambiguity_handler.resolve(explanation='superseded by the new turn')
        state = self.dialogue_state
        curr_flow = self.world.flows.get_flow()
        in_flight = bool(curr_flow) and curr_flow.status in ('Active', 'Pending')
        flow = curr_flow.name() if in_flight else ''
        working = flow if (flow and intent2flow(state.pred_intent)  # only domain intents continue
                          and state.pred_intent == FLOW_ONTOLOGY[flow]['intent']) else ''
        return detection_snippet(state.pred_intent, working), working

    def think(self, user_text:str, payload:dict={}):
        """Run check → detect_flows → fill_slots → validate against the live flow on the stack.
        PEX resolves disagreement with its current flow through the scratchpad entry written by validate()."""
        snippet, working = self.check()
        state, context = self.world.state, self.world.context
        detection = state.detect_flows(self.engineer, context, user_text, snippet, working)
        intents = {FLOW_ONTOLOGY[flow['name']]['intent'] for flow in detection['pred_flows']}
        if len(intents) > 1 and detection['confidence'] < self.ambiguity_handler.confidence_min:
            # Use coarse intent classification only to break a low-confidence, cross-intent detection.
            state.classify_intent(self.engineer, context, self.world.flows.get_flow())
            if intent2flow(state.pred_intent):  # domain intents only — Plan/Clarify add no
                detection = state.detect_flows(self.engineer, context, user_text,  # narrowing
                                               detection_snippet(state.pred_intent))

        predicted = detection.get('pred_flows', [])
        if not detection['flows']:   # Every voter abstained, so ask without stacking a flow.
            state.pred_flow = ''
            state.pred_flows = []
            state.confidence = detection['confidence']
            self.ambiguity_handler.recognize('general', metadata={'missing': 'intent'},
                observation="I'm not sure what you'd like to do yet — could you clarify the task?")
            self.review_scratchpad()
            return self.validate(state, 'think')

        steps = detection['flows']
        if state.pred_intent == 'Plan' and len(steps) > 1:
            # Stack the Pending Plan marker first, then its steps in reverse order with the first step Active.
            state.has_plan = True
            marker = self.world.flows.stackon('plan', transfer=False, active=False)
            for step in steps:
                marker.slots['steps'].add_one(step)
            for step in reversed(steps):                    # last step first → first on top
                self.world.flows.stackon(step, transfer=False, active=False)
            curr_flow = self.world.flows.get_flow()
            curr_flow.status = 'Active'                     # the first step runs; the rest wait
            # Ground and fill the first step from the live utterance; later steps ground when promoted.
            state.ground_flow(curr_flow)
            state.fill_slots(self.engineer, context, curr_flow, payload, self.ambiguity_handler)
            state = self._write_belief(steps[0], detection['confidence'], predicted, curr_flow)
            self.review_scratchpad()
            return self.validate(state, 'plan')

        flow_name = steps[0]
        prev_flow = self.world.flows.get_flow()
        # Both Active and Pending flows are in flight because a Pending plan step is still next to run.
        in_flight = bool(prev_flow) and prev_flow.status in ('Active', 'Pending')
        prev = prev_flow.name() if in_flight else ''
        repeat = in_flight and prev_flow.name() == flow_name
        # Matching stackon's filled-entity condition ensures the next stackon creates a second instance.
        entity = prev_flow.slots.get(prev_flow.entity_slot) if repeat else None
        if repeat and entity and entity.check_if_filled():
            # Keep the new entity slot open. Merge the flows if filling finds the same entity; otherwise,
            # retain both as separate tasks and let validate announce the second one.
            curr_flow = self.world.flows.stackon(flow_name, transfer=False)
            state.fill_slots(self.engineer, context, curr_flow, payload, self.ambiguity_handler)
            fresh = _entity_ids(curr_flow)
            if not fresh or fresh == _entity_ids(prev_flow):
                values = {name: slot.to_dict() for name, slot in curr_flow.slots.items()
                          if slot.filled and not prev_flow.slots[name].filled}
                prev_flow.fill_slot_values(values)
                curr_flow.status = 'Invalid'
                self.world.flows.pop()   # removes the extra entry, promotes the original back
                curr_flow = prev_flow
        else:
            curr_flow = prev_flow if repeat else self.world.flows.stackon(
                flow_name, transfer=not self.ambiguity_handler.is_present)
            state.ground_flow(curr_flow)
            state.fill_slots(self.engineer, context, curr_flow, payload, self.ambiguity_handler)
        state = self._write_belief(flow_name, detection['confidence'], predicted, curr_flow)
        if state.confidence < self.ambiguity_handler.confidence_min:
            self.ambiguity_handler.recognize('general', metadata={'top_detection': flow_name},
                observation=f'Low confidence ({state.confidence:.2f}) on flow "{flow_name}"')
        self.review_scratchpad()      # Review entries appended since NLU's previous turn point.
        return self.validate(state, 'think', prev)

    def react(self, gold_dax:str, payload:dict={}):
        """Resolve a clicked dax, stack its live flow when needed, and fill it directly from the payload."""
        flow_name = dax2flow(gold_dax)
        state, context = self.world.state, self.world.context
        _, payload = self._fill_slices(state, payload)
        curr_flow = self.world.flows.get_flow()
        if not (curr_flow and curr_flow.status == 'Active' and curr_flow.name() == flow_name):
            curr_flow = self.world.flows.stackon(flow_name,
                                                 transfer=not self.ambiguity_handler.is_present)
        state.ground_flow(curr_flow)
        state.fill_slots(self.engineer, context, curr_flow, payload, self.ambiguity_handler)
        state = self._write_belief(flow_name, 0.99,
                                   [{'name': flow_name, 'dax': gold_dax, 'confidence': 0.99}], curr_flow)
        self.review_scratchpad()
        return self.validate(state, 'react')

    def contemplate(self, user_text:str=''):
        """Re-detect among the failed flow's edges, the current flow, and chat, then stack the replacement.
        Stack transfer carries existing slots, the policy fills gaps, and validate records the announcement."""
        state, context = self.world.state, self.world.context
        failed = state.flow_name(string=True)
        candidates = set(edge_flows_for(failed)) if failed else set()
        prev_flow = self.world.flows.get_flow()
        if prev_flow and prev_flow.name() != failed:
            candidates.add(prev_flow.name())
        candidates.add('chat')
        candidates.discard(failed)
        candidates = sorted(candidates)

        lines = [f'- {name}: {FLOW_ONTOLOGY[name]["description"]}' for name in candidates]
        prompt = _build_contemplate_prompt_text(user_text, failed or 'unknown',
            self.ambiguity_handler.observation, '\n'.join(lines), context.compile_history())
        detection = {'flows': ['chat'], 'confidence': 0.5}
        try:
            parsed = self.engineer(prompt, task='contemplate', max_tokens=512,
                                   schema=_flow_detection_schema(candidates))
            if parsed['flows'] and parsed['flows'][0] in FLOW_ONTOLOGY:
                # Treat a successful single re-route call as a majority-confidence detection.
                detection = {'flows': [parsed['flows'][0]], 'confidence': 0.7}
        except Exception as ecp:
            log.warning('contemplate routing failed: %s', ecp)
            if self.config.get('debug', False):
                raise

        flow_name = detection['flows'][0]
        curr_flow = self.world.flows.stackon(flow_name, transfer=not self.ambiguity_handler.is_present)
        state = self._write_belief(flow_name, detection['confidence'],
            [{'name': flow_name, 'dax': flow2dax(flow_name),
              'confidence': detection['confidence']}], curr_flow)

        # Context compilation requires string text for the API content block.
        text = f"re-detected '{flow_name}' (confidence {detection['confidence']})"
        turn_content = {'text': text, 'tool_uses': [], 'tool_results': []}
        self.world.context.add_turn('agent', turn_content, turn_type='action')
        self.world.context.add_turn('system', {'text': '[contemplate] NLU re-routed the flow based on contemplation.'})
        return self.validate(state, 'think', failed or '')


    def validate(self, state, op:str='think', prev:str=''):
        """Apply ontology fallback, intent correction, and slot repair, then write exactly one scratchpad entry.
        `prev` distinguishes alignment with PEX's prior flow from a new-flow announcement."""
        if state.pred_flows:   # a deliberate abstention (empty detection) stays empty
            cat = FLOW_ONTOLOGY.get(state.flow_name(string=True))
            if not cat:
                state.pred_intent = 'Converse'
                state.pred_flow = flow2dax('chat')
                state.pred_flows = [{'name': 'chat', 'dax': flow2dax('chat'), 'confidence': 0.3}]
                state.confidence = 0.3
            elif state.pred_intent != cat['intent']:
                state.pred_intent = cat['intent']

        flow = self.world.flows.find_by_name(state.flow_name(string=True))
        if flow and op == 'think':   # the rule pass polices the LLM fill only — click payloads
            self._repair_slots(flow) # are the frontend's internal contract, trusted as-is

        detected = state.flow_name(string=True)
        entry = {'turn_number': self.world.context.num_utterances}  # append_entry stamps the rest
        if op != 'react' and state.pred_flows:
            # Preserve candidate tallies so PEX can recover a flow whose support was at or below 0.5.
            entry['tally'] = {flow['name']: flow['confidence'] for flow in state.pred_flows}
        if op == 'react':
            entry.update(gold_dax=state.pred_flow,
                         summary=f'click resolved {detected} from its dax')
        elif op == 'plan':      # keyed on the stacking pass itself, so a mid-plan divergent
            marker = self.world.flows.find_by_name('plan')      # detection still announces
            steps = [step['name'] for step in marker.slots['steps'].steps]
            entry['summary'] = 'plan: stacked ' + ' → '.join(steps)
        elif not detected:      # abstention — every voter returned an empty list
            entry['summary'] = 'no confident detection; nothing stacked'
        elif detected == prev and sum(1 for item in self.world.flows._stack
                if item.flow_type == detected and item.status in ('Active', 'Pending')) <= 1:
            # Multiple live instances of the same flow indicate a second entity task that needs announcement.
            entry['summary'] = f'aligned on {detected}'
        elif flow is None:      # ontology fallback fired — nothing stacked to announce
            entry['summary'] = f'detected {detected}; nothing stacked'
        else:
            summary = (f'added {detected} to the stack before completing {prev}' if prev
                       else f'added {detected} to the stack')
            entry.update(prev_flow=prev, new_flow=detected, summary=summary,
                         rationale=state.pred_flows[0].get('rationale', '') if state.pred_flows else '',
                         question=self.ambiguity_handler.observation)
        self.world.scratchpad.append_entry('nlu', entry)
        return state

    def _repair_slots(self, flow):
        """Preserve established source identities, validate snippet shapes, and derive verification from grounding.
        Target slots may name a new post or section, so they are exempt from source-identity preservation."""
        grounded = self.world.state.get_active_entity()
        # A currently displayed choice is a deliberate entity switch rather than a prediction conflict.
        shown = {choice['entity']['post'] for choice in self.world.state.grounding['choices']
                 if isinstance(choice, dict)}
        for name, slot in flow.slots.items():
            if slot.slot_type not in ('source', 'target', 'removal') or not slot.values:
                continue
            for pred in slot.values:
                if slot.slot_type in ('source', 'removal'):
                    for part in ('post', 'sec'):
                        if grounded.get(part) and pred.get(part) and pred[part] != grounded[part]:
                            if part == 'post' and pred['post'] in shown:
                                continue
                            question = f'switch {name} from {grounded[part]} to {pred[part]}?'
                            self.ambiguity_handler.recognize('confirmation',
                                metadata={'missing': name, 'question': question})
                            self.world.scratchpad.append_entry('nlu', {
                                'turn_number': self.world.context.num_utterances,
                                'summary': f'{name} conflict on {part}: kept {grounded[part]}'})
                            pred[part] = grounded[part]      # the live target wins
                if pred.get('snip') and not _valid_snip(pred['snip']):
                    pred['snip'] = ''                        # a description is not a snippet id
                pred['chl'] = pred.get('chl') or grounded.get('chl', '')  # preserve the channel
                same_entity = (pred.get('post') == grounded.get('post')
                               and pred.get('sec') == grounded.get('sec'))
                pred['ver'] = grounded.get('ver', False) if same_entity else False
            slot._rebuild_keys()
            slot.check_if_filled()

    def recover(self):
        """Try to resolve a pending ambiguity from L2 preferences and the scratchpad before PEX asks the user.
        Record every attempt; the inactive sketch extends recovery through L3 and fills the Active flow."""
        missing = self.world.ambiguity.metadata.get('missing', '')
        result, success = self.ambiguity_handler.recover(self.world.prefs, self.world.scratchpad)
        # Future L3 recovery and slot filling:
        #   if not success:                                       # L2 miss → try L3 knowledge
        #       hit = self.world.knowledge.search_documents(missing, top_k=1)
        #       result, success = (hit['result'][0], True) if hit['result'] else (result, False)
        #   if success:                                           # fill the flow so it can proceed
        #       self.world.flows.get_flow().fill_slots_by_label({missing: result})
        entry = {'turn_number': self.world.context.num_utterances,
                 'found' if success else 'missing': result}
        self.world.scratchpad.append_entry('recovery', entry)
        return {'recovery': result}

    def review_scratchpad(self) -> dict:
        """Repair scratchpad entries missing `turn_number` without consuming them or changing `used_count`.
        Non-consuming reads preserve PEX's cursor; `amend_entry` retains the entry's stamped contract fields."""
        repaired = 0
        for entry in self.world.scratchpad.read(consume=False):
            if 'turn_number' in entry:
                continue
            amended = {'turn_number': self.world.context.num_utterances, **entry}
            self.world.scratchpad.amend_entry(entry['origin'], entry.get('turn_number'), amended)
            repaired += 1
        return {'reviewed': True, 'size': self.world.scratchpad.size, 'repaired': repaired}

    # ── Prediction ────────────────────────────────────────────────────

    def _fill_slices(self, state, payload):
        filtered = {}
        for key, val in payload.items():
            if key in ['choices', 'channels', 'campaigns']:
                for slice_value in val:
                    # Add payload guardrails here if slices require validation.
                    state.grounding.setdefault(key, []).append(slice_value)
            else:
                filtered[key] = val
        return state, filtered

    # ── Support (private) ─────────────────────────────────────────────

    def _write_belief(self, flow_name:str, confidence:float, pred_flows:list, flow=None):
        """Write detection fields into the session belief; predictions contain name, dax, confidence, and rationale.
        Slot predictions remain on the live flow while the Dialogue State stores the flow-level prediction."""
        state = self.world.state
        cat = FLOW_ONTOLOGY.get(flow_name, {})
        state.pred_intent = cat.get('intent', 'Converse')
        state.pred_flow = flow2dax(flow_name)
        state.confidence = confidence
        state.pred_flows = pred_flows
        return state


def _entity_ids(flow) -> set:
    """Reduce the entity slot to comparable post, section, snippet, and channel identities, ignoring `ver`.
    Compare string-valued entity slots such as find queries and chat topics directly as strings."""
    slot = flow.slots.get(flow.entity_slot)
    ids = set()
    for val in (getattr(slot, 'values', None) or []):
        if isinstance(val, dict):
            ids.add(tuple(val.get(part, '') for part in ('post', 'sec', 'snip', 'chl')))
        else:
            ids.add(str(val))
    return ids


def _valid_snip(snip) -> bool:
    """Accept a non-negative integer index or a two-item ascending slice parsed from the schema string."""
    if snip in ('', None):
        return False
    if isinstance(snip, int):
        return snip >= 0
    parts = snip if isinstance(snip, list) else str(snip).strip().strip('[]').split(',')
    try:
        nums = [int(str(part).strip()) for part in parts]
    except ValueError:
        return False
    if len(nums) == 1:
        return nums[0] >= 0
    return len(nums) == 2 and 0 <= nums[0] < nums[1]


# Module alias — the module is NLU; the class name spells it out.
NLU = NaturalLanguageUnderstanding
