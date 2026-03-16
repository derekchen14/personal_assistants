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

        seen_ids: set = set()
        items: list = []
        if query:
            for term in self._expand_query(query):
                result = tools('post_search', {'query': term})
                for item in result.get('result', []) if result.get('status') == 'success' else []:
                    if item['post_id'] not in seen_ids:
                        seen_ids.add(item['post_id'])
                        items.append(item)
        else:
            result = tools('post_search', {})
            items = result.get('result', []) if result.get('status') == 'success' else []
        if limit:
            items = items[:limit]

        n = len(items)
        summary = f"Found {n} item(s) matching '{query}'." if query else f"Found {n} item(s)."
        for it in items[:10]:
            line = f"  - {it.get('title', 'Untitled')}"
            if it.get('snippet'):
                line += f": {it['snippet']}"
            summary += '\n' + line

        convo_history = context.compile_history()
        history_with_data = f"{convo_history}\n\n[Data retrieved]\n{summary}"
        skill_prompt = self._load_skill_template(flow.name())
        messages = self.engineer.build_skill_prompt(flow, history_with_data, self.memory.read_scratchpad(), skill_prompt)
        text = self.engineer.call(messages)

        if n == 0:
            return self.build_frame('default', {'content': text}, source='find')

        if n == 1:
            post_id = items[0]['post_id']
            result = tools('post_get', {'post_id': post_id})
            if result.get('status') == 'success':
                post = result['result']
                return self.build_frame('card', {
                    'post_id': post.get('post_id', ''),
                    'title': post.get('title', ''),
                    'status': post.get('status', ''),
                    'content': post.get('content', ''),
                }, source='find', panel='bottom')

        post_count = sum(1 for it in items if it.get('status') == 'published')
        draft_count = sum(1 for it in items if it.get('status') == 'draft')
        page = 'posts' if post_count >= draft_count else 'drafts'
        block_data = {'content': text, 'items': items, 'source': 'find', 'page': page}
        if n <= 8:
            block_data['expanded_ids'] = [it['post_id'] for it in items]
        return self.build_frame('list', block_data, source='find', panel='top')

    def _expand_query(self, query: str) -> list[str]:
        """Use LLM to generate semantically similar search terms."""
        import json
        system = (
            f'Return 3-4 short search terms that are semantically similar or related to "{query}". '
            'Include the original term. Reply with ONLY a JSON array of strings, no explanation.'
        )
        try:
            text = self.engineer.call(query, system=system, max_tokens=128).strip()
            text = text.strip('`').removeprefix('json').strip()
            terms = json.loads(text)
            if isinstance(terms, list) and terms:
                return [str(t) for t in terms[:4]]
        except Exception:
            pass
        return [query]

    def compare_policy(self, flow, state, context, tools):
        source_slot = flow.slots.get('source')
        if not source_slot or not source_slot.filled:
            self.ambiguity.declare('specific', metadata={'missing_slot': 'source'})
            return self.build_frame('default', {'content': self.ambiguity.ask()})

        sources = source_slot.to_dict()
        entries = sources if isinstance(sources, list) else [sources]

        posts = []
        for entry in entries[:2]:
            identifier = entry.get('post', '') if isinstance(entry, dict) else str(entry)
            post_id = self.resolve_post_id(identifier, tools) if identifier else None
            if post_id:
                result = tools('post_get', {'post_id': post_id})
                if result.get('status') == 'success':
                    posts.append(result['result'])

        text, tool_log = self.llm_execute(flow, state, context, tools)

        left = posts[0] if len(posts) > 0 else {}
        right = posts[1] if len(posts) > 1 else {}
        return self.build_frame('compare', {
            'left': left, 'right': right, 'content': text,
        }, source='compare')

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
