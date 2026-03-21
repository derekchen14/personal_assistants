from __future__ import annotations
from backend.modules.policies.base import BasePolicy
from backend.components.display_frame import DisplayFrame


class ResearchPolicy(BasePolicy):

    _TAB_TO_STATUS = {
        'drafts': 'draft', 'draft': 'draft',
        'posts': 'published', 'post': 'published', 'published': 'published',
        'notes': 'note', 'note': 'note',
    }

    def __init__(self, components:dict):
        super().__init__(components)
        self.flow_stack = components['flow_stack']

    def execute(self, state, context, tools) -> 'DisplayFrame':
        flow = self.flow_stack.get_active_flow()

        match flow.name():
            case 'browse': return self.browse_policy(flow, state, context, tools)
            case 'summarize': return self.summarize_policy(flow, state, context, tools)
            case 'check': return self.check_policy(flow, state, context, tools)
            case 'inspect': return self.inspect_policy(flow, state, context, tools)
            case 'find': return self.find_policy(flow, state, context, tools)
            case 'compare': return self.compare_policy(flow, state, context, tools)
            case 'diff': return self.diff_policy(flow, state, context, tools)
            case _:
                frame = self.build_frame('default')
                frame.data = {'content': ''}
                return frame

    def browse_policy(self, flow, state, context, tools):
        cat_slot = flow.slots.get('category')
        category = str(cat_slot.to_dict()) if cat_slot and cat_slot.filled else None

        if category:
            result = tools('find_posts', {'query': category})
        else:
            result = tools('find_posts', {'status': 'note'})
        items = result.get('items', []) if result.get('_success') else []

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
        flow.status = 'Completed'
        frame = self.build_frame('list', origin='browse')
        frame.data = {'content': text, 'items': items}
        return frame

    def summarize_policy(self, flow, state, context, tools):
        post_id, _ = self._resolve_source_ids(flow, state, tools)

        if not post_id:
            self.ambiguity.declare('specific', metadata={'missing_slot': flow.entity_slot})
            frame = self.build_frame('default')
            frame.data = {'content': self.ambiguity.ask()}
            return frame

        meta = tools('read_metadata', {'post_id': post_id, 'include_outline': True})
        if not meta.get('_success'):
            frame = self.build_frame('default')
            frame.data = {'content': 'Could not find the specified post.'}
            return frame

        length_slot = flow.slots.get('length')
        length_hint = f" Aim for {length_slot.to_dict()} words." if length_slot and length_slot.filled else ''

        convo_history = context.compile_history()
        history_with_data = (
            f"{convo_history}\n\n[Post content]\nTitle: {meta.get('title', '')}\n"
            f"Content: {meta.get('outline', '')}"
        )
        skill_prompt = self._load_skill_template(flow.name())
        messages = self.engineer.build_skill_prompt(
            flow, history_with_data, self.memory.read_scratchpad(),
            skill_prompt + length_hint,
        )
        text = self.engineer.call(messages)
        flow.status = 'Completed'
        frame = self.build_frame('card', origin='summarize', panel='bottom')
        frame.data = {
            'post_id': post_id,
            'title': meta.get('title', ''),
            'content': text,
        }
        return frame

    def check_policy(self, flow, state, context, tools):
        grounding = flow.slots.get(flow.entity_slot)
        status = None
        if grounding and grounding.filled:
            tab = grounding.values[0].get('post', '')
            status = self._TAB_TO_STATUS.get(tab.lower())

        params = {'status': status} if status else {}
        result = tools('find_posts', params)
        items = result.get('items', []) if result.get('_success') else []

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
        flow.status = 'Completed'
        frame = self.build_frame('default', origin='check')
        frame.data = {'content': text}
        return frame

    def inspect_policy(self, flow, state, context, tools):
        grounding = flow.slots[flow.entity_slot]
        if not grounding.filled:
            self.ambiguity.declare('specific', metadata={'missing_slot': flow.entity_slot})
            frame = self.build_frame('default')
            frame.data = {'content': self.ambiguity.ask()}
            return frame

        text, tool_log = self.llm_execute(flow, state, context, tools)
        result = self.extract_tool_result(tool_log, 'inspect_post')

        # Build a clean metrics summary from tool results
        metrics = self._format_inspect_metrics(result)
        flow.status = 'Completed'
        frame = self.build_frame('list', origin='inspect', thoughts=text)
        frame.data = {'content': metrics or text}
        return frame

    @staticmethod
    def _format_inspect_metrics(result:dict) -> str|None:
        """Format inspect tool results into a readable metrics summary."""
        fields = {
            'word_count': 'Word count',
            'section_count': 'Sections',
            'estimated_read_time': 'Read time (min)',
            'image_count': 'Images',
            'link_count': 'Links',
            'avg_paragraph_length': 'Avg paragraph length',
            'heading_depth': 'Heading depth',
        }
        lines = []
        for key, label in fields.items():
            if key in result:
                lines.append(f'{label}: {result[key]}')
        empty = result.get('empty_sections', [])
        if empty:
            lines.append(f'Empty sections: {", ".join(empty)}')
        return '\n'.join(lines) if lines else None

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
                result = tools('find_posts', {'query': term})
                for item in result.get('items', []) if result.get('_success') else []:
                    if item['post_id'] not in seen_ids:
                        seen_ids.add(item['post_id'])
                        items.append(item)
        else:
            result = tools('find_posts', {})
            items = result.get('items', []) if result.get('_success') else []
        if limit:
            items = items[:limit]

        n = len(items)
        summary = f"Found {n} item(s) matching '{query}'." if query else f"Found {n} item(s)."
        for it in items[:10]:
            line = f"  - {it.get('title', 'Untitled')}"
            if it.get('preview_snippet'):
                line += f": {it['preview_snippet']}"
            summary += '\n' + line

        convo_history = context.compile_history()
        history_with_data = f"{convo_history}\n\n[Data retrieved]\n{summary}"
        skill_prompt = self._load_skill_template(flow.name())
        messages = self.engineer.build_skill_prompt(flow, history_with_data, self.memory.read_scratchpad(), skill_prompt)
        text = self.engineer.call(messages)
        flow.status = 'Completed'

        if n == 0:
            frame = self.build_frame('default', origin='find')
            frame.data = {'content': text}
            return frame

        if n == 1:
            post_id = items[0]['post_id']
            result = tools('read_metadata', {'post_id': post_id, 'include_outline': True})
            if result.get('_success'):
                frame = self.build_frame('card', origin='find', panel='bottom')
                frame.data = {
                    'post_id': post_id,
                    'title': result.get('title', ''),
                    'status': result.get('status', ''),
                    'content': result.get('outline', ''),
                }
                return frame

        post_count = sum(1 for it in items if it.get('status') == 'published')
        draft_count = sum(1 for it in items if it.get('status') == 'draft')
        page = 'posts' if post_count >= draft_count else 'drafts'
        frame = self.build_frame('list', origin='find', panel='top')
        frame.data = {'content': text, 'items': items, 'page': page}
        if n <= 8:
            frame.data['expanded_ids'] = [it['post_id'] for it in items]
        return frame

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
        grounding = flow.slots.get(flow.entity_slot)
        if not grounding or not grounding.filled:
            self.ambiguity.declare('specific', metadata={'missing_slot': flow.entity_slot})
            frame = self.build_frame('default')
            frame.data = {'content': self.ambiguity.ask()}
            return frame

        posts = []
        for entry in grounding.values[:2]:
            identifier = entry.get('post', '')
            post_id = self.resolve_post_id(identifier, tools) if identifier else None
            if post_id:
                result = tools('read_metadata', {'post_id': post_id, 'include_outline': True})
                if result.get('_success'):
                    posts.append(result)

        text, tool_log = self.llm_execute(flow, state, context, tools)
        flow.status = 'Completed'

        left = posts[0] if len(posts) > 0 else {}
        right = posts[1] if len(posts) > 1 else {}
        frame = self.build_frame('compare', origin='compare', thoughts=text)
        frame.data = {'left': left, 'right': right, 'content': text}
        return frame

    def diff_policy(self, flow, state, context, tools):
        grounding = flow.slots[flow.entity_slot]
        if not grounding.filled:
            self.ambiguity.declare('specific', metadata={'missing_slot': flow.entity_slot})
            frame = self.build_frame('default')
            frame.data = {'content': self.ambiguity.ask()}
            return frame

        text, tool_log = self.llm_execute(flow, state, context, tools)
        flow.status = 'Completed'
        frame = self.build_frame('list', origin='diff', thoughts=text)
        frame.data = {'content': text}
        return frame
