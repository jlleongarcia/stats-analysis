"""Reliability / item analysis: Cronbach's alpha, corrected item-total
correlations, and alpha-if-item-deleted."""

from __future__ import annotations

import numpy as np
import pandas as pd

from stats_core._util import DataError
from stats_core.results import ResultTable, TestResult


def _cronbach_alpha(item_matrix: np.ndarray) -> float:
    k = item_matrix.shape[1]
    if k < 2:
        return float("nan")
    item_vars = item_matrix.var(axis=0, ddof=1)
    total_var = item_matrix.sum(axis=1).var(ddof=1)
    if total_var == 0:
        return float("nan")
    return float(k / (k - 1) * (1 - item_vars.sum() / total_var))


def reliability_analysis(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    cols = roles.get("columns") or []
    if len(cols) < 3:
        raise DataError("Reliability analysis needs at least 3 items (numeric columns).")
    sub = frame[cols].apply(pd.to_numeric, errors="coerce").dropna()
    if len(sub) < 3:
        raise DataError("Fewer than 3 complete rows across the selected items.")
    X = sub.to_numpy(float)
    n = X.shape[0]
    alpha = _cronbach_alpha(X)

    rows = []
    for j, col in enumerate(cols):
        item = X[:, j]
        rest = X.sum(axis=1) - item
        r_it = float(np.corrcoef(item, rest)[0, 1]) if n > 2 else float("nan")
        alpha_wo = _cronbach_alpha(np.delete(X, j, axis=1))
        rows.append([col, float(item.mean()), float(item.std(ddof=1)), r_it, alpha_wo])

    return TestResult(
        test_id="reliability_analysis",
        test_name="Reliability analysis (Cronbach's alpha)",
        summary=(
            f"{len(cols)} items, n = {n}: Cronbach's alpha = {alpha:.3f} "
            f"({'acceptable' if alpha >= 0.7 else 'questionable' if alpha >= 0.6 else 'poor'} "
            "internal consistency by common rule-of-thumb thresholds)."
        ),
        apa=f"alpha = {alpha:.3f} ({len(cols)} items, n = {n})",
        statistic={"cronbachAlpha": alpha, "nItems": float(len(cols))},
        p_value=None,
        tables=[ResultTable(
            "Item statistics",
            ["item", "mean", "sd", "corrected_item_total_r", "alpha_if_deleted"],
            rows,
        )],
        plot_specs=[{
            "kind": "bar",
            "data": {"category": cols, "value": [r[3] for r in rows]},
            "encoding": {"x": {"field": "category"}, "y": {"field": "value", "title": "item-total correlation"}},
        }],
        notes=["Rule of thumb: alpha >= .9 excellent, >= .8 good, >= .7 acceptable, "
               ">= .6 questionable, < .6 poor."],
    )
