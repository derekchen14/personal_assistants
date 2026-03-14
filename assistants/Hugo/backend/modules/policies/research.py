from __future__ import annotations

from typing import TYPE_CHECKING

from backend.modules.policies.base import BasePolicy

if TYPE_CHECKING:
    from backend.components.dialogue_state import DialogueState
    from backend.components.context_coordinator import ContextCoordinator
    from backend.components.display_frame import DisplayFrame
    from backend.components.flow_stack.parents import BaseFlow


class ResearchPolicy(BasePolicy):

    _TAB_TO_STATUS = {
        'drafts': 'draft', 'draft': 'draft',
        'posts': 'published', 'post': 'published', 'published': 'published',
        'notes': 'note', 'note': 'note',
    }

    def execute(self, flow: 'BaseFlow', state: 'DialogueState',
                context: 'ContextCoordinator', tools) -> 'DisplayFrame':
        match flow.name():
            case 'browse': return self.browse_policy(flow, state, context, tools)
            case 'view': return self.view_policy(flow, state, context, tools)
            case 'check': return self.check_policy(flow, state, context, tools)
            case 'inspect': return self.inspect_policy(flow, state, context, tools)
            case 'find': return self.find_policy(flow, state, context, tools)
            case 'compare': return self.compare_policy(flow, state, context, tools)
            case 'diff': return self.diff_policy(flow, state, context, tools)
            case _:
                return self.build_frame('default', {'content': ''})

    def browse_policy(self, flow, state, context, tools):
        cat_slot = flow.slots.get('category')
        category = str(cat_slot.to_dict()) if cat_slot and cat_slot.filled else None

        search_params = {'category': category} if category else {'status': 'note'}
        result = tools('post_search', search_params)
        items = result.get('result', []) if result.get('status') == 'success' else []

        summary = f"Found {len(items)} item(s)"
        summary += f" in category '{category}'" if category else " (saved notes/ideas)"
        summary += '.'
        if items:
            titles = [it.get('title', 'Untitled') for it in items[:10]]
            summary += ' Titles: ' + ', '.join(titles)

        convo_history = context.compile_history()
        history_with_data = f"{convo_history}\n\n[Data retrieved]\n{summary}"

        skill_prompt = self._load_skill_template(flow.name())
        messages = self.engineer.build_skill_prompt(flow, history_with_data, self.memory.read_scratchpad(), skill_prompt)
        text = self.engineer.call(messages)
        return self.build_frame('list', {
            'flow_name': flow.name(), 'content': text, 'items': items,
        }, source='browse')

    def view_policy(self, flow, state, context, tools):
        identifier = self.extract_source(flow, state)
        post_id = self.resolve_post_id(identifier, tools) if identifier else None

        if post_id:
            result = tools('post_get', {'post_id': post_id})
        else:
            result = {'status': 'error'}

        if result.get('status') == 'success':
            post = result['result']
            return self.build_frame('card', {
                'post_id': post.get('post_id', ''),
                'title': post.get('title', ''),
                'status': post.get('status', ''),
                'content': post.get('content', ''),
            }, source='view', panel='bottom')
        else:
            return self.build_frame('default', {
                'content': f'Could not find post "{identifier}".',
            })

    def check_policy(self, flow, state, context, tools):
        source_slot = flow.slots.get('source')
        status = None
        if source_slot and source_slot.filled:
            val = source_slot.to_dict()
            tab = val[0].get('post', '') if isinstance(val, list) and val else str(val)
            status = self._TAB_TO_STATUS.get(tab.lower())

        search_params = {'status': status} if status else {}
        result = tools('post_search', search_params)
        items = result.get('result', []) if result.get('status') == 'success' else []

        summary = f"Found {len(items)} item(s)"
        if status:
            summary += f" with status '{status}'"
        summary += '.'
        if items:
            titles = [it.get('title', 'Untitled') for it in items[:10]]
            summary += ' Titles: ' + ', '.join(titles)

        convo_history = context.compile_history()
        history_with_data = f"{convo_history}\n\n[Data retrieved]\n{summary}"

        skill_prompt = self._load_skill_template(flow.name())
        messages = self.engineer.build_skill_prompt(flow, history_with_data, self.memory.read_scratchpad(), skill_prompt)
        text = self.engineer.call(messages)
        return self.build_frame('default', {
            'flow_name': flow.name(), 'content': text,
        }, source='check')

    def inspect_policy(self, flow, state, context, tools):
        if not flow.slots.get('source', None) or not flow.slots['source'].filled:
            identifier = self.extract_source(flow, state)
            if identifier:
                flow.fill_slots_by_label({'source': identifier})
            if not flow.slots.get('source') or not flow.slots['source'].filled:
                self.ambiguity.declare('specific', metadata={'missing_slot': 'source'})
                return self.build_frame('default', {'content': self.ambiguity.ask()})

        text, tool_log = self.llm_execute(flow, state, context, tools)
        block_data = self.build_block_data(flow, text, tool_log)
        return self.build_frame('list', block_data, source='inspect')

    def find_policy(self, flow, state, context, tools):
        query_slot = flow.slots.get('query')
        query = str(query_slot.to_dict()) if query_slot and query_slot.filled else ''

        count_slot = flow.slots.get('count')
        limit = None
        if count_slot and count_slot.filled:
            try:
                limit = int(count_slot.to_dict())
            except (ValueError, TypeError):
                pass

        search_params = {'query': query} if query else {}
        result = tools('post_search', search_params)
        items = result.get('result', []) if result.get('status') == 'success' else []
        if limit:
            items = items[:limit]

        summary = f"Found {len(items)} item(s)"
        if query:
            summary += f" matching '{query}'"
        summary += '.'
        if items:
            titles = [it.get('title', 'Untitled') for it in items[:10]]
            summary += ' Titles: ' + ', '.join(titles)

        convo_history = context.compile_history()
        history_with_data = f"{convo_history}\n\n[Data retrieved]\n{summary}"

        skill_prompt = self._load_skill_template(flow.name())
        messages = self.engineer.build_skill_prompt(flow, history_with_data, self.memory.read_scratchpad(), skill_prompt)
        text = self.engineer.call(messages)
        return self.build_frame('list', {
            'flow_name': flow.name(), 'content': text, 'items': items,
        }, source='find')

    def compare_policy(self, flow, state, context, tools):
        source_slot = flow.slots.get('source')
        if not source_slot or not source_slot.filled:
            self.ambiguity.declare('specific', metadata={'missing_slot': 'source'})
            return self.build_frame('default', {'content': self.ambiguity.ask()})

        text, tool_log = self.llm_execute(flow, state, context, tools)
        block_data = self.build_block_data(flow, text, tool_log)
        return self.build_frame('list', block_data, source='compare')

    def diff_policy(self, flow, state, context, tools):
        if not flow.slots.get('source', None) or not flow.slots['source'].filled:
            identifier = self.extract_source(flow, state)
            if identifier:
                flow.fill_slots_by_label({'source': identifier})
            if not flow.slots.get('source') or not flow.slots['source'].filled:
                self.ambiguity.declare('specific', metadata={'missing_slot': 'source'})
                return self.build_frame('default', {'content': self.ambiguity.ask()})

        text, tool_log = self.llm_execute(flow, state, context, tools)
        block_data = self.build_block_data(flow, text, tool_log)
        return self.build_frame('list', block_data, source='diff')
