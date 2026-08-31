"""Rank-based alternatives to the t-tests and one-way ANOVA."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from stats_core._util import (
    DataError,
    clean_pair,
    fmt_p,
    groups_from,
    r_magnitude,
    significance_phrase,
)
from stats_core.results import AssumptionCheck, EffectSize, ResultTable, TestResult


def mann_whitney(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    value_col, group_col = roles["values"], roles["group"]
    groups = groups_from(frame, value_col, group_col, min_per_group=1)
    if len(groups) != 2:
        raise DataError(f"Mann-Whitney needs exactly 2 groups; got {len(groups)}.")
    (g1, a), (g2, b) = groups.items()
    alt = params.get("alternative", "two-sided")
    res = stats.mannwhitneyu(a, b, alternative=alt)
    n1, n2 = a.size, b.size
    # rank-biserial correlation
    rbc = 1 - (2 * res.statistic) / (n1 * n2)
    # normal approximation z for effect size r
    mu = n1 * n2 / 2
    sigma = np.sqrt(n1 * n2 * (n1 + n2 + 1) / 12)
    z = (res.statistic - mu) / sigma if sigma > 0 else float("nan")
    r = abs(z) / np.sqrt(n1 + n2) if np.isfinite(z) else float("nan")
    return TestResult(
        test_id="mann_whitney",
        test_name="Mann-Whitney U test",
        summary=(
            f"{g1} (Mdn = {np.median(a):.4g}, n = {n1}) vs "
            f"{g2} (Mdn = {np.median(b):.4g}, n = {n2}): "
            f"U = {res.statistic:.1f}, {fmt_p(res.pvalue)} "
            f"({significance_phrase(res.pvalue)})."
        ),
        apa=f"U = {res.statistic:.1f}, {fmt_p(res.pvalue)}, r = {r:.3f}",
        statistic={"U": float(res.statistic), "z": float(z)},
        p_value=float(res.pvalue),
        effect_sizes=[
            EffectSize("Rank-biserial r", float(rbc), None, None, r_magnitude(rbc)),
            EffectSize("r (Z/sqrt(N))", float(r), None, None, r_magnitude(r)),
        ],
        assumptions=[
            AssumptionCheck(
                "Independent observations",
                None,
                "Assumed from the study design; not testable from the data.",
            )
        ],
        tables=[
            ResultTable(
                "Group summary",
                ["group", "n", "median", "mean_rank"],
                [
                    [g1, n1, float(np.median(a)), float(stats.rankdata(np.r_[a, b])[:n1].mean())],
                    [g2, n2, float(np.median(b)), float(stats.rankdata(np.r_[a, b])[n1:].mean())],
                ],
            )
        ],
        plot_spec={
            "kind": "box",
            "data": {"value": [*a.tolist(), *b.tolist()], "group": [g1] * n1 + [g2] * n2},
            "encoding": {"x": {"field": "group"}, "y": {"field": "value", "title": value_col}},
        },
    )


def wilcoxon_signed_rank(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    col_a, col_b = roles["first"], roles["second"]
    a, b = clean_pair(frame, col_a, col_b)
    diff = a - b
    nonzero = diff[diff != 0]
    if nonzero.size < 1:
        raise DataError("All paired differences are zero; Wilcoxon is undefined.")
    alt = params.get("alternative", "two-sided")
    res = stats.wilcoxon(a, b, alternative=alt, zero_method="wilcox")
    n = nonzero.size
    mu = n * (n + 1) / 4
    sigma = np.sqrt(n * (n + 1) * (2 * n + 1) / 24)
    z = (res.statistic - mu) / sigma if sigma > 0 else float("nan")
    r = abs(z) / np.sqrt(n) if np.isfinite(z) else float("nan")
    return TestResult(
        test_id="wilcoxon",
        test_name="Wilcoxon signed-rank test",
        summary=(
            f"{col_a} vs {col_b} (n = {n} non-tied pairs): "
            f"W = {res.statistic:.1f}, {fmt_p(res.pvalue)} "
            f"({significance_phrase(res.pvalue)}); median difference "
            f"{np.median(diff):.4g}."
        ),
        apa=f"W = {res.statistic:.1f}, {fmt_p(res.pvalue)}, r = {r:.3f}",
        statistic={"W": float(res.statistic), "z": float(z)},
        p_value=float(res.pvalue),
        effect_sizes=[EffectSize("r (Z/sqrt(N))", float(r), None, None, r_magnitude(r))],
        assumptions=[
            AssumptionCheck(
                "Symmetric distribution of differences",
                None,
                f"Skew of differences = {stats.skew(diff):.3f} (inspect the histogram).",
                statistic=float(stats.skew(diff)),
            )
        ],
        plot_spec={
            "kind": "histogram",
            "data": {"x": diff.tolist()},
            "encoding": {"x": {"field": "x", "title": f"{col_a} - {col_b}"}},
            "rule": 0,
        },
    )


def kruskal_wallis(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    value_col, group_col = roles["values"], roles["group"]
    groups = groups_from(frame, value_col, group_col, min_per_group=1)
    labels = list(groups.keys())
    arrays = list(groups.values())
    res = stats.kruskal(*arrays)
    N = sum(a.size for a in arrays)
    k = len(arrays)
    eta2_h = (res.statistic - k + 1) / (N - k) if N > k else float("nan")
    rows = [[lab, a.size, float(np.median(a))] for lab, a in zip(labels, arrays)]
    result = TestResult(
        test_id="kruskal_wallis",
        test_name="Kruskal-Wallis H test",
        summary=(
            f"{group_col} ({k} groups, N = {N}): "
            f"H({k - 1}) = {res.statistic:.3f}, {fmt_p(res.pvalue)} "
            f"({significance_phrase(res.pvalue)})."
        ),
        apa=f"H({k - 1}) = {res.statistic:.3f}, {fmt_p(res.pvalue)}",
        statistic={"H": float(res.statistic), "df": float(k - 1)},
        p_value=float(res.pvalue),
        effect_sizes=[EffectSize("epsilon^2", float(eta2_h))],
        tables=[ResultTable("Group medians", ["group", "n", "median"], rows)],
        plot_spec={
            "kind": "box",
            "data": {
                "value": np.concatenate(arrays).tolist(),
                "group": np.repeat(labels, [a.size for a in arrays]).tolist(),
            },
            "encoding": {"x": {"field": "group"}, "y": {"field": "value", "title": value_col}},
        },
    )
    if res.pvalue < float(params.get("alpha", 0.05)):
        result.add_note(
            "Significant omnibus result - follow up with pairwise Mann-Whitney "
            "tests and a multiple-comparison correction (e.g. Holm)."
        )
    return result


def friedman(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    cols = roles.get("columns") or []
    if len(cols) < 3:
        raise DataError("Friedman needs at least 3 repeated-measure columns.")
    sub = frame[cols].apply(pd.to_numeric, errors="coerce").dropna()
    if len(sub) < 2:
        raise DataError("Fewer than 2 complete cases across the selected columns.")
    mats = [sub[c].to_numpy(float) for c in cols]
    res = stats.friedmanchisquare(*mats)
    n, k = len(sub), len(cols)
    kendall_w = res.statistic / (n * (k - 1))
    rows = [[c, float(sub[c].median()), float(stats.rankdata(sub.to_numpy(), axis=1).mean(axis=0)[i])]
            for i, c in enumerate(cols)]
    return TestResult(
        test_id="friedman",
        test_name="Friedman test",
        summary=(
            f"{k} repeated conditions (n = {n}): "
            f"chi^2({k - 1}) = {res.statistic:.3f}, {fmt_p(res.pvalue)} "
            f"({significance_phrase(res.pvalue)})."
        ),
        apa=f"chi^2({k - 1}) = {res.statistic:.3f}, {fmt_p(res.pvalue)}, W = {kendall_w:.3f}",
        statistic={"chi2": float(res.statistic), "df": float(k - 1)},
        p_value=float(res.pvalue),
        effect_sizes=[EffectSize("Kendall's W", float(kendall_w))],
        tables=[ResultTable("Conditions", ["column", "median", "mean_rank"], rows)],
        plot_spec={
            "kind": "box",
            "data": {
                "value": sub.to_numpy(float).T.reshape(-1).tolist(),
                "group": np.repeat(cols, n).tolist(),
            },
            "encoding": {"x": {"field": "group"}, "y": {"field": "value"}},
        },
    )
