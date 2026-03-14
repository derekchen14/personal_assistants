from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from backend.components.display_frame import DisplayFrame

if TYPE_CHECKING:
    from backend.components.flow_stack.parents import BaseFlow


class BasePolicy:
    """Toolkit of reusable utility methods for per-flow policy methods.

    No lifecycle orchestration — each flow method decides what to call and when.
    """

    _SKILL_DIR = Path(__file__).resolve().parents[2] / 'prompts' / 'skills'
    _STATUS_SUFFIXES = (' draft', ' post', ' note', ' published')

    def __init__(self, components: dict):
        self.engineer = components['engineer']
        self.memory = components['memory']
        self.config = components['config']
        self.ambiguity = components['ambiguity']
        self._get_tools_fn = components.get('get_tools')

    # -- Execution utilities ------------------------------------------------

    def llm_execute(self, flow, state, context, tools):
        """Agentic tool-use loop for multi-tool flows.

        Returns (text, tool_log).
        """
        convo_history = context.compile_history()
        skill_prompt = self._load_skill_template(flow.name())
        messages = self.engineer.build_skill_prompt(flow, convo_history, self.memory.read_scratchpad(), skill_prompt)
        tool_defs = self._get_tools_fn(flow)
        text, tool_log = self.engineer.tool_call(messages, tool_defs, tools)
        return text, tool_log

    def build_frame(self, block_type, block_data, source=None, panel=None):
        """Create a DisplayFrame."""
        frame = DisplayFrame(self.config)
        frame.set_frame(block_type, block_data, source=source, panel=panel)
        return frame

    def build_block_data(self, flow, text, tool_log):
        """Merge tool results into a block_data dict."""
        block_data = {'flow_name': flow.name(), 'content': text}
        for entry in tool_log:
            result = entry.get('result', {})
            if result.get('status') == 'success':
                result_data = result.get('result', {})
                if isinstance(result_data, dict):
                    block_data.update(result_data)
                elif isinstance(result_data, list):
                    block_data['items'] = result_data
        return block_data

    # -- Post helpers -------------------------------------------------------

    def extract_source(self, flow, state):
        """Get post identifier from source slot or state.active_post."""
        source_slot = flow.slots.get('source')
        identifier = None
        if source_slot and source_slot.filled:
            val = source_slot.to_dict()
            identifier = val[0].get('post', '') if isinstance(val, list) and val else str(val)
        if not identifier and state:
            identifier = state.active_post
        return identifier or None

    def resolve_post_id(self, identifier, tools):
        """Resolve a title or post_id string to an actual post_id."""
        if not identifier:
            return None
        # If it looks like a UUID, use it directly
        if len(identifier) == 8 or '-' in identifier:
            result = tools('post_get', {'post_id': identifier})
            if result.get('status') == 'success':
                return identifier

        # Try with and without status suffixes
        candidates = [identifier]
        lower = identifier.lower()
        for suffix in self._STATUS_SUFFIXES:
            if lower.endswith(suffix):
                candidates.append(identifier[:len(identifier) - len(suffix)])

        for query in candidates:
            result = tools('post_search', {'query': query})
            if result.get('status') != 'success':
                continue
            items = result.get('result', [])
            for item in items:
                if item.get('title', '').lower() == query.lower():
                    return item.get('post_id')
            if items:
                return items[0].get('post_id')
        return None

    # -- Template loading ---------------------------------------------------

    def _load_skill_template(self, flow_name):
        """Load backend/prompts/skills/{flow_name}.md."""
        path = self._SKILL_DIR / f'{flow_name}.md'
        if path.exists():
            return path.read_text(encoding='utf-8')
        return None

    # -- Slot helpers -------------------------------------------------------

    def _parse_value(self, text):
        """Extract a simple value from LLM text output."""
        if not text:
            return None
        cleaned = text.strip().strip('"').strip("'")
        return cleaned if cleaned else None
