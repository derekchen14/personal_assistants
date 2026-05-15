TEMPLATES = {
    'explain':    {'template': "{message}"},
    'chat':       {'template': "{message}"},
    'preference': {'template': "{message}", 'skip_naturalize': True},
    'suggest':    {'template': "{message}"},
    'undo':       {'template': "{message}", 'block_hint': 'toast'},
    'endorse':    {'template': "{message}", 'skip_naturalize': True},
    'dismiss':    {'template': "{message}", 'skip_naturalize': True},
}

def fill_converse_template(template:str, flow, artifact) -> str:
    template = TEMPLATES[flow.name()]['template']
    return template.format(message=artifact.thoughts)
