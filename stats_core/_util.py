"""Small shared helpers: data coercion, p-value formatting, effect-size labels."""

from __future__ import annotations

import numpy as np
import pandas as pd


class DataError(ValueError):
    """Raised when the supplied data/roles cannot support the requested test."""


def numeric_series(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        raise DataError(f"Column {column!r} is not in the dataset.")
    series = pd.to_numeric(frame[column], errors="coerce")
    return series


def clean_1d(frame: pd.DataFrame, column: str) -> np.ndarray:
    """Numeric column with NaNs dropped, as a float array."""
    series = numeric_series(frame, column).dropna()
    if series.empty:
        raise DataError(f"Column {column!r} has no numeric values.")
    return series.to_numpy(dtype=float)


def clean_pair(frame: pd.DataFrame, col_a: str, col_b: str) -> tuple[np.ndarray, np.ndarray]:
    """Two numeric columns aligned row-wise, dropping rows where either is NaN."""
    sub = pd.DataFrame(
        {
            "a": numeric_series(frame, col_a),
            "b": numeric_series(frame, col_b),
        }
    ).dropna()
    if len(sub) < 2:
        raise DataError(
            f"Columns {col_a!r} and {col_b!r} share fewer than 2 complete rows."
        )
    return sub["a"].to_numpy(float), sub["b"].to_numpy(float)


def groups_from(
    frame: pd.DataFrame, value_col: str, group_col: str, min_per_group: int = 2
) -> dict[str, np.ndarray]:
    """Split a numeric column by the levels of a grouping column."""
    if group_col not in frame.columns:
        raise DataError(f"Grouping column {group_col!r} is not in the dataset.")
    sub = pd.DataFrame(
        {"value": numeric_series(frame, value_col), "group": frame[group_col]}
    ).dropna()
    out: dict[str, np.ndarray] = {}
    for level, chunk in sub.groupby("group", sort=True):
        arr = chunk["value"].to_numpy(float)
        if arr.size >= min_per_group:
            out[str(level)] = arr
    if len(out) < 2:
        raise DataError(
            f"Grouping column {group_col!r} needs at least 2 levels with "
            f">= {min_per_group} numeric observations each."
        )
    return out


def fmt_p(p: float | None) -> str:
    if p is None or (isinstance(p, float) and np.isnan(p)):
        return "p = n/a"
    if p < 0.001:
        return "p < .001"
    return f"p = {p:.3f}".replace("0.", ".", 1)


def cohen_d_magnitude(d: float) -> str:
    d = abs(d)
    if d < 0.2:
        return "negligible"
    if d < 0.5:
        return "small"
    if d < 0.8:
        return "medium"
    return "large"


def eta_squared_magnitude(eta2: float) -> str:
    if eta2 < 0.01:
        return "negligible"
    if eta2 < 0.06:
        return "small"
    if eta2 < 0.14:
        return "medium"
    return "large"


def r_magnitude(r: float) -> str:
    r = abs(r)
    if r < 0.1:
        return "negligible"
    if r < 0.3:
        return "small"
    if r < 0.5:
        return "medium"
    return "large"


def cramers_v_magnitude(v: float, dof: int) -> str:
    # Cohen's benchmarks scaled by the table's smaller dimension.
    k = max(dof, 1)
    small, medium = 0.1 / np.sqrt(k) * np.sqrt(1), 0.3
    if v < 0.1:
        return "negligible"
    if v < 0.3:
        return "small"
    if v < 0.5:
        return "medium"
    return "large"


def significance_phrase(p: float | None, alpha: float = 0.05) -> str:
    if p is None or np.isnan(p):
        return "could not be computed"
    return "statistically significant" if p < alpha else "not statistically significant"
