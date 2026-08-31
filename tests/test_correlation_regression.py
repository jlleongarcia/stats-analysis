from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm
from scipy import stats

from stats_core import run_test


def _num(df):
    return [c for c in df.columns if df[c].dtype.kind in "fi"]


def test_pearson_matches_scipy(ceras):
    x, y = _num(ceras)[:2]
    sub = ceras[[x, y]].dropna()
    r_ref, p_ref = stats.pearsonr(sub[x], sub[y])
    out = run_test("pearson", ceras, {"x": x, "y": y}, {})
    assert out["statistic"]["coefficient"] == pytest.approx(r_ref, rel=1e-9)
    assert out["pValue"] == pytest.approx(p_ref, rel=1e-9)
    es = out["effectSizes"][0]
    assert es["ciLow"] <= es["value"] <= es["ciHigh"]


def test_spearman_and_kendall_match_scipy(ceras):
    x, y = _num(ceras)[:2]
    sub = ceras[[x, y]].dropna()
    out_s = run_test("spearman", ceras, {"x": x, "y": y}, {})
    out_k = run_test("kendall", ceras, {"x": x, "y": y}, {})
    assert out_s["statistic"]["coefficient"] == pytest.approx(stats.spearmanr(sub[x], sub[y])[0], rel=1e-9)
    assert out_k["statistic"]["coefficient"] == pytest.approx(stats.kendalltau(sub[x], sub[y])[0], rel=1e-9)


def test_correlation_matrix_diagonal_is_one(ceras):
    cols = _num(ceras)[:4]
    out = run_test("correlation_matrix", ceras, {"columns": cols}, {"method": "pearson"})
    coeff = next(t for t in out["tables"] if t["title"] == "Coefficients")
    for i, row in enumerate(coeff["rows"]):
        assert row[i + 1] == pytest.approx(1.0, abs=1e-9)


def test_linear_regression_matches_statsmodels(ceras):
    y, *xs = _num(ceras)[:3]
    sub = ceras[[y, *xs]].dropna()
    X = sm.add_constant(sub[xs].to_numpy(float))
    ref = sm.OLS(sub[y].to_numpy(float), X).fit()
    out = run_test("linear_regression", ceras, {"outcome": y, "predictors": xs}, {})
    assert out["statistic"]["rSquared"] == pytest.approx(ref.rsquared, rel=1e-9)
    assert out["statistic"]["F"] == pytest.approx(ref.fvalue, rel=1e-9)
    coefs = out["tables"][0]["rows"]
    assert len(coefs) == len(xs) + 1
    assert coefs[1][1] == pytest.approx(ref.params[1], rel=1e-8)


def test_logistic_regression_binary_outcome(rng):
    n = 300
    x1 = rng.normal(0, 1, n)
    x2 = rng.normal(5, 20, n)  # very different scale -> exercises standardization
    logit = -0.3 + 1.4 * x1 + 0.02 * x2
    y = rng.random(n) < 1 / (1 + np.exp(-logit))
    # label the event "1" so it sorts last -> model estimates P(y == "1")
    df = pd.DataFrame({"x1": x1, "x2": x2, "y": np.where(y, "1", "0")})
    out = run_test("logistic_regression", df, {"outcome": "y", "predictors": ["x1", "x2"]}, {})
    assert 0 <= out["statistic"]["pseudoRSquared"] <= 1
    assert out["pValue"] < 0.05
    or_x1 = out["tables"][0]["rows"][1][2]  # odds ratio for x1 (per 1 SD)
    assert or_x1 > 1  # positive association recovered


def test_logistic_regression_rejects_non_binary(ceras, campaign_col):
    from stats_core._util import DataError

    with pytest.raises(DataError):
        run_test("logistic_regression", ceras, {"outcome": campaign_col, "predictors": _num(ceras)[:1]}, {})
