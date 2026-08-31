"""Every registered test must run end-to-end on the real sample data and return
a JSON-serializable payload with the standard shape."""

from __future__ import annotations

import json
import math

import pytest

from stats_core import get_registry, run_test
from stats_core.registry import REGISTRY

REQUIRED_KEYS = {
    "testId", "testName", "summary", "apa", "statistic", "pValue",
    "effectSizes", "assumptions", "tables", "plotSpec", "notes",
}


def _roles_for(test_id, ceras, fame, fame2, two_group_ceras, campaign_col):
    num = [c for c in ceras.columns if ceras[c].dtype.kind in "fi"][:6]
    fnum = [c for c in fame.columns if fame[c].dtype.kind in "fi"][:6]
    g2 = two_group_ceras
    table = {
        "descriptives": (ceras, {"columns": num[:3], "group": campaign_col}, {}),
        "shapiro_wilk": (ceras, {"values": num[0]}, {}),
        "dagostino_pearson": (ceras, {"values": num[0]}, {}),
        "ks_normal": (ceras, {"values": num[0]}, {}),
        "anderson_darling": (ceras, {"values": num[0]}, {}),
        "one_sample_t": (ceras, {"values": num[0]}, {"popmean": 10}),
        "welch_t": (g2, {"values": num[0], "group": campaign_col}, {}),
        "student_t": (g2, {"values": num[0], "group": campaign_col}, {}),
        "paired_t": (ceras, {"first": num[0], "second": num[1]}, {}),
        "mann_whitney": (g2, {"values": num[0], "group": campaign_col}, {}),
        "wilcoxon": (ceras, {"first": num[0], "second": num[1]}, {}),
        "kruskal_wallis": (ceras, {"values": num[0], "group": campaign_col}, {}),
        "friedman": (ceras, {"columns": num[:4]}, {}),
        "one_way_anova": (ceras, {"values": num[0], "group": campaign_col}, {}),
        "welch_anova": (ceras, {"values": num[0], "group": campaign_col}, {}),
        "two_way_anova": (fame2, {"values": fnum[0], "factor_a": "CAMPANA", "factor_b": "SEASON"}, {}),
        "rm_anova": (ceras, {"columns": num[:3]}, {}),
        "ancova": (ceras, {"values": num[0], "group": campaign_col, "covariates": [num[1]]}, {}),
        "posthoc_tukey": (ceras, {"values": num[0], "group": campaign_col}, {}),
        "posthoc_games_howell": (ceras, {"values": num[0], "group": campaign_col}, {}),
        "pearson": (ceras, {"x": num[0], "y": num[1]}, {}),
        "spearman": (ceras, {"x": num[0], "y": num[1]}, {}),
        "kendall": (ceras, {"x": num[0], "y": num[1]}, {}),
        "correlation_matrix": (ceras, {"columns": num[:4]}, {}),
        "linear_regression": (ceras, {"outcome": num[0], "predictors": num[1:3]}, {}),
        "logistic_regression": (None, None, None),  # needs a binary outcome; own module
        "chi_square_independence": (fame2, {"rows": "CAMPANA", "columns": "SEASON"}, {}),
        "chi_square_gof": (fame, {"values": "CAMPANA"}, {}),
        "fisher_exact": (None, None, None),
        "mcnemar": (None, None, None),
        "levene": (ceras, {"values": num[0], "group": campaign_col}, {}),
        "bartlett": (ceras, {"values": num[0], "group": campaign_col}, {}),
    }
    return table[test_id]


@pytest.mark.parametrize("spec", REGISTRY, ids=lambda s: s.id)
def test_every_test_runs(spec, ceras, fame, fame2, two_group_ceras, campaign_col):
    data, roles, params = _roles_for(spec.id, ceras, fame, fame2, two_group_ceras, campaign_col)
    if data is None:
        pytest.skip(f"{spec.id} validated in a dedicated module")
    out = run_test(spec.id, data, roles, params)
    assert REQUIRED_KEYS.issubset(out), f"{spec.id} missing keys: {REQUIRED_KEYS - set(out)}"
    assert out["testName"]
    # must be JSON-serializable with no raw NaN/inf leaking through
    text = json.dumps(out, allow_nan=False)
    assert "NaN" not in text
    for es in out["effectSizes"]:
        assert es["value"] is None or math.isfinite(es["value"])


def test_get_registry_shape():
    reg = get_registry()
    assert reg["version"] == 1
    ids = {t["id"] for t in reg["tests"]}
    assert len(ids) == len(REGISTRY) >= 20
    for t in reg["tests"]:
        assert t["family"] in reg["families"]
        assert "func" not in t
        for role in t["roles"]:
            assert role["dtype"] in {"numeric", "categorical", "any"}
