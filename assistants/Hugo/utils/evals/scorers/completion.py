"""P1 completion scorer (step_1_evals.md — completion scorer, primary-flow only).

A turn *completes* iff a real reply came back AND the agent behaved in the right MODE for the turn's
label. The label is now `{intent, stack:[{flow,dax},...]}` plus a flat `ambiguity` (a level or null):
  - **ambiguous turn** (`ambiguity` is a level): the agent must DECLARE ambiguity — ask, not guess. We
    pass the live handler's `agent.ambiguity.level` as `declared_level` (`''` when clear); the eval label
    needs no ambiguity object of its own (the runtime's `ambiguity.present()`/`.level` is separate).
  - **plan turn** (multi-flow stack, the decomposition): a coarse P1 pass on any real reply — the agent
    proposes/decomposes rather than running a single flow, so we don't match one origin here.
  - **normal turn** (one-flow stack): the primary flow (artifact origin, set to flow.name() in
    policies/base.py) matches that flow — no trace parsing; the full trajectory is the Traces tier's job.

The "didn't really finish" sentinels: the loop give-up message is the canonical _FALLBACK_MESSAGE
(backend.modules.pex); the crash message has no named constant (an inline literal at agent.py:51),
so it is mirrored here; the timeout literal is set by the eval runner on a hung turn.
"""
import sys
from pathlib import Path

_HUGO_ROOT = Path(__file__).resolve().parents[3]
if str(_HUGO_ROOT) not in sys.path:
    sys.path.insert(0, str(_HUGO_ROOT))

from backend.modules.pex import _FALLBACK_MESSAGE

_CRASH_FALLBACK = 'Something went wrong on my end. Please try again.'   # mirrors agent.py:51
_TIMEOUT = '(turn timed out)'
FALLBACKS = (_CRASH_FALLBACK, _FALLBACK_MESSAGE, _TIMEOUT)


def is_completed(result:dict, turn:dict, declared_level:str='') -> tuple[bool, str]:
    """Returns (completed, reason). Order matters: the fallback/empty checks run before reading the
    artifact, because the crash path returns artifact=None. `declared_level` is the live handler's
    `agent.ambiguity.level` (`''` when no ambiguity was declared)."""
    message = result['message']
    if message in FALLBACKS:
        return False, f'fallback: {message[:40]!r}'
    if not message.strip():
        return False, 'empty reply'

    level = turn['ambiguity']                     # a level string, or None (not ambiguous)
    if level is not None:                         # ambiguous turn: the agent must ask, not guess
        if not declared_level:
            return False, f'expected {level!r} ambiguity, none declared'
        if declared_level != level:
            return True, f'ok (declared {declared_level!r}, expected {level!r})'
        return True, 'ok'

    stack = turn['labels']['stack']
    if len(stack) > 1:                            # plan turn: coarse pass — the agent proposes/decomposes
        return True, 'ok (plan)'
    origin = result['artifact']['origin']         # normal turn: primary flow must match
    expected_flow = stack[0]['flow']
    if origin != expected_flow:
        return False, f'expected {expected_flow!r}, got {origin!r}'
    return True, 'ok'
