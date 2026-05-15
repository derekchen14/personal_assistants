TEMPLATES = {
    'release':   {'template': "Published! {message}", 'block_hint': 'toast'},
    'syndicate': {'template': "Cross-posted! {message}", 'block_hint': 'toast', 'skip_naturalize': True},
    'schedule':  {'template': "Scheduled! {message}", 'block_hint': 'toast', 'skip_naturalize': True},
    'preview':   {'template': "{message}", 'block_hint': 'card'},
    'promote':   {'template': "{message}", 'block_hint': 'card'},
    'cancel':    {'template': "Publication cancelled. {message}", 'block_hint': 'toast'},
    'survey':    {'template': "{message}", 'block_hint': 'list'},
}

def fill_publish_template(template:str, flow, artifact) -> str:
    template = TEMPLATES[flow.name()]['template']
    message = artifact.thoughts
    return template.format(message=message)
