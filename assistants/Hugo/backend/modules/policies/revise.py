from __future__ import annotations
from backend.modules.policies.base import BasePolicy
from backend.components.display_frame import DisplayFrame


class RevisePolicy(BasePolicy):

    def __init__(self, components:dict):
        super().__init__(components)
        self.flow_stack = components['flow_stack']

    def execute(self, state, context, tools) -> 'DisplayFrame':
        flow = self.flow_stack.get_active_flow()

        match flow.name():
            case 'rework': return self.rework_policy(flow, state, context, tools)
            case 'polish': return self.polish_policy(flow, state, context, tools)
            case 'tone': return self.tone_policy(flow, state, context, tools)
            case 'audit': return self.audit_policy(flow, state, context, tools)
            case 'simplify': return self.simplify_policy(flow, state, context, tools)
            case 'remove': return self.remove_policy(flow, state, context, tools)
            case 'tidy': return self.tidy_policy(flow, state, context, tools)
            case _:
                frame = self.build_frame('default')
                frame.data = {'content': ''}
                return frame

    def _require_source(self, flow, state, context):
        """Check entity slot is filled. Returns frame if missing."""
        grounding = flow.slots[flow.entity_slot]
        if not grounding.filled:
            self.ambiguity.declare('specific', metadata={'missing_slot': flow.entity_slot})
            frame = self.build_frame('default')
            frame.data = {'content': self.ambiguity.ask()}
            return frame
        return None

    def rework_policy(self, flow, state, context, tools):
        missing = self._require_source(flow, state, context)
        if missing:
            return missing

        post_id, _ = self._resolve_source_ids(flow, state, tools)
        text, tool_log = self.llm_execute(flow, state, context, tools)
        flow.status = 'Completed'
        frame = self.build_frame('card', origin='rework', thoughts=text)
        if post_id:
            frame.data = self._read_post_content(post_id, tools)
        return frame

    def polish_policy(self, flow, state, context, tools):
        missing = self._require_source(flow, state, context)
        if missing:
            return missing

        post_id, sec_id = self._resolve_source_ids(flow, state, tools)
        text, tool_log = self.llm_execute(flow, state, context, tools)

        if post_id and sec_id and text:
            self._persist_section(post_id, sec_id, text, tools)

        # Check for structural issues via tool results
        result = self.extract_tool_result(tool_log, 'inspect_post')
        if result.get('structural_issues'):
            self.flow_stack.fallback('rework')
            state.keep_going = True
            frame = self.build_frame('default')
            frame.data = {'content': 'Structural issues found — switching to rework.'}
            return frame

        flow.status = 'Completed'
        frame = self.build_frame('card', origin='polish', thoughts=text)
        if post_id:
            frame.data = self._read_post_content(post_id, tools)
        return frame

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

        post_id, _ = self._resolve_source_ids(flow, state, tools)
        text, tool_log = self.llm_execute(flow, state, context, tools)
        frame = self.build_frame('card', origin='tone', thoughts=text)
        if post_id:
            frame.data = self._read_post_content(post_id, tools)

        flow.status = 'Completed'
        if state.has_plan:
            self.memory.write_scratchpad(f'flow:{flow.name()}', f'tone: {text[:200]}')
        return frame

    def audit_policy(self, flow, state, context, tools):
        missing = self._require_source(flow, state, context)
        if missing:
            return missing

        # Default reference_count to 5
        ref_slot = flow.slots.get('reference_count')
        if not ref_slot or not ref_slot.filled:
            flow.fill_slot_values({'reference_count': 5})

        # Default threshold to 0.2
        thresh_slot = flow.slots.get('threshold')
        threshold = float(thresh_slot.to_dict()) if thresh_slot and thresh_slot.filled else 0.2

        text, tool_log = self.llm_execute(flow, state, context, tools)
        result = self.extract_tool_result(tool_log, 'audit_post')

        # Format audit results into a structured report
        report = self._format_audit_report(result, text)

        # Threshold check: count affected sections / total sections
        sections_affected = result.get('sections_affected', 0)
        total_sections = result.get('total_sections', 1)
        pct = sections_affected / total_sections if total_sections else 0
        if pct > threshold:
            self.ambiguity.declare('confirmation', metadata={
                'reason': 'audit_threshold_exceeded',
                'pct': round(pct, 2),
                'threshold': threshold,
            })
            frame = self.build_frame('default')
            frame.data = {'content': report or text}
            return frame

        flow.status = 'Completed'
        frame = self.build_frame('card', origin='audit', thoughts=text)
        frame.data = {'content': report or text}
        return frame

    @staticmethod
    def _format_audit_report(result:dict, text:str) -> str|None:
        """Format audit tool results into a style consistency report."""
        lines = []
        if result.get('style_score') is not None:
            lines.append(f'Style consistency score: {result["style_score"]}')
        if result.get('tone_match') is not None:
            lines.append(f'Tone match: {result["tone_match"]}')
        if result.get('findings'):
            lines.append('Findings:')
            for finding in result['findings']:
                lines.append(f'  - {finding}')
        if result.get('suggestions'):
            lines.append('Suggestions:')
            for sug in result['suggestions']:
                lines.append(f'  - {sug}')
        # Fall back to LLM text if no structured results
        if not lines:
            for para in text.split('\n\n'):
                stripped = para.strip()
                if any(word in stripped.lower() for word in
                       ['style', 'tone', 'voice', 'consistency', 'finding', 'suggest']):
                    lines.append(stripped)
        return '\n'.join(lines) if lines else None

    def simplify_policy(self, flow, state, context, tools):
        source = flow.slots.get('source')
        image = flow.slots.get('image')
        if (not source or not source.filled) and (not image or not image.filled):
            self.ambiguity.declare('partial', metadata={'missing_slot': 'source_or_image'})
            frame = self.build_frame('default')
            frame.data = {'content': self.ambiguity.ask()}
            return frame

        post_id, sec_id = self._resolve_source_ids(flow, state, tools)
        text, tool_log = self.llm_execute(flow, state, context, tools)

        if post_id and sec_id and text:
            self._persist_section(post_id, sec_id, text, tools)

        flow.status = 'Completed'
        frame = self.build_frame('card', origin='simplify', thoughts=text)
        if post_id:
            frame.data = self._read_post_content(post_id, tools)
        return frame

    def remove_policy(self, flow, state, context, tools):
        missing = self._require_source(flow, state, context)
        if missing:
            return missing

        if not flow.slots.get('type', None) or not flow.slots['type'].filled:
            self.ambiguity.declare('specific', metadata={'missing_slot': 'type'})
            frame = self.build_frame('default')
            frame.data = {'content': self.ambiguity.ask()}
            return frame

        post_id, _ = self._resolve_source_ids(flow, state, tools)
        text, tool_log = self.llm_execute(flow, state, context, tools)
        flow.status = 'Completed'
        frame = self.build_frame('card', origin='remove', thoughts=text)
        if post_id:
            frame.data = self._read_post_content(post_id, tools)
        return frame

    def tidy_policy(self, flow, state, context, tools):
        missing = self._require_source(flow, state, context)
        if missing:
            return missing

        post_id, _ = self._resolve_source_ids(flow, state, tools)
        if post_id:
            result = tools('read_metadata', {'post_id': post_id, 'include_outline': True})
        else:
            result = {'_success': False}

        if result.get('_success'):
            content = result.get('outline', '')

            settings_slot = flow.slots.get('settings')
            settings = settings_slot.to_dict() if settings_slot and settings_slot.filled else {}

            convo_history = context.compile_history()
            history_with_data = (
                f"{convo_history}\n\n[Post content]\nTitle: {result.get('title', '')}\n"
                f"Content ({len(content)} chars): {content[:500]}\n\n"
                f"[Settings] {settings if settings else 'default normalization'}"
            )

            skill_prompt = self._load_skill_template(flow.name())
            messages = self.engineer.build_skill_prompt(flow, history_with_data, self.memory.read_scratchpad(), skill_prompt)
            text = self.engineer.call(messages, max_tokens=4096)

            flow.status = 'Completed'
            frame = self.build_frame('card', origin='tidy', thoughts=text)
            frame.data = {
                'post_id': post_id,
                'title': result.get('title', ''),
                'content': text,
            }
            return frame
        else:
            flow.status = 'Completed'
            frame = self.build_frame('default')
            frame.data = {'content': 'Could not find the specified post.'}
            return frame
