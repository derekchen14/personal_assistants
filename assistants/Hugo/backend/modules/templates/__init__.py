from backend.modules.templates import research, draft, revise, publish, converse, plan
from backend.modules.templates.research import fill_research_template
from backend.modules.templates.draft import fill_draft_template
from backend.modules.templates.revise import fill_revise_template
from backend.modules.templates.publish import fill_publish_template
from backend.modules.templates.converse import fill_converse_template
from backend.modules.templates.plan import fill_plan_template

_MODULES = {'Research':research, 'Draft':draft, 'Revise':revise, 'Publish':publish, 'Converse':converse, 'Plan':plan}

def get_template(flow_name:str, intent:str) -> dict:
    """Look up the template entry for `flow_name` in the intent module. Crashes loudly when the
    flow has no registered template — every non-Internal flow must have one in its intent module."""
    entry = _MODULES[intent].TEMPLATES[flow_name]
    return {'template': entry.get('template', '{message}'),
            'block_hint': entry.get('block_hint'),
            'skip_naturalize': entry.get('skip_naturalize', False)}