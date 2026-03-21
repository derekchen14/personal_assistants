from backend.components.flow_stack.parents import BaseFlow
from backend.components.display_frame import DisplayFrame

TEMPLATES = {
    'brainstorm': {'template': "{message}", 'skip_naturalize': True},
    'create':     {'template': "I've created a new draft called '{title}'", 'block_hint': 'form'},
    'outline':    {'template': "{message}", 'skip_naturalize': True},
    'refine':     {'template': "{message}", 'block_hint': 'card'},
    'cite':       {'template': "{message}", 'block_hint': 'card'},
    'compose':    {'template': "{message}", 'block_hint': 'card'},
    'add':        {'template': "{message}", 'block_hint': 'card'},
}

def fill_draft_template(template:str, flow:BaseFlow, frame:DisplayFrame) -> str:
    flow_name = flow.name()
    template = TEMPLATES[flow_name]['template']

    if flow_name == 'create':
        filled = template.format(title=flow.slots['title'].value)
    else:
        message = frame.thoughts or frame.data.get('content', '')
        filled = template.format(message=message)

    return filled