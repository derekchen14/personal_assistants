"""Trace recorder for the §9.2 tool-call trace dev set (changes.md §9.2, Phase 6).

Reads a session dir (`database/sessions/<conversation_id>/`) produced by the NEW orchestrator
path and extracts, per user turn: the ordered (tool_name, key_args) trace, the flows dispatched,
the completion records written, and the final utterance. The raw material is messages.jsonl
(decision 12 — the full orchestrator transcript, tool calls included) plus scratchpad.jsonl
(completion records for click-bypass turns, which never appear as message tool results).

Pure-click turns (decision 13) bypass the loop: messages.jsonl shows only the `[click] ...`
marker and the assistant utterance. The recorder synthesizes the two deterministic calls the
bypass always makes (activate_flow + respond), flagged `bypass: true` so tolerance rules can
treat them as code-guaranteed rather than model-chosen.

Also renders a trace to the human-readable markdown sidecar Derek approves (§9.2 item 3).

CLI (debugging):  python utils/traces/parity/trace_recorder.py <session_dir>
"""

import json
import re
import sys
from pathlib import Path

_NUDGE_PREFIX = 'Your last response had no visible text and no tool calls.'
_WRAP_UP_PREFIX = 'Stop calling tools. Reply to the user now'
_SUMMARY_MARK = '--- CONTEXT SUMMARY'
_MAX_STR = 120


def _truncate(value, depth:int=0):
    """Compact a tool arg for the trace: long strings clipped, nesting capped at 5 levels
    (slot fills sit at args→fields→slots→values→entity-dict, and entity values matter
    for review)."""
    if isinstance(value, str):
        return value if len(value) <= _MAX_STR else value[:_MAX_STR - 3] + '...'
    if isinstance(value, dict):
        if depth >= 5:
            return f'{{...{len(value)} keys}}'
        return {key: _truncate(val, depth + 1) for key, val in value.items()}
    if isinstance(value, list):
        if depth >= 5:
            return f'[...{len(value)} items]'
        return [_truncate(item, depth + 1) for item in value]
    return value


def _new_turn(user:str, kind:str) -> dict:
    return {'user': user, 'kind': kind, 'tool_calls': [], 'dispatched_flows': [],
            'completions': [], 'notes': [], 'utterance': ''}


def _classify_user(content:str) -> tuple[str, str] | None:
    """Map a string user message to (turn kind, display text), or None for loop-control
    messages that belong to the CURRENT turn rather than starting a new one."""
    if content.startswith(_NUDGE_PREFIX) or content.startswith(_WRAP_UP_PREFIX):
        return None
    if content.startswith('[click] '):
        return 'click', content[len('[click] '):]
    if content.startswith('[action] '):
        return 'action', content
    if _SUMMARY_MARK in content[:80]:
        return None
    return 'utterance', content


def _absorb_click(turn:dict):
    """Synthesize the deterministic bypass calls (decision 13): a pure click always runs
    activate_flow on the resolved flow, then the respond tool. Flagged bypass=True."""
    match = re.match(r'dax=(\S+) flow=(\S+) payload=(.*)$', turn['user'])
    dax, flow_name, payload_raw = match.groups()
    payload_keys = sorted(json.loads(payload_raw))
    turn['notes'].append(f'pure click — loop bypass (dax={dax}, payload keys {payload_keys})')
    turn['tool_calls'].append({'tool': 'activate_flow', 'args': {'flow_name': flow_name},
                               'ok': True, 'bypass': True})
    turn['tool_calls'].append({'tool': 'respond', 'args': {'flow_name': flow_name},
                               'ok': True, 'bypass': True})
    turn['dispatched_flows'].append(flow_name)


def _absorb_result(turn:dict, call:dict, raw:str):
    """Fold one tool_result body into its recorded call: success flag, and for activate_flow
    the completion record / pending-question handoff."""
    try:
        body = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        call['ok'] = True  # non-JSON result — treat as plain success payload
        return
    call['ok'] = bool(body.get('_success'))
    if not call['ok']:
        call['error'] = body.get('_error', '')
        if body.get('_message'):
            call['error_message'] = _truncate(body['_message'])
    if call['tool'] == 'activate_flow' and call['ok']:
        turn['dispatched_flows'].append(call['args'].get('flow_name', '?'))
        if body.get('completion'):
            turn['completions'].append(_truncate(body['completion']))
        elif body.get('question'):
            turn['notes'].append(f"flow status={body.get('status')} — asked: "
                                 f"{_truncate(body['question'])}")


def extract_trace(session_dir) -> dict:
    """Parse a session dir into the §9.2 trace shape: ordered tool calls with key args,
    dispatched flows, completion records, and the final utterance, grouped per user turn."""
    session_dir = Path(session_dir)
    lines = (session_dir / 'messages.jsonl').read_text(encoding='utf-8').splitlines()
    messages = [json.loads(line) for line in lines]

    turns = []
    pending = {}  # tool_use_id → recorded call dict (result not yet seen)
    for message in messages:
        content = message['content']
        if message['role'] == 'user' and isinstance(content, str):
            kind_text = _classify_user(content)
            if kind_text is None:
                if turns and content.startswith(_WRAP_UP_PREFIX):
                    turns[-1]['notes'].append('round budget exhausted — forced wrap-up')
                elif turns and content.startswith(_NUDGE_PREFIX):
                    turns[-1]['notes'].append('thinking-only response — nudged once')
                continue
            kind, text = kind_text
            turns.append(_new_turn(text, kind))
            if kind == 'click':
                _absorb_click(turns[-1])
        elif message['role'] == 'user':  # list content = tool results
            for item in content:
                call = pending.pop(item['tool_use_id'], None)
                if call is not None:
                    _absorb_result(turns[-1], call, item['content'])
        elif isinstance(content, str):  # assistant plain text — the turn's reply (last wins)
            if turns:
                turns[-1]['utterance'] = content
        else:  # assistant content blocks: text + tool_use
            for block in content:
                if block['type'] != 'tool_use':
                    continue
                call = {'tool': block['name'], 'args': _truncate(block['input']), 'ok': None}
                turns[-1]['tool_calls'].append(call)
                pending[block['id']] = call

    _attach_bypass_completions(session_dir, turns)
    return {'session': session_dir.name, 'turns': turns}


def _attach_bypass_completions(session_dir, turns:list):
    """Click-bypass dispatches never return through messages.jsonl, so their completion
    records only exist in scratchpad.jsonl — claim the unclaimed ones, in order."""
    scratchpad = session_dir / 'scratchpad.jsonl'
    if not scratchpad.exists():
        return
    entries = [json.loads(line) for line in scratchpad.read_text(encoding='utf-8').splitlines()]
    records = [entry for entry in entries if 'flow' in entry and 'summary' in entry]
    claimed = {(comp.get('flow'), comp.get('summary'))
               for turn in turns for comp in turn['completions']}
    for turn in turns:
        if turn['kind'] != 'click':
            continue
        for record in records:
            key = (record['flow'], record['summary'])
            if record['flow'] in turn['dispatched_flows'] and key not in claimed:
                turn['completions'].append(_truncate(record))
                claimed.add(key)
                break


# ── Markdown sidecar (§9.2 item 3 — the artifact Derek approves) ─────────

def _format_args(args:dict) -> str:
    parts = [f'{key}={json.dumps(val, default=str)}' for key, val in args.items()]
    return ', '.join(parts)


def _quote(text:str) -> str:
    """Blockquote every line so multi-line utterances stay inside the quote block."""
    return '\n'.join(f'> {line}' for line in text.split('\n'))


def render_sidecar(trace:dict, name:str, description:str, recorded_at:str) -> str:
    lines = [f'# Trace — {name}', '', 'APPROVED: [ ]', '',
             f'{description}', '',
             f'Recorded {recorded_at} on the NEW orchestrator path '
             f'(session `{trace["session"]}`).', '']
    for idx, turn in enumerate(trace['turns'], 1):
        lines.append(f'## Turn {idx} — user ({turn["kind"]})')
        lines.append('')
        lines.append(_quote(turn['user']))
        lines.append('')
        if turn['tool_calls']:
            lines.append('Tool calls:')
            for num, call in enumerate(turn['tool_calls'], 1):
                mark = 'bypass' if call.get('bypass') else \
                       ('ok' if call['ok'] else f"ERROR:{call.get('error', 'no result')}")
                lines.append(f'{num:2d}. `{call["tool"]}({_format_args(call["args"])})` — {mark}')
        else:
            lines.append('Tool calls: (none — direct reply)')
        lines.append('')
        if turn['dispatched_flows']:
            lines.append(f'Dispatched flows: {", ".join(turn["dispatched_flows"])}')
            lines.append('')
        for record in turn['completions']:
            meta_keys = sorted(record.get('metadata') or {})
            summary = ' '.join(record['summary'].split())  # flatten newlines/markdown spillover
            lines.append(f'Completion record — **{record["flow"]}**: {summary}')
            lines.append(f'  (metadata keys: {meta_keys})')
            lines.append('')
        for note in turn['notes']:
            lines.append(f'Note: {note}')
            lines.append('')
        lines.append('Final utterance:')
        lines.append('')
        lines.append(_quote(turn['utterance'] or '(none)'))
        lines.append('')
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    print(json.dumps(extract_trace(sys.argv[1]), indent=2))
