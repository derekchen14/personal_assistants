import logging

log = logging.getLogger(__name__)


_PARTIAL_FRAMING = {
    'query':    "Which {entity} should I query?",
    'lookup':   "Which {entity} should I look up?",
    'describe': "Which {entity} should I describe?",
    'compare':  "Which {entity}s should I compare?",
    'segment':  "Which {entity} should I segment?",
    'pivot':    "Which {entity} should I pivot?",
    'plot':     "Which {entity} should I plot?",
    'trend':    "Which {entity} should I trend?",
    'validate': "Which {entity} should I validate?",
    'format':   "Which {entity} should I format?",
    'fill':     "Which {entity} should I fill?",
    'replace':  "Which {entity} should I replace?",
    'dedupe':   "Which {entity} should I dedupe?",
    'join':     "Which {entity}s should I join?",
    'merge':    "Which {entity}s should I merge?",
    'split':    "Which {entity} should I split?",
}


class AmbiguityHandler:

    def __init__(self, config, engineer=None):
        self.config = config
        self.engineer = engineer
        thresholds = config.get('thresholds', {})
        self.confidence_min = thresholds.get('nlu_confidence_min', 0.64)
        self.max_turns = thresholds.get('ambiguity_escalation_turns', 3)

        self.level: str = ''
        self.metadata: dict = {}
        self.observation: str = ''
        self.counts: dict[str, int] = {
            'general': 0, 'partial': 0, 'specific': 0, 'confirmation': 0,
        }

    def declare(self, level:str, metadata:dict={}, observation:str=''):
        self.level = level
        self.metadata = metadata
        self.observation = observation
        if level in self.counts:
            self.counts[level] += 1

    def present(self, name:bool=False):
        if name:
            return self.level if self.level else 'None'
        else:
            return bool(self.level)

    def ask(self, flow_name:str='') -> str:
        if self.observation:
            return self.observation

        match self.level:
            case 'general': response = self._general_ask()
            case 'partial': response = self._partial_ask(flow_name)
            case 'specific': response = self._specific_ask()
            case 'confirmation': response = self._confirmation_ask()
        return response

    def resolve(self):
        self.level = ''
        self.metadata = {}
        self.observation = ''

    def needs_clarification(self, confidence:float) -> bool:
        return confidence < self.confidence_min

    def should_escalate(self) -> bool:
        return sum(self.counts.values()) >= self.max_turns

    def _general_ask(self) -> str:
        missing = self.metadata.get('missing', 'intent')
        if missing == 'intent':
            return ("I'm not sure what you'd like to do — clean, transform, "
                    "analyze, or report on the data?")
        return "I'm not sure how to handle that yet — could you say it differently?"

    def _partial_ask(self, flow_name:str='') -> str:
        entity = self.metadata.get('entity', self.metadata['missing'])
        phrase = _PARTIAL_FRAMING.get(flow_name)
        if phrase and entity in ('table', 'column', 'row'):
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
