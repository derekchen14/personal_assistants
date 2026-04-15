from backend.components.flow_stack.parents import BaseFlow
from backend.components.display_frame import DisplayFrame

TEMPLATES = {
    'rework':   {'template': "{message}", 'block_hint': 'card'},
    'polish':   {'template': "{message}", 'block_hint': 'card'},
    'tone':     {'template': "{message}", 'block_hint': 'card'},
    'audit':    {'template': "{message}", 'block_hint': 'card'},
    'simplify': {'template': "{message}", 'block_hint': 'card'},
    'remove':   {'template': "{message}", 'block_hint': 'card'},
    'tidy':     {'template': "{message}", 'block_hint': 'card'},
}

def fill_revise_template(template:str, flow:BaseFlow, frame:DisplayFrame) -> str:
    template = TEMPLATES[flow.name()]['template']
    return template.format(message=frame.thoughts)
