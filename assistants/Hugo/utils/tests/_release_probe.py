"""Step-14 release probe — does the skill publish cleanly via MT1T?

Seeds the agent with the existing Vision post on disk, instruments tool
dispatch, runs just the release utterance, and reports:
  - Every tool call (name + args + success/error)
  - The final frame (origin, blocks, metadata, thoughts)
  - Whether the MT1T draft file landed on disk
  - The skill's JSON response (parsed if possible)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
_HUGO_ROOT = Path(__file__).resolve().parents[2]
if str(_HUGO_ROOT) not in sys.path:
    sys.path.insert(0, str(_HUGO_ROOT))

from dotenv import load_dotenv
import os
load_dotenv(_HUGO_ROOT / '.env')
os.environ['HUGO_EVAL_MODE'] = '1'

from schemas.config import load_config
from backend.agent import Agent
import backend.agent as agent_mod


POST_TITLE = 'Using Multi-modal Models to Improve AI Agents'
UTTERANCE = 'Publish the multi-modal models post'
DAX = '{04A}'


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
    ctx = agent.world.context
    ctx.add_turn('User', f'Create a new post about {title}', turn_type='utterance')
    ctx.add_turn('Agent', f'Created draft "{title}" with ID {post_id}.', turn_type='utterance')

    mt1t_drafts = Path(os.getenv('MT1T_REPO_PATH', '')) / '_drafts'
    before_files = set(mt1t_drafts.glob('*.md')) if mt1t_drafts.is_dir() else set()

    tool_trace = []
    original_dispatch = agent.pex._dispatch_tool
    def wrapped(tool_name, tool_input):
        result = original_dispatch(tool_name, tool_input)
        tool_trace.append({
            'tool': tool_name,
            'input': {k: (str(v)[:200] if not isinstance(v, (int, float, bool)) else v) for k, v in tool_input.items()},
            'success': result.get('_success', True),
            'error': result.get('_error'),
            'message': (result.get('_message') or '')[:200],
        })
        return result
    agent.pex._dispatch_tool = wrapped

    turn_result = agent.take_turn(UTTERANCE, dax=DAX)

    after_files = set(mt1t_drafts.glob('*.md')) if mt1t_drafts.is_dir() else set()
    new_files = after_files - before_files

    print('=' * 70)
    print('RELEASE PROBE')
    print('=' * 70)
    print(f'Post: {post_id} | {title}')
    print(f'Utterance: {UTTERANCE}')
    print()
    print(f'Tool calls ({len(tool_trace)}):')
    for i, entry in enumerate(tool_trace, 1):
        marker = '✓' if entry['success'] else '✗'
        args = ', '.join(f'{k}={v!r}' for k, v in entry['input'].items())
        print(f'  [{i}] {marker} {entry["tool"]}({args})')
        if not entry['success']:
            print(f'      error: {entry["error"]} | {entry["message"]}')
    print()

    frame = turn_result.get('frame') or {}
    print(f'Frame origin:    {frame.get("origin")!r}')
    print(f'Frame metadata:  {frame.get("metadata")}')
    print(f'Frame blocks:    {[b.get("type") for b in (frame.get("blocks") or [])]}')
    for b in frame.get('blocks', []):
        print(f'  {b.get("type")} data keys: {sorted((b.get("data") or {}).keys())}')
        data = b.get('data') or {}
        if data.get('message'):
            print(f'  {b.get("type")} message: {data.get("message")[:300]}')
        if 'level' in data:
            print(f'  {b.get("type")} level: {data["level"]}')
    print(f'Frame thoughts (first 600): {(frame.get("thoughts") or "")[:600]}')
    print()
    print(f'state.has_issues: {agent.world.current_state().has_issues}')
    print(f'flow_stack (all): {[(f.flow_type, f.status) for f in agent.world.flow_stack._stack]}')
    print()
    print(f'New MT1T files under {mt1t_drafts}:')
    for f in new_files:
        print(f'  {f.name} ({f.stat().st_size} bytes)')
    if not new_files:
        print('  (none — release did NOT write a file)')

    agent.close()


if __name__ == '__main__':
    main()
