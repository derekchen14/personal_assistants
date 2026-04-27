from __future__ import annotations

from types import MappingProxyType
from uuid import uuid4

from backend.components.flow_stack.parents import BaseFlow
from schemas.ontology import FlowLifecycle


class FlowStack:

    def __init__(self, config:MappingProxyType, flow_classes:dict|None=None):
        self.config = config
        self._stack: list[BaseFlow] = []
        self._max_depth: int = config.get('session', {}).get('max_flow_depth', 8)
        self._flow_classes = flow_classes or {}

    # ── Public API ──────────────────────────────────────────────────

    def stackon(self, flow_name:str, plan_id:str|None=None) -> BaseFlow:
        """Push a flow on top of the stack. The current flow stays below and resumes after the new flow completes.
        Also carry over the grounding entity when parent flow and child flow share the same entity slot. """
        curr_flow = self._stack[-1] if self._stack else None
        new_flow = self._push(flow_name, plan_id)
        if curr_flow and curr_flow.entity_slot == new_flow.entity_slot:
            src = curr_flow.slots.get(curr_flow.entity_slot)
            dst = new_flow.slots.get(new_flow.entity_slot)
            for entity in src.values:
                payload = entity.copy()
                if any(payload.get(k) for k in ('post', 'sec', 'snippet')):
                    dst.add_one(**payload)
        return new_flow

    def fallback(self, flow_name:str) -> BaseFlow:
        """Replace the current flow. Marks it Invalid and transfers matching slot values to the new flow."""
        old_flow, new_flow = self._stack[-1], self._push(flow_name)
        old_flow.status = FlowLifecycle.INVALID.value
        for slot_name, slot in old_flow.slots.items():
            if slot_name in new_flow.slots and slot.filled:
                new_flow.fill_slot_values({slot_name: slot.to_dict()})
        return new_flow

    def peek(self) -> BaseFlow|None:
        """Top of stack without removing."""
        return self._stack[-1] if self._stack else None

    def get_flow(self, status:str|None=None) -> BaseFlow|None:
        """Top-of-stack flow, optionally filtered by lifecycle status
        (e.g. 'Active', 'Pending')."""
        for entry in reversed(self._stack):
            if status is None or entry.status == status:
                return entry
        return None

    def find_by_name(self, flow_name:str) -> BaseFlow|None:
        """Search the stack for an active/pending flow by name."""
        for entry in reversed(self._stack):
            if entry.flow_type == flow_name and entry.status not in (
                FlowLifecycle.COMPLETED.value, FlowLifecycle.INVALID.value,
            ):
                return entry
        return None

    def pop_completed(self) -> list[BaseFlow]:
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

    def _push(self, flow_name:str, plan_id:str|None=None) -> BaseFlow:
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

    def _pop(self) -> BaseFlow|None:
        return self._stack.pop() if self._stack else None
