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

    def _guard_entity(self, flow):
        """Entity-missing guard. Declares `partial` and returns an empty frame with origin=flow.name() 
        when the entity slot is unfilled. Callers early-return on non-None result"""
        grounding = flow.slots[flow.entity_slot]
        if not grounding.check_if_filled():
            self.ambiguity.declare('partial', metadata={'missing_entity': 'post'})
            return DisplayFrame(flow.name())
        return None

    def rework_policy(self, flow, state, context, tools):
        early = self._guard_entity(flow)
        if early is not None: return early
        post_id, _ = self._resolve_source_ids(flow, state, tools)

        # Preload per-section preview (title + first few lines). This gives context to handle whole-post operations
        # (swap two sections, reorder, cross-section rewrite) in a single llm_execute pass instead of looping.
        text, tool_log = self.llm_execute(flow, state, context, tools, include_preview=True)
        self._mark_suggestions_done(flow, tool_log, text)

        flow.status = 'Completed'
        frame = DisplayFrame(flow.name(), thoughts=text)
        if post_id:
            frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        return frame

    def _mark_suggestions_done(self, flow, tool_log, text):
        """Inspect the skill's JSON reply for `done` markers on suggestions and check the corresponding
        ChecklistSlot items off. The skill returns either {"target": ..., "added": [...], "done": ["sug1", "sug2"]}
        or {"suggestions": {"sug1": "done", "sug2": "done"}}; both shapes work."""
        sug_slot = flow.slots.get('suggestions')
        if not sug_slot or not getattr(sug_slot, 'steps', None):
            return
        saved, _ = self.engineer.tool_succeeded(tool_log, 'revise_content')
        if not saved:
            return
        parsed = self.engineer.apply_guardrails(text)
        if not isinstance(parsed, dict):
            return
        completed_names = []
        if isinstance(parsed.get('done'), list):
            completed_names.extend(str(name) for name in parsed['done'])
        sug_payload = parsed.get('suggestions')
        if isinstance(sug_payload, dict):
            completed_names.extend(name for name, status in sug_payload.items() if str(status).lower() == 'done')
        for step_name in completed_names:
            sug_slot.mark_as_complete(step_name)

    def polish_policy(self, flow, state, context, tools):
        early = self._guard_entity(flow)
        if early is not None:
            return early

        post_id, sec_id = self._resolve_source_ids(flow, state, tools)
        text, tool_log = self.llm_execute(flow, state, context, tools)

        if post_id and sec_id and text:
            self._persist_section(post_id, sec_id, text, tools)

        # Bump used_count on scratchpad entries the skill actually consumed.
        parsed = self.engineer.apply_guardrails(text)
        if isinstance(parsed, dict):
            for key in parsed.get('used', []):
                entry = self.memory.read_scratchpad(str(key))
                if isinstance(entry, dict):
                    entry['used_count'] = entry.get('used_count', 0) + 1
                    self.memory.write_scratchpad(str(key), entry)

        # Scope-mismatch fallback: if inspect_post flagged structural issues,
        # re-route to rework rather than committing the polish.
        inspect_result = self.engineer.extract_tool_result(tool_log, 'inspect_post')
        if inspect_result.get('structural_issues'):
            self.flow_stack.fallback('rework')
            state.keep_going = True
            frame = DisplayFrame(flow.name(), thoughts='Structural issues found, rerouting to rework.')
        else:
            flow.status = 'Completed'
            frame = DisplayFrame(flow.name(), thoughts=text)
            if post_id:
                frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        return frame

    def tone_policy(self, flow, state, context, tools):
        early = self._guard_entity(flow)
        if early is not None:
            return early

        # Default-commit: at least one tone elective must land before dispatch.
        if not flow.slots['chosen_tone'].check_if_filled() and not flow.slots['custom_tone'].check_if_filled():
            pref = self.memory.read_preference('tone')
            flow.fill_slot_values({'chosen_tone': pref or 'natural'})

        post_id, _ = self._resolve_source_ids(flow, state, tools)
        text, tool_log = self.llm_execute(flow, state, context, tools)

        flow.status = 'Completed'
        frame = DisplayFrame(flow.name(), thoughts=text)
        if post_id:
            frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        # Record brief result for downstream plan steps to consume.
        if state.has_plan:
            self.memory.write_scratchpad(flow.name(), {
                'version': '1',
                'turn_number': context.turn_id,
                'used_count': 0,
                'summary': text[:200],
            })
        return frame

    def audit_policy(self, flow, state, context, tools):
        early = self._guard_entity(flow)
        if early is not None:
            return early

        # Default-commit: reference_count=5.
        if not flow.slots['reference_count'].filled:
            flow.fill_slot_values({'reference_count': 5})

        post_id, _ = self._resolve_source_ids(flow, state, tools)
        _, tool_log = self.llm_execute(flow, state, context, tools)

        # Source of truth is the save_findings tool call. The tool already
        # wrote scratchpad (keyed by flow.name()); we just read what was saved.
        saved = self.engineer.extract_tool_result(tool_log, 'save_findings')
        if not saved:
            return self.error_frame(flow, 'parse_failure', thoughts='Audit did not emit structured findings.')

        flow.status = 'Completed'
        frame = DisplayFrame(flow.name())
        frame.add_block({'type': 'card', 'data': {
            'post_id': post_id,
            'findings': saved['findings'],
            'summary': saved.get('summary', ''),
        }})
        return frame

    def simplify_policy(self, flow, state, context, tools):
        # Disjunction entity: source OR image must be filled.
        if not flow.slots['source'].check_if_filled() and not flow.slots['image'].check_if_filled():
            self.ambiguity.declare('partial', metadata={'missing_entity': 'post_or_image'})
            return DisplayFrame(flow.name())

        post_id, sec_id = self._resolve_source_ids(flow, state, tools)

        # Preload target section so the skill skips a runtime read_section.
        extra = {}
        if post_id and sec_id:
            sec = tools('read_section', {'post_id': post_id, 'sec_id': sec_id})
            if sec.get('_success'):
                extra['section_content'] = sec.get('content', '')

        text, tool_log = self.llm_execute(flow, state, context, tools, extra_resolved=extra or None)

        # Fallback persistence: if skill produced prose but didn't call revise_content.
        already_saved, _ = self.engineer.tool_succeeded(tool_log, 'revise_content')
        if post_id and sec_id and text and not already_saved:
            self._persist_section(post_id, sec_id, text, tools)

        flow.status = 'Completed'
        frame = DisplayFrame(flow.name(), thoughts=text)
        if post_id:
            frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        return frame

    def remove_policy(self, flow, state, context, tools):
        early = self._guard_entity(flow)
        if early is not None:
            return early

        if not flow.slots['type'].check_if_filled():
            self.ambiguity.declare('specific', metadata={'missing_slot': 'type'})
            frame = DisplayFrame(flow.name())
        else:
            post_id, _ = self._resolve_source_ids(flow, state, tools)
            text, tool_log = self.llm_execute(flow, state, context, tools)
            flow.status = 'Completed'
            frame = DisplayFrame(flow.name(), thoughts=text)
            if post_id:
                frame.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
        return frame

    def tidy_policy(self, flow, state, context, tools):
        early = self._guard_entity(flow)
        if early is not None:
            return early

        post_id, _ = self._resolve_source_ids(flow, state, tools)
        result = tools('read_metadata', {'post_id': post_id, 'include_outline': True}) if post_id else {'_success': False}

        if not result.get('_success'):
            frame = self.error_frame(flow, 'missing_reference',
                thoughts='Could not find the specified post.',
                missing_entity='post')
        else:
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
            frame = DisplayFrame(flow.name(), thoughts=text)
            frame.add_block({'type': 'card', 'data': {
                'post_id': post_id,
                'title': result.get('title', ''),
                'content': text,
            }})
        return frame
