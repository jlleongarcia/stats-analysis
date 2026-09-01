"""Bivariate correlation (Pearson, Spearman, Kendall) and a correlation matrix."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from stats_core._util import DataError, clean_pair, fmt_p, r_magnitude, significance_phrase
from stats_core.results import AssumptionCheck, EffectSize, ResultTable, TestResult


def _fisher_ci(r: float, n: int, alpha: float = 0.05) -> tuple[float, float]:
    if n < 4 or abs(r) >= 1:
        return float("nan"), float("nan")
    z = np.arctanh(r)
    se = 1 / np.sqrt(n - 3)
    crit = stats.norm.ppf(1 - alpha / 2)
    return float(np.tanh(z - crit * se)), float(np.tanh(z + crit * se))


def _bivariate(frame, roles, params, method: str, test_id: str, name: str) -> TestResult:
    x_col, y_col = roles["x"], roles["y"]
    x, y = clean_pair(frame, x_col, y_col)
    n = x.size
    if method == "pearson":
        r, p = stats.pearsonr(x, y)
        lo, hi = _fisher_ci(float(r), n)
        sh = min(
            stats.shapiro(x).pvalue if 3 <= n <= 5000 else 1.0,
            stats.shapiro(y).pvalue if 3 <= n <= 5000 else 1.0,
        )
        assumptions = [
            AssumptionCheck(
                "Bivariate normality (approx.)",
                bool(sh >= 0.05),
                f"Weakest Shapiro-Wilk across the two variables: {fmt_p(sh)}",
                p_value=float(sh),
            ),
            AssumptionCheck("Linearity", None, "Inspect the scatter plot for a linear trend."),
        ]
    elif method == "spearman":
        r, p = stats.spearmanr(x, y)
        lo, hi = _fisher_ci(float(r), n)
        assumptions = [AssumptionCheck("Monotonic relationship", None, "Rank-based; no normality assumption.")]
    else:  # kendall
        r, p = stats.kendalltau(x, y)
        lo, hi = float("nan"), float("nan")
        assumptions = [AssumptionCheck("Monotonic relationship", None, "Rank-based; robust to outliers and ties.")]

    r = float(r)
    return TestResult(
        test_id=test_id,
        test_name=name,
        summary=(
            f"{x_col} vs {y_col} (n = {n}): "
            f"{'r' if method == 'pearson' else 'rho' if method == 'spearman' else 'tau'} "
            f"= {r:.3f}, {fmt_p(p)} ({significance_phrase(p)}); "
            f"{r_magnitude(r)} {'positive' if r >= 0 else 'negative'} association."
        ),
        apa=f"{'r' if method == 'pearson' else 'rho' if method == 'spearman' else 'tau'}"
        f"({n - 2}) = {r:.3f}, {fmt_p(p)}",
        statistic={"coefficient": r, "n": float(n), "rSquared": r * r if method == "pearson" else None},
        p_value=float(p),
        effect_sizes=[EffectSize(
            {"pearson": "Pearson r", "spearman": "Spearman rho", "kendall": "Kendall tau"}[method],
            r, lo, hi, r_magnitude(r),
        )],
        assumptions=assumptions,
        tables=[ResultTable("Correlation", ["coefficient", "ci95_low", "ci95_high", "p"],
                            [[r, lo, hi, float(p)]])],
        plot_specs=[{
            "kind": "scatter",
            "data": {"x": x.tolist(), "y": y.tolist()},
            "encoding": {"x": {"field": "x", "title": x_col}, "y": {"field": "y", "title": y_col}},
            "regression": True,
        }],
    )


def pearson(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    return _bivariate(frame, roles, params, "pearson", "pearson", "Pearson correlation")


def spearman(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    return _bivariate(frame, roles, params, "spearman", "spearman", "Spearman rank correlation")


def kendall(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    return _bivariate(frame, roles, params, "kendall", "kendall", "Kendall's tau correlation")


def correlation_matrix(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    cols = roles.get("columns") or []
    if len(cols) < 2:
        raise DataError("Select at least 2 numeric columns for a correlation matrix.")
    method = params.get("method", "pearson")
    if method not in {"pearson", "spearman", "kendall"}:
        raise DataError("method must be pearson, spearman or kendall.")
    data = frame[cols].apply(pd.to_numeric, errors="coerce")
    corr = data.corr(method=method)
    # pairwise p-values
    p_rows = []
    test = {"pearson": stats.pearsonr, "spearman": stats.spearmanr, "kendall": stats.kendalltau}[method]
    for a in cols:
        row = []
        for b in cols:
            if a == b:
                row.append(0.0)
                continue
            sub = data[[a, b]].dropna()
            row.append(float(test(sub[a], sub[b])[1]) if len(sub) > 2 else None)
        p_rows.append([a, *row])

    return TestResult(
        test_id="correlation_matrix",
        test_name=f"Correlation matrix ({method})",
        summary=f"{method.capitalize()} correlations among {len(cols)} variables.",
        p_value=None,
        tables=[
            ResultTable("Coefficients", ["variable", *cols],
                        [[a, *[float(corr.loc[a, b]) for b in cols]] for a in cols]),
            ResultTable("p-values", ["variable", *cols], p_rows),
        ],
        plot_specs=[{
            "kind": "heatmap",
            "data": {
                "row": np.repeat(cols, len(cols)).tolist(),
                "col": cols * len(cols),
                "value": [float(corr.loc[a, b]) for a in cols for b in cols],
            },
            "encoding": {"x": {"field": "col"}, "y": {"field": "row"}, "color": {"field": "value"}},
        }],
    )
