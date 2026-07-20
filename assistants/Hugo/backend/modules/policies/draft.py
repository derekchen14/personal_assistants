import logging

from backend.modules.policies.base import BasePolicy
from backend.components.task_artifact import TaskArtifact

log = logging.getLogger(__name__)

def _count_bullets(outline:str) -> int:
    if not outline:
        return 0
    total = 0
    for line in outline.split('\n'):
        stripped = line.strip()
        if stripped.startswith('- ') or stripped.startswith('* '):
            total += 1
    return total


_BRAINSTORM_TOPIC_SCHEMA = {
    'type': 'object',
    'properties': {
        'topic': {'type': 'string'},
        'ideas': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {'title': {'type': 'string'}, 'hook': {'type': 'string'}},
                'required': ['title', 'hook'],
            },
        },
    },
    'required': ['topic', 'ideas'],
}

_BRAINSTORM_SNIPPET_SCHEMA = {
    'type': 'object',
    'properties': {
        'original': {'type': 'string'},
        'alternatives': {'type': 'array', 'items': {'type': 'string'}},
    },
    'required': ['original', 'alternatives'],
}


def _format_brainstorm(parsed:dict) -> str:
    """Skill returns JSON in two shapes (topic ideas / snippet alternatives). Dispatch on the
    presence of `ideas` vs `alternatives` so the agent ships readable prose, not raw JSON."""
    if 'ideas' in parsed:
        topic = parsed.get('topic', '')
        header = f'Angles for "{topic}":' if topic else 'Angles:'
        lines = [header]
        for idea in parsed['ideas'] or []:
            title, hook = idea.get('title', ''), idea.get('hook', '')
            lines.append(f'- {title}: {hook}' if title and hook else f'- {title or hook}')
        return '\n'.join(lines)
    if 'alternatives' in parsed:
        original = parsed.get('original', '')
        header = f'Alternatives for "{original}":' if original else 'Alternatives:'
        return '\n'.join([header] + [f'- {alt}' for alt in parsed['alternatives'] or []])
    return ''

class DraftPolicy(BasePolicy):

    def __init__(self, components):
        super().__init__(components)
        self.flow_stack = components['flow_stack']
        self.content = components['content_service']

    def execute(self, state, context, tools):
        flow = self.flow_stack.get_flow()

        match flow.name():
            case 'outline': return self.outline_policy(flow, state, context, tools)
            case 'compose': return self.compose_policy(flow, state, context, tools)
            case 'refine': return self.refine_policy(flow, state, context, tools)
            case 'brainstorm': return self.brainstorm_policy(flow, state, context, tools)
            case _: raise ValueError(f"Unknown flow name: {flow.name()}")

    def outline_policy(self, flow, state, context, tools):
        depth_slot = flow.slots['depth']
        depth = int(depth_slot.level) if depth_slot.check_if_filled() else 2

        if not flow.slots['source'].check_if_filled() and not flow.slots['topic'].check_if_filled():
            convo_history = context.compile_history(look_back=3)
            prompt = f'{convo_history}\n\nExtract the topic the user wants to outline for the blog post or note. Reply with JSON: {{"topic": "..."}}.'
            parsed = self.engineer.parse(self.engineer(prompt, task='fill_slots'))
            flow.fill_slots_by_label({'topic': parsed and parsed.get('topic')})

        if not flow.slots['source'].check_if_filled() and not flow.slots['topic'].check_if_filled():
            self.ambiguity.recognize('partial', metadata={'missing': 'source', 'entity': 'post'})
            return TaskArtifact(flow.name())

        post_id, title, error = self._outline_post(flow, state, tools)
        if error:
            return error

        flow.stage = 'direct'
        self.record_snapshot(self.content, flow, context, post_id)
        text, tool_log = self.llm_execute(flow, state, context, tools,
            extra_resolved={'depth': depth, 'topic': title})
        saved, _ = self.engineer.tool_succeeded(tool_log, 'generate_outline')
        if not saved:                       # the generate is flaky — one retry before giving up
            text, tool_log = self.llm_execute(flow, state, context, tools,
                extra_resolved={'depth': depth, 'topic': title})
            saved, _ = self.engineer.tool_succeeded(tool_log, 'generate_outline')

        if not text or not saved:
            failed = next((entry['result'] for entry in tool_log
                if entry['tool'] == 'generate_outline' and not entry['result']['_success']), None)
            thoughts = failed['_message'] if failed else 'Sub-agent did not call generate_outline.'
            artifact = self.error_artifact(flow, 'failed_to_save', thoughts=thoughts, code=text)
        else:
            for step in flow.slots['sections'].steps:
                flow.slots['sections'].mark_as_complete(step['name'])
            self.complete_flow(flow, state, context, f'Generated and saved a depth-{depth} outline.',
                metadata={'post_id': post_id, 'title': title})
            artifact = TaskArtifact(origin='outline', thoughts=text)
            artifact.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})

        return artifact

    def _outline_post(self, flow, state, tools):
        """Return (post_id, title, error_artifact), creating a draft when outline starts a new post."""
        source_slot = flow.slots['source']
        topic_slot = flow.slots['topic']
        reference = ''
        if source_slot.values:
            reference = next((ent.get('post', '') for ent in source_slot.values if ent.get('post')), '')
        title = topic_slot.to_dict() if topic_slot.check_if_filled() else reference
        post_id = self._resolve_post_id(reference, tools) if reference else None
        verified = bool(source_slot.values and source_slot.values[0].get('ver'))
        post_id, verified = self.verify_grounding(post_id, reference, state, tools, verified)
        if not post_id:
            if not title:
                return None, '', self.error_artifact(flow, 'missing_reference',
                    thoughts='No post or topic was available for the outline.', missing_entity='post')
            created = tools('create_post', {'title': title})
            if not created['_success']:
                return None, title, self.toast_error(flow, 'tool_error',
                    created.get('_message', 'Could not create a draft for the outline.'))
            post_id = created['post_id']
            title = created.get('title') or title
            verified = True  # create_post returned this exact id for the user's new draft
        else:
            meta = tools('read_metadata', {'post_id': post_id})
            title = meta.get('title', title) if meta.get('_success') else title
        state.set_active_entity(post=post_id, sec='', ver=verified)
        if source_slot.values:
            source_slot.values[0]['post'] = post_id
            source_slot.values[0]['ver'] = verified
            source_slot._rebuild_keys()
            source_slot.check_if_filled()
        else:
            source_slot.add_one(post=post_id, ver=verified)
        return post_id, title, None

    def _propose_outline(self, flow, state, context, tools, depth:int=2):
        # Defensive guard: Remove persistence tools from the skill's tool inventory for Propose mode.
        # Also pass propose_mode=True in the resolved-context hint so the skill knows to stay text-only.
        artifact = TaskArtifact(origin='outline')

        raw, tool_log = self.llm_execute(flow, state, context, tools,
            extra_resolved={'depth': depth, 'propose_mode': True},
            exclude_tools=('generate_outline',))
        candidates = self.engineer.parse(raw, format='markdown', shape='candidates')
        flow.slots['proposals'].options = candidates

        if candidates:
            options = [{
                'label': f'Option {idx + 1}',
                'dax': '{002}',
                'payload': {'proposals': [cand]},
                'body': '\n\n'.join(f"**{sec['name']}**\n\n{sec.get('description', '')}" for sec in cand),
            } for idx, cand in enumerate(candidates)]
            artifact.add_block({'type': 'selection', 'data': {
                'title': 'Outline options',
                'options': options,
            }})
        return artifact

    def refine_policy(self, flow, state, context, tools):
        if not flow.is_filled():
            if not flow.slots['source'].filled:
                self.ambiguity.recognize('partial', metadata={'missing': 'source', 'entity': 'post'})
            elif not flow.slots['feedback'].filled or not flow.slots['steps'].filled:
                self.ambiguity.recognize('specific', metadata={'missing': 'refine_details'})
            return TaskArtifact(flow.name())

        post_id, _, error = self.resolve_source_ids(flow, state, tools)
        if error: return error
        result = tools('read_metadata', {'post_id': post_id, 'include_outline': True})
        content = result['outline']

        # Stack-on: if the outline has no bullets yet, outline first so refine has something to
        # operate on.
        if _count_bullets(content) == 0:
            self.flow_stack.stackon('outline')
            return TaskArtifact(thoughts='No bullets in the outline yet, outlining first.')

        self.record_snapshot(self.content, flow, context, post_id)
        text, tool_log = self.llm_execute(flow, state, context, tools,
            extra_resolved={'current_outline': content})
        revised, _ = self.engineer.tool_succeeded(tool_log, 'revise_content')
        inserted, _ = self.engineer.tool_succeeded(tool_log, 'insert_section')
        restructured, _ = self.engineer.tool_succeeded(tool_log, 'update_post')
        removed, _ = self.engineer.tool_succeeded(tool_log, 'remove_content')
        saved = revised or inserted or restructured or removed

        if not text or not saved:
            return TaskArtifact(
                origin=flow.name(),
                parts={'violation': 'failed_to_save'},
                thoughts='The refine skill did not save any changes (revise_content, insert_section, update_post, or remove_content).',
            )

        self.complete_flow(flow, state, context, 'Refined the outline per the requested changes.',
            metadata={'post_id': post_id})
        artifact = TaskArtifact(origin='refine', thoughts=text)
        artifact.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        return artifact

    def compose_policy(self, flow, state, context, tools):
        if not flow.slots['source'].check_if_filled():
            self.ambiguity.recognize('partial', metadata={'missing': 'source', 'entity': 'post'})
            return TaskArtifact()
        post_id, _, error = self.resolve_source_ids(flow, state, tools)
        if error: return error

        # Compose converts an existing outline into prose; if there are no bullets yet,
        # outline first so there's something to write from.
        result = tools('read_metadata', {'post_id': post_id, 'include_outline': True})
        if _count_bullets(result['outline']) == 0:
            self.flow_stack.stackon('outline')
            return TaskArtifact(thoughts='No outline to compose from yet — outlining first.')

        self.record_snapshot(self.content, flow, context, post_id)
        text, tool_log = self.llm_execute(flow, state, context, tools, include_preview=True)
        saved, _ = self.engineer.tool_succeeded(tool_log, 'revise_content')
        if not text or not saved:
            return self.error_artifact(flow, 'failed_to_save',
                thoughts='Compose did not persist prose (revise_content not called or failed).', code=text)

        self.complete_flow(flow, state, context, 'Composed prose for the requested section(s).',
            metadata={'post_id': post_id})
        artifact = TaskArtifact(origin='compose', thoughts=text)
        artifact.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        return artifact

    def brainstorm_policy(self, flow, state, context, tools):
        snippet = ''
        if flow.slots['source'].check_if_filled():
            snippet = (flow.slots['source'].values[0] or {}).get('snip') or ''
        schema = _BRAINSTORM_SNIPPET_SCHEMA if snippet else _BRAINSTORM_TOPIC_SCHEMA

        if flow.slots['topic'].check_if_filled():
            text, _ = self.llm_execute(flow, state, context, tools, tier='high', schema=schema)
        elif flow.slots['source'].check_if_filled():
            post_id, _, error = self.resolve_source_ids(flow, state, tools)
            if error: return error
            post_title = tools('read_metadata', {'post_id': post_id})['title']
            flow.slots['topic'].add_one(post_title) # use the title as a pseudo-topic
            text, _ = self.llm_execute(flow, state, context, tools, tier='high', schema=schema)
        else:
            convo_history = context.compile_history(look_back=3)
            prompt = f'{convo_history}\n\nExtract the topic the user wants to brainstorm about. Reply with JSON: {{"topic": "..."}}.'
            raw_output = self.engineer(prompt, task='fill_slots')
            parsed = self.engineer.parse(raw_output)
            flow.fill_slots_by_label({'topic': parsed and parsed.get('topic')})
            if not flow.slots['topic'].filled:
                self.ambiguity.recognize('specific', metadata={'missing': 'topic'})
                return TaskArtifact(flow.name())
            else:
                text, _ = self.llm_execute(flow, state, context, tools, tier='high', schema=schema)

        self.complete_flow(flow, state, context, f'Brainstormed ideas on "{flow.slots["topic"].term}".')
        parsed = self.engineer.parse(text)
        thoughts = _format_brainstorm(parsed) if isinstance(parsed, dict) else text
        return TaskArtifact(origin='brainstorm', thoughts=thoughts)
