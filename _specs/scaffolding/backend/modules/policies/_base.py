from pathlib import Path

from backend.components.task_artifact import TaskArtifact


_SKILL_DIR = Path(__file__).resolve().parents[2] / 'prompts' / 'pex' / 'skills'

_BATCH_1:set[str] = set()   # Domain-specific: flows implemented in batch 1
_BATCH_2:set[str] = set()   # Domain-specific: flows deferred to batch 2


class BasePolicy:
    """Hugo-style policy orchestrator. Each domain subclasses this with the
    per-intent policy methods. The base demonstrates the agentic dispatch
    via `llm_execute`; deterministic flows skip the skill entirely and call
    `tools(name, params)` directly."""

    def __init__(self, components:dict):
        self.engineer = components['engineer']
        self.memory = components['memory']
        self.world = components['world']
        self._get_tools_fn = components['get_tools']

    def execute(self, flow, state, tool_dispatcher) -> TaskArtifact:
        if flow.name() in _BATCH_2:
            return TaskArtifact(origin=flow.name(),
                                thoughts="That feature is coming soon — stay tuned!")
        return self.llm_execute(flow, state, self.world.context, tool_dispatcher)

    def llm_execute(self, flow, state, context, tool_dispatcher) -> tuple[str, list[dict]]:
        """Agentic dispatch — loads the per-flow skill, runs the tool loop,
        returns (text, tool_log). Policies inspect tool_log to build the frame."""
        skill_prompt = self._load_skill_template(flow.name())
        convo_history = context.compile_history(turns=5)
        scratchpad = self.memory.read_scratchpad()
        tool_defs = self._get_tools_fn(flow)

        return self.engineer.tool_call(
            flow, convo_history, scratchpad, tool_defs, tool_dispatcher,
            skill_name=flow.name(), skill_prompt=skill_prompt,
            resolved=getattr(flow, 'resolved', {}),
        )

    def _load_skill_template(self, flow_name:str) -> str|None:
        path = _SKILL_DIR / f'{flow_name}.md'
        if path.exists():
            return path.read_text(encoding='utf-8')
        return None
