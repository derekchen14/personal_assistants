"""Per-turn starter prompt for PromoteFlow.

Amplifies an already-published post via pin / feature / announce / social.
Channel slot is a CategorySlot (the action), not a publishing channel.
"""


TEMPLATE = """<task>
Promote "{post_title}" via {action_label}. Confirm the post is published via `read_metadata`, then call `promote_post(action=<action>)` for each requested action. End once every action is executed.
</task>

<resolved_details>
{parameters}
</resolved_details>"""


def build(flow, resolved:dict, user_text:str) -> str:
    return TEMPLATE.format(
        post_title=resolved.get('post_title', 'this post'),
        action_label=_action_label(flow),
        parameters=_format_parameters(flow),
    )


def _action_label(flow) -> str:
    channel = flow.slots['channel']
    if channel.check_if_filled() and channel.values:
        val = channel.values[0]
        return str(val)
    return 'pin or feature (default)'


def _format_parameters(flow) -> str:
    lines = []
    channel = flow.slots['channel']
    if channel.check_if_filled():
        lines.append(f'Action: {_action_label(flow)}')
    return '\n'.join(lines) if lines else '(no parameters filled — propose options in your reply)'
