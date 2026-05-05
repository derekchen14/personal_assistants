TEMPLATES = {
    'blueprint': {'template': "Here's the plan: {message}", 'block_hint': 'list'},
    'triage':    {'template': "{message}", 'block_hint': 'list'},
    'calendar':  {'template': "{message}", 'block_hint': 'list'},
    'scope':     {'template': "{message}", 'block_hint': 'list'},
    'digest':    {'template': "{message}", 'block_hint': 'list'},
    'remember':  {'template': "{message}"},
}

def fill_plan_template(template:str, flow, frame) -> str:
    template = TEMPLATES[flow.name()]['template']
    return template.format(message=frame.thoughts)
