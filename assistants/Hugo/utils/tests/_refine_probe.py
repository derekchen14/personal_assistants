"""Step-4 refine probe — why is refine failing in 5s?

Seeds the agent post-outline-direct (Motivation/Process/Ideas/Takeaways
headings, no bullets yet) and runs step 4's utterance. Reports:
  - RefineFlow slot state after NLU: source / steps / feedback
  - Tool trajectory
  - Final frame + ambiguity level if any
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
_HUGO_ROOT = Path(__file__).resolve().parents[2]
if str(_HUGO_ROOT) not in sys.path:
    sys.path.insert(0, str(_HUGO_ROOT))

from dotenv import load_dotenv
load_dotenv(_HUGO_ROOT / '.env')
os.environ['HUGO_EVAL_MODE'] = '1'

from schemas.config import load_config
from backend.agent import Agent
import backend.agent as agent_mod


POST_TITLE = 'Using Multi-modal Models to Improve AI Agents'
UTTERANCE = (
    'Add bullets to the outline. Under Process, add: pick a vision encoder, '
    'wire it to the planner, fine-tune on UI traces, evaluate on held-out '
    'workflows, and ship behind a flag. Under Ideas, add: using video for '
    'temporal grounding, treating screenshots as a tool the agent can call, '
    'and falling back to text-only when latency budget is tight.'
)
DAX = '{02B}'


def main():
    orig_load = agent_mod.load_config
    agent_mod.load_config = lambda: load_config(overrides={'debug': True})
    agent = Agent(username='test_user')
    agent_mod.load_config = orig_load

    from backend.utilities.services import PostService
    svc = PostService()
    post_id = None
    for ent in svc.list_preview().get('items', []):
        if ent.get('title', '').lower() == POST_TITLE.lower():
            post_id = ent['post_id']
            break
    if not post_id:
        print(f'POST_NOT_FOUND: {POST_TITLE!r}.')
        return

    from backend.components.dialogue_state import DialogueState
    state = DialogueState(agent.config)
    state.active_post = post_id
    agent.world.insert_state(state)

    ctx = agent.world.context
    ctx.add_turn('User', f'Create a post about {POST_TITLE}', turn_type='utterance')
    ctx.add_turn('Agent', f'Created draft "{POST_TITLE}" with ID {post_id}.', turn_type='utterance')
    ctx.add_turn('User', 'Make an outline with Motivation, Process, Ideas, Takeaways', turn_type='utterance')
    ctx.add_turn('Agent', 'Outline saved with 4 sections: motivation, process, ideas, takeaways.', turn_type='utterance')

    tool_trace = []
    original_dispatch = agent.pex._dispatch_tool
    def wrapped(tool_name, tool_input):
        result = original_dispatch(tool_name, tool_input)
        tool_trace.append({
            'tool': tool_name,
            'input': {k: (str(v)[:160] if not isinstance(v, (int, float, bool)) else v) for k, v in tool_input.items()},
            'success': result.get('_success', True),
            'error': result.get('_error'),
        })
        return result
    agent.pex._dispatch_tool = wrapped

    # Intercept refine flow after NLU to inspect slot fills
    from backend.components.flow_stack.flows import RefineFlow
    original_refine_init = RefineFlow.__init__
    captured_flow = {'flow': None}
    def captured_init(self):
        original_refine_init(self)
        captured_flow['flow'] = self
    RefineFlow.__init__ = captured_init

    turn_result = agent.take_turn(UTTERANCE, dax=DAX)

    print('=' * 70)
    print('REFINE PROBE')
    print('=' * 70)
    print()
    print(f'Utterance: {UTTERANCE[:140]}...')
    print()

    active = agent.world.flow_stack.get_flow()
    if active and active.flow_type == 'refine':
        print('Active RefineFlow slots (top-of-stack after turn):')
        for name, slot in active.slots.items():
            filled = getattr(slot, 'filled', False)
            detail = ''
            if hasattr(slot, 'values') and slot.values:
                detail = f' values={slot.values}'
            if hasattr(slot, 'steps') and slot.steps:
                detail = f' steps={[s.get("name") for s in slot.steps]}'
            print(f'  {name:12} filled={filled}{detail} priority={slot.priority}')
        print(f'  is_filled(): {active.is_filled()}')
    else:
        print(f'(top of stack is not refine: {active.flow_type if active else "empty"})')

    print()
    print(f'Tool calls ({len(tool_trace)}):')
    for i, e in enumerate(tool_trace, 1):
        marker = '✓' if e['success'] else '✗'
        args = ', '.join(f'{k}={v!r}' for k, v in e['input'].items())
        print(f'  [{i}] {marker} {e["tool"]}({args})')

    frame = turn_result.get('frame') or {}
    print()
    print(f'Frame origin:    {frame.get("origin")!r}')
    print(f'Frame metadata:  {frame.get("metadata")}')
    print(f'Frame blocks:    {[b.get("type") for b in (frame.get("blocks") or [])]}')
    print(f'Frame thoughts (first 300): {(frame.get("thoughts") or "")[:300]}')
    print()
    print(f'ambiguity.present(): {agent.ambiguity.present()}')
    print(f'ambiguity.level: {agent.ambiguity.level}')
    print(f'ambiguity.metadata: {agent.ambiguity.metadata}')
    print(f'state.has_issues: {agent.world.current_state().has_issues}')
    print(f'flow_stack: {[(f.flow_type, f.status) for f in agent.world.flow_stack._stack]}')

    agent.close()


if __name__ == '__main__':
    main()
