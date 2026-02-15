from __future__ import annotations

from types import MappingProxyType

from schemas.ontology import AmbiguityLevel


class AmbiguityHandler:

    def __init__(self, config: MappingProxyType):
        self.config = config
        thresholds = config.get('thresholds', {})
        self._confidence_min = thresholds.get('nlu_confidence_min', 0.64)
        self._max_turns = thresholds.get('ambiguity_escalation_turns', 3)

        self._level: str | None = None
        self._metadata: dict = {}
        self._observation: str | None = None
        self._counts: dict[str, int] = {
            'general': 0, 'partial': 0, 'specific': 0, 'confirmation': 0,
        }

    def declare(self, level: str, metadata: dict | None = None,
                observation: str | None = None):
        self._level = level
        self._metadata = metadata or {}
        self._observation = observation
        if level in self._counts:
            self._counts[level] += 1

    def present(self) -> bool:
        return self._level is not None

    def ask(self) -> str:
        if not self._level:
            return 'Could you tell me more about what you need?'

        if self._level == AmbiguityLevel.GENERAL.value:
            return self._general_ask()
        elif self._level == AmbiguityLevel.PARTIAL.value:
            return self._partial_ask()
        elif self._level == AmbiguityLevel.SPECIFIC.value:
            return self._specific_ask()
        elif self._level == AmbiguityLevel.CONFIRMATION.value:
            return self._confirmation_ask()
        return 'Could you clarify what you mean?'

    def resolve(self):
        self._level = None
        self._metadata = {}
        self._observation = None

    def needs_clarification(self, confidence: float) -> bool:
        return confidence < self._confidence_min

    def should_escalate(self) -> bool:
        total = sum(self._counts.values())
        return total >= self._max_turns

    @property
    def level(self) -> str | None:
        return self._level

    @property
    def metadata(self) -> dict:
        return self._metadata

    @property
    def observation(self) -> str | None:
        return self._observation

    def _general_ask(self) -> str:
        if self._observation:
            return self._observation
        return (
            "I'm not quite sure what you're looking for. Would you like to "
            "work on a blog post, search your previous writing, revise "
            "something, or publish?"
        )

    def _partial_ask(self) -> str:
        if self._observation:
            return self._observation
        missing = self._metadata.get('missing_entity', 'some details')
        return f"I think I understand, but I need {missing}. Could you provide that?"

    def _specific_ask(self) -> str:
        if self._observation:
            return self._observation
        slot = self._metadata.get('missing_slot', 'a value')
        return f"I need a specific {slot} to proceed. What would you like to use?"

    def _confirmation_ask(self) -> str:
        if self._observation:
            return self._observation
        candidate = self._metadata.get('candidate', 'this')
        return f"Just to confirm — did you mean {candidate}?"
