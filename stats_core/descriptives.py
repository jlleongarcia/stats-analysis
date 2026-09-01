"""Descriptive statistics for one or more numeric columns."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from stats_core._util import DataError, numeric_series
from stats_core.results import ResultTable, TestResult

_STAT_COLUMNS = [
    "n",
    "missing",
    "mean",
    "sd",
    "se",
    "min",
    "q1",
    "median",
    "q3",
    "max",
    "iqr",
    "skew",
    "kurtosis",
    "ci95_low",
    "ci95_high",
]


def _describe_one(name: str, raw: pd.Series) -> list:
    series = pd.to_numeric(raw, errors="coerce")
    values = series.dropna().to_numpy(float)
    n = values.size
    missing = int(series.isna().sum())
    if n == 0:
        return [name] + [0, missing] + [None] * (len(_STAT_COLUMNS) - 2)
    mean = float(np.mean(values))
    sd = float(np.std(values, ddof=1)) if n > 1 else float("nan")
    se = sd / np.sqrt(n) if n > 1 else float("nan")
    q1, median, q3 = (float(x) for x in np.percentile(values, [25, 50, 75]))
    if n > 1 and np.isfinite(se) and se > 0:
        margin = stats.t.ppf(0.975, n - 1) * se
        ci_low, ci_high = mean - margin, mean + margin
    else:
        ci_low = ci_high = float("nan")
    return [
        name,
        n,
        missing,
        mean,
        sd,
        se,
        float(np.min(values)),
        q1,
        median,
        q3,
        float(np.max(values)),
        q3 - q1,
        float(stats.skew(values)) if n > 2 else float("nan"),
        float(stats.kurtosis(values)) if n > 3 else float("nan"),
        ci_low,
        ci_high,
    ]


def describe(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    columns = roles.get("columns") or []
    if isinstance(columns, str):
        columns = [columns]
    if not columns:
        raise DataError("Select at least one numeric column to describe.")
    group_col = roles.get("group")

    table = ResultTable(
        title="Descriptive statistics", columns=["variable", *_STAT_COLUMNS], rows=[]
    )
    if group_col:
        if group_col not in frame.columns:
            raise DataError(f"Grouping column {group_col!r} is not in the dataset.")
        table.columns = ["variable", "group", *_STAT_COLUMNS]
        for col in columns:
            for level, chunk in frame.groupby(group_col, sort=True):
                row = _describe_one(col, chunk[col])
                table.rows.append([col, str(level), *row[1:]])
    else:
        for col in columns:
            table.rows.append(_describe_one(col, numeric_series(frame, col)))

    result = TestResult(
        test_id="descriptives",
        test_name="Descriptive statistics",
        summary=(
            f"Summary statistics for {len(columns)} variable(s)"
            + (f", split by {group_col}." if group_col else ".")
        ),
        tables=[table],
    )
    if len(columns) == 1 and not group_col:
        col = columns[0]
        values = numeric_series(frame, col).dropna().to_numpy(float)
        result.plot_specs = [{
            "kind": "histogram",
            "data": {"x": values.tolist()},
            "encoding": {"x": {"field": "x", "title": col}},
        }]
    return result
