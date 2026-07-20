import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from backend.prompts.for_experts import (build_flow_prompt, render_flow_ontology,
                                         INTENT_CRITERIA, INTENT_QUESTION, NOUL_THRESHOLD,
                                         PLAN_NOUL, CLARIFY_NOUL)
from backend.prompts.for_nlu import build_slot_filling_prompt, build_shown_candidates
from backend.utilities.services import PostService
from schemas.ontology import FLOW_ONTOLOGY, INTENTS
from utils.helper import flow2dax, dax2flow

log = logging.getLogger(__name__)

ENTITY_PARTS = ('post', 'sec', 'snip', 'chl', 'ver')

_ENTITY_MAPPER = {'snippet': 'snip', 'post': 'post', 'section': 'sec', 'channel': 'chl'}


def _flow_detection_schema(candidate_flow_names:list[str]) -> dict:
    return {
        'type': 'object',
        'properties': {
            'reasoning': {
                'type': 'string',
                'description': 'Terse rationale (<100 tokens) naming the key signals that separate the top candidates.',
            },
            # Usually one entry; a Plan turn lists its steps in execution order; an empty
            # list is an abstention (non-emptiness is enforced in code, not the schema —
            # the abstention IS a valid output).
            'flows': {'type': 'array',
                      'items': {'type': 'string', 'enum': list(candidate_flow_names)}}
        },
        'required': ['reasoning', 'flows'],
        'additionalProperties': False,
    }


def _fill_slots_schema(flow) -> dict:
    """Build the JSON schema for slot-fill. Only includes unfilled slots since filled values
    are considered correct. The entity slot is treated like any other slot."""
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


def _split_payload(payload:dict) -> tuple[dict, dict]:
    entity_dict, filtered_payload = {}, {}
    for key, val in payload.items():
        if key in _ENTITY_MAPPER:
            entity_dict[_ENTITY_MAPPER[key]] = val
        else:
            filtered_payload[key] = val
    return entity_dict, filtered_payload


def _extract_entities(flow, entity_dict:dict) -> bool:
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


def _unpack_user_actions(flow, payload:dict):
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

class DialogueState:
    """The main object holding the assistant's belief, owned by NLU and shared through the World.
    It lives for the session lifetime and is not re-created per turn."""
    def __init__(self, config):
        self.config = config
        self._posts = PostService()
        self.reset()

    def reset(self):
        """ each predicted flow is of the form: {
            'name': str,
            'dax': 3-digit str, 
            'confidence': float from 0.0 to 1.0
            'rationale' (optional): 'str'
        }  """
        self.pred_intent = ''  # from PEX
        self.pred_flows: list[dict] = []
        self.pred_flow = ''    # top detection's dax
        self.confidence = 0.0  # top detection's ensemble agreement
        self.keep_going = False  # "this turn still has PEX work" — prepare() sets True,
                                 # orchestrate()'s terminal paths set False (round 2.16)

        """ each entity for the blog domain is {post, sec, snip, chl, ver}
        In most cases, there is only on active entity in the list """
        self.grounding = {'choices': [], 'notes': [], 'entities': []}
        self.conversation_id: str = ''
        self.username = ''
        self.has_plan = False # signals that multiple flows are valid
        self.has_issues = False  # signals need for contemplation
        self.turn_id = 0  # snapshot of Context.num_utterances, recorded by MEM at save time (a consumer)

    def flow_name(self, string=True, threshold=0.0):
        candidates = [flow for flow in self.pred_flows if flow['confidence'] > threshold]
        if not candidates:
            return None
        return candidates[0]['name'] if string else candidates[0]['dax']

    def save(self, path):
        """Rewrite state.json — the single document form, one write per write_state."""
        Path(path).write_text(json.dumps(self.read_state(), indent=2), encoding='utf-8')

    @classmethod
    def load(cls, path):
        """Rebuild a past session's state from its state.json — a MEM read of the disk record
        (a throwaway view object), never a rebind of the live world.state."""
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        session, beliefs = data['session'], data['beliefs']
        state = cls(config={})
        state.pred_intent = beliefs['intent']
        state.pred_flows = beliefs['flows']
        state.conversation_id = session['convo_id']
        state.username = session['username']
        state.has_plan = session['has_plan']
        state.has_issues = session['has_issues']
        state.turn_id = session['turn_id']
        state.grounding = data['grounding']
        return state

    # ── read_state / write_state tool surfaces ─────────
    # These methods are the callable surface for the tool catalog.

    def get_active_post(self) -> str:
        return self.get_active_entity().get('post', '')

    def get_active_entity(self) -> dict:
        entities = self.grounding.get('entities') or []
        if not entities:
            return {}
        return {part: entities[0].get(part, False if part == 'ver' else '') for part in ENTITY_PARTS}

    def set_active_entity(self, **parts) -> dict:
        entity = self.get_active_entity() or {part: False if part == 'ver' else '' for part in ENTITY_PARTS}
        for part, value in parts.items():
            if part not in ENTITY_PARTS:
                raise KeyError(f'Unknown entity part: {part!r}')
            entity[part] = value
        entities = self.grounding.setdefault('entities', [])
        if entities:
            entities[0] = entity
        else:
            entities.append(entity)
        return entity

    def read_state(self) -> dict:
        # serialize and return the dialogue state
        beliefs = {'intent': self.pred_intent, 'flows': self.pred_flows}
        session = {'convo_id': self.conversation_id, 'username': self.username,
                    'has_plan': self.has_plan, 'has_issues': self.has_issues,
                    'turn_id': self.turn_id}
        state = {'session': session, 'beliefs': beliefs, 'grounding': self.grounding}
        return state

    # ── Prediction (detect_flows / fill_slots — collaborators passed per call, never stored) ──

    def active_post_dict(self) -> dict | None:
        post_id = self.get_active_post()
        if not post_id:
            return None
        title = self._posts.get_title(post_id)
        if not title:
            return None
        return {'id': post_id, 'title': title}

    def classify_intent(self, engineer, context, prev_flow) -> str:
        """A quick System-1 decision on the next step. Choose from:
        a. Standard intents - which are mapped to basic flows: {000}, {001}, {002}, {003}, {004}
        b. Plan intent - which implies a multi-step task
        c. Clarify intent - implies none of the above, or underspecified request
        d. Continue - which means we just continue on with the current active flow
        The classified intent is stored within `self.pred_intent`.
        """
        criteria = dict(INTENT_CRITERIA)
        if prev_flow:
            continue_desc = (f'The turn continues on with `{prev_flow.name()}`, the task already in progress'
                             '— an answer, a detail, an approval, or "keep going".')
            criteria['Continue'] = (continue_desc)
            
        document = {'history': context.compile_history(), 'utterance': context.last_user_utt}
        questions = {'intent': {'type': 'choice', 'instructions': INTENT_QUESTION, 'criteria': criteria},
                     'has_plan': PLAN_NOUL, 'needs_clarify': CLARIFY_NOUL}
        try:
            answers = engineer.typesafe(document, questions)
            plan, clarify = answers['has_plan']['noul'], answers['needs_clarify']['noul']
            if plan >= NOUL_THRESHOLD or clarify >= NOUL_THRESHOLD:
                intent = 'Plan' if plan >= clarify else 'Clarify'
                self.pred_flows = []
            elif answers['intent']['choice'] == 'Continue':
                intent = self.pred_intent
                # no change needed to predicted flows
            else:
                intent = answers['intent']['choice']
                dax = f'00{INTENTS.index(intent)}'
                flow_name = dax2flow(dax)
                self.pred_flows = [{'name': flow_name, 'dax': dax, 'confidence': 0.5}]

        except Exception as ecp:
            log.warning(f'intent classification failed: {ecp}')
            if self.config.get('debug', False): raise ecp
            intent = ''
        self.pred_intent = intent
        return intent

    def detect_flows(self, engineer, context, user_text:str, snippet:str='', working:str=''):
        """Ensemble flow detection — two to five voters, confidence = voter agreement. `snippet` is
        the extra prompt block check() picked; `working` is the flow already in progress
        (check() reads it off the stack the belief no longer carries last turn's detection). 
        A working flow narrows candidates to that flow + its edges and seeds the vote; 
        any other hint narrows to the intent's flows."""
        hint = working or self.pred_intent
        convo_history = context.compile_history()
        prompt = self._detection_prompt(user_text, hint, convo_history)
        if snippet:
            prompt += '\n\n' + snippet
        schema = _flow_detection_schema(self._candidate_names(hint))

        votes: list[dict] = []
        med_families = ('claude', 'gemini', 'gpt')
        if hint in FLOW_ONTOLOGY:
            pex_family = self._orchestrator_family()
            votes.append({'flows': [hint], '_model': pex_family, '_tier': 'med'})
            med_families = tuple(fam for fam in med_families if fam != pex_family)
        votes += self._collect_votes(engineer, med_families, 'med', prompt, schema)
        if not votes:
            return {
                'flows': ['chat'], 'confidence': 0.3,
                'pred_flows': [{'name': 'chat', 'dax': flow2dax('chat'), 'confidence': 0.3}],
            }
        detection = self._tally_votes(votes)
        confidence_min = self.config.get('thresholds', {}).get('nlu_confidence_min', 0.64)
        if detection['confidence'] < confidence_min:
            votes += self._collect_votes(engineer, ('gemini', 'claude'), 'high', prompt, schema)
            detection = self._tally_votes(votes)
        return detection

    def ground_flow(self, flow):
        """The grounding backstop, split out of fill_slots (round 2.13.3): transfer the
        session's active post into the flow's empty entity slots. Callers run it BEFORE
        fill_slots on the ordinary paths; think's same-type reconciliation skips it so a
        user-named NEW entity stays in the fill schema instead of being masked by the
        pre-fill. Gate on `slot.values` (not `slot.filled`) so a slot already partially
        populated isn't double-grounded."""
        active_post = self.get_active_post()
        if active_post:
            for slot in flow.slots.values():
                if slot.slot_type in ('source', 'target') and not slot.values:
                    slot.add_one(post=active_post)

    def fill_slots(self, engineer, context, flow, payload:dict, ambiguity):
        """Fill the LIVE flow's open slots — payload extraction, then the LLM fill (the
        grounding backstop is the caller's step, `ground_flow`). The entity slot is treated
        like any other slot; repair is validate's job."""
        if payload:
            entity_dict, filtered = _split_payload(payload)
            extracted = _extract_entities(flow, entity_dict)
            # A payload only ever arrives on an action turn (internal FE contract) — no
            # turn_type re-check.
            if not extracted and filtered:
                _unpack_user_actions(flow, filtered)

        if flow.is_filled():
            return
        convo_history = context.compile_history()
        prompt = build_slot_filling_prompt(flow, convo_history, self.active_post_dict())
        # The shown-candidates block rides the prompt whenever choices exist (2.13.1) — a fresh
        # flow resolves "those two published posts" from the list the user just saw; the
        # pending-question framing wraps the same block only when an ambiguity is open.
        if self.grounding['choices'] or ambiguity.is_present:
            prompt += '\n\n' + build_shown_candidates(self.grounding['choices'],
                                                      ambiguity.observation,
                                                      pending=ambiguity.is_present)
        for attempt in (1, 2):
            try:
                parsed = engineer(prompt, task='fill_slots', max_tokens=2048,
                                  schema=_fill_slots_schema(flow))
            except ValueError:
                parsed = {}
            if 'slots' in parsed:
                break
            log.warning('[fill_slots] schema violation flow=%s attempt=%s payload=%s',
                        flow.name(), attempt, parsed)
        if 'slots' not in parsed:
            log.warning('[fill_slots] convo_history=\n%s', convo_history)
            log.warning('[fill_slots] filled-state: %s', {n: s.filled for n, s in flow.slots.items()})
            return
        cleaned = engineer._strip_nulls(parsed['slots'])
        flow.fill_slot_values(cleaned)

    def _detection_prompt(self, user_text:str, hint:str, convo_history:str) -> str:
        from backend.components.flow_stack import flow_classes
        candidate_names = self._candidate_names(hint)
        ontology = render_flow_ontology(candidate_names, FLOW_ONTOLOGY, flow_classes)
        # A flow-name hint (Continue) borrows its flow's intent for the prompt content; the
        # candidate narrowing already carries the flow-level signal.
        intent = FLOW_ONTOLOGY[hint]['intent'] if hint in FLOW_ONTOLOGY else hint
        return build_flow_prompt(user_text, intent, convo_history,
                                 ontology, active_post=self.active_post_dict())

    def _candidate_names(self, hint:str='') -> list[str]:
        if not hint:
            return list(FLOW_ONTOLOGY)
        if hint in FLOW_ONTOLOGY:   # Continue: the Active flow's name narrows to it + its edges
            return [hint, *FLOW_ONTOLOGY[hint]['edge_flows']]
        edges = set()
        for name, cat in FLOW_ONTOLOGY.items():
            if cat['intent'] == hint:
                edges.update(cat.get('edge_flows', []))
        names = [name for name, cat in FLOW_ONTOLOGY.items()
                 if cat['intent'] == hint or name in edges]
        # Narrowing that produces zero candidates falls back to the full list — Plan and
        # Clarify own no flows, so detection under those intents runs over everything.
        return names or list(FLOW_ONTOLOGY)

    def _orchestrator_family(self) -> str:
        """The model family PEX runs on — its voters are the OTHER two families. Prefix match,
        since the orchestrator model id need not appear in the voter tier table."""
        model_id = self.config['models']['overrides']['orchestrator']['model_id']
        for family in ('claude', 'gemini', 'gpt'):
            if model_id.startswith(family):
                return family
        raise ValueError(f'orchestrator model {model_id!r} maps to no voter family')

    def _collect_votes(self, engineer, families:tuple, level:str, prompt:str, schema:dict) -> list[dict]:
        def _call_voter(family:str) -> dict | None:
            try:
                parsed = engineer(prompt, task='detect_flow', family=family, tier=level,
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
                if not recoverable and self.config.get('debug', False):
                    raise ecp
                return None

        votes: list[dict] = []
        with ThreadPoolExecutor(max_workers=len(families)) as pool:
            futures = [pool.submit(_call_voter, family) for family in families]
            for future in as_completed(futures):
                result = future.result()
                if result and isinstance(result.get('flows'), list):
                    # An empty list is a deliberate abstention — a vote for nothing that still
                    # counts in the majority denominators (round 3.5).
                    result['flows'] = [flow for flow in result['flows'] if flow in FLOW_ONTOLOGY]
                    votes.append(result)
        return votes

    def _tally_votes(self, votes:list[dict]) -> dict:
        """Per-flow majority tally over list votes (round 3.5 defaults, revisit later):
        every flow any voter names goes through the tally; majority support survives.
        The Claude voter's proposed order is canonical; survivors it never named follow in
        support order, dropped flows rank after. All-abstain (every voter returned an empty
        list) is the no-detection signal — think stacks nothing and the zero confidence
        raises a clarification."""
        unique: list[str] = []
        for vote in votes:
            for flow in vote['flows']:
                if flow not in unique:
                    unique.append(flow)
        if not unique:
            return {'flows': [], 'confidence': 0.0, 'pred_flows': []}
        support = {flow: sum(1 for vote in votes if flow in vote['flows']) for flow in unique}
        survivors = [flow for flow in unique if support[flow] * 2 > len(votes)]
        if not survivors:   # no majority anywhere — keep the single best-supported flow
            survivors = [max(unique, key=support.get)]
        claude = next((vote['flows'] for vote in votes if vote['_model'] == 'claude'), [])
        ordered = [flow for flow in claude if flow in survivors]
        ordered += sorted((flow for flow in survivors if flow not in ordered),
                          key=lambda flow: -support[flow])
        dropped = sorted((flow for flow in unique if flow not in survivors),
                         key=lambda flow: -support[flow])
        pred_flows = [{'name': name, 'dax': flow2dax(name),
                       'confidence': support[name] / len(votes)} for name in ordered + dropped]
        # One majority voter's reasoning rides along as the winning flow's rationale.
        rationale = next((vote['reasoning'] for vote in votes
                          if ordered[0] in vote['flows'] and vote.get('reasoning')), '')
        if rationale:
            pred_flows[0]['rationale'] = rationale
        return {'flows': ordered, 'confidence': self._score_votes(votes, ordered[0]),
                'pred_flows': pred_flows}

    def _score_votes(self, votes:list[dict], best_flow:str) -> float:
        """Confidence is voter AGREEMENT, never a self-reported score (models can't calibrate
        their own confidence). Round 1 (the 3 medium voters): all agree 0.9, majority 0.7, full
        split 0.5/0.3 by whether the split stays within one intent. Round 2 (5 votes): the
        (agreement, intent-spread) ladder, +0.1 when the two high voters agree with each other.
        With list votes agreement CAN reach 4-5 of 5 (a flow rides several voters' lists after
        the mediums split on their primaries) — the ladder saturates at its (3, ·) row.
        Membership counts a vote naming best_flow anywhere in its list; the intent spread reads
        each voter's primary (first) flow, skipping abstentions."""
        agree = sum(1 for vote in votes if best_flow in vote['flows'])
        intents = len({FLOW_ONTOLOGY[vote['flows'][0]]['intent'] for vote in votes
                       if vote['flows']})

        if len(votes) <= 3:   # round 1: only the medium voters have voted
            if agree == len(votes):
                return 0.9
            return 0.7 if agree > 1 else (0.5 if intents == 1 else 0.3)

        ladder = {(3, 1): 0.8, (3, 2): 0.7, (3, 3): 0.5,
                  (2, 1): 0.6, (2, 2): 0.4, (2, 3): 0.3,
                  (1, 1): 0.2, (1, 2): 0.2, (1, 3): 0.1}
        confidence = ladder[(min(agree, 3), min(intents, 3))]
        high = [vote['flows'][0] for vote in votes if vote['_tier'] == 'high' and vote['flows']]
        if len(high) == 2 and high[0] == high[1]:
            confidence += 0.1
        return confidence