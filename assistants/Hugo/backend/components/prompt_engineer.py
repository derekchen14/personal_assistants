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
import yaml
from pydantic import BaseModel

from backend.prompts.general import build_system
from backend.prompts.for_pex import build_skill_system, build_skill_messages

log = logging.getLogger(__name__)

_TASK_SUFFIXES = {
    'classify_intent': 'You are a precise NLU classifier. Respond with only valid JSON. No markdown fences, no explanation.',
    'detect_flow': 'You are a precise flow classifier. Respond with only valid JSON. No markdown fences.',
    'fill_slots': 'You are a slot extraction engine. Respond with only valid JSON.',
    'contemplate': 'You are re-evaluating a failed flow detection. Respond with only valid JSON.',
    'repair_slot': 'Reply with ONLY the best matching valid option, or "NONE" if no match is reasonable.',
    'skill': '',
    'naturalize': 'Rewrite the given templated response to sound more natural. Keep the same information. Do not add information. Respond with ONLY the rewritten text.',
    'quality_check': (
        'You are a quality checker. Given recent conversation history, '
        'the user\'s latest request, and the agent\'s output (which may '
        'include the agent\'s spoken reply, card content, and structured '
        'data like proposed options), decide whether the response addresses '
        'what the user asked. Treat persisted action (an outline saved, a '
        'section written) as success even if the spoken reply is brief. '
        'Reply with ONLY "pass" or "fail: <one-sentence reason>".'
    ),
    'clarify': '',
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
    _SKILL_DIRS = (
        Path(__file__).resolve().parents[1] / 'prompts' / 'pex' / 'skills',
        Path(__file__).resolve().parents[1] / 'prompts' / 'skills',
    )

    _CLIENT_ENVARS = {
        'anthropic': 'ANTHROPIC_API_KEY',
        'google':    'GOOGLE_API_KEY',
        'openai':    'OPENAI_API_KEY',
        'qwen':      ('TOGETHER_API_KEY', 'QWEN_API_KEY'),
    }

    def __init__(self, config:MappingProxyType):
        self.config = config
        self._models = config.get('models', {})
        self.persona = config.get('persona', {})
        self._resilience = config.get('resilience', {})
        self._clients: dict[str, object] = {}

    def _get_client(self, provider:str):
        if provider in self._clients:
            return self._clients[provider]
        envars = self._CLIENT_ENVARS[provider]
        if isinstance(envars, str):
            envars = (envars,)
        api_key = next((os.getenv(e) for e in envars if os.getenv(e)), None)
        if not api_key:
            raise RuntimeError(f'{envars[0]} not set. Set it in .env or environment.')
        if provider == 'anthropic':
            client = anthropic.Anthropic(api_key=api_key)
        elif provider == 'google':
            from google import genai
            client = genai.Client(api_key=api_key)
        elif provider == 'openai':
            import openai
            client = openai.OpenAI(api_key=api_key)
        elif provider == 'qwen':
            import openai
            client = openai.OpenAI(api_key=api_key, base_url='https://api.together.xyz/v1')
        self._clients[provider] = client
        return client

    # ── Model resolution ─────────────────────────────────────────────

    @staticmethod
    def _resolve_model(model:str) -> str:
        if model not in _MODEL_IDS:
            raise ValueError(f'Unknown model: {model!r}')
        return _MODEL_IDS[model]

    @staticmethod
    def _model_family(model:str) -> str:
        if model in _CLAUDE_MODELS: return 'claude'
        if model in _GEMINI_MODELS: return 'gemini'
        if model in _QWEN_MODELS:   return 'qwen'
        if model in _GPT_MODELS:    return 'gpt'
        raise ValueError(f'Unknown model family for: {model!r}')

    def _get_temperature(self, task:str='skill') -> float:
        overrides = self._models.get('overrides', {})
        if task in overrides:
            val = overrides[task].get('temperature')
            if val is not None:
                return val
        return self._models.get('default', {}).get('temperature', 0.0)

    def _get_retry_config(self) -> tuple[int, float, float]:
        llm_cfg = self._resilience.get('llm_retries', {})
        max_attempts = llm_cfg.get('max_attempts', 2)
        backoff_base = llm_cfg.get('backoff_base_ms', 500) / 1000
        backoff_max = llm_cfg.get('backoff_max_ms', 10000) / 1000
        return max_attempts, backoff_base, backoff_max

    # ── Public API ────────────────────────────────────────────────────

    def _system_for_task(self, task:str) -> str:
        base = build_system(self.persona)
        suffix = _TASK_SUFFIXES.get(task, '')
        return f'{base}\n\n{suffix}'.strip() if suffix else base

    def __call__(self, prompt:str, task:str='skill',
                 model:str='sonnet', max_tokens:int=1024,
                 schema:type[BaseModel]|dict|None=None) -> str|dict|BaseModel:
        messages = [{'role': 'user', 'content': prompt}]
        system = self._system_for_task(task)
        model_id = self._resolve_model(model)
        log.info('  task=%s  model=%s', task, model_id)
        schema_dict = self._to_json_schema(schema) if schema is not None else None
        match self._model_family(model):
            case 'claude':
                response = self._call_claude(system, messages, model_id, max_tokens=max_tokens, schema_dict=schema_dict)
                text = ''.join(block.text for block in response.content if block.type == 'text')
            case 'gemini':
                text = self._call_gemini(system, messages, model_id, max_tokens, schema_dict=schema_dict)
            case 'qwen':
                text = self._call_qwen(system, messages, model_id, max_tokens, schema_dict=schema_dict)
            case 'gpt':
                text = self._call_gpt(system, messages, model_id, max_tokens, schema_dict=schema_dict)
        if schema is None:
            return text
        parsed = self.apply_guardrails(text, format='json')
        if parsed is None:
            raise ValueError(f'schema-constrained call returned unparseable JSON: {text!r}')
        if isinstance(schema, type) and issubclass(schema, BaseModel):
            return schema.model_validate(parsed)
        return parsed

    @staticmethod
    def _to_json_schema(schema:type[BaseModel]|dict) -> dict:
        if isinstance(schema, dict):
            return schema
        if isinstance(schema, type) and issubclass(schema, BaseModel):
            return schema.model_json_schema()
        raise TypeError(f'schema must be a dict or Pydantic BaseModel subclass, got {type(schema)!r}')

    def skill_call(self, flow, convo_history:str, scratchpad:dict, skill_name:str|None=None,
                   skill_prompt:str|None=None, resolved:dict|None=None, max_tokens:int=1024,
                   user_text:str|None=None) -> str:
        """Skill execution WITHOUT tool use. Sibling of tool_call."""
        if skill_prompt is None:
            skill_prompt = self.load_skill_template(skill_name or flow.name())
        base_system = build_system(self.persona)
        system = build_skill_system(base_system, flow, skill_prompt)
        messages = list(build_skill_messages(flow, convo_history, user_text, resolved))
        model_id = self._resolve_model('sonnet')
        response = self._call_claude(system, messages, model_id, max_tokens=max_tokens)
        return ''.join(block.text for block in response.content if block.type == 'text')

    def tool_call(self, flow, convo_history:str, scratchpad:dict, tool_defs:list[dict], tool_dispatcher,
                  skill_name:str|None=None, skill_prompt:str|None=None, resolved:dict|None=None,
                  max_tokens:int=4096, user_text:str|None=None) -> tuple[str, list[dict]]:
        """Skill execution WITH tool use. Sibling of skill_call."""
        if skill_prompt is None:
            skill_prompt = self.load_skill_template(skill_name or flow.name())
        base_system = build_system(self.persona)
        system = build_skill_system(base_system, flow, skill_prompt)
        msgs = list(build_skill_messages(flow, convo_history, user_text, resolved))
        model_id = self._resolve_model('sonnet')
        tool_log: list[dict] = []

        max_num_calls = 8
        # Allow certain flows that need more effort to increase the number of tool calls
        if flow.name() in ['audit', 'refine', 'rework', 'compose', 'simplify', 'add']:
            max_num_calls *= 2

        for _ in range(max_num_calls):
            response = self._call_claude(system, msgs, model_id, tools=tool_defs, max_tokens=max_tokens)

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
                log.info('  skill tool=%s  input=%s', tool_use.name,
                         {key: val for key, val in tool_use.input.items()} if tool_use.input else {})
                result = tool_dispatcher(tool_use.name, tool_use.input)
                tool_log.append({'tool': tool_use.name, 'input': tool_use.input, 'result': result})
                parsed_content = json.dumps(result, default=str) 
                tool_results.append({'type': 'tool_result', 'tool_use_id': tool_use.id, 'content': parsed_content})
            msgs.append({'role': 'user', 'content': tool_results})

        return '\n'.join(text_parts) if text_parts else '', tool_log

    async def stream(self, prompt:str, task:str='skill', model:str='sonnet', max_tokens:int=4096):
        """Token streaming. Same routing as __call__, yields text chunks."""
        messages = [{'role': 'user', 'content': prompt}]
        system = self._system_for_task(task)
        model_id = self._resolve_model(model)
        log.info('  task=%s  model=%s  stream=true', task, model_id)
        match self._model_family(model):
            case 'claude':
                with self._get_client('anthropic').messages.stream(
                    model=model_id, max_tokens=max_tokens,
                    system=system, messages=messages,
                ) as stm:
                    for text in stm.text_stream:
                        yield text
            case _:
                text = self(prompt, task=task, model=model, max_tokens=max_tokens)
                yield text

    # ── Private provider methods ──────────────────────────────────────

    def _retry(self, fn, retryable):
        max_attempts, backoff_base, backoff_max = self._get_retry_config()
        last_error = None
        for attempt in range(max_attempts):
            try:
                return fn()
            except retryable as ecp:
                last_error = ecp
                if attempt < max_attempts - 1:
                    time.sleep(min(backoff_base * (2 ** attempt), backoff_max))
        raise last_error

    def _call_claude(self, system, messages, model_id, *, tools=None, max_tokens=4096, schema_dict=None):
        # Prompt caching: put a breakpoint at the end of the system prompt and at the end of tool
        # definitions. These are the stable prefix shared across turns within a flow; per-turn
        # content in `messages` sits after the cache boundary and is not cached.
        system_blocks = [{
            'type': 'text',
            'text': system,
            'cache_control': {'type': 'ephemeral'},
        }] if system else []
        kwargs: dict[str, Any] = {
            'model': model_id, 'max_tokens': max_tokens,
            'system': system_blocks, 'messages': messages,
        }
        temp = self._get_temperature()
        if temp > 0:
            kwargs['temperature'] = temp
        if tools:
            tool_defs = [
                {key: val for key, val in tool.items() if key in ('name', 'description', 'input_schema')}
                for tool in tools
            ]
            if tool_defs:
                # Cache breakpoint on the last tool definition.
                tool_defs[-1] = {**tool_defs[-1], 'cache_control': {'type': 'ephemeral'}}
            kwargs['tools'] = tool_defs
        if schema_dict is not None:
            kwargs['output_config'] = {'format': {'type': 'json_schema', 'schema': schema_dict}}
        client = self._get_client('anthropic')
        try:
            return self._retry(lambda: client.messages.create(**kwargs),
                (anthropic.RateLimitError, anthropic.APITimeoutError, anthropic.InternalServerError))
        except anthropic.APIError:
            raise

    def _call_gemini(self, system, messages, model_id, max_tokens=4096, schema_dict=None):
        from google.genai import types
        temp = self._get_temperature()
        gemini_contents = [
            types.Content(role=('model' if msg['role'] == 'assistant' else 'user'),
                parts=[types.Part.from_text(text=msg['content'])])
            for msg in messages
        ]
        config = types.GenerateContentConfig(
            system_instruction=system, max_output_tokens=max_tokens,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )
        if temp > 0:
            config.temperature = temp
        if schema_dict is not None:
            config.response_mime_type = 'application/json'
            config.response_json_schema = schema_dict
        client = self._get_client('google')
        response = self._retry(
            lambda: client.models.generate_content(
                model=model_id, contents=gemini_contents, config=config),
            Exception,
        )
        return response.text

    def _call_gpt(self, system, messages, model_id, max_tokens=4096, schema_dict=None):
        import openai
        temp = self._get_temperature()
        oai_messages = [{'role': 'system', 'content': system}]
        oai_messages.extend({'role': msg['role'], 'content': msg['content']} for msg in messages)
        kwargs: dict[str, Any] = {
            'model': model_id, 'messages': oai_messages,
            'max_completion_tokens': max_tokens,
        }
        if temp > 0:
            kwargs['temperature'] = temp
        if schema_dict is not None:
            kwargs['response_format'] = {
                'type': 'json_schema',
                'json_schema': {'name': 'response', 'schema': schema_dict, 'strict': True},
            }
        client = self._get_client('openai')
        try:
            response = self._retry(lambda: client.chat.completions.create(**kwargs),
                (openai.RateLimitError, openai.APITimeoutError, openai.InternalServerError))
            return response.choices[0].message.content or ''
        except openai.APIError:
            raise

    def _call_qwen(self, system, messages, model_id, max_tokens=4096, schema_dict=None):
        import openai
        temp = self._get_temperature()
        is_thinking = 'thinking' in model_id.lower()
        qwen_messages = [{'role': 'system', 'content': system}]
        qwen_messages.extend({'role': msg['role'], 'content': msg['content']} for msg in messages)
        kwargs: dict[str, Any] = {
            'model': model_id, 'messages': qwen_messages,
            'max_completion_tokens': max_tokens if is_thinking else None,
        }
        if not is_thinking:
            kwargs['max_tokens'] = max_tokens
        if temp > 0 and not is_thinking:
            kwargs['temperature'] = temp
        if schema_dict is not None:
            kwargs['response_format'] = {
                'type': 'json_schema',
                'json_schema': {'name': 'response', 'schema': schema_dict, 'strict': True},
            }
        kwargs = {key: val for key, val in kwargs.items() if val is not None}
        client = self._get_client('qwen')
        try:
            response = self._retry(lambda: client.chat.completions.create(**kwargs),
                (openai.RateLimitError, openai.APITimeoutError, openai.InternalServerError))
        except openai.APIError:
            raise
        raw_text = response.choices[0].message.content or ''
        if is_thinking and '<think>' in raw_text:
            parts = raw_text.split('</think>')
            if len(parts) > 1:
                raw_text = parts[-1].strip()
            else:
                match = re.search(r'\{[^{}]*\}', raw_text)
                if match:
                    raw_text = match.group()
        return raw_text

    # ── Output parsers ───────────────────────────────────────────────

    @classmethod
    def apply_guardrails(cls, text:str, format:str='json', shape:str|None=None):
        """Strip fences, then dispatch to the right format parser. `format` is one of
        'json' | 'sql' | 'markdown'; `shape` is an optional hint passed to the format parser
        (e.g. 'outline', 'candidates')."""
        text = cls._strip_fences(text)
        match format:
            case 'json':     return cls._parse_json(text)
            case 'sql':      return cls._parse_sql(text)
            case 'markdown': return cls._parse_markdown(text, shape)

    @staticmethod
    def _strip_fences(text:str) -> str:
        text = text.strip()
        if text.startswith('```'):
            lines = [line for line in text.split('\n') if not line.strip().startswith('```')]
            text = '\n'.join(lines)
        return text

    @staticmethod
    def _parse_json(text:str) -> dict | None:
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

    @staticmethod
    def _parse_sql(text:str) -> str:
        return text.strip()

    @staticmethod
    def _parse_markdown(text:str, shape:str|None=None):
        if not text:
            return [] if shape == 'candidates' else ''
        if shape == 'candidates':
            option_parts = re.split(r'(?m)^###\s+Option\s+\d+\s*\n', text)
            candidates = []
            for option_body in option_parts[1:]:
                sections = []
                for section_body in re.split(r'(?m)^##\s+', option_body)[1:]:
                    lines = section_body.strip().split('\n', 1)
                    name = lines[0].strip()
                    description = lines[1].strip() if len(lines) > 1 else ''
                    if name:
                        sections.append({'name': name, 'description': description, 'checked': False})
                if sections:
                    candidates.append(sections)
            return candidates
        # shape='outline' or default: extract ## sections
        lines = text.split('\n')
        outline_lines = []
        in_outline = False
        for line in lines:
            if line.startswith('## '):
                in_outline = True
            if in_outline:
                outline_lines.append(line)
        if outline_lines:
            return '\n'.join(outline_lines)
        sections = []
        for line in lines:
            stripped = line.strip()
            if stripped and stripped[0].isdigit() and '**' in stripped:
                match = re.search(r'\*\*(.+?)\*\*', stripped)
                if match:
                    title = match.group(1).strip().lstrip('#').strip()
                    desc = stripped.split('**')[-1].strip(' —-–:')
                    sections.append(f'## {title}')
                    if desc:
                        sections.append(f'\n- {desc}')
                    sections.append('')
        return '\n'.join(sections) if sections else ''

    @classmethod
    def _resolve_skill_path(cls, flow_name:str) -> Path | None:
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

    @staticmethod
    def extract_tool_result(tool_log:list, tool_name:str) -> dict:
        for entry in tool_log:
            if entry.get('tool') != tool_name:
                continue
            result = entry.get('result', {})
            if result.get('_success'):
                return {k: v for k, v in result.items() if not k.startswith('_')}
        return {}

    @staticmethod
    def tool_succeeded(tool_log:list, tool_name:str) -> tuple[bool, dict]:
        """Check whether a named tool was called AND every call succeeded.

        Returns (True, last_result_dict) when the tool appears at least once in the log and every
        matching entry has _success=True; returns (False, {}) otherwise. The result dict strips
        underscore-prefixed control keys."""
        calls = [tc for tc in tool_log if tc.get('tool') == tool_name]
        if not calls:
            return False, {}
        last = calls[-1].get('result', {})
        if not all(tc.get('result', {}).get('_success') for tc in calls):
            return False, {}
        return True, {k: v for k, v in last.items() if not k.startswith('_')}

