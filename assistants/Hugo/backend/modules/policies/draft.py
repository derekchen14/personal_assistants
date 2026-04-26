import logging

from backend.modules.policies.base import BasePolicy
from backend.components.display_frame import DisplayFrame

log = logging.getLogger(__name__)

_REMOVAL_TOKENS = ('remove', 'delete', 'drop', 'cut', 'trim')


def _count_bullets(outline:str) -> int:
    if not outline:
        return 0
    total = 0
    for line in outline.split('\n'):
        stripped = line.strip()
        if stripped.startswith('- ') or stripped.startswith('* '):
            total += 1
    return total


def _has_removal_intent(flow) -> bool:
    steps_slot = flow.slots['steps']
    for step in steps_slot.steps:
        desc = (step.get('description') or '').lower()
        name = (step.get('name') or '').lower()
        for token in _REMOVAL_TOKENS:
            if token in desc or token in name:
                return True
    feedback_slot = flow.slots['feedback']
    for entry in feedback_slot.values:
        lowered = (entry or '').lower()
        for token in _REMOVAL_TOKENS:
            if token in lowered:
                return True
    return False


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

    def outline_policy(self, flow, state, context, tools):
        if not flow.slots['source'].check_if_filled():
            self.ambiguity.declare('partial')
            return DisplayFrame()

        depth_slot = flow.slots['depth']
        depth = int(depth_slot.level) if depth_slot.check_if_filled() else 2

        if flow.slots['sections'].check_if_filled():
            flow.stage = 'direct'
            post_id = state.active_post

            text, tool_log = self.llm_execute(flow, state, context, tools,
                extra_resolved={'depth': depth})
            saved, _ = self.engineer.tool_succeeded(tool_log, 'generate_outline')

            if not text or not saved:
                frame = self.error_frame(flow, 'failed_to_save',
                    thoughts='LLM failed to generate outline.')
            else:
                for step in flow.slots['sections'].steps:
                    flow.slots['sections'].mark_as_complete(step['name'])
                flow.status = 'Completed'
                frame = DisplayFrame(origin='outline', thoughts=text)
                frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})

        elif flow.slots['topic'].check_if_filled():
            flow.stage = 'propose'
            frame = self._propose_outline(flow, state, context, tools, depth=depth)

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
                frame = DisplayFrame(flow.name())

        return frame

    def _propose_outline(self, flow, state, context, tools, depth:int=2):
        post_id = state.active_post
        # Defensive guard: Remove persistence tools from the skill's tool registry for Propose mode.
        # Also pass propose_mode=True in the resolved-context hint so the skill knows to stay text-only.
        frame = DisplayFrame(origin='outline')

        raw, tool_log = self.llm_execute(flow, state, context, tools,
            extra_resolved={'depth': depth, 'propose_mode': True},
            exclude_tools=('generate_outline',))
        candidates = self.engineer.apply_guardrails(raw, format='markdown', shape='candidates')
        flow.slots['proposals'].options = candidates

        if candidates:
            frame.add_block({'type': 'selection', 'data': {'candidates': candidates}})
        return frame

    def refine_policy(self, flow, state, context, tools):
        if not flow.is_filled():
            if not flow.slots['source'].filled:
                self.ambiguity.declare('partial', metadata={'missing_entity': 'post'})
            elif not flow.slots['feedback'].filled or not flow.slots['steps'].filled:
                self.ambiguity.declare('specific', metadata={'missing_slot': 'refine_details'})
            return DisplayFrame(flow.name())

        post_id, _ = self._resolve_source_ids(flow, state, tools)
        if not post_id:
            self.ambiguity.declare('partial', metadata={'missing_entity': 'post'})
            return DisplayFrame(flow.name())
        result = tools('read_metadata', {'post_id': post_id, 'include_outline': True})
        content = result.get('outline', '')

        # Stack-on: if the outline has no bullets yet, outline first so refine has something to
        # operate on.
        if _count_bullets(content) == 0:
            self.flow_stack.stackon('outline')
            state.keep_going = True
            return DisplayFrame(thoughts='No bullets in the outline yet, outlining first.')

        text, tool_log = self.llm_execute(flow, state, context, tools,
            extra_resolved={'current_outline': content})
        revised, _ = self.engineer.tool_succeeded(tool_log, 'revise_content')
        inserted, _ = self.engineer.tool_succeeded(tool_log, 'insert_section')
        renamed, _ = self.engineer.tool_succeeded(tool_log, 'update_post')
        removed, _ = self.engineer.tool_succeeded(tool_log, 'remove_content')
        saved = revised or inserted or renamed or removed

        if not text or not saved:
            return DisplayFrame(
                origin=flow.name(),
                metadata={'violation': 'failed_to_save'},
                thoughts='The refine skill did not save any changes (revise_content, insert_section, update_post rename, or remove_content).',
            )

        # Contract backstop: the skill must preserve existing bullets. If the post-save outline
        # is strictly shorter AND the user did not request removal, the skill violated the
        # contract.
        prior_bullets = _count_bullets(content)
        new_result = tools('read_metadata', {'post_id': post_id, 'include_outline': True})
        new_outline = new_result.get('outline', '')
        new_bullets = _count_bullets(new_outline)
        if new_bullets < prior_bullets and not _has_removal_intent(flow):
            thoughts = f'Outline shrunk from {prior_bullets} bullets to {new_bullets} without an explicit removal directive.'
            return DisplayFrame(
                origin=flow.name(),
                metadata={
                    'violation': 'failed_to_save',
                    'prior_bullets': prior_bullets,
                    'new_bullets': new_bullets,
                },
                thoughts=thoughts,
            )

        flow.status = 'Completed'
        frame = DisplayFrame(origin='refine', thoughts=text)
        frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        return frame

    def cite_policy(self, flow, state, context, tools):
        target_slot = flow.slots['target']
        url_slot = flow.slots['url']
        if not target_slot.check_if_filled() and not url_slot.check_if_filled():
            self.ambiguity.declare('specific', metadata={'missing_slot': 'target_or_url'})
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
                return DisplayFrame(thoughts='No sections yet, outlining first.')

        # Preload title + section preview into resolved-entities so the skill plans without re-fetching.
        # Skill owns persistence (calls revise_content per section); the post-read below refreshes the card.
        text, tool_log = self.llm_execute(flow, state, context, tools, include_preview=True)
        flow.status = 'Completed'
        frame = DisplayFrame(origin='compose', thoughts=text)
        if post_id:
            frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        return frame

    def add_policy(self, flow, state, context, tools):
        grounding = flow.slots[flow.entity_slot]
        if not grounding.check_if_filled():
            self.ambiguity.declare('specific', metadata={'missing_slot': flow.entity_slot})
            return DisplayFrame(flow.name())

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
            return DisplayFrame(flow.name())

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
            # If topic provided, chain into OutlineFlow to propose an initial outline.
            # if 'topic' in slots:
            #     self.flow_stack.stackon('outline')
            #     state.keep_going = True
            #     outline_flow = self.flow_stack.get_flow()
            #     outline_flow.slots['source'].add_one(post=new_id)
            #     outline_flow.slots['topic'].add_one(slots['topic'])
            #     frame.thoughts = 'Created the post, moving on to outline.'

        elif result.get('_error') == 'duplicate':
            observation = f'A post titled "{slots["title"]}" already exists. Overwrite it, or pick a different title?'
            self.ambiguity.declare('confirmation', observation=observation,
                metadata={'duplicate_title': slots['title']})
            frame = DisplayFrame(flow.name(), metadata={'duplicate_title': slots['title']})
        else:
            frame_meta = {'violation': 'tool_error', 'failed_tool': 'create_post'}
            reason = result.get('_message', 'unknown error')
            message = f"Could not create {slots['type']} _{slots['title']}_: {reason}."
            frame = DisplayFrame(origin='create', metadata=frame_meta, thoughts=message)
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
                return DisplayFrame(flow.name())
            else:
                text, _ = self.llm_execute(flow, state, context, tools)

        flow.status = 'Completed'
        return DisplayFrame(origin='brainstorm', thoughts=text)
