from backend.components.flow_stack.parents import BaseFlow
from backend.components.display_frame import DisplayFrame

TEMPLATES = {
    'browse':    {'template': "Here are some topic ideas: {message}", 'block_hint': 'list'},
    'check':     {'template': "Here are your current drafts: {message}", 'block_hint': 'list'},
    'summarize': {'template': "Here's a summary: {message}"},
    'inspect':   {'template': "Post metrics: {message}", 'block_hint': 'card'},
    'find':      {'template': "Here's what I found: {message}", 'block_hint': 'list'},
    'compare':   {'template': "Here's how they compare: {message}", 'block_hint': 'card'},
    'diff':      {'template': "{message}", 'block_hint': 'card'},
}

def fill_research_template(template:str, flow:BaseFlow, frame:DisplayFrame) -> str:
    template = TEMPLATES[flow.name()]['template']
    message = frame.thoughts
    return template.format(message=message)
