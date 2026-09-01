"""Dimension-reduction / structure-exploring multivariate methods: PCA, factor
analysis, canonical correlation, correspondence analysis, and classical MDS.

Unlike the hypothesis tests elsewhere in stats_core, most of these describe
structure rather than test a null hypothesis, so ``p_value`` is often ``None``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.spatial.distance import pdist, squareform
from statsmodels.multivariate.cancorr import CanCorr
from statsmodels.multivariate.factor import Factor

from stats_core._util import DataError, fmt_p, significance_phrase
from stats_core.results import ResultTable, TestResult


def _numeric_frame(frame: pd.DataFrame, cols: list[str], min_rows_over_cols: int = 2) -> pd.DataFrame:
    sub = frame[cols].apply(pd.to_numeric, errors="coerce").dropna()
    if len(sub) < len(cols) + min_rows_over_cols:
        raise DataError("Not enough complete rows for the number of selected variables.")
    return sub


def pca(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    cols = roles.get("columns") or []
    if len(cols) < 2:
        raise DataError("PCA needs at least 2 numeric columns.")
    sub = _numeric_frame(frame, cols, min_rows_over_cols=1)
    standardize = bool(params.get("standardize", True))
    X = sub.to_numpy(float)
    n, p = X.shape
    Xc = X - X.mean(axis=0)
    if standardize:
        sd = X.std(axis=0, ddof=1)
        sd[sd == 0] = 1.0
        Xc = Xc / sd

    max_k = min(n - 1, p)
    requested = params.get("n_components")
    n_components = max(1, min(int(requested) if requested else max_k, max_k))

    U, S, Vt = np.linalg.svd(Xc, full_matrices=False)
    eigenvalues = (S**2) / (n - 1)
    total_var = float(eigenvalues.sum())
    explained = eigenvalues / total_var if total_var > 0 else eigenvalues
    cumulative = np.cumsum(explained)

    loadings = Vt.T[:, :n_components] * np.sqrt(np.maximum(eigenvalues[:n_components], 0))
    scores = U[:, :n_components] * S[:n_components]

    comp_labels = [f"PC{i + 1}" for i in range(max_k)]
    var_table = ResultTable(
        "Explained variance",
        ["component", "eigenvalue", "pct_variance", "cumulative_pct"],
        [
            [comp_labels[i], float(eigenvalues[i]), float(explained[i] * 100), float(cumulative[i] * 100)]
            for i in range(max_k)
        ],
    )
    load_table = ResultTable(
        "Loadings",
        ["variable", *comp_labels[:n_components]],
        [[cols[j], *[float(loadings[j, k]) for k in range(n_components)]] for j in range(p)],
    )

    plot_specs = [{
        "kind": "line",
        "data": {"x": comp_labels, "y": (explained * 100).tolist()},
        "encoding": {"x": {"title": "component"}, "y": {"title": "% variance explained"}},
    }]
    if n_components >= 2:
        plot_specs.append({
            "kind": "scatter",
            "data": {"x": scores[:, 0].tolist(), "y": scores[:, 1].tolist()},
            "encoding": {"x": {"field": "x", "title": "PC1"}, "y": {"field": "y", "title": "PC2"}},
        })

    return TestResult(
        test_id="pca",
        test_name="Principal component analysis",
        summary=(
            f"{n_components} of {max_k} possible components retained, explaining "
            f"{cumulative[n_components - 1] * 100:.1f}% of the variance in {p} variables "
            f"(n = {n})."
        ),
        apa=f"PC1 explains {explained[0] * 100:.1f}% of variance (eigenvalue = {eigenvalues[0]:.3f}).",
        statistic={"nComponentsRetained": float(n_components),
                   "cumulativeVariancePct": float(cumulative[n_components - 1] * 100)},
        p_value=None,
        tables=[var_table, load_table],
        plot_specs=plot_specs,
        notes=["Loadings are eigenvectors scaled by the square root of their eigenvalue "
               "(correlations between variable and component when standardized)."],
    )


def factor_analysis(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    cols = roles.get("columns") or []
    if len(cols) < 3:
        raise DataError("Factor analysis needs at least 3 numeric columns.")
    sub = _numeric_frame(frame, cols, min_rows_over_cols=2)
    method = params.get("method", "pa")
    if method not in {"pa", "ml"}:
        raise DataError("method must be 'pa' (principal axis) or 'ml' (maximum likelihood).")
    n_factors = int(params.get("n_factors", 2))
    n_factors = max(1, min(n_factors, len(cols) - 1))
    rotation = params.get("rotation", "varimax")

    fa = Factor(sub.to_numpy(float), n_factor=n_factors, method=method).fit()
    if rotation and rotation != "none":
        fa.rotate(rotation)

    loadings = np.asarray(fa.loadings)
    eigenvals = np.asarray(fa.eigenvals)
    communality = np.asarray(fa.communality)
    uniqueness = np.asarray(fa.uniqueness)
    factor_labels = [f"Factor{i + 1}" for i in range(n_factors)]
    positive = eigenvals[eigenvals > 0]
    total = float(positive.sum()) if positive.size else 1.0

    return TestResult(
        test_id="factor_analysis",
        test_name=f"Factor analysis ({'principal axis' if method == 'pa' else 'maximum likelihood'})",
        summary=(
            f"{n_factors} factor(s) extracted from {len(cols)} variables "
            f"(n = {len(sub)}), rotation = {rotation}."
        ),
        p_value=None,
        statistic={"nFactors": float(n_factors)},
        tables=[
            ResultTable(
                "Eigenvalues",
                ["factor", "eigenvalue", "pct_of_positive_sum"],
                [[f"F{i + 1}", float(v), float(v / total * 100) if total else None]
                 for i, v in enumerate(eigenvals)],
            ),
            ResultTable(
                "Loadings",
                ["variable", *factor_labels],
                [[cols[j], *[float(loadings[j, k]) for k in range(n_factors)]] for j in range(len(cols))],
            ),
            ResultTable(
                "Communalities",
                ["variable", "communality", "uniqueness"],
                [[cols[j], float(communality[j]), float(uniqueness[j])] for j in range(len(cols))],
            ),
        ],
        plot_specs=[{
            "kind": "line",
            "data": {"x": [f"F{i + 1}" for i in range(len(eigenvals))], "y": eigenvals.tolist()},
            "encoding": {"x": {"title": "factor"}, "y": {"title": "eigenvalue"}},
        }],
        notes=["Eigenvalues are of the reduced correlation matrix (communalities on the diagonal), "
               "so they need not sum to the number of variables."],
    )


def canonical_correlation(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    set_a = roles.get("set_a") or []
    set_b = roles.get("set_b") or []
    if len(set_a) < 2 or len(set_b) < 2:
        raise DataError("Canonical correlation needs at least 2 variables in each set.")
    overlap = sorted(set(set_a) & set(set_b))
    if overlap:
        raise DataError(f"Variable(s) {overlap} cannot appear in both sets.")
    sub = _numeric_frame(frame, [*set_a, *set_b], min_rows_over_cols=2)
    A = sub[set_a].to_numpy(float)
    B = sub[set_b].to_numpy(float)

    cc = CanCorr(A, B)  # endog=A -> y_cancoef; exog=B -> x_cancoef
    test = cc.corr_test()
    n_pairs = len(cc.cancorr)

    Ac, Bc = A - A.mean(axis=0), B - B.mean(axis=0)
    score_a1 = Ac @ cc.y_cancoef[:, 0]
    score_b1 = Bc @ cc.x_cancoef[:, 0]

    p0 = float(test.stats["Pr > F"].iloc[0])
    wilks0 = float(test.stats["Wilks' lambda"].iloc[0])
    df1_0 = float(test.stats["Num DF"].iloc[0])
    df2_0 = float(test.stats["Den DF"].iloc[0])
    f0 = float(test.stats["F Value"].iloc[0])
    return TestResult(
        test_id="canonical_correlation",
        test_name="Canonical correlation analysis",
        summary=(
            f"{len(set_a)} vs {len(set_b)} variables (n = {len(sub)}): {n_pairs} canonical pair(s); "
            f"first canonical correlation = {cc.cancorr[0]:.3f}, {fmt_p(p0)} "
            f"({significance_phrase(p0)})."
        ),
        apa=f"Wilks' lambda = {wilks0:.3f}, F({df1_0:.0f}, {df2_0:.0f}) = {f0:.3f}, {fmt_p(p0)}",
        statistic={"firstCanonicalCorrelation": float(cc.cancorr[0]), "nPairs": float(n_pairs)},
        p_value=p0,
        tables=[
            ResultTable(
                "Canonical correlations",
                ["pair", "r", "wilks_lambda", "df1", "df2", "F", "p"],
                [
                    [i + 1, float(test.stats["Canonical Correlation"].iloc[i]),
                     float(test.stats["Wilks' lambda"].iloc[i]),
                     float(test.stats["Num DF"].iloc[i]), float(test.stats["Den DF"].iloc[i]),
                     float(test.stats["F Value"].iloc[i]), float(test.stats["Pr > F"].iloc[i])]
                    for i in range(n_pairs)
                ],
            ),
            ResultTable(
                "Set A coefficients (standardized on centered data)",
                ["variable", *[f"pair{i + 1}" for i in range(n_pairs)]],
                [[set_a[j], *[float(cc.y_cancoef[j, k]) for k in range(n_pairs)]] for j in range(len(set_a))],
            ),
            ResultTable(
                "Set B coefficients (standardized on centered data)",
                ["variable", *[f"pair{i + 1}" for i in range(n_pairs)]],
                [[set_b[j], *[float(cc.x_cancoef[j, k]) for k in range(n_pairs)]] for j in range(len(set_b))],
            ),
        ],
        plot_specs=[{
            "kind": "scatter",
            "data": {"x": score_a1.tolist(), "y": score_b1.tolist()},
            "encoding": {"x": {"field": "x", "title": "Set A canonical variate 1"},
                         "y": {"field": "y", "title": "Set B canonical variate 1"}},
            "regression": True,
        }],
    )


def correspondence_analysis(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    row_col, col_col = roles["rows"], roles["columns"]
    for c in (row_col, col_col):
        if c not in frame.columns:
            raise DataError(f"Column {c!r} is not in the dataset.")
    tab = pd.crosstab(frame[row_col], frame[col_col])
    if tab.shape[0] < 2 or tab.shape[1] < 2:
        raise DataError("Both variables need at least 2 categories.")

    N = tab.to_numpy(float)
    n = N.sum()
    P = N / n
    row_mass = P.sum(axis=1)
    col_mass = P.sum(axis=0)
    expected = np.outer(row_mass, col_mass)
    S = (P - expected) / np.sqrt(expected)
    U, D, Vt = np.linalg.svd(S, full_matrices=False)
    k = min(2, D.size)

    row_coords = (U[:, :k] * D[:k]) / np.sqrt(row_mass)[:, None]
    col_coords = (Vt.T[:, :k] * D[:k]) / np.sqrt(col_mass)[:, None]

    inertia = D**2
    total_inertia = float(inertia.sum())

    rows_lab = [str(i) for i in tab.index]
    cols_lab = [str(c) for c in tab.columns]
    scatter_data = {
        "x": [*row_coords[:, 0].tolist(), *col_coords[:, 0].tolist()],
        "y": ([*row_coords[:, 1].tolist(), *col_coords[:, 1].tolist()] if k >= 2
              else [0.0] * (len(rows_lab) + len(cols_lab))),
        "group": [f"{row_col}: {r}" for r in rows_lab] + [f"{col_col}: {c}" for c in cols_lab],
    }

    return TestResult(
        test_id="correspondence_analysis",
        test_name="Correspondence analysis",
        summary=(
            f"{row_col} ({tab.shape[0]}) x {col_col} ({tab.shape[1]}): total inertia = "
            f"{total_inertia:.4f}, first {k} dimension(s) shown."
        ),
        p_value=None,
        statistic={"totalInertia": total_inertia},
        tables=[
            ResultTable(
                "Dimension inertia",
                ["dimension", "inertia", "pct_of_total"],
                [[i + 1, float(v), float(v / total_inertia * 100) if total_inertia else None]
                 for i, v in enumerate(inertia)],
            ),
            ResultTable(
                "Row coordinates",
                ["category", *[f"dim{i + 1}" for i in range(k)]],
                [[rows_lab[i], *[float(row_coords[i, j]) for j in range(k)]] for i in range(len(rows_lab))],
            ),
            ResultTable(
                "Column coordinates",
                ["category", *[f"dim{i + 1}" for i in range(k)]],
                [[cols_lab[i], *[float(col_coords[i, j]) for j in range(k)]] for i in range(len(cols_lab))],
            ),
        ],
        plot_specs=[{
            "kind": "scatter",
            "data": scatter_data,
            "encoding": {"x": {"field": "x", "title": "Dimension 1"}, "y": {"field": "y", "title": "Dimension 2"}},
        }],
        notes=["Total inertia equals Pearson chi^2 / N for this table."],
    )


def mds(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    cols = roles.get("columns") or []
    if len(cols) < 2:
        raise DataError("MDS needs at least 2 numeric columns.")
    sub = _numeric_frame(frame, cols, min_rows_over_cols=1)
    standardize = bool(params.get("standardize", True))
    X = sub.to_numpy(float)
    if standardize:
        sd = X.std(axis=0, ddof=1)
        sd[sd == 0] = 1.0
        X = (X - X.mean(axis=0)) / sd

    n = X.shape[0]
    n_components = max(2, min(int(params.get("n_components") or 2), n - 1))
    D2 = squareform(pdist(X, metric="euclidean")) ** 2
    J = np.eye(n) - np.ones((n, n)) / n
    B = -0.5 * J @ D2 @ J
    B = (B + B.T) / 2  # guard against asymmetric float error

    eigvals, eigvecs = np.linalg.eigh(B)
    order = np.argsort(eigvals)[::-1]
    eigvals, eigvecs = eigvals[order], eigvecs[:, order]
    positive = np.maximum(eigvals[:n_components], 0)
    coords = eigvecs[:, :n_components] * np.sqrt(positive)

    total_positive = float(np.sum(eigvals[eigvals > 0])) or 1.0
    group_col = roles.get("group")
    data = {"x": coords[:, 0].tolist(), "y": coords[:, 1].tolist()}
    if group_col:
        data["group"] = frame.loc[sub.index, group_col].astype(str).tolist()

    return TestResult(
        test_id="mds",
        test_name="Multidimensional scaling (classical/metric)",
        summary=(
            f"{n} cases in {len(cols)} variables reduced to {n_components} dimensions; "
            f"first 2 dimensions capture {float(np.sum(positive[:2]) / total_positive * 100):.1f}% "
            "of scaled variance."
        ),
        p_value=None,
        statistic={"nComponents": float(n_components)},
        tables=[ResultTable(
            "Eigenvalues",
            ["dimension", "eigenvalue", "pct_of_positive_sum"],
            [[i + 1, float(v), float(v / total_positive * 100)] for i, v in enumerate(eigvals[:n_components])],
        )],
        plot_specs=[{
            "kind": "scatter",
            "data": data,
            "encoding": {"x": {"field": "x", "title": "Dimension 1"}, "y": {"field": "y", "title": "Dimension 2"}},
        }],
        notes=["Classical (Torgerson) MDS via double-centered squared Euclidean distances, "
               "not the iterative stress-minimizing (SMACOF) variant."],
    )
