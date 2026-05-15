import logging

from backend.modules.policies.base import BasePolicy
from backend.components.task_artifact import TaskArtifact

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


def _format_brainstorm(parsed:dict) -> str:
    """Skill returns JSON in two shapes (topic mode / highlight mode). Render either as readable prose so RES doesn't ship raw JSON to the user."""
    mode = parsed.get('mode')
    if mode == 'topic':
        topic = parsed.get('topic', '')
        ideas = parsed.get('ideas') or []
        header = f'Angles for "{topic}":' if topic else 'Angles:'
        lines = [header]
        for idea in ideas:
            title, hook = idea.get('title', ''), idea.get('hook', '')
            lines.append(f'- {title}: {hook}' if title and hook else f'- {title or hook}')
        return '\n'.join(lines)
    if mode == 'highlight':
        original = parsed.get('original', '')
        alts = parsed.get('alternatives') or []
        header = f'Alternatives for "{original}":' if original else 'Alternatives:'
        return '\n'.join([header] + [f'- {alt}' for alt in alts])
    return ''


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

    def __init__(self, components):
        super().__init__(components)
        self.flow_stack = components['flow_stack']
        self.content = components['content_service']

    def execute(self, state, context, tools):
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
            self.ambiguity.declare('partial', metadata={'missing': 'source', 'entity': 'post'})
            return TaskArtifact()

        depth_slot = flow.slots['depth']
        depth = int(depth_slot.level) if depth_slot.check_if_filled() else 2

        if flow.slots['sections'].check_if_filled():
            flow.stage = 'direct'
            post_id = state.active_post

            self.record_snapshot(self.content, flow, context, post_id)
            text, tool_log = self.llm_execute(flow, state, context, tools,
                extra_resolved={'depth': depth})
            saved, _ = self.engineer.tool_succeeded(tool_log, 'generate_outline')

            if not text or not saved:
                artifact = self.error_artifact(flow, 'failed_to_save',
                    thoughts='LLM failed to generate outline.')
            else:
                for step in flow.slots['sections'].steps:
                    flow.slots['sections'].mark_as_complete(step['name'])
                flow.status = 'Completed'
                artifact = TaskArtifact(origin='outline', thoughts=text)
                artifact.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})

        elif flow.slots['topic'].check_if_filled():
            flow.stage = 'discovery'
            artifact = self._propose_outline(flow, state, context, tools, depth=depth)

        else:
            convo_history = context.compile_history(look_back=3)
            prompt = f'{convo_history}\n\nExtract the topic the user wants to outline for the blog post or note. Reply with JSON: {{"topic": "..."}}.'
            parsed = self.engineer.apply_guardrails(self.engineer(prompt, 'fill_slots'))
            flow.fill_slots_by_label({'topic': parsed and parsed.get('topic')})

            if flow.slots['topic'].filled:
                flow.stage = 'discovery'
                artifact = self._propose_outline(flow, state, context, tools)
            else:
                self.ambiguity.declare('specific', metadata={'missing': 'topic'})
                artifact = TaskArtifact(flow.name())

        return artifact

    def _propose_outline(self, flow, state, context, tools, depth:int=2):
        post_id = state.active_post
        # Defensive guard: Remove persistence tools from the skill's tool registry for Propose mode.
        # Also pass propose_mode=True in the resolved-context hint so the skill knows to stay text-only.
        artifact = TaskArtifact(origin='outline')

        raw, tool_log = self.llm_execute(flow, state, context, tools,
            extra_resolved={'depth': depth, 'propose_mode': True},
            exclude_tools=('generate_outline',))
        candidates = self.engineer.apply_guardrails(raw, format='markdown', shape='candidates')
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
                self.ambiguity.declare('partial', metadata={'missing': 'source', 'entity': 'post'})
            elif not flow.slots['feedback'].filled or not flow.slots['steps'].filled:
                self.ambiguity.declare('specific', metadata={'missing': 'refine_details'})
            return TaskArtifact(flow.name())

        post_id, _, error = self.resolve_source_ids(flow, state, tools)
        if error: return error
        result = tools('read_metadata', {'post_id': post_id, 'include_outline': True})
        content = result['outline']

        # Stack-on: if the outline has no bullets yet, outline first so refine has something to
        # operate on.
        if _count_bullets(content) == 0:
            self.flow_stack.stackon('outline')
            state.keep_going = True
            return TaskArtifact(thoughts='No bullets in the outline yet, outlining first.')

        self.record_snapshot(self.content, flow, context, post_id)
        text, tool_log = self.llm_execute(flow, state, context, tools,
            extra_resolved={'current_outline': content})
        revised, _ = self.engineer.tool_succeeded(tool_log, 'revise_content')
        inserted, _ = self.engineer.tool_succeeded(tool_log, 'insert_section')
        renamed, _ = self.engineer.tool_succeeded(tool_log, 'update_post')
        removed, _ = self.engineer.tool_succeeded(tool_log, 'remove_content')
        saved = revised or inserted or renamed or removed

        if not text or not saved:
            return TaskArtifact(
                origin=flow.name(),
                parts={'violation': 'failed_to_save'},
                thoughts='The refine skill did not save any changes (revise_content, insert_section, update_post rename, or remove_content).',
            )

        # Contract backstop: the skill must preserve existing bullets. If the post-save outline
        # is strictly shorter AND the user did not request removal, the skill violated the contract.
        prior_bullets = _count_bullets(content)
        new_result = tools('read_metadata', {'post_id': post_id, 'include_outline': True})
        new_outline = new_result['outline']
        new_bullets = _count_bullets(new_outline)
        if new_bullets < prior_bullets and not _has_removal_intent(flow):
            thoughts = f'Outline shrunk from {prior_bullets} bullets to {new_bullets} without an explicit removal directive.'
            return TaskArtifact(
                origin=flow.name(),
                parts={
                    'violation': 'failed_to_save',
                    'prior_bullets': prior_bullets,
                    'new_bullets': new_bullets,
                },
                thoughts=thoughts,
            )

        flow.status = 'Completed'
        artifact = TaskArtifact(origin='refine', thoughts=text)
        artifact.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        return artifact

    def cite_policy(self, flow, state, context, tools):
        target_slot = flow.slots['target']
        url_slot = flow.slots['url']
        if not target_slot.check_if_filled() and not url_slot.check_if_filled():
            self.ambiguity.declare('specific', metadata={'missing': 'target'})
            return TaskArtifact()

        if state.active_post:
            sec_id = target_slot.values[0].get('sec') if target_slot.check_if_filled() else None
            self.record_snapshot(self.content, flow, context, state.active_post,
                sec_ids=[sec_id] if sec_id else None)

        text, tool_log = self.llm_execute(flow, state, context, tools)
        flow.status = 'Completed'
        return TaskArtifact(origin='cite', thoughts=text)

    def compose_policy(self, flow, state, context, tools):
        grounding = flow.slots[flow.entity_slot]
        if not grounding.check_if_filled():
            self.ambiguity.declare('specific', metadata={'missing': flow.entity_slot})
            return TaskArtifact()

        # Stack-on: compose needs an outline only when the post has no structure yet.
        post_id, _, error = self.resolve_source_ids(flow, state, tools)
        if error: return error
        result = tools('read_metadata', {'post_id': post_id})
        if result['_success'] and not result.get('section_ids'):
            self.flow_stack.stackon('outline')
            state.keep_going = True
            return TaskArtifact(thoughts='No sections yet, outlining first.')

        # Preload title + section preview into resolved-entities so the skill plans without re-fetching.
        # Skill owns persistence (calls revise_content per section); the post-read below refreshes the card.
        self.record_snapshot(self.content, flow, context, post_id)
        text, tool_log = self.llm_execute(flow, state, context, tools, include_preview=True)
        flow.status = 'Completed'
        artifact = TaskArtifact(origin='compose', thoughts=text)
        artifact.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        return artifact

    def add_policy(self, flow, state, context, tools):
        grounding = flow.slots[flow.entity_slot]
        if not grounding.check_if_filled():
            self.ambiguity.declare('specific', metadata={'missing': flow.entity_slot})
            return TaskArtifact(flow.name())

        post_id, _, error = self.resolve_source_ids(flow, state, tools)
        if error: return error
        self.record_snapshot(self.content, flow, context, post_id)
        text, tool_log = self.llm_execute(flow, state, context, tools)
        flow.status = 'Completed'
        artifact = TaskArtifact(origin='add', thoughts=text)
        artifact.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        return artifact

    def create_policy(self, flow, state, context, tools):
        if not flow.is_filled():
            if not flow.slots['title'].filled:
                self.ambiguity.declare('specific', metadata={'missing': 'title'})
            elif not flow.slots['type'].filled:
                self.ambiguity.declare('specific', metadata={'missing': 'type'})
            else:
                self.ambiguity.declare('partial', metadata={'missing': 'source'})
            return TaskArtifact(flow.name())

        slots = flow.slot_values_dict()
        create_params = { 'title': slots['title'], 'type': slots['type'] }
        if 'topic' in slots:
            create_params['topic'] = slots['topic']
        result = tools('create_post', create_params)

        if result['_success']:
            new_id = result['post_id']
            state.active_post = new_id
            flow.status = 'Completed'
            artifact = TaskArtifact(origin='create')
            block_data = {'post_id': new_id, 'title': result['title'], 'status': result['status']}
            artifact.add_block({'type': 'card', 'data': block_data, 'expand': True})
            # If topic provided, chain into OutlineFlow to propose an initial outline.
            # if 'topic' in slots:
            #     self.flow_stack.stackon('outline')
            #     state.keep_going = True
            #     outline_flow = self.flow_stack.get_flow()
            #     outline_flow.slots['source'].add_one(post=new_id)
            #     outline_flow.slots['topic'].add_one(slots['topic'])
            #     artifact.thoughts = 'Created the post, moving on to outline.'

        elif result.get('_error') == 'duplicate':
            observation = f'A post titled "{slots["title"]}" already exists. Overwrite it, or pick a different title?'
            self.ambiguity.declare('confirmation', metadata={
                'missing': 'overwrite_intent', 'question': observation,
                'duplicate_title': slots['title'],
            })
            artifact = TaskArtifact(flow.name(), parts={'duplicate_title': slots['title']})
        else:
            frame_meta = {'violation': 'tool_error', 'failed_tool': 'create_post'}
            reason = result.get('_message', 'unknown error')
            message = f"Could not create {slots['type']} _{slots['title']}_: {reason}."
            artifact = TaskArtifact(origin='create', parts=frame_meta, thoughts=message)
        return artifact

    def brainstorm_policy(self, flow, state, context, tools):
        if flow.slots['topic'].check_if_filled():
            text, _ = self.llm_execute(flow, state, context, tools)
        elif flow.slots['source'].check_if_filled():
            entity = flow.slots['source'].values[0]
            post_title = tools('read_metadata', {'post_id': entity['post']})['title']
            flow.slots['topic'].add_one(post_title) # use the title as a pseudo-topic
            text, _ = self.llm_execute(flow, state, context, tools)
        else:
            convo_history = context.compile_history(look_back=3)
            prompt = f'{convo_history}\n\nExtract the topic the user wants to brainstorm about. Reply with JSON: {{"topic": "..."}}.'
            raw_output = self.engineer(prompt, 'fill_slots')
            parsed = self.engineer.apply_guardrails(raw_output)
            flow.fill_slots_by_label({'topic': parsed and parsed.get('topic')})
            if not flow.slots['topic'].filled:
                self.ambiguity.declare('specific', metadata={'missing': 'topic'})
                return TaskArtifact(flow.name())
            else:
                text, _ = self.llm_execute(flow, state, context, tools)

        flow.status = 'Completed'
        parsed = self.engineer.apply_guardrails(text)
        thoughts = _format_brainstorm(parsed) if isinstance(parsed, dict) else text
        return TaskArtifact(origin='brainstorm', thoughts=thoughts)
