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
        self._flow_classes = flow_classes or {}

    def push(self, flow_name: str, plan_id: str | None = None) -> BaseFlow:
        """Instantiate and push a flow as Active. Slots are NOT filled here."""
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
        self._stack.append(flow)
        return flow

    def pop(self) -> BaseFlow | None:
        return self._stack.pop() if self._stack else None

    def peek(self) -> BaseFlow | None:
        return self._stack[-1] if self._stack else None

    def get_flow(self, status:str|None=None) -> BaseFlow | None:
        """Top-of-stack flow. Pass status to filter (e.g. 'Active', 'Pending')."""
        for entry in reversed(self._stack):
            if status is None or entry.status == status:
                return entry
        return None

    def mark_complete(self) -> BaseFlow | None:
        if self._stack:
            top = self._stack[-1]
            top.status = FlowLifecycle.COMPLETED.value
            return top
        return None

    def mark_invalid(self) -> BaseFlow | None:
        if self._stack:
            top = self._stack[-1]
            top.status = FlowLifecycle.INVALID.value
            return top
        return None

    def pop_completed_and_invalid(self) -> list[BaseFlow]:
        popped = []
        remaining = []
        for entry in self._stack:
            if entry.status in (FlowLifecycle.COMPLETED.value,
                                FlowLifecycle.INVALID.value):
                popped.append(entry)
            else:
                remaining.append(entry)
        self._stack = remaining
        if self._stack and self._stack[-1].status == FlowLifecycle.PENDING.value:
            self._stack[-1].status = FlowLifecycle.ACTIVE.value
        return popped

    def get_pending_flows(self) -> list[BaseFlow]:
        return [e for e in self._stack if e.status == FlowLifecycle.PENDING.value]

    def find_by_name(self, flow_name: str) -> BaseFlow | None:
        for entry in reversed(self._stack):
            if entry.flow_type == flow_name and entry.status not in (
                FlowLifecycle.COMPLETED.value, FlowLifecycle.INVALID.value,
            ):
                return entry
        return None

    def clear(self):
        self._stack.clear()

    @property
    def depth(self) -> int:
        return len(self._stack)

    def to_list(self) -> list[dict]:
        return [e.to_dict() for e in self._stack]
