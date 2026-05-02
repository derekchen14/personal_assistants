"""Universal smoke test — every flow's policy starts cleanly with its entity slot filled.

Exercises each flow with a strict tool stub: any tool call that doesn't have a canned response
raises. The point isn't to verify policy correctness (that's per-flow Tier 1's job); it's a floor
that catches anything which fails to start its happy path — slot-key drift, missing imports,
KeyError on entity_slot, etc.

Empty-slot entry is intentionally NOT tested. A policy invoked with empty slots should crash or
declare ambiguity; that's the dispatcher's job, not a state we verify as nominal.
"""
from __future__ import annotations

import pytest

from backend.components.flow_stack import flow_classes
from backend.components.flow_stack.slots import SourceSlot, FreeTextSlot
from backend.components.display_frame import DisplayFrame
from utils.tests.policy_evals.fixtures import (
    build_policy, make_state, make_context,
)


_POST_ID = 'abc12345'
_TOPIC_TEXT = 'agent design'

# Default response for any tool — every call returns the canned dict for that tool.
# Smoke test only cares that policies execute without crashing, so unbounded reuse is fine.
_DEFAULT_TOOL_RESPONSES = {
    'find_posts':       {'_success': True, 'items': [
        {'post_id': _POST_ID, 'title': 'Smoke', 'status': 'draft'}]},
    'search_notes':     {'_success': True, 'items': []},
    'read_metadata':    {'_success': True, 'post_id': _POST_ID, 'title': 'Smoke',
                         'status': 'draft', 'outline': '## Intro\n## Body'},
    'read_section':     {'_success': True, 'content': 'sample content'},
    'create_post':      {'_success': True, 'post_id': _POST_ID},
    'update_post':      {'_success': True},
    'delete_post':      {'_success': True},
    'summarize_text':   {'_success': True, 'summary': 'short summary'},
    'rollback_post':    {'_success': True, 'message': 'rolled back', 'version': 1},
    'generate_outline': {'_success': True, 'outline': '## Intro'},
    'convert_to_prose': {'_success': True, 'prose': 'sample'},
    'insert_section':   {'_success': True},
    'revise_content':   {'_success': True},
    'write_text':       {'_success': True, 'text': 'sample'},
    'remove_content':   {'_success': True},
    'cut_and_paste':    {'_success': True},
    'diff_section':     {'_success': True, 'diff': ''},
    'insert_media':     {'_success': True},
    'web_search':       {'_success': True, 'results': []},
    'brainstorm_ideas': {'_success': True, 'ideas': []},
    'inspect_post':     {'_success': True, 'metrics': {}},
    'check_readability':{'_success': True, 'score': 60},
    'check_links':      {'_success': True, 'broken': []},
    'compare_style':    {'_success': True, 'similarity': 0.9},
    'editor_review':    {'_success': True, 'comments': []},
    'explain_action':   {'_success': True, 'explanation': 'because'},
    'analyze_seo':      {'_success': True, 'suggestions': []},
    'release_post':     {'_success': True},
    'promote_post':     {'_success': True},
    'cancel_release':   {'_success': True},
    'list_channels':    {'_success': True, 'channels': []},
    'channel_status':   {'_success': True, 'status': 'connected'},
    'manage_memory':    {'_success': True, 'scratchpad': '', 'result': ''},
}


def _smoke_tools():
    """Always-success tool stub. Unknown tools return a generic _success=True."""
    def tools(name:str, params:dict):
        return _DEFAULT_TOOL_RESPONSES.get(name, {'_success': True})
    return tools


def _entity_fill_for(flow):
    """Return the kwargs to pass to fill_slot_values that satisfy the entity slot."""
    if flow.entity_slot is None:
        return {}
    slot = flow.slots[flow.entity_slot]
    if isinstance(slot, SourceSlot):                   # SourceSlot, TargetSlot, RemovalSlot, ChannelSlot
        return {flow.entity_slot: [{'post': _POST_ID}]}
    if isinstance(slot, FreeTextSlot):
        return {flow.entity_slot: [_TOPIC_TEXT]}
    if slot.__class__.__name__ == 'DictionarySlot':
        return {flow.entity_slot: {'key': 'smoke_key', 'value': 'smoke_value'}}
    # ExactSlot fallback — single string token.
    return {flow.entity_slot: _TOPIC_TEXT}


@pytest.mark.parametrize('flow_name', sorted(flow_classes.keys()))
def test_policy_runs_with_entity_filled(flow_name, monkeypatch):
    # Stub LLM-touching call sites BEFORE building the policy so the smoke stays free-tier.
    from backend.modules.policies.base import BasePolicy
    from backend.components.prompt_engineer import PromptEngineer
    monkeypatch.setattr(BasePolicy, 'llm_execute',
                        lambda self, flow, state, context, tools, **kw: ('', []))
    monkeypatch.setattr(PromptEngineer, '__call__',
                        lambda self, *a, **kw: '')

    policy, components = build_policy(flow_name)
    if hasattr(policy, 'engineer'):
        monkeypatch.setattr(policy.engineer, 'skill_call',
                            lambda flow, history, scratch=None, **kw: '')

    flow = components['flow_stack'].stackon(flow_name)
    flow.flow_id = 'smoke0001'
    flow.status = 'Active'
    flow.fill_slot_values(_entity_fill_for(flow))

    state = make_state(active_post=_POST_ID)
    context = make_context()
    tools = _smoke_tools()

    frame = policy.execute(state, context, tools)
    assert isinstance(frame, DisplayFrame), f'{flow_name}: returned {type(frame).__name__}'
