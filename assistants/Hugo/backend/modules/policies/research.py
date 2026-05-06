from backend.modules.policies.base import BasePolicy
from backend.components.display_frame import DisplayFrame


class ResearchPolicy(BasePolicy):

    _TAB_TO_STATUS = {
        'drafts': 'draft', 'draft': 'draft',
        'posts': 'published', 'post': 'published', 'published': 'published',
        'notes': 'note', 'note': 'note',
    }

    def __init__(self, components):
        super().__init__(components)
        self.flow_stack = components['flow_stack']

    def execute(self, state, context, tools):
        flow = self.flow_stack.get_flow()

        match flow.name():
            case 'browse': return self.browse_policy(flow, state, context, tools)
            case 'summarize': return self.summarize_policy(flow, state, context, tools)
            case 'check': return self.check_policy(flow, state, context, tools)
            case 'inspect': return self.inspect_policy(flow, state, context, tools)
            case 'find': return self.find_policy(flow, state, context, tools)
            case 'compare': return self.compare_policy(flow, state, context, tools)
            case 'diff': return self.diff_policy(flow, state, context, tools)
            case _:
                return DisplayFrame()

    def browse_policy(self, flow, state, context, tools):
        query_slot = flow.slots['query']
        if not query_slot.check_if_filled():
            self.ambiguity.declare('partial', metadata={'missing': 'query'})
            return DisplayFrame(flow.name())

        target_slot = flow.slots['target']
        # Default-commit: target is elective; commit 'note' when unset.
        target = str(target_slot.to_dict()) if target_slot.check_if_filled() else 'note'

        tags = query_slot.to_dict()
        params = {'tags': tags}
        if target == 'note':
            params['status'] = 'note'
        result = tools('find_posts', params)
        items = result['items'] if result['_success'] else []

        titles = [it['title'] for it in items[:10]]
        summary = f"Found {len(items)} item(s) tagged {', '.join(tags)} (target='{target}')."
        if titles:
            summary += ' Titles: ' + ', '.join(titles)

        convo_history = context.compile_history()
        history_with_data = f"{convo_history}\n\n[Data retrieved]\n{summary}"
        text = self.engineer.skill_call(flow, history_with_data, self.memory.read_scratchpad())

        flow.status = 'Completed'
        frame = DisplayFrame(flow.name(), thoughts=text)
        frame.add_block({'type': 'list', 'data': {'items': items}})
        return frame

    def summarize_policy(self, flow, state, context, tools):
        if frame := self._guard_entity(flow): return frame
        post_id, _, error = self.resolve_source_ids(flow, state, tools)
        if error: return error

        flow_metadata = tools('read_metadata', {'post_id': post_id, 'include_outline': True})
        if not flow_metadata['_success']:
            frame = self.error_frame(flow, 'missing_reference',
                thoughts='Could not find the specified post.',
                missing_entity='post')
        else:
            length_slot = flow.slots['length']
            length_hint = f" Aim for {length_slot.to_dict()} words." if length_slot.filled else ''

            convo_history = context.compile_history()
            history_with_data = (
                f"{convo_history}\n\n[Post content]\nTitle: {flow_metadata['title']}\n"
                f"Content: {flow_metadata['outline']}"
            )
            skill_prompt = self.engineer.load_skill_template(flow.name()) + length_hint
            summary = self.engineer.skill_call(
                flow, history_with_data, self.memory.read_scratchpad(),
                skill_prompt=skill_prompt,
            )
            flow.status = 'Completed'
            frame = DisplayFrame(flow.name(), thoughts=summary)
        return frame

    def check_policy(self, flow, state, context, tools):
        # Check treats grounding as optional — a filled tab narrows the search.
        # No entity guard fires; the flow is happy to list everything.
        grounding = flow.slots[flow.entity_slot]
        status = None
        if grounding.check_if_filled():
            tab = grounding.values[0]['post']
            status = self._TAB_TO_STATUS.get(tab.lower())

        params = {'status': status} if status else {}
        result = tools('find_posts', params)
        items = result['items'] if result['_success'] else []

        summary = f"Found {len(items)} item(s)"
        if status:
            summary += f" with status '{status}'"
        summary += '.'
        if items:
            titles = [it['title'] for it in items[:10]]
            summary += ' Titles: ' + ', '.join(titles)

        convo_history = context.compile_history()
        history_with_data = f"{convo_history}\n\n[Data retrieved]\n{summary}"
        text = self.engineer.skill_call(flow, history_with_data, self.memory.read_scratchpad())

        flow.status = 'Completed'
        # Check narrates the result in chat — no Display-Container update.
        return DisplayFrame(flow.name(), thoughts=text)

    def inspect_policy(self, flow, state, context, tools):
        if frame := self._guard_entity(flow): return frame

        post_id, _, error = self.resolve_source_ids(flow, state, tools)
        if error: return error

        # Elective-with-default: limit metrics when aspect is filled.
        params = {'post_id': post_id}
        aspect_slot = flow.slots['aspect']
        if aspect_slot.filled:
            params['metrics'] = [str(aspect_slot.to_dict())]

        result = tools('inspect_post', params)
        if not result['_success']:
            frame = self.error_frame(flow, 'tool_error',
                thoughts=result['_message'],
                failed_tool='inspect_post')
        else:
            metrics = {key: val for key, val in result.items() if key != '_success'}
            # Scratchpad write for cross-turn findings consumption.
            self.memory.write_scratchpad(flow.name(), {
                'version': '1',
                'turn_number': context.turn_id,
                'used_count': 0,
                'post_id': post_id,
                'metrics': metrics,
            })
            flow.status = 'Completed'
            # Inspect narrates in chat — the metrics stay in metadata for
            # downstream policy consumers, but no block updates the UI.
            frame = DisplayFrame(flow.name(), metadata={'metrics': metrics})
        return frame

    def find_policy(self, flow, state, context, tools):
        query_slot = flow.slots['query']
        query = str(query_slot.to_dict()) if query_slot.check_if_filled() else ''

        count_slot = flow.slots['count']
        limit = int(count_slot.to_dict()) if count_slot.check_if_filled() else None

        seen_ids:set = set()
        items:list = []
        if query:
            for term in self._expand_query(query):
                result = tools('find_posts', {'query': term})
                for item in (result['items'] if result['_success'] else []):
                    if item['post_id'] not in seen_ids:
                        seen_ids.add(item['post_id'])
                        items.append(item)
        else:
            result = tools('find_posts', {})
            items = result['items'] if result['_success'] else []
        if limit:
            items = items[:limit]

        post_count = sum(1 for it in items if it['status'] == 'published')
        draft_count = sum(1 for it in items if it['status'] == 'draft')
        page = 'posts' if post_count >= draft_count else 'drafts'

        list_data = {'items': items, 'page': page}
        if items and len(items) <= 8:
            list_data['expanded_ids'] = [it['post_id'] for it in items]

        # Scratchpad write — downstream audit/polish can reference matches.
        self.memory.write_scratchpad(flow.name(), {
            'version': '1',
            'turn_number': context.turn_id,
            'used_count': 0,
            'query': query,
            'items': [
                {'post_id': it['post_id'], 'title': it['title'], 'status': it['status'],
                    'preview': it.get('preview', it.get('preview_snippet', '')),
                }
                for it in items
            ],
        })

        flow.status = 'Completed'
        frame = DisplayFrame(flow.name())
        frame.add_block({'type': 'list', 'data': list_data, 'expand': True})
        return frame

    def _expand_query(self, query:str) -> list[str]:
        """LLM-generate 3-4 semantically similar search terms."""
        import json
        prompt = (
            f'Return 3-4 short search terms that are semantically similar or related to "{query}". '
            'Include the original term. Reply with ONLY a JSON array of strings, no explanation.'
        )
        try:
            raw_output = self.engineer(prompt, max_tokens=128)
            cleaned = raw_output.strip().strip('`').removeprefix('json').strip()
            terms = json.loads(cleaned)
            if isinstance(terms, list) and terms:
                return [str(t) for t in terms[:4]]
        except Exception:
            pass
        return [query]

    def compare_policy(self, flow, state, context, tools):
        if frame := self._guard_entity(flow): return frame

        # Comparison kind drives both the metrics surfaced and the prose framing.
        # Ask before dispatching when none was named.
        if not flow.slots['category'].check_if_filled():
            self.ambiguity.declare('specific',
                observation='Should I compare metrics, metadata, or tone?',
                metadata={'missing': 'category'})
            return DisplayFrame(flow.name())

        grounding = flow.slots[flow.entity_slot]
        posts = [self._read_post_content(self._resolve_post_id(e['post'], tools), tools)
                 for e in grounding.values[:2]]
        if not (posts[0] and posts[1]):
            named = [e['post'] for e in grounding.values[:2]]
            return self.error_frame(flow, 'missing_reference',
                thoughts=f"Could not find one or both posts: {named}.",
                missing_entity='post')

        text, tool_log = self.llm_execute(flow, state, context, tools)

        # Skill may declare ambiguity (e.g. missing category); leave flow Active so the
        # next turn can resolve rather than treating completion as final.
        if self.ambiguity.present():
            return DisplayFrame(flow.name())

        flow.status = 'Completed'
        frame = DisplayFrame(flow.name(), thoughts=text)
        frame.add_block({'type': 'compare', 'data': {'left': posts[0], 'right': posts[1]}, 'expand': True})
        return frame

    def diff_policy(self, flow, state, context, tools):
        if frame := self._guard_entity(flow): return frame

        text, tool_log = self.llm_execute(flow, state, context, tools)
        flow.status = 'Completed'
        frame = DisplayFrame(flow.name(), thoughts=text)
        # Diff compares two code versions — users need to SEE the diff visually, not just hear it
        # narrated. Surface the structured diff via a compare block so the frontend can render it.
        # extract_tool_result returns the success payload (with _* keys stripped) or {} if the
        # tool wasn't called or its call failed. Non-empty dict = success path.
        diff_result = self.engineer.extract_tool_result(tool_log, 'diff_section')
        if diff_result:
            frame.add_block({'type': 'compare', 'data': {
                'left':    {'title': 'Original', 'content': diff_result['source']},
                'right':   {'title': 'Updated',  'content': diff_result['target']},
                'content': diff_result['diff'],
            }})
        return frame
