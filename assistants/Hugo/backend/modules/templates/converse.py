from backend.components.flow_stack.parents import BaseFlow
from backend.components.display_frame import DisplayFrame

TEMPLATES = {
    'explain':    {'template': "{message}"},
    'chat':       {'template': "{message}"},
    'preference': {'template': "{message}", 'skip_naturalize': True},
    'suggest':    {'template': "{message}"},
    'undo':       {'template': "{message}", 'block_hint': 'toast'},
    'endorse':    {'template': "{message}", 'skip_naturalize': True},
    'dismiss':    {'template': "{message}", 'skip_naturalize': True},
}

def fill_converse_template(template:str, flow:BaseFlow, frame:DisplayFrame) -> str:
    template = TEMPLATES[flow.name()]['template']
    message = frame.thoughts or frame.data.get('content', '')
    return template.format(message=message)
