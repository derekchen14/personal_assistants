from __future__ import annotations
from backend.modules.policies.base import BasePolicy
from backend.components.display_frame import DisplayFrame

class DraftPolicy(BasePolicy):

    def __init__(self, components:dict):
        super().__init__(components)
        self.flow_stack = components['flow_stack']

    def execute(self, state, context, tools) -> 'DisplayFrame':
        flow = self.flow_stack.get_flow()

        match flow.name():
            case 'outline': return self.outline_policy(flow, state, context, tools)
            case 'refine': return self.refine_policy(flow, state, context, tools)
            case 'cite': return self.cite_policy(flow, state, context, tools)
            case 'compose': return self.compose_policy(flow, state, context, tools)
            case 'add': return self.add_policy(flow, state, context, tools)
            case 'create': return self.create_policy(flow, state, context, tools)
            case 'brainstorm': return self.brainstorm_policy(flow, state, context, tools)
            case _: return self.build_frame()

    @staticmethod
    def _has_bullets(content:str) -> bool:
        for line in content.split('\n'):
            stripped = line.strip()
            if stripped.startswith('- ') or stripped.startswith('* ') or stripped.startswith('1. '):
                return True
        return False

    def outline_policy(self, flow, state, context, tools):
        if flow.slots['sections'].check_if_filled():
            flow.stage = 'direct'

            if flow.slots['sections'].is_verified():
                post_id, _ = self._resolve_source_ids(flow, state, tools)
                frame = self.build_frame(origin='outline')
                block_content = self._read_post_content(post_id, tools)
                frame.add_block({'type': 'card', 'data': block_content})
                flow.status = 'Completed'
            else:
                frame = self._outline_direct(flow, state, context, tools)

        elif flow.slots['topic'].check_if_filled():
            flow.stage = 'propose'

            if flow.slots['proposals'].check_if_filled():
                chosen_outline = flow.slots['proposals'].values[0]
                for section in chosen_outline:
                    flow.slots['sections'].add_one(section)
                frame = self.outline_policy(flow, state, context, tools)
            else:
                frame = self._propose_outline(flow, state, context, tools)

        else:
            convo_history = context.compile_history(look_back=3)
            text = self.engineer.call(convo_history, system="Extract the topic the user wants to outline for the blog post or note.")
            flow.fill_slots_by_label({'topic': self._parse_value(text)})

            if flow.slots['topic'].filled:
                flow.stage = 'propose'
                frame = self._propose_outline(flow, state, context, tools)
            else:
                flow.stage = 'default'
                self.ambiguity.declare('specific', metadata={'missing_slot': 'topic'})
                frame = self.build_frame()

        return frame

    def _resolve_outline_post_id(self, flow, state, tools):
        post_id, _ = self._resolve_source_ids(flow, state, tools)
        if post_id:
            return post_id
        topic = flow.slots['topic']
        if topic.filled:
            post_id = self.resolve_post_id(str(topic.to_dict()), tools)
        return post_id or state.active_post

    def _propose_outline(self, flow, state, context, tools):
        post_id = self._resolve_outline_post_id(flow, state, tools)
        raw, tool_log = self.llm_execute(flow, state, context, tools)

        # Resilience: if the LLM ignored propose-mode rules and saved directly,
        # treat it as a direct completion rather than returning an empty card.
        if any(tc.get('tool') == 'generate_outline' for tc in tool_log):
            flow.stage = 'direct'
            flow.status = 'Completed'
            frame = self.build_frame(origin='outline')
            if post_id:
                frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
            return frame

        candidates = self._parse_candidates(raw)
        flow.slots['proposals'].options = candidates
        return self.build_frame(origin='outline')

    @staticmethod
    def _parse_candidates(text:str) -> list[list[dict]]:
        """Parse LLM output into a list of candidates; each candidate is a list of section dicts."""
        import re
        if not text:
            return []
        option_parts = re.split(r'(?m)^###\s+Option\s+\d+\s*\n', text)
        candidates = []
        for option_body in option_parts[1:]:
            sections = []
            section_parts = re.split(r'(?m)^##\s+', option_body)
            for section_body in section_parts[1:]:
                lines = section_body.strip().split('\n', 1)
                name = lines[0].strip()
                description = lines[1].strip() if len(lines) > 1 else ''
                if name:
                    sections.append({'name': name, 'description': description, 'checked': False})
            if sections:
                candidates.append(sections)
        return candidates

    def _outline_respond(self, flow, state, context, tools):
        proposals = flow.slots['proposals']
        sections = flow.slots['sections']

        # Click path — proposals.values already holds the chosen candidate.
        if proposals.values:
            chosen = proposals.values[0]
            if isinstance(chosen, list):
                sections.steps = [dict(sec) for sec in chosen]
                sections.check_if_filled()
                flow.stage = 'direct'
                return self._outline_direct(flow, state, context, tools)

        # Chat fallback — user typed something like "Option 2" or gave feedback.
        import json
        user_text = context.last_user_text or ''
        candidates_md = self._render_candidates_md(proposals.options)
        system = (
            'The user was shown outline candidates and replied. '
            'Classify the reply as "select" (they picked one) or "revise" (they gave feedback). '
            'If "select", return the 1-based index of the picked option. '
            'Reply with ONLY a JSON object: {"action": "select"|"revise", "index": N}.'
        )
        prompt = f"Candidates:\n{candidates_md}\n\nUser reply: {user_text}"
        raw = self.engineer.call(prompt, system=system, max_tokens=128).strip()
        raw = raw.strip('`').removeprefix('json').strip()
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            parsed = {'action': 'revise'}

        idx = parsed.get('index')
        if parsed.get('action') == 'select' and isinstance(idx, int) and 1 <= idx <= len(proposals.options):
            chosen = proposals.options[idx - 1]
            proposals.values = [chosen]
            proposals.check_if_filled()
            sections.steps = [dict(sec) for sec in chosen]
            sections.check_if_filled()
            flow.stage = 'direct'
            return self._outline_direct(flow, state, context, tools)
        return self._outline_propose(flow, state, context, tools)

    @staticmethod
    def _render_candidates_md(candidates:list[list[dict]]) -> str:
        blocks = []
        for idx, sections in enumerate(candidates, start=1):
            lines = [f'### Option {idx}']
            for sec in sections:
                lines.append(f"## {sec.get('name', '')}")
                if sec.get('description'):
                    lines.append(sec['description'])
            blocks.append('\n'.join(lines))
        return '\n\n'.join(blocks)

    def _outline_direct(self, flow, state, context, tools):
        post_id = self._resolve_outline_post_id(flow, state, tools)
        text, tool_log = self.llm_execute(flow, state, context, tools)
        llm_saved = any(tc.get('tool') == 'generate_outline' for tc in tool_log)
        if post_id and text and not llm_saved:
            self._persist_outline(post_id, text, tools)
        sections = flow.slots['sections']
        for step in sections.steps:
            sections.mark_as_complete(step['name'])
        flow.status = 'Completed'
        frame = self.build_frame(origin='outline')
        if post_id:
            frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        return frame

    def refine_policy(self, flow, state, context, tools):
        grounding = flow.slots[flow.entity_slot]
        if not grounding.check_if_filled():
            self.ambiguity.declare('specific', metadata={'missing_slot': flow.entity_slot})
            return self.build_frame()

        # Fallback: if no outline bullets, push outline instead
        post_id, _ = self._resolve_source_ids(flow, state, tools)
        if post_id:
            result = tools('read_metadata', {'post_id': post_id, 'include_outline': True})
            if result['_success']:
                content = result.get('outline', '')
                if not self._has_bullets(content):
                    self.flow_stack.fallback('outline')
                    state.keep_going = True
                    return self.build_frame()

        text, tool_log = self.llm_execute(flow, state, context, tools)
        llm_saved = any(tc.get('tool') == 'generate_outline' for tc in tool_log)
        if post_id and text and not llm_saved:
            self._persist_outline(post_id, text, tools)
        flow.status = 'Completed'
        frame = self.build_frame(origin='refine', thoughts=text)
        if post_id:
            frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        return frame

    def cite_policy(self, flow, state, context, tools):
        source_slot = flow.slots['source']
        url_slot = flow.slots['url']
        if not source_slot.check_if_filled() and not url_slot.check_if_filled():
            self.ambiguity.declare('specific', metadata={'missing_slot': 'source_or_url'})
            return self.build_frame()

        text, tool_log = self.llm_execute(flow, state, context, tools)
        flow.status = 'Completed'
        return self.build_frame(origin='cite', thoughts=text)

    def compose_policy(self, flow, state, context, tools):
        grounding = flow.slots[flow.entity_slot]
        if not grounding.check_if_filled():
            self.ambiguity.declare('specific', metadata={'missing_slot': flow.entity_slot})
            return self.build_frame()

        # Stack-on: compose needs an outline
        post_id, _ = self._resolve_source_ids(flow, state, tools)
        if post_id:
            result = tools('read_metadata', {'post_id': post_id, 'include_outline': True})
            if result['_success']:
                content = result.get('outline', '')
                if not self._has_bullets(content):
                    self.flow_stack.push('outline')
                    state.keep_going = True
                    return self.build_frame()

        text, tool_log = self.llm_execute(flow, state, context, tools)
        if post_id and text:
            _, sec_id = self._resolve_source_ids(flow, state, tools)
            if sec_id:
                self._persist_section(post_id, sec_id, text, tools)
        flow.status = 'Completed'
        frame = self.build_frame(origin='compose', thoughts=text)
        if post_id:
            frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        return frame

    def add_policy(self, flow, state, context, tools):
        grounding = flow.slots[flow.entity_slot]
        if not grounding.check_if_filled():
            self.ambiguity.declare('specific', metadata={'missing_slot': flow.entity_slot})
            return self.build_frame()

        post_id, _ = self._resolve_source_ids(flow, state, tools)
        text, tool_log = self.llm_execute(flow, state, context, tools)
        flow.status = 'Completed'
        frame = self.build_frame(origin='add', thoughts=text)
        if post_id:
            frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        return frame

    def create_policy(self, flow, state, context, tools):
        if not flow.slots['title'].check_if_filled():
            self.ambiguity.declare('specific', metadata={'missing_slot': 'title'})
            return self.build_frame()

        slots = flow.slot_values_dict()
        title = slots['title']
        post_type = slots.get('type', 'draft')    # required-by-schema, but NLU may not have filled
        topic = slots.get('topic', '')            # optional slot — .get() is correct here

        create_params = {'title': title, 'type': post_type}
        if topic:
            create_params['topic'] = topic
        result = tools('create_post', create_params)

        if result['_success']:
            new_id = result['post_id']
            state.active_post = new_id
            flow.status = 'Completed'
            frame = self.build_frame(origin='create')
            frame.add_block({'type': 'card', 'data': {
                'post_id': new_id,
                'title': result['title'],
                'status': result['status'],
            }})
        elif result.get('_error') == 'duplicate':
            self.ambiguity.declare('confirmation', metadata={
                'reason': 'duplicate_file',
            })
            frame = self.build_frame()
            frame.add_block({'type': 'confirmation', 'data': {
                'prompt': result.get('_message', ''),
                'confirm_label': 'Override',
                'cancel_label': 'Keep Existing',
            }})
        else:
            message = result.get('_message', f'Could not create {post_type} "{title}".')
            frame = self.build_frame(thoughts=message)
        return frame

    def brainstorm_policy(self, flow, state, context, tools):
        if flow.slots['source'].check_if_filled():
            text, _ = self.llm_execute(flow, state, context, tools)
        elif flow.slots['topic'].check_if_filled():
            flow.entity_slot = 'topic'
            text, _ = self.llm_execute(flow, state, context, tools)
        else:
            convo_history = context.compile_history(look_back=3)
            text = self.engineer.call(convo_history, system="Extract the topic the user wants to brainstorm about.")
            flow.fill_slots_by_label({'topic': self._parse_value(text)})
            if not flow.slots['topic'].filled:
                self.ambiguity.declare('specific', metadata={'missing_slot': 'topic'})
                return self.build_frame()
            else:
                text, _ = self.llm_execute(flow, state, context, tools)

        flow.status = 'Completed'
        return self.build_frame(thoughts=text)
