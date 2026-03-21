from __future__ import annotations

from pathlib import Path

_DB_DIR = Path(__file__).resolve().parents[2] / 'database'


class ToolService:

    def _success(self, result) -> dict:
        return {'status': 'success', 'result': result}

    def _error(self, message:str) -> dict:
        return {'status': 'error', 'message': message}


# ── Re-exports (so pex.py import doesn't change) ─────────────────────

from backend.utilities.entity1_service import Entity1Service       # noqa: E402
from backend.utilities.entity2_service import Entity2Service       # noqa: E402
from backend.utilities.entity3_service import Entity3Service       # noqa: E402
