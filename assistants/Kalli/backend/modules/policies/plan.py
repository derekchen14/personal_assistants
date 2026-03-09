from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

from schemas.ontology import FLOW_CATALOG, Intent

if TYPE_CHECKING:
    from backend.components.dialogue_state import DialogueState
    from backend.components.display_frame import DisplayFrame


_SKILL_DIR = Path(__file__).resolve().parents[2] / 'prompts' / 'skills'

_BATCH_1 = {'onboard'}
_BATCH_2 = {'research', 'expand'}

_APPROVE_PATTERN = re.compile(
    r'^(yes|yeah|yep|yup|ok|okay|sure|confirm|approve|accept|go ahead)\s*[.!?]*$',
    re.I,
)


class PlanPolicy:

    def __init__(self, components: dict):
        self.engineer = components['engineer']
        self.memory = components['memory']
        self.world = components['world']
        self._get_tools_fn = components['get_tools']

    def execute(self, flow_name: str, flow_info: dict,
                state: 'DialogueState', tool_dispatcher) -> 'DisplayFrame':
        from backend.components.display_frame import DisplayFrame

        if flow_name in _BATCH_2:
            frame = DisplayFrame(self.world.config)
            frame.set_frame('default', {'content': "That feature is coming soon — stay tuned!"}, source=flow_name)
            return frame

        handler = getattr(self, f'_do_{flow_name}', None)
        if handler:
            return handler(flow_info, state, tool_dispatcher)

        structured_plan = state.structured_plan

        if not structured_plan:
            return self._generate_plan(flow_name, flow_info, state, tool_dispatcher)
        if not state.has_plan:
            return self._handle_approval(flow_name, flow_info, state, tool_dispatcher)
        return self._verify_and_continue(flow_name, flow_info, state, tool_dispatcher)

    # ── Onboard (auto-approve) ───────────────────────────────────────

    def _do_onboard(self, flow_info, state, tool_dispatcher):
        from backend.components.display_frame import DisplayFrame

        structured_plan = state.structured_plan
        if structured_plan and state.has_plan:
            return self._verify_and_continue('onboard', flow_info, state, tool_dispatcher)

        skill_prompt = self._load_skill_template('onboard')
        system, messages = self.engineer.build_skill_prompt(
            'onboard', flow_info, state.slots,
            self.world.context.compile_history(turns=5),
            self.memory.read_scratchpad(),
            skill_prompt=skill_prompt,
        )
        tools = self._get_tools('onboard', flow_info)

        text, tool_log = self.engineer.call_with_tools(
            system, messages, tools, tool_dispatcher, call_site='skill',
        )

        freeform, structured_plan = self._parse_dual_output(text, tool_log)

        if not structured_plan.get('sub_flows'):
            structured_plan['sub_flows'] = [
                {'flow_name': ef, 'slots': {}, 'tools': [], 'rationale': 'onboard', 'status': 'pending'}
                for ef in flow_info.get('edge_flows', [])
                if FLOW_CATALOG.get(ef)
            ]

        for sub_flow in structured_plan.get('sub_flows', []):
            sub_flow.setdefault('status', 'pending')

        state.structured_plan = structured_plan

        plan_flow = self.world.flow_stack.get_active_flow()
        plan_id = plan_flow.flow_id if plan_flow else None
        self._push_next_sub_flow(state, plan_id)

        state.update_flags(has_plan=True, keep_going=True)

        frame = DisplayFrame(self.world.config)
        frame.set_frame('list', {
            'title': f'Plan: {flow_info.get("description", "onboard")}',
            'content': freeform,
            'items': [sf['flow_name'] for sf in structured_plan.get('sub_flows', [])],
        }, source='onboard')
        return frame

    # ── Mode A: Generate plan ────────────────────────────────────────

    def _generate_plan(self, flow_name, flow_info, state, tool_dispatcher):
        from backend.components.display_frame import DisplayFrame

        skill_prompt = self._load_skill_template(flow_name)
        system, messages = self.engineer.build_skill_prompt(
            flow_name, flow_info, state.slots,
            self.world.context.compile_history(turns=5),
            self.memory.read_scratchpad(),
            skill_prompt=skill_prompt,
        )
        tools = self._get_tools(flow_name, flow_info)

        text, tool_log = self.engineer.call_with_tools(
            system, messages, tools, tool_dispatcher, call_site='skill',
        )

        freeform, structured_plan = self._parse_dual_output(text, tool_log)

        for sub_flow in structured_plan.get('sub_flows', []):
            sub_flow.setdefault('status', 'pending')

        state.structured_plan = structured_plan

        frame = DisplayFrame(self.world.config)
        frame.set_frame('default', {
            'flow_name': flow_name,
            'content': freeform,
        }, source=flow_name)
        return frame

    # ── Mode B: Handle approval ──────────────────────────────────────

    def _handle_approval(self, flow_name, flow_info, state, tool_dispatcher):
        recent = self.world.context.compile_history(turns=1)
        user_text = ''
        for turn in reversed(recent):
            if turn.get('speaker') == 'User':
                user_text = turn.get('text', '')
                break

        if not _APPROVE_PATTERN.match(user_text.strip()):
            state.structured_plan = {}
            return self._generate_plan(flow_name, flow_info, state, tool_dispatcher)

        plan_flow = self.world.flow_stack.get_active_flow()
        plan_id = plan_flow.flow_id if plan_flow else None

        self._push_next_sub_flow(state, plan_id)

        state.update_flags(has_plan=True, keep_going=True)

        from backend.components.display_frame import DisplayFrame
        frame = DisplayFrame(self.world.config)
        frame.set_frame('default', {
            'flow_name': flow_name,
            'content': 'Plan approved — executing now.',
        }, source=flow_name)
        return frame

    # ── Mode C: Verify and continue ──────────────────────────────────

    def _verify_and_continue(self, flow_name, flow_info, state, tool_dispatcher):
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
                    f"plan:{flow_name}:{last_completed['flow_name']}",
                    str(result_data)[:200],
                )
            else:
                last_completed['status'] = 'completed'

        all_done = all(sf['status'] == 'completed' for sf in sub_flows)

        if all_done:
            self.world.flow_stack.mark_complete(result={'flow_name': flow_name})
            frame = DisplayFrame(self.world.config)
            frame.set_frame('default', {
                'flow_name': flow_name,
                'content': f'Plan completed: {structured_plan.get("description", flow_name)}',
            }, source=flow_name)
            state.update_flags(keep_going=False)
            return frame

        plan_flow = self.world.flow_stack.get_active_flow()
        plan_id = plan_flow.flow_id if plan_flow else None
        self._push_next_sub_flow(state, plan_id)
        state.update_flags(keep_going=True)

        frame = DisplayFrame(self.world.config)
        completed_names = [sf['flow_name'] for sf in sub_flows if sf['status'] == 'completed']
        frame.set_frame('default', {
            'flow_name': flow_name,
            'content': f'Completed: {", ".join(completed_names)}. Continuing to next step.',
        }, source=flow_name)
        return frame

    # ── Helpers ───────────────────────────────────────────────────────

    def _push_next_sub_flow(self, state, plan_id):
        sub_flows = state.structured_plan.get('sub_flows', [])

        for sf in sub_flows:
            if sf['status'] != 'pending':
                continue
            flow_name = sf['flow_name']
            flow_info = FLOW_CATALOG.get(flow_name)
            if not flow_info:
                sf['status'] = 'completed'
                continue

            intent_val = flow_info['intent']
            if hasattr(intent_val, 'value'):
                intent_val = intent_val.value

            if intent_val == Intent.INTERNAL.value:
                self.world.flow_stack.push(
                    flow_name, flow_info['dax'], intent_val,
                    slots=sf.get('slots', {}), plan_id=plan_id,
                )
                sf['status'] = 'in_progress'
                continue

            self.world.flow_stack.push(
                flow_name, flow_info['dax'], intent_val,
                slots=sf.get('slots', {}), plan_id=plan_id,
            )
            sf['status'] = 'in_progress'
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

    def _get_tools(self, flow_name: str, flow_info: dict) -> list[dict]:
        return self._get_tools_fn(flow_name, flow_info)
