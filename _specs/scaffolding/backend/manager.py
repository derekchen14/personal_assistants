"""
Manager: agent lifecycle for personal assistants.

Why username over JWT:
  Personal assistants run with a single trusted user per instance (you, or a
  small team). A session cookie containing the user's name is enough.  JWT adds
  key management, expiry logic, and a DB round-trip with no security benefit in
  this context.  If you ever need multi-tenant auth, swap get_or_create() to
  decode a JWT and key the dict on user_id instead of username.

Thread safety:
  Reads (checking `username in self._agents`) happen without a lock because
  Python dict reads are thread-safe for the GIL.  Writes (creating a new agent)
  use double-check locking so two simultaneous connections for the same user
  only ever create one agent.
"""

import gc
import threading

from backend.agent import Agent


class Manager:
    """
    Owns the pool of live Agent instances, keyed by username.

    One manager per process (module-level singleton below). All WebSocket
    handlers call the module-level helper functions; they never import Manager
    directly.
    """

    def __init__(self):
        self._agents: dict[str, Agent] = {}
        # Only used during agent creation — reads need no lock (GIL guarantee)
        self._write_lock = threading.Lock()

    def get_or_create(self, username: str) -> Agent:
        """
        Return the existing agent for *username*, or create and cache a new one.

        The double-check pattern (test → lock → test again) prevents two
        concurrent first-connections from spawning duplicate agents.
        """
        if username in self._agents:
            return self._agents[username]

        with self._write_lock:
            # Re-check inside the lock — another thread may have created it
            if username in self._agents:
                return self._agents[username]
            agent = Agent(username)
            self._agents[username] = agent
            return agent

    def cleanup(self, username: str, source: str = 'general') -> bool:
        """
        Remove the agent from the pool and release resources.

        *source* is just for log context (e.g. 'websocket', 'timeout').
        Returns True if an agent was found and removed.
        """
        agent = self._agents.pop(username, None)
        if agent is None:
            return False
        # Give the agent a chance to flush state, close file handles, etc.
        if hasattr(agent, 'close'):
            try:
                agent.close()
            except Exception:
                pass
        gc.collect()
        return True

    def reset(self, username: str) -> dict:
        """
        Reset the conversation state without destroying the agent object.

        Cheaper than cleanup() + get_or_create() because it reuses the
        already-initialized models and config.
        """
        if username not in self._agents:
            return {'message': 'No active session to reset'}
        self._agents[username].reset()
        return {'message': 'Session reset successfully'}


# ── Module-level singleton ────────────────────────────────────────────────────
# Use the helper functions below in routers — never import _manager directly.

_manager = Manager()


def get_or_create_agent(username: str) -> Agent:
    """Get or create the agent for this username. Called on every WS connect."""
    return _manager.get_or_create(username)


def cleanup_agent(username: str, source: str = 'general') -> bool:
    """Destroy the agent when the WebSocket closes. Always call in finally."""
    return _manager.cleanup(username, source)


def reset_agent(username: str) -> dict:
    """Reset conversation state, keep the agent alive. Called on 'reset' WS msg."""
    return _manager.reset(username)
