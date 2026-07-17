import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from backend.prompts.for_experts import (build_flow_prompt, render_flow_ontology,
                                         INTENT_CRITERIA, INTENT_QUESTION, NOUL_THRESHOLD,
                                         PLAN_NOUL, CLARIFY_NOUL)
from backend.prompts.for_nlu import build_slot_filling_prompt, build_pending_question
from backend.utilities.services import PostService
from schemas.ontology import FLOW_ONTOLOGY
from utils.helper import flow2dax, intent2flow

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
            'flow_name': {'type': 'string', 'enum': list(candidate_flow_names)}
        },
        'required': ['reasoning', 'flow_name'],
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

        """ each entity for the blog domain is {post, sec, snip, chl, ver}
        In most cases, there is only on active entity in the list """
        self.grounding = {'choices': [], 'notes': [], 'entities': []}
        self.conversation_id: str = ''
        self.username = ''
        self.has_plan = False # signals that multiple flows are valid
        self.has_issues = False  # signals need for contemplation
        self.turn_count = 0

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
        state.turn_count = session['turn_count']
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
                    'turn_count': self.turn_count}
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

    def classify_intent(self, engineer, context, user_text:str) -> str:
        """The turn's first model call (NLU 1) — one TypeSafe request (`engineer.typesafe`,
        the non-LLM System-1 model) with three questions fanned out: a Choice over the domain
        intents (+ Continue when a continuable flow is grounded) and the two nouls. Either
        noul at or above NOUL_THRESHOLD IS the intent — Plan or Clarify, the higher of the
        two when both cross; otherwise the Choice's pick stands. 'Continue' is never stored:
        it maps to the working flow's intent before the write (audit + Continue → 'Revise').
        A failed call stores '' — no signal, so detection runs over the full ontology."""
        flow = self.flow_name(string=True)
        working = flow if flow and intent2flow(FLOW_ONTOLOGY[flow]['intent']) else ''
        criteria = dict(INTENT_CRITERIA)
        if working:
            criteria['Continue'] = (f'The turn advances `{working}`, the task already in '
                                    f'progress — an answer, a detail, an approval, or '
                                    f'"keep going".')
        document = {'history': context.compile_history(), 'utterance': user_text}
        questions = {'intent': {'type': 'choice', 'instructions': INTENT_QUESTION,
                                'criteria': criteria},
                     'has_plan': PLAN_NOUL, 'needs_clarify': CLARIFY_NOUL}
        try:
            answers = engineer.typesafe(document, questions)
            plan, clarify = answers['has_plan']['noul'], answers['needs_clarify']['noul']
            if plan >= NOUL_THRESHOLD or clarify >= NOUL_THRESHOLD:
                intent = 'Plan' if plan >= clarify else 'Clarify'
            else:
                intent = answers['intent']['choice']
        except Exception as ecp:
            log.warning('intent classification failed: %s', ecp)
            if self.config.get('debug', False):
                raise ecp
            intent = ''
        if intent == 'Continue':
            intent = FLOW_ONTOLOGY[working]['intent']
        self.pred_intent = intent
        return intent

    def detect_flows(self, engineer, context, user_text:str, snippet:str=''):
        """Ensemble flow detection — 2-5 voters, confidence = voter agreement. Nothing is
        passed in beyond the turn: the working intent is read off the belief (`pred_intent`).
        'Continue' is never stored (classify_intent maps it to the Active flow's intent), so
        a Continue reading is pred_intent matching the belief flow's intent — it narrows
        candidates to that flow + its edges and seeds the vote; any other intent narrows to
        its flows. `snippet` is the extra prompt block check() picked."""
        flow = self.flow_name(string=True)
        working = flow if (flow and intent2flow(self.pred_intent)   # only domain intents continue
                          and self.pred_intent == FLOW_ONTOLOGY[flow]['intent']) else ''
        hint = working or self.pred_intent
        convo_history = context.compile_history()
        prompt = self._detection_prompt(user_text, hint, convo_history)
        if snippet:
            prompt += '\n\n' + snippet
        schema = _flow_detection_schema(self._candidate_names(hint))

        votes: list[dict] = []
        med_families = ('claude', 'gemini', 'gpt')
        if hint in FLOW_ONTOLOGY:
            # Continue: PEX already offered a flow-level vote for the Active flow — seed it and
            # poll only the two families PEX is NOT running on. The tally runs over three votes
            # exactly as on any other turn.
            pex_family = self._orchestrator_family()
            votes.append({'flow_name': hint, '_model': pex_family, '_tier': 'med'})
            med_families = tuple(fam for fam in med_families if fam != pex_family)
        votes += self._collect_votes(engineer, med_families, 'med', prompt, schema)
        if not votes:
            return {
                'flow_name': 'chat', 'confidence': 0.3,
                'pred_flows': [{'name': 'chat', 'dax': flow2dax('chat'), 'confidence': 0.3}],
            }
        detection = self._tally_votes(votes)
        confidence_min = self.config.get('thresholds', {}).get('nlu_confidence_min', 0.64)
        if detection['confidence'] < confidence_min:
            votes += self._collect_votes(engineer, ('gemini', 'claude'), 'high', prompt, schema)
            detection = self._tally_votes(votes)
        return detection

    def fill_slots(self, engineer, context, flow, payload:dict, ambiguity):
        """Fill the LIVE flow's open slots — payload extraction, grounding transfer, then the
        LLM fill. The entity slot is treated like any other slot; repair is validate's job."""
        if payload:
            entity_dict, filtered = _split_payload(payload)
            extracted = _extract_entities(flow, entity_dict)
            if not extracted and context.last_user_turn.turn_type == 'action' and filtered:
                _unpack_user_actions(flow, filtered)

        # Transfer entity grounding from the session to the flow. Gate on `slot.values` (not
        # `slot.filled`) so a slot already partially populated isn't double-grounded.
        active_post = self.get_active_post()
        if active_post:
            for slot in flow.slots.values():
                if slot.slot_type in ('source', 'target') and not slot.values:
                    slot.add_one(post=active_post)

        if flow.is_filled():
            return
        convo_history = context.compile_history()
        prompt = build_slot_filling_prompt(flow, convo_history, self.active_post_dict())
        if ambiguity.is_present:  # the open question + shown candidates, conservative-fill guidance
            prompt += '\n\n' + build_pending_question(ambiguity.observation,
                                                      self.grounding['choices'])
        for attempt in (1, 2):
            try:
                parsed = engineer(prompt, 'fill_slots', max_tokens=2048,
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
        return [name for name, cat in FLOW_ONTOLOGY.items()
                if cat['intent'] == hint or name in edges]

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
                parsed = engineer(prompt, 'detect_flow', family=family, tier=level,
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
                if result and result.get('flow_name') in FLOW_ONTOLOGY:
                    votes.append(result)
        return votes

    def _tally_votes(self, votes:list[dict]) -> dict:
        counts: dict[str, int] = {}
        for vote in votes:
            counts[vote['flow_name']] = counts.get(vote['flow_name'], 0) + 1

        best_flow = max(counts, key=counts.get)
        ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        pred_flows = [{'name': name, 'dax': flow2dax(name), 'confidence': count / len(votes)}
                      for name, count in ranked]
        # One majority voter's reasoning rides along as the winning flow's rationale.
        rationale = next((vote['reasoning'] for vote in votes
                          if vote['flow_name'] == best_flow and vote.get('reasoning')), '')
        if rationale:
            pred_flows[0]['rationale'] = rationale
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