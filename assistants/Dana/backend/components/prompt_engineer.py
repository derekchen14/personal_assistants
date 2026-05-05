from __future__ import annotations

import json
import os
import re
import time
import yaml
from pathlib import Path
from types import MappingProxyType
from typing import Any

import logging

import anthropic

from backend.prompts.general import build_system, SLOT_7_REMINDER

log = logging.getLogger(__name__)
from backend.prompts.for_experts import build_intent_prompt, build_flow_prompt
from backend.prompts.for_nlu import build_slot_filling_prompt
from backend.prompts.for_pex import build_skill_system, build_skill_messages
from backend.prompts.for_res import build_naturalize_prompt, build_clarification
from backend.prompts.for_contemplate import build_contemplate_prompt

from backend.components.flow_stack import flow_classes
from schemas.ontology import FLOW_CATALOG, Intent

from backend.modules.templates import get_template as _get_template


# Single-token provider swap. Callers pass abstract tiers (`low` / `med` / `high`) while the concrete
# model is resolved against ACTIVE_FAMILY. Provider-specific keys remain for explicit overrides.
ACTIVE_FAMILY = 'claude'
FAMILY_TIERS = {
    'claude':   ('claude-haiku-4-5-20251001', 'claude-sonnet-4-6', 'claude-opus-4-7'),
    'gemini':   ('gemma-3-27b-it', 'gemini-2.5-flash', 'gemini-2.5-pro'),
    'gpt':      ('gpt-5-nano', 'gpt-5-mini', 'gpt-5.2'),
    'together': ('Qwen/Qwen2.5-7B-Instruct', 'Qwen/Qwen3-80B', 'Qwen/Qwen3-235B-Instruct'),
}

_low, _med, _high = FAMILY_TIERS[ACTIVE_FAMILY]
_TIER_MODELS = {'low': _low, 'med': _med, 'high': _high}


class PromptEngineer:

    VERSION = 'v1'
    _SKILL_DIRS = (
        Path(__file__).resolve().parents[1] / 'prompts' / 'pex' / 'skills',
        Path(__file__).resolve().parents[1] / 'prompts' / 'skills',
    )

    def __init__(self, config:MappingProxyType):
        self.config = config
        self._models = config.get('models', {})
        self._persona = config.get('persona', {})
        self._resilience = config.get('resilience', {})
        self._api_key = os.getenv('ANTHROPIC_API_KEY')
        self._client: anthropic.Anthropic | None = None
        self._gemini_client = None

    @property
    def client(self) -> anthropic.Anthropic:
        if self._client is None:
            if not self._api_key:
                raise RuntimeError(
                    'ANTHROPIC_API_KEY not set. Set it in .env or environment.'
                )
            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    @property
    def gemini_client(self):
        if self._gemini_client is None:
            api_key = os.getenv('GOOGLE_API_KEY')
            if not api_key:
                raise RuntimeError(
                    'GOOGLE_API_KEY not set. Set it in .env or environment.'
                )
            from google import genai
            self._gemini_client = genai.Client(api_key=api_key)
        return self._gemini_client

    # ── Model selection ──────────────────────────────────────────────

    def _get_model_param(self, call_site:str, key:str, default):
        overrides = self._models.get('overrides', {})
        if call_site in overrides:
            val = overrides[call_site].get(key)
            if val is not None:
                return val
        return self._models.get('default', {}).get(key, default)

    def get_model_id(self, call_site:str='default') -> str:
        if call_site in _TIER_MODELS:
            return _TIER_MODELS[call_site]
        return self._get_model_param(call_site, 'model_id', _TIER_MODELS['med'])

    @staticmethod
    def resolve_tier(tier:str) -> str:
        if tier not in _TIER_MODELS:
            raise ValueError(f'Unknown tier: {tier!r}. Expected one of {tuple(_TIER_MODELS)}')
        return _TIER_MODELS[tier]

    def _get_temperature(self, call_site:str='default') -> float:
        return self._get_model_param(call_site, 'temperature', 0.0)

    def _get_provider(self, call_site:str='default') -> str:
        return self._get_model_param(call_site, 'provider', 'anthropic')

    # ── Resilience config ────────────────────────────────────────────

    def _get_retry_config(self) -> tuple[int, float, float]:
        llm_cfg = self._resilience.get('llm_retries', {})
        max_attempts = llm_cfg.get('max_attempts', 2)
        backoff_base = llm_cfg.get('backoff_base_ms', 500) / 1000
        backoff_max = llm_cfg.get('backoff_max_ms', 10000) / 1000
        return max_attempts, backoff_base, backoff_max

    # ── Core LLM call ────────────────────────────────────────────────

    def call(
        self,
        system:str,
        messages:list[dict],
        call_site:str='default',
        tools:list[dict]|None=None,
        max_tokens:int=4096,
    ) -> anthropic.types.Message:
        max_attempts, backoff_base, backoff_max = self._get_retry_config()

        # Prompt caching: put a breakpoint at the end of the system prompt and at the end of tool
        # definitions. These are the stable prefix shared across turns within a flow.
        system_blocks = [{
            'type': 'text', 'text': system, 'cache_control': {'type': 'ephemeral'},
        }] if system else []
        kwargs: dict[str, Any] = {
            'model': self.get_model_id(call_site),
            'max_tokens': max_tokens,
            'system': system_blocks,
            'messages': messages,
        }
        temp = self._get_temperature(call_site)
        if temp > 0:
            kwargs['temperature'] = temp
        if tools:
            tool_defs = [
                {key: val for key, val in tool.items() if key in ('name', 'description', 'input_schema')}
                for tool in tools
            ]
            if tool_defs:
                tool_defs[-1] = {**tool_defs[-1], 'cache_control': {'type': 'ephemeral'}}
            kwargs['tools'] = tool_defs

        model_id = kwargs['model']
        log.info('  llm call_site=%s  model=%s', call_site, model_id)

        last_error = None
        for attempt in range(max_attempts):
            try:
                return self.client.messages.create(**kwargs)
            except (
                anthropic.RateLimitError,
                anthropic.APITimeoutError,
                anthropic.InternalServerError,
            ) as ecp:
                last_error = ecp
                if attempt < max_attempts - 1:
                    delay = min(backoff_base * (2 ** attempt), backoff_max)
                    time.sleep(delay)
            except anthropic.APIError:
                raise
        raise last_error

    def call_text(
        self,
        system:str,
        messages:list[dict],
        call_site:str='default',
        max_tokens:int=4096,
    ) -> str:
        provider = self._get_provider(call_site)
        if provider == 'google':
            return self._call_gemini(system, messages, call_site, max_tokens)
        response = self.call(system, messages, call_site, max_tokens=max_tokens)
        return ''.join(block.text for block in response.content if block.type == 'text')

    def _call_gemini(
        self,
        system:str,
        messages:list[dict],
        call_site:str='default',
        max_tokens:int=4096,
    ) -> str:
        from google import genai
        from google.genai import types

        max_attempts, backoff_base, backoff_max = self._get_retry_config()

        model_id = self.get_model_id(call_site)
        temp = self._get_temperature(call_site)
        log.info('  llm call_site=%s  model=%s (gemini)', call_site, model_id)

        gemini_contents = []
        for msg in messages:
            role = 'model' if msg['role'] == 'assistant' else 'user'
            gemini_contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=msg['content'])],
                )
            )

        config = types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
        )
        if temp > 0:
            config.temperature = temp

        last_error = None
        for attempt in range(max_attempts):
            try:
                response = self.gemini_client.models.generate_content(
                    model=model_id,
                    contents=gemini_contents,
                    config=config,
                )
                return response.text
            except Exception as ecp:
                last_error = ecp
                if attempt < max_attempts - 1:
                    delay = min(backoff_base * (2 ** attempt), backoff_max)
                    time.sleep(delay)
        raise last_error

    def call_with_tools(
        self,
        system:str,
        messages:list[dict],
        tools:list[dict],
        tool_dispatcher,
        call_site:str='skill',
        max_rounds:int=10,
        max_tokens:int=4096,
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
            for tool_use in tool_uses:
                result = tool_dispatcher(tool_use.name, tool_use.input)
                tool_log.append({
                    'tool': tool_use.name,
                    'input': tool_use.input,
                    'result': result,
                })
                tool_results.append({
                    'type': 'tool_result',
                    'tool_use_id': tool_use.id,
                    'content': json.dumps(result, default=str),
                })
            msgs.append({'role': 'user', 'content': tool_results})

        return '\n'.join(text_parts) if text_parts else '', tool_log

    # ── Guardrails ────────────────────────────────────────────────────

    @staticmethod
    def apply_guardrails(text:str) -> dict | None:
        """Strip LLM artifacts and parse JSON."""
        text = text.strip()
        if text.startswith('```'):
            lines = text.split('\n')
            lines = [line for line in lines if not line.strip().startswith('```')]
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

    # ── Prompt assembly ──────────────────────────────────────────────

    def build_system_prompt(self) -> str:
        return build_system(self._persona)

    def build_nlu_prompt(
        self, user_text:str, history_text:str,
    ) -> tuple[str, list[dict]]:
        system = (
            f'{self.build_system_prompt()}\n\n'
            'You are a precise NLU classifier. '
            'Respond with only valid JSON. No markdown fences, no explanation.'
        )

        intent_prompt = build_intent_prompt(user_text, history_text)
        messages = [{'role': 'user', 'content': intent_prompt}]
        return system, messages

    def build_flow_prompt(
        self, user_text:str, intent:str|None, history_text:str,
    ) -> tuple[str, list[dict]]:
        if intent is None:
            groups: dict[str, list[str]] = {}
            for name, cat in FLOW_CATALOG.items():
                intent = cat['intent']
                if intent == Intent.INTERNAL:
                    continue
                cls = flow_classes.get(name)
                slots_desc = _slots_desc(cls)
                line = (
                    f'- {name} (dax={cat["dax"]}): {cat.get("description", "")}'
                    + (f' [slots: {slots_desc}]' if slots_desc else '')
                )
                groups.setdefault(intent, []).append(line)
            parts = []
            for group in sorted(groups):
                parts.append(f'### {group}')
                parts.extend(groups[group])
                parts.append('')
            candidates = '\n'.join(parts)
        else:
            candidate_lines = []
            edge_flows = _get_edge_flows_for_intent(intent)
            for name, cat in FLOW_CATALOG.items():
                flow_intent = cat['intent']
                if flow_intent == intent or name in edge_flows:
                    cls = flow_classes.get(name)
                    slots_desc = _slots_desc(cls)
                    candidate_lines.append(
                        f'- {name} (dax={cat["dax"]}): {cat.get("description", "")}'
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
        self, user_text:str, flow_name:str, history_text:str,
    ) -> tuple[str, list[dict]]:
        cls = flow_classes.get(flow_name)
        slots = cls().slots if cls else {}
        slot_schema = _describe_slot_schema(slots)

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
        flow_name:str,
        flow_info:dict,
        filled_slots:dict,
        history_text:str,
        scratchpad:dict,
        skill_prompt:str|None=None,
    ) -> tuple[str, list[dict]]:
        base_system = self.build_system_prompt()

        system = build_skill_system(
            base_system, flow_name, flow_info,
            skill_prompt, filled_slots, scratchpad,
        )
        messages = build_skill_messages(flow_name, history_text)
        return system, messages

    def build_naturalize_prompt(
        self,
        raw_response:str,
        history_text:str,
        block_type:str|None=None,
    ) -> tuple[str, list[dict]]:
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
        level:str,
        metadata:dict,
        observation:str|None,
        history_text:str,
    ) -> str:
        return build_clarification(level, metadata, observation)

    def build_contemplate_prompt(
        self, user_text:str, failed_flow:str, failure_reason:str,
        candidates:list[str], history_text:str,
    ) -> tuple[str, list[dict]]:
        candidate_lines = []
        for name in candidates:
            cat = FLOW_CATALOG.get(name, {})
            candidate_lines.append(f'- {name}: {cat.get("description", "")}')
        candidates_text = '\n'.join(candidate_lines)

        system = (
            f'{self.build_system_prompt()}\n\n'
            'You are re-evaluating a failed flow detection. '
            'Respond with only valid JSON.'
        )

        prompt = build_contemplate_prompt(
            user_text, failed_flow, failure_reason,
            candidates_text, history_text,
        )
        messages = [{'role': 'user', 'content': prompt}]
        return system, messages

    # ── Template registry ────────────────────────────────────────────

    def get_template(self, flow_name:str, intent:str) -> dict:
        return _get_template(flow_name, intent)

    # ── New three-layer skill API (sibling of legacy call_with_tools) ───

    def skill_call(self, flow, convo_history:str, scratchpad:dict, skill_name:str|None=None,
                   skill_prompt:str|None=None, resolved:dict|None=None, max_tokens:int=1024,
                   user_text:str|None=None) -> str:
        """Skill execution WITHOUT tool use. Sibling of tool_call."""
        if skill_prompt is None:
            skill_prompt = self.load_skill_template(skill_name or flow.name())
        base_system = self.build_system_prompt()
        system = build_skill_system(base_system, flow, skill_prompt) if skill_prompt else base_system
        messages = list(build_skill_messages(flow, convo_history, user_text, resolved)) \
                   if 'flow' in build_skill_messages.__code__.co_varnames \
                   else build_skill_messages(flow.name() if hasattr(flow, 'name') else flow, convo_history)
        response = self.call(system, messages, call_site='med', max_tokens=max_tokens)
        return ''.join(b.text for b in response.content if b.type == 'text')

    def tool_call(self, flow, convo_history:str, scratchpad:dict, tool_defs:list[dict], tool_dispatcher,
                  skill_name:str|None=None, skill_prompt:str|None=None, resolved:dict|None=None,
                  max_tokens:int=4096, user_text:str|None=None) -> tuple[str, list[dict]]:
        """Skill execution WITH tool use. Sibling of skill_call. Caps at 8 iterations."""
        if skill_prompt is None:
            skill_prompt = self.load_skill_template(skill_name or flow.name())
        base_system = self.build_system_prompt()
        system = build_skill_system(base_system, flow, skill_prompt) if skill_prompt else base_system
        if 'flow' in build_skill_messages.__code__.co_varnames:
            msgs = list(build_skill_messages(flow, convo_history, user_text, resolved))
        else:
            msgs = build_skill_messages(flow.name() if hasattr(flow, 'name') else flow, convo_history)
        return self.call_with_tools(system, msgs, tool_defs, tool_dispatcher,
                                    call_site='med', max_rounds=8, max_tokens=max_tokens)

    # ── Skill template loading ──────────────────────────────────────────

    @classmethod
    def _resolve_skill_path(cls, flow_name:str):
        for base in cls._SKILL_DIRS:
            path = base / f'{flow_name}.md'
            if path.exists():
                return path
        return None

    @classmethod
    def load_skill_template(cls, flow_name:str) -> str | None:
        path = cls._resolve_skill_path(flow_name)
        if path is None:
            return None
        _, body = cls._split_frontmatter(path.read_text(encoding='utf-8'))
        return body

    @classmethod
    def load_skill_meta(cls, flow_name:str) -> dict:
        path = cls._resolve_skill_path(flow_name)
        if path is None:
            return {}
        meta, _ = cls._split_frontmatter(path.read_text(encoding='utf-8'))
        return meta

    @staticmethod
    def _split_frontmatter(text:str) -> tuple[dict, str]:
        if not text.startswith('---\n'):
            return {}, text
        end = text.find('\n---\n', 4)
        if end == -1:
            return {}, text
        meta = yaml.safe_load(text[4:end]) or {}
        body = text[end + 5:]
        return meta, body

    # ── Tool log inspection helpers ─────────────────────────────────────

    @staticmethod
    def extract_tool_result(tool_log:list, tool_name:str) -> dict:
        for entry in tool_log:
            if entry['tool'] != tool_name:
                continue
            if entry['result']['_success']:
                return {k: v for k, v in entry['result'].items() if not k.startswith('_')}
        return {}

    @staticmethod
    def tool_succeeded(tool_log:list, tool_name:str) -> tuple[bool, dict]:
        """Check whether a named tool was called AND every call succeeded.

        Returns (True, last_result_dict) when the tool appears at least once in the log and every
        matching entry has _success=True; returns (False, {}) otherwise."""
        calls = [tc for tc in tool_log if tc['tool'] == tool_name]
        if not calls:
            return False, {}
        if not all(tc['result']['_success'] for tc in calls):
            return False, {}
        return True, {k: v for k, v in calls[-1]['result'].items() if not k.startswith('_')}


def _slots_desc(cls) -> str:
    if not cls:
        return ''
    inst = cls()
    return ', '.join(f'{name} ({slot.priority})' for name, slot in inst.slots.items())


def _get_edge_flows_for_intent(intent:str) -> set[str]:
    edge_flows = set()
    for name, cat in FLOW_CATALOG.items():
        if cat['intent'] == intent:
            for ef in cat.get('edge_flows', []):
                edge_flows.add(ef)
    return edge_flows


def _describe_slot_schema(slots:dict) -> str:
    if not slots:
        return 'No slots defined.'
    lines = []
    for name, slot in slots.items():
        lines.append(f'- {name} ({slot.priority}): type={type(slot).__name__}')
    return '\n'.join(lines)
