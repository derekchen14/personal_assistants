from uuid import uuid4

from backend.components.flow_stack.parents import BaseFlow
from schemas.ontology import FlowLifecycle


class FlowStack:

    def __init__(self, config, flow_classes:dict|None=None):
        self.config = config
        self._stack: list[BaseFlow] = []
        self._max_depth: int = config['session']['max_flow_depth']
        self._flow_classes = flow_classes or {}

    def reset(self):
        """New session: clear in place (the no-rebind rule) — the one stack lives for the
        Assistant's lifetime."""
        self._stack.clear()

    # ── Public API ──────────────────────────────────────────────────

    def stackon(self, flow_name:str, transfer:bool=True):
        """Push a flow on top of the stack. An in-flight flow beneath reverts to Pending and
        resumes after the new flow completes (pop promotes it back). Transfers filled slot values
        to the new flow when slot names match — callers pass transfer=False while an ambiguity is
        open, since the incomplete flow's values are exactly what is in question.

        Same-type dedupe: pushing the type already in flight returns the existing flow ONLY while
        that flow's entity slot is still empty — once it is grounded to an entity, a same-type
        push is a new task on a new entity, not a repeat (planner spec scenario 12b).
        Completed/Invalid tops never block or transfer — those are stale, the new flow is real."""
        curr_flow = self._stack[-1] if self._stack else None
        _terminal = (FlowLifecycle.COMPLETED.value, FlowLifecycle.INVALID.value)
        in_flight = bool(curr_flow) and curr_flow.status not in _terminal
        if in_flight and curr_flow.flow_type == flow_name:
            entity = curr_flow.slots.get(curr_flow.entity_slot)  # chat-style flows have none
            if not (entity and entity.check_if_filled()):
                return curr_flow
        new_flow = self._push(flow_name)
        if in_flight:
            if transfer:
                for slot_name, slot in curr_flow.slots.items():
                    if slot_name in new_flow.slots and slot.filled:
                        new_flow.fill_slot_values({slot_name: slot.to_dict()})
            curr_flow.status = FlowLifecycle.PENDING.value  # the new flow claims the conversation
        return new_flow

    def update_flow(self, flow_name:str='', slots:dict|None=None, stage:str='', status:str=''):
        """Update a flow IN PLACE at any depth. Unlike the top-only ops (stackon / fallback / pop /
        get_flow), this locates the flow by name — blank name means the top flow — and writes
        slots/stage/status without running anything. Slot values arrive pre-normalized
        (DialogueState.write_state normalizes LLM-authored shapes before delegating here)."""
        flow = self.find_by_name(flow_name) if flow_name else self.get_flow()
        if not flow:  # LLM-authored flow_name — corrective error, not a crash
            raise ValueError(f'no live flow named {flow_name!r} on the stack')
        if slots:
            flow.fill_slot_values(slots)
            flow.is_filled()
        if stage:
            flow.stage = stage
        if status:
            flow.status = status
        return flow

    def fallback(self, flow_name:str):
        """Replace the current flow. Marks it Invalid first, then pushes the new flow,
        and transfers matching slot values to the new flow."""
        old_flow = self._stack[-1]
        old_flow.status = FlowLifecycle.INVALID.value
        new_flow = self._push(flow_name)
        new_flow.status = FlowLifecycle.ACTIVE.value  # replaces a running flow: takes over now
        for slot_name, slot in old_flow.slots.items():
            if slot_name in new_flow.slots and slot.filled:
                new_flow.fill_slot_values({slot_name: slot.to_dict()})
        return new_flow

    def get_flow(self, status:str|None=None):
        """Top-of-stack flow, optionally filtered by lifecycle status
        (e.g. 'Active', 'Pending')."""
        for entry in reversed(self._stack):
            if status is None or entry.status == status:
                return entry
        return None

    def find_by_name(self, flow_name:str):
        """Search the stack for an active/pending flow by name."""
        for entry in reversed(self._stack):
            if entry.flow_type == flow_name and entry.status not in (
                FlowLifecycle.COMPLETED.value, FlowLifecycle.INVALID.value,
            ):
                return entry
        return None

    def stack_size(self) -> int:
        """Number of active/pending flows on the stack (excludes Completed/Invalid)."""
        live = (FlowLifecycle.ACTIVE.value, FlowLifecycle.PENDING.value)
        return sum(1 for entry in self._stack if entry.status in live)

    def pop(self):
        """Remove all Completed and Invalid flows. Returns only the
        Completed ones (Invalid are silently discarded). Activates the
        next Pending flow if one is now on top."""
        completed = []
        remaining = []
        for entry in self._stack:
            if entry.status == FlowLifecycle.COMPLETED.value:
                completed.append(entry)
            elif entry.status == FlowLifecycle.INVALID.value:
                pass
            else:
                remaining.append(entry)
        self._stack = remaining
        if self._stack and self._stack[-1].status == FlowLifecycle.PENDING.value:
            self._stack[-1].status = FlowLifecycle.ACTIVE.value
        return completed

    def to_list(self) -> list[dict]:
        return [e.to_dict() for e in self._stack]

    # ── Internal ────────────────────────────────────────────────────

    def _push(self, flow_name:str):
        if len(self._stack) >= self._max_depth:
            raise RuntimeError(
                f'Flow stack depth limit ({self._max_depth}) exceeded'
            )
        cls = self._flow_classes.get(flow_name)
        if not cls:
            raise ValueError(f'Unknown flow: {flow_name}')
        flow = cls()
        flow.flow_id = str(uuid4())[:8]
        # Pushed flows wait as Pending (the user 2026-07-03) — activation promotes to Active
        # (activate_flow, or pop surfacing the next top).
        flow.status = FlowLifecycle.PENDING.value
        self._stack.append(flow)
        return flow

    def _pop(self):
        return self._stack.pop() if self._stack else None
