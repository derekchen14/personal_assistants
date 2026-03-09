from __future__ import annotations

import base64
import io
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

_DB_DIR = Path(__file__).resolve().parents[2] / 'database'
_SEED_FILE = _DB_DIR / 'seed_data.json'
_DATASETS_DIR = _DB_DIR / 'datasets'


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ToolService:

    def _success(self, result, **metadata):
        envelope = {'status': 'success', 'result': result}
        if metadata:
            envelope['metadata'] = metadata
        return envelope

    def _error(self, category: str, message: str,
               retryable: bool = False, **metadata):
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


def _get_df(name: str) -> pd.DataFrame | None:
    return _workspace.get(name)


def _put_df(name: str, df: pd.DataFrame):
    _workspace[name] = df


def _list_datasets() -> list[dict]:
    results = []
    for name, df in _workspace.items():
        results.append({
            'name': name,
            'columns': list(df.columns),
            'row_count': len(df),
            'dtypes': {c: str(df[c].dtype) for c in df.columns},
        })
    return results


# ── DatasetService ───────────────────────────────────────────────────

class DatasetService(ToolService):

    def load(self, name: str, source: str = 'seed',
             format: str = 'csv') -> dict:
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
        except Exception as e:
            return self._error('server_error', f'Failed to load: {e}')

        _put_df(name, df)
        return self._success({
            'name': name,
            'columns': list(df.columns),
            'row_count': len(df),
            'dtypes': {c: str(df[c].dtype) for c in df.columns},
        })

    def _load_seed(self, name: str) -> dict:
        if not _SEED_FILE.exists():
            return self._error('not_found', 'Seed data file not found')
        try:
            seed = json.loads(_SEED_FILE.read_text(encoding='utf-8'))
        except Exception as e:
            return self._error('server_error', f'Failed to read seed data: {e}')

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
            'dtypes': {c: str(df[c].dtype) for c in df.columns},
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

    def schema(self, dataset: str) -> dict:
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

    def sample(self, dataset: str, n: int = 5) -> dict:
        df = _get_df(dataset)
        if df is None:
            return self._error('not_found', f'Dataset not loaded: {dataset}')
        n = min(n, len(df))
        sample_df = df.head(n)
        return self._success({
            'name': dataset,
            'columns': list(sample_df.columns),
            'rows': sample_df.to_dict('records'),
            'row_count': n,
            'total_rows': len(df),
        })

    def profile(self, dataset: str, column: str) -> dict:
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

    def update(self, dataset: str, column: str, row: int | None = None,
               value: str = '') -> dict:
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

    def delete(self, dataset: str, target: str) -> dict:
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

    def insert(self, dataset: str, column: str | None = None,
               row: dict | None = None) -> dict:
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


# ── QueryService ─────────────────────────────────────────────────────

class QueryService(ToolService):

    def execute_sql(self, query: str, dataset: str | None = None) -> dict:
        try:
            from pandasql import sqldf
        except ImportError:
            return self._error(
                'server_error',
                'pandasql is not installed. Run: pip install pandasql',
            )

        env = {name: df for name, df in _workspace.items()}

        if dataset and dataset in _workspace:
            env['df'] = _workspace[dataset]

        try:
            result_df = sqldf(query, env)
        except Exception as e:
            return self._error('invalid_input', f'SQL error: {e}')

        return self._success({
            'columns': list(result_df.columns),
            'rows': result_df.to_dict('records'),
            'row_count': len(result_df),
        })

    def execute_python(self, code: str, dataset: str | None = None) -> dict:
        env = {'pd': pd}
        for name, df in _workspace.items():
            env[name] = df
        if dataset and dataset in _workspace:
            env['df'] = _workspace[dataset]

        try:
            result = eval(code, {'__builtins__': {}}, env)
        except Exception as e:
            return self._error('invalid_input', f'Python error: {e}')

        if isinstance(result, pd.DataFrame):
            return self._success({
                'columns': list(result.columns),
                'rows': result.head(100).to_dict('records'),
                'row_count': len(result),
            })
        if isinstance(result, pd.Series):
            return self._success({
                'values': result.head(100).to_dict(),
                'count': len(result),
            })
        return self._success({'value': str(result)})

    def analyze_column(self, dataset: str, column: str,
                       metrics: list[str] | None = None) -> dict:
        df = _get_df(dataset)
        if df is None:
            return self._error('not_found', f'Dataset not loaded: {dataset}')
        if column not in df.columns:
            return self._error('invalid_input', f'Column not found: {column}')

        col = df[column]
        all_metrics = metrics or ['min', 'max', 'mean', 'median', 'std', 'nulls', 'unique']
        result = {'column': column, 'dtype': str(col.dtype)}

        for m in all_metrics:
            try:
                if m == 'min':
                    result['min'] = float(col.min()) if pd.api.types.is_numeric_dtype(col) else str(col.min())
                elif m == 'max':
                    result['max'] = float(col.max()) if pd.api.types.is_numeric_dtype(col) else str(col.max())
                elif m == 'mean' and pd.api.types.is_numeric_dtype(col):
                    result['mean'] = float(col.mean())
                elif m == 'median' and pd.api.types.is_numeric_dtype(col):
                    result['median'] = float(col.median())
                elif m == 'std' and pd.api.types.is_numeric_dtype(col):
                    result['std'] = float(col.std())
                elif m == 'nulls':
                    result['nulls'] = int(col.isnull().sum())
                elif m == 'unique':
                    result['unique'] = int(col.nunique())
            except Exception:
                result[m] = None

        return self._success(result)


# ── ChartService ─────────────────────────────────────────────────────

class ChartService(ToolService):

    def render(self, dataset: str, chart_type: str,
               x: str | None = None, y: str | None = None,
               title: str | None = None, color: str | None = None) -> dict:
        df = _get_df(dataset)
        if df is None:
            return self._error('not_found', f'Dataset not loaded: {dataset}')

        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
        except ImportError:
            return self._error(
                'server_error',
                'matplotlib is not installed. Run: pip install matplotlib',
            )

        fig, ax = plt.subplots(figsize=(8, 5))

        try:
            if chart_type == 'bar':
                if x and y:
                    if color:
                        df.pivot_table(index=x, columns=color, values=y, aggfunc='sum').plot.bar(ax=ax)
                    else:
                        df.groupby(x)[y].sum().plot.bar(ax=ax)
                elif x:
                    df[x].value_counts().plot.bar(ax=ax)
                else:
                    df.select_dtypes('number').sum().plot.bar(ax=ax)

            elif chart_type == 'line':
                if x and y:
                    df.plot(x=x, y=y, ax=ax)
                elif y:
                    df[y].plot(ax=ax)
                else:
                    df.select_dtypes('number').plot(ax=ax)

            elif chart_type == 'pie':
                col = y or x or df.select_dtypes('number').columns[0]
                if x:
                    df.groupby(x)[col].sum().plot.pie(ax=ax, autopct='%1.1f%%')
                else:
                    df[col].value_counts().plot.pie(ax=ax, autopct='%1.1f%%')

            elif chart_type == 'scatter':
                if x and y:
                    df.plot.scatter(x=x, y=y, ax=ax)
                else:
                    numeric = df.select_dtypes('number').columns
                    if len(numeric) >= 2:
                        df.plot.scatter(x=numeric[0], y=numeric[1], ax=ax)

            elif chart_type == 'histogram':
                col = x or y or df.select_dtypes('number').columns[0]
                df[col].plot.hist(ax=ax, bins=20)

            else:
                plt.close(fig)
                return self._error('invalid_input', f'Unknown chart type: {chart_type}')

        except Exception as e:
            plt.close(fig)
            return self._error('server_error', f'Chart rendering failed: {e}')

        if title:
            ax.set_title(title)
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=100)
        plt.close(fig)
        buf.seek(0)
        b64 = base64.b64encode(buf.read()).decode('ascii')

        return self._success({
            'chart_type': chart_type,
            'image_base64': b64,
            'format': 'png',
            'dataset': dataset,
        })


# ── TransformService ─────────────────────────────────────────────────

class TransformService(ToolService):

    def merge(self, left: str, right: str, key: str,
              how: str = 'inner') -> dict:
        left_df = _get_df(left)
        right_df = _get_df(right)
        if left_df is None:
            return self._error('not_found', f'Dataset not loaded: {left}')
        if right_df is None:
            return self._error('not_found', f'Dataset not loaded: {right}')

        try:
            result = pd.merge(left_df, right_df, on=key, how=how)
        except Exception as e:
            return self._error('invalid_input', f'Merge failed: {e}')

        result_name = f'{left}_{right}_merged'
        _put_df(result_name, result)
        return self._success({
            'name': result_name,
            'columns': list(result.columns),
            'row_count': len(result),
            'rows': result.head(10).to_dict('records'),
        })

    def join(self, left: str, right: str, key: str,
             how: str = 'inner') -> dict:
        return self.merge(left, right, key, how)

    def pivot(self, dataset: str, index: str, columns: str,
              values: str, aggfunc: str = 'sum') -> dict:
        df = _get_df(dataset)
        if df is None:
            return self._error('not_found', f'Dataset not loaded: {dataset}')

        try:
            result = pd.pivot_table(
                df, index=index, columns=columns,
                values=values, aggfunc=aggfunc,
            )
            result = result.reset_index()
        except Exception as e:
            return self._error('invalid_input', f'Pivot failed: {e}')

        result_name = f'{dataset}_pivot'
        _put_df(result_name, result)
        return self._success({
            'name': result_name,
            'columns': list(result.columns),
            'rows': result.head(20).to_dict('records'),
            'row_count': len(result),
        })

    def reshape(self, dataset: str, method: str = 'melt') -> dict:
        df = _get_df(dataset)
        if df is None:
            return self._error('not_found', f'Dataset not loaded: {dataset}')

        try:
            if method == 'melt':
                result = pd.melt(df)
            elif method == 'transpose':
                result = df.T.reset_index()
            else:
                return self._error('invalid_input', f'Unknown reshape method: {method}')
        except Exception as e:
            return self._error('server_error', f'Reshape failed: {e}')

        result_name = f'{dataset}_{method}'
        _put_df(result_name, result)
        return self._success({
            'name': result_name,
            'columns': list(result.columns),
            'rows': result.head(20).to_dict('records'),
            'row_count': len(result),
        })

    def rename(self, dataset: str, column: str, name: str) -> dict:
        df = _get_df(dataset)
        if df is None:
            return self._error('not_found', f'Dataset not loaded: {dataset}')
        if column not in df.columns:
            return self._error('invalid_input', f'Column not found: {column}')
        df = df.rename(columns={column: name})
        _put_df(dataset, df)
        return self._success({
            'dataset': dataset, 'renamed': {column: name},
        })

    def split(self, dataset: str, column: str,
              delimiter: str = ' ') -> dict:
        df = _get_df(dataset)
        if df is None:
            return self._error('not_found', f'Dataset not loaded: {dataset}')
        if column not in df.columns:
            return self._error('invalid_input', f'Column not found: {column}')

        try:
            split_df = df[column].str.split(delimiter, expand=True)
            for i, col in enumerate(split_df.columns):
                df[f'{column}_{i+1}'] = split_df[col]
            _put_df(dataset, df)
        except Exception as e:
            return self._error('server_error', f'Split failed: {e}')

        return self._success({
            'dataset': dataset, 'split_column': column,
            'new_columns': [f'{column}_{i+1}' for i in range(len(split_df.columns))],
        })

    def merge_columns(self, dataset: str, columns: list[str],
                      name: str, separator: str = ' ') -> dict:
        df = _get_df(dataset)
        if df is None:
            return self._error('not_found', f'Dataset not loaded: {dataset}')
        for c in columns:
            if c not in df.columns:
                return self._error('invalid_input', f'Column not found: {c}')
        df[name] = df[columns].astype(str).agg(separator.join, axis=1)
        _put_df(dataset, df)
        return self._success({
            'dataset': dataset, 'merged_columns': columns, 'new_column': name,
        })

    def apply_formula(self, dataset: str, column: str,
                      formula: str) -> dict:
        df = _get_df(dataset)
        if df is None:
            return self._error('not_found', f'Dataset not loaded: {dataset}')
        try:
            df[column] = df.eval(formula)
            _put_df(dataset, df)
        except Exception as e:
            return self._error('invalid_input', f'Formula error: {e}')
        return self._success({
            'dataset': dataset, 'column': column, 'formula': formula,
        })

    def validate(self, dataset: str, rules: list[dict],
                 action: str = 'flag') -> dict:
        df = _get_df(dataset)
        if df is None:
            return self._error('not_found', f'Dataset not loaded: {dataset}')

        failures = []
        for rule in rules:
            col = rule.get('column', '')
            check = rule.get('check', '')
            value = rule.get('value')

            if col not in df.columns:
                failures.append({'rule': rule, 'error': f'Column not found: {col}'})
                continue

            if check == 'not_null':
                mask = df[col].isnull()
            elif check == 'unique':
                mask = df[col].duplicated()
            elif check == 'min':
                mask = df[col] < value
            elif check == 'max':
                mask = df[col] > value
            elif check == 'in':
                mask = ~df[col].isin(value)
            else:
                failures.append({'rule': rule, 'error': f'Unknown check: {check}'})
                continue

            fail_count = int(mask.sum())
            if fail_count > 0:
                failures.append({
                    'rule': rule,
                    'fail_count': fail_count,
                    'sample_indices': df.index[mask].tolist()[:10],
                })

        return self._success({
            'dataset': dataset,
            'rules_checked': len(rules),
            'failures': failures,
            'pass': len(failures) == 0,
        })

    def export(self, dataset: str, format: str = 'csv',
               path: str | None = None) -> dict:
        df = _get_df(dataset)
        if df is None:
            return self._error('not_found', f'Dataset not loaded: {dataset}')

        if format == 'clipboard':
            try:
                df.to_clipboard(index=False)
                return self._success({
                    'dataset': dataset, 'format': 'clipboard',
                    'row_count': len(df),
                })
            except Exception as e:
                return self._error('server_error', f'Clipboard export failed: {e}')

        if not path:
            _DATASETS_DIR.mkdir(parents=True, exist_ok=True)
            ext = 'csv' if format == 'csv' else 'json'
            path = str(_DATASETS_DIR / f'{dataset}.{ext}')

        try:
            if format == 'csv':
                df.to_csv(path, index=False)
            elif format == 'json':
                df.to_json(path, orient='records', indent=2)
            else:
                return self._error('invalid_input', f'Unknown format: {format}')
        except Exception as e:
            return self._error('server_error', f'Export failed: {e}')

        return self._success({
            'dataset': dataset, 'format': format, 'path': path,
            'row_count': len(df),
        })
