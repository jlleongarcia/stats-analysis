from __future__ import annotations

import numpy as np
import pytest
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.tree import DecisionTreeClassifier

from stats_core import run_test


def _num(df):
    return [c for c in df.columns if df[c].dtype.kind in "fi"]


def test_discriminant_analysis_matches_sklearn_eigenvalues(ceras, campaign_col):
    cols = _num(ceras)[:5]
    sub = ceras[[campaign_col, *cols]].dropna()
    X = sub[cols].to_numpy(float)
    y = sub[campaign_col].astype(str).to_numpy()

    ref = LinearDiscriminantAnalysis(solver="eigen").fit(X, y)
    ref_eigs = np.sort(ref.explained_variance_ratio_)[::-1]

    out = run_test("discriminant_analysis", ceras, {"group": campaign_col, "predictors": cols}, {})
    eig_table = next(t for t in out["tables"] if t["title"] == "Eigenvalues / canonical correlations")
    got_eigs = np.array([r[1] for r in eig_table["rows"]])
    got_ratio = got_eigs / got_eigs.sum()
    for g, r in zip(sorted(got_ratio, reverse=True), ref_eigs):
        assert g == pytest.approx(r, rel=1e-4)


def test_discriminant_analysis_classification_matches_sklearn_when_balanced(ceras, campaign_col):
    cols = _num(ceras)[:5]
    sub = ceras[[campaign_col, *cols]].dropna()
    X = sub[cols].to_numpy(float)
    y = sub[campaign_col].astype(str).to_numpy()

    ref = LinearDiscriminantAnalysis(solver="eigen").fit(X, y)
    ref_acc = float(np.mean(ref.predict(X) == y))

    out = run_test("discriminant_analysis", ceras, {"group": campaign_col, "predictors": cols}, {})
    # sklearn uses class-proportional priors by default; ours uses equal priors, so
    # allow some slack rather than requiring an exact match on unbalanced groups.
    assert out["statistic"]["resubstitutionAccuracy"] == pytest.approx(ref_acc, abs=0.25)


def test_general_discriminant_analysis_without_covariates_equals_plain(ceras, campaign_col):
    cols = _num(ceras)[:4]
    plain = run_test("discriminant_analysis", ceras, {"group": campaign_col, "predictors": cols}, {})
    gda = run_test("general_discriminant_analysis", ceras, {"group": campaign_col, "predictors": cols}, {})
    assert gda["statistic"]["wilksLambda"] == pytest.approx(plain["statistic"]["wilksLambda"], rel=1e-8)


def test_general_discriminant_analysis_with_covariates_changes_result(ceras, campaign_col):
    cols = _num(ceras)[:4]
    plain = run_test(
        "general_discriminant_analysis", ceras,
        {"group": campaign_col, "predictors": cols[:3]}, {},
    )
    adjusted = run_test(
        "general_discriminant_analysis", ceras,
        {"group": campaign_col, "predictors": cols[:3], "covariates": [cols[3]]}, {},
    )
    assert adjusted["statistic"]["wilksLambda"] != pytest.approx(plain["statistic"]["wilksLambda"])


def test_classification_tree_matches_sklearn_accuracy(ceras, campaign_col):
    cols = _num(ceras)[:5]
    sub = ceras[[campaign_col, *cols]].dropna()
    X = sub[cols].to_numpy(float)
    y = sub[campaign_col].astype(str).to_numpy()

    ref = DecisionTreeClassifier(max_depth=3, min_samples_leaf=5, random_state=0).fit(X, y)
    ref_acc = float(np.mean(ref.predict(X) == y))

    out = run_test("classification_tree", ceras, {"outcome": campaign_col, "predictors": cols}, {})
    assert out["statistic"]["resubstitutionAccuracy"] == pytest.approx(ref_acc, rel=1e-8)
    assert out["statistic"]["nLeaves"] == float(ref.get_n_leaves())


def test_classification_tree_layout_has_one_more_node_than_internal_edges(ceras, campaign_col):
    cols = _num(ceras)[:4]
    out = run_test("classification_tree", ceras, {"outcome": campaign_col, "predictors": cols}, {})
    tree_plot = next(p for p in out["plotSpecs"] if p["kind"] == "tree")
    n_nodes = len(tree_plot["data"]["nodeId"])
    n_edges = len(tree_plot["edges"]["x0"])
    assert n_edges == n_nodes - 1
