from __future__ import annotations
from pathlib import Path
from backend.components.display_frame import DisplayFrame

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

    def llm_execute(self, flow, state, context, tools):
        """Agentic tool-use loop for multi-tool flows.

        Returns (text, tool_log).
        """
        resolved = self._build_resolved_context(flow, state, tools)
        convo_history = context.compile_history()
        skill_prompt = self._load_skill_template(flow.name())
        messages = self.engineer.build_skill_prompt(
            flow, convo_history, self.memory.read_scratchpad(),
            skill_prompt, resolved,
        )
        tool_defs = self._get_tools_fn(flow)
        text, tool_log = self.engineer.tool_call(messages, tool_defs, tools)
        return text, tool_log

    def build_frame(self, origin:str='', thoughts:str='') -> DisplayFrame:
        frame = DisplayFrame(self.config)
        frame.origin = origin
        frame.thoughts = thoughts
        return frame

    @staticmethod
    def extract_tool_result(tool_log:list, tool_name:str) -> dict:
        """Extract the first successful result for a given tool name."""
        for entry in tool_log:
            if entry.get('tool') != tool_name:
                continue
            result = entry.get('result', {})
            if result.get('_success'):
                return {k: v for k, v in result.items() if not k.startswith('_')}
        return {}

    # -- Content readback ---------------------------------------------------

    def _read_post_content(self, post_id, tools) -> dict:
        """Read back full post content from disk for frame display."""
        if not post_id:
            return {}
        meta = tools('read_metadata', {'post_id': post_id})
        if not meta.get('_success'):
            return {}
        info = {
            'post_id': post_id,
            'title': meta.get('title', ''),
            'status': meta.get('status', ''),
        }
        parts = []
        for sec_id in meta.get('section_ids', []):
            sec = tools('read_section', {'post_id': post_id, 'sec_id': sec_id})
            if sec.get('_success'):
                title = sec.get('title', sec_id)
                body = sec.get('content', '')
                final_content = body if title == '_hidden_section_title' else f'## {title}\n{body}'
                parts.append(final_content)
        info['content'] = '\n\n'.join(parts)
        return info

    # -- Post helpers -------------------------------------------------------

    def resolve_post_id(self, identifier, tools):
        """Resolve a title or post_id string to an actual post_id."""
        if not identifier:
            return None
        # If it looks like a UUID, use it directly
        if len(identifier) == 8 or '-' in identifier:
            result = tools('read_metadata', {'post_id': identifier})
            if result.get('_success'):
                return identifier

        # Try with and without status suffixes
        candidates = [identifier]
        lower = identifier.lower()
        for suffix in self._STATUS_SUFFIXES:
            if lower.endswith(suffix):
                candidates.append(identifier[:len(identifier) - len(suffix)])

        for query in candidates:
            result = tools('find_posts', {'query': query})
            if not result.get('_success'):
                continue
            items = result.get('items', [])
            for item in items:
                if item.get('title', '').lower() == query.lower():
                    return item.get('post_id')
            if items:
                return items[0].get('post_id')
        return None

    def _load_skill_template(self, flow_name):
        """Load backend/prompts/skills/{flow_name}.md."""
        path = self._SKILL_DIR / f'{flow_name}.md'
        if path.exists():
            return path.read_text(encoding='utf-8')
        return None

    # -- Persistence helpers ------------------------------------------------

    def _resolve_source_ids(self, flow, state, tools):
        """Extract (post_id, sec_id) from entity slot. Syncs state.active_post
        as a side-effect so downstream turns can rely on the dialogue state."""
        grounding = flow.slots[flow.entity_slot]
        if grounding.slot_type == 'topic' or not grounding.filled:
            return None, None
        vals = grounding.values[0]
        post_id = self.resolve_post_id(vals['post'], tools)
        sec_id = vals.get('sec', '') or None
        if post_id:
            state.active_post = post_id
        return post_id, sec_id

    def _build_resolved_context(self, flow, state, tools) -> dict|None:
        """Pre-resolve post/section IDs so the LLM gets deterministic entities."""
        post_id, sec_id = self._resolve_source_ids(flow, state, tools)
        if not post_id and state.active_post:
            post_id = state.active_post
        if not post_id:
            return None
        meta = tools('read_metadata', {'post_id': post_id})
        if not meta.get('_success'):
            return {'post_id': post_id}
        resolved = {
            'post_id': post_id,
            'post_title': meta.get('title', ''),
            'section_ids': meta.get('section_ids', []),
        }
        if sec_id:
            resolved['target_section'] = sec_id
        return resolved

    def _persist_section(self, post_id, sec_id, text, tools):
        """Save revised text to a section on disk."""
        if post_id and sec_id and text:
            tools('revise_content', {'post_id': post_id, 'sec_id': sec_id, 'content': text})

    def _persist_outline(self, post_id, text, tools):
        """Extract ## sections from text and save as outline."""
        outline_md = self._extract_outline_markdown(text)
        if post_id and outline_md:
            tools('generate_outline', {'post_id': post_id, 'content': outline_md})

    @staticmethod
    def _extract_outline_markdown(text:str) -> str:
        """Extract ## sections from LLM output to save as outline content."""
        import re
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
        # Fallback: look for numbered sections and convert to ## headings
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

    # -- Slot helpers -------------------------------------------------------

    def _parse_value(self, text):
        """Extract a simple value from LLM text output."""
        if not text:
            return None
        cleaned = text.strip().strip('"').strip("'")
        return cleaned if cleaned else None
