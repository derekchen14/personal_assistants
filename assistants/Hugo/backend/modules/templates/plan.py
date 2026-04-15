from backend.components.flow_stack.parents import BaseFlow
from backend.components.display_frame import DisplayFrame

TEMPLATES = {
    'blueprint': {'template': "Here's the plan: {message}", 'block_hint': 'list'},
    'triage':    {'template': "{message}", 'block_hint': 'list'},
    'calendar':  {'template': "{message}", 'block_hint': 'list'},
    'scope':     {'template': "{message}", 'block_hint': 'list'},
    'digest':    {'template': "{message}", 'block_hint': 'list'},
    'remember':  {'template': "{message}"},
}

def fill_plan_template(template:str, flow:BaseFlow, frame:DisplayFrame) -> str:
    template = TEMPLATES[flow.name()]['template']
    return template.format(message=frame.thoughts)
