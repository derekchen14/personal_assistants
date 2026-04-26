"""Pytest configuration for the Playwright UI tier (Part 4, Phase 3).

Gated on the ``--ui`` CLI flag so CI default-skips the whole directory. Spins up backend (port 8001)
+ frontend (port 5174) only if they are not already running; tears them down on session end only if
this fixture started them.
"""

import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest


HUGO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_PORT = 8001
FRONTEND_PORT = 5174
FRONTEND_URL = f'http://localhost:{FRONTEND_PORT}'
BACKEND_URL = f'http://localhost:{BACKEND_PORT}'


# ── CLI flag ──────────────────────────────────────────────────────────

def pytest_addoption(parser):
    group = parser.getgroup('playwright_evals')
    group.addoption(
        '--ui',
        action='store_true',
        default=False,
        help='Run the Playwright UI tier (spins up backend+frontend if needed).',
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption('--ui'):
        return
    skip_marker = pytest.mark.skip(reason='Playwright UI tier gated on --ui flag')
    here = Path(__file__).resolve().parent
    for item in items:
        if Path(str(item.fspath)).resolve().is_relative_to(here):
            item.add_marker(skip_marker)


# ── Port helpers ──────────────────────────────────────────────────────

def _port_open(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.5)
    try:
        return sock.connect_ex(('127.0.0.1', port)) == 0
    finally:
        sock.close()


def _wait_for_http(url, timeout=30.0):
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception as ecp:
            last_error = ecp
            time.sleep(0.5)
    raise RuntimeError(f'{url} did not serve 200 within {timeout}s: {last_error!r}')


# ── Server lifecycle ──────────────────────────────────────────────────

@pytest.fixture(scope='session')
def hugo_servers(pytestconfig):
    """Ensure backend + frontend are reachable. Start them only if absent."""
    if not pytestconfig.getoption('--ui'):
        yield None
        return

    started = []
    try:
        if not _port_open(BACKEND_PORT):
            proc = subprocess.Popen(
                [str(HUGO_ROOT / 'init_backend.sh')],
                cwd=str(HUGO_ROOT),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            started.append(('backend', proc))
            _wait_for_http(f'{BACKEND_URL}/health', timeout=45)

        if not _port_open(FRONTEND_PORT):
            proc = subprocess.Popen(
                [str(HUGO_ROOT / 'init_frontend.sh')],
                cwd=str(HUGO_ROOT),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            started.append(('frontend', proc))
            _wait_for_http(FRONTEND_URL, timeout=60)
        else:
            _wait_for_http(FRONTEND_URL, timeout=10)

        yield {'backend': BACKEND_URL, 'frontend': FRONTEND_URL}
    finally:
        for label, proc in started:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


# ── Playwright import guard ───────────────────────────────────────────

def _import_playwright():
    try:
        from playwright.sync_api import sync_playwright
        return sync_playwright
    except ImportError:
        pytest.skip(
            'pytest-playwright not installed. Run: '
            'uv pip install pytest-playwright && playwright install chromium'
        )


@pytest.fixture(scope='session')
def playwright_instance(pytestconfig):
    if not pytestconfig.getoption('--ui'):
        yield None
        return
    sync_playwright = _import_playwright()
    with sync_playwright() as pw:
        yield pw


@pytest.fixture(scope='session')
def browser(playwright_instance, pytestconfig):
    if not pytestconfig.getoption('--ui'):
        yield None
        return
    headless = os.environ.get('PLAYWRIGHT_HEADLESS', '1') != '0'
    browser_obj = playwright_instance.chromium.launch(headless=headless)
    try:
        yield browser_obj
    finally:
        browser_obj.close()


@pytest.fixture
def browser_context(browser, hugo_servers, pytestconfig):
    """Fresh isolated context per test."""
    if not pytestconfig.getoption('--ui'):
        yield None
        return
    context = browser.new_context()
    yield context
    context.close()


@pytest.fixture
def network_log(browser_context, pytestconfig):
    """Accumulates the most recent network responses during a test."""
    if not pytestconfig.getoption('--ui'):
        yield []
        return

    log = []

    def on_response(response):
        log.append({
            'timestamp': time.strftime('%H:%M:%S'),
            'method': response.request.method,
            'url': response.url,
            'status': response.status,
        })

    browser_context.on('response', on_response)
    yield log


@pytest.fixture
def console_log(browser_context, pytestconfig):
    """Captures browser-side console.log / console.error events.

    The Phase-2 logging instrumentation in the frontend (conversation.ts `[frame] received`,
    display.ts `[setFrame] dispatch`) emits structured JSON-ish messages we can assert on. Diff
    against the backend-side log lines (`AGENT-FRAME:`, `WS-HANDOFF:`) to spot serialization gaps.
    """
    if not pytestconfig.getoption('--ui'):
        yield []
        return

    log = []

    def on_console(msg):
        try:
            text = msg.text
        except Exception:
            text = '<unavailable>'
        log.append({
            'timestamp': time.strftime('%H:%M:%S'),
            'type': msg.type,
            'text': text,
        })

    def on_pageerror(error):
        log.append({
            'timestamp': time.strftime('%H:%M:%S'),
            'type': 'pageerror',
            'text': str(error),
        })

    # The browser_context.on hooks fire for ALL pages opened in the context.
    browser_context.on('page', lambda page: page.on('console', on_console))
    browser_context.on('page', lambda page: page.on('pageerror', on_pageerror))
    yield log
