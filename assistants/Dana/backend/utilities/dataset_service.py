from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from backend.utilities.services import ToolService, _get_df, _put_df, _list_datasets

_DB_DIR = Path(__file__).resolve().parents[2] / 'database'
_SEED_FILE = _DB_DIR / 'seed_data.json'
_DATASETS_DIR = _DB_DIR / 'datasets'


class DatasetService(ToolService):

    def load(self, name:str, source:str='seed',
             format:str='csv') -> dict:
        if source == 'seed':
            return self._load_seed(name)

        path = Path(source)
        if not path.exists():
            return self._error('not_found', f'File not found: {source}')

        try:
            if format == 'csv' or path.suffix == '.csv':
                df = pd.read_csv(path)
            elif format == 'json' or path.suffix == '.json':
                df = pd.read_json(path)
            elif format == 'excel' or path.suffix in ('.xlsx', '.xls'):
                df = pd.read_excel(path)
            else:
                return self._error('invalid_input', f'Unsupported format: {format}')
        except Exception as ecp:
            return self._error('server_error', f'Failed to load: {ecp}')

        _put_df(name, df)
        return self._success({
            'name': name,
            'columns': list(df.columns),
            'row_count': len(df),
            'dtypes': {col: str(df[col].dtype) for col in df.columns},
        })

    def _load_seed(self, name:str) -> dict:
        if not _SEED_FILE.exists():
            return self._error('not_found', 'Seed data file not found')
        try:
            seed = json.loads(_SEED_FILE.read_text(encoding='utf-8'))
        except Exception as ecp:
            return self._error('server_error', f'Failed to read seed data: {ecp}')

        if name not in seed:
            available = ', '.join(seed.keys())
            return self._error(
                'not_found',
                f'Dataset "{name}" not in seed data. Available: {available}',
            )

        entry = seed[name]
        df = pd.DataFrame(entry['rows'])
        _put_df(name, df)
        return self._success({
            'name': name,
            'description': entry.get('description', ''),
            'columns': list(df.columns),
            'row_count': len(df),
            'dtypes': {col: str(df[col].dtype) for col in df.columns},
        })

    def list_datasets(self) -> dict:
        datasets = _list_datasets()
        if not datasets and _SEED_FILE.exists():
            try:
                seed = json.loads(_SEED_FILE.read_text(encoding='utf-8'))
                for name in seed:
                    self._load_seed(name)
                datasets = _list_datasets()
            except Exception:
                pass
        return self._success(datasets, count=len(datasets))

    def schema(self, dataset:str) -> dict:
        df = _get_df(dataset)
        if df is None:
            return self._error('not_found', f'Dataset not loaded: {dataset}')
        info = {
            'name': dataset,
            'columns': [],
            'row_count': len(df),
        }
        for col in df.columns:
            info['columns'].append({
                'name': col,
                'dtype': str(df[col].dtype),
                'nulls': int(df[col].isnull().sum()),
                'unique': int(df[col].nunique()),
            })
        return self._success(info)

    def sample(self, dataset:str, count:int=5) -> dict:
        df = _get_df(dataset)
        if df is None:
            return self._error('not_found', f'Dataset not loaded: {dataset}')
        count = min(count, len(df))
        sample_df = df.head(count)
        return self._success({
            'name': dataset,
            'columns': list(sample_df.columns),
            'rows': sample_df.to_dict('records'),
            'row_count': count,
            'total_rows': len(df),
        })

    def profile(self, dataset:str, column:str) -> dict:
        df = _get_df(dataset)
        if df is None:
            return self._error('not_found', f'Dataset not loaded: {dataset}')
        if column not in df.columns:
            return self._error('invalid_input', f'Column not found: {column}')
        col = df[column]
        stats = {
            'column': column,
            'dtype': str(col.dtype),
            'count': int(col.count()),
            'nulls': int(col.isnull().sum()),
            'unique': int(col.nunique()),
        }
        if pd.api.types.is_numeric_dtype(col):
            stats.update({
                'min': float(col.min()) if not col.empty else None,
                'max': float(col.max()) if not col.empty else None,
                'mean': float(col.mean()) if not col.empty else None,
                'median': float(col.median()) if not col.empty else None,
                'std': float(col.std()) if not col.empty else None,
            })
        return self._success(stats)

    def update(self, dataset:str, column:str, row:int|None=None,
               value:str='') -> dict:
        df = _get_df(dataset)
        if df is None:
            return self._error('not_found', f'Dataset not loaded: {dataset}')
        if column not in df.columns:
            return self._error('invalid_input', f'Column not found: {column}')
        if row is not None:
            if row < 0 or row >= len(df):
                return self._error('invalid_input', f'Row index out of range: {row}')
            df.at[row, column] = value
        else:
            df[column] = value
        _put_df(dataset, df)
        return self._success({'dataset': dataset, 'updated': True})

    def delete(self, dataset:str, target:str) -> dict:
        df = _get_df(dataset)
        if df is None:
            return self._error('not_found', f'Dataset not loaded: {dataset}')
        if target in df.columns:
            df = df.drop(columns=[target])
            _put_df(dataset, df)
            return self._success({
                'dataset': dataset, 'dropped': 'column', 'target': target,
            })
        try:
            row_idx = int(target)
            if 0 <= row_idx < len(df):
                df = df.drop(index=row_idx).reset_index(drop=True)
                _put_df(dataset, df)
                return self._success({
                    'dataset': dataset, 'dropped': 'row', 'target': row_idx,
                })
        except ValueError:
            pass
        return self._error('invalid_input', f'Target not found: {target}')

    def insert(self, dataset:str, column:str|None=None,
               row:dict|None=None) -> dict:
        df = _get_df(dataset)
        if df is None:
            return self._error('not_found', f'Dataset not loaded: {dataset}')
        if column:
            df[column] = None
            _put_df(dataset, df)
            return self._success({
                'dataset': dataset, 'added': 'column', 'column': column,
            })
        if row:
            new_row = pd.DataFrame([row])
            df = pd.concat([df, new_row], ignore_index=True)
            _put_df(dataset, df)
            return self._success({
                'dataset': dataset, 'added': 'row', 'row_count': len(df),
            })
        return self._error('invalid_input', 'Provide either column or row')
