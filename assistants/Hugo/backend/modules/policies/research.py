from backend.modules.policies.base import BasePolicy
from backend.components.task_artifact import TaskArtifact


class ResearchPolicy(BasePolicy):

    def __init__(self, components):
        super().__init__(components)
        self.flow_stack = components['flow_stack']

    def execute(self, state, context, tools):
        flow = self.flow_stack.get_flow()

        match flow.name():
            case 'browse': return self.browse_policy(flow, state, context, tools)
            case 'summarize': return self.summarize_policy(flow, state, context, tools)
            case 'find': return self.find_policy(flow, state, context, tools)
            case 'compare': return self.compare_policy(flow, state, context, tools)
            case _:
                return TaskArtifact()

    def browse_policy(self, flow, state, context, tools):
        query_slot = flow.slots['query']
        if not query_slot.check_if_filled():
            self.ambiguity.recognize('partial', metadata={'missing': 'query'})
            return TaskArtifact(flow.name())

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
        text = self.engineer.flow_reply(flow, history_with_data, self.scratchpad.read())

        self.complete_flow(flow, state, context, summary, metadata={'tags': tags, 'target': target})
        artifact = TaskArtifact(flow.name(), thoughts=text)
        artifact.add_block({'type': 'list', 'data': {'items': items}})
        return artifact

    def summarize_policy(self, flow, state, context, tools):
        if artifact := self._guard_entity(flow): return artifact
        post_id, _, error = self.resolve_source_ids(flow, state, tools)
        if error: return error

        flow_metadata = tools('read_metadata', {'post_id': post_id, 'include_outline': True})
        if not flow_metadata['_success']:
            artifact = self.error_artifact(flow, 'missing_reference',
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
            flow_prompt = self.engineer.load_flow_prompt(flow.name()) + length_hint
            summary = self.engineer.flow_reply(
                flow, history_with_data, self.scratchpad.read(),
                flow_prompt=flow_prompt,
            )
            self.complete_flow(flow, state, context, f"Summarized '{flow_metadata['title']}'.",
                metadata={'post_id': post_id})
            artifact = TaskArtifact(flow.name(), thoughts=summary)
        return artifact

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

        # Scratchpad write — downstream audit can reference matches.
        self.scratchpad.append_entry(flow.name(), {
            'version': 1,
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

        found = f"Found {len(items)} post(s) matching '{query}'." if query else f'Listed {len(items)} post(s).'
        self.complete_flow(flow, state, context, found, metadata={'query': query})
        artifact = TaskArtifact(flow.name())
        artifact.add_block({'type': 'list', 'data': list_data, 'expand': True})
        return artifact

    def _expand_query(self, query:str) -> list[str]:
        """LLM-generate 3-4 semantically similar search terms, then always append the query's
        deterministic sub-phrases (split on or/and/commas) and their head nouns. find_posts is
        a verbatim substring match, so a multi-clause request ('X or Y') only ever matches a
        post containing the full phrase — recall must not hinge on the LLM's term luck."""
        import json
        import re
        prompt = (
            f'Return 3-4 short search terms that are semantically similar or related to "{query}". '
            'Include the original term. Reply with ONLY a JSON array of strings, no explanation.'
        )
        terms = []
        try:
            raw_output = self.engineer(prompt, max_tokens=128)
            cleaned = raw_output.strip().strip('`').removeprefix('json').strip()
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                terms = [str(term) for term in parsed[:4]]
        except Exception:
            pass
        for part in re.split(r'\s+or\s+|\s+and\s+|,', query):
            part = part.strip()
            if not part:
                continue
            head = part.split()[-1]
            for sub_term in (part, head) if len(head) >= 5 else (part,):
                if sub_term not in terms:
                    terms.append(sub_term)
        return terms or [query]

    def compare_policy(self, flow, state, context, tools):
        # Version-diff mode: a single-post comparison across versions, signaled
        # by lookback/mapping. It needs only one grounded post, so it precedes the two-post guard.
        if flow.slots['lookback'].check_if_filled() or flow.slots['mapping'].check_if_filled():
            return self._compare_diff(flow, state, context, tools)

        if artifact := self._guard_entity(flow): return artifact

        # Comparison kind drives both the metrics surfaced and the prose framing.
        # Ask before dispatching when none was named.
        if not flow.slots['category'].check_if_filled():
            self.ambiguity.recognize('specific',
                observation='Should I compare metrics, metadata, or tone?',
                metadata={'missing': 'category'})
            return TaskArtifact(flow.name())

        grounding = flow.slots[flow.entity_slot]
        posts = [self._read_post_content(self._resolve_post_id(e['post'], tools), tools)
                 for e in grounding.values[:2]]
        if not (posts[0] and posts[1]):
            named = [e['post'] for e in grounding.values[:2]]
            return self.error_artifact(flow, 'missing_reference',
                thoughts=f"Could not find one or both posts: {named}.",
                missing_entity='post')

        text, tool_log = self.llm_execute(flow, state, context, tools)

        # Skill may declare ambiguity (e.g. missing category); leave flow Active so the
        # next turn can resolve rather than treating completion as final.
        if self.ambiguity.present:
            return TaskArtifact(flow.name())

        self.complete_flow(flow, state, context, text or 'Compared the two posts.',
            metadata={'post_ids': [posts[0]['post_id'], posts[1]['post_id']]})
        artifact = TaskArtifact(flow.name(), thoughts=text)
        artifact.add_block({'type': 'compare', 'data': {'left': posts[0], 'right': posts[1]}, 'expand': True})
        return artifact

    def _compare_diff(self, flow, state, context, tools):
        """Single-post version diff. Resolves one post (+ section) and
        lets the skill call diff_section against the requested prior version (lookback) or a
        draft-vs-published mapping. Only one grounded post is required, unlike the two-post compare."""
        post_id, _, error = self.resolve_source_ids(flow, state, tools)
        if error: return error
        if not post_id:
            self.ambiguity.recognize('partial', metadata={'missing': 'source', 'entity': 'post'})
            return TaskArtifact(flow.name())
        text, _ = self.llm_execute(flow, state, context, tools)
        if self.ambiguity.present:
            return TaskArtifact(flow.name())
        self.complete_flow(flow, state, context, text or 'Diffed the section against a prior version.',
            metadata={'post_id': post_id})
        return TaskArtifact(flow.name(), thoughts=text)
