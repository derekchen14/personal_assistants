from __future__ import annotations

from typing import TYPE_CHECKING

from backend.modules.policies.base import BasePolicy

if TYPE_CHECKING:
    from backend.components.dialogue_state import DialogueState
    from backend.components.context_coordinator import ContextCoordinator
    from backend.components.display_frame import DisplayFrame
    from backend.components.flow_stack.parents import BaseFlow


class DraftPolicy(BasePolicy):

    def execute(self, flow: 'BaseFlow', state: 'DialogueState',
                context: 'ContextCoordinator', tools) -> 'DisplayFrame':
        match flow.name():
            case 'outline': return self.outline_policy(flow, state, context, tools)
            case 'refine': return self.refine_policy(flow, state, context, tools)
            case 'expand': return self.expand_policy(flow, state, context, tools)
            case 'compose': return self.compose_policy(flow, state, context, tools)
            case 'add': return self.add_policy(flow, state, context, tools)
            case 'create': return self.create_policy(flow, state, context, tools)
            case 'brainstorm': return self.brainstorm_policy(flow, state, context, tools)
            case _:
                return self.build_frame('default', {'content': ''})

    def outline_policy(self, flow, state, context, tools):
        if not flow.slots.get('topic', None) or not flow.slots['topic'].filled:
            convo_history = context.compile_history(look_back=3)
            text = self.engineer.call(convo_history, system="Extract the topic the user wants to outline for the blog post or note.")
            flow.fill_slots_by_label({'topic': self._parse_value(text)})
            if not flow.slots['topic'].filled:
                self.ambiguity.declare('specific', metadata={'missing_slot': 'topic'})
                return self.build_frame('default', {'content': self.ambiguity.ask()})

        text, tool_log = self.llm_execute(flow, state, context, tools)
        block_data = self.build_block_data(flow, text, tool_log)
        return self.build_frame('card', block_data, source='outline')

    def refine_policy(self, flow, state, context, tools):
        if not flow.slots.get('source', None) or not flow.slots['source'].filled:
            identifier = self.extract_source(flow, state)
            if identifier:
                flow.fill_slots_by_label({'source': identifier})
            if not flow.slots.get('source') or not flow.slots['source'].filled:
                self.ambiguity.declare('specific', metadata={'missing_slot': 'source'})
                return self.build_frame('default', {'content': self.ambiguity.ask()})

        text, tool_log = self.llm_execute(flow, state, context, tools)
        block_data = self.build_block_data(flow, text, tool_log)
        return self.build_frame('card', block_data, source='refine')

    def expand_policy(self, flow, state, context, tools):
        if not flow.slots.get('source', None) or not flow.slots['source'].filled:
            identifier = self.extract_source(flow, state)
            if identifier:
                flow.fill_slots_by_label({'source': identifier})
            if not flow.slots.get('source') or not flow.slots['source'].filled:
                self.ambiguity.declare('specific', metadata={'missing_slot': 'source'})
                return self.build_frame('default', {'content': self.ambiguity.ask()})

        text, tool_log = self.llm_execute(flow, state, context, tools)
        block_data = self.build_block_data(flow, text, tool_log)
        return self.build_frame('card', block_data, source='expand')

    def compose_policy(self, flow, state, context, tools):
        if not flow.slots.get('source', None) or not flow.slots['source'].filled:
            identifier = self.extract_source(flow, state)
            if identifier:
                flow.fill_slots_by_label({'source': identifier})
            if not flow.slots.get('source') or not flow.slots['source'].filled:
                self.ambiguity.declare('specific', metadata={'missing_slot': 'source'})
                return self.build_frame('default', {'content': self.ambiguity.ask()})

        text, tool_log = self.llm_execute(flow, state, context, tools)
        block_data = self.build_block_data(flow, text, tool_log)
        return self.build_frame('card', block_data, source='compose')

    def add_policy(self, flow, state, context, tools):
        if not flow.slots.get('source', None) or not flow.slots['source'].filled:
            identifier = self.extract_source(flow, state)
            if identifier:
                flow.fill_slots_by_label({'source': identifier})
            if not flow.slots.get('source') or not flow.slots['source'].filled:
                self.ambiguity.declare('specific', metadata={'missing_slot': 'source'})
                return self.build_frame('default', {'content': self.ambiguity.ask()})

        if not flow.slots.get('target', None) or not flow.slots['target'].filled:
            self.ambiguity.declare('specific', metadata={'missing_slot': 'target'})
            return self.build_frame('default', {'content': self.ambiguity.ask()})

        text, tool_log = self.llm_execute(flow, state, context, tools)
        block_data = self.build_block_data(flow, text, tool_log)
        return self.build_frame('card', block_data, source='add')

    def create_policy(self, flow, state, context, tools):
        if not flow.slots.get('title', None) or not flow.slots['title'].filled:
            self.ambiguity.declare('specific', metadata={'missing_slot': 'title'})
            return self.build_frame('default', {'content': self.ambiguity.ask()})

        slots = flow.slot_values_dict()
        title = slots.get('title', 'Untitled')
        post_type = slots.get('type', 'draft')
        topic = slots.get('topic', '')

        create_params = {
            'title': title,
            'status': 'note' if post_type == 'note' else 'draft',
        }
        if topic:
            create_params['topic'] = topic

        result = tools('post_create', create_params)

        if result.get('status') == 'success':
            post = result.get('result', {})
            return self.build_frame('card', {
                'post_id': post.get('post_id', ''),
                'title': post.get('title', title),
                'status': post.get('status', post_type),
                'content': post.get('content', ''),
            }, source='create')
        else:
            return self.build_frame('default', {
                'content': f'Created new {post_type} "{title}".',
            })

    def brainstorm_policy(self, flow, state, context, tools):
        if not flow.slots.get('topic', None) or not flow.slots['topic'].filled:
            convo_history = context.compile_history(look_back=3)
            text = self.engineer.call(convo_history, system="Extract the topic the user wants to brainstorm about.")
            flow.fill_slots_by_label({'topic': self._parse_value(text)})
            if not flow.slots['topic'].filled:
                self.ambiguity.declare('specific', metadata={'missing_slot': 'topic'})
                return self.build_frame('default', {'content': self.ambiguity.ask()})

        text, tool_log = self.llm_execute(flow, state, context, tools)
        block_data = self.build_block_data(flow, text, tool_log)
        return self.build_frame('card', block_data, source='brainstorm')
