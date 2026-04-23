"""Step-12 audit probe — did the skill call save_findings?

Seeds the agent with the Vision post, installs a tool-dispatch wrapper
that captures every tool call with its args + success flag, runs just
step 12's utterance, and prints the full trajectory plus the final frame.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
_HUGO_ROOT = Path(__file__).resolve().parents[2]
if str(_HUGO_ROOT) not in sys.path:
    sys.path.insert(0, str(_HUGO_ROOT))

from dotenv import load_dotenv
load_dotenv(_HUGO_ROOT / '.env')

from schemas.config import load_config
from backend.agent import Agent
import backend.agent as agent_mod


POST_TITLE = 'Using Multi-modal Models to Improve AI Agents'
UTTERANCE = 'Check if the multi-modal models post matches my usual writing style'
DAX = '{13A}'


def main():
    orig_load = agent_mod.load_config
    agent_mod.load_config = lambda: load_config(overrides={'debug': True})
    agent = Agent(username='test_user')
    agent_mod.load_config = orig_load

    from backend.utilities.services import PostService
    svc = PostService()
    preview = svc.list_preview().get('items', [])
    post_id = None
    for ent in preview:
        if ent.get('title', '').lower() == POST_TITLE.lower():
            post_id = ent['post_id']
            break
    if not post_id:
        print(f'POST_NOT_FOUND: {POST_TITLE!r}. Run Vision scenario first.')
        return

    from backend.components.dialogue_state import DialogueState
    state = DialogueState(agent.config)
    state.active_post = post_id
    agent.world.insert_state(state)

    meta = svc.read_metadata(post_id)
    title = meta.get('title', '')
    sections = meta.get('section_ids', [])
    ctx = agent.world.context
    ctx.add_turn('User', f'Create a new post about {title}', turn_type='utterance')
    ctx.add_turn('Agent', f'Created draft "{title}" with ID {post_id}.', turn_type='utterance')

    tool_trace = []
    original_dispatch = agent.pex._dispatch_tool
    def wrapped(tool_name, tool_input):
        result = original_dispatch(tool_name, tool_input)
        tool_trace.append({
            'tool': tool_name,
            'input_keys': sorted(tool_input.keys()),
            'input_preview': {k: (str(v)[:120] if not isinstance(v, (int, float, bool)) else v) for k, v in tool_input.items()},
            'success': result.get('_success', True),
            'error': result.get('_error'),
            'message': result.get('_message', '')[:200] if result.get('_message') else '',
        })
        return result
    agent.pex._dispatch_tool = wrapped

    turn_result = agent.take_turn(UTTERANCE, dax=DAX)

    print('=' * 70)
    print('AUDIT PROBE — did the skill call save_findings?')
    print('=' * 70)
    print()
    print(f'Tool calls: {len(tool_trace)}')
    for i, entry in enumerate(tool_trace):
        marker = '✓' if entry['success'] else '✗'
        print(f'  [{i+1}] {marker} {entry["tool"]}({", ".join(entry["input_keys"])})')
        if not entry['success']:
            print(f'      error: {entry["error"]} | {entry["message"]}')
    print()
    print('save_findings called:', any(t['tool'] == 'save_findings' for t in tool_trace))
    print()

    frame = turn_result.get('frame') or {}
    print(f'Frame origin: {frame.get("origin")!r}')
    print(f'Frame metadata: {frame.get("metadata")}')
    print(f'Frame blocks: {[b.get("type") for b in (frame.get("blocks") or [])]}')
    print(f'Frame thoughts (first 300): {(frame.get("thoughts") or "")[:300]}')
    print()
    print(f'state.has_issues: {agent.world.current_state().has_issues}')
    print(f'flow_stack (active): {[f.flow_type for f in agent.world.flow_stack._stack if f.status == "Active"]}')
    print(f'flow_stack (all): {[(f.flow_type, f.status) for f in agent.world.flow_stack._stack]}')

    agent.close()


if __name__ == '__main__':
    main()
