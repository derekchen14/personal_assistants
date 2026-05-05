from types import MappingProxyType

from schemas.ontology import AmbiguityLevel


# Closed vocabulary — never extend without explicit approval.
VALID_LEVELS = frozenset(('general', 'partial', 'specific', 'confirmation'))


class AmbiguityHandler:
    """Closed 4-level ambiguity system. `declare(level, observation=, metadata=)`
    records the level (one of `general | partial | specific | confirmation`),
    the human-readable observation that becomes the clarification question,
    and a sparse classification dict (e.g., `{missing_slot: 'tone'}`).

    Tool failures are NOT ambiguity — they emit a `tool_error` violation
    frame instead. Ambiguity is the only channel that produces a clarification
    question for the user."""

    def __init__(self, config:MappingProxyType, engineer=None):
        self.config = config
        self.engineer = engineer
        thresholds = config.get('thresholds', {})
        self._confidence_min = thresholds.get('nlu_confidence_min', 0.64)
        self._max_turns = thresholds.get('ambiguity_escalation_turns', 3)

        self.level:str|None = None
        self.metadata:dict = {}
        self.observation:str|None = None
        self._counts:dict[str, int] = {'general': 0, 'partial': 0, 'specific': 0, 'confirmation': 0}

    def declare(self, level:str, observation:str|None=None, metadata:dict|None=None):
        if level not in VALID_LEVELS:
            raise ValueError(f"Unknown ambiguity level: {level!r}. Must be one of {sorted(VALID_LEVELS)}.")
        self.level = level
        self.observation = observation
        self.metadata = metadata or {}
        self._counts[level] += 1

    def present(self) -> bool:
        return self.level is not None

    def ask(self) -> str:
        """Return the clarification text. RES naturalizes via the engineer when
        an observation is present; otherwise falls back to a level-shaped default."""
        if self.observation and self.engineer is not None:
            return self._naturalize(self.observation)
        if self.observation:
            return self.observation
        return self._default_ask()

    def _default_ask(self) -> str:
        if self.level == AmbiguityLevel.GENERAL.value:
            return "I'm not quite sure what you're looking for. Could you tell me more?"
        if self.level == AmbiguityLevel.PARTIAL.value:
            missing = self.metadata.get('missing_entity', 'some details')
            return f"I think I understand, but I need {missing}. Could you provide that?"
        if self.level == AmbiguityLevel.SPECIFIC.value:
            slot = self.metadata.get('missing_slot', 'a value')
            return f"I need a specific {slot} to proceed. What would you like to use?"
        if self.level == AmbiguityLevel.CONFIRMATION.value:
            candidate = self.metadata.get('candidate', 'this')
            return f"Just to confirm — did you mean {candidate}?"
        return 'Could you clarify what you mean?'

    def _naturalize(self, observation:str) -> str:
        """Pass observation through the engineer's naturalization path. The
        engineer routes to `skill_call` at the `low` tier under the hood."""
        return self.engineer(observation, task='naturalize', max_tokens=256)

    def resolve(self):
        self.level = None
        self.metadata = {}
        self.observation = None

    def needs_clarification(self, confidence:float) -> bool:
        return confidence < self._confidence_min

    def should_escalate(self) -> bool:
        return sum(self._counts.values()) >= self._max_turns
