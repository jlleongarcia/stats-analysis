"""t-tests: one-sample, independent (Welch / Student), and paired."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from stats_core._util import (
    DataError,
    clean_1d,
    clean_pair,
    cohen_d_magnitude,
    fmt_p,
    groups_from,
    significance_phrase,
)
from stats_core.results import AssumptionCheck, EffectSize, ResultTable, TestResult

_ALTERNATIVES = {"two-sided", "less", "greater"}


def _alt(params: dict) -> str:
    alt = params.get("alternative", "two-sided")
    if alt not in _ALTERNATIVES:
        raise DataError(f"alternative must be one of {sorted(_ALTERNATIVES)}")
    return alt


def _ci_diff(mean_diff: float, se: float, df: float, alt: str) -> tuple[float, float]:
    if not np.isfinite(se) or se == 0:
        return float("nan"), float("nan")
    if alt == "two-sided":
        crit = stats.t.ppf(0.975, df)
        return mean_diff - crit * se, mean_diff + crit * se
    crit = stats.t.ppf(0.95, df)
    if alt == "greater":
        return mean_diff - crit * se, float("inf")
    return float("-inf"), mean_diff + crit * se


def one_sample_t(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    col = roles["values"]
    x = clean_1d(frame, col)
    popmean = float(params.get("popmean", 0.0))
    alt = _alt(params)
    res = stats.ttest_1samp(x, popmean, alternative=alt)
    n = x.size
    mean = float(np.mean(x))
    sd = float(np.std(x, ddof=1))
    se = sd / np.sqrt(n)
    d = (mean - popmean) / sd if sd > 0 else float("nan")
    lo, hi = _ci_diff(mean - popmean, se, n - 1, alt)
    shap_p = stats.shapiro(x).pvalue if 3 <= n <= 5000 else float("nan")
    return TestResult(
        test_id="one_sample_t",
        test_name="One-sample t-test",
        summary=(
            f"Mean of {col} ({mean:.4g}) vs {popmean:g}: "
            f"t({n - 1}) = {res.statistic:.3f}, {fmt_p(res.pvalue)} "
            f"({significance_phrase(res.pvalue)})."
        ),
        apa=f"t({n - 1}) = {res.statistic:.3f}, {fmt_p(res.pvalue)}, d = {d:.3f}",
        statistic={"t": float(res.statistic), "df": float(n - 1), "mean": mean, "se": se},
        p_value=float(res.pvalue),
        effect_sizes=[EffectSize("Cohen's d", float(d), lo / sd if sd else None,
                                 hi / sd if sd else None, cohen_d_magnitude(d))],
        assumptions=[
            AssumptionCheck(
                "Normality of the variable",
                None if np.isnan(shap_p) else bool(shap_p >= 0.05),
                f"Shapiro-Wilk {fmt_p(shap_p)}" if not np.isnan(shap_p)
                else "n outside 3-5000; not assessed",
                p_value=None if np.isnan(shap_p) else float(shap_p),
            )
        ],
        tables=[
            ResultTable(
                "Sample",
                ["n", "mean", "sd", "se", "mean_diff", "ci95_low", "ci95_high"],
                [[n, mean, sd, se, mean - popmean, lo, hi]],
            )
        ],
        plot_spec={
            "kind": "histogram",
            "data": {"x": x.tolist()},
            "encoding": {"x": {"field": "x", "title": col}},
            "rule": popmean,
        },
    )


def _independent(frame, roles, params, equal_var: bool, test_id: str, name: str) -> TestResult:
    value_col = roles["values"]
    group_col = roles["group"]
    groups = groups_from(frame, value_col, group_col)
    if len(groups) != 2:
        raise DataError(
            f"{name} needs exactly 2 groups; {group_col!r} has {len(groups)}."
        )
    (g1, a), (g2, b) = groups.items()
    alt = _alt(params)
    res = stats.ttest_ind(a, b, equal_var=equal_var, alternative=alt)

    n1, n2 = a.size, b.size
    m1, m2 = float(np.mean(a)), float(np.mean(b))
    v1, v2 = float(np.var(a, ddof=1)), float(np.var(b, ddof=1))
    mean_diff = m1 - m2
    # pooled SD for Hedges/Cohen
    sp = np.sqrt(((n1 - 1) * v1 + (n2 - 1) * v2) / (n1 + n2 - 2))
    d = mean_diff / sp if sp > 0 else float("nan")
    J = 1 - 3 / (4 * (n1 + n2) - 9)  # Hedges' correction
    g = d * J
    if equal_var:
        se = sp * np.sqrt(1 / n1 + 1 / n2)
        df = n1 + n2 - 2
    else:
        se = np.sqrt(v1 / n1 + v2 / n2)
        df = (v1 / n1 + v2 / n2) ** 2 / (
            (v1 / n1) ** 2 / (n1 - 1) + (v2 / n2) ** 2 / (n2 - 1)
        )
    lo, hi = _ci_diff(mean_diff, se, df, alt)
    lev_p = stats.levene(a, b, center="median").pvalue
    sh1 = stats.shapiro(a).pvalue if 3 <= n1 <= 5000 else float("nan")
    sh2 = stats.shapiro(b).pvalue if 3 <= n2 <= 5000 else float("nan")

    assumptions = [
        AssumptionCheck(
            "Homogeneity of variance (Levene)",
            bool(lev_p >= 0.05),
            f"Levene {fmt_p(lev_p)}"
            + ("" if equal_var else "; Welch correction applied so this is not required"),
            p_value=float(lev_p),
        ),
        AssumptionCheck(
            f"Normality of {g1}",
            None if np.isnan(sh1) else bool(sh1 >= 0.05),
            f"Shapiro-Wilk {fmt_p(sh1)}" if not np.isnan(sh1) else "not assessed",
            p_value=None if np.isnan(sh1) else float(sh1),
        ),
        AssumptionCheck(
            f"Normality of {g2}",
            None if np.isnan(sh2) else bool(sh2 >= 0.05),
            f"Shapiro-Wilk {fmt_p(sh2)}" if not np.isnan(sh2) else "not assessed",
            p_value=None if np.isnan(sh2) else float(sh2),
        ),
    ]
    return TestResult(
        test_id=test_id,
        test_name=name,
        summary=(
            f"{g1} (M = {m1:.4g}, n = {n1}) vs {g2} (M = {m2:.4g}, n = {n2}): "
            f"t({df:.1f}) = {res.statistic:.3f}, {fmt_p(res.pvalue)} "
            f"({significance_phrase(res.pvalue)}); mean difference {mean_diff:.4g}."
        ),
        apa=f"t({df:.2f}) = {res.statistic:.3f}, {fmt_p(res.pvalue)}, g = {g:.3f}",
        statistic={"t": float(res.statistic), "df": float(df), "meanDifference": mean_diff, "se": float(se)},
        p_value=float(res.pvalue),
        effect_sizes=[
            EffectSize("Cohen's d", float(d), None, None, cohen_d_magnitude(d)),
            EffectSize("Hedges' g", float(g), None, None, cohen_d_magnitude(g)),
        ],
        assumptions=assumptions,
        tables=[
            ResultTable(
                "Group descriptives",
                ["group", "n", "mean", "sd"],
                [[g1, n1, m1, np.sqrt(v1)], [g2, n2, m2, np.sqrt(v2)]],
            ),
            ResultTable(
                "Difference",
                ["mean_diff", "se", "df", "ci95_low", "ci95_high"],
                [[mean_diff, float(se), float(df), lo, hi]],
            ),
        ],
        plot_spec={
            "kind": "box",
            "data": {
                "value": [*a.tolist(), *b.tolist()],
                "group": [g1] * n1 + [g2] * n2,
            },
            "encoding": {"x": {"field": "group"}, "y": {"field": "value", "title": value_col}},
        },
    )


def welch_t(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    return _independent(frame, roles, params, False, "welch_t", "Welch's t-test (independent samples)")


def student_t(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    return _independent(frame, roles, params, True, "student_t", "Student's t-test (independent samples)")


def paired_t(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    col_a, col_b = roles["first"], roles["second"]
    a, b = clean_pair(frame, col_a, col_b)
    alt = _alt(params)
    res = stats.ttest_rel(a, b, alternative=alt)
    diff = a - b
    n = diff.size
    md = float(np.mean(diff))
    sd = float(np.std(diff, ddof=1))
    se = sd / np.sqrt(n)
    d = md / sd if sd > 0 else float("nan")
    lo, hi = _ci_diff(md, se, n - 1, alt)
    sh_p = stats.shapiro(diff).pvalue if 3 <= n <= 5000 else float("nan")
    return TestResult(
        test_id="paired_t",
        test_name="Paired-samples t-test",
        summary=(
            f"{col_a} vs {col_b} (n = {n} pairs): "
            f"t({n - 1}) = {res.statistic:.3f}, {fmt_p(res.pvalue)} "
            f"({significance_phrase(res.pvalue)}); mean difference {md:.4g}."
        ),
        apa=f"t({n - 1}) = {res.statistic:.3f}, {fmt_p(res.pvalue)}, d = {d:.3f}",
        statistic={"t": float(res.statistic), "df": float(n - 1), "meanDifference": md, "se": se},
        p_value=float(res.pvalue),
        effect_sizes=[EffectSize("Cohen's d (paired)", float(d), None, None, cohen_d_magnitude(d))],
        assumptions=[
            AssumptionCheck(
                "Normality of the difference scores",
                None if np.isnan(sh_p) else bool(sh_p >= 0.05),
                f"Shapiro-Wilk {fmt_p(sh_p)}" if not np.isnan(sh_p) else "not assessed",
                p_value=None if np.isnan(sh_p) else float(sh_p),
            )
        ],
        tables=[
            ResultTable(
                "Differences",
                ["n_pairs", "mean_diff", "sd_diff", "se", "ci95_low", "ci95_high"],
                [[n, md, sd, se, lo, hi]],
            )
        ],
        plot_spec={
            "kind": "histogram",
            "data": {"x": diff.tolist()},
            "encoding": {"x": {"field": "x", "title": f"{col_a} - {col_b}"}},
            "rule": 0,
        },
    )
