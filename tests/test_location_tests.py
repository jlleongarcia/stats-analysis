"""Validate the t-tests against direct scipy calls on the sample data."""

from __future__ import annotations

import numpy as np
import pytest
from scipy import stats

from stats_core import run_test
from stats_core._util import DataError


def _num_cols(df):
    return [c for c in df.columns if df[c].dtype.kind in "fi"]


def test_one_sample_t_matches_scipy(ceras):
    col = _num_cols(ceras)[0]
    x = ceras[col].dropna().to_numpy(float)
    ref = stats.ttest_1samp(x, 5.0)
    out = run_test("one_sample_t", ceras, {"values": col}, {"popmean": 5.0})
    assert out["statistic"]["t"] == pytest.approx(ref.statistic, rel=1e-9)
    assert out["pValue"] == pytest.approx(ref.pvalue, rel=1e-9)
    assert out["statistic"]["df"] == len(x) - 1


def test_welch_t_matches_scipy(two_group_ceras, campaign_col):
    col = _num_cols(two_group_ceras)[0]
    g = two_group_ceras.dropna(subset=[col, campaign_col])
    levels = sorted(g[campaign_col].astype(str).unique())
    a = g[g[campaign_col].astype(str) == levels[0]][col].to_numpy(float)
    b = g[g[campaign_col].astype(str) == levels[1]][col].to_numpy(float)
    ref = stats.ttest_ind(a, b, equal_var=False)
    out = run_test("welch_t", two_group_ceras, {"values": col, "group": campaign_col}, {})
    assert out["statistic"]["t"] == pytest.approx(ref.statistic, rel=1e-9)
    assert out["pValue"] == pytest.approx(ref.pvalue, rel=1e-9)
    names = {e["name"] for e in out["effectSizes"]}
    assert {"Cohen's d", "Hedges' g"} <= names


def test_student_t_matches_scipy(two_group_ceras, campaign_col):
    col = _num_cols(two_group_ceras)[1]
    g = two_group_ceras.dropna(subset=[col, campaign_col])
    levels = sorted(g[campaign_col].astype(str).unique())
    a = g[g[campaign_col].astype(str) == levels[0]][col].to_numpy(float)
    b = g[g[campaign_col].astype(str) == levels[1]][col].to_numpy(float)
    ref = stats.ttest_ind(a, b, equal_var=True)
    out = run_test("student_t", two_group_ceras, {"values": col, "group": campaign_col}, {})
    assert out["statistic"]["t"] == pytest.approx(ref.statistic, rel=1e-9)
    assert out["statistic"]["df"] == len(a) + len(b) - 2


def test_paired_t_matches_scipy(ceras):
    c1, c2 = _num_cols(ceras)[:2]
    sub = ceras[[c1, c2]].dropna()
    ref = stats.ttest_rel(sub[c1], sub[c2])
    out = run_test("paired_t", ceras, {"first": c1, "second": c2}, {})
    assert out["statistic"]["t"] == pytest.approx(ref.statistic, rel=1e-9)
    assert out["pValue"] == pytest.approx(ref.pvalue, rel=1e-9)


def test_one_sided_alternative_halves_p(ceras):
    col = _num_cols(ceras)[0]
    two = run_test("one_sample_t", ceras, {"values": col}, {"popmean": 0, "alternative": "two-sided"})
    one = run_test("one_sample_t", ceras, {"values": col}, {"popmean": 0, "alternative": "greater"})
    # all-positive chemistry data => mean > 0 => one-sided p is ~half the two-sided p
    assert one["pValue"] == pytest.approx(two["pValue"] / 2, rel=1e-6)


def test_welch_t_rejects_three_groups(ceras, campaign_col):
    col = _num_cols(ceras)[0]
    with pytest.raises(DataError):
        run_test("welch_t", ceras, {"values": col, "group": campaign_col}, {})
