from __future__ import annotations

from pathlib import Path

import pandas as pd

_DB_DIR = Path(__file__).resolve().parents[2] / 'database'


class ToolService:

    def _success(self, result, **metadata):
        envelope = {'status': 'success', 'result': result}
        if metadata:
            envelope['metadata'] = metadata
        return envelope

    def _error(self, category:str, message:str,
               retryable:bool=False, **metadata):
        envelope = {
            'status': 'error',
            'error_category': category,
            'message': message,
            'retryable': retryable,
        }
        if metadata:
            envelope['metadata'] = metadata
        return envelope


# ── In-memory dataset workspace ──────────────────────────────────────

_workspace: dict[str, pd.DataFrame] = {}


def _get_df(name:str) -> pd.DataFrame | None:
    return _workspace.get(name)


def _put_df(name:str, df:pd.DataFrame):
    _workspace[name] = df


def _list_datasets() -> list[dict]:
    results = []
    for name, df in _workspace.items():
        results.append({
            'name': name,
            'columns': list(df.columns),
            'row_count': len(df),
            'dtypes': {col: str(df[col].dtype) for col in df.columns},
        })
    return results


# ── Re-exports (so pex.py import doesn't change) ─────────────────────

from backend.utilities.dataset_service import DatasetService      # noqa: E402
from backend.utilities.query_service import QueryService, ChartService  # noqa: E402
from backend.utilities.catalog_service import SavedQueryService, MetricService  # noqa: E402
from backend.utilities.transform_service import TransformService   # noqa: E402
