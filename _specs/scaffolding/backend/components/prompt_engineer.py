import json
import os
import time
import logging
from types import MappingProxyType

import anthropic

# Domain-specific: import from backend.prompts
# from backend.prompts.general import build_system
# from backend.prompts.for_experts import build_intent_prompt, build_flow_prompt
# from backend.prompts.for_nlu import build_slot_filling_prompt
# from backend.prompts.for_pex import build_skill_system, build_skill_messages
# from backend.prompts.for_res import build_naturalize_prompt, build_clarification
# from backend.prompts.for_contemplate import build_contemplate_prompt

from schemas.ontology import FLOW_ONTOLOGY, Intent
from backend.modules.templates import get_template as _get_template

log = logging.getLogger(__name__)

# Provider-agnostic dispatch. Swap families with a single token. Per-family
# tiers map the abstract `low | med | high` levels to concrete model IDs.
ACTIVE_FAMILY = 'claude'
FAMILY_TIERS = {
    'claude':   ('claude-haiku-4-5-20251001', 'claude-sonnet-4-6', 'claude-opus-4-7'),
    'gemini':   ('gemma-3-27b-it',           'gemini-2.5-flash',  'gemini-2.5-pro'),
    'gpt':      ('gpt-5-nano',               'gpt-5-mini',        'gpt-5.2'),
    'together': ('Qwen/Qwen2.5-7B-Instruct', 'Qwen/Qwen3-80B',    'Qwen/Qwen3-235B-Instruct'),
}
_TIERS = ('low', 'med', 'high')


class PromptEngineer:
    """Provider-agnostic prompt interface. Owns model dispatch (via
    ACTIVE_FAMILY + FAMILY_TIERS), prompt caching, retry/backoff, and
    structured-output parsing. Exposes `skill_call` (no tools) and
    `tool_call` (agentic loop) as siblings."""

    VERSION = 'v1'

    def __init__(self, config:MappingProxyType):
        self.config = config
        self._persona = config.get('persona', {})
        self._resilience = config.get('resilience', {})
        self._api_key = os.getenv('ANTHROPIC_API_KEY')
        self._client:anthropic.Anthropic|None = None

    @property
    def client(self) -> anthropic.Anthropic:
        if self._client is None:
            if not self._api_key:
                raise RuntimeError('ANTHROPIC_API_KEY not set. Set it in .env or environment.')
            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    # ── Model selection (tier → family → concrete ID) ───────────────

    def resolve_model(self, tier:str='med') -> str:
        """Map an abstract tier (`low | med | high`) to a concrete model ID
        through the active family. Call sites never reference IDs directly."""
        if tier not in _TIERS:
            raise ValueError(f"Unknown tier: {tier!r}. Must be one of {_TIERS}.")
        return FAMILY_TIERS[ACTIVE_FAMILY][_TIERS.index(tier)]

    # ── Core LLM call ────────────────────────────────────────────────

    def call(self, system:str, messages:list[dict], tier:str='med',
             tools:list[dict]|None=None, max_tokens:int=4096):
        """Provider-aware single-shot call. Stable system prompt + tools tail
        get a 1-hour ephemeral cache marker so prompt caching kicks in."""
        llm_cfg = self._resilience.get('llm_retries', {})
        max_attempts = llm_cfg.get('max_attempts', 2)
        backoff_base = llm_cfg.get('backoff_base_ms', 500) / 1000
        backoff_max = llm_cfg.get('backoff_max_ms', 10000) / 1000

        kwargs:dict = {
            'model': self.resolve_model(tier),
            'max_tokens': max_tokens,
            'system': [{'type': 'text', 'text': system, 'cache_control': {'type': 'ephemeral'}}],
            'messages': messages,
        }
        if tools:
            tail = {**tools[-1], 'cache_control': {'type': 'ephemeral'}}
            kwargs['tools'] = [*tools[:-1], tail]

        log.info('  llm tier=%s  family=%s  model=%s', tier, ACTIVE_FAMILY, kwargs['model'])
        last_error = None
        for attempt in range(max_attempts):
            try:
                return self.client.messages.create(**kwargs)
            except (anthropic.RateLimitError, anthropic.APITimeoutError, anthropic.InternalServerError) as ecp:
                last_error = ecp
                if attempt < max_attempts - 1:
                    delay = min(backoff_base * (2 ** attempt), backoff_max)
                    time.sleep(delay)
            except anthropic.APIError:
                raise
        raise last_error

    def __call__(self, prompt:str, task:str='default', tier:str='med', max_tokens:int=2048) -> str:
        """One-shot convenience: `engineer(prompt, task=...)` returns the text
        from a single call at the requested tier."""
        system = self.build_system_prompt()
        messages = [{'role': 'user', 'content': prompt}]
        response = self.call(system, messages, tier=tier, max_tokens=max_tokens)
        return ''.join(b.text for b in response.content if b.type == 'text')

    # ── Skill entry points: skill_call vs tool_call ─────────────────

    def skill_call(self, flow, convo_history:str, scratchpad:dict, skill_name:str|None=None,
                   skill_prompt:str|None=None, resolved:dict|None=None, max_tokens:int=2048) -> str:
        """Skill execution WITHOUT tools — single-shot LLM call. Returns text.
        Sibling of tool_call; both load the per-flow skill body and starter."""
        system, messages = self.build_skill_prompt(flow.name(), getattr(flow, '__dict__', {}),
                                                   resolved or {}, [], scratchpad, skill_prompt)
        response = self.call(system, messages, tier='med', max_tokens=max_tokens)
        return ''.join(b.text for b in response.content if b.type == 'text')

    def tool_call(self, flow, convo_history:str, scratchpad:dict, tool_defs:list[dict],
                  tool_dispatcher, skill_name:str|None=None, skill_prompt:str|None=None,
                  resolved:dict|None=None, max_tokens:int=4096, max_rounds:int=8) -> tuple[str, list[dict]]:
        """Skill execution WITH tools — agentic loop, 8-iteration cap by default.
        Returns (text, tool_log). Policies read tool_log via tool_succeeded /
        extract_tool_result, never walk it directly."""
        system, messages = self.build_skill_prompt(flow.name(), getattr(flow, '__dict__', {}),
                                                   resolved or {}, [], scratchpad, skill_prompt)
        msgs = list(messages)
        tool_log:list[dict] = []
        text_parts:list[str] = []

        for _ in range(max_rounds):
            response = self.call(system, msgs, tier='med', tools=tool_defs, max_tokens=max_tokens)

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
                tool_log.append({'tool': tu.name, 'input': tu.input, 'result': result})
                tool_results.append({'type': 'tool_result', 'tool_use_id': tu.id,
                                     'content': json.dumps(result, default=str)})
            msgs.append({'role': 'user', 'content': tool_results})

        return '\n'.join(text_parts) if text_parts else '', tool_log

    # ── Tool-log readers (canonical interface for policies) ─────────

    def tool_succeeded(self, tool_log:list[dict], tool_name:str) -> tuple[bool, dict|None]:
        """Returns (success, last_result) for the named tool. Policies use
        this instead of walking tool_log directly."""
        for entry in reversed(tool_log):
            if entry['tool'] == tool_name:
                result = entry.get('result', {})
                return bool(result.get('_success')), result
        return False, None

    def extract_tool_result(self, tool_log:list[dict], tool_name:str) -> dict|None:
        for entry in reversed(tool_log):
            if entry['tool'] == tool_name:
                return entry.get('result')
        return None

    # ── Prompt assembly ──────────────────────────────────────────────

    def build_system_prompt(self) -> str:
        # Domain-specific: import from backend.prompts
        name = self._persona.get('name', 'Assistant')
        tone = self._persona.get('tone', 'friendly and helpful')
        return f'You are {name}, a {tone} assistant.'

    def build_nlu_prompt(
        self, user_text: str, history: list[dict],
    ) -> tuple[str, list[dict]]:
        history_text = self._format_history(history, 5)

        system = (
            f'{self.build_system_prompt()}\n\n'
            'You are a precise NLU classifier. '
            'Respond with only valid JSON. No markdown fences, no explanation.'
        )

        # Domain-specific: import from backend.prompts
        intent_prompt = (
            f'Classify the intent of this user message.\n\n'
            f'History:\n{history_text}\n\n'
            f'User: {user_text}\n\n'
            f'Respond with JSON: {{"intent": "<intent_name>"}}'
        )
        messages = [{'role': 'user', 'content': intent_prompt}]
        return system, messages

    def build_flow_prompt(
        self, user_text: str, intent: str | None, history: list[dict],
    ) -> tuple[str, list[dict]]:
        history_text = self._format_history(history, 5)

        if intent is None:
            groups: dict[str, list[str]] = {}
            for name, flow in FLOW_ONTOLOGY.items():
                fi = flow['intent']
                if fi == Intent.INTERNAL:
                    continue
                fi_val = fi.value if hasattr(fi, 'value') else str(fi)
                slots_desc = ', '.join(
                    f'{s} ({info.get("priority", "optional")})'
                    for s, info in flow.get('slots', {}).items()
                )
                line = (
                    f'- {name} (dax={flow["dax"]}): {flow["description"]}'
                    + (f' [slots: {slots_desc}]' if slots_desc else '')
                )
                groups.setdefault(fi_val, []).append(line)
            parts = []
            for gi in sorted(groups):
                parts.append(f'### {gi}')
                parts.extend(groups[gi])
                parts.append('')
            candidates = '\n'.join(parts)
        else:
            candidate_lines = []
            for name, flow in FLOW_ONTOLOGY.items():
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

        # Domain-specific: import from backend.prompts
        flow_prompt = (
            f'Select the best flow for this user message.\n\n'
            f'Intent: {intent or "unknown"}\n\n'
            f'Available flows:\n{candidates}\n\n'
            f'History:\n{history_text}\n\n'
            f'User: {user_text}\n\n'
            f'Respond with JSON: {{"flow_name": "<name>", "confidence": <0-1>, "slots": {{}}}}'
        )
        messages = [{'role': 'user', 'content': flow_prompt}]
        return system, messages

    def build_slot_filling_prompt(
        self, user_text: str, flow_name: str, history: list[dict],
    ) -> tuple[str, list[dict]]:
        flow_info = FLOW_ONTOLOGY.get(flow_name, {})
        slot_schema = _describe_slot_schema(flow_info.get('slots', {}))
        history_text = self._format_history(history, 5)

        system = (
            f'{self.build_system_prompt()}\n\n'
            'You are a slot extraction engine. '
            'Respond with only valid JSON.'
        )

        # Domain-specific: import from backend.prompts
        prompt = (
            f'Extract slot values from the user message for flow "{flow_name}".\n\n'
            f'Slot schema:\n{slot_schema}\n\n'
            f'History:\n{history_text}\n\n'
            f'User: {user_text}\n\n'
            f'Respond with JSON: {{"slots": {{}}}}'
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

        # Domain-specific: import from backend.prompts
        skill_section = f'\n\nSkill instructions:\n{skill_prompt}' if skill_prompt else ''
        slots_str = json.dumps(filled_slots, default=str) if filled_slots else '{}'
        scratch_str = json.dumps(dict(scratchpad), default=str)[:500] if scratchpad else '{}'

        system = (
            f'{base_system}\n\n'
            f'You are executing the "{flow_name}" flow.\n'
            f'Description: {flow_info.get("description", "")}\n'
            f'Filled slots: {slots_str}\n'
            f'Scratchpad: {scratch_str}'
            f'{skill_section}'
        )
        messages = [{'role': 'user', 'content': f'Execute the {flow_name} flow based on history:\n{history_text}'}]
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

        # Domain-specific: import from backend.prompts
        prompt = (
            f'Rewrite this response naturally:\n\n'
            f'{raw_response}\n\n'
            f'Context:\n{history_text}'
        )
        if block_type:
            prompt += f'\n\nBlock type: {block_type}'
        messages = [{'role': 'user', 'content': prompt}]
        return system, messages

    def build_clarification_prompt(
        self,
        level: str,
        metadata: dict,
        observation: str | None,
        history: list[dict],
    ) -> str:
        # Domain-specific: import from backend.prompts
        if observation:
            return observation
        return f'Please clarify (level={level}): {json.dumps(metadata)}'

    def build_contemplate_prompt(
        self, user_text: str, failed_flow: str, failure_reason: str,
        candidates: list[str], history: list[dict],
    ) -> tuple[str, list[dict]]:
        history_text = self._format_history(history, 5)

        candidate_lines = []
        for name in candidates:
            flow = FLOW_ONTOLOGY.get(name, {})
            candidate_lines.append(f'- {name}: {flow.get("description", "")}')
        candidates_text = '\n'.join(candidate_lines)

        system = (
            f'{self.build_system_prompt()}\n\n'
            'You are re-evaluating a failed flow detection. '
            'Respond with only valid JSON.'
        )

        # Domain-specific: import from backend.prompts
        prompt = (
            f'The flow "{failed_flow}" failed because: {failure_reason}\n\n'
            f'Alternative flows:\n{candidates_text}\n\n'
            f'History:\n{history_text}\n\n'
            f'User: {user_text}\n\n'
            f'Respond with JSON: {{"flow_name": "<name>", "confidence": <0-1>, "slots": {{}}}}'
        )
        messages = [{'role': 'user', 'content': prompt}]
        return system, messages

    # ── Template registry ────────────────────────────────────────────

    def get_template(self, flow_name:str, intent:str) -> dict:
        return _get_template(flow_name, intent)

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
    for name, flow in FLOW_ONTOLOGY.items():
        flow_intent = flow['intent'].value if hasattr(flow['intent'], 'value') else str(flow['intent'])
        if flow_intent == intent:
            for ef in flow.get('edge_flows', []):
                edge_flows.add(ef)
    return edge_flows


def _describe_slot_schema(slots: dict) -> str:
    if not slots:
        return 'No slots defined.'
    lines = []
    for name, info in slots.items():
        priority = info.get('priority', 'optional')
        slot_type = info.get('type', 'BaseSlot')
        lines.append(f'- {name} ({priority}): type={slot_type}')
    return '\n'.join(lines)
