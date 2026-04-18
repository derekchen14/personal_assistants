from __future__ import annotations
from backend.modules.policies.base import BasePolicy
from backend.components.display_frame import DisplayFrame


class RevisePolicy(BasePolicy):

    def __init__(self, components:dict):
        super().__init__(components)
        self.flow_stack = components['flow_stack']

    def execute(self, state, context, tools) -> 'DisplayFrame':
        flow = self.flow_stack.get_flow()

        match flow.name():
            case 'rework': return self.rework_policy(flow, state, context, tools)
            case 'polish': return self.polish_policy(flow, state, context, tools)
            case 'tone': return self.tone_policy(flow, state, context, tools)
            case 'audit': return self.audit_policy(flow, state, context, tools)
            case 'simplify': return self.simplify_policy(flow, state, context, tools)
            case 'remove': return self.remove_policy(flow, state, context, tools)
            case 'tidy': return self.tidy_policy(flow, state, context, tools)
            case _:
                return DisplayFrame()

    def _require_source(self, flow, state, context):
        """Check entity slot is filled. Returns frame if missing."""
        grounding = flow.slots[flow.entity_slot]
        if not grounding.check_if_filled():
            self.ambiguity.declare('specific', metadata={'missing_slot': flow.entity_slot})
            return DisplayFrame()
        return None

    def rework_policy(self, flow, state, context, tools):
        missing = self._require_source(flow, state, context)
        if missing:
            return missing

        post_id, _ = self._resolve_source_ids(flow, state, tools)
        text, tool_log = self.llm_execute(flow, state, context, tools)
        flow.status = 'Completed'
        frame = DisplayFrame(origin='rework', thoughts=text)
        if post_id:
            frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
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
        result = self.engineer.extract_tool_result(tool_log, 'inspect_post')
        if result.get('structural_issues'):
            self.flow_stack.fallback('rework')
            state.keep_going = True
            return DisplayFrame()

        flow.status = 'Completed'
        frame = DisplayFrame(origin='polish', thoughts=text)
        if post_id:
            frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        return frame

    def tone_policy(self, flow, state, context, tools):
        missing = self._require_source(flow, state, context)
        if missing:
            return missing

        # Tone — at least one elective needed (chosen_tone or custom_tone)
        if not flow.slots['chosen_tone'].check_if_filled() and not flow.slots['custom_tone'].check_if_filled():
            pref = self.memory.read_preference('tone')
            flow.fill_slot_values({'chosen_tone': pref or 'natural'})

        post_id, _ = self._resolve_source_ids(flow, state, tools)
        text, tool_log = self.llm_execute(flow, state, context, tools)
        frame = DisplayFrame(origin='tone', thoughts=text)
        if post_id:
            frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})

        flow.status = 'Completed'
        if state.has_plan:
            self.memory.write_scratchpad(f'flow:{flow.name()}', f'tone: {text[:200]}')
        return frame

    def audit_policy(self, flow, state, context, tools):
        missing = self._require_source(flow, state, context)
        if missing:
            return missing

        # Default reference_count to 5
        if not flow.slots['reference_count'].filled:
            flow.fill_slot_values({'reference_count': 5})

        # Default threshold to 0.2
        thresh_slot = flow.slots['threshold']
        threshold = float(thresh_slot.to_dict()) if thresh_slot.filled else 0.2

        text, tool_log = self.llm_execute(flow, state, context, tools)
        result = self.engineer.extract_tool_result(tool_log, 'audit_post')

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
            return DisplayFrame()

        flow.status = 'Completed'
        post_id, _ = self._resolve_source_ids(flow, state, tools)
        frame = DisplayFrame(origin='audit', thoughts=report or text)
        if post_id:
            frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
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
        if not flow.slots['source'].check_if_filled() and not flow.slots['image'].check_if_filled():
            self.ambiguity.declare('partial', metadata={'missing_slot': 'source_or_image'})
            return DisplayFrame()

        post_id, sec_id = self._resolve_source_ids(flow, state, tools)
        text, tool_log = self.llm_execute(flow, state, context, tools)

        if post_id and sec_id and text:
            self._persist_section(post_id, sec_id, text, tools)

        flow.status = 'Completed'
        frame = DisplayFrame(origin='simplify', thoughts=text)
        if post_id:
            frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        return frame

    def remove_policy(self, flow, state, context, tools):
        missing = self._require_source(flow, state, context)
        if missing:
            return missing

        if not flow.slots['type'].check_if_filled():
            self.ambiguity.declare('specific', metadata={'missing_slot': 'type'})
            return DisplayFrame()

        post_id, _ = self._resolve_source_ids(flow, state, tools)
        text, tool_log = self.llm_execute(flow, state, context, tools)
        flow.status = 'Completed'
        frame = DisplayFrame(origin='remove', thoughts=text)
        if post_id:
            frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
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

            settings_slot = flow.slots['settings']
            settings = settings_slot.to_dict() if settings_slot.filled else {}

            convo_history = context.compile_history()
            history_with_data = (
                f"{convo_history}\n\n[Post content]\nTitle: {result.get('title', '')}\n"
                f"Content ({len(content)} chars): {content[:500]}\n\n"
                f"[Settings] {settings if settings else 'default normalization'}"
            )

            text = self.engineer.skill_call(flow, history_with_data, self.memory.read_scratchpad(), max_tokens=4096)

            flow.status = 'Completed'
            frame = DisplayFrame(origin='tidy', thoughts=text)
            frame.add_block({'type': 'card', 'data': {
                'post_id': post_id,
                'title': result.get('title', ''),
                'content': text,
            }})
            return frame
        else:
            flow.status = 'Completed'
            return DisplayFrame(thoughts='Could not find the specified post.')
