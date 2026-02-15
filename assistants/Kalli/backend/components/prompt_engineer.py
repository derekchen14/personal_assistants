from __future__ import annotations

import json
import time
import os
from pathlib import Path
from types import MappingProxyType
from typing import Any

import anthropic

from backend.prompts.general import build_system, SLOT_7_REMINDER
from backend.prompts.for_experts import build_intent_prompt, build_flow_prompt
from backend.prompts.for_nlu import build_slot_filling_prompt
from backend.prompts.for_pex import build_skill_system, build_skill_messages
from backend.prompts.for_res import build_naturalize_prompt, build_clarification
from backend.prompts.for_contemplate import build_contemplate_prompt
from backend.prompts.for_metadata import describe_slot_schema
from schemas.ontology import FLOW_CATALOG, Intent

_TEMPLATE_BASE = Path(__file__).resolve().parents[2] / 'schemas' / 'templates'


class PromptEngineer:

    VERSION = 'v1'

    def __init__(self, config: MappingProxyType):
        self.config = config
        self._models = config.get('models', {})
        self._persona = config.get('persona', {})
        self._resilience = config.get('resilience', {})
        self._api_key = os.getenv('ANTHROPIC_API_KEY')
        self._client: anthropic.Anthropic | None = None
        self._template_cache: dict[str, str] = {}

    @property
    def client(self) -> anthropic.Anthropic:
        if self._client is None:
            if not self._api_key:
                raise RuntimeError(
                    'ANTHROPIC_API_KEY not set. Set it in .env or environment.'
                )
            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    # ── Model selection ──────────────────────────────────────────────

    def get_model_id(self, call_site: str = 'default') -> str:
        overrides = self._models.get('overrides', {})
        if call_site in overrides:
            mid = overrides[call_site].get('model_id')
            if mid:
                return mid
        return self._models.get('default', {}).get(
            'model_id', 'claude-sonnet-4-5-latest'
        )

    def _get_temperature(self, call_site: str = 'default') -> float:
        overrides = self._models.get('overrides', {})
        if call_site in overrides:
            t = overrides[call_site].get('temperature')
            if t is not None:
                return t
        return self._models.get('default', {}).get('temperature', 0.0)

    # ── Core LLM call ────────────────────────────────────────────────

    def call(
        self,
        system: str,
        messages: list[dict],
        call_site: str = 'default',
        tools: list[dict] | None = None,
        max_tokens: int = 4096,
    ) -> anthropic.types.Message:
        llm_cfg = self._resilience.get('llm_retries', {})
        max_attempts = llm_cfg.get('max_attempts', 2)
        backoff_base = llm_cfg.get('backoff_base_ms', 500) / 1000
        backoff_max = llm_cfg.get('backoff_max_ms', 10000) / 1000

        kwargs: dict[str, Any] = {
            'model': self.get_model_id(call_site),
            'max_tokens': max_tokens,
            'system': system,
            'messages': messages,
        }
        temp = self._get_temperature(call_site)
        if temp > 0:
            kwargs['temperature'] = temp
        if tools:
            kwargs['tools'] = tools

        last_error = None
        for attempt in range(max_attempts):
            try:
                return self.client.messages.create(**kwargs)
            except (
                anthropic.RateLimitError,
                anthropic.APITimeoutError,
                anthropic.InternalServerError,
            ) as e:
                last_error = e
                if attempt < max_attempts - 1:
                    delay = min(backoff_base * (2 ** attempt), backoff_max)
                    time.sleep(delay)
            except anthropic.APIError:
                raise
        raise last_error

    def call_with_tools(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict],
        tool_dispatcher,
        call_site: str = 'skill',
        max_rounds: int = 10,
        max_tokens: int = 4096,
    ) -> tuple[str, list[dict]]:
        msgs = list(messages)
        tool_log: list[dict] = []

        for _ in range(max_rounds):
            response = self.call(system, msgs, call_site, tools, max_tokens)

            text_parts = []
            tool_uses = []
            for block in response.content:
                if block.type == 'text':
                    text_parts.append(block.text)
                elif block.type == 'tool_use':
                    tool_uses.append(block)

            if not tool_uses:
                return '\n'.join(text_parts), tool_log

            msgs.append({'role': 'assistant', 'content': response.content})
            tool_results = []
            for tu in tool_uses:
                result = tool_dispatcher(tu.name, tu.input)
                tool_log.append({
                    'tool': tu.name,
                    'input': tu.input,
                    'result': result,
                })
                tool_results.append({
                    'type': 'tool_result',
                    'tool_use_id': tu.id,
                    'content': json.dumps(result, default=str),
                })
            msgs.append({'role': 'user', 'content': tool_results})

        return '\n'.join(text_parts) if text_parts else '', tool_log

    # ── Prompt assembly ──────────────────────────────────────────────

    def build_system_prompt(self) -> str:
        return build_system(self._persona)

    def build_nlu_prompt(
        self, user_text: str, history: list[dict],
    ) -> tuple[str, list[dict]]:
        history_text = self._format_history(history, 5)

        system = (
            f'{self.build_system_prompt()}\n\n'
            'You are a precise NLU classifier. '
            'Respond with only valid JSON. No markdown fences, no explanation.'
        )

        # Two-step: intent first, then flow
        intent_prompt = build_intent_prompt(user_text, history_text)
        messages = [{'role': 'user', 'content': intent_prompt}]
        return system, messages

    def build_flow_prompt(
        self, user_text: str, intent: str, history: list[dict],
    ) -> tuple[str, list[dict]]:
        history_text = self._format_history(history, 5)

        candidate_lines = []
        for name, flow in FLOW_CATALOG.items():
            flow_intent = flow['intent'].value if hasattr(flow['intent'], 'value') else str(flow['intent'])
            if flow_intent == intent or name in _get_edge_flows_for_intent(intent):
                slots_desc = ', '.join(
                    f'{s} ({info.get("priority", "optional")})'
                    for s, info in flow.get('slots', {}).items()
                )
                candidate_lines.append(
                    f'- {name} (dax={flow["dax"]}): {flow["description"]}'
                    + (f' [slots: {slots_desc}]' if slots_desc else '')
                )
        candidates = '\n'.join(candidate_lines)

        system = (
            f'{self.build_system_prompt()}\n\n'
            'You are a precise flow classifier. '
            'Respond with only valid JSON. No markdown fences.'
        )

        flow_prompt = build_flow_prompt(user_text, intent, history_text, candidates)
        messages = [{'role': 'user', 'content': flow_prompt}]
        return system, messages

    def build_slot_filling_prompt(
        self, user_text: str, flow_name: str, history: list[dict],
    ) -> tuple[str, list[dict]]:
        flow_info = FLOW_CATALOG.get(flow_name, {})
        slot_schema = describe_slot_schema(flow_info.get('slots', {}))
        history_text = self._format_history(history, 5)

        system = (
            f'{self.build_system_prompt()}\n\n'
            'You are a slot extraction engine. '
            'Respond with only valid JSON.'
        )

        prompt = build_slot_filling_prompt(
            user_text, flow_name, slot_schema, history_text,
        )
        messages = [{'role': 'user', 'content': prompt}]
        return system, messages

    def build_skill_prompt(
        self,
        flow_name: str,
        flow_info: dict,
        filled_slots: dict,
        history: list[dict],
        scratchpad: dict,
        skill_prompt: str | None = None,
    ) -> tuple[str, list[dict]]:
        base_system = self.build_system_prompt()
        history_text = self._format_history(history, 5)

        system = build_skill_system(
            base_system, flow_name, flow_info,
            skill_prompt, filled_slots, scratchpad,
        )
        messages = build_skill_messages(flow_name, history_text)
        return system, messages

    def build_naturalize_prompt(
        self,
        raw_response: str,
        history: list[dict],
        block_type: str | None = None,
    ) -> tuple[str, list[dict]]:
        history_text = self._format_history(history, 3)

        system = (
            f'{self.build_system_prompt()}\n\n'
            'Rewrite the given response to sound natural. '
            'Keep the same information. Do not add information. '
            'Respond with ONLY the rewritten text.'
        )

        prompt = build_naturalize_prompt(raw_response, history_text, block_type)
        messages = [{'role': 'user', 'content': prompt}]
        return system, messages

    def build_clarification_prompt(
        self,
        level: str,
        metadata: dict,
        observation: str | None,
        history: list[dict],
    ) -> str:
        return build_clarification(level, metadata, observation)

    def build_contemplate_prompt(
        self, user_text: str, failed_flow: str, failure_reason: str,
        candidates: list[str], history: list[dict],
    ) -> tuple[str, list[dict]]:
        history_text = self._format_history(history, 5)

        candidate_lines = []
        for name in candidates:
            flow = FLOW_CATALOG.get(name, {})
            candidate_lines.append(f'- {name}: {flow.get("description", "")}')
        candidates_text = '\n'.join(candidate_lines)

        system = (
            f'{self.build_system_prompt()}\n\n'
            'You are re-evaluating a failed flow prediction. '
            'Respond with only valid JSON.'
        )

        prompt = build_contemplate_prompt(
            user_text, failed_flow, failure_reason,
            candidates_text, history_text,
        )
        messages = [{'role': 'user', 'content': prompt}]
        return system, messages

    # ── Template registry ─────────────────────────────────────────────

    def get_template(self, flow_name: str, intent: str) -> dict:
        if flow_name in self._template_cache:
            raw = self._template_cache[flow_name]
        else:
            raw = self._load_template(flow_name, intent)
            self._template_cache[flow_name] = raw

        lines = raw.strip().split('\n')
        template_text = lines[0] if lines else '{message}'
        meta = {}
        for line in lines[1:]:
            if ':' in line:
                key, val = line.split(':', 1)
                key = key.strip()
                val = val.strip()
                if val.lower() in ('true', 'false'):
                    val = val.lower() == 'true'
                meta[key] = val

        return {
            'template': template_text,
            'block_hint': meta.get('block_hint'),
            'skip_naturalize': meta.get('skip_naturalize', False),
        }

    def _load_template(self, flow_name: str, intent: str) -> str:
        domain_path = _TEMPLATE_BASE / 'onboarding' / f'{flow_name}.txt'
        if domain_path.exists():
            return domain_path.read_text(encoding='utf-8')

        intent_lower = intent.lower() if isinstance(intent, str) else intent.value.lower()
        base_path = _TEMPLATE_BASE / 'base' / f'{intent_lower}.txt'
        if base_path.exists():
            return base_path.read_text(encoding='utf-8')

        return '{message}'

    # ── Helpers ───────────────────────────────────────────────────────

    def _format_history(self, history: list[dict], turns: int) -> str:
        if not history:
            return ''
        lines = []
        for turn in history[-turns:]:
            role = turn.get('speaker', 'User')
            text = turn.get('text', '')
            lines.append(f'{role}: {text}')
        return '\n'.join(lines)


def _get_edge_flows_for_intent(intent: str) -> set[str]:
    edge_flows = set()
    for name, flow in FLOW_CATALOG.items():
        flow_intent = flow['intent'].value if hasattr(flow['intent'], 'value') else str(flow['intent'])
        if flow_intent == intent:
            for ef in flow.get('edge_flows', []):
                edge_flows.add(ef)
    return edge_flows
