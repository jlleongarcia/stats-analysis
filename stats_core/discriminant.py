"""Discriminant analysis: classic Fisher/canonical LDA, and a covariate-adjusted
"General Discriminant Analysis" variant (predictors residualized on covariates
before the same eigendecomposition, ANCOVA-style)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import linalg as la
from scipy import stats
from statsmodels.formula.api import ols

from stats_core._util import DataError, fmt_p, significance_phrase
from stats_core.results import EffectSize, ResultTable, TestResult


@dataclass
class _LdaCore:
    classes: list[str]
    eigenvalues: np.ndarray
    coefficients: np.ndarray  # p x s, unstandardized canonical coefficients
    std_coefficients: np.ndarray  # p x s, standardized
    group_means: np.ndarray  # k x p
    scores: np.ndarray  # n x s
    predicted: np.ndarray  # n, predicted class label per row
    wilks_lambda: float
    chi2: float
    df: float
    p_value: float


def _lda_core(X: np.ndarray, y: np.ndarray) -> _LdaCore:
    classes = sorted(set(y.tolist()))
    k = len(classes)
    n, p = X.shape
    if k < 2:
        raise DataError("Need at least 2 groups for a discriminant analysis.")
    s = min(k - 1, p)
    grand = X.mean(axis=0)

    Sw = np.zeros((p, p))
    Sb = np.zeros((p, p))
    group_means = np.zeros((k, p))
    for i, c in enumerate(classes):
        Xc = X[y == c]
        mc = Xc.mean(axis=0)
        group_means[i] = mc
        Sw += (Xc - mc).T @ (Xc - mc)
        Sb += len(Xc) * np.outer(mc - grand, mc - grand)
    Sw_cov = Sw / (n - k)

    eigvals, eigvecs = la.eig(np.linalg.solve(Sw, Sb))
    order = np.argsort(-eigvals.real)
    eigvals = np.clip(eigvals.real[order][:s], 0, None)
    eigvecs = eigvecs.real[:, order][:, :s]

    pooled_sd = np.sqrt(np.diag(Sw_cov))
    std_coef = eigvecs * pooled_sd[:, None]

    wilks = float(np.prod(1.0 / (1.0 + eigvals))) if eigvals.size else 1.0
    df = float(p * (k - 1))
    chi2 = -((n - 1) - (p + k) / 2) * np.log(wilks) if wilks > 0 else float("nan")
    p_value = float(stats.chi2.sf(chi2, df)) if np.isfinite(chi2) and df > 0 else float("nan")

    scores = (X - grand) @ eigvecs
    Sw_inv = np.linalg.pinv(Sw_cov)
    dists = np.stack([np.einsum("ij,jk,ik->i", X - m, Sw_inv, X - m) for m in group_means], axis=1)
    predicted = np.array(classes)[np.argmin(dists, axis=1)]

    return _LdaCore(classes, eigvals, eigvecs, std_coef, group_means, scores, predicted,
                     wilks, float(chi2), df, p_value)


def _confusion_table(actual: np.ndarray, predicted: np.ndarray, classes: list[str]) -> ResultTable:
    rows = []
    for a in classes:
        mask = actual == a
        rows.append([a, *[int(np.sum((predicted == p) & mask)) for p in classes]])
    return ResultTable("Classification results (resubstitution)", ["actual \\ predicted", *classes], rows)


def _build_result(test_id: str, name: str, cols: list[str], group_col: str,
                   core: _LdaCore, y: np.ndarray, notes: list[str]) -> TestResult:
    k, s, n = len(core.classes), core.eigenvalues.size, y.size
    accuracy = float(np.mean(core.predicted == y))

    tables = [
        ResultTable(
            "Eigenvalues / canonical correlations",
            ["function", "eigenvalue", "pct_of_sum", "canonical_r"],
            [[i + 1, float(ev), float(ev / core.eigenvalues.sum() * 100) if core.eigenvalues.sum() else None,
              float(np.sqrt(ev / (1 + ev)))]
             for i, ev in enumerate(core.eigenvalues)],
        ),
        ResultTable(
            "Standardized canonical discriminant function coefficients",
            ["variable", *[f"function{i + 1}" for i in range(s)]],
            [[cols[j], *[float(core.std_coefficients[j, i]) for i in range(s)]] for j in range(len(cols))],
        ),
        ResultTable(
            "Group means (raw variables)",
            ["group", *cols],
            [[core.classes[g], *[float(v) for v in core.group_means[g]]] for g in range(k)],
        ),
        _confusion_table(y, core.predicted, core.classes),
    ]

    plot_specs = []
    if s >= 1:
        plot_specs.append({
            "kind": "scatter",
            "data": {
                "x": core.scores[:, 0].tolist(),
                "y": (core.scores[:, 1].tolist() if s >= 2 else [0.0] * n),
                "group": y.tolist(),
            },
            "encoding": {"x": {"field": "x", "title": "Function 1"}, "y": {"field": "y", "title": "Function 2"}},
        })

    return TestResult(
        test_id=test_id,
        test_name=name,
        summary=(
            f"{group_col} ({k} groups) discriminated by {len(cols)} predictor(s), n = {n}: "
            f"Wilks' lambda = {core.wilks_lambda:.3f}, chi^2({core.df:.0f}) = {core.chi2:.3f}, "
            f"{fmt_p(core.p_value)} ({significance_phrase(core.p_value)}); "
            f"resubstitution accuracy = {accuracy * 100:.1f}%."
        ),
        apa=f"Wilks' lambda = {core.wilks_lambda:.3f}, chi^2({core.df:.0f}, N = {n}) "
        f"= {core.chi2:.3f}, {fmt_p(core.p_value)}",
        statistic={"wilksLambda": core.wilks_lambda, "chi2": core.chi2, "df": core.df,
                   "resubstitutionAccuracy": accuracy},
        p_value=core.p_value,
        effect_sizes=[EffectSize(f"Canonical correlation (function {i + 1})",
                                  float(np.sqrt(ev / (1 + ev))))
                      for i, ev in enumerate(core.eigenvalues)],
        tables=tables,
        plot_specs=plot_specs,
        notes=notes,
    )


def discriminant_analysis(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    group_col = roles["group"]
    cols = roles.get("predictors") or []
    if len(cols) < 1:
        raise DataError("Discriminant analysis needs at least 1 predictor.")
    sub = frame[[group_col, *cols]].dropna().copy()
    for c in cols:
        sub[c] = pd.to_numeric(sub[c], errors="coerce")
    sub = sub.dropna()
    if sub[group_col].nunique() < 2:
        raise DataError("Need at least 2 groups in the grouping variable.")
    X = sub[cols].to_numpy(float)
    y = sub[group_col].astype(str).to_numpy()

    core = _lda_core(X, y)
    return _build_result(
        "discriminant_analysis", "Discriminant analysis (Fisher LDA)", cols, group_col, core, y,
        notes=["Classification uses equal group priors and Mahalanobis distance to each "
               "group mean (pooled within-group covariance)."],
    )


def general_discriminant_analysis(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    group_col = roles["group"]
    cols = roles.get("predictors") or []
    covariates = roles.get("covariates") or []
    if isinstance(covariates, str):
        covariates = [covariates]
    if len(cols) < 1:
        raise DataError("General discriminant analysis needs at least 1 predictor.")
    keep = [group_col, *cols, *covariates]
    sub = frame[keep].dropna().copy()
    for c in [*cols, *covariates]:
        sub[c] = pd.to_numeric(sub[c], errors="coerce")
    sub = sub.dropna()
    if sub[group_col].nunique() < 2:
        raise DataError("Need at least 2 groups in the grouping variable.")

    if covariates:
        cov_frame = sub[covariates].rename(columns={c: f"cov{i}" for i, c in enumerate(covariates)})
        cov_terms = " + ".join(f"cov{i}" for i in range(len(covariates)))
        residual_cols = []
        for p in cols:
            fit_data = cov_frame.assign(target=sub[p].to_numpy(float))
            residual_cols.append(ols(f"target ~ {cov_terms}", data=fit_data).fit().resid.to_numpy())
        X = np.column_stack(residual_cols)
        note = (f"Predictors were residualized on covariate(s) {', '.join(covariates)} "
                "before the discriminant eigendecomposition (ANCOVA-style adjustment).")
    else:
        X = sub[cols].to_numpy(float)
        note = "No covariates supplied - identical to a plain discriminant analysis."

    y = sub[group_col].astype(str).to_numpy()
    core = _lda_core(X, y)
    return _build_result(
        "general_discriminant_analysis", "General discriminant analysis (covariate-adjusted)",
        cols, group_col, core, y,
        notes=[note, "Classification uses equal group priors and Mahalanobis distance to each "
               "group mean (pooled within-group covariance) on the (adjusted) predictors."],
    )
