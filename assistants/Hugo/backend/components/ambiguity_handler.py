import logging
log = logging.getLogger(__name__)

class AmbiguityHandler:

    def __init__(self, config, engineer=None):
        self.config = config
        self.engineer = engineer
        thresholds = config.get('thresholds', {})
        self.confidence_min = thresholds.get('nlu_confidence_min', 0.64)

        self.is_present: bool = False
        self.metadata: dict = {}
        self.observation: str = ''
        self.counts: dict[str, int] = {
            'general': 0, 'partial': 0, 'specific': 0, 'confirmation': 0,
        }

    def recognize(self, level:str, metadata:dict={}, observation:str=''):
        """Concurrent ambiguities are legal (planner spec scenario 21): metadata merges ADDITIVELY —
        new keys join without kicking out prior information — and counts keep incrementing to show
        several ambiguities are open at once. The observation string is immutable: a newer one
        replaces it wholesale, and nothing ever appends to it."""
        log.info('[ambig-trace] recognize level=%s metadata=%s observation=%r', level, metadata, observation)
        self.metadata = {**self.metadata, **metadata}
        if observation:
            self.observation = observation
        if level in self.counts:
            self.counts[level] += 1
        self.is_present = True

    def get_level(self):
        # return the greatest level of ambiguity
        for level in ['general', 'partial', 'specific', 'confirmation']:
            if self.counts[level] > 0:
                return level
        return ''

    def recover(self, prefs, scratchpad):
        """Try to clear the pending ambiguity internally before escalating: look the missing slot
        up in L2 preferences, then in the scratchpad. Resolve the ambiguity when a value is found;
        the caller (NLU) records the attempt on the scratchpad. Deterministic this round — an
        LLM-judged version is designed-not-built."""
        missing = self.metadata.get('missing', '')
        found = prefs.read(missing).get(missing)
        if not found:
            for entry in scratchpad.read(keys=[missing]):
                found = entry[missing]
                break
        if found:
            self.resolve(explanation=f'recovered {missing}={found} from memory')
            return found, True
        return missing, False

    def ask(self, flow_name:str) -> str:
        if self.observation:
            return self.observation

        match self.get_level():
            case 'general': response = self._general_ask()
            case 'partial': response = self._partial_ask(flow_name)
            case 'specific': response = self._specific_ask()
            case _: response = self._confirmation_ask()
        return response

    def resolve(self, explanation:str=''):
        log.info('[ambig-trace] resolve was=%s explanation=%r', self.get_level(), explanation)
        self.is_present = False
        self.metadata = {}
        self.observation = ''

    def needs_clarification(self, confidence:float) -> bool:
        return confidence < self.confidence_min

    def _general_ask(self) -> str:
        missing = self.metadata.get('missing', 'intent')
        if missing == 'intent':
            return ("I'm not sure what you'd like to work on — drafting, revising, "
                    "publishing, or something else?")
        return "I'm not sure how to handle that yet — could you say it differently?"

    def _partial_ask(self, flow_name:str='') -> str:
        entity = self.metadata.get('entity', self.metadata['missing'])
        match flow_name:
            case 'write':    phrase = "Which {entity} should I edit?"
            case 'audit':    phrase = "Which post should I audit?"
            case 'rework':   phrase = "Which {entity} should I rework?"
            case 'compare':  phrase = "Which posts should I compare?"
            case _:          phrase = ''

        if phrase and entity in ('post', 'section'):
            return phrase.format(entity=entity)
        return f"Which {entity} did you mean?"

    def _specific_ask(self) -> str:
        slot = self.metadata['missing']
        suffix = {
            'invalid_value': " I couldn't find one matching what you said.",
            'unclear_value': ' Your earlier value was a bit unclear.',
            'wrong_slot':    " That value didn't fit the expected field.",
        }.get(self.metadata.get('reason', ''), '')
        return f"What would you like for {slot}?{suffix}"

    def _confirmation_ask(self) -> str:
        if 'question' in self.metadata:
            return self.metadata['question']
        candidates = self.metadata.get('candidates') or []
        if candidates:
            opts = ', '.join(candidates[:-1]) + f", or {candidates[-1]}"
            return f"Did you mean {opts}?"
        candidate = self.metadata.get('candidate')
        if candidate:
            return f'Did you mean "{candidate}"?'
        return 'Should I go ahead with that?'
