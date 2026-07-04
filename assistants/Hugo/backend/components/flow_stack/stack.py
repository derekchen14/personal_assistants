from uuid import uuid4

from backend.components.flow_stack.parents import BaseFlow
from schemas.ontology import FlowLifecycle


class FlowStack:

    def __init__(self, config, flow_classes:dict|None=None):
        self.config = config
        self._stack: list[BaseFlow] = []
        self._max_depth: int = config.get('session', {}).get('max_flow_depth', 16)
        self._flow_classes = flow_classes or {}

    # ── Public API ──────────────────────────────────────────────────

    def stackon(self, flow_name:str):
        """Push a flow on top of the stack. The current flow stays below and resumes after the new flow completes.
        Transfers filled slot values to the new flow when slot names match across parent and child."""
        curr_flow = self._stack[-1] if self._stack else None
        # No consecutive same-type stackon when the top is still in flight. The active
        # flow IS already that flow, so there is nothing to "push as a prerequisite".
        # Completed/Invalid tops do not block — those are stale, the new flow is real.
        _terminal = (FlowLifecycle.COMPLETED.value, FlowLifecycle.INVALID.value)
        if curr_flow and curr_flow.flow_type == flow_name and curr_flow.status not in _terminal:
            return curr_flow
        new_flow = self._push(flow_name)
        # Slot transfer only from a flow still in flight — a Completed/Invalid top is stale
        # (see above), and seeding the new flow from it re-grounds fresh requests on old
        # entities (e.g. inspect post A, then "now check post B" inheriting A).
        if curr_flow and curr_flow.status not in _terminal:
            for slot_name, slot in curr_flow.slots.items():
                if slot_name in new_flow.slots and slot.filled:
                    new_flow.fill_slot_values({slot_name: slot.to_dict()})
        return new_flow

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

    def peek(self):
        """Top of stack without removing."""
        return self._stack[-1] if self._stack else None

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

    def pop_completed(self):
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
        # (activate_flow via _stack_flow, or pop_completed surfacing the next top).
        flow.status = FlowLifecycle.PENDING.value
        self._stack.append(flow)
        return flow

    def _pop(self):
        return self._stack.pop() if self._stack else None
