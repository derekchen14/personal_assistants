"""
FlowStack — manages the LIFO stack of active and pending flows.

The flow stack tracks every flow the agent has started in the current session.
At most one flow is ACTIVE at a time; others are PENDING (waiting for the
active flow to complete) or already COMPLETED/INVALID.

Lifecycle:
  push(name)            → instantiate flow, push to stack
                          new flow is ACTIVE if stack was empty, else PENDING
  get_active_flow()     → find the first ACTIVE flow from the top
  mark_complete(result) → top flow → COMPLETED with result stored
  mark_invalid()        → top flow → INVALID (user changed intent)
  pop_completed_and_invalid() → remove finished flows, activate next PENDING

Why a stack (not a queue):
  Flows can nest.  A Plan flow may push sub-flows that must complete before the
  plan resumes.  The stack's LIFO order naturally handles this: the inner flow
  is on top and runs first; when it completes, the outer flow resumes.

find_by_name():
  Searches only ACTIVE and PENDING flows (not COMPLETED/INVALID).  Used when
  the agent wants to check if a flow is already in progress before pushing a
  new one.

pop_completed_and_invalid():
  Sweeps finished flows off the stack and activates the next PENDING flow.
  Called at the end of each turn before checking get_active_flow().
"""

from __future__ import annotations

from types import MappingProxyType
from uuid import uuid4

from backend.components.flow_stack.parents import BaseFlow
from schemas.ontology import FlowLifecycle


class FlowStack:

    def __init__(self, config: MappingProxyType, flow_classes: dict | None = None):
        self.config = config
        self._stack: list[BaseFlow] = []
        self._max_depth: int = config.get('session', {}).get('max_flow_depth', 8)
        # flow_classes injected at construction so the stack doesn't import flows.py
        self._flow_classes = flow_classes or {}

    def push(self, flow_name: str, plan_id: str | None = None) -> BaseFlow:
        """
        Instantiate a flow class and push it onto the stack.

        Slots are NOT filled here — that happens in PEX via fill_slots_by_label().
        plan_id links the flow to a Plan if it was spawned by one.

        Status on push:
          ACTIVE  — if the stack was empty (this becomes the current flow)
          PENDING — if there's already an active flow (this waits in line)
        """
        if len(self._stack) >= self._max_depth:
            raise RuntimeError(
                f'Flow stack depth limit ({self._max_depth}) exceeded'
            )
        cls = self._flow_classes.get(flow_name)
        if not cls:
            raise ValueError(f'Unknown flow: {flow_name}')
        flow = cls()
        flow.flow_id = str(uuid4())[:8]
        flow.status = FlowLifecycle.ACTIVE.value
        flow.plan_id = plan_id
        if self._stack:
            # Don't preempt an already-active flow
            flow.status = FlowLifecycle.PENDING.value
        self._stack.append(flow)
        return flow

    def pop(self) -> BaseFlow | None:
        """Remove and return the top flow, regardless of status."""
        return self._stack.pop() if self._stack else None

    def peek(self) -> BaseFlow | None:
        """Return the top flow without removing it."""
        return self._stack[-1] if self._stack else None

    def get_active_flow(self) -> BaseFlow | None:
        """
        Return the first ACTIVE flow searching from the top (most recent).
        Returns None if no flow is currently active.
        """
        for entry in reversed(self._stack):
            if entry.status == FlowLifecycle.ACTIVE.value:
                return entry
        return None

    def mark_complete(self, result: dict | None = None) -> BaseFlow | None:
        """Mark the top flow as COMPLETED and store its result."""
        if self._stack:
            top = self._stack[-1]
            top.status = FlowLifecycle.COMPLETED.value
            top.result = result
            return top
        return None

    def mark_invalid(self) -> BaseFlow | None:
        """Mark the top flow as INVALID (abandoned, e.g., user changed intent)."""
        if self._stack:
            top = self._stack[-1]
            top.status = FlowLifecycle.INVALID.value
            return top
        return None

    def pop_completed_and_invalid(self) -> list[BaseFlow]:
        """
        Remove all COMPLETED and INVALID flows from the stack.

        After removal, if the new top flow is PENDING, activate it.
        Returns the list of popped flows (for logging or result propagation).

        Call this at the start of each turn before get_active_flow() to
        ensure the stack reflects only live work.
        """
        popped = []
        remaining = []
        for entry in self._stack:
            if entry.status in (FlowLifecycle.COMPLETED.value,
                                FlowLifecycle.INVALID.value):
                popped.append(entry)
            else:
                remaining.append(entry)
        self._stack = remaining
        # Activate the next waiting flow, if any
        if self._stack and self._stack[-1].status == FlowLifecycle.PENDING.value:
            self._stack[-1].status = FlowLifecycle.ACTIVE.value
        return popped

    def get_pending_flows(self) -> list[BaseFlow]:
        return [e for e in self._stack if e.status == FlowLifecycle.PENDING.value]

    def find_by_name(self, flow_name: str) -> BaseFlow | None:
        """
        Search for an ACTIVE or PENDING flow by flow_type name.

        Does not return COMPLETED or INVALID flows — those are done.
        Searches from top (most recent) to bottom.
        """
        for entry in reversed(self._stack):
            if entry.flow_type == flow_name and entry.status in (
                FlowLifecycle.PENDING.value, FlowLifecycle.ACTIVE.value,
            ):
                return entry
        return None

    def clear(self):
        """Remove all flows. Called on session reset."""
        self._stack.clear()

    @property
    def depth(self) -> int:
        return len(self._stack)

    def to_list(self) -> list[dict]:
        """Serialize all flows for logging or state inspection."""
        return [e.to_dict() for e in self._stack]
