from __future__ import annotations

import json
import os
import re
import time
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

_TEMPLATE_BASE = Path(__file__).resolve().parents[2] / 'schemas' / 'templates'

_TASK_LABELS = {
    'classify_intent': 'classify_intent',
    'detect_flow': 'detect_flow',
    'fill_slots': 'fill_slots',
    'contemplate': 'contemplate',
    'repair_slot': 'repair_slot',
    'naturalize': 'naturalize',
    'clarify': 'clarify',
    'skill': 'skill',
}

# model tier → concrete model ID
_MODEL_IDS = {
    'haiku':  'claude-haiku-4-5-20251001',
    'sonnet': 'claude-sonnet-4-6',
    'opus':   'claude-opus-4-6',
    'flash':  'gemini-3-flash-preview',
    'pro':    'gemini-3.1-pro-preview',
    'qwen':   'Qwen/Qwen3.5-397B-A17B',
    'mini':   'gpt-5-mini',
    'gpt':    'gpt-5.4',
}

_CLAUDE_MODELS = {'haiku', 'sonnet', 'opus'}
_GEMINI_MODELS = {'flash', 'pro'}
_QWEN_MODELS   = {'qwen'}
_GPT_MODELS    = {'mini', 'gpt'}


class PromptEngineer:

    VERSION = 'v1'

    def __init__(self, config: MappingProxyType):
        self.config = config
        self._models = config.get('models', {})
        self._persona = config.get('persona', {})
        self._resilience = config.get('resilience', {})
        self._api_key = os.getenv('ANTHROPIC_API_KEY')
        self._client: anthropic.Anthropic | None = None
        self._gemini_client = None
        self._openai_client = None
        self._qwen_client = None
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

    @property
    def openai_client(self):
        if self._openai_client is None:
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                raise RuntimeError(
                    'OPENAI_API_KEY not set. Set it in .env or environment.'
                )
            import openai
            self._openai_client = openai.OpenAI(api_key=api_key)
        return self._openai_client

    @property
    def qwen_client(self):
        if self._qwen_client is None:
            api_key = os.getenv('TOGETHER_API_KEY') or os.getenv('QWEN_API_KEY')
            if not api_key:
                raise RuntimeError(
                    'TOGETHER_API_KEY not set. Set it in .env or environment.'
                )
            import openai
            self._qwen_client = openai.OpenAI(
                api_key=api_key,
                base_url='https://api.together.xyz/v1',
            )
        return self._qwen_client

    # ── Model resolution ─────────────────────────────────────────────

    @staticmethod
    def _resolve_model(model: str) -> str:
        if model not in _MODEL_IDS:
            raise ValueError(f'Unknown model: {model!r}')
        return _MODEL_IDS[model]

    @staticmethod
    def _model_family(model: str) -> str:
        if model in _CLAUDE_MODELS: return 'claude'
        if model in _GEMINI_MODELS: return 'gemini'
        if model in _QWEN_MODELS:   return 'qwen'
        if model in _GPT_MODELS:    return 'gpt'
        raise ValueError(f'Unknown model family for: {model!r}')

    def _get_temperature(self, task: str = 'skill') -> float:
        overrides = self._models.get('overrides', {})
        if task in overrides:
            val = overrides[task].get('temperature')
            if val is not None:
                return val
        return self._models.get('default', {}).get('temperature', 0.0)

    # ── Resilience config ────────────────────────────────────────────

    def _get_retry_config(self) -> tuple[int, float, float]:
        llm_cfg = self._resilience.get('llm_retries', {})
        max_attempts = llm_cfg.get('max_attempts', 2)
        backoff_base = llm_cfg.get('backoff_base_ms', 500) / 1000
        backoff_max = llm_cfg.get('backoff_max_ms', 10000) / 1000
        return max_attempts, backoff_base, backoff_max

    # ── Public API ────────────────────────────────────────────────────

    def call(
        self,
        messages: str | list[dict],
        *,
        system: str | None = None,
        task: str = 'skill',
        model: str = 'sonnet',
        max_tokens: int = 1024,
    ) -> str:
        """Universal text-return LLM call. Routes to the right provider."""
        if isinstance(messages, str):
            messages = [{'role': 'user', 'content': messages}]
        if system is None and messages and messages[0].get('role') == 'system':
            system = messages[0]['content']
            messages = messages[1:]
        if system is None:
            system = self.build_system_prompt()
        model_id = self._resolve_model(model)
        log.info('  task=%s  model=%s', _TASK_LABELS.get(task, task), model_id)
        match self._model_family(model):
            case 'claude':
                response = self._call_claude(system, messages, model_id, max_tokens=max_tokens)
                return ''.join(b.text for b in response.content if b.type == 'text')
            case 'gemini':
                return self._call_gemini(system, messages, model_id, max_tokens)
            case 'qwen':
                return self._call_qwen(system, messages, model_id, max_tokens)
            case 'gpt':
                return self._call_gpt(system, messages, model_id, max_tokens)

    def tool_call(
        self,
        messages: list[dict],
        tools: list[dict],
        tool_dispatcher,
        *,
        system: str | None = None,
        max_tokens: int = 4096,
    ) -> tuple[str, list[dict]]:
        """Agentic tool-use loop. Claude only (depends on Anthropic tool_use blocks)."""
        if system is None and messages and messages[0].get('role') == 'system':
            system = messages[0]['content']
            messages = messages[1:]
        if system is None:
            system = self.build_system_prompt()
        model_id = self._resolve_model('sonnet')
        msgs = list(messages)
        tool_log: list[dict] = []

        for _ in range(10):
            response = self._call_claude(system, msgs, model_id, tools=tools, max_tokens=max_tokens)

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
                log.info('  skill tool=%s  input=%s', tu.name,
                         {k: v for k, v in tu.input.items()} if tu.input else {})
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

    async def stream(
        self,
        messages: list[dict],
        *,
        system: str | None = None,
        task: str = 'skill',
        model: str = 'sonnet',
        max_tokens: int = 4096,
    ):
        """Token streaming. Same routing as call(), yields text chunks."""
        if system is None:
            system = self.build_system_prompt()
        model_id = self._resolve_model(model)
        log.info('  task=%s  model=%s  stream=true', _TASK_LABELS.get(task, task), model_id)
        match self._model_family(model):
            case 'claude':
                with self.client.messages.stream(
                    model=model_id, max_tokens=max_tokens,
                    system=system, messages=messages,
                ) as s:
                    for text in s.text_stream:
                        yield text
            case _:
                # Fallback: non-streaming call, yield full text as single chunk
                text = self.call(
                    messages, system=system, task=task,
                    model=model, max_tokens=max_tokens,
                )
                yield text

    # ── Private provider methods ──────────────────────────────────────

    def _call_claude(
        self,
        system: str,
        messages: list[dict],
        model_id: str,
        *,
        tools: list[dict] | None = None,
        max_tokens: int = 4096,
    ) -> anthropic.types.Message:
        max_attempts, backoff_base, backoff_max = self._get_retry_config()

        kwargs: dict[str, Any] = {
            'model': model_id,
            'max_tokens': max_tokens,
            'system': system,
            'messages': messages,
        }
        temp = self._get_temperature()
        if temp > 0:
            kwargs['temperature'] = temp
        if tools:
            kwargs['tools'] = [
                {k: v for k, v in t.items() if k in ('name', 'description', 'input_schema')}
                for t in tools
            ]

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

    def _call_gemini(
        self,
        system: str,
        messages: list[dict],
        model_id: str,
        max_tokens: int = 4096,
    ) -> str:
        from google import genai
        from google.genai import types

        max_attempts, backoff_base, backoff_max = self._get_retry_config()
        temp = self._get_temperature()

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
            except Exception as e:
                last_error = e
                if attempt < max_attempts - 1:
                    delay = min(backoff_base * (2 ** attempt), backoff_max)
                    time.sleep(delay)
        raise last_error

    def _call_gpt(
        self,
        system: str,
        messages: list[dict],
        model_id: str,
        max_tokens: int = 4096,
    ) -> str:
        """Call OpenAI GPT models."""
        import openai

        max_attempts, backoff_base, backoff_max = self._get_retry_config()
        temp = self._get_temperature()

        oai_messages = [{'role': 'system', 'content': system}]
        for msg in messages:
            oai_messages.append({'role': msg['role'], 'content': msg['content']})

        kwargs: dict[str, Any] = {
            'model': model_id,
            'messages': oai_messages,
            'max_completion_tokens': max_tokens,
        }
        if temp > 0:
            kwargs['temperature'] = temp

        last_error = None
        for attempt in range(max_attempts):
            try:
                response = self.openai_client.chat.completions.create(**kwargs)
                return response.choices[0].message.content or ''
            except (
                openai.RateLimitError,
                openai.APITimeoutError,
                openai.InternalServerError,
            ) as e:
                last_error = e
                if attempt < max_attempts - 1:
                    delay = min(backoff_base * (2 ** attempt), backoff_max)
                    time.sleep(delay)
            except openai.APIError:
                raise
        raise last_error

    def _call_qwen(
        self,
        system: str,
        messages: list[dict],
        model_id: str,
        max_tokens: int = 4096,
    ) -> str:
        """Call Qwen models via Together.AI's OpenAI-compatible endpoint."""
        import openai

        max_attempts, backoff_base, backoff_max = self._get_retry_config()
        temp = self._get_temperature()
        is_thinking = 'thinking' in model_id.lower()

        qwen_messages = [{'role': 'system', 'content': system}]
        for msg in messages:
            qwen_messages.append({'role': msg['role'], 'content': msg['content']})

        kwargs: dict[str, Any] = {
            'model': model_id,
            'messages': qwen_messages,
            'max_completion_tokens': max_tokens if is_thinking else None,
        }
        if not is_thinking:
            kwargs['max_tokens'] = max_tokens
        # Thinking models don't support temperature
        if temp > 0 and not is_thinking:
            kwargs['temperature'] = temp
        # Remove None values
        kwargs = {k: v for k, v in kwargs.items() if v is not None}

        last_error = None
        for attempt in range(max_attempts):
            try:
                response = self.qwen_client.chat.completions.create(**kwargs)
                raw_text = response.choices[0].message.content or ''

                # Thinking models wrap output in <think>...</think> tags
                if is_thinking and '<think>' in raw_text:
                    parts = raw_text.split('</think>')
                    if len(parts) > 1:
                        raw_text = parts[-1].strip()
                    else:
                        match = re.search(r'\{[^{}]*\}', raw_text)
                        if match:
                            raw_text = match.group()

                return raw_text
            except (
                openai.RateLimitError,
                openai.APITimeoutError,
                openai.InternalServerError,
            ) as e:
                last_error = e
                if attempt < max_attempts - 1:
                    delay = min(backoff_base * (2 ** attempt), backoff_max)
                    time.sleep(delay)
            except openai.APIError:
                raise
        raise last_error

    # ── Guardrails ────────────────────────────────────────────────────

    @staticmethod
    def apply_guardrails(text: str) -> dict | None:
        """Strip LLM artifacts and parse JSON."""
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

    # ── Prompt assembly ──────────────────────────────────────────────

    def build_system_prompt(self) -> str:
        return build_system(self._persona)

    def build_nlu_prompt(
        self, user_text: str, convo_history: str,
    ) -> tuple[str, list[dict]]:
        system = (
            f'{self.build_system_prompt()}\n\n'
            'You are a precise NLU classifier. '
            'Respond with only valid JSON. No markdown fences, no explanation.'
        )

        intent_prompt = build_intent_prompt(user_text, convo_history)
        messages = [{'role': 'user', 'content': intent_prompt}]
        return system, messages

    def build_flow_prompt(
        self, user_text: str, intent: str | None, convo_history: str,
    ) -> tuple[str, list[dict]]:
        if intent is None:
            groups: dict[str, list[str]] = {}
            for name, cat in FLOW_CATALOG.items():
                fi = cat['intent']
                if fi == Intent.INTERNAL:
                    continue
                cls = flow_classes.get(name)
                slots_desc = _slots_desc(cls)
                line = (
                    f'- {name} (dax={cat["dax"]}): {cat.get("description", "")}'
                    + (f' [slots: {slots_desc}]' if slots_desc else '')
                )
                groups.setdefault(fi, []).append(line)
            parts = []
            for gi in sorted(groups):
                parts.append(f'### {gi}')
                parts.extend(groups[gi])
                parts.append('')
            candidates = '\n'.join(parts)
        else:
            candidate_lines = []
            edge_flows = _get_edge_flows_for_intent(intent)
            for name, cat in FLOW_CATALOG.items():
                fi = cat['intent']
                if fi == intent or name in edge_flows:
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

        flow_prompt = build_flow_prompt(user_text, intent, convo_history, candidates)
        messages = [{'role': 'user', 'content': flow_prompt}]
        return system, messages

    def build_slot_fill_prompt(self, flow, convo_history:str) -> tuple[str, list[dict]]:
        slot_schema = _describe_slot_schema(flow.slots)
        system = (f'{self.build_system_prompt()}\n\n'
            'You are a slot extraction engine. Respond with only valid JSON.'
        )

        prompt = build_slot_filling_prompt(flow.name(), slot_schema, convo_history)
        messages = [{'role': 'user', 'content': prompt}]
        return system, messages

    def build_skill_prompt(
        self,
        flow,
        convo_history: str,
        scratchpad: dict,
        skill_prompt: str | None = None,
    ) -> list[dict]:
        base_system = self.build_system_prompt()
        system = build_skill_system(base_system, flow, skill_prompt, scratchpad)
        messages = [{'role': 'system', 'content': system}]
        messages.extend(build_skill_messages(flow.name(), convo_history))
        return messages

    def build_naturalize_prompt(
        self,
        raw_response: str,
        convo_history: str,
        block_type: str | None = None,
    ) -> tuple[str, list[dict]]:
        system = (
            f'{self.build_system_prompt()}\n\n'
            'Rewrite the given response to sound natural. '
            'Keep the same information. Do not add information. '
            'Respond with ONLY the rewritten text.'
        )

        prompt = build_naturalize_prompt(raw_response, convo_history, block_type)
        messages = [{'role': 'user', 'content': prompt}]
        return system, messages

    def build_clarification_prompt(
        self, level: str, metadata: dict, observation: str | None,
    ) -> str:
        return build_clarification(level, metadata, observation)

    def build_contemplate_prompt(
        self, user_text: str, failed_flow: str, failure_reason: str,
        candidates: list[str], convo_history: str,
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
            candidates_text, convo_history,
        )
        messages = [{'role': 'user', 'content': prompt}]
        return system, messages

    # ── Template registry ────────────────────────────────────────────

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
        domain_path = _TEMPLATE_BASE / 'blogger' / f'{flow_name}.txt'
        if domain_path.exists():
            return domain_path.read_text(encoding='utf-8')

        intent_lower = intent.lower()
        base_path = _TEMPLATE_BASE / 'base' / f'{intent_lower}.txt'
        if base_path.exists():
            return base_path.read_text(encoding='utf-8')

        return '{message}'


def _slots_desc(cls) -> str:
    if not cls:
        return ''
    inst = cls()
    return ', '.join(f'{s} ({slot.priority})' for s, slot in inst.slots.items())


def _get_edge_flows_for_intent(intent: str) -> set[str]:
    edge_flows = set()
    for name, cat in FLOW_CATALOG.items():
        if cat['intent'] == intent:
            for ef in cat.get('edge_flows', []):
                edge_flows.add(ef)
    return edge_flows


def _describe_slot_schema(slots: dict) -> str:
    if not slots:
        return 'No slots defined.'
    lines = []
    for name, slot in slots.items():
        desc = f'- {name} ({slot.priority}): type={type(slot).__name__}'
        if hasattr(slot, 'options') and slot.options:
            desc += f', options={slot.options}'
        if hasattr(slot, 'purpose') and slot.purpose:
            desc += f', purpose="{slot.purpose}"'
        lines.append(desc)
    return '\n'.join(lines)
