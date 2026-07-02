"""P1 completion scorer (step_1_evals.md — completion scorer, primary-flow only).

A turn *completes* iff a real reply came back AND the primary flow matched what the case expects.
The primary flow is the artifact's origin (set to flow.name() in policies/base.py), so completion
needs no trace parsing — the full trajectory is the Observability Traces tier's job.

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


def is_completed(result:dict, expected_flow:str) -> tuple[bool, str]:
    """Returns (completed, reason). Order matters: the fallback/empty checks run before reading
    the artifact, because the crash path returns artifact=None."""
    message = result['message']
    if message in FALLBACKS:
        return False, f'fallback: {message[:40]!r}'
    if not message.strip():
        return False, 'empty reply'
    origin = result['artifact']['origin']
    if origin != expected_flow:
        return False, f'expected {expected_flow!r}, got {origin!r}'
    return True, 'ok'
