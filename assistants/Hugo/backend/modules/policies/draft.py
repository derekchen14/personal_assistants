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
            case _: raise ValueError(f"Unknown flow name: {flow.name()}")

    @staticmethod
    def _has_bullets(content:str) -> bool:
        for line in content.split('\n'):
            stripped = line.strip()
            if stripped.startswith('- ') or stripped.startswith('* ') or stripped.startswith('1. '):
                return True
        return False

    def outline_policy(self, flow, state, context, tools):
        if not flow.slots['source'].check_if_filled():
            self.ambiguity.declare('partial')
            return DisplayFrame()

        if flow.slots['sections'].check_if_filled():
            flow.stage = 'direct'
            post_id = state.active_post

            text, tool_log = self.llm_execute(flow, state, context, tools)
            outline_calls = [tc for tc in tool_log if tc.get('tool') == 'generate_outline']
            saved = outline_calls and all(tc.get('result', {}).get('_success') for tc in outline_calls)

            if not text or not saved:
                frame = DisplayFrame(origin='outline', metadata={'error': 'LLM failed to generate outline'})
            else:
                for step in flow.slots['sections'].steps:
                    flow.slots['sections'].mark_as_complete(step['name'])
                flow.status = 'Completed'
                frame = DisplayFrame(origin='outline', thoughts=text)
                frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})

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
            prompt = f'{convo_history}\n\nExtract the topic the user wants to outline for the blog post or note. Reply with JSON: {{"topic": "..."}}.'
            parsed = self.engineer.apply_guardrails(self.engineer(prompt, 'fill_slots'))
            flow.fill_slots_by_label({'topic': parsed and parsed.get('topic')})

            if flow.slots['topic'].filled:
                flow.stage = 'propose'
                frame = self._propose_outline(flow, state, context, tools)
            else:
                flow.stage = 'error'  # Missing topic is an error state
                self.ambiguity.declare('specific', metadata={'missing_slot': 'topic'})
                frame = DisplayFrame('error')

        return frame

    def _propose_outline(self, flow, state, context, tools):
        post_id = state.active_post
        raw, tool_log = self.llm_execute(flow, state, context, tools)
        frame = DisplayFrame(origin='outline')

        # If LLM ignored propose-mode rules and saved directly, treat it as such rather than returning an empty card
        if any(tc.get('tool') == 'generate_outline' for tc in tool_log):
            flow.stage = 'direct'
            flow.status = 'Completed'
            if post_id:
                frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        else:
            candidates = self.engineer.apply_guardrails(raw, format='markdown', shape='candidates')
            flow.slots['proposals'].options = candidates
            if candidates:
                frame.add_block({'type': 'selection', 'data': {'candidates': candidates}})
        return frame

    def refine_policy(self, flow, state, context, tools):
        if not flow.is_filled():
            if not flow.slots['source'].filled:
                self.ambiguity.declare('partial', metadata={'missing_ground': 'source slot empty'})
            elif not flow.slots['feedback'].filled or not flow.slots['steps'].filled:
                self.ambiguity.declare('specific', metadata={'missing_slot': 'details on how to refine the outline are incomplete'})
            return DisplayFrame()

        post_id, _ = self._resolve_source_ids(flow, state, tools)
        if not post_id:
            self.ambiguity.declare('specific', metadata={'missing_ground': 'could not resolve source to a post'})
            return DisplayFrame()
        result = tools('read_metadata', {'post_id': post_id, 'include_outline': True})
        content = result.get('outline', '')

        if self._has_bullets(content):
            text, tool_log = self.llm_execute(flow, state, context, tools)
            outline_calls = [tc for tc in tool_log if tc.get('tool') == 'generate_outline']
            saved = outline_calls and all(tc.get('result', {}).get('_success') for tc in outline_calls)

            if not text or not saved:
                frame = DisplayFrame(origin='refine', metadata={'error': 'LLM failed to refine outline bulletpoints'})
            else:
                flow.status = 'Completed'
                frame = DisplayFrame(origin='refine', thoughts=text)
                frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        else:
            # if the outline doesn't have bulletpoints, then stack-on OutlineFlow
            self.flow_stack.stackon('outline')
            state.keep_going = True
            frame = DisplayFrame()

        return frame

    def cite_policy(self, flow, state, context, tools):
        source_slot = flow.slots['source']
        url_slot = flow.slots['url']
        if not source_slot.check_if_filled() and not url_slot.check_if_filled():
            self.ambiguity.declare('specific', metadata={'missing_slot': 'source_or_url'})
            return DisplayFrame()

        text, tool_log = self.llm_execute(flow, state, context, tools)
        flow.status = 'Completed'
        return DisplayFrame(origin='cite', thoughts=text)

    def compose_policy(self, flow, state, context, tools):
        grounding = flow.slots[flow.entity_slot]
        if not grounding.check_if_filled():
            self.ambiguity.declare('specific', metadata={'missing_slot': flow.entity_slot})
            return DisplayFrame()

        # Stack-on: compose needs an outline only when the post has no structure yet.
        post_id, _ = self._resolve_source_ids(flow, state, tools)
        if post_id:
            result = tools('read_metadata', {'post_id': post_id})
            if result['_success'] and not result.get('section_ids'):
                self.flow_stack.stackon('outline')
                state.keep_going = True
                return DisplayFrame()

        text, tool_log = self.llm_execute(flow, state, context, tools)
        if post_id and text:
            _, sec_id = self._resolve_source_ids(flow, state, tools)
            if sec_id:
                self._persist_section(post_id, sec_id, text, tools)
        flow.status = 'Completed'
        frame = DisplayFrame(origin='compose', thoughts=text)
        if post_id:
            frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        return frame

    def add_policy(self, flow, state, context, tools):
        grounding = flow.slots[flow.entity_slot]
        if not grounding.check_if_filled():
            self.ambiguity.declare('specific', metadata={'missing_slot': flow.entity_slot})
            return DisplayFrame('error')

        post_id, _ = self._resolve_source_ids(flow, state, tools)
        text, tool_log = self.llm_execute(flow, state, context, tools)
        flow.status = 'Completed'
        frame = DisplayFrame(origin='add', thoughts=text)
        if post_id:
            frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        return frame

    def create_policy(self, flow, state, context, tools):
        if not flow.is_filled():
            if not flow.slots['title'].filled:
                self.ambiguity.declare('specific', metadata={'missing_slot': 'title'})
            elif not flow.slots['type'].filled:
                self.ambiguity.declare('specific', metadata={'missing_slot': 'type'})
            else:
                self.ambiguity.declare('partial')
            return DisplayFrame('error')

        slots = flow.slot_values_dict()
        create_params = { 'title': slots['title'], 'type': slots['type'] }
        if 'topic' in slots:
            create_params['topic'] = slots['topic']
        result = tools('create_post', create_params)

        if result['_success']:
            new_id = result['post_id']
            state.active_post = new_id
            flow.status = 'Completed'
            frame = DisplayFrame(origin='create')
            block_data = {'post_id': new_id, 'title': result.get('title', ''), 'status': result['status']}
            frame.add_block({'type': 'card', 'data': block_data})

        elif result.get('_error') == 'duplicate':
            self.ambiguity.declare('confirmation', metadata={'reason': 'duplicate_file'})
            frame = DisplayFrame(origin='create', metadata={'duplicate_title': slots['title']})

            warning_msg = 'A post with this title already exists. Do you want to create another one with the same title?'
            block_data = {
                'prompt': result.get('_message', warning_msg),
                'confirm_label': 'Yes, create duplicate',
                'cancel_label': 'No, keep existing post'
            }
            frame.add_block({'type': 'confirmation', 'data': block_data})
        else:
            message = result.get('_message', f"Could not create {slots['type']}: _{slots['title']}_.")
            frame = DisplayFrame(origin='create', thoughts=message)
        return frame

    def brainstorm_policy(self, flow, state, context, tools):
        if flow.slots['source'].check_if_filled():
            text, _ = self.llm_execute(flow, state, context, tools)
        elif flow.slots['topic'].check_if_filled():
            flow.entity_slot = 'topic'
            text, _ = self.llm_execute(flow, state, context, tools)
        else:
            convo_history = context.compile_history(look_back=3)
            prompt = f'{convo_history}\n\nExtract the topic the user wants to brainstorm about. Reply with JSON: {{"topic": "..."}}.'
            raw_output = self.engineer(prompt, 'fill_slots')
            parsed = self.engineer.apply_guardrails(raw_output)
            flow.fill_slots_by_label({'topic': parsed and parsed.get('topic')})
            if not flow.slots['topic'].filled:
                self.ambiguity.declare('specific', metadata={'missing_slot': 'topic'})
                return DisplayFrame('error')
            else:
                text, _ = self.llm_execute(flow, state, context, tools)

        flow.status = 'Completed'
        return DisplayFrame(origin='brainstorm', thoughts=text)
