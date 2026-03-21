from __future__ import annotations

import base64
import io

import pandas as pd

from backend.utilities.services import ToolService, _workspace, _get_df


class QueryService(ToolService):

    def execute_sql(self, query:str, dataset:str|None=None) -> dict:
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
        except Exception as ecp:
            return self._error('invalid_input', f'SQL error: {ecp}')

        return self._success({
            'columns': list(result_df.columns),
            'rows': result_df.to_dict('records'),
            'row_count': len(result_df),
        })

    def execute_python(self, code:str, dataset:str|None=None) -> dict:
        env = {'pd': pd}
        for name, df in _workspace.items():
            env[name] = df
        if dataset and dataset in _workspace:
            env['df'] = _workspace[dataset]

        try:
            result = eval(code, {'__builtins__': {}}, env)
        except Exception as ecp:
            return self._error('invalid_input', f'Python error: {ecp}')

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

    def analyze_column(self, dataset:str, column:str,
                       metrics:list[str]|None=None) -> dict:
        df = _get_df(dataset)
        if df is None:
            return self._error('not_found', f'Dataset not loaded: {dataset}')
        if column not in df.columns:
            return self._error('invalid_input', f'Column not found: {column}')

        col = df[column]
        all_metrics = metrics or ['min', 'max', 'mean', 'median', 'std', 'nulls', 'unique']
        result = {'column': column, 'dtype': str(col.dtype)}

        for metric in all_metrics:
            try:
                if metric == 'min':
                    result['min'] = float(col.min()) if pd.api.types.is_numeric_dtype(col) else str(col.min())
                elif metric == 'max':
                    result['max'] = float(col.max()) if pd.api.types.is_numeric_dtype(col) else str(col.max())
                elif metric == 'mean' and pd.api.types.is_numeric_dtype(col):
                    result['mean'] = float(col.mean())
                elif metric == 'median' and pd.api.types.is_numeric_dtype(col):
                    result['median'] = float(col.median())
                elif metric == 'std' and pd.api.types.is_numeric_dtype(col):
                    result['std'] = float(col.std())
                elif metric == 'nulls':
                    result['nulls'] = int(col.isnull().sum())
                elif metric == 'unique':
                    result['unique'] = int(col.nunique())
            except Exception:
                result[metric] = None

        return self._success(result)


class ChartService(ToolService):

    def render(self, dataset:str, chart_type:str,
               x:str|None=None, y:str|None=None,
               title:str|None=None, color:str|None=None) -> dict:
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

        except Exception as ecp:
            plt.close(fig)
            return self._error('server_error', f'Chart rendering failed: {ecp}')

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
