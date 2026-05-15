from backend.components.task_artifact import TaskArtifact
from backend.prompts.pex.support.converse_prompts import (
    REFERENCE_LOOKUP_SCHEMA, build_reference_prompt,
)


class InternalPolicy:

    def __init__(self, components):
        self.memory = components['memory']
        self.config = components['config']
        self.flow_stack = components['flow_stack']
        self.engineer = components['engineer']

    def execute(self, state, context, tools):
        flow = self.flow_stack.get_flow()

        match flow.name():
            case 'recap': return self.recap_policy(flow, tools)
            case 'remember': return self.remember_policy(flow, tools)
            case 'recall': return self.recall_policy(flow, tools)
            case 'store': return self.store_policy(flow, tools)
            case 'retrieve': return self.retrieve_policy(flow, tools)
            case 'search': return self.search_policy(flow, tools)
            case 'reference': return self.reference_policy(flow, tools)
            case 'study': return self.study_policy(flow, tools)
            case _: return TaskArtifact(self.config)

    def recap_policy(self, flow, tools):
        topic = flow.slots['topic']
        if topic.check_if_filled():
            query = topic.to_dict()
            val = self.memory.read_scratchpad(query)
            if val:
                self.memory.write_scratchpad(f'recap:{query}', val)
        flow.status = 'Completed'
        return TaskArtifact(flow.name())

    def remember_policy(self, flow, tools):
        flow.status = 'Completed'
        return TaskArtifact(flow.name())

    def recall_policy(self, flow, tools):
        target = flow.slots['target']
        if target.check_if_filled():
            key = target.values[0].get('snip', '')
            val = self.memory.read_preference(key)
            if val:
                self.memory.write_scratchpad(f'recall:{key}', str(val))
        flow.status = 'Completed'
        return TaskArtifact(flow.name())

    def store_policy(self, flow, tools):
        target = flow.slots['target']
        if target.check_if_filled():
            origin_slot = flow.slots['origin']
            origin = origin_slot.value if origin_slot.check_if_filled() else flow.flow_type
            for snippet in target.values:
                self.memory.write_scratchpad(origin, snippet)
        flow.status = 'Completed'
        return TaskArtifact(flow.name())

    def retrieve_policy(self, flow, tools):
        result = tools('manage_memory', {'action': 'read_scratchpad'})
        if result['_success']:
            payload = result.get('scratchpad', result.get('result', ''))
            self.memory.write_scratchpad('retrieve:last', str(payload))
        flow.status = 'Completed'
        return TaskArtifact(flow.name())

    def search_policy(self, flow, tools):
        query_slot = flow.slots['query']
        if query_slot.check_if_filled():
            query = str(query_slot.to_dict())
        else:
            query = self.memory.read_scratchpad('search:query')

        if not query:
            flow.status = 'Completed'
            return TaskArtifact(flow.name())

        result = tools('search_faqs', {'query': query, 'top_k': 3})

        if result['_success'] and result['matches']:
            top = result['matches'][0]
            summary = f"Top FAQ match for '{query}': {top['question']} — {top['answer']}"
            self.memory.write_scratchpad('search', {'query': query,
                'matches': result['matches'], 'summary': summary})
        else:
            self.memory.write_scratchpad('search', {'query': query, 'matches': [],
                'summary': f"No FAQ match found for '{query}'."})

        flow.status = 'Completed'
        return TaskArtifact(flow.name())

    def reference_policy(self, flow, tools):
        target_slot = flow.slots['target']
        if target_slot.check_if_filled():
            word = target_slot.values[0].get('word', '').strip()
        else:
            word = self.memory.read_scratchpad('reference:word').strip()

        if not word:
            flow.status = 'Completed'
            return TaskArtifact(flow.name())

        prompt = build_reference_prompt(word)
        entry = self.engineer(prompt, task='skill', schema=REFERENCE_LOOKUP_SCHEMA)

        if entry['definition']:
            summary = f"'{entry['word']}' — {entry['definition']}"
            if entry['synonyms']:
                summary += f" Synonyms: {', '.join(entry['synonyms'][:5])}."
        else:
            summary = f"No standard reference entry found for '{word}'."

        self.memory.write_scratchpad('reference', {**entry, 'summary': summary})
        flow.status = 'Completed'
        return TaskArtifact(flow.name())

    def study_policy(self, flow, tools):
        source = flow.slots['source']
        post_id = source.values[0]['post'] if source.check_if_filled() else ''
        result = tools('read_metadata', {'post_id': post_id, 'include_outline': True})
        if result['_success']:
            self.memory.write_scratchpad(
                f'post:{post_id}',
                f'{result["title"]}: {result["outline"][:500]}',
            )
        flow.status = 'Completed'
        return TaskArtifact(flow.name())
