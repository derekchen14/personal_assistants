"""Tiny snapshot-test helper. JSON sidecars under evaluation_suite/_evals/snapshots/.

Re-record with `UPDATE_SNAPSHOTS=1 pytest ...`. Otherwise compares.
Pillar 1 of the regression-prevention plan — keep the implementation
below library-trivial so swapping to syrupy later is mechanical."""

from __future__ import annotations

import json
import os
from pathlib import Path

SNAPSHOT_DIR = Path(__file__).parent / '_evals' / 'snapshots'


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


_VOLATILE_KEYS = frozenset(('flow_id', 'turn_id', 'turn_ids', 'post_id', 'created_at', 'updated_at'))
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
    artifact structure, tool sequence) — NOT the LLM-generated text values that vary turn-to-turn.
    This is what catches Bugs #2-#5 without flaking on legitimate LLM variance."""
    state = agent.world.current_state()
    artifact_data = result.get('artifact') or {}
    parts = artifact_data.get('parts') or []
    blocks = artifact_data.get('blocks') or []
    data_part = next((p.get('data') for p in parts if 'data' in p), {}) or {}
    has_text_kind = lambda kind: any(
        'text' in p and (p.get('metadata') or {}).get('kind') == kind for p in parts
    )

    flow_stack = agent.world.flow_stack
    top = flow_stack.get_flow()

    projection = {
        'state': _project_state_obj(state),
        'flow_stack': [_project_flow(entry) for entry in flow_stack._stack],
        'top_flow': _project_top(top),
        'artifact': {
            'origin': artifact_data.get('origin'),
            'parts_keys': sorted(data_part.keys()),
            'violation': data_part.get('violation'),
            'missing': data_part.get('missing'),
            'entity': data_part.get('entity'),
            'reason': data_part.get('reason'),
            'block_types': [b.get('type') for b in blocks],
            'block_data_keys': [sorted((b.get('data') or {}).keys()) for b in blocks],
            'block_panels': [b.get('panel') for b in blocks],
            'has_thoughts': has_text_kind('thoughts'),
            'has_code': has_text_kind('code'),
        },
        'tool_log': [
            # Tolerate both call-log shapes: {tool, success} (flat) or
            # {name, result: {_success, ...}} (wrapped). Read whichever is present.
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
