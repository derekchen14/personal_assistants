from __future__ import annotations

import json
import re

from backend.modules.policies.base import BasePolicy
from backend.components.display_frame import DisplayFrame
from schemas.ontology import Intent


_APPROVE_PATTERN = re.compile(
    r'^(yes|yeah|yep|yup|ok|okay|sure|confirm|approve|accept|go ahead)\s*[.!?]*$',
    re.I,
)


class PlanPolicy(BasePolicy):

    def __init__(self, components:dict):
        super().__init__(components)
        self.flow_stack = components['flow_stack']

    def execute(self, state, context, tools) -> 'DisplayFrame':
        flow = self.flow_stack.get_flow()

        match flow.name():
            case 'remember': return self.remember_policy(flow, state, context, tools)
            case _: return self._plan_lifecycle(flow, state, context, tools)

    # -- Plan lifecycle (3-phase state machine) -----------------------------

    def _plan_lifecycle(self, flow, state, context, tools):
        structured_plan = flow.structured_plan

        if not structured_plan:
            return self._generate_plan(flow, state, context, tools)
        if not state.has_plan:
            return self._handle_approval(flow, state, context, tools)
        return self._verify_and_continue(flow, state, context, tools)

    # -- Per-flow methods ---------------------------------------------------

    def remember_policy(self, flow, state, context, tools):
        """Deterministic — skips plan lifecycle."""
        slots = flow.slot_values_dict()
        topic = slots.get('topic', '')

        if topic:
            scratchpad = self.memory.read_scratchpad(topic)
            content = str(scratchpad) if scratchpad else ''
        else:
            content = str(self.memory.read_scratchpad())

        flow.status = 'Completed'
        return DisplayFrame(origin='remember', thoughts=content)

    # -- Mode A: Generate plan ----------------------------------------------

    def _generate_plan(self, flow, state, context, tools):
        text, tool_log = self.llm_execute(flow, state, context, tools)
        freeform, structured_plan = self._parse_dual_output(text, tool_log)

        for sub_flow in structured_plan.get('sub_flows', []):
            sub_flow.setdefault('status', 'pending')

        flow.structured_plan = structured_plan

        return DisplayFrame(origin=flow.name(), thoughts=freeform)

    # -- Mode B: Handle approval --------------------------------------------

    def _handle_approval(self, flow, state, context, tools):
        user_text = context.last_user_text or ''

        if not _APPROVE_PATTERN.match(user_text.strip()):
            flow.structured_plan = {}
            return self._generate_plan(flow, state, context, tools)

        plan_id = self.flow_stack.get_flow().flow_id

        self._push_next_sub_flow(flow, plan_id)

        state.has_plan=True
        state.keep_going=True

        return DisplayFrame(origin=flow.name())

    # -- Mode C: Verify and continue ----------------------------------------

    def _verify_and_continue(self, flow, state, context, tools):
        structured_plan = flow.structured_plan
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
            self.flow_stack.get_flow().status = 'Completed'
            state.keep_going=False
            summary = f'Plan completed: {structured_plan.get("description", flow.name())}'
            return DisplayFrame(origin=flow.name(), thoughts=summary)

        plan_id = self.flow_stack.get_flow().flow_id
        self._push_next_sub_flow(flow, plan_id)
        state.keep_going = True

        return DisplayFrame(origin=flow.name())

    # -- Helpers ------------------------------------------------------------

    def _push_next_sub_flow(self, plan_flow, plan_id):
        sub_flows = plan_flow.structured_plan.get('sub_flows', [])

        for sf in sub_flows:
            if sf['status'] != 'pending':
                continue
            flow_name = sf['flow_name']

            try:
                flow = self.flow_stack.stackon(flow_name, plan_id=plan_id)
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
            if result.get('_success'):
                # Check all non-underscore keys for sub_flows
                for k, v in result.items():
                    if k.startswith('_'):
                        continue
                    if isinstance(v, dict) and 'sub_flows' in v:
                        return text, v
                if 'sub_flows' in result:
                    return text, result

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
