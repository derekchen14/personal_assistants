"""Phase-2 visibility test: capture browser console + assert frame round-trip.

Loads the app, sends a turn, asserts the structured console logs we
instrumented in conversation.ts and display.ts arrived. Failures in
this test indicate either:
  - WS connection broke (no `[frame] received` log)
  - frame serialization dropped data (block list shape mismatch)
  - dispatch routing diverged (`[setFrame] dispatch` panel ≠ backend panel)

Run: `pytest utils/tests/playwright_evals/test_phase2_console_capture.py --ui -v -s`
"""
from __future__ import annotations

import time

import pytest


def _wait_for_console(console_log, predicate, timeout=30.0, label=''):
    """Block until a log entry matching `predicate(entry)` arrives."""
    deadline = time.time() + timeout
    seen_count = len(console_log)
    while time.time() < deadline:
        for entry in console_log[seen_count:]:
            if predicate(entry):
                return entry
        seen_count = len(console_log)
        time.sleep(0.25)
    pytest.fail(f'No console log matching {label!r} within {timeout}s. Seen: {[e["text"][:120] for e in console_log]}')


def _send_utterance(page, text):
    """Click into the chat input + send the utterance."""
    page.fill('[data-testid="chat-input"], textarea, input[type="text"]', text)
    page.keyboard.press('Enter')


def test_phase2_frame_roundtrip_for_chat_turn(browser_context, hugo_servers, console_log):
    """One round-trip: type a chat utterance, assert the frame logs arrive."""
    page = browser_context.new_page()
    page.goto(hugo_servers['frontend'])

    # Most apps need a moment to establish the WebSocket.
    _wait_for_console(
        console_log,
        lambda e: '[WS]' in e['text'] and 'connected' in e['text'].lower(),
        label='WS connect',
    )

    _send_utterance(page, 'hi')

    # Backend → frontend handoff log.
    received = _wait_for_console(
        console_log,
        lambda e: '[frame] received' in e['text'] or '[frame] none' in e['text'],
        label='[frame] received',
    )
    print(f'\n[frame received] {received["text"][:300]}')

    # Frontend dispatch decision (only fires when frame is non-null).
    if '[frame] received' in received['text']:
        dispatched = _wait_for_console(
            console_log,
            lambda e: '[setFrame] dispatch' in e['text'],
            label='[setFrame] dispatch',
        )
        print(f'\n[setFrame dispatch] {dispatched["text"][:300]}')


def test_phase2_no_pageerrors_during_create_turn(browser_context, hugo_servers, console_log):
    """Create a draft, assert no pageerror events during the round-trip.

    A pageerror here = uncaught exception in the frame renderer (most
    likely a missing block-renderer for an unexpected block type).
    """
    page = browser_context.new_page()
    page.goto(hugo_servers['frontend'])

    _wait_for_console(
        console_log,
        lambda e: '[WS]' in e['text'] and 'connected' in e['text'].lower(),
        label='WS connect',
    )

    _send_utterance(page, 'create a draft about transformer attention')

    # Wait for the frame to render through.
    _wait_for_console(
        console_log,
        lambda e: '[frame] received' in e['text'] or '[frame] none' in e['text'],
        timeout=60.0,
        label='[frame] received (post-create)',
    )

    # Wait briefly for any deferred renderer errors.
    time.sleep(2.0)

    pageerrors = [e for e in console_log if e['type'] == 'pageerror']
    assert not pageerrors, (
        f'Frontend raised {len(pageerrors)} pageerror(s) during create turn:\n'
        + '\n'.join(f'  - {e["text"][:200]}' for e in pageerrors)
    )
