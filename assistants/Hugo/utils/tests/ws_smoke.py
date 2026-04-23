"""WebSocket smoke test against a running Hugo backend.

Exercises the SAME path the frontend hits — `ws://localhost:8001/api/v1/ws` —
so we can A/B against the CLI eval (which calls Agent.take_turn directly).

Usage:
    1. Start the backend:    `python -m backend.webserver` (or however you run it)
    2. Run this:             `python utils/tests/ws_smoke.py`

Output: per-turn frame snapshots so you can see what the backend serializes
to the wire. Diff against the frontend `[frame] received` console log to
catch handoff drift.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time

import websockets


WS_URL = 'ws://localhost:8001/api/v1/ws'


# Stamp every run with a unique slug so create probes don't trip the
# duplicate-title confirmation path.
_STAMP = f'smoke{int(time.time())}'


# Probes covering the most common frame shapes the UI cares about.
PROBES = [
    {'utterance': 'hi', 'note': 'chat — text-only frame (no blocks expected)'},
    {'utterance': f'create a draft titled "Smoke Probe {_STAMP}"', 'note': 'create — should yield card block with post_id/title/status'},
    {'utterance': 'find my recent drafts', 'note': 'find — should yield list block with items[]'},
    {'utterance': 'what are my recent drafts', 'note': 'check — narration only, no blocks expected'},
    {'utterance': f'inspect the post titled "Smoke Probe {_STAMP}"', 'note': 'inspect — metrics in metadata, no blocks'},
]


def _summarize(payload:dict) -> dict:
    """Extract the diagnostic fields we care about."""
    frame = payload.get('frame') or {}
    blocks = frame.get('blocks') or []
    return {
        'msg_len': len(payload.get('message', '') or ''),
        'panel': payload.get('panel'),
        'frame_origin': frame.get('origin'),
        'frame_metadata_keys': sorted((frame.get('metadata') or {}).keys()),
        'blocks': [
            {
                'type': b.get('type'),
                'data_keys': sorted((b.get('data') or {}).keys()),
                'location': b.get('location'),
            }
            for b in blocks
        ],
    }


async def _drain_initial(ws):
    """Drain any unprompted frames the backend sends right after connect
    (e.g. the 'welcome' grid refresh). Returns the list of payloads we drained
    so we can log them for diagnostic purposes."""
    drained = []
    try:
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
            drained.append(json.loads(raw))
    except asyncio.TimeoutError:
        pass
    return drained


async def probe():
    async with websockets.connect(WS_URL) as ws:
        # Hand off the username (matches the frontend's connect flow).
        await ws.send(json.dumps({'username': 'smoke_test'}))

        # Drain any post-connect frames before our first probe so the
        # responses we capture are aligned to the utterance that triggered them.
        drained = await _drain_initial(ws)
        if drained:
            print(f'\n=== Post-connect frames (drained, {len(drained)}) ===')
            for entry in drained:
                print(f'    {json.dumps(_summarize(entry), indent=6)}')

        for probe in PROBES:
            print(f'\n=== {probe["note"]} ===')
            print(f'    utterance: {probe["utterance"]!r}')
            await ws.send(json.dumps({'text': probe['utterance']}))

            # Capture every frame the backend emits for this turn, until a
            # quiet period of >2s. Multiple side-effect frames (e.g. grid
            # refresh + chat reply) may all belong to the same probe.
            try:
                first = await asyncio.wait_for(ws.recv(), timeout=60.0)
                turn_payloads = [json.loads(first)]
                while True:
                    try:
                        more = await asyncio.wait_for(ws.recv(), timeout=2.0)
                        turn_payloads.append(json.loads(more))
                    except asyncio.TimeoutError:
                        break
                for idx, payload in enumerate(turn_payloads, start=1):
                    label = f'response[{idx}/{len(turn_payloads)}]'
                    print(f'    {label}: {json.dumps(_summarize(payload), indent=6)}')
            except asyncio.TimeoutError:
                print('    [timeout — backend did not respond within 60s]')


if __name__ == '__main__':
    try:
        asyncio.run(probe())
    except (ConnectionRefusedError, OSError) as ecp:
        print(f'Could not connect to {WS_URL}: {ecp}', file=sys.stderr)
        print('Is the backend running? Try: python -m backend.webserver', file=sys.stderr)
        sys.exit(1)
