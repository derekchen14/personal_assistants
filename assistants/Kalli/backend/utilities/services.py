from __future__ import annotations

from pathlib import Path

_DB_DIR = Path(__file__).resolve().parents[2] / 'database'


class ToolService:

    def _success(self, result) -> dict:
        return {'status': 'success', 'result': result}

    def _error(self, message:str) -> dict:
        return {'status': 'error', 'message': message}


# ── Re-exports (so pex.py import doesn't change) ─────────────────────

from backend.utilities.spec_service import SpecService            # noqa: E402
from backend.utilities.config_service import ConfigService, GeneratorService  # noqa: E402
from backend.utilities.catalog_service import RequirementService, ToolDefService, LessonService  # noqa: E402
from backend.utilities.code_service import CodeService             # noqa: E402
