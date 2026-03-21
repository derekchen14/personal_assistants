from __future__ import annotations

import pandas as pd

from backend.utilities.services import ToolService, _get_df, _put_df


class TransformService(ToolService):

    def merge(self, left:str, right:str, key:str,
              how:str='inner') -> dict:
        left_df = _get_df(left)
        right_df = _get_df(right)
        if left_df is None:
            return self._error('not_found', f'Dataset not loaded: {left}')
        if right_df is None:
            return self._error('not_found', f'Dataset not loaded: {right}')

        try:
            result = pd.merge(left_df, right_df, on=key, how=how)
        except Exception as ecp:
            return self._error('invalid_input', f'Merge failed: {ecp}')

        result_name = f'{left}_{right}_merged'
        _put_df(result_name, result)
        return self._success({
            'name': result_name,
            'columns': list(result.columns),
            'row_count': len(result),
            'rows': result.head(10).to_dict('records'),
        })

    def join(self, left:str, right:str, key:str,
             how:str='inner') -> dict:
        return self.merge(left, right, key, how)

    def pivot(self, dataset:str, index:str, columns:str,
              values:str, aggfunc:str='sum') -> dict:
        df = _get_df(dataset)
        if df is None:
            return self._error('not_found', f'Dataset not loaded: {dataset}')

        try:
            result = pd.pivot_table(
                df, index=index, columns=columns,
                values=values, aggfunc=aggfunc,
            )
            result = result.reset_index()
        except Exception as ecp:
            return self._error('invalid_input', f'Pivot failed: {ecp}')

        result_name = f'{dataset}_pivot'
        _put_df(result_name, result)
        return self._success({
            'name': result_name,
            'columns': list(result.columns),
            'rows': result.head(20).to_dict('records'),
            'row_count': len(result),
        })

    def reshape(self, dataset:str, method:str='melt') -> dict:
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
        except Exception as ecp:
            return self._error('server_error', f'Reshape failed: {ecp}')

        result_name = f'{dataset}_{method}'
        _put_df(result_name, result)
        return self._success({
            'name': result_name,
            'columns': list(result.columns),
            'rows': result.head(20).to_dict('records'),
            'row_count': len(result),
        })

    def rename(self, dataset:str, column:str, name:str) -> dict:
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

    def split(self, dataset:str, column:str,
              delimiter:str=' ') -> dict:
        df = _get_df(dataset)
        if df is None:
            return self._error('not_found', f'Dataset not loaded: {dataset}')
        if column not in df.columns:
            return self._error('invalid_input', f'Column not found: {column}')

        try:
            split_df = df[column].str.split(delimiter, expand=True)
            for idx, col in enumerate(split_df.columns):
                df[f'{column}_{idx+1}'] = split_df[col]
            _put_df(dataset, df)
        except Exception as ecp:
            return self._error('server_error', f'Split failed: {ecp}')

        return self._success({
            'dataset': dataset, 'split_column': column,
            'new_columns': [f'{column}_{idx+1}' for idx in range(len(split_df.columns))],
        })

    def merge_columns(self, dataset:str, columns:list[str],
                      name:str, separator:str=' ') -> dict:
        df = _get_df(dataset)
        if df is None:
            return self._error('not_found', f'Dataset not loaded: {dataset}')
        for col in columns:
            if col not in df.columns:
                return self._error('invalid_input', f'Column not found: {col}')
        df[name] = df[columns].astype(str).agg(separator.join, axis=1)
        _put_df(dataset, df)
        return self._success({
            'dataset': dataset, 'merged_columns': columns, 'new_column': name,
        })

    def apply_formula(self, dataset:str, column:str,
                      formula:str) -> dict:
        df = _get_df(dataset)
        if df is None:
            return self._error('not_found', f'Dataset not loaded: {dataset}')
        try:
            df[column] = df.eval(formula)
            _put_df(dataset, df)
        except Exception as ecp:
            return self._error('invalid_input', f'Formula error: {ecp}')
        return self._success({
            'dataset': dataset, 'column': column, 'formula': formula,
        })

    def validate(self, dataset:str, rules:list[dict],
                 action:str='flag') -> dict:
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

    def export(self, dataset:str, format:str='csv',
               path:str|None=None) -> dict:
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
            except Exception as ecp:
                return self._error('server_error', f'Clipboard export failed: {ecp}')

        if not path:
            _DATASETS_DIR = Path(__file__).resolve().parents[2] / 'database' / 'datasets'
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
        except Exception as ecp:
            return self._error('server_error', f'Export failed: {ecp}')

        return self._success({
            'dataset': dataset, 'format': format, 'path': path,
            'row_count': len(df),
        })
