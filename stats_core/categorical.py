"""Tests for categorical / count data: chi-square, Fisher's exact, McNemar."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from stats_core._util import DataError, fmt_p, significance_phrase
from stats_core.results import AssumptionCheck, EffectSize, ResultTable, TestResult


def _crosstab(frame: pd.DataFrame, row_col: str, col_col: str) -> pd.DataFrame:
    for c in (row_col, col_col):
        if c not in frame.columns:
            raise DataError(f"Column {c!r} is not in the dataset.")
    tab = pd.crosstab(frame[row_col], frame[col_col])
    if tab.shape[0] < 2 or tab.shape[1] < 2:
        raise DataError("Both variables need at least 2 categories.")
    return tab


def chi_square_independence(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    row_col, col_col = roles["rows"], roles["columns"]
    tab = _crosstab(frame, row_col, col_col)
    chi2, p, dof, expected = stats.chi2_contingency(
        tab.to_numpy(), correction=bool(params.get("yates", tab.shape == (2, 2)))
    )
    n = tab.to_numpy().sum()
    min_dim = min(tab.shape) - 1
    cramers_v = np.sqrt(chi2 / (n * min_dim)) if min_dim > 0 else float("nan")
    low_expected = int((expected < 5).sum())
    return TestResult(
        test_id="chi_square_independence",
        test_name="Chi-square test of independence",
        summary=(
            f"{row_col} x {col_col}: chi^2({dof}) = {chi2:.3f}, {fmt_p(p)} "
            f"({significance_phrase(p)}); Cramer's V = {cramers_v:.3f}."
        ),
        apa=f"chi^2({dof}, N = {int(n)}) = {chi2:.3f}, {fmt_p(p)}, V = {cramers_v:.3f}",
        statistic={"chi2": float(chi2), "df": float(dof), "n": float(n)},
        p_value=float(p),
        effect_sizes=[EffectSize(
            "Cramer's V", float(cramers_v), None, None,
            "negligible" if cramers_v < 0.1 else "small" if cramers_v < 0.3
            else "medium" if cramers_v < 0.5 else "large",
        )],
        assumptions=[
            AssumptionCheck(
                "Expected counts >= 5",
                low_expected == 0,
                f"{low_expected} of {expected.size} expected cells are < 5"
                + ("; consider Fisher's exact test." if low_expected else "."),
            )
        ],
        tables=[
            ResultTable("Observed", ["", *[str(c) for c in tab.columns]],
                        [[str(idx), *[int(v) for v in row]] for idx, row in tab.iterrows()]),
            ResultTable("Expected", ["", *[str(c) for c in tab.columns]],
                        [[str(idx), *[float(v) for v in expected[i]]]
                         for i, idx in enumerate(tab.index)]),
        ],
        plot_spec={
            "kind": "heatmap",
            "data": {
                "row": np.repeat([str(i) for i in tab.index], tab.shape[1]).tolist(),
                "col": [str(c) for c in tab.columns] * tab.shape[0],
                "value": tab.to_numpy().reshape(-1).tolist(),
            },
            "encoding": {"x": {"field": "col"}, "y": {"field": "row"}, "color": {"field": "value"}},
        },
    )


def chi_square_goodness_of_fit(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    col = roles["values"]
    counts = frame[col].value_counts().sort_index()
    if counts.size < 2:
        raise DataError("Need at least 2 categories.")
    observed = counts.to_numpy(float)
    expected_param = params.get("expected")
    if expected_param:
        expected = np.asarray(expected_param, float)
        if expected.size != observed.size:
            raise DataError("Length of expected proportions must match the number of categories.")
        expected = expected / expected.sum() * observed.sum()
    else:
        expected = np.full(observed.size, observed.sum() / observed.size)
    chi2, p = stats.chisquare(observed, expected)
    dof = observed.size - 1
    return TestResult(
        test_id="chi_square_gof",
        test_name="Chi-square goodness-of-fit test",
        summary=(
            f"{col}: chi^2({dof}) = {chi2:.3f}, {fmt_p(p)} "
            f"({significance_phrase(p)}) vs "
            + ("the specified" if expected_param else "a uniform")
            + " distribution."
        ),
        apa=f"chi^2({dof}, N = {int(observed.sum())}) = {chi2:.3f}, {fmt_p(p)}",
        statistic={"chi2": float(chi2), "df": float(dof)},
        p_value=float(p),
        assumptions=[
            AssumptionCheck("Expected counts >= 5", bool((expected >= 5).all()),
                            f"min expected = {expected.min():.2f}")
        ],
        tables=[ResultTable(
            "Observed vs expected",
            ["category", "observed", "expected"],
            [[str(k), int(o), float(e)] for k, o, e in zip(counts.index, observed, expected)],
        )],
        plot_spec={
            "kind": "bar",
            "data": {"category": [str(k) for k in counts.index], "value": observed.tolist()},
            "encoding": {"x": {"field": "category"}, "y": {"field": "value", "title": "count"}},
        },
    )


def fisher_exact(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    row_col, col_col = roles["rows"], roles["columns"]
    tab = _crosstab(frame, row_col, col_col)
    if tab.shape != (2, 2):
        raise DataError("Fisher's exact test here supports 2x2 tables only.")
    alt = params.get("alternative", "two-sided")
    odds_ratio, p = stats.fisher_exact(tab.to_numpy(), alternative=alt)
    return TestResult(
        test_id="fisher_exact",
        test_name="Fisher's exact test (2x2)",
        summary=(
            f"{row_col} x {col_col}: odds ratio = {odds_ratio:.3f}, {fmt_p(p)} "
            f"({significance_phrase(p)})."
        ),
        apa=f"OR = {odds_ratio:.3f}, {fmt_p(p)}",
        statistic={"oddsRatio": float(odds_ratio)},
        p_value=float(p),
        effect_sizes=[EffectSize("Odds ratio", float(odds_ratio))],
        assumptions=[AssumptionCheck("Exact test", None,
                                     "No minimum expected-count requirement; valid for small samples.")],
        tables=[ResultTable("Observed", ["", *[str(c) for c in tab.columns]],
                            [[str(idx), *[int(v) for v in row]] for idx, row in tab.iterrows()])],
    )


def mcnemar_test(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    a_col, b_col = roles["first"], roles["second"]
    sub = frame[[a_col, b_col]].dropna()
    tab = pd.crosstab(sub[a_col], sub[b_col])
    if tab.shape != (2, 2):
        raise DataError("McNemar's test needs two paired binary variables (2x2 table).")
    b = int(tab.iloc[0, 1])
    c = int(tab.iloc[1, 0])
    n_disc = b + c
    exact = n_disc < 25
    if exact:
        p = float(stats.binomtest(min(b, c), n_disc, 0.5).pvalue) if n_disc else 1.0
        stat = float(min(b, c))
        stat_name = "min(b, c)"
    else:
        stat = (abs(b - c) - 1) ** 2 / n_disc
        p = float(stats.chi2.sf(stat, 1))
        stat_name = "chi^2 (continuity-corrected)"
    return TestResult(
        test_id="mcnemar",
        test_name="McNemar's test (paired nominal)",
        summary=(
            f"Discordant pairs: b = {b}, c = {c}. "
            f"{stat_name} = {stat:.3f}, {fmt_p(p)} ({significance_phrase(p)}); "
            + ("exact binomial" if exact else "asymptotic") + " version."
        ),
        apa=f"{stat_name} = {stat:.3f}, {fmt_p(p)}",
        statistic={"b": float(b), "c": float(c)},
        p_value=p,
        tables=[ResultTable("Paired table", ["", *[str(c2) for c2 in tab.columns]],
                            [[str(idx), *[int(v) for v in row]] for idx, row in tab.iterrows()])],
    )
