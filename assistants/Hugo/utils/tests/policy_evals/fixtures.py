"""Shared fixtures for policy-in-isolation tests (Part 4 tier 1).

Each policy is exercised without the NLU/PEX/RES pipeline: we feed it a DialogueState, a flow on a
real FlowStack, a canned-response tools stub, and a minimal ContextCoordinator. Real PromptEngineer
/ MemoryManager / AmbiguityHandler / FlowStack instances are used — policies treat them as
collaborators, and the methods we exercise (apply_guardrails, extract_tool_result, write_scratchpad,
declare, stackon) do not make LLM calls.
"""

from __future__ import annotations

from schemas.config import load_config
from schemas.ontology import Intent
from backend.components.ambiguity_handler import AmbiguityHandler
from backend.components.context_coordinator import ContextCoordinator
from backend.components.dialogue_state import DialogueState
from backend.components.flow_stack import FlowStack, flow_classes
from backend.components.memory_manager import MemoryManager
from backend.components.prompt_engineer import PromptEngineer
from backend.modules.policies.converse import ConversePolicy
from backend.modules.policies.draft import DraftPolicy
from backend.modules.policies.internal import InternalPolicy
from backend.modules.policies.plan import PlanPolicy
from backend.modules.policies.publish import PublishPolicy
from backend.modules.policies.research import ResearchPolicy
from backend.modules.policies.revise import RevisePolicy


_POLICY_FOR_INTENT = {
    Intent.CONVERSE: ConversePolicy,
    Intent.RESEARCH: ResearchPolicy,
    Intent.DRAFT: DraftPolicy,
    Intent.REVISE: RevisePolicy,
    Intent.PUBLISH: PublishPolicy,
    Intent.PLAN: PlanPolicy,
    Intent.INTERNAL: InternalPolicy,
}


def _load_test_config():
    return load_config(overrides={'debug': True})


def make_state(**overrides) -> DialogueState:
    """Return a DialogueState with sensible defaults; any kwarg overrides."""
    state = DialogueState(intent=None, dax=None, turn_count=1)
    state.active_post = None
    state.keep_going = False
    state.has_plan = False
    state.has_issues = False
    for key, value in overrides.items():
        setattr(state, key, value)
    return state


def make_context(compiled_history:str='', turn_id:int=1) -> ContextCoordinator:
    """Return a real ContextCoordinator prefilled with a synthetic history.

    The policies under test call `context.compile_history()` and read `context.turn_id`. We seed a
    single User turn so both return something non-trivial without invoking NLU.
    """
    config = _load_test_config()
    context = ContextCoordinator(config)
    for _ in range(max(0, turn_id - 1)):
        context.add_turn('System', 'filler', 'system')
    if compiled_history:
        context.add_turn('User', compiled_history, 'utterance')
    else:
        context.add_turn('User', 'test utterance', 'utterance')
    return context


def make_flow(flow_name:str, **slot_values):
    """Instantiate a flow class from the registry and fill the requested slots.

    slot_values are forwarded through `flow.fill_slot_values`, which handles
    every slot type including ExactSlot-typed entity slots. Pass
    `source={'post': 'abc123'}` for SourceSlot-typed entity slots.
    """
    cls = flow_classes[flow_name]
    flow = cls()
    flow.flow_id = 'test0000'
    flow.status = 'Active'
    if slot_values:
        flow.fill_slot_values(slot_values)
    for slot in flow.slots.values():
        slot.check_if_filled()
    return flow


def make_tool_stub(responses:dict):
    """Build a callable `tools(name, params)` that returns canned responses.

    `responses` is `{tool_name: [dict, dict, ...]}` — each call pops the
    front of the per-tool FIFO. If a tool is called without a canned response, raises AssertionError
    so tests fail loudly on unexpected tool traffic.
    """
    queues = {name: list(items) for name, items in responses.items()}

    def tools(name:str, params:dict):
        if name not in queues or not queues[name]:
            raise AssertionError(
                f"tool {name!r} called with {params!r} but no canned response remains"
            )
        return queues[name].pop(0)

    return tools


def real_tools(monkeypatch, tmp_path):
    """Build a `tools(name, params)` callable that dispatches to REAL service methods
    against a tmp_path-isolated DB. Pillar 2b: replaces `make_tool_stub` so policy
    evals exercise the actual service contracts (catches argument-shape and
    state-propagation bugs the canned stub silently accepted).

    Mirrors the registry in `backend/modules/pex.py:51-88` so the dispatch matches
    production exactly. Returns a callable with `.log` (list of {name, params, result}).

    Usage:
        tools = real_tools(monkeypatch, tmp_path)
        # pre-seed any post the test depends on, e.g.:
        from backend.utilities.services import PostService
        PostService().create_post(title='Test', type='draft')
        # ...then run the policy with `tools`.
    """
    db = tmp_path / 'database'
    content = db / 'content'
    (content / 'drafts').mkdir(parents=True)
    (content / 'notes').mkdir(parents=True)
    (content / 'posts').mkdir(parents=True)
    (db / '.snapshots').mkdir(parents=True)
    (db / 'guides').mkdir(parents=True)
    (content / 'metadata.json').write_text('{"entries": []}')

    import backend.utilities.services as _svc
    monkeypatch.setattr(_svc, '_DB_DIR', db)

    from backend.utilities.services import (
        PostService, ContentService, AnalysisService, PlatformService,
    )
    post = PostService()
    cont = ContentService()
    analysis = AnalysisService()
    platform = PlatformService()
    registry = {
        'find_posts': post.find_posts, 'search_notes': post.search_notes,
        'read_metadata': post.read_metadata, 'read_section': post.read_section,
        'create_post': post.create_post, 'update_post': post.update_post,
        'delete_post': post.delete_post, 'summarize_text': post.summarize_text,
        'rollback_post': post.rollback_post,
        'generate_outline': cont.generate_outline,
        'convert_to_prose': cont.convert_to_prose,
        'insert_section': cont.insert_section, 'revise_content': cont.revise_content,
        'write_text': cont.write_text, 'remove_content': cont.remove_content,
        'cut_and_paste': cont.cut_and_paste, 'diff_section': cont.diff_section,
        'insert_media': cont.insert_media, 'web_search': cont.web_search,
        'brainstorm_ideas': analysis.brainstorm_ideas,
        'inspect_post': analysis.inspect_post,
        'check_readability': analysis.check_readability,
        'check_links': analysis.check_links, 'compare_style': analysis.compare_style,
        'editor_review': analysis.editor_review,
        'explain_action': analysis.explain_action, 'analyze_seo': analysis.analyze_seo,
        'release_post': platform.release_post, 'promote_post': platform.promote_post,
        'cancel_release': platform.cancel_release,
        'list_channels': platform.list_channels,
        'channel_status': platform.channel_status,
    }

    log:list[dict] = []
    def tools(name:str, params:dict):
        from backend.utilities.services import PostNotFoundError, OutlineValidationError
        if name not in registry:
            result = {'_success': False, '_error': 'invalid_input',
                      '_message': f'Unknown tool: {name}'}
        else:
            try:
                result = registry[name](**params)
            except OutlineValidationError as ecp:
                result = {'_success': False, '_error': 'validation', '_message': str(ecp)}
            except PostNotFoundError as ecp:
                result = {'_success': False, '_error': 'not_found', '_message': str(ecp)}
        log.append({'name': name, 'params': params, 'result': result})
        return result

    tools.log = log
    tools.db = db  # exposed so tests can read disk state directly
    return tools


def capture_tool_log(tools_fn):
    """Wrap a tools stub so every call is appended to tools_fn.log.

    Each log entry is `{'name': str, 'params': dict, 'result': dict}`. Tests
    can assert on the full sequence of tool calls without having to re-instrument the stub.
    """
    log:list[dict] = []

    def wrapped(name:str, params:dict):
        result = tools_fn(name, params)
        log.append({'name': name, 'params': params, 'result': result})
        return result

    wrapped.log = log
    return wrapped


def build_policy(flow_name:str):
    """Return a (policy, components) pair ready to drive a single flow.

    The returned dict contains the real collaborator objects the test can inspect after the policy
    executes (flow_stack, ambiguity, memory, engineer, state-agnostic config).
    """
    config = _load_test_config()
    engineer = PromptEngineer(config)
    memory = MemoryManager(config)
    ambiguity = AmbiguityHandler(config, engineer=engineer)
    flow_stack = FlowStack(config, flow_classes=flow_classes)

    def _unused_get_tools(_flow):
        raise AssertionError(
            'get_tools_for_flow should not be called in policy-isolation tests'
        )

    components = {
        'engineer': engineer, 'memory': memory, 'config': config,
        'ambiguity': ambiguity, 'flow_stack': flow_stack,
        'get_tools': _unused_get_tools,
    }

    cls = flow_classes[flow_name]
    probe = cls()
    policy_cls = _POLICY_FOR_INTENT[probe.intent]
    policy = policy_cls(components)

    return policy, components


def assert_frame(frame, origin=None, block_types=(), metadata=None,
                 has_code=None, thoughts_contains=None):
    """Single helper for DisplayFrame invariants.

    - origin: exact string match
    - block_types: tuple compared against [b.block_type for b in frame.blocks]
    - metadata: subset match — every key/value in `metadata` must appear in
      frame.metadata (extra keys in the frame are fine)
    - has_code: True/False to require a non-empty / empty frame.code
    - thoughts_contains: substring must appear in frame.thoughts
    """
    assert frame is not None, 'frame was None'
    assert hasattr(frame, 'origin'), 'object is not a DisplayFrame'
    if origin is not None:
        assert frame.origin == origin, f'origin={frame.origin!r} != {origin!r}'
    if block_types:
        actual = tuple(block.block_type for block in frame.blocks)
        assert actual == block_types, f'blocks={actual!r} != {block_types!r}'
    if metadata is not None:
        for key, value in metadata.items():
            assert key in frame.metadata, f'metadata missing key {key!r}'
            assert frame.metadata[key] == value, (
                f'metadata[{key!r}]={frame.metadata[key]!r} != {value!r}'
            )
    if has_code is True:
        assert frame.code, 'expected frame.code to be set'
    elif has_code is False:
        assert not frame.code, f'expected no frame.code, got {frame.code!r}'
    if thoughts_contains is not None:
        assert thoughts_contains in (frame.thoughts or ''), (
            f'thoughts={frame.thoughts!r} missing {thoughts_contains!r}'
        )
