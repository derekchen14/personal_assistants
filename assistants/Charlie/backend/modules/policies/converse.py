from backend.modules.policies.base import BasePolicy
from backend.components.task_artifact import TaskArtifact


class ConversePolicy(BasePolicy):

    def __init__(self, components):
        super().__init__(components)
        self.flow_stack = components['flow_stack']

    def execute(self, state, context, tools):
        flow = self.flow_stack.get_flow()

        match flow.name():
            case 'chat': return self.chat_policy(flow, state, context, tools)
            case _:
                return TaskArtifact()

    def chat_policy(self, flow, state, context, tools):
        text, _ = self.llm_execute(flow, state, context, tools)
        flow.stage = 'direct'
        self.complete_flow(flow, state, text or 'Responded to the user directly.')
        return TaskArtifact(origin='chat', thoughts=text)
