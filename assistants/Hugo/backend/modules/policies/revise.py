from __future__ import annotations

from typing import TYPE_CHECKING

from backend.modules.policies.base import BasePolicy

if TYPE_CHECKING:
    from backend.components.dialogue_state import DialogueState
    from backend.components.context_coordinator import ContextCoordinator
    from backend.components.display_frame import DisplayFrame
    from backend.components.flow_stack.parents import BaseFlow


class RevisePolicy(BasePolicy):

    def execute(self, flow: 'BaseFlow', state: 'DialogueState',
                context: 'ContextCoordinator', tools) -> 'DisplayFrame':
        match flow.name():
            case 'rework': return self.rework_policy(flow, state, context, tools)
            case 'polish': return self.polish_policy(flow, state, context, tools)
            case 'tone': return self.tone_policy(flow, state, context, tools)
            case 'audit': return self.audit_policy(flow, state, context, tools)
            case 'format': return self.format_policy(flow, state, context, tools)
            case 'amend': return self.amend_policy(flow, state, context, tools)
            case 'remove': return self.remove_policy(flow, state, context, tools)
            case 'tidy': return self.tidy_policy(flow, state, context, tools)
            case _:
                return self.build_frame('default', {'content': ''})

    def _require_source(self, flow, state, context):
        """Check source slot, attempt to fill from context. Returns frame if missing."""
        if not flow.slots.get('source', None) or not flow.slots['source'].filled:
            identifier = self.extract_source(flow, state)
            if identifier:
                flow.fill_slots_by_label({'source': identifier})
            if not flow.slots.get('source') or not flow.slots['source'].filled:
                self.ambiguity.declare('specific', metadata={'missing_slot': 'source'})
                return self.build_frame('default', {'content': self.ambiguity.ask()})
        return None

    def rework_policy(self, flow, state, context, tools):
        missing = self._require_source(flow, state, context)
        if missing:
            return missing

        text, tool_log = self.llm_execute(flow, state, context, tools)
        block_data = self.build_block_data(flow, text, tool_log)
        return self.build_frame('card', block_data, source='rework')

    def polish_policy(self, flow, state, context, tools):
        missing = self._require_source(flow, state, context)
        if missing:
            return missing

        text, tool_log = self.llm_execute(flow, state, context, tools)
        block_data = self.build_block_data(flow, text, tool_log)
        return self.build_frame('card', block_data, source='polish')

    def tone_policy(self, flow, state, context, tools):
        missing = self._require_source(flow, state, context)
        if missing:
            return missing

        # Tone — at least one elective needed (chosen_tone or custom_tone)
        chosen = flow.slots.get('chosen_tone')
        custom = flow.slots.get('custom_tone')
        if (not chosen or not chosen.filled) and (not custom or not custom.filled):
            pref = self.memory.read_preference('tone')
            if pref:
                flow.fill_slot_values({'chosen_tone': pref})
            else:
                flow.fill_slot_values({'chosen_tone': 'natural'})

        text, tool_log = self.llm_execute(flow, state, context, tools)
        block_data = self.build_block_data(flow, text, tool_log)
        frame = self.build_frame('card', block_data, source='tone')

        if state.has_plan:
            self.memory.write_scratchpad(f'flow:{flow.name()}', f'tone: {text[:200]}')
        return frame

    def audit_policy(self, flow, state, context, tools):
        missing = self._require_source(flow, state, context)
        if missing:
            return missing

        text, tool_log = self.llm_execute(flow, state, context, tools)
        block_data = self.build_block_data(flow, text, tool_log)
        return self.build_frame('card', block_data, source='audit')

    def format_policy(self, flow, state, context, tools):
        missing = self._require_source(flow, state, context)
        if missing:
            return missing

        if not flow.slots.get('format', None) or not flow.slots['format'].filled:
            self.ambiguity.declare('specific', metadata={'missing_slot': 'format'})
            return self.build_frame('default', {'content': self.ambiguity.ask()})

        text, tool_log = self.llm_execute(flow, state, context, tools)
        block_data = self.build_block_data(flow, text, tool_log)
        return self.build_frame('card', block_data, source='format')

    def amend_policy(self, flow, state, context, tools):
        if not flow.slots.get('feedback', None) or not flow.slots['feedback'].filled:
            convo_history = context.compile_history(look_back=3)
            text = self.engineer.call(convo_history, system="Extract the user's feedback or revision notes.")
            flow.fill_slots_by_label({'feedback': self._parse_value(text)})
            if not flow.slots['feedback'].filled:
                self.ambiguity.declare('specific', metadata={'missing_slot': 'feedback'})
                return self.build_frame('default', {'content': self.ambiguity.ask()})

        missing = self._require_source(flow, state, context)
        if missing:
            return missing

        text, tool_log = self.llm_execute(flow, state, context, tools)
        block_data = self.build_block_data(flow, text, tool_log)
        return self.build_frame('card', block_data, source='amend')

    def remove_policy(self, flow, state, context, tools):
        missing = self._require_source(flow, state, context)
        if missing:
            return missing

        if not flow.slots.get('type', None) or not flow.slots['type'].filled:
            self.ambiguity.declare('specific', metadata={'missing_slot': 'type'})
            return self.build_frame('default', {'content': self.ambiguity.ask()})

        text, tool_log = self.llm_execute(flow, state, context, tools)
        block_data = self.build_block_data(flow, text, tool_log)
        return self.build_frame('card', block_data, source='remove')

    def tidy_policy(self, flow, state, context, tools):
        missing = self._require_source(flow, state, context)
        if missing:
            return missing

        identifier = self.extract_source(flow, state)
        post_id = self.resolve_post_id(identifier, tools) if identifier else None
        if post_id:
            result = tools('post_get', {'post_id': post_id})
        else:
            result = {'status': 'error'}

        if result.get('status') == 'success':
            post = result['result']
            content = post.get('content', '')

            settings_slot = flow.slots.get('settings')
            settings = settings_slot.to_dict() if settings_slot and settings_slot.filled else {}

            convo_history = context.compile_history()
            history_with_data = (
                f"{convo_history}\n\n[Post content]\nTitle: {post.get('title', '')}\n"
                f"Content ({len(content)} chars): {content[:500]}\n\n"
                f"[Settings] {settings if settings else 'default normalization'}"
            )

            skill_prompt = self._load_skill_template(flow.name())
            messages = self.engineer.build_skill_prompt(flow, history_with_data, self.memory.read_scratchpad(), skill_prompt)
            text = self.engineer.call(messages, max_tokens=4096)

            return self.build_frame('card', {
                'post_id': post.get('post_id', ''),
                'title': post.get('title', ''),
                'content': text,
            }, source='tidy')
        else:
            return self.build_frame('default', {
                'content': f'Could not find post "{identifier}".',
            })
