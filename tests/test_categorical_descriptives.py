from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from stats_core import run_test
from stats_core._util import DataError


def _num(df):
    return [c for c in df.columns if df[c].dtype.kind in "fi"]


# ---- descriptives ---------------------------------------------------

def test_descriptives_values_match_numpy(ceras):
    col = _num(ceras)[0]
    x = ceras[col].dropna().to_numpy(float)
    out = run_test("descriptives", ceras, {"columns": [col]}, {})
    row = out["tables"][0]["rows"][0]
    cols = out["tables"][0]["columns"]
    d = dict(zip(cols[1:], row[1:]))
    assert d["n"] == x.size
    assert d["mean"] == pytest.approx(x.mean(), rel=1e-9)
    assert d["sd"] == pytest.approx(x.std(ddof=1), rel=1e-9)
    assert d["median"] == pytest.approx(np.median(x), rel=1e-9)


def test_descriptives_grouped_rows(ceras, campaign_col):
    col = _num(ceras)[0]
    k = ceras[campaign_col].nunique()
    out = run_test("descriptives", ceras, {"columns": [col], "group": campaign_col}, {})
    assert len(out["tables"][0]["rows"]) == k


# ---- chi-square ---------------------------------------------------

def test_chi_square_independence_matches_scipy(fame2):
    tab = pd.crosstab(fame2["CAMPANA"], fame2["SEASON"])
    chi2, p, dof, _ = stats.chi2_contingency(tab.to_numpy(), correction=False)
    out = run_test("chi_square_independence", fame2,
                   {"rows": "CAMPANA", "columns": "SEASON"}, {"yates": False})
    assert out["statistic"]["chi2"] == pytest.approx(chi2, rel=1e-9)
    assert out["statistic"]["df"] == dof
    assert out["pValue"] == pytest.approx(p, rel=1e-9)


def test_chi_square_gof_uniform(fame):
    counts = fame["CAMPANA"].value_counts().sort_index().to_numpy(float)
    exp = np.full(counts.size, counts.sum() / counts.size)
    chi2, p = stats.chisquare(counts, exp)
    out = run_test("chi_square_gof", fame, {"values": "CAMPANA"}, {})
    assert out["statistic"]["chi2"] == pytest.approx(chi2, rel=1e-9)
    assert out["pValue"] == pytest.approx(p, rel=1e-9)


def test_fisher_exact_2x2():
    df = pd.DataFrame({
        "grp": ["a"] * 20 + ["b"] * 20,
        "out": ["y"] * 6 + ["n"] * 14 + ["y"] * 15 + ["n"] * 5,
    })
    _, p_ref = stats.fisher_exact([[6, 14], [15, 5]])
    out = run_test("fisher_exact", df, {"rows": "grp", "columns": "out"}, {})
    assert out["pValue"] == pytest.approx(p_ref, rel=1e-9)


def test_mcnemar_exact_small_sample():
    # 10 discordant pairs, lopsided 8 vs 2
    before = ["pos"] * 30 + ["neg"] * 30
    after = (["pos"] * 22 + ["neg"] * 8) + (["pos"] * 2 + ["neg"] * 28)
    df = pd.DataFrame({"before": before, "after": after})
    out = run_test("mcnemar", df, {"first": "before", "second": "after"}, {})
    ref = stats.binomtest(2, 10, 0.5).pvalue
    assert out["pValue"] == pytest.approx(ref, rel=1e-9)


def test_chi_square_rejects_single_category():
    df = pd.DataFrame({"a": ["only"] * 20, "b": ["x", "y"] * 10})
    with pytest.raises(DataError):
        run_test("chi_square_independence", df, {"rows": "a", "columns": "b"}, {})
