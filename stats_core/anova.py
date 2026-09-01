"""Analysis of variance: one-way, Welch, two-way, repeated measures, ANCOVA,
plus Tukey HSD and Games-Howell post-hoc comparisons."""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.formula.api import ols
from statsmodels.stats.anova import AnovaRM, anova_lm
from statsmodels.stats.multicomp import pairwise_tukeyhsd

from stats_core._util import (
    DataError,
    eta_squared_magnitude,
    fmt_p,
    groups_from,
    significance_phrase,
)
from stats_core.results import AssumptionCheck, EffectSize, ResultTable, TestResult


def one_way_anova(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    value_col, group_col = roles["values"], roles["group"]
    groups = groups_from(frame, value_col, group_col)
    labels, arrays = list(groups.keys()), list(groups.values())
    f, p = stats.f_oneway(*arrays)

    grand = np.concatenate(arrays)
    N, k = grand.size, len(arrays)
    ss_between = sum(a.size * (a.mean() - grand.mean()) ** 2 for a in arrays)
    ss_within = sum(((a - a.mean()) ** 2).sum() for a in arrays)
    ss_total = ss_between + ss_within
    df_b, df_w = k - 1, N - k
    eta2 = ss_between / ss_total if ss_total > 0 else float("nan")
    omega2 = (ss_between - df_b * (ss_within / df_w)) / (ss_total + ss_within / df_w)
    lev_p = stats.levene(*arrays, center="median").pvalue

    return TestResult(
        test_id="one_way_anova",
        test_name="One-way ANOVA",
        summary=(
            f"Effect of {group_col} ({k} groups) on {value_col}: "
            f"F({df_b}, {df_w}) = {f:.3f}, {fmt_p(p)} "
            f"({significance_phrase(p)})."
        ),
        apa=f"F({df_b}, {df_w}) = {f:.3f}, {fmt_p(p)}, eta^2 = {eta2:.3f}",
        statistic={"F": float(f), "dfBetween": float(df_b), "dfWithin": float(df_w)},
        p_value=float(p),
        effect_sizes=[
            EffectSize("eta^2", float(eta2), None, None, eta_squared_magnitude(eta2)),
            EffectSize("omega^2", float(omega2)),
        ],
        assumptions=[
            AssumptionCheck(
                "Homogeneity of variance (Levene)",
                bool(lev_p >= 0.05),
                f"Levene {fmt_p(lev_p)}. If violated, prefer Welch's ANOVA.",
                p_value=float(lev_p),
            )
        ],
        tables=[
            ResultTable(
                "ANOVA table",
                ["source", "SS", "df", "MS", "F", "p"],
                [
                    [group_col, ss_between, df_b, ss_between / df_b, float(f), float(p)],
                    ["Residual", ss_within, df_w, ss_within / df_w, None, None],
                    ["Total", ss_total, N - 1, None, None, None],
                ],
            ),
            ResultTable(
                "Group means",
                ["group", "n", "mean", "sd"],
                [[lab, a.size, float(a.mean()), float(a.std(ddof=1))] for lab, a in zip(labels, arrays)],
            ),
        ],
        plot_specs=[{
            "kind": "box",
            "data": {
                "value": grand.tolist(),
                "group": np.repeat(labels, [a.size for a in arrays]).tolist(),
            },
            "encoding": {"x": {"field": "group"}, "y": {"field": "value", "title": value_col}},
        }],
    )


def welch_anova(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    value_col, group_col = roles["values"], roles["group"]
    groups = groups_from(frame, value_col, group_col)
    labels, arrays = list(groups.keys()), list(groups.values())
    k = len(arrays)
    n = np.array([a.size for a in arrays], float)
    m = np.array([a.mean() for a in arrays])
    v = np.array([a.var(ddof=1) for a in arrays])
    w = n / v
    m_bar = np.sum(w * m) / np.sum(w)
    A = np.sum(w * (m - m_bar) ** 2) / (k - 1)
    B = (2 * (k - 2) / (k**2 - 1)) * np.sum((1 - w / np.sum(w)) ** 2 / (n - 1))
    F = A / (1 + B)
    df1 = k - 1
    df2 = 1 / (3 / (k**2 - 1) * np.sum((1 - w / np.sum(w)) ** 2 / (n - 1)))
    p = float(stats.f.sf(F, df1, df2))
    return TestResult(
        test_id="welch_anova",
        test_name="Welch's ANOVA (unequal variances)",
        summary=(
            f"Effect of {group_col} on {value_col} (Welch): "
            f"F({df1}, {df2:.1f}) = {F:.3f}, {fmt_p(p)} ({significance_phrase(p)})."
        ),
        apa=f"F({df1}, {df2:.2f}) = {F:.3f}, {fmt_p(p)}",
        statistic={"F": float(F), "dfBetween": float(df1), "dfWithin": float(df2)},
        p_value=p,
        assumptions=[
            AssumptionCheck(
                "Homogeneity of variance",
                None,
                "Not required - Welch's ANOVA is robust to unequal variances.",
            )
        ],
        tables=[
            ResultTable(
                "Group means",
                ["group", "n", "mean", "sd"],
                [[lab, int(nn), float(mm), float(np.sqrt(vv))] for lab, nn, mm, vv in zip(labels, n, m, v)],
            )
        ],
        plot_specs=[{
            "kind": "box",
            "data": {
                "value": np.concatenate(arrays).tolist(),
                "group": np.repeat(labels, [a.size for a in arrays]).tolist(),
            },
            "encoding": {"x": {"field": "group"}, "y": {"field": "value", "title": value_col}},
        }],
    )


def two_way_anova(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    dv, fa, fb = roles["values"], roles["factor_a"], roles["factor_b"]
    sub = frame[[dv, fa, fb]].dropna().copy()
    sub[dv] = pd.to_numeric(sub[dv], errors="coerce")
    sub = sub.dropna()
    if len(sub) < 4:
        raise DataError("Not enough complete rows for a two-way ANOVA.")
    d = sub.rename(columns={dv: "y", fa: "A", fb: "B"})
    d["A"] = d["A"].astype("category")
    d["B"] = d["B"].astype("category")
    typ = int(params.get("anova_type", 2))
    model = ols("y ~ C(A) + C(B) + C(A):C(B)", data=d).fit()
    table = anova_lm(model, typ=typ)
    ss_total = table["sum_sq"].sum()
    rows, effects = [], []
    label_map = {"C(A)": fa, "C(B)": fb, "C(A):C(B)": f"{fa} x {fb}", "Residual": "Residual"}
    for idx, r in table.iterrows():
        name = label_map.get(idx, idx)
        F = r.get("F", np.nan)
        p = r.get("PR(>F)", np.nan)
        rows.append([name, float(r["sum_sq"]), float(r["df"]),
                     float(r["sum_sq"] / r["df"]),
                     None if pd.isna(F) else float(F),
                     None if pd.isna(p) else float(p)])
        if idx != "Residual":
            eta2 = float(r["sum_sq"] / ss_total)
            partial = float(r["sum_sq"] / (r["sum_sq"] + table.loc["Residual", "sum_sq"]))
            effects.append(EffectSize(f"partial eta^2 ({name})", partial, None, None,
                                      eta_squared_magnitude(partial)))
    main = table.drop(index="Residual")
    key = main["PR(>F)"].idxmin()
    return TestResult(
        test_id="two_way_anova",
        test_name=f"Two-way ANOVA (Type {typ})",
        summary=(
            f"{dv} by {fa} and {fb}. Smallest p is for "
            f"{label_map.get(key, key)}: F = {main.loc[key, 'F']:.3f}, "
            f"{fmt_p(main.loc[key, 'PR(>F)'])}."
        ),
        apa="; ".join(
            f"{label_map.get(i, i)}: F({r['df']:.0f}, {table.loc['Residual', 'df']:.0f}) "
            f"= {r['F']:.3f}, {fmt_p(r['PR(>F)'])}"
            for i, r in main.iterrows()
        ),
        statistic={"rSquared": float(model.rsquared)},
        p_value=float(main.loc[key, "PR(>F)"]),
        effect_sizes=effects,
        tables=[ResultTable("ANOVA table", ["source", "SS", "df", "MS", "F", "p"], rows)],
        plot_specs=[{
            "kind": "interaction",
            "data": {
                "y": d["y"].tolist(),
                "a": d["A"].astype(str).tolist(),
                "b": d["B"].astype(str).tolist(),
            },
            "encoding": {"x": {"field": "a"}, "detail": {"field": "b"}, "y": {"field": "y", "title": dv}},
        }],
    )


def rm_anova(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    cols = roles.get("columns") or []
    if len(cols) < 2:
        raise DataError("Repeated-measures ANOVA needs at least 2 condition columns.")
    wide = frame[cols].apply(pd.to_numeric, errors="coerce").dropna().reset_index(drop=True)
    if len(wide) < 2:
        raise DataError("Fewer than 2 complete cases across the selected columns.")
    wide["subject"] = range(len(wide))
    long = wide.melt(id_vars="subject", value_vars=cols, var_name="condition", value_name="y")
    aov = AnovaRM(long, depvar="y", subject="subject", within=["condition"]).fit()
    tbl = aov.anova_table
    F = float(tbl["F Value"].iloc[0])
    p = float(tbl["Pr > F"].iloc[0])
    df1 = float(tbl["Num DF"].iloc[0])
    df2 = float(tbl["Den DF"].iloc[0])
    # partial eta^2 from F and dfs
    partial_eta2 = (F * df1) / (F * df1 + df2)
    return TestResult(
        test_id="rm_anova",
        test_name="Repeated-measures ANOVA (one within factor)",
        summary=(
            f"Effect of condition ({len(cols)} levels, n = {len(wide)}): "
            f"F({df1:.0f}, {df2:.0f}) = {F:.3f}, {fmt_p(p)} ({significance_phrase(p)})."
        ),
        apa=f"F({df1:.0f}, {df2:.0f}) = {F:.3f}, {fmt_p(p)}, partial eta^2 = {partial_eta2:.3f}",
        statistic={"F": F, "dfNum": df1, "dfDen": df2},
        p_value=p,
        effect_sizes=[EffectSize("partial eta^2", float(partial_eta2), None, None,
                                 eta_squared_magnitude(partial_eta2))],
        assumptions=[
            AssumptionCheck(
                "Sphericity",
                None,
                "Not assessed here; with >2 conditions consider a "
                "Greenhouse-Geisser correction.",
            )
        ],
        tables=[
            ResultTable(
                "Condition means",
                ["condition", "mean", "sd"],
                [[c, float(wide[c].mean()), float(wide[c].std(ddof=1))] for c in cols],
            )
        ],
        plot_specs=[{
            "kind": "box",
            "data": {
                "value": wide[cols].to_numpy(float).T.reshape(-1).tolist(),
                "group": np.repeat(cols, len(wide)).tolist(),
            },
            "encoding": {"x": {"field": "group"}, "y": {"field": "value"}},
        }],
    )


def ancova(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    dv, group_col = roles["values"], roles["group"]
    covariates = roles.get("covariates") or []
    if isinstance(covariates, str):
        covariates = [covariates]
    if not covariates:
        raise DataError("ANCOVA needs at least one covariate.")
    keep = [dv, group_col, *covariates]
    sub = frame[keep].dropna().copy()
    for c in [dv, *covariates]:
        sub[c] = pd.to_numeric(sub[c], errors="coerce")
    sub = sub.dropna()
    d = sub.rename(columns={dv: "y", group_col: "grp"})
    d["grp"] = d["grp"].astype("category")
    cov_terms = " + ".join(f"Q('{c}')" for c in covariates)
    model = ols(f"y ~ C(grp) + {cov_terms}", data=d).fit()
    table = anova_lm(model, typ=2)
    F = float(table.loc["C(grp)", "F"])
    p = float(table.loc["C(grp)", "PR(>F)"])
    ss_grp = float(table.loc["C(grp)", "sum_sq"])
    ss_res = float(table.loc["Residual", "sum_sq"])
    partial_eta2 = ss_grp / (ss_grp + ss_res)
    rows = [
        [idx if idx == "Residual" else (group_col if idx == "C(grp)" else idx),
         float(r["sum_sq"]), float(r["df"]),
         None if pd.isna(r.get("F", np.nan)) else float(r["F"]),
         None if pd.isna(r.get("PR(>F)", np.nan)) else float(r["PR(>F)"])]
        for idx, r in table.iterrows()
    ]
    return TestResult(
        test_id="ancova",
        test_name="ANCOVA (one factor, covariate-adjusted)",
        summary=(
            f"Adjusted effect of {group_col} on {dv}, controlling for "
            f"{', '.join(covariates)}: F({table.loc['C(grp)', 'df']:.0f}, "
            f"{table.loc['Residual', 'df']:.0f}) = {F:.3f}, {fmt_p(p)} "
            f"({significance_phrase(p)})."
        ),
        apa=f"F({table.loc['C(grp)', 'df']:.0f}, {table.loc['Residual', 'df']:.0f}) "
        f"= {F:.3f}, {fmt_p(p)}, partial eta^2 = {partial_eta2:.3f}",
        statistic={"F": F, "rSquared": float(model.rsquared)},
        p_value=p,
        effect_sizes=[EffectSize("partial eta^2 (group)", float(partial_eta2), None, None,
                                 eta_squared_magnitude(partial_eta2))],
        tables=[ResultTable("ANCOVA table (Type II)", ["source", "SS", "df", "F", "p"], rows)],
    )


def _tukey(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    value_col, group_col = roles["values"], roles["group"]
    sub = pd.DataFrame(
        {"y": pd.to_numeric(frame[value_col], errors="coerce"), "g": frame[group_col]}
    ).dropna()
    if sub["g"].nunique() < 2:
        raise DataError("Need at least 2 groups for post-hoc comparisons.")
    alpha = float(params.get("alpha", 0.05))
    res = pairwise_tukeyhsd(sub["y"].to_numpy(float), sub["g"].astype(str).to_numpy(), alpha=alpha)
    rows = []
    for rec in res.summary().data[1:]:
        g1, g2, meandiff, p_adj, lo, hi, reject = rec
        rows.append([str(g1), str(g2), float(meandiff), float(lo), float(hi),
                     float(p_adj), bool(reject)])
    sig = [r for r in rows if r[6]]
    return TestResult(
        test_id="posthoc_tukey",
        test_name="Tukey HSD post-hoc comparisons",
        summary=(
            f"{len(rows)} pairwise comparisons at alpha = {alpha:g}; "
            f"{len(sig)} significant after HSD adjustment."
        ),
        p_value=None,
        tables=[
            ResultTable(
                "Pairwise (Tukey HSD)",
                ["group1", "group2", "mean_diff", "ci_low", "ci_high", "p_adj", "significant"],
                rows,
            )
        ],
    )


def _games_howell(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    value_col, group_col = roles["values"], roles["group"]
    groups = groups_from(frame, value_col, group_col)
    labels = list(groups)
    alpha = float(params.get("alpha", 0.05))
    rows = []
    for a, b in itertools.combinations(labels, 2):
        xa, xb = groups[a], groups[b]
        na, nb = xa.size, xb.size
        va, vb = xa.var(ddof=1), xb.var(ddof=1)
        diff = xa.mean() - xb.mean()
        se = np.sqrt(va / na + vb / nb)
        t = diff / se
        df = (va / na + vb / nb) ** 2 / (
            (va / na) ** 2 / (na - 1) + (vb / nb) ** 2 / (nb - 1)
        )
        # studentized range -> p
        p = stats.studentized_range.sf(abs(t) * np.sqrt(2), len(labels), df)
        q_crit = stats.studentized_range.ppf(1 - alpha, len(labels), df)
        margin = q_crit / np.sqrt(2) * se
        rows.append([a, b, float(diff), float(diff - margin), float(diff + margin),
                     float(p), bool(p < alpha)])
    sig = sum(r[6] for r in rows)
    return TestResult(
        test_id="posthoc_games_howell",
        test_name="Games-Howell post-hoc comparisons",
        summary=(
            f"{len(rows)} pairwise comparisons (unequal variances) at "
            f"alpha = {alpha:g}; {sig} significant."
        ),
        p_value=None,
        tables=[
            ResultTable(
                "Pairwise (Games-Howell)",
                ["group1", "group2", "mean_diff", "ci_low", "ci_high", "p_adj", "significant"],
                rows,
            )
        ],
    )


# public aliases
posthoc_tukey = _tukey
posthoc_games_howell = _games_howell
