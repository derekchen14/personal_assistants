from __future__ import annotations

import json
from types import MappingProxyType
from typing import TYPE_CHECKING

from backend.components.dialogue_state import DialogueState
from backend.components.display_frame import DisplayFrame
from backend.components.ambiguity_handler import AmbiguityHandler
from backend.components.prompt_engineer import PromptEngineer
from backend.components.memory_manager import MemoryManager
# Domain-specific: import policy classes
# from backend.modules.policies import ConversePolicy, PlanPolicy, InternalPolicy
from schemas.ontology import FLOW_CATALOG, Intent

if TYPE_CHECKING:
    from backend.components.world import World


_UNSUPPORTED: set[str] = set()


class PEX:

    def __init__(self, config: MappingProxyType, ambiguity: AmbiguityHandler,
                 engineer: PromptEngineer, memory: MemoryManager,
                 world: 'World'):
        self.config = config
        self.ambiguity = ambiguity
        self.engineer = engineer
        self.memory = memory
        self.world = world

        # Domain-specific: initialize service classes
        # self._post_service = PostService()

        self._tool_definitions = self._build_tool_definitions()

        components = {
            'engineer': engineer,
            'memory': memory,
            'world': world,
            'get_tools': self.get_tools_for_flow,
        }
        self._policies: dict[str, object] = {
            # Domain-specific: register policy classes per intent
            # Intent.CONVERSE.value: ConversePolicy(components),
            # Intent.PLAN.value: PlanPolicy(components),
            # Intent.INTERNAL.value: InternalPolicy(components),
        }

    def execute(self, state: DialogueState) -> tuple[DisplayFrame, bool]:
        flow_name = state.flow_name
        flow_info = FLOW_CATALOG.get(flow_name)
        if not flow_info:
            frame = DisplayFrame(self.config)
            return frame, False

        check_result = self._check(state, flow_info)
        if check_result:
            return check_result, False

        existing = self.world.flow_stack.find_by_name(flow_name)
        if existing:
            flow_entry = existing
        else:
            flow_entry = self.world.flow_stack.push(
                flow_name, state.dax, state.intent,
                slots=state.slots,
            )

        if flow_name in _UNSUPPORTED:
            self.world.flow_stack.mark_complete(result={'unsupported': True})
            frame = self.world.latest_frame() or DisplayFrame(self.config)
            return frame, False

        intent_val = state.intent
        if hasattr(intent_val, 'value'):
            intent_val = intent_val.value
        policy = self._policies.get(intent_val)
        if policy:
            frame = policy.execute(
                flow_name, flow_info, state, self._dispatch_tool,
            )
        else:
            frame = DisplayFrame(self.config)

        if intent_val != Intent.PLAN.value:
            self.world.flow_stack.mark_complete(result={'flow_name': flow_name})
        self.world.insert_frame(frame)

        if frame.has_content():
            text_summary = frame.data.get('content', '')
            if text_summary:
                self.memory.write_scratchpad(
                    f'flow:{flow_name}',
                    f'{flow_name}: {text_summary[:200]}',
                )

        self._verify()

        keep_going = state.keep_going
        return frame, keep_going

    # ── Pre-hook ─────────────────────────────────────────────────────

    def _check(self, state: DialogueState,
               flow_info: dict) -> DisplayFrame | None:
        if state.flow_name in _UNSUPPORTED:
            return None

        required_missing = []
        for slot_name, slot_info in flow_info.get('slots', {}).items():
            if slot_info.get('priority') == 'required':
                if slot_name not in state.slots or not state.slots[slot_name]:
                    required_missing.append(slot_name)

        if required_missing:
            for slot_name in list(required_missing):
                filled = self._fill_from_context(slot_name, flow_info)
                if filled:
                    state.slots[slot_name] = filled
                    required_missing.remove(slot_name)

        if required_missing:
            self.ambiguity.declare(
                'specific',
                metadata={'missing_slots': required_missing},
                observation=f'I need the following to proceed: {", ".join(required_missing)}',
            )
            frame = DisplayFrame(self.config)
            frame.set_frame('default', {'message': self.ambiguity.ask()})
            return frame

        tools = self.get_tools_for_flow(state.flow_name, flow_info)
        for tool in tools:
            caps = tool.get('capabilities', {})
            if (caps.get('accesses_private_data')
                    and caps.get('receives_untrusted_input')
                    and caps.get('communicates_externally')):
                self.ambiguity.declare(
                    'confirmation',
                    metadata={'tool': tool['name'], 'reason': 'lethal_trifecta'},
                    observation=(
                        f'This action requires your approval because '
                        f'"{tool["name"]}" accesses private data, accepts '
                        f'user input, and communicates externally.'
                    ),
                )
                frame = DisplayFrame(self.config)
                frame.set_frame('confirmation', {
                    'prompt': self.ambiguity.ask(),
                    'confirm_label': 'Approve',
                    'cancel_label': 'Cancel',
                })
                return frame

        return None

    def _fill_from_context(self, slot_name: str, flow_info: dict) -> str | None:
        scratchpad_val = self.memory.read_scratchpad(slot_name)
        if scratchpad_val:
            return scratchpad_val

        recent = self.world.context.compile_history(turns=3)
        for turn in reversed(recent):
            if turn['speaker'] == 'User' and slot_name.lower() in turn['text'].lower():
                return turn['text']
        return None

    # ── Tool dispatch ────────────────────────────────────────────────

    def _dispatch_tool(self, tool_name: str, tool_input: dict) -> dict:
        self.world.context.add_turn(
            'Agent', f'[tool:{tool_name}] {json.dumps(tool_input)[:200]}',
            turn_type='action',
        )
        try:
            # Domain-specific: add domain tool dispatch cases
            if tool_name == 'context_coordinator':
                return self._dispatch_context_tool(tool_input)
            elif tool_name == 'memory_manager':
                return self.memory.dispatch_tool(
                    tool_input.get('action', ''),
                    tool_input,
                )
            elif tool_name == 'flow_stack':
                return self._dispatch_flow_stack_tool(tool_input)
            else:
                return {'status': 'error', 'message': f'Unknown tool: {tool_name}'}
        except Exception as e:
            return {
                'status': 'error',
                'error_category': 'server_error',
                'message': f'{type(e).__name__}: {e}',
            }

    def _dispatch_context_tool(self, params: dict) -> dict:
        action = params.get('action', '')
        if action == 'get_history':
            turns = params.get('turns', 3)
            history = self.world.context.compile_history(turns=turns)
            return {'status': 'success', 'result': history}
        elif action == 'get_turn':
            turn_id = params.get('turn_id', '')
            turn = self.world.context.get_turn(turn_id)
            return {'status': 'success', 'result': turn}
        elif action == 'get_checkpoint':
            label = params.get('label', '')
            cp = self.world.context.get_checkpoint(label)
            return {'status': 'success', 'result': cp}
        return {'status': 'error', 'message': f'Unknown action: {action}'}

    def _dispatch_flow_stack_tool(self, params: dict) -> dict:
        action = params.get('action', '')
        if action == 'get_slots':
            active = self.world.flow_stack.get_active_flow()
            if active:
                return {'status': 'success', 'result': active.slots}
            return {'status': 'success', 'result': {}}
        elif action == 'get_flow_meta':
            active = self.world.flow_stack.get_active_flow()
            if active:
                return {'status': 'success', 'result': active.to_dict()}
            return {'status': 'success', 'result': None}
        elif action == 'get_stack':
            return {'status': 'success', 'result': self.world.flow_stack.to_list()}
        return {'status': 'error', 'message': f'Unknown action: {action}'}

    # ── Tool definitions ─────────────────────────────────────────────

    def get_tools_for_flow(self, flow_name: str, flow_info: dict) -> list[dict]:
        tools = []
        tools.extend(self._component_tool_definitions())
        # Domain-specific: add domain tools based on intent
        return [t for t in tools if t is not None]

    def _build_tool_definitions(self) -> dict[str, dict]:
        # Domain-specific: define domain tools per assistant
        return {}

    def _component_tool_definitions(self) -> list[dict]:
        return [
            {
                'name': 'context_coordinator',
                'description': 'Access conversation history. Actions: get_history, get_turn, get_checkpoint',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'action': {'type': 'string', 'enum': ['get_history', 'get_turn', 'get_checkpoint']},
                        'turns': {'type': 'integer'},
                        'turn_id': {'type': 'string'},
                        'label': {'type': 'string'},
                    },
                    'required': ['action'],
                },
            },
            {
                'name': 'memory_manager',
                'description': 'Read/write session scratchpad and user preferences. Actions: read_scratchpad, write_scratchpad, read_preferences',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'action': {'type': 'string', 'enum': ['read_scratchpad', 'write_scratchpad', 'read_preferences']},
                        'key': {'type': 'string'},
                        'value': {'type': 'string'},
                    },
                    'required': ['action'],
                },
            },
            {
                'name': 'flow_stack',
                'description': 'Read flow stack state. Actions: get_slots, get_flow_meta, get_stack',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'action': {'type': 'string', 'enum': ['get_slots', 'get_flow_meta', 'get_stack']},
                    },
                    'required': ['action'],
                },
            },
        ]

    # ── Post-hook ────────────────────────────────────────────────────

    def _verify(self):
        state = self.world.current_state()
        if state and state.keep_going and not self.world.flow_stack.get_pending_flows():
            state.keep_going = False

    # ── Type checks (preserved from data-analysis scaffold) ──────────

    def check_types(self, context, table, properties=None):
        from backend.components.metadata.typechecks import TypeCheck

        properties = properties or {}
        num_columns, num_rows = len(table.columns), len(table)

        predicted_properties = {}
        if 0 < num_columns <= 10:
            if len(properties) > 0:
                type_prediction = {'columns': properties}
            else:
                table_md = table.head(32).to_markdown(index=False)
                convo_history = context.compile_history()
                # Domain-specific: build type_check_prompt from prompts module
                user_msg = "Each column should have a datatype and subtype."
                raw_output = self.engineer.call(
                    system=f'Predict datatypes for columns:\n{table_md}',
                    messages=[{'role': 'user', 'content': user_msg}],
                    call_site='type_check', max_tokens=1024,
                )
                text = ''
                for block in raw_output.content:
                    if block.type == 'text':
                        text += block.text
                try:
                    type_prediction = json.loads(text)
                except (json.JSONDecodeError, TypeError):
                    type_prediction = {'columns': {}}

            predicted_properties = type_prediction.get('columns', {})

            for col_name, column in table.items():
                try:
                    col_props = predicted_properties.get(col_name, {})
                    if not col_props:
                        col_props = TypeCheck.build_properties(col_name, column)
                    predicted_properties[col_name] = col_props
                    table[col_name] = column
                except Exception:
                    continue

        if len(predicted_properties) < num_columns:
            for col_name, column in table.items():
                if col_name not in predicted_properties:
                    col_props = TypeCheck.build_properties(col_name, column)
                    predicted_properties[col_name] = col_props
                    table[col_name] = column

        return predicted_properties, table
