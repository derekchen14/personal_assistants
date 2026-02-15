from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from types import MappingProxyType

from backend.components.dialogue_state import DialogueState
from backend.components.context_coordinator import ContextCoordinator
from backend.components.ambiguity_handler import AmbiguityHandler
from backend.components.prompt_engineer import PromptEngineer
from schemas.ontology import FLOW_CATALOG, Intent


class NLUResult:

    def __init__(self, intent: str, dax: str, flow_name: str,
                 confidence: float, slots: dict | None = None):
        self.intent = intent
        self.dax = dax
        self.flow_name = flow_name
        self.confidence = confidence
        self.slots = slots or {}

    def __repr__(self):
        return f'<NLUResult {self.intent}/{self.flow_name} conf={self.confidence:.2f}>'


_SHORTCUTS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'^(hi|hello|hey)\b', re.I), 'chat'),
    (re.compile(r'^(help|what can you do)\b', re.I), 'chat'),
    (re.compile(r'^(bye|goodbye|exit|quit)\b', re.I), 'chat'),
    (re.compile(r'\bwhat.*(next|now)\b', re.I), 'next'),
    (re.compile(r'\bstatus\b', re.I), 'check'),
]

_NUM_VOTERS = 2


class NLU:

    def __init__(self, config: MappingProxyType, dialogue_state: DialogueState,
                 context: ContextCoordinator, ambiguity: AmbiguityHandler,
                 prompt_engineer: PromptEngineer):
        self.config = config
        self.dialogue_state = dialogue_state
        self.context = context
        self.ambiguity = ambiguity
        self.prompt_engineer = prompt_engineer

    def understand(self, user_text: str, gold_dax: str | None = None) -> NLUResult:
        prep = self._prepare(user_text)
        if prep is not None:
            return prep

        if gold_dax:
            return self._resolve_gold_dax(gold_dax, user_text)

        result = self._predict(user_text)
        result = self._validate(result)

        self.dialogue_state.update(
            intent=result.intent,
            dax=result.dax,
            flow_name=result.flow_name,
            confidence=result.confidence,
            slots=result.slots,
        )

        if self.ambiguity.needs_clarification(result.confidence):
            self.ambiguity.declare(
                'general',
                metadata={'top_prediction': result.flow_name},
                observation=f'Low confidence ({result.confidence:.2f}) on '
                            f'flow "{result.flow_name}"',
            )

        return result

    # ── Pre-hook ─────────────────────────────────────────────────────

    def _prepare(self, user_text: str) -> NLUResult | None:
        text = user_text.strip()

        if not text:
            return NLUResult('Converse', '{000}', 'chat', 1.0)

        if len(text) < 2:
            return NLUResult('Converse', '{000}', 'chat', 0.8)

        for pattern, flow_name in _SHORTCUTS:
            if pattern.search(text):
                flow = FLOW_CATALOG.get(flow_name)
                if flow:
                    return NLUResult(
                        intent=flow['intent'].value,
                        dax=flow['dax'],
                        flow_name=flow_name,
                        confidence=1.0,
                    )
        return None

    # ── Prediction (parallel voting) ─────────────────────────────────

    def _predict(self, user_text: str) -> NLUResult:
        history = self.context.compile_history(turns=5)
        system, messages = self.prompt_engineer.build_flow_prompt(
            user_text, None, history,
        )

        def _call_voter() -> dict | None:
            try:
                response = self.prompt_engineer.call(
                    system=system, messages=messages,
                    call_site='nlu_vote', max_tokens=512,
                )
                text = self._extract_text(response)
                return self._parse_json(text)
            except Exception as e:
                print(f'NLU vote error: {e}')
                return None

        votes: list[dict] = []
        with ThreadPoolExecutor(max_workers=_NUM_VOTERS) as pool:
            futures = [pool.submit(_call_voter) for _ in range(_NUM_VOTERS)]
            for future in as_completed(futures):
                result = future.result()
                if result and result.get('flow_name') in FLOW_CATALOG:
                    votes.append(result)

        if not votes:
            return NLUResult('Converse', '{000}', 'chat', 0.3)

        return self._tally_votes(votes)

    def _tally_votes(self, votes: list[dict]) -> NLUResult:
        flow_counts: dict[str, list[dict]] = {}
        for v in votes:
            fn = v['flow_name']
            flow_counts.setdefault(fn, []).append(v)

        best_flow = max(flow_counts, key=lambda f: len(flow_counts[f]))
        best_votes = flow_counts[best_flow]
        agreement = len(best_votes) / len(votes)

        avg_confidence = sum(
            float(v.get('confidence', 0.5)) for v in best_votes
        ) / len(best_votes)

        if agreement == 1.0 and len(votes) >= 2:
            final_confidence = min(avg_confidence + 0.15, 1.0)
        elif agreement >= 0.5:
            final_confidence = avg_confidence
        else:
            final_confidence = avg_confidence * 0.7

        best_vote = max(best_votes, key=lambda v: float(v.get('confidence', 0)))
        slots = best_vote.get('slots', {})

        flow = FLOW_CATALOG[best_flow]
        return NLUResult(
            intent=flow['intent'].value,
            dax=flow['dax'],
            flow_name=best_flow,
            confidence=final_confidence,
            slots=slots,
        )

    # ── Gold dax resolution ──────────────────────────────────────────

    def _resolve_gold_dax(self, gold_dax: str, user_text: str) -> NLUResult:
        for flow_name, flow in FLOW_CATALOG.items():
            if flow['dax'] == gold_dax:
                return NLUResult(
                    intent=flow['intent'].value,
                    dax=gold_dax,
                    flow_name=flow_name,
                    confidence=1.0,
                )
        return NLUResult('Converse', '{000}', 'chat', 0.5)

    # ── Post-hook ────────────────────────────────────────────────────

    def _validate(self, result: NLUResult) -> NLUResult:
        flow = FLOW_CATALOG.get(result.flow_name)
        if not flow:
            return NLUResult('Converse', '{000}', 'chat', 0.3)

        catalog_intent = flow['intent'].value
        if result.intent != catalog_intent:
            result.intent = catalog_intent

        result.dax = flow['dax']

        valid_slot_names = set(flow.get('slots', {}).keys())
        result.slots = {
            k: v for k, v in result.slots.items()
            if k in valid_slot_names
        }

        return result

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _extract_text(response) -> str:
        text = ''
        for block in response.content:
            if block.type == 'text':
                text += block.text
        return text

    @staticmethod
    def _parse_json(text: str) -> dict | None:
        text = text.strip()
        if text.startswith('```'):
            lines = text.split('\n')
            lines = [l for l in lines if not l.strip().startswith('```')]
            text = '\n'.join(lines)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
        return None
