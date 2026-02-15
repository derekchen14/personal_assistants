"""Flow Stack — LIFO stack with lifecycle: Pending → Active → Completed | Invalid."""

from __future__ import annotations

from types import MappingProxyType
from uuid import uuid4

from schemas.ontology import FlowLifecycle


class FlowEntry:

    def __init__(self, flow_name: str, dax: str, intent: str,
                 slots: dict | None = None, plan_id: str | None = None):
        self.flow_id: str = str(uuid4())[:8]
        self.flow_name = flow_name
        self.dax = dax
        self.intent = intent
        self.status: str = FlowLifecycle.ACTIVE.value
        self.slots: dict = slots or {}
        self.plan_id: str | None = plan_id
        self.turn_ids: list[str] = []
        self.result: dict | None = None

    def to_dict(self) -> dict:
        return {
            'flow_id': self.flow_id,
            'flow_name': self.flow_name,
            'dax': self.dax,
            'intent': self.intent,
            'status': self.status,
            'slots': self.slots,
            'plan_id': self.plan_id,
            'turn_ids': self.turn_ids,
        }


class FlowStack:

    def __init__(self, config: MappingProxyType):
        self.config = config
        self._stack: list[FlowEntry] = []
        self._max_depth: int = config.get('session', {}).get('max_flow_depth', 8)

    def push(self, flow_name: str, dax: str, intent: str,
             slots: dict | None = None, plan_id: str | None = None) -> FlowEntry:
        if len(self._stack) >= self._max_depth:
            raise RuntimeError(
                f'Flow stack depth limit ({self._max_depth}) exceeded'
            )
        entry = FlowEntry(flow_name, dax, intent, slots, plan_id)
        if self._stack:
            entry.status = FlowLifecycle.PENDING.value
        self._stack.append(entry)
        return entry

    def pop(self) -> FlowEntry | None:
        return self._stack.pop() if self._stack else None

    def peek(self) -> FlowEntry | None:
        return self._stack[-1] if self._stack else None

    def get_active_flow(self) -> FlowEntry | None:
        for entry in reversed(self._stack):
            if entry.status == FlowLifecycle.ACTIVE.value:
                return entry
        return None

    def mark_complete(self, result: dict | None = None) -> FlowEntry | None:
        if self._stack:
            top = self._stack[-1]
            top.status = FlowLifecycle.COMPLETED.value
            top.result = result
            return top
        return None

    def mark_invalid(self) -> FlowEntry | None:
        if self._stack:
            top = self._stack[-1]
            top.status = FlowLifecycle.INVALID.value
            return top
        return None

    def pop_completed_and_invalid(self) -> list[FlowEntry]:
        """Pop all terminal flows. Auto-activates new top if Pending."""
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

    def get_pending_flows(self) -> list[FlowEntry]:
        return [e for e in self._stack if e.status == FlowLifecycle.PENDING.value]

    def find_by_name(self, flow_name: str) -> FlowEntry | None:
        for entry in reversed(self._stack):
            if entry.flow_name == flow_name and entry.status in (
                FlowLifecycle.PENDING.value, FlowLifecycle.ACTIVE.value,
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
