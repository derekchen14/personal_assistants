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

    # ── Main methods: react / think / contemplate (round 3.4) ─────────
    # The Assistant calls these directly — `understand` survives only as the name of PEX's
    # tool. Each ends in validate(), which writes the turn's scratchpad entry.

    def check(self) -> tuple:
        """Opens `think` with the preliminary work (round 3.4): prior ambiguity is ALWAYS
        cleared here — the dynamic, situation-dependent resolve comes in a later round — and
        the extra detection-prompt snippet is picked for the classified intent (Continue reads
        very differently from Plan or Clarify). Returns (snippet, working). The working flow
        is the LIVE stack's in-flight flow, kept only when this turn's classified intent
        matches it — the Continue reading. It reads the stack, not the belief, because
        classify_intent writes the belief flow at prediction time (round 2.16), so pred_flows
        no longer preserves last turn's detection."""
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
        """One path: check → detect_flows → fill_slots → validate. Stacks and fills the LIVE
        flow — no transient, no copy step. Any disagreement with what PEX is running is
        resolved on PEX's side (the hook 3/5 read of validate's entry)."""
        snippet, working = self.check()
        state, context = self.world.state, self.world.context
        detection = state.detect_flows(self.engineer, context, user_text, snippet, working)
        if self._intent_split(detection):                   # low-confidence AND spans >1 intent
            state.classify_intent(self.engineer, context, self.world.flows.get_flow())
            if intent2flow(state.pred_intent):  # domain intents only — Plan/Clarify add no
                detection = state.detect_flows(self.engineer, context, user_text,  # narrowing
                                               detection_snippet(state.pred_intent))

        predicted = detection.get('pred_flows', [])
        if not detection['flows']:   # every voter abstained (round 3.5) — stack nothing, ask
            state.pred_flow = ''
            state.pred_flows = []
            state.confidence = detection['confidence']
            self.ambiguity_handler.recognize('general', metadata={'missing': 'intent'},
                observation="I'm not sure what you'd like to do yet — could you clarify the task?")
            self.review_scratchpad()
            return self.validate(state, 'think')

        steps = detection['flows']
        if state.pred_intent == 'Plan' and len(steps) > 1:
            # The Plan Flow oversees, it does not do the work: the marker stacks first
            # (Pending, at the bottom) with the steps' checklist filled directly — no LLM
            # slot fill — then the steps in reverse execution order, first step Active.
            state.has_plan = True
            marker = self.world.flows.stackon('plan', transfer=False, active=False)
            for step in steps:
                marker.slots['steps'].add_one(step)
            for step in reversed(steps):                    # last step first → first on top
                self.world.flows.stackon(step, transfer=False, active=False)
            curr_flow = self.world.flows.get_flow()
            curr_flow.status = 'Active'                     # the first step runs; the rest wait
            # The first step grounds and fills like the single-flow path (2.14.3) — its
            # originating utterance is live, so the LLM fill is worth one call. Later steps
            # ground inside pex.execute() when promoted.
            state.ground_flow(curr_flow)
            state.fill_slots(self.engineer, context, curr_flow, payload, self.ambiguity_handler)
            state = self._write_belief(steps[0], detection['confidence'], predicted, curr_flow)
            self.review_scratchpad()
            return self.validate(state, 'plan')

        flow_name = steps[0]
        prev_flow = self.world.flows.get_flow()
        # An in-flight flow counts whether Active or Pending — a plan step stacked with
        # active=False waits as Pending and is still the flow PEX runs next.
        in_flight = bool(prev_flow) and prev_flow.status in ('Active', 'Pending')
        prev = prev_flow.name() if in_flight else ''
        repeat = in_flight and prev_flow.name() == flow_name
        # The reconciliation gate matches stackon's dedupe condition exactly (entity slot
        # FILLED), so the stackon below always pushes a real second instance.
        entity = prev_flow.slots.get(prev_flow.entity_slot) if repeat else None
        if repeat and entity and entity.check_if_filled():
            # Same-type detection over a GROUNDED flow (round 2.13.3, post-fill
            # reconciliation): push a second instance without the grounding backstop, so the
            # fill schema keeps the entity slot open and a user-named new target can land.
            # Same identity after the fill (or none named) → fold the fill back into the
            # original and drop the extra entry; a different identity is a new task and both
            # instances stay (validate announces the second one).
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
        """The failed-flow re-route — the Assistant calls this after PEX queues the request
        (3.4.7). One re-route call over the failed flow's edges + the current flow + chat, then
        the replacement is stacked directly. No LLM slot fill: stackon's transfer carries the
        failed flow's slots and the policy's fill_slots_by_label covers gaps. Ends in
        validate like think/react — the announcement is the re-route's record."""
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
                # Single re-route call, no ensemble to agree — score it as a majority vote (0.7).
                detection = {'flows': [parsed['flows'][0]], 'confidence': 0.7}
        except Exception as ecp:
            log.warning('contemplate routing failed: %s', ecp)
            self._raise_if_debug(ecp)

        flow_name = detection['flows'][0]
        curr_flow = self.world.flows.stackon(flow_name, transfer=not self.ambiguity_handler.is_present)
        state = self._write_belief(flow_name, detection['confidence'],
            [{'name': flow_name, 'dax': flow2dax(flow_name),
              'confidence': detection['confidence']}], curr_flow)

        # The turn's text must be a string — compile_messages renders it as an API text block.
        text = f"re-detected '{flow_name}' (confidence {detection['confidence']})"
        turn_content = {'text': text, 'tool_uses': [], 'tool_results': []}
        self.world.context.add_turn('agent', turn_content, turn_type='action')
        self.world.context.add_turn('system', {'text': '[contemplate] NLU re-routed the flow based on contemplation.'})
        return self.validate(state, 'think', failed or '')


    def validate(self, state, op:str='think', prev:str=''):
        """Ends the thinking: ontology fallback + intent correction, rules-based slot repair,
        then the turn's scratchpad entry — every turn writes exactly one (aligned /
        announcement / click / plan / abstention). `prev` is the flow PEX was running at think's stackon
        decision point — it labels the entry aligned vs announcement and fills `prev_flow`.
        The announcement carries `is_newborn: true` as the consumed marker (the scratchpad's
        read() flips it) plus NLU's rationale."""
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
        entry = {'version': 1, 'turn_number': self.world.context.num_utterances, 'used_count': 0}
        if op != 'react' and state.pred_flows:
            # The candidate flows and their tallies ride the entry — PEX's back-up channel to
            # stack a dropped flow later (support at or below 0.5 marks a dropped flow).
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
        elif detected == prev and _repeat_count(self.world.flows, detected) <= 1:
            # Two live same-name instances mean reconciliation kept a second task on a new
            # entity (2.13.3) — that falls through to the announcement below, same-name or not.
            entry['summary'] = f'aligned on {detected}'
        elif flow is None:      # ontology fallback fired — nothing stacked to announce
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
        # An entity picked from the CURRENTLY shown choices is a deliberate selection (2.13.1)
        # — the preserve rule polices hallucinated switches, not on-screen picks.
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
                            self.world.scratchpad.append_entry('nlu', {'version': 1,
                                'turn_number': self.world.context.num_utterances, 'used_count': 0,
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
        result, success = self.ambiguity_handler.recover(self.world.prefs, self.world.scratchpad)
        entry = {'version': 1, 'turn_number': self.world.context.num_utterances,
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
                       'turn_number': self.world.context.num_utterances, **entry}
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
        state.pred_intent = cat.get('intent', 'Converse')
        state.pred_flow = flow2dax(flow_name)
        state.confidence = confidence
        state.pred_flows = pred_flows
        return state


def _repeat_count(flows, name:str) -> int:
    """How many live (Active/Pending) instances of `name` sit on the stack — more than one
    means reconciliation kept a second same-type task (round 2.13.3)."""
    return sum(1 for entry in flows._stack
               if entry.flow_type == name and entry.status in ('Active', 'Pending'))


def _entity_ids(flow) -> set:
    """The flow's task identity (round 2.13.3): its entity slot's values reduced to the domain
    parts (post/sec/snip/chl — `ver` is bookkeeping, ignored), so equivalent serialized shapes
    compare equal. String-valued entity slots (find.query, chat.topic) compare as strings."""
    slot = flow.slots.get(flow.entity_slot)
    ids = set()
    for val in (getattr(slot, 'values', None) or []):
        if isinstance(val, dict):
            ids.add(tuple(val.get(part, '') for part in ('post', 'sec', 'snip', 'chl')))
        else:
            ids.add(str(val))
    return ids


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


# Module alias — the module is NLU; the class name spells it out.
NLU = NaturalLanguageUnderstanding
