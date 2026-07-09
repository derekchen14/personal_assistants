import gc
import threading

from backend.assistant import Assistant


class Manager:

    def __init__(self):
        self._assistants: dict[str, Assistant] = {}
        self._write_lock = threading.Lock()

    def get_or_create(self, username:str) -> Assistant:
        if username in self._assistants:
            return self._assistants[username]

        with self._write_lock:
            if username in self._assistants:
                return self._assistants[username]
            assistant = Assistant(username)
            self._assistants[username] = assistant
            return assistant

    def cleanup(self, username:str, source:str='general') -> bool:
        assistant = self._assistants.pop(username, None)
        if assistant is None:
            return False
        if hasattr(assistant, 'close'):
            try:
                assistant.close()
            except Exception:
                pass
        gc.collect()
        return True

    def reset(self, username:str) -> dict:
        if username not in self._assistants:
            return {'message': 'No active session to reset'}
        self._assistants[username].reset()
        return {'message': 'Session reset successfully'}


_manager = Manager()


def get_or_create_assistant(username:str) -> Assistant:
    return _manager.get_or_create(username)


def cleanup_assistant(username:str, source:str='general') -> bool:
    return _manager.cleanup(username, source)


def reset_assistant(username:str) -> dict:
    return _manager.reset(username)
