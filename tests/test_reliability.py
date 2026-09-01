from __future__ import annotations

import numpy as np
import pytest

from stats_core import run_test


def _num(df):
    return [c for c in df.columns if df[c].dtype.kind in "fi"]


def _manual_cronbach_alpha(X: np.ndarray) -> float:
    k = X.shape[1]
    item_vars = X.var(axis=0, ddof=1)
    total_var = X.sum(axis=1).var(ddof=1)
    return k / (k - 1) * (1 - item_vars.sum() / total_var)


def test_cronbach_alpha_matches_manual_formula(ceras):
    cols = _num(ceras)[:5]
    sub = ceras[cols].dropna()
    ref = _manual_cronbach_alpha(sub.to_numpy(float))

    out = run_test("reliability_analysis", ceras, {"columns": cols}, {})
    assert out["statistic"]["cronbachAlpha"] == pytest.approx(ref, rel=1e-10)


def test_alpha_of_perfectly_correlated_items_is_one():
    import pandas as pd

    rng = np.random.default_rng(0)
    base = rng.normal(size=50)
    df = pd.DataFrame({"i1": base, "i2": base, "i3": base, "i4": base})
    out = run_test("reliability_analysis", df, {"columns": ["i1", "i2", "i3", "i4"]}, {})
    assert out["statistic"]["cronbachAlpha"] == pytest.approx(1.0, abs=1e-8)


def test_item_total_correlations_present_for_every_item(ceras):
    cols = _num(ceras)[:4]
    out = run_test("reliability_analysis", ceras, {"columns": cols}, {})
    table = next(t for t in out["tables"] if t["title"] == "Item statistics")
    assert len(table["rows"]) == len(cols)
    for row in table["rows"]:
        assert -1.0 <= row[3] <= 1.0
