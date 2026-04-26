"""NLU isolation probe — verify the outline-direct NLU exemplar lands.

Runs NLU against Scenario 2 (Observability) step 3's utterance in a state that mirrors
post-propose-turn (topic filled, sections empty, OutlineFlow on stack in propose stage).
"""
from __future__ import annotations

import json

from schemas.config import load_config
from backend.agent import Agent
import backend.agent as agent_mod


TURN3_UTTERANCE = (
    'Make an outline with 6 sections: Motivation, Latency Targets, '
    'Token Accounting, Cost Modeling, Dashboards, and Takeaways. '
    'Under Motivation, add bullets about why agents drift silently when '
    'they run for hours, and how a billing surprise after a weekend '
    'agent run kicked off this work.'
)


def main():
    orig_load = agent_mod.load_config
    agent_mod.load_config = lambda: load_config(overrides={'debug': True})
    agent = Agent(username='test_user')
    agent_mod.load_config = orig_load

    ctx = agent.world.context
    ctx.add_turn('User', 'Create a post about observability for long-running AI agents',
                 turn_type='utterance')
    ctx.add_turn('Agent', 'Created draft "Observability for Long-Running AI Agents".',
                 turn_type='utterance')
    ctx.add_turn('User', 'Make an outline — propose a few options I can pick from',
                 turn_type='utterance')
    ctx.add_turn('Agent',
                 '### Option 1\n## A\n...\n### Option 2\n## B\n...\n### Option 3\n## C\n...',
                 turn_type='utterance')

    from backend.components.dialogue_state import DialogueState
    state = DialogueState(agent.config)
    state.active_post = 'obs12345'
    agent.world.insert_state(state)

    agent.world.flow_stack.stackon('outline')
    flow = agent.world.flow_stack.get_flow()
    flow.slots['topic'].add_one('observability for long-running AI agents')
    flow.stage = 'propose'

    state = agent.nlu.understand(TURN3_UTTERANCE, ctx, dax='{002}', payload={})

    flow = agent.world.flow_stack.get_flow()
    result = {
        'flow_name': flow.name(),
        'stage': getattr(flow, 'stage', None),
        'slots': {
            name: {
                'filled': slot.filled,
                'preview': str(slot.to_dict())[:300] if slot.filled else '—',
            }
            for name, slot in flow.slots.items()
        },
    }
    print(json.dumps(result, indent=2, default=str))
    agent.close()


if __name__ == '__main__':
    main()
