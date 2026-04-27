from backend.components.flow_stack.parents import BaseFlow
from backend.components.display_frame import DisplayFrame

TEMPLATES = {
    'brainstorm': {'template': "{message}", 'skip_naturalize': True},
    'create':     {'template': "I've created a new draft called '{title}'", 'block_hint': 'card'},
    'outline':    {'template': "{message}", 'skip_naturalize': True, 'block_hint': 'card'},
    'refine':     {'template': "{message}", 'block_hint': 'card'},
    'cite':       {'template': "{message}", 'block_hint': 'card'},
    'compose':    {'template': "{message}", 'block_hint': 'card'},
    'add':        {'template': "{message}", 'block_hint': 'card'},
}

def fill_draft_template(template:str, flow:BaseFlow, frame:DisplayFrame) -> str:
    flow_name = flow.name()

    if flow_name == 'create':
        return TEMPLATES['create']['template'].format(title=flow.slots['title'].value)

    if flow_name == 'outline':
        if flow.stage == 'propose':
            n = len(flow.slots['proposals'].options) if flow.slots['proposals'].options else 0
            return f"I drafted {n} outline options — click one to continue, or tell me what to adjust."
        n = len(flow.slots['sections'].steps) if flow.slots['sections'].filled else 0
        return f"Saved the outline with {n} sections." if n else "Saved the outline."

    return TEMPLATES[flow_name]['template'].format(message=frame.thoughts)
