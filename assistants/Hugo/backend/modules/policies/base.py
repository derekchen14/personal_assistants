from __future__ import annotations
from backend.components.display_frame import DisplayFrame

class BasePolicy:
    """Toolkit of reusable utility methods for per-flow policy methods.
    No lifecycle orchestration — each flow method decides what to call and when.
    """

    _STATUS_SUFFIXES = (' draft', ' post', ' note', ' published')

    def __init__(self, components: dict):
        self.engineer = components['engineer']
        self.memory = components['memory']
        self.config = components['config']
        self.ambiguity = components['ambiguity']
        self._get_tools_fn = components.get('get_tools')

    def llm_execute(self, flow, state, context, tools):
        """Agentic tool-use loop for multi-tool flows. Returns (text, tool_log)."""
        resolved = self._build_resolved_context(flow, state, tools)
        convo_history = context.compile_history()
        tool_defs = self._get_tools_fn(flow)
        return self.engineer.tool_call(
            flow, convo_history, self.memory.read_scratchpad(),
            tool_defs, tools, resolved=resolved,
        )

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

    # -- Persistence helpers ------------------------------------------------

    def _resolve_source_ids(self, flow, state, tools):
        """Extract (post_id, sec_id) from entity slot. Syncs state.active_post
        as a side-effect so downstream turns can rely on the dialogue state."""
        grounding = flow.slots[flow.entity_slot]
        if grounding.slot_type not in ('source', 'target', 'removal', 'channel') or not grounding.filled:
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
        outline_md = self.engineer.apply_guardrails(text, format='markdown', shape='outline')
        if post_id and outline_md:
            tools('generate_outline', {'post_id': post_id, 'content': outline_md})
