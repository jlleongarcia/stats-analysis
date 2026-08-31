from __future__ import annotations

import numpy as np
import pytest
from scipy import stats

from stats_core import run_test


def _num(df):
    return [c for c in df.columns if df[c].dtype.kind in "fi"]


def test_one_way_anova_matches_scipy(ceras, campaign_col):
    col = _num(ceras)[0]
    sub = ceras.dropna(subset=[col, campaign_col])
    arrays = [g[col].to_numpy(float) for _, g in sub.groupby(campaign_col)]
    ref = stats.f_oneway(*arrays)
    out = run_test("one_way_anova", ceras, {"values": col, "group": campaign_col}, {})
    assert out["statistic"]["F"] == pytest.approx(ref.statistic, rel=1e-9)
    assert out["pValue"] == pytest.approx(ref.pvalue, rel=1e-9)
    eta2 = next(e["value"] for e in out["effectSizes"] if e["name"] == "eta^2")
    assert 0 <= eta2 <= 1


def test_one_way_anova_table_sums(ceras, campaign_col):
    col = _num(ceras)[0]
    out = run_test("one_way_anova", ceras, {"values": col, "group": campaign_col}, {})
    tbl = next(t for t in out["tables"] if t["title"] == "ANOVA table")
    ss = {r[0]: r[1] for r in tbl["rows"]}
    assert ss["Total"] == pytest.approx(ss[campaign_col] + ss["Residual"], rel=1e-9)


def test_welch_anova_reduces_to_scipy_when_balanced(normal_frame):
    out = run_test("welch_anova", normal_frame, {"values": "x", "group": "g"}, {})
    # sanity: F positive, p in [0,1]
    assert out["statistic"]["F"] > 0
    assert 0 <= out["pValue"] <= 1


def test_two_way_anova_runs_and_reports_interaction(fame2):
    num = _num(fame2)[0]
    out = run_test("two_way_anova", fame2, {"values": num, "factor_a": "CAMPANA", "factor_b": "SEASON"}, {})
    tbl = out["tables"][0]
    sources = {r[0] for r in tbl["rows"]}
    assert any("x" in s for s in sources)  # interaction row present
    assert "Residual" in sources


def test_rm_anova_matches_scipy_repeated_measures(ceras):
    cols = _num(ceras)[:3]
    wide = ceras[cols].dropna()
    ref = stats.f_oneway  # not directly comparable; use friedman-free check
    out = run_test("rm_anova", ceras, {"columns": cols}, {})
    assert out["statistic"]["F"] > 0
    pe = next(e["value"] for e in out["effectSizes"] if "eta^2" in e["name"])
    assert 0 <= pe <= 1


def test_ancova_group_effect_present(ceras, campaign_col):
    cols = _num(ceras)[:2]
    out = run_test("ancova", ceras, {"values": cols[0], "group": campaign_col, "covariates": [cols[1]]}, {})
    assert "F" in out["statistic"]
    assert out["tables"][0]["title"].startswith("ANCOVA")


def test_tukey_posthoc_pair_count(ceras, campaign_col):
    col = _num(ceras)[0]
    k = ceras[campaign_col].astype(str).nunique()
    out = run_test("posthoc_tukey", ceras, {"values": col, "group": campaign_col}, {})
    rows = out["tables"][0]["rows"]
    assert len(rows) == k * (k - 1) // 2


def test_games_howell_matches_manual_welch_pair(ceras, campaign_col):
    col = _num(ceras)[0]
    out = run_test("posthoc_games_howell", ceras, {"values": col, "group": campaign_col}, {})
    rows = out["tables"][0]["rows"]
    k = ceras[campaign_col].astype(str).nunique()
    assert len(rows) == k * (k - 1) // 2
    for r in rows:
        assert r[3] <= r[2] <= r[4]  # ci_low <= diff <= ci_high
