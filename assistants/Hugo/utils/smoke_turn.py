"""Round 0.3 smoke: one real 3-turn conversation through Assistant.take_turn — find a post,
outline it, release it — against the live PEX agent. Prints each turn's utterance, the belief
(intent / flow / confidence), and the flow stack.

Run from the Hugo root: python utils/smoke_turn.py
"""
import sys
from pathlib import Path

from dotenv import load_dotenv

_HUGO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_HUGO_ROOT))
load_dotenv(_HUGO_ROOT / '.env')

from backend.assistant import Assistant  # noqa: E402

TURNS = [
    "Can you find my draft titled 'Roman Concrete Heals Itself; Ours Just Crumbles'?",
    "Great, put together an outline for it.",
    "Looks good, release it to the blog.",
]


def main():
    assistant = Assistant('smoke')
    for idx, text in enumerate(TURNS, start=1):
        result = assistant.take_turn(text)
        state = assistant.world.state
        top = state.pred_flows[0] if state.pred_flows else {}
        stack = [(entry['flow_name'], entry['status']) for entry in assistant.world.flows.to_list()]
        print(f"\n== turn {idx} ==")
        print(f"USER:   {text}")
        print(f"AGENT:  {result['message']}")
        print(f"belief: intent={state.pred_intent} flow={top.get('flow_name')} "
              f"confidence={top.get('confidence')}")
        print(f"stack:  {stack}")


if __name__ == '__main__':
    main()
