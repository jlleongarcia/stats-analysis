from __future__ import annotations

import numpy as np
import pytest
from scipy import stats as sstats
from sklearn.decomposition import PCA as SkPCA

from stats_core import run_test


def _num(df):
    return [c for c in df.columns if df[c].dtype.kind in "fi"]


def test_pca_matches_sklearn(ceras):
    cols = _num(ceras)[:5]
    sub = ceras[cols].dropna()
    X = sub.to_numpy(float)
    Xs = (X - X.mean(axis=0)) / X.std(axis=0, ddof=1)
    ref = SkPCA().fit(Xs)

    out = run_test("pca", ceras, {"columns": cols}, {})
    var_rows = next(t for t in out["tables"] if t["title"] == "Explained variance")["rows"]
    got_pct = [r[2] for r in var_rows]
    ref_pct = (ref.explained_variance_ratio_ * 100).tolist()
    for g, r in zip(got_pct, ref_pct):
        assert g == pytest.approx(r, rel=1e-6)


def test_pca_n_components_param(ceras):
    cols = _num(ceras)[:5]
    out = run_test("pca", ceras, {"columns": cols}, {"n_components": 2})
    assert out["statistic"]["nComponentsRetained"] == 2
    load_rows = next(t for t in out["tables"] if t["title"] == "Loadings")["rows"]
    assert len(load_rows[0]) == 1 + 2  # variable + 2 components


def test_factor_analysis_shapes(ceras):
    cols = _num(ceras)[:6]
    out = run_test("factor_analysis", ceras, {"columns": cols}, {"n_factors": 2})
    loadings = next(t for t in out["tables"] if t["title"] == "Loadings")
    assert loadings["columns"] == ["variable", "Factor1", "Factor2"]
    assert len(loadings["rows"]) == len(cols)
    comm = next(t for t in out["tables"] if t["title"] == "Communalities")
    for row in comm["rows"]:
        # communality + uniqueness should be close to 1 for principal-axis extraction
        assert row[1] + row[2] == pytest.approx(1.0, abs=1e-6)


def test_canonical_correlation_matches_statsmodels(ceras):
    cols = _num(ceras)[:6]
    set_a, set_b = cols[:3], cols[3:6]
    from statsmodels.multivariate.cancorr import CanCorr

    sub = ceras[cols].dropna()
    cc = CanCorr(sub[set_a].to_numpy(float), sub[set_b].to_numpy(float))
    ref = cc.corr_test()

    out = run_test("canonical_correlation", ceras, {"set_a": set_a, "set_b": set_b}, {})
    assert out["statistic"]["firstCanonicalCorrelation"] == pytest.approx(cc.cancorr[0], rel=1e-8)
    assert out["pValue"] == pytest.approx(float(ref.stats["Pr > F"].iloc[0]), rel=1e-6)


def test_canonical_correlation_rejects_overlapping_sets(ceras):
    cols = _num(ceras)[:4]
    with pytest.raises(Exception):
        run_test("canonical_correlation", ceras, {"set_a": cols[:3], "set_b": cols[1:4]}, {})


def test_correspondence_analysis_inertia_matches_chi_square(fame2):
    tab_cols = ["CAMPANA", "SEASON"]
    for c in tab_cols:
        assert c in fame2.columns
    import pandas as pd

    tab = pd.crosstab(fame2["CAMPANA"], fame2["SEASON"])
    chi2, *_ = sstats.chi2_contingency(tab.to_numpy(), correction=False)
    n = tab.to_numpy().sum()

    out = run_test("correspondence_analysis", fame2, {"rows": "CAMPANA", "columns": "SEASON"}, {})
    assert out["statistic"]["totalInertia"] == pytest.approx(chi2 / n, rel=1e-6)


def test_mds_preserves_distance_structure(ceras):
    cols = _num(ceras)[:5]
    out = run_test("mds", ceras, {"columns": cols}, {})
    tab = next(t for t in out["tables"] if t["title"] == "Eigenvalues")
    pcts = [r[2] for r in tab["rows"]]
    assert sum(pcts) <= 100 + 1e-6
    assert pcts[0] >= pcts[1]
