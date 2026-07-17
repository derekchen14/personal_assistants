import logging

log = logging.getLogger(__name__)


from backend.components.flow_stack import flow_classes
from backend.components.ambiguity_handler import AmbiguityHandler
from backend.components.dialogue_state import DialogueState, _flow_detection_schema

from backend.prompts.for_experts import detection_snippet
from backend.prompts.for_contemplate import build_contemplate_prompt as _build_contemplate_prompt_text
from schemas.ontology import FLOW_ONTOLOGY, Intent
from utils.helper import edge_flows_for, dax2flow, flow2dax, intent2flow

def _valid_snip(snip) -> bool:
    """Shape check only: an int index, or a two-item non-negative ascending slice, parsed from
    the string the schema emits. Range-vs-sentence-count stays execution-time."""
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

class NaturalLanguageUnderstanding:

    def __init__(self, config, prompt_engineer):
        self.config = config
        self.ambiguity_handler = AmbiguityHandler(config)
        self.dialogue_state = DialogueState(config)
        self.engineer = prompt_engineer
        self.world = None

    # ── Main methods: react / think / contemplate (round 3.4) ─────────
    # The Assistant calls these directly — `understand` survives only as the name of PEX's
    # tool. Each ends in validate(), which writes the turn's scratchpad entry.

    def check(self) -> str:
        """Opens `think` with the preliminary work (round 3.4): prior ambiguity is ALWAYS
        cleared here — the dynamic, situation-dependent resolve comes in a later round — and
        the extra detection-prompt snippet is picked for the classified intent (Continue reads
        very differently from Plan or Clarify). Nothing is passed in: the working intent is
        dialogue_state.pred_intent. 'Continue' itself is never stored — classify_intent (T16)
        maps it to the Active flow's intent — so a Continue reading is pred_intent matching
        the belief flow's own intent, and the flow name comes from flow_name()."""
        if self.ambiguity_handler.is_present:
            self.ambiguity_handler.resolve(explanation='superseded by the new turn')
        state = self.dialogue_state
        flow = state.flow_name(string=True)
        working = flow if (flow and intent2flow(state.pred_intent)  # only domain intents continue
                          and state.pred_intent == FLOW_ONTOLOGY[flow]['intent']) else ''
        return detection_snippet(state.pred_intent, working)

    def think(self, user_text:str, payload:dict={}):
        """One path: check → detect_flows → fill_slots → validate. Stacks and fills the LIVE
        flow — no transient, no copy step. Any disagreement with what PEX is running is
        resolved on PEX's side (the hook 3/5 read of validate's entry)."""
        snippet = self.check()
        state, context = self.world.state, self.world.context
        detection = state.detect_flows(self.engineer, context, user_text, snippet)
        if self._intent_split(detection):                   # low-confidence AND spans >1 intent
            state.classify_intent(self.engineer, context, user_text)  # the tie-break re-classify
            detection = state.detect_flows(self.engineer, context, user_text,
                                           detection_snippet(state.pred_intent))

        flow_name = detection['flow_name']
        predicted = detection.get('pred_flows', [])
        if flow_name not in flow_classes:
            prev = ''
            state = self._write_non_policy_belief(flow_name, detection['confidence'], predicted)
        else:
            top = self.world.flows.get_flow()
            prev = top.name() if top and top.status == 'Active' else ''  # what PEX runs now
            if not (top and top.status == 'Active' and top.name() == flow_name):
                top = self.world.flows.stackon(flow_name,
                                               transfer=not self.ambiguity_handler.is_present)
            state.fill_slots(self.engineer, context, top, payload, self.ambiguity_handler)
            state = self._write_belief(flow_name, detection['confidence'], predicted, top)
            if self.ambiguity_handler.needs_clarification(state.confidence):
                self.ambiguity_handler.recognize('general', metadata={'top_detection': flow_name},
                    observation=f'Low confidence ({state.confidence:.2f}) on flow "{flow_name}"')
        self.review_scratchpad()      # NLU's turn point — reviews last turn's appends too
        return self.validate(state, 'think', prev)

    def react(self, gold_dax:str, payload:dict={}):
        """A click resolved the flow via its dax — stack the LIVE flow and fill it directly
        (no check: the react path needs no detection setup)."""
        flow_name = dax2flow(gold_dax)
        state, context = self.world.state, self.world.context
        _, payload = self._fill_slices(state, payload)
        top = self.world.flows.get_flow()
        if not (top and top.status == 'Active' and top.name() == flow_name):
            top = self.world.flows.stackon(flow_name,
                                           transfer=not self.ambiguity_handler.is_present)
        state.fill_slots(self.engineer, context, top, payload, self.ambiguity_handler)
        state = self._write_belief(flow_name, 0.99,
                                   [{'name': flow_name, 'dax': gold_dax, 'confidence': 0.99}], top)
        self.review_scratchpad()
        return self.validate(state, 'react')

    def contemplate(self, user_text:str=''):
        """The failed-flow re-route — the Assistant calls this after PEX queues the request
        (3.4.7). One re-route call over the failed flow's edges + the live top + chat, then
        the replacement is stacked directly. No LLM slot fill: stackon's transfer carries the
        failed flow's slots and the policy's fill_slots_by_label covers gaps. Ends in
        validate like think/react — the announcement is the re-route's record."""
        state, context = self.world.state, self.world.context
        failed = state.flow_name(string=True)
        candidates = set(edge_flows_for(failed)) if failed else set()
        top = self.world.flows.get_flow()
        if top and top.name() != failed:
            candidates.add(top.name())
        candidates.add('chat')
        candidates.discard(failed)
        candidates = sorted(candidates)

        lines = [f'- {name}: {FLOW_ONTOLOGY[name]["description"]}' for name in candidates]
        prompt = _build_contemplate_prompt_text(user_text, failed or 'unknown',
            self.ambiguity_handler.observation, '\n'.join(lines), context.compile_history())
        detection = {'flow_name': 'chat', 'confidence': 0.5}
        try:
            parsed = self.engineer(prompt, 'contemplate', max_tokens=512,
                                   schema=_flow_detection_schema(candidates))
            if parsed['flow_name'] in FLOW_ONTOLOGY:
                # Single re-route call, no ensemble to agree — score it as a majority vote (0.7).
                detection = {'flow_name': parsed['flow_name'], 'confidence': 0.7}
        except Exception as ecp:
            log.warning('contemplate routing failed: %s', ecp)
            self._raise_if_debug(ecp)

        flow_name = detection['flow_name']
        top = self.world.flows.stackon(flow_name, transfer=not self.ambiguity_handler.is_present)
        state = self._write_belief(flow_name, detection['confidence'],
            [{'name': flow_name, 'dax': flow2dax(flow_name),
              'confidence': detection['confidence']}], top)
        return self.validate(state, 'think', failed or '')

    def _write_non_policy_belief(self, flow_name:str, confidence:float, pred_flows:list):
        state = self._write_belief(flow_name, confidence, pred_flows, flow=None)
        if flow_name == 'plan':
            # Multi-step mode: PEX's hook-1 read consumes the stacked plan off the flow stack.
            # The step decomposition (S7's find → outline → schedule) is round 3.5's
            # decompose_plan — until that lands, think stacks no steps here and the plan entry
            # records the empty decomposition.
            state.has_plan = True
        if flow_name == 'clarify':
            self.ambiguity_handler.recognize(
                'general',
                metadata={'missing': 'intent', 'top_detection': flow_name},
                observation="I'm not sure what you'd like to do yet — could you clarify the task?",
            )
        return state

    def validate(self, state, op:str='think', prev:str=''):
        """Ends the thinking: ontology fallback + intent correction, rules-based slot repair,
        then the turn's scratchpad entry — every turn writes exactly one (aligned /
        announcement / click / plan). `prev` is the flow PEX was running at think's stackon
        decision point — it labels the entry aligned vs announcement and fills `prev_flow`.
        The announcement carries `is_newborn: true` as the consumed marker (the scratchpad's
        read() flips it) plus NLU's rationale."""
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
        entry = {'version': 1, 'turn_number': self.world.context.turn_id, 'used_count': 0}
        if op == 'react':
            entry.update(gold_dax=state.pred_flow,
                         summary=f'click resolved {detected} from its dax')
        elif state.has_plan:    # plan: summary only — hook 1 reads the stacked plan itself
            steps = [step.name() for step in self.world.flows._stack]
            entry['summary'] = 'plan: stacked ' + (' → '.join(steps) if steps else 'no steps yet')
        elif detected == prev:
            entry['summary'] = f'aligned on {detected}'
        elif flow is None:      # non-policy detection (clarify) — nothing stacked to announce
            entry['summary'] = f'detected {detected}; nothing stacked'
        else:
            summary = (f'added {detected} to the stack before completing {prev}' if prev
                       else f'added {detected} to the stack')
            entry.update(prev_flow=prev, new_flow=detected, is_newborn=True, summary=summary,
                         rationale=state.pred_flows[0].get('rationale', '') if state.pred_flows else '',
                         question=self.ambiguity_handler.observation)
        self.world.scratchpad.append_entry('nlu', entry)
        return state

    def _repair_slots(self, flow):
        """validate's rule pass (3.4.2): preserve the established entity identity, shape-check
        snip, and never trust a predicted ver. Rules only — no LLM. Targets are exempt from
        the post/sec preserve rule (a new post title legitimately differs from the grounded
        post)."""
        grounded = self.world.state.get_active_entity()
        for name, slot in flow.slots.items():
            if slot.slot_type not in ('source', 'target', 'removal') or not slot.values:
                continue
            for pred in slot.values:
                if slot.slot_type in ('source', 'removal'):
                    for part in ('post', 'sec'):
                        if grounded.get(part) and pred.get(part) and pred[part] != grounded[part]:
                            question = f'switch {name} from {grounded[part]} to {pred[part]}?'
                            self.ambiguity_handler.recognize('confirmation',
                                metadata={'missing': name, 'question': question})
                            self.world.scratchpad.append_entry('nlu', {'version': 1,
                                'turn_number': self.world.context.turn_id, 'used_count': 0,
                                'summary': f'{name} conflict on {part}: kept {grounded[part]}'})
                            pred[part] = grounded[part]      # the live target wins
                if pred.get('snip') and not _valid_snip(pred['snip']):
                    pred['snip'] = ''                        # a description is not a snippet id
                same_entity = (pred.get('post') == grounded.get('post')
                               and pred.get('sec') == grounded.get('sec'))
                pred['ver'] = grounded.get('ver', False) if same_entity else False
            slot._rebuild_keys()
            slot.check_if_filled()

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

    # ── Prediction ────────────────────────────────────────────────────

    def _intent_split(self, detection:dict) -> bool:
        """True only when the ranked flows span >1 intent AND top-1 is under the confidence floor —
        the one case a coarse-intent tie-break is worth a call. Under D1-A the span clause is almost
        always true, so the confidence clause is the real trigger. At most one extra classify + one
        extra detect per turn."""
        intents = {FLOW_ONTOLOGY[flow['name']]['intent'] for flow in detection['pred_flows']}
        return len(intents) > 1 and detection['confidence'] < self.ambiguity_handler.confidence_min

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

    def _raise_if_debug(self, ecp:Exception):
        if self.config.get('debug', False):
            raise ecp

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
        truth for predictions. Each pred_flows entry is {name, dax, confidence, rationale?}.
        Slot predictions live on the flow itself (the stacked flow carries them), never on the
        state. Never inserts a new per-turn state; PEX stages and activates."""
        state = self.world.state
        cat = FLOW_ONTOLOGY.get(flow_name, {})
        state.pred_intent = cat.get('intent', Intent.CONVERSE)
        state.pred_flow = flow2dax(flow_name)
        state.confidence = confidence
        state.pred_flows = pred_flows
        return state

# Module alias — the module is NLU; the class name spells it out.
NLU = NaturalLanguageUnderstanding
