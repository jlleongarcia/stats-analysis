"""Tests for equality of variance across groups: Levene and Bartlett."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from stats_core._util import fmt_p, groups_from, significance_phrase
from stats_core.results import AssumptionCheck, ResultTable, TestResult


def _group_table(labels, arrays) -> ResultTable:
    return ResultTable(
        "Group spread",
        ["group", "n", "variance", "sd"],
        [[lab, a.size, float(a.var(ddof=1)), float(a.std(ddof=1))] for lab, a in zip(labels, arrays)],
    )


def levene(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    value_col, group_col = roles["values"], roles["group"]
    groups = groups_from(frame, value_col, group_col)
    labels, arrays = list(groups.keys()), list(groups.values())
    center = params.get("center", "median")  # "median" = Brown-Forsythe
    stat, p = stats.levene(*arrays, center=center)
    equal = p >= float(params.get("alpha", 0.05))
    return TestResult(
        test_id="levene",
        test_name=f"Levene's test for equality of variances (center = {center})",
        summary=(
            f"{group_col} ({len(arrays)} groups): W = {stat:.3f}, {fmt_p(p)} "
            f"({significance_phrase(p)}). Variances appear "
            + ("homogeneous." if equal else "heterogeneous.")
        ),
        apa=f"W = {stat:.3f}, {fmt_p(p)}",
        statistic={"W": float(stat)},
        p_value=float(p),
        assumptions=[
            AssumptionCheck("Homogeneity of variance", bool(equal),
                            f"Levene {fmt_p(p)}", statistic=float(stat), p_value=float(p))
        ],
        tables=[_group_table(labels, arrays)],
        plot_spec={
            "kind": "box",
            "data": {
                "value": np.concatenate(arrays).tolist(),
                "group": np.repeat(labels, [a.size for a in arrays]).tolist(),
            },
            "encoding": {"x": {"field": "group"}, "y": {"field": "value", "title": value_col}},
        },
    )


def bartlett(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    value_col, group_col = roles["values"], roles["group"]
    groups = groups_from(frame, value_col, group_col)
    labels, arrays = list(groups.keys()), list(groups.values())
    stat, p = stats.bartlett(*arrays)
    equal = p >= float(params.get("alpha", 0.05))
    return TestResult(
        test_id="bartlett",
        test_name="Bartlett's test for equality of variances",
        summary=(
            f"{group_col} ({len(arrays)} groups): chi^2({len(arrays) - 1}) = {stat:.3f}, "
            f"{fmt_p(p)} ({significance_phrase(p)})."
        ),
        apa=f"chi^2({len(arrays) - 1}) = {stat:.3f}, {fmt_p(p)}",
        statistic={"chi2": float(stat), "df": float(len(arrays) - 1)},
        p_value=float(p),
        assumptions=[
            AssumptionCheck("Homogeneity of variance", bool(equal), f"Bartlett {fmt_p(p)}",
                            statistic=float(stat), p_value=float(p)),
            AssumptionCheck("Normality within groups", None,
                            "Bartlett is sensitive to non-normality; prefer Levene if in doubt."),
        ],
        tables=[_group_table(labels, arrays)],
    )
