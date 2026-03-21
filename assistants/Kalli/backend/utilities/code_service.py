from __future__ import annotations

from backend.utilities.services import ToolService


class CodeService(ToolService):
    """Executes Python code via exec()."""

    def execute(self, code:str, timeout_ms:int=30000) -> dict:
        """tool_id: python_execute"""
        import io
        import contextlib
        try:
            stdout = io.StringIO()
            namespace = {}
            with contextlib.redirect_stdout(stdout):
                exec(code, namespace)
            output = stdout.getvalue()
            return_value = namespace.get('result', None)
            return {
                'status': 'success',
                'result': {'output': output, 'return_value': return_value},
                'metadata': {'tool_id': 'python_execute'},
            }
        except Exception as ecp:
            return {
                'status': 'error',
                'error_category': 'server_error',
                'message': f'{type(ecp).__name__}: {ecp}',
                'retryable': False,
                'metadata': {'tool_id': 'python_execute', 'attempt': 1},
            }
