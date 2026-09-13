"""Normality pre-check for Shewhart charts.

Shewhart limits assume the individual measurements are roughly normal; severe
non-normality inflates the false-alarm rate. The check is **advisory** - it
annotates the result and never blocks the analysis.

This is deliberately not a fourth normality test. ``stats_core.normality``
already owns the implementations, but its functions are registry-shaped
(``frame, roles, params -> TestResult``) and a control chart needs a single
:class:`~stats_core.results.AssumptionCheck` it can attach. This module is that
adapter, and it applies the same selection rule the original SPC tool used:
Shapiro-Wilk within its valid range, Anderson-Darling beyond it.
"""

from __future__ import annotations

import pandas as pd
from scipy import stats

from stats_core.results import AssumptionCheck

SHAPIRO_MAX_N = 5000


def normality_precheck(values: pd.Series, *, alpha: float = 0.05) -> AssumptionCheck:
    """Assess whether *values* are plausibly normal, as an assumption check."""
    clean = pd.to_numeric(values, errors="coerce").dropna().to_numpy(float)
    n = clean.size

    if n < 3:
        return AssumptionCheck(
            name="Approximate normality",
            passed=None,
            detail=f"Only {n} observations: too few to assess normality (need at least 3).",
        )

    if n <= SHAPIRO_MAX_N:
        statistic, p_value = (float(v) for v in stats.shapiro(clean))
        normal = p_value >= alpha
        detail = (
            f"Shapiro-Wilk W = {statistic:.4f}, p = {p_value:.4f} (n = {n}). "
            + (
                "Consistent with normality; Shewhart limits apply as usual."
                if normal
                else "Non-normality detected, so the nominal false-alarm rate no "
                "longer holds. Consider a transformation, or investigate whether "
                "the data mixes sub-populations."
            )
        )
        return AssumptionCheck(
            name="Approximate normality",
            passed=normal,
            detail=detail,
            statistic=statistic,
            p_value=p_value,
        )

    # Shapiro-Wilk is not valid past n = 5000; Anderson-Darling has no direct
    # p-value, so the verdict comes from the 5% critical value instead.
    result = stats.anderson(clean, dist="norm")
    statistic = float(result.statistic)
    critical = float(result.critical_values[2])  # index 2 is the 5% level
    normal = statistic < critical
    return AssumptionCheck(
        name="Approximate normality",
        passed=normal,
        detail=(
            f"Anderson-Darling A2 = {statistic:.4f} against a 5% critical value "
            f"of {critical:.4f} (n = {n}). "
            + (
                "Consistent with normality."
                if normal
                else "Non-normality detected; interpret the control limits with caution."
            )
        ),
        statistic=statistic,
    )


def normality_summary(check: AssumptionCheck) -> dict:
    """JSON-friendly form of the pre-check, for the Studio protocol."""
    return {
        "name": check.name,
        "passed": check.passed,
        "detail": check.detail,
        "statistic": None if check.statistic is None else float(check.statistic),
        "pValue": None if check.p_value is None else float(check.p_value),
    }


__all__ = ["normality_precheck", "normality_summary", "SHAPIRO_MAX_N"]
