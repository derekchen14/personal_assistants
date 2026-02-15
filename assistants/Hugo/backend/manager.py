import gc
import threading

from backend.agent import Agent


class Manager:

    def __init__(self):
        self._agents: dict[str, Agent] = {}
        self._write_lock = threading.Lock()

    def get_or_create(self, username: str) -> Agent:
        if username in self._agents:
            return self._agents[username]

        with self._write_lock:
            if username in self._agents:
                return self._agents[username]
            agent = Agent(username)
            self._agents[username] = agent
            return agent

    def cleanup(self, username: str, source: str = 'general') -> bool:
        agent = self._agents.pop(username, None)
        if agent is None:
            return False
        if hasattr(agent, 'close'):
            try:
                agent.close()
            except Exception:
                pass
        gc.collect()
        return True

    def reset(self, username: str) -> dict:
        if username not in self._agents:
            return {'message': 'No active session to reset'}
        self._agents[username].reset()
        return {'message': 'Session reset successfully'}


_manager = Manager()


def get_or_create_agent(username: str) -> Agent:
    return _manager.get_or_create(username)


def cleanup_agent(username: str, source: str = 'general') -> bool:
    return _manager.cleanup(username, source)


def reset_agent(username: str) -> dict:
    return _manager.reset(username)
