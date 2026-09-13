"""SPC engine tests.

Ported from the SPC-analysis project's `tests/test_spc_core.py`, then extended
to cover the behaviours that used to live in its Streamlit pages and therefore
had no tests at all: the bridging moving-range mask, the audit log, two-pass
finalisation, cross-variable flagging, and the interpretation heuristics.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from stats_core._util import DataError
from stats_core.spc import (
    AssignableCauseRequired,
    Decision,
    DecisionSet,
    apply_all_rules,
    bridging_mr_mask,
    build_audit_log,
    capability_verdicts,
    compute_capability,
    compute_limits,
    compute_moving_range,
    constants_for,
    cross_flags,
    finalise,
    normality_precheck,
    phase_i_verdicts,
    rule1_action_limits,
    rule2_warning_zone,
    rule3_run_same_side,
    rule4_trend,
    run_phase_i_pass,
    shared_removals,
    spc_call,
)
from stats_core.spc.constants import D2

# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------


@pytest.fixture
def stable_series() -> pd.Series:
    """50-point in-control series (mean 100, sigma ~2)."""
    rng = np.random.default_rng(0)
    return pd.Series(rng.normal(100, 2, 50), name="value")


@pytest.fixture
def series_with_outlier(stable_series) -> pd.Series:
    s = stable_series.copy()
    s.iloc[25] = 120.0  # unmistakable rule 1 violation
    return s


@pytest.fixture
def spc_frame(series_with_outlier) -> dict:
    """A Studio-shaped payload body: columnar data plus a label column."""
    n = len(series_with_outlier)
    return {
        "day": [f"2026-01-{i + 1:02d}" for i in range(n)],
        "measurement": series_with_outlier.tolist(),
    }


# --------------------------------------------------------------------------
# constants
# --------------------------------------------------------------------------


class TestConstants:
    def test_n2_matches_the_classic_individuals_values(self):
        c = constants_for(2)
        assert c.d2 == pytest.approx(1.128)
        assert c.D4 == pytest.approx(3.267)
        assert c.D3 == 0.0  # why the MR chart's LCL is always zero at n=2

    def test_d2_increases_with_subgroup_size(self):
        sizes = range(2, 26)
        d2s = [constants_for(n).d2 for n in sizes]
        assert all(b > a for a, b in zip(d2s, d2s[1:]))

    def test_range_chart_lower_factor_appears_at_n7(self):
        assert constants_for(6).D3 == 0.0
        assert constants_for(7).D3 > 0.0

    def test_untabulated_size_is_refused_not_extrapolated(self):
        with pytest.raises(ValueError, match="X-bar/S"):
            constants_for(40)


# --------------------------------------------------------------------------
# limits
# --------------------------------------------------------------------------


class TestLimits:
    def test_structure(self, stable_series):
        lim = compute_limits(stable_series)
        assert set(lim) == {
            "n", "x_bar", "mr_bar", "sigma_within",
            "i_ucl", "i_uwl", "i_cl", "i_lwl", "i_lcl",
            "mr_ucl", "mr_uwl", "mr_cl", "mr_lcl",
        }

    def test_limits_are_symmetric_about_the_centre(self, stable_series):
        lim = compute_limits(stable_series)
        assert lim["i_ucl"] - lim["i_cl"] == pytest.approx(lim["i_cl"] - lim["i_lcl"])
        assert lim["i_uwl"] - lim["i_cl"] == pytest.approx(lim["i_cl"] - lim["i_lwl"])

    def test_sigma_comes_from_mr_bar_over_d2(self, stable_series):
        expected = compute_moving_range(stable_series).dropna().mean() / D2
        assert compute_limits(stable_series)["sigma_within"] == pytest.approx(expected)

    def test_action_limit_is_three_sigma(self, stable_series):
        lim = compute_limits(stable_series)
        assert lim["i_ucl"] == pytest.approx(lim["i_cl"] + 3 * lim["sigma_within"])
        assert lim["i_uwl"] == pytest.approx(lim["i_cl"] + 2 * lim["sigma_within"])

    def test_mr_chart_lower_limit_is_zero(self, stable_series):
        assert compute_limits(stable_series)["mr_lcl"] == 0.0

    def test_too_few_values_raises(self):
        with pytest.raises(ValueError, match="At least 2"):
            compute_limits(pd.Series([1.0]))

    def test_nan_is_ignored(self):
        lim = compute_limits(pd.Series([1.0, np.nan, 2.0, 3.0, 4.0]))
        assert np.isfinite(lim["x_bar"])
        assert lim["n"] == 4

    def test_mismatched_mask_is_rejected(self, stable_series):
        with pytest.raises(ValueError, match="they must match"):
            compute_limits(stable_series, mr_mask=np.ones(3, dtype=bool))


class TestBridgingMask:
    """Rescued from pages/02_phase_i.py - previously untested UI logic."""

    def test_contiguous_run_has_no_bridges(self):
        assert bridging_mr_mask([0, 1, 2, 3]).tolist() == [True, True, True, True]

    def test_gap_marks_the_range_that_spans_it(self):
        # Point 3 removed: the MR from 2 to 4 never existed in the real process.
        assert bridging_mr_mask([0, 1, 2, 4, 5]).tolist() == [
            True, True, True, False, True,
        ]

    def test_first_point_is_always_true(self):
        # Its moving range is NaN and gets dropped regardless.
        assert bool(bridging_mr_mask([7, 8, 9])[0])

    def test_mask_excludes_the_bridging_range_from_mr_bar(self):
        # Spike at index 5. After removal, 9.9 and 10.0 sit next to each other
        # in the filtered series but were never adjacent in the process, so
        # their range must not inform sigma_within.
        values = pd.Series([10.0, 10.2, 9.8, 10.1, 9.9, 40.0, 10.0, 10.3, 9.7])
        kept = [0, 1, 2, 3, 4, 6, 7, 8]
        survivors = values.iloc[kept].reset_index(drop=True)
        #      survivor MRs: [nan, 0.2, 0.4, 0.3, 0.2, 0.1, 0.3, 0.6]
        #      bridging one:                          ^^^ (9.9 -> 10.0)
        masked = compute_limits(survivors, mr_mask=bridging_mr_mask(kept))
        unmasked = compute_limits(survivors)

        assert masked["mr_bar"] == pytest.approx(2.0 / 6)    # 0.1 dropped
        assert unmasked["mr_bar"] == pytest.approx(2.1 / 7)  # 0.1 included

    def test_masking_is_not_about_shrinking_sigma(self):
        # The bridging range is excluded because it is not a valid measurement
        # of short-term variation - not because it is large. Here it happens to
        # be the smallest range present, so excluding it raises the estimate.
        values = pd.Series([10.0, 10.2, 9.8, 10.1, 9.9, 40.0, 10.0, 10.3, 9.7])
        kept = [0, 1, 2, 3, 4, 6, 7, 8]
        survivors = values.iloc[kept].reset_index(drop=True)

        masked = compute_limits(survivors, mr_mask=bridging_mr_mask(kept))
        unmasked = compute_limits(survivors)
        assert masked["sigma_within"] > unmasked["sigma_within"]


# --------------------------------------------------------------------------
# rules
# --------------------------------------------------------------------------


class TestRules:
    def test_rule1_detects_a_high_outlier(self):
        s = pd.Series([10.0] * 20)
        s.iloc[10] = 50.0
        lim = compute_limits(s)
        assert rule1_action_limits(s, lim["i_ucl"], lim["i_lcl"]).iloc[10]

    def test_rule1_is_quiet_on_stable_data(self, stable_series):
        lim = compute_limits(stable_series)
        assert rule1_action_limits(stable_series, lim["i_ucl"], lim["i_lcl"]).sum() <= 2

    def test_rule2_fires_on_two_of_three_in_one_zone(self):
        s = pd.Series([0, 0, 3.0, 3.0, 0, 0, 0, 0, 0, 0])
        flags = rule2_warning_zone(s, cl=0.0, uwl=2.0, lwl=-2.0)
        assert flags.iloc[3]

    def test_rule2_does_not_mix_opposite_zones(self):
        # One point high, one low: opposite shifts, not a single signal.
        s = pd.Series([0.0, 3.0, -3.0, 0.0, 0.0])
        assert not rule2_warning_zone(s, cl=0.0, uwl=2.0, lwl=-2.0).any()

    def test_rule3_fires_at_eight_on_one_side(self):
        assert rule3_run_same_side(pd.Series([1.0] * 8 + [0.0] * 5), cl=0.0, k=8).iloc[7]

    def test_rule3_ignores_seven(self):
        assert not rule3_run_same_side(pd.Series([1.0] * 7 + [0.0] * 5), cl=0.0, k=8).any()

    def test_rule3_ignores_points_exactly_on_the_centre(self):
        assert not rule3_run_same_side(pd.Series([0.0] * 12), cl=0.0, k=8).any()

    def test_rule4_fires_on_six_rising(self):
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0] + [5.0] * 5)
        assert rule4_trend(s, k=6).iloc[5]

    def test_rule4_ignores_five_rising(self):
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0] + [4.0] * 5)
        assert not rule4_trend(s, k=6).any()

    def test_rule4_is_broken_by_a_tie(self):
        s = pd.Series([1.0, 2.0, 3.0, 3.0, 4.0, 5.0, 6.0])
        assert not rule4_trend(s, k=6).any()

    def test_apply_all_rules_shape(self, series_with_outlier):
        lim = compute_limits(series_with_outlier)
        flags = apply_all_rules(series_with_outlier, lim)
        assert list(flags.columns) == ["rule1", "rule2", "rule3", "rule4", "any_violation"]
        assert flags["any_violation"].iloc[25]


# --------------------------------------------------------------------------
# capability
# --------------------------------------------------------------------------


class TestCapability:
    def test_cp_formula(self, stable_series):
        lim = compute_limits(stable_series)
        cap = compute_capability(stable_series, 106.0, 94.0, mr_bar=lim["mr_bar"])
        assert cap["cp"] == pytest.approx(12.0 / (6 * lim["sigma_within"]))

    def test_rpi_equals_cp(self, stable_series):
        cap = compute_capability(stable_series, 106.0, 94.0)
        assert cap["rpi"] == pytest.approx(cap["cp"])

    def test_cpk_never_exceeds_cp(self, stable_series):
        cap = compute_capability(stable_series, 106.0, 94.0)
        assert cap["cpk"] <= cap["cp"] + 1e-9

    def test_cpk_equals_cp_when_perfectly_centred(self):
        rng = np.random.default_rng(3)
        s = pd.Series(rng.normal(100, 1, 200))
        cap = compute_capability(s, 100 + 6, 100 - 6)
        # Centring is empirical, not exact, so allow a little slack.
        assert cap["cpk"] == pytest.approx(cap["cp"], rel=0.05)

    def test_inverted_specs_are_rejected(self, stable_series):
        with pytest.raises(ValueError, match="USL must be strictly greater"):
            compute_capability(stable_series, usl=90.0, lsl=100.0)

    def test_supplied_mr_bar_wins_over_recomputation(self, stable_series):
        # The mr_bar trap: passing the baseline's value must drive sigma_within,
        # not a fresh (potentially bridge-contaminated) computation.
        cap = compute_capability(stable_series, 106.0, 94.0, mr_bar=4.0)
        assert cap["sigma_within"] == pytest.approx(4.0 / D2)


# --------------------------------------------------------------------------
# phase I
# --------------------------------------------------------------------------


class TestPhaseIPass:
    def test_stable_data_produces_no_violations(self):
        mean, sigma = 100.0, 2.0
        values = [mean + (0.3 * sigma if i % 2 == 0 else -0.3 * sigma) for i in range(30)]
        assert not run_phase_i_pass(pd.Series(values)).any_violations

    def test_obvious_outlier_is_flagged(self, series_with_outlier):
        result = run_phase_i_pass(series_with_outlier)
        assert result.any_violations
        assert 25 in result.flagged_positions

    def test_labels_and_positions_align_with_values(self, stable_series):
        result = run_phase_i_pass(stable_series)
        assert len(result.original_labels) == len(result.values)
        assert len(result.original_positions) == len(result.values)

    def test_nan_rows_are_excluded(self):
        result = run_phase_i_pass(pd.Series([1.0, np.nan, 2.0, 3.0, 4.0, 5.0]))
        assert result.n_original == 5

    def test_too_few_observations_raises(self):
        with pytest.raises(ValueError, match="At least 2"):
            run_phase_i_pass(pd.Series([1.0]))

    def test_rule_config_is_recorded(self, stable_series):
        assert run_phase_i_pass(stable_series, rule3_k=10).rule_config["rule3_k"] == 10

    def test_flagged_positions_are_in_range(self, series_with_outlier):
        result = run_phase_i_pass(series_with_outlier)
        assert all(0 <= p < result.n_original for p in result.flagged_positions)

    def test_string_index_is_preserved_as_labels(self):
        dates = pd.date_range("2026-01-01", periods=30, freq="D").strftime("%Y-%m-%d")
        rng = np.random.default_rng(42)
        result = run_phase_i_pass(pd.Series(rng.normal(100, 2, 30), index=dates))
        assert all(isinstance(label, str) for label in result.original_labels)

    def test_the_pass_never_mutates_its_input(self, series_with_outlier):
        before = series_with_outlier.copy()
        run_phase_i_pass(series_with_outlier)
        pd.testing.assert_series_equal(series_with_outlier, before)


class TestFinalise:
    """Rescued from pages/02_phase_i.py::_finalise - previously untested."""

    def test_no_removals_certifies_pass_one(self, series_with_outlier):
        first = run_phase_i_pass(series_with_outlier)
        result = finalise(first, series_with_outlier, DecisionSet())
        assert result.n_passes == 1
        assert result.n_removed == 0
        assert result.n_final == first.n_original
        assert result.final_limits == first.limits

    def test_removal_triggers_a_second_pass(self, series_with_outlier):
        first = run_phase_i_pass(series_with_outlier)
        decisions = DecisionSet({25: Decision(25, remove=True, cause="Sensor fault")})
        result = finalise(first, series_with_outlier, decisions)

        assert result.n_passes == 2
        assert result.n_removed == 1
        assert result.n_final == first.n_original - 1
        # Dropping the spike must tighten the limits.
        assert result.final_limits["sigma_within"] < first.limits["sigma_within"]

    def test_removal_without_a_cause_is_refused(self, series_with_outlier):
        first = run_phase_i_pass(series_with_outlier)
        decisions = DecisionSet({25: Decision(25, remove=True, cause="   ")})
        with pytest.raises(AssignableCauseRequired, match="assignable cause"):
            finalise(first, series_with_outlier, decisions)

    def test_retaining_a_flagged_point_needs_no_cause(self, series_with_outlier):
        first = run_phase_i_pass(series_with_outlier)
        decisions = DecisionSet({25: Decision(25, remove=False)})
        result = finalise(first, series_with_outlier, decisions)
        assert result.n_removed == 0
        assert result.final_pass_has_violations

    def test_removal_is_duplicate_label_safe(self):
        # Two observations share the label "B"; only the spike must go.
        values = pd.Series(
            [10.0, 10.1, 60.0, 10.2, 9.9, 10.0, 10.1, 9.8],
            index=["A", "B", "B", "C", "D", "E", "F", "G"],
        )
        first = run_phase_i_pass(values)
        spike = next(
            p for p in first.flagged_positions
            if float(first.values.iloc[p]) == pytest.approx(60.0)
        )
        result = finalise(
            first, values, DecisionSet({spike: Decision(spike, True, "Calibration slip")})
        )
        assert result.n_final == 7
        assert list(result.original_labels).count("B") == 1

    def test_second_pass_limits_use_the_bridging_mask(self):
        # A spike in the middle: after removal, the range spanning the gap must
        # not contribute to mr_bar.
        values = pd.Series([10.0, 10.4, 10.1, 60.0, 10.3, 9.9, 10.2, 10.0, 10.1, 9.8])
        first = run_phase_i_pass(values)
        spike = next(
            p for p in first.flagged_positions
            if float(first.values.iloc[p]) == pytest.approx(60.0)
        )
        result = finalise(
            first, values, DecisionSet({spike: Decision(spike, True, "Known upset")})
        )

        survivors = values.drop(index=values.index[spike]).reset_index(drop=True)
        naive = compute_limits(survivors)["mr_bar"]
        masked = compute_limits(
            survivors,
            mr_mask=bridging_mr_mask([i for i in range(len(values)) if i != spike]),
        )["mr_bar"]

        assert result.final_limits["mr_bar"] == pytest.approx(masked)
        assert masked != pytest.approx(naive)

    def test_removal_rate_is_reported(self, series_with_outlier):
        first = run_phase_i_pass(series_with_outlier)
        result = finalise(
            first, series_with_outlier,
            DecisionSet({25: Decision(25, True, "Sensor fault")}),
        )
        assert result.removal_rate == pytest.approx(1 / 50)


# --------------------------------------------------------------------------
# audit log
# --------------------------------------------------------------------------


class TestAuditLog:
    """Rescued from pages/02_phase_i.py - the decision log schema."""

    def test_every_flagged_point_gets_a_row(self, series_with_outlier):
        first = run_phase_i_pass(series_with_outlier)
        log = build_audit_log(first, DecisionSet())
        assert len(log) == len(first.flagged_positions)

    def test_columns_match_the_documented_schema(self, series_with_outlier):
        first = run_phase_i_pass(series_with_outlier)
        log = build_audit_log(first, DecisionSet())
        assert list(log.columns) == [
            "pass", "observation", "value", "rules_violated",
            "decision", "assignable_cause", "x_bar", "ual", "lal",
        ]

    def test_retained_points_are_logged_as_decisions(self, series_with_outlier):
        first = run_phase_i_pass(series_with_outlier)
        log = build_audit_log(first, DecisionSet())
        assert (log["decision"] == "Retained (analyst decision)").all()

    def test_removal_records_the_cause(self, series_with_outlier):
        first = run_phase_i_pass(series_with_outlier)
        log = build_audit_log(
            first, DecisionSet({25: Decision(25, True, "Chiller trip WO-1142")})
        )
        row = log[log["decision"] == "Removed"].iloc[0]
        assert row["assignable_cause"] == "Chiller trip WO-1142"
        assert "rule1" in row["rules_violated"]

    def test_limits_at_review_time_are_captured(self, series_with_outlier):
        first = run_phase_i_pass(series_with_outlier)
        log = build_audit_log(first, DecisionSet())
        assert log["x_bar"].iloc[0] == pytest.approx(first.limits["i_cl"])
        assert log["ual"].iloc[0] == pytest.approx(first.limits["i_ucl"])

    def test_empty_log_keeps_its_columns(self):
        stable = pd.Series([100.0 + (0.3 if i % 2 == 0 else -0.3) for i in range(30)])
        log = build_audit_log(run_phase_i_pass(stable), DecisionSet())
        assert log.empty
        assert "assignable_cause" in log.columns


# --------------------------------------------------------------------------
# cross-variable flagging
# --------------------------------------------------------------------------


class TestCrossFlag:
    """Rescued from pages/02_phase_i.py::_cross_flagged_info."""

    @staticmethod
    def _log(pairs: list[tuple[str, str]]) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"observation": label, "decision": decision, "pass": 1, "value": 0.0,
                 "rules_violated": "rule1", "assignable_cause": "", "x_bar": 0.0,
                 "ual": 0.0, "lal": 0.0}
                for label, decision in pairs
            ]
        )

    def test_flags_labels_removed_from_other_variables(self):
        logs = {
            "temp": self._log([("2026-01-05", "Removed")]),
            "pressure": self._log([("2026-01-05", "Removed"), ("2026-01-09", "Removed")]),
        }
        flags = cross_flags(logs, target="temp")
        assert set(flags) == {"2026-01-05", "2026-01-09"}
        assert flags["2026-01-05"].removed_from == ("pressure",)

    def test_a_variable_never_cross_flags_itself(self):
        logs = {"temp": self._log([("2026-01-05", "Removed")])}
        assert cross_flags(logs, target="temp") == {}

    def test_retained_points_are_not_evidence(self):
        logs = {"pressure": self._log([("2026-01-05", "Retained (analyst decision)")])}
        assert cross_flags(logs, target="temp") == {}

    def test_shared_removals_need_two_variables(self):
        logs = {
            "a": self._log([("d1", "Removed"), ("d2", "Removed")]),
            "b": self._log([("d1", "Removed")]),
        }
        shared = shared_removals(logs)
        assert set(shared) == {"d1"}
        assert shared["d1"] == ("a", "b")


# --------------------------------------------------------------------------
# verdicts
# --------------------------------------------------------------------------


class TestVerdicts:
    """Rescued from pages/04_capability.py and pages/05_audit_trail.py."""

    def test_over_pruning_is_called_out(self):
        # A step change midway: the grand mean falls in the gap, so every point
        # sits outside the limits and the analyst is tempted to prune heavily.
        # Removing 6 of 20 is a 30% rate - exactly what the heuristic catches.
        low = [100.0, 100.2, 99.8, 100.1, 99.9, 100.0, 100.2, 99.8, 100.1, 99.9]
        values = pd.Series(low + [v + 5 for v in low])

        first = run_phase_i_pass(values)
        to_remove = first.flagged_positions[:6]
        result = finalise(
            first, values,
            DecisionSet({p: Decision(p, True, "documented upset") for p in to_remove}),
        )

        assert result.removal_rate == pytest.approx(0.30)
        assert any("baseline period itself is suspect" in n for n in phase_i_verdicts(result))

    def test_clean_baseline_reads_as_in_control(self):
        stable = pd.Series([100.0 + (0.3 if i % 2 == 0 else -0.3) for i in range(30)])
        result = finalise(run_phase_i_pass(stable), stable, DecisionSet())
        assert any("in statistical control" in n for n in phase_i_verdicts(result))

    def test_small_baseline_is_flagged_as_provisional(self):
        short = pd.Series([100.0 + (0.3 if i % 2 == 0 else -0.3) for i in range(10)])
        result = finalise(run_phase_i_pass(short), short, DecisionSet())
        assert any("provisional" in n for n in phase_i_verdicts(result))

    def test_off_centre_process_is_diagnosed(self):
        rng = np.random.default_rng(7)
        s = pd.Series(rng.normal(104, 1, 200))  # spec centred on 100
        cap = compute_capability(s, 106.0, 94.0)
        assert any("off-centre" in n for n in capability_verdicts(cap))

    def test_out_of_control_data_gets_a_prominent_caveat(self, stable_series):
        cap = compute_capability(stable_series, 106.0, 94.0)
        notes = capability_verdicts(cap, in_control=False)
        assert "not in statistical control" in notes[0]

    def test_incapable_process_is_stated_plainly(self):
        rng = np.random.default_rng(11)
        s = pd.Series(rng.normal(100, 5, 200))
        cap = compute_capability(s, 102.0, 98.0)
        assert any("variation exceeds the tolerance band" in n for n in capability_verdicts(cap))


# --------------------------------------------------------------------------
# normality pre-check
# --------------------------------------------------------------------------


class TestPrecheck:
    def test_normal_data_passes(self, stable_series):
        check = normality_precheck(stable_series)
        assert check.passed is True
        assert "Shapiro-Wilk" in check.detail

    def test_skewed_data_fails(self):
        rng = np.random.default_rng(5)
        check = normality_precheck(pd.Series(rng.exponential(1.0, 300)))
        assert check.passed is False

    def test_too_few_points_is_inconclusive_not_a_failure(self):
        check = normality_precheck(pd.Series([1.0, 2.0]))
        assert check.passed is None


# --------------------------------------------------------------------------
# studio protocol
# --------------------------------------------------------------------------


class TestSpcCall:
    def test_evaluate_returns_a_chartable_payload(self, spc_frame):
        out = spc_call("evaluate", {"data": spc_frame, "column": "measurement", "orderColumn": "day"})
        assert out["nEvaluated"] == 50
        assert len(out["points"]) == 50
        assert out["anyViolations"] is True
        assert out["points"][25]["flagged"] is True
        assert out["points"][25]["label"] == "2026-01-26"
        assert out["limits"]["i_ucl"] > out["limits"]["i_cl"]
        assert out["normality"]["name"] == "Approximate normality"

    def test_evaluate_honours_exclusions(self, spc_frame):
        base = spc_call("evaluate", {"data": spc_frame, "column": "measurement"})
        trimmed = spc_call(
            "evaluate",
            {"data": spc_frame, "column": "measurement", "excluded": [25]},
        )
        assert trimmed["nEvaluated"] == base["nEvaluated"] - 1
        assert trimmed["nExcluded"] == 1
        assert trimmed["limits"]["sigma_within"] < base["limits"]["sigma_within"]

    def test_evaluate_without_a_label_column_numbers_rows(self, spc_frame):
        out = spc_call("evaluate", {"data": spc_frame, "column": "measurement"})
        assert out["points"][0]["label"] == "1"

    def test_certify_requires_a_cause(self, spc_frame):
        with pytest.raises(AssignableCauseRequired):
            spc_call("certify", {
                "data": spc_frame,
                "column": "measurement",
                "decisions": [{"position": 25, "remove": True, "cause": ""}],
            })

    def test_certify_returns_the_baseline_and_audit_log(self, spc_frame):
        out = spc_call("certify", {
            "data": spc_frame,
            "column": "measurement",
            "orderColumn": "day",
            "decisions": [{"position": 25, "remove": True, "cause": "Sensor fault"}],
        })
        assert out["nPasses"] == 2
        assert out["nRemoved"] == 1
        assert out["nFinal"] == 49
        assert out["removedSourceRows"] == [25]
        assert out["auditLog"]["columns"][1] == "observation"
        assert out["verdicts"]

    def test_capability_flags_an_out_of_control_process(self, spc_frame):
        out = spc_call("capability", {
            "data": spc_frame,
            "column": "measurement",
            "usl": 106.0,
            "lsl": 94.0,
        })
        assert out["inControl"] is False
        assert "not in statistical control" in out["verdicts"][0]
        assert out["capability"]["cp"] > 0

    def test_capability_needs_both_specs(self, spc_frame):
        with pytest.raises(DataError, match="USL and LSL"):
            spc_call("capability", {"data": spc_frame, "column": "measurement", "usl": 1.0})

    def test_cross_variable_reports_shared_removals(self, spc_frame):
        certified = spc_call("certify", {
            "data": spc_frame,
            "column": "measurement",
            "orderColumn": "day",
            "decisions": [{"position": 25, "remove": True, "cause": "Sensor fault"}],
        })
        out = spc_call("cross_variable", {
            "auditLogs": {"a": certified["auditLog"], "b": certified["auditLog"]}
        })
        assert out["shared"][0]["removedFrom"] == ["a", "b"]

    def test_unknown_operation_is_rejected(self):
        with pytest.raises(DataError, match="Unknown SPC operation"):
            spc_call("obliterate", {})

    def test_missing_column_is_a_data_error(self, spc_frame):
        with pytest.raises(DataError, match="not in the dataset"):
            spc_call("evaluate", {"data": spc_frame, "column": "nope"})

    def test_label_column_cannot_be_the_measurement(self, spc_frame):
        with pytest.raises(DataError, match="must differ"):
            spc_call("evaluate", {
                "data": spc_frame, "column": "measurement", "orderColumn": "measurement",
            })

    def test_payload_is_json_safe(self, spc_frame):
        import json

        out = spc_call("evaluate", {"data": spc_frame, "column": "measurement"})
        json.dumps(out)  # must not raise on numpy scalars or NaN
