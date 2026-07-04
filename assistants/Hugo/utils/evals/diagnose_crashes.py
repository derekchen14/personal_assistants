"""Diagnostic script — exercises specific crash hypotheses WITHOUT LLM calls.

Hypotheses to verify:
  H1: pex.py:228 — thoughts.strip() crashes when artifact.thoughts is None
  H2: nlu.py:410-414 — slot-fill schema violation falls through to KeyError
  H3: revise.py:218 — audit completion crashes when scratchpad summary is missing

Run: python -m utils.evals.diagnose_crashes
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

# Ensure repo root on path for `backend.*` imports
HUGO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HUGO_ROOT))
sys.path.insert(0, str(HUGO_ROOT.parents[1]))  # personal_assistants root for `schemas`


def header(text:str):
    print(f'\n{"="*70}\n{text}\n{"="*70}')


def H1_thoughts_none_crash():
    """pex.py:228 — `thoughts.strip() == last_user.strip()` when thoughts is None"""
    header('H1: pex.py:228 — thoughts None AttributeError')
    from backend.components.task_artifact import TaskArtifact

    # Construct an artifact that has block data but no thoughts.
    # The has_data check (L223) passes because of block_data, but L228 still runs.
    artifact = TaskArtifact(origin='polish')
    artifact.add_block({'type': 'card', 'data': {'post_id': 'p1', 'title': 'hi'}})
    print(f'artifact.thoughts = {artifact.thoughts!r}  (None or "")?')

    # Simulate the relevant slice of _validate_artifact
    last_user = 'polish that post'
    thoughts = artifact.thoughts  # this is what pex.py:222 grabs
    block_data = {'post_id': 'p1', 'title': 'hi'}
    has_data = ('default' in [] or block_data or artifact.thoughts or artifact.data)
    print(f'has_data = {bool(has_data)}  →  will reach L228')

    try:
        result = (thoughts.strip() == last_user.strip())
        print(f'NO CRASH — thoughts.strip() returned: {result}')
        print('=> thoughts must be empty string, not None. Hypothesis partially wrong.')
    except AttributeError as ecp:
        print(f'CONFIRMED CRASH: {type(ecp).__name__}: {ecp}')
        print('=> pex.py:228 needs `thoughts and thoughts.strip() == ...` guard')


def H2_slot_fill_fallthrough():
    """nlu.py:410-414 — pred_slots without 'slots' key falls through to KeyError"""
    header("H2: nlu.py:410-414 — slot-fill fallthrough KeyError")

    # Simulate the LLM returning a payload that violates the schema
    pred_slots = {'reasoning': 'I am confused', 'foo': 'bar'}  # no 'slots' key
    print(f'pred_slots = {pred_slots}')
    print('Walking through nlu.py:410-414 logic...')

    try:
        # nlu.py:410-411 — log warning, NO RETURN
        if 'slots' not in pred_slots:
            print(f'  [warning logged] schema violation: missing "slots"')
        # nlu.py:414 — KeyError waiting to happen
        cleaned = pred_slots['slots']
        print(f'NO CRASH — got: {cleaned}')
    except KeyError as ecp:
        print(f'CONFIRMED CRASH: KeyError: {ecp}')
        print('=> nlu.py:410-414 needs `return` after the warning log')


def H3_audit_summary_none():
    """revise.py:218 — read_scratchpad(step['name'])['summary'] when entry is None"""
    header("H3: revise.py:218 — audit summary None")

    # Simulate the audit completion path
    class FakeMemory:
        def read_scratchpad(self, key:str):
            return None  # delegate hasn't written its summary yet

    memory = FakeMemory()
    steps = [{'name': 'polish'}, {'name': 'simplify'}]
    reports = {}

    try:
        for step in steps:
            reports[step['name']] = memory.read_scratchpad(step['name'])['summary']
        print(f'NO CRASH — reports: {reports}')
    except TypeError as ecp:
        print(f'CONFIRMED CRASH: {type(ecp).__name__}: {ecp}')
        print('=> revise.py:218 needs None guard on read_scratchpad result')


def H4_thoughts_actually_set():
    """Cross-check: in real usage, do polish/refine artifacts ALWAYS set thoughts?"""
    header('H4: Cross-check — does TaskArtifact() default thoughts to None or ""?')
    from backend.components.task_artifact import TaskArtifact

    # Default construction
    a = TaskArtifact()
    print(f'TaskArtifact() default thoughts: {a.thoughts!r}')

    # _guard_entity path returns TaskArtifact(flow.name())
    a = TaskArtifact('polish')
    print(f"TaskArtifact('polish') thoughts: {a.thoughts!r}")

    # When ambiguity is declared → return empty TaskArtifact (no thoughts)
    # This is exactly what polish_policy does on ambiguity (revise.py:147)
    a_no_thoughts = TaskArtifact(origin='polish')
    a_no_thoughts.add_block({'type': 'card', 'data': {'post_id': 'p1'}})
    print(f'origin=polish + card block, thoughts: {a_no_thoughts.thoughts!r}')


def main():
    runners = [H4_thoughts_actually_set, H1_thoughts_none_crash, H2_slot_fill_fallthrough, H3_audit_summary_none]
    for fn in runners:
        try:
            fn()
        except Exception:
            print(f'DIAGNOSTIC ITSELF CRASHED in {fn.__name__}:')
            traceback.print_exc()


if __name__ == '__main__':
    main()
