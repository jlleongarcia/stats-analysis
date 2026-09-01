"""Normality / distribution-shape tests for a single numeric column."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from stats_core._util import DataError, clean_1d, fmt_p
from stats_core.results import AssumptionCheck, ResultTable, TestResult


def _hist_spec(values: np.ndarray, field: str) -> dict:
    return {
        "kind": "histogram",
        "data": {"x": values.tolist()},
        "encoding": {"x": {"field": "x", "title": field}},
        "overlay": "normal",
    }


def shapiro_wilk(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    col = roles["values"]
    x = clean_1d(frame, col)
    if x.size < 3:
        raise DataError("Shapiro-Wilk needs at least 3 observations.")
    if x.size > 5000:
        note = "n > 5000: p-value is approximate for the Shapiro-Wilk test."
    else:
        note = None
    w, p = stats.shapiro(x)
    alpha = float(params.get("alpha", 0.05))
    normal = p >= alpha
    res = TestResult(
        test_id="shapiro_wilk",
        test_name="Shapiro-Wilk normality test",
        summary=(
            f"{col}: W = {w:.3f}, {fmt_p(p)}. The distribution is "
            + ("consistent with" if normal else "inconsistent with")
            + " normality at alpha = "
            + f"{alpha:g}."
        ),
        apa=f"W = {w:.3f}, {fmt_p(p)}",
        statistic={"W": float(w)},
        p_value=float(p),
        assumptions=[
            AssumptionCheck(
                name="Normality",
                passed=bool(normal),
                detail=f"Shapiro-Wilk W = {w:.3f}, {fmt_p(p)}",
                statistic=float(w),
                p_value=float(p),
            )
        ],
        plot_specs=[_hist_spec(x, col)],
    )
    if note:
        res.add_note(note)
    return res


def normaltest(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    """D'Agostino & Pearson omnibus test (skew + kurtosis)."""
    col = roles["values"]
    x = clean_1d(frame, col)
    if x.size < 8:
        raise DataError("D'Agostino-Pearson needs at least 8 observations.")
    k2, p = stats.normaltest(x)
    alpha = float(params.get("alpha", 0.05))
    normal = p >= alpha
    return TestResult(
        test_id="dagostino_pearson",
        test_name="D'Agostino-Pearson omnibus normality test",
        summary=(
            f"{col}: K^2 = {k2:.3f}, {fmt_p(p)}. Combined skew/kurtosis is "
            + ("consistent with" if normal else "inconsistent with")
            + " normality."
        ),
        apa=f"K^2 = {k2:.3f}, {fmt_p(p)}",
        statistic={"K2": float(k2), "skew": float(stats.skew(x)), "kurtosis": float(stats.kurtosis(x))},
        p_value=float(p),
        assumptions=[
            AssumptionCheck(
                name="Normality",
                passed=bool(normal),
                detail=f"D'Agostino-Pearson K^2 = {k2:.3f}, {fmt_p(p)}",
                statistic=float(k2),
                p_value=float(p),
            )
        ],
        plot_specs=[_hist_spec(x, col)],
    )


def ks_normal(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    """One-sample Kolmogorov-Smirnov against a fitted normal distribution."""
    col = roles["values"]
    x = clean_1d(frame, col)
    mu, sigma = float(np.mean(x)), float(np.std(x, ddof=1))
    if sigma == 0:
        raise DataError("Column is constant; KS test is undefined.")
    # standardize and compare to the standard normal (equivalent, and avoids a
    # scipy `args=` dispatch quirk on some builds)
    d, p = stats.kstest((x - mu) / sigma, "norm")
    alpha = float(params.get("alpha", 0.05))
    normal = p >= alpha
    return TestResult(
        test_id="ks_normal",
        test_name="Kolmogorov-Smirnov test (vs fitted normal)",
        summary=f"{col}: D = {d:.3f}, {fmt_p(p)}.",
        apa=f"D = {d:.3f}, {fmt_p(p)}",
        statistic={"D": float(d), "mu": mu, "sigma": sigma},
        p_value=float(p),
        assumptions=[
            AssumptionCheck(
                name="Normality",
                passed=bool(normal),
                detail=f"KS D = {d:.3f}, {fmt_p(p)} (parameters estimated from data; "
                "treat p as approximate)",
                statistic=float(d),
                p_value=float(p),
            )
        ],
        plot_specs=[_hist_spec(x, col)],
    ).add_note(
        "Distribution parameters were estimated from the sample, so the KS "
        "p-value is liberal; prefer Shapiro-Wilk for n < 5000."
    )


def anderson_darling(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    col = roles["values"]
    x = clean_1d(frame, col)
    out = stats.anderson(x, dist="norm")
    rows = [
        [float(sl), float(cv), bool(out.statistic > cv)]
        for sl, cv in zip(out.significance_level, out.critical_values)
    ]
    # Reject normality at 5% if A^2 exceeds the 5% critical value.
    idx5 = int(np.argmin(np.abs(np.asarray(out.significance_level) - 5.0)))
    reject5 = bool(out.statistic > out.critical_values[idx5])
    return TestResult(
        test_id="anderson_darling",
        test_name="Anderson-Darling normality test",
        summary=(
            f"{col}: A^2 = {out.statistic:.3f}. Normality is "
            + ("rejected" if reject5 else "not rejected")
            + " at the 5% level."
        ),
        apa=f"A^2 = {out.statistic:.3f}",
        statistic={"A2": float(out.statistic)},
        p_value=None,
        assumptions=[
            AssumptionCheck(
                name="Normality",
                passed=not reject5,
                detail=f"A^2 = {out.statistic:.3f} vs 5% critical value "
                f"{out.critical_values[idx5]:.3f}",
                statistic=float(out.statistic),
            )
        ],
        tables=[
            ResultTable(
                title="Critical values",
                columns=["significance_level_pct", "critical_value", "reject_normality"],
                rows=rows,
            )
        ],
        plot_specs=[_hist_spec(x, col)],
    )
