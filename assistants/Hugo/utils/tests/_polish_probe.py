"""Step-9 polish probe — did the LLM actually change the opening paragraph?

Seeds the agent with the Vision-scenario post that already exists on disk,
installs a tool-dispatch wrapper that captures the `content` arg to every
`revise_content` call, then runs just step 9's utterance.

Prints:
  - Motivation section content BEFORE the turn
  - Every (attempt, content) pair passed to revise_content during the turn
  - Motivation section content AFTER the turn
  - The agent's frame.thoughts (what Haiku sees)
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
UTTERANCE = 'Tighten the opening paragraph of the Motivation section — make it punchier'
DAX = '{3BD}'


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
        print(f'POST_NOT_FOUND: no post titled {POST_TITLE!r}. Run Vision scenario first.')
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
    ctx.add_turn('User', 'Generate an outline and convert it to prose.', turn_type='utterance')
    ctx.add_turn('Agent', (
        f'Done. The post has {len(sections)} sections: {", ".join(sections)}. '
        f'All sections have been composed into prose, expanded, and simplified.'
    ), turn_type='utterance')

    motivation_before = svc.read_section(post_id, sec_id='motivation')

    original_dispatch = agent.pex._dispatch_tool
    revise_log = []
    def wrapped(tool_name, tool_input):
        result = original_dispatch(tool_name, tool_input)
        if tool_name == 'revise_content':
            revise_log.append({
                'attempt': len(revise_log) + 1,
                'sec_id': tool_input.get('sec_id'),
                'snip_id': tool_input.get('snip_id'),
                'content_len': len(tool_input.get('content', '')),
                'content_preview': tool_input.get('content', '')[:800],
                'success': result.get('_success'),
            })
        return result
    agent.pex._dispatch_tool = wrapped

    turn_result = agent.take_turn(UTTERANCE, dax=DAX)

    motivation_after = svc.read_section(post_id, sec_id='motivation')
    frame = turn_result.get('frame') or {}

    print('=' * 70)
    print('POST:', post_id, '|', title)
    print('SECTION: motivation')
    print('=' * 70)
    print()
    print('--- MOTIVATION BEFORE (first 600 chars) ---')
    print((motivation_before.get('content') or '')[:600])
    print()
    print(f'--- revise_content CALLS: {len(revise_log)} ---')
    for entry in revise_log:
        print(json.dumps(entry, indent=2, default=str))
    print()
    print('--- MOTIVATION AFTER (first 600 chars) ---')
    print((motivation_after.get('content') or '')[:600])
    print()
    print('--- CHANGED? ---')
    before_txt = motivation_before.get('content') or ''
    after_txt = motivation_after.get('content') or ''
    print(f'  before len: {len(before_txt)}')
    print(f'  after  len: {len(after_txt)}')
    print(f'  identical: {before_txt == after_txt}')
    print()
    print('--- frame.thoughts (what Haiku sees, first 800 chars) ---')
    print((frame.get('thoughts') or '')[:800])
    print()
    print('--- ambiguity present? ---')
    print(f'  level: {agent.ambiguity.level}')
    print(f'  state.has_issues: {turn_result.get("state", {}).get("has_issues")}')

    agent.close()


if __name__ == '__main__':
    main()
