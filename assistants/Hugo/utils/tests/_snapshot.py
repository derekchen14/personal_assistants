"""Tiny snapshot-test helper. JSON sidecars under utils/tests/snapshots/.

Re-record with `UPDATE_SNAPSHOTS=1 pytest ...`. Otherwise compares.
Pillar 1 of the regression-prevention plan — keep the implementation
below library-trivial so swapping to syrupy later is mechanical."""

from __future__ import annotations

import json
import os
from pathlib import Path

SNAPSHOT_DIR = Path(__file__).parent / 'snapshots'


def assert_snapshot(actual:dict, name:str):
    """Compare `actual` to SNAPSHOT_DIR/<name>.json. Record when env var set."""
    path = SNAPSHOT_DIR / f'{name}.json'
    serialized = json.dumps(actual, indent=2, sort_keys=True, default=str)
    if os.environ.get('UPDATE_SNAPSHOTS'):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(serialized + '\n')
        return
    if not path.exists():
        raise AssertionError(
            f'No snapshot at {path}. Re-run with UPDATE_SNAPSHOTS=1 to record.'
        )
    expected = path.read_text().rstrip('\n')
    if serialized != expected:
        raise AssertionError(
            f'Snapshot mismatch for {name}. '
            f'Re-run with UPDATE_SNAPSHOTS=1 if intentional.\n'
            f'--- expected\n{expected}\n\n+++ got\n{serialized}'
        )


_VOLATILE_KEYS = frozenset(('flow_id', 'turn_id', 'turn_ids', 'plan_id', 'post_id', 'created_at', 'updated_at'))
_MASK = '<masked>'


def _mask_volatile(obj):
    """Recursively replace volatile values with a fixed sentinel.
    Slot value keys (the *shape*) stay un-masked — that is the point of the harness."""
    if isinstance(obj, dict):
        return {k: (_MASK if k in _VOLATILE_KEYS else _mask_volatile(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_mask_volatile(item) for item in obj]
    return obj


def project_state(agent, result:dict, tool_log:list) -> dict:
    """Build a deterministic structural projection of the post-turn agent state.

    Captures shape (slot fill state, value-count, value key-sets, flow_stack composition,
    frame structure, tool sequence) — NOT the LLM-generated text values that vary turn-to-turn.
    This is what catches Bugs #2-#5 without flaking on legitimate LLM variance."""
    state = agent.world.current_state()
    frame_data = result.get('frame') or {}
    metadata = frame_data.get('metadata') or {}
    blocks = frame_data.get('blocks') or []

    flow_stack = agent.world.flow_stack
    top = flow_stack.get_flow()

    projection = {
        'state': _project_state_obj(state),
        'flow_stack': [_project_flow(entry) for entry in flow_stack._stack],
        'top_flow': _project_top(top),
        'frame': {
            'origin': frame_data.get('origin'),
            'metadata_keys': sorted(metadata.keys()),
            'violation': metadata.get('violation'),
            'missing_slot': metadata.get('missing_slot'),
            'missing_entity': metadata.get('missing_entity'),
            'block_types': [b.get('type') for b in blocks],
            'block_data_keys': [sorted((b.get('data') or {}).keys()) for b in blocks],
            'block_locations': [b.get('location') for b in blocks],
            'has_thoughts': bool(frame_data.get('thoughts')),
            'has_code': bool(frame_data.get('code')),
        },
        'tool_log': [
            # Two known shapes: e2e_agent_evals._install_tool_logger emits
            # {tool, input, success, error} (flat). policy_evals.capture_tool_log
            # emits {name, params, result: {_success, ...}}. Read whichever is present.
            {'tool': entry.get('tool') or entry.get('name'),
             'success': entry['success'] if 'success' in entry
                        else (entry.get('result') or {}).get('_success')}
            for entry in tool_log
        ],
    }
    return _mask_volatile(projection)


def _project_state_obj(state) -> dict:
    if state is None:
        return {}
    return {
        'pred_intent': state.pred_intent,
        'flow_dax': state.pred_flow,
        'keep_going': state.keep_going,
        'has_issues': state.has_issues,
        'has_plan': state.has_plan,
        'natural_birth': state.natural_birth,
        'active_post_set': state.active_post is not None,
    }


def _project_flow(entry) -> dict:
    return {
        'flow_type': entry.flow_type,
        'parent_type': entry.parent_type,
        'status': entry.status,
        'is_newborn': entry.is_newborn,
        'is_uncertain': entry.is_uncertain,
        'interjected': entry.interjected,
        'slot_shape': _slot_shape(entry),
    }


def _project_top(flow) -> dict:
    if flow is None:
        return {}
    return {
        'flow_type': flow.flow_type,
        'parent_type': flow.parent_type,
        'entity_slot': flow.entity_slot,
        'is_filled': flow.is_filled(),
    }


def _slot_shape(flow) -> dict:
    shape = {}
    for name, slot in flow.slots.items():
        info = {
            'priority': slot.priority,
            'criteria': slot.criteria,
            'filled': slot.filled,
        }
        values = getattr(slot, 'values', None)
        if values is not None:
            info['value_count'] = len(values)
            if values and isinstance(values[0], dict):
                info['value_keys'] = sorted(values[0].keys())
        if hasattr(slot, 'level'):
            info['level_set'] = slot.level is not None
        shape[name] = info
    return shape
