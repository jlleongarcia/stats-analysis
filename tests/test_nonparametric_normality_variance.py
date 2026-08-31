from __future__ import annotations

import numpy as np
import pytest
from scipy import stats

from stats_core import run_test


def _num(df):
    return [c for c in df.columns if df[c].dtype.kind in "fi"]


# ---- normality ---------------------------------------------------------

def test_shapiro_matches_scipy(ceras):
    col = _num(ceras)[0]
    x = ceras[col].dropna().to_numpy(float)
    w, p = stats.shapiro(x)
    out = run_test("shapiro_wilk", ceras, {"values": col}, {})
    assert out["statistic"]["W"] == pytest.approx(w, rel=1e-9)
    assert out["pValue"] == pytest.approx(p, rel=1e-9)
    assert out["assumptions"][0]["name"] == "Normality"
    assert out["assumptions"][0]["passed"] == (p >= 0.05)


def test_normal_data_passes_shapiro(normal_frame):
    out = run_test("shapiro_wilk", normal_frame, {"values": "x"}, {})
    assert out["assumptions"][0]["passed"] is True


def test_dagostino_matches_scipy(normal_frame):
    k2, p = stats.normaltest(normal_frame["x"].to_numpy(float))
    out = run_test("dagostino_pearson", normal_frame, {"values": "x"}, {})
    assert out["statistic"]["K2"] == pytest.approx(k2, rel=1e-9)


def test_anderson_darling_reports_critical_values(ceras):
    col = _num(ceras)[0]
    out = run_test("anderson_darling", ceras, {"values": col}, {})
    assert out["tables"][0]["title"] == "Critical values"
    assert len(out["tables"][0]["rows"]) >= 3


# ---- nonparametric --------------------------------------------------

def test_mann_whitney_matches_scipy(two_group_ceras, campaign_col):
    col = _num(two_group_ceras)[0]
    g = two_group_ceras.dropna(subset=[col, campaign_col])
    levels = sorted(g[campaign_col].astype(str).unique())
    a = g[g[campaign_col].astype(str) == levels[0]][col].to_numpy(float)
    b = g[g[campaign_col].astype(str) == levels[1]][col].to_numpy(float)
    ref = stats.mannwhitneyu(a, b, alternative="two-sided")
    out = run_test("mann_whitney", two_group_ceras, {"values": col, "group": campaign_col}, {})
    assert out["statistic"]["U"] == pytest.approx(ref.statistic, rel=1e-9)
    assert out["pValue"] == pytest.approx(ref.pvalue, rel=1e-9)


def test_kruskal_matches_scipy(ceras, campaign_col):
    col = _num(ceras)[0]
    sub = ceras.dropna(subset=[col, campaign_col])
    arrays = [g[col].to_numpy(float) for _, g in sub.groupby(campaign_col)]
    ref = stats.kruskal(*arrays)
    out = run_test("kruskal_wallis", ceras, {"values": col, "group": campaign_col}, {})
    assert out["statistic"]["H"] == pytest.approx(ref.statistic, rel=1e-9)
    assert out["pValue"] == pytest.approx(ref.pvalue, rel=1e-9)


def test_wilcoxon_matches_scipy(ceras):
    c1, c2 = _num(ceras)[:2]
    sub = ceras[[c1, c2]].dropna()
    ref = stats.wilcoxon(sub[c1], sub[c2])
    out = run_test("wilcoxon", ceras, {"first": c1, "second": c2}, {})
    assert out["statistic"]["W"] == pytest.approx(ref.statistic, rel=1e-9)


def test_friedman_matches_scipy(ceras):
    cols = _num(ceras)[:4]
    sub = ceras[cols].dropna()
    ref = stats.friedmanchisquare(*[sub[c].to_numpy(float) for c in cols])
    out = run_test("friedman", ceras, {"columns": cols}, {})
    assert out["statistic"]["chi2"] == pytest.approx(ref.statistic, rel=1e-9)


# ---- variance ---------------------------------------------------------

def test_levene_matches_scipy(ceras, campaign_col):
    col = _num(ceras)[0]
    sub = ceras.dropna(subset=[col, campaign_col])
    arrays = [g[col].to_numpy(float) for _, g in sub.groupby(campaign_col)]
    ref = stats.levene(*arrays, center="median")
    out = run_test("levene", ceras, {"values": col, "group": campaign_col}, {})
    assert out["statistic"]["W"] == pytest.approx(ref.statistic, rel=1e-9)
    assert out["pValue"] == pytest.approx(ref.pvalue, rel=1e-9)


def test_bartlett_matches_scipy(ceras, campaign_col):
    col = _num(ceras)[0]
    sub = ceras.dropna(subset=[col, campaign_col])
    arrays = [g[col].to_numpy(float) for _, g in sub.groupby(campaign_col)]
    ref = stats.bartlett(*arrays)
    out = run_test("bartlett", ceras, {"values": col, "group": campaign_col}, {})
    assert out["statistic"]["chi2"] == pytest.approx(ref.statistic, rel=1e-9)
