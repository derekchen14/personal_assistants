"""Shared fixtures for policy-in-isolation tests (Part 4 tier 1).

Each policy is exercised without the NLU/PEX/RES pipeline: we feed it a
DialogueState, a flow on a real FlowStack, a canned-response tools stub, and
a minimal ContextCoordinator. Real PromptEngineer / MemoryManager /
AmbiguityHandler / FlowStack instances are used — policies treat them as
collaborators, and the methods we exercise (apply_guardrails,
extract_tool_result, write_scratchpad, declare, stackon) do not make LLM
calls.
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
    config = _load_test_config()
    state = DialogueState(config)
    state.turn_count = 1
    state.active_post = None
    state.keep_going = False
    state.has_plan = False
    state.has_issues = False
    for key, value in overrides.items():
        setattr(state, key, value)
    return state


def make_context(compiled_history:str='', turn_id:int=1) -> ContextCoordinator:
    """Return a real ContextCoordinator prefilled with a synthetic history.

    The policies under test call `context.compile_history()` and read
    `context.turn_id`. We seed a single User turn so both return something
    non-trivial without invoking NLU.
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
    front of the per-tool FIFO. If a tool is called without a canned
    response, raises AssertionError so tests fail loudly on unexpected
    tool traffic.
    """
    queues = {name: list(items) for name, items in responses.items()}

    def tools(name:str, params:dict):
        if name not in queues or not queues[name]:
            raise AssertionError(
                f"tool {name!r} called with {params!r} but no canned response remains"
            )
        return queues[name].pop(0)

    return tools


def capture_tool_log(tools_fn):
    """Wrap a tools stub so every call is appended to tools_fn.log.

    Each log entry is `{'name': str, 'params': dict, 'result': dict}`. Tests
    can assert on the full sequence of tool calls without having to
    re-instrument the stub.
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

    The returned dict contains the real collaborator objects the test can
    inspect after the policy executes (flow_stack, ambiguity, memory,
    engineer, state-agnostic config).
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
