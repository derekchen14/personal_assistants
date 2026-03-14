from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

from schemas.ontology import Intent

if TYPE_CHECKING:
    from backend.components.dialogue_state import DialogueState
    from backend.components.context_coordinator import ContextCoordinator
    from backend.components.display_frame import DisplayFrame
    from backend.components.flow_stack.parents import BaseFlow


_SKILL_DIR = Path(__file__).resolve().parents[2] / 'prompts' / 'skills'

_BATCH_1 = {'insight', 'pipeline'}
_BATCH_2 = {'blank', 'issue', 'outline'}

_APPROVE_PATTERN = re.compile(
    r'^(yes|yeah|yep|yup|ok|okay|sure|confirm|approve|accept|go ahead)\s*[.!?]*$',
    re.I,
)


class PlanPolicy:

    def __init__(self, components: dict):
        self.engineer = components['engineer']
        self.memory = components['memory']
        self.config = components['config']
        self.flow_stack = components['flow_stack']
        self._get_tools_fn = components['get_tools']

    def execute(self, flow: 'BaseFlow', state: 'DialogueState',
                context: 'ContextCoordinator', tools) -> 'DisplayFrame':
        from backend.components.display_frame import DisplayFrame

        if flow.name() in _BATCH_2:
            frame = DisplayFrame(self.config)
            frame.set_frame('default', {'content': "That feature is coming soon — stay tuned!"})
            return frame

        structured_plan = state.structured_plan

        if not structured_plan:
            return self._generate_plan(flow, state, context, tools)
        if not state.has_plan:
            return self._handle_approval(flow, state, context, tools)
        return self._verify_and_continue(flow, state, context, tools)

    # -- Mode A: Generate plan ────────────────────────────────────────

    def _generate_plan(self, flow, state, context, tools):
        from backend.components.display_frame import DisplayFrame

        skill_prompt = self._load_skill_template(flow.name())
        system, messages = self.engineer.build_skill_prompt(
            flow.name(), flow, flow.slot_values_dict(),
            context.compile_history(look_back=5),
            self.memory.read_scratchpad(),
            skill_prompt=skill_prompt,
        )
        tool_defs = self._get_tools_fn(flow)

        text, tool_log = self.engineer.call_with_tools(
            system, messages, tool_defs, tools, call_site='skill',
        )

        freeform, structured_plan = self._parse_dual_output(text, tool_log)

        for sub_flow in structured_plan.get('sub_flows', []):
            sub_flow.setdefault('status', 'pending')

        state.structured_plan = structured_plan

        frame = DisplayFrame(self.config)
        frame.set_frame('default', {
            'flow_name': flow.name(),
            'content': freeform,
        }, source=flow.name())
        return frame

    # -- Mode B: Handle approval ──────────────────────────────────────

    def _handle_approval(self, flow, state, context, tools):
        user_text = context.last_user_text or ''

        if not _APPROVE_PATTERN.match(user_text.strip()):
            state.structured_plan = {}
            return self._generate_plan(flow, state, context, tools)

        plan_flow = self.flow_stack.get_active_flow()
        plan_id = plan_flow.flow_id if plan_flow else None

        self._push_next_sub_flow(state, plan_id)

        state.update_flags(has_plan=True, keep_going=True)

        from backend.components.display_frame import DisplayFrame
        frame = DisplayFrame(self.config)
        frame.set_frame('default', {
            'flow_name': flow.name(),
            'content': 'Plan approved — executing now.',
        }, source=flow.name())
        return frame

    # -- Mode C: Verify and continue ──────────────────────────────────

    def _verify_and_continue(self, flow, state, context, tools):
        from backend.components.display_frame import DisplayFrame

        structured_plan = state.structured_plan
        sub_flows = structured_plan.get('sub_flows', [])

        last_completed = None
        for sf in sub_flows:
            if sf['status'] == 'in_progress':
                last_completed = sf
                break

        if last_completed:
            scratchpad = self.memory.read_scratchpad()
            result_key = f"flow:{last_completed['flow_name']}"
            result_data = scratchpad.get(result_key, '') if isinstance(scratchpad, dict) else ''

            if result_data:
                last_completed['status'] = 'completed'
                self.memory.write_scratchpad(
                    f"plan:{flow.name()}:{last_completed['flow_name']}",
                    str(result_data)[:200],
                )
            else:
                last_completed['status'] = 'completed'

        all_done = all(sf['status'] == 'completed' for sf in sub_flows)

        if all_done:
            self.flow_stack.mark_complete(result={'flow_name': flow.name()})
            frame = DisplayFrame(self.config)
            frame.set_frame('default', {
                'flow_name': flow.name(),
                'content': f'Plan completed: {structured_plan.get("description", flow.name())}',
            }, source=flow.name())
            state.update_flags(keep_going=False)
            return frame

        plan_flow = self.flow_stack.get_active_flow()
        plan_id = plan_flow.flow_id if plan_flow else None
        self._push_next_sub_flow(state, plan_id)
        state.update_flags(keep_going=True)

        frame = DisplayFrame(self.config)
        completed_names = [sf['flow_name'] for sf in sub_flows if sf['status'] == 'completed']
        frame.set_frame('default', {
            'flow_name': flow.name(),
            'content': f'Completed: {", ".join(completed_names)}. Continuing to next step.',
        }, source=flow.name())
        return frame

    # -- Helpers ───────────────────────────────────────────────────────

    def _push_next_sub_flow(self, state, plan_id):
        sub_flows = state.structured_plan.get('sub_flows', [])

        for sf in sub_flows:
            if sf['status'] != 'pending':
                continue
            flow_name = sf['flow_name']

            try:
                flow = self.flow_stack.push(flow_name, plan_id=plan_id)
            except ValueError:
                sf['status'] = 'completed'
                continue

            flow.fill_slot_values(sf.get('slots', {}))
            sf['status'] = 'in_progress'

            if flow.intent != Intent.INTERNAL:
                break

    def _parse_dual_output(self, text, tool_log):
        for entry in tool_log:
            result = entry.get('result', {})
            if result.get('status') == 'success':
                result_data = result.get('result', {})
                if isinstance(result_data, dict) and 'sub_flows' in result_data:
                    return text, result_data

        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                freeform = parsed.get('freeform', text)
                structured = parsed.get('structured', parsed)
                if 'sub_flows' in structured:
                    return freeform, structured
        except (json.JSONDecodeError, TypeError):
            pass

        return text, {
            'description': text[:200],
            'sub_flows': [],
            'ambiguities': [],
            'tool_calls': [],
            'verification': [],
        }

    def _load_skill_template(self, flow_name: str) -> str | None:
        path = _SKILL_DIR / f'{flow_name}.md'
        if path.exists():
            return path.read_text(encoding='utf-8')
        return None
