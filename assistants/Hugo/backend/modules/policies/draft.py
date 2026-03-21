from __future__ import annotations
from backend.modules.policies.base import BasePolicy
from backend.components.display_frame import DisplayFrame

class DraftPolicy(BasePolicy):

    def __init__(self, components:dict):
        super().__init__(components)
        self.flow_stack = components['flow_stack']

    def execute(self, state, context, tools) -> 'DisplayFrame':
        flow = self.flow_stack.get_active_flow()

        match flow.name():
            case 'outline': return self.outline_policy(flow, state, context, tools)
            case 'refine': return self.refine_policy(flow, state, context, tools)
            case 'cite': return self.cite_policy(flow, state, context, tools)
            case 'compose': return self.compose_policy(flow, state, context, tools)
            case 'add': return self.add_policy(flow, state, context, tools)
            case 'create': return self.create_policy(flow, state, context, tools)
            case 'brainstorm': return self.brainstorm_policy(flow, state, context, tools)
            case _: return self.build_frame('default')

    @staticmethod
    def _has_bullets(content:str) -> bool:
        for line in content.split('\n'):
            stripped = line.strip()
            if stripped.startswith('- ') or stripped.startswith('* ') or stripped.startswith('1. '):
                return True
        return False

    def outline_policy(self, flow, state, context, tools):
        sections = flow.slots.get('sections')
        topic = flow.slots.get('topic')

        # 1. Already verified — re-entry edge case
        if sections and sections.is_verified():
            post_id, _ = self._resolve_source_ids(flow, state, tools)
            frame = self.build_frame('card', origin='outline')
            if post_id:
                frame.data = self._read_post_content(post_id, tools)
            flow.status = 'Completed'
            return frame

        # 2. Sections filled — direct path
        if sections and sections.filled:
            flow.stage = 'default'
            return self._outline_direct(flow, state, context, tools)

        # 3. Already iterating — respond to user feedback
        if flow.stage == 'iterate':
            return self._outline_respond(flow, state, context, tools)

        # 4. Topic filled — start proposing candidates
        if topic and topic.filled:
            flow.stage = 'iterate'
            return self._outline_propose(flow, state, context, tools)

        # 5. Extract topic or declare ambiguity
        convo_history = context.compile_history(look_back=3)
        text = self.engineer.call(convo_history, system="Extract the topic the user wants to outline for the blog post or note.")
        flow.fill_slots_by_label({'topic': self._parse_value(text)})
        if flow.slots['topic'].filled:
            flow.stage = 'iterate'
            return self._outline_propose(flow, state, context, tools)
        self.ambiguity.declare('specific', metadata={'missing_slot': 'topic'})
        frame = self.build_frame('default')
        frame.data = {'content': self.ambiguity.ask()}
        return frame

    def _outline_propose(self, flow, state, context, tools):
        post_id, _ = self._resolve_source_ids(flow, state, tools)
        if not post_id:
            topic = flow.slots.get('topic')
            if topic and topic.filled:
                post_id = self.resolve_post_id(str(topic.to_dict()), tools)
        text, tool_log = self.llm_execute(flow, state, context, tools)
        self.memory.write_scratchpad('outline:candidates', text)
        frame = self.build_frame('default', origin='outline', thoughts=text)
        frame.data = {'content': text}
        return frame

    def _outline_respond(self, flow, state, context, tools):
        import json
        user_text = context.last_user_text or ''
        candidates = self.memory.read_scratchpad('outline:candidates') or ''
        system = (
            'The user was shown outline candidates and replied. '
            'Classify the reply as "select" (they picked one) or "revise" (they gave feedback). '
            'If "select", extract the section titles as a JSON array of strings. '
            'Reply with ONLY a JSON object: {"action": "select"|"revise", "sections": [...]}.'
        )
        prompt = f"Candidates:\n{candidates}\n\nUser reply: {user_text}"
        raw = self.engineer.call(prompt, system=system, max_tokens=256).strip()
        raw = raw.strip('`').removeprefix('json').strip()
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            parsed = {'action': 'revise'}

        if parsed.get('action') == 'select' and parsed.get('sections'):
            sections = flow.slots['sections']
            sections.steps = [
                {'name': title, 'description': '', 'checked': False}
                for title in parsed['sections']
            ]
            sections.check_if_filled()
            flow.stage = 'default'
            return self._outline_direct(flow, state, context, tools)
        return self._outline_propose(flow, state, context, tools)

    def _outline_direct(self, flow, state, context, tools):
        post_id, _ = self._resolve_source_ids(flow, state, tools)
        if not post_id:
            topic = flow.slots.get('topic')
            if topic and topic.filled:
                post_id = self.resolve_post_id(str(topic.to_dict()), tools)
        text, tool_log = self.llm_execute(flow, state, context, tools)
        llm_saved = any(tc.get('tool') == 'generate_outline' for tc in tool_log)
        if post_id and text and not llm_saved:
            self._persist_outline(post_id, text, tools)
        sections = flow.slots.get('sections')
        if sections:
            for step in sections.steps:
                sections.mark_as_complete(step['name'])
        flow.status = 'Completed'
        frame = self.build_frame('card', origin='outline', thoughts=text)
        if post_id:
            frame.data = self._read_post_content(post_id, tools)
        return frame

    def refine_policy(self, flow, state, context, tools):
        grounding = flow.slots[flow.entity_slot]
        if not grounding.filled:
            self.ambiguity.declare('specific', metadata={'missing_slot': flow.entity_slot})
            frame = self.build_frame('default')
            frame.data = {'content': self.ambiguity.ask()}
            return frame

        # Fallback: if no outline bullets, push outline instead
        post_id, _ = self._resolve_source_ids(flow, state, tools)
        if post_id:
            result = tools('read_metadata', {'post_id': post_id, 'include_outline': True})
            if result.get('_success'):
                content = result.get('outline', '')
                if not self._has_bullets(content):
                    self.flow_stack.fallback('outline')
                    state.keep_going = True
                    frame = self.build_frame('default')
                    frame.data = {'content': 'No outline found — generating one.'}
                    return frame

        text, tool_log = self.llm_execute(flow, state, context, tools)
        llm_saved = any(tc.get('tool') == 'generate_outline' for tc in tool_log)
        if post_id and text and not llm_saved:
            self._persist_outline(post_id, text, tools)
        flow.status = 'Completed'
        frame = self.build_frame('card', origin='refine', thoughts=text)
        if post_id:
            frame.data = self._read_post_content(post_id, tools)
        return frame

    def cite_policy(self, flow, state, context, tools):
        source_slot = flow.slots.get('source')
        url_slot = flow.slots.get('url')
        if (not source_slot or not source_slot.filled) and (not url_slot or not url_slot.filled):
            self.ambiguity.declare('specific', metadata={'missing_slot': 'source_or_url'})
            frame = self.build_frame('default')
            frame.data = {'content': self.ambiguity.ask()}
            return frame

        text, tool_log = self.llm_execute(flow, state, context, tools)
        flow.status = 'Completed'
        frame = self.build_frame('card', origin='cite', thoughts=text)
        frame.data = {'content': text}
        return frame

    def compose_policy(self, flow, state, context, tools):
        grounding = flow.slots[flow.entity_slot]
        if not grounding.filled:
            self.ambiguity.declare('specific', metadata={'missing_slot': flow.entity_slot})
            frame = self.build_frame('default')
            frame.data = {'content': self.ambiguity.ask()}
            return frame

        # Stack-on: compose needs an outline
        post_id, _ = self._resolve_source_ids(flow, state, tools)
        if post_id:
            result = tools('read_metadata', {'post_id': post_id, 'include_outline': True})
            if result.get('_success'):
                content = result.get('outline', '')
                if not self._has_bullets(content):
                    self.flow_stack.push('outline')
                    state.keep_going = True
                    frame = self.build_frame('default')
                    frame.data = {'content': 'Generating outline first...'}
                    return frame

        text, tool_log = self.llm_execute(flow, state, context, tools)
        if post_id and text:
            _, sec_id = self._resolve_source_ids(flow, state, tools)
            if sec_id:
                self._persist_section(post_id, sec_id, text, tools)
        flow.status = 'Completed'
        frame = self.build_frame('card', origin='compose', thoughts=text)
        if post_id:
            frame.data = self._read_post_content(post_id, tools)
        return frame

    def add_policy(self, flow, state, context, tools):
        grounding = flow.slots[flow.entity_slot]
        if not grounding.filled:
            self.ambiguity.declare('specific', metadata={'missing_slot': flow.entity_slot})
            frame = self.build_frame('default')
            frame.data = {'content': self.ambiguity.ask()}
            return frame

        post_id, _ = self._resolve_source_ids(flow, state, tools)
        text, tool_log = self.llm_execute(flow, state, context, tools)
        flow.status = 'Completed'
        frame = self.build_frame('card', origin='add', thoughts=text)
        if post_id:
            frame.data = self._read_post_content(post_id, tools)
        return frame

    def create_policy(self, flow, state, context, tools):
        if not flow.slots.get('title', None) or not flow.slots['title'].filled:
            self.ambiguity.declare('specific', metadata={'missing_slot': 'title'})
            frame = self.build_frame('default')
            frame.data = {'content': self.ambiguity.ask()}
            return frame

        slots = flow.slot_values_dict()
        title = slots.get('title', 'Untitled')
        post_type = slots.get('type', 'draft')
        topic = slots.get('topic', '')

        create_params = {'title': title, 'type': post_type}
        if topic:
            create_params['topic'] = topic

        result = tools('create_post', create_params)

        if result.get('_success'):
            new_id = result.get('post_id', '')
            if new_id and state:
                state.active_post = new_id
            flow.status = 'Completed'
            frame = self.build_frame('card', origin='create')
            frame.data = {
                'post_id': new_id,
                'title': result.get('title', title),
                'status': result.get('status', post_type),
                'content': '',
            }
            return frame
        elif result.get('_error') == 'duplicate':
            self.ambiguity.declare('confirmation', metadata={
                'reason': 'duplicate_file',
            })
            frame = self.build_frame('confirmation')
            frame.data = {
                'prompt': result.get('_message', ''),
                'confirm_label': 'Override',
                'cancel_label': 'Keep Existing',
            }
            return frame
        else:
            frame = self.build_frame('default')
            frame.data = {
                'content': result.get('_message', f'Could not create {post_type} "{title}".'),
            }
            return frame

    def brainstorm_policy(self, flow, state, context, tools):
        if flow.slots['source'].filled or flow.slots['topic'].filled:
            text, _ = self.llm_execute(flow, state, context, tools)
        else:
            convo_history = context.compile_history(look_back=3)
            text = self.engineer.call(convo_history, system="Extract the topic the user wants to brainstorm about.")
            flow.fill_slots_by_label({'topic': self._parse_value(text)})
            if not flow.slots['topic'].filled:
                self.ambiguity.declare('specific', metadata={'missing_slot': 'topic'})
                frame = self.build_frame('default')
                frame.data = {'content': self.ambiguity.ask()}
                return frame
            else:
                text, _ = self.llm_execute(flow, state, context, tools)

        flow.status = 'Completed'
        frame = self.build_frame('default', thoughts=text)
        frame.data = {'content': text}
        return frame
