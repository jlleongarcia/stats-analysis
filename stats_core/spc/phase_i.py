"""Phase I engine - analyst-driven two-pass baseline establishment.

Oakland's principle (J.S. Oakland, *Statistical Process Control*, Ch. 4-5;
Wheeler, *Understanding SPC*):

* Only common-cause variation should remain in the Phase I baseline.
* A point may be removed ONLY when an assignable cause is identified.
* The analyst - not the algorithm - decides whether a flagged point is a
  genuine special cause or natural common-cause variation.

Two functions carry the workflow, and both are **pure**:

:func:`run_phase_i_pass`
    Evaluate one pass and report what the rules flagged. Removes nothing.
:func:`finalise`
    Apply the analyst's rulings, run pass 2 if anything was removed, and
    return the certified baseline plus its audit log.

Why two passes rather than iterating to zero violations: Oakland (5.4) warns
that iterating produces "utopia limits" - each removal tightens the limits,
which exposes fresh violations, which triggers more removals, until the
baseline no longer describes the real process. Capping at two passes stops the
cascade. Violations still present after pass 2 are reported, not acted on.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from stats_core.spc.audit import DecisionSet, build_audit_log
from stats_core.spc.limits import bridging_mr_mask, compute_limits, compute_moving_range
from stats_core.spc.rules import RULE_COLUMNS, apply_all_rules, apply_mr_rules


@dataclass
class PassResult:
    """One Phase I evaluation pass.

    Everything is addressed by integer position (0..n-1) into ``values``, which
    stays unambiguous when observation labels repeat. ``original_labels[i]`` is
    the display label for ``values.iloc[i]``, and ``original_positions[i]`` is
    that row's position in the *input* series - the duplicate-safe handle used
    when actually removing points.
    """

    values: pd.Series                     # retained measurements, RangeIndex
    mr: pd.Series                         # moving range, first entry NaN
    limits: dict[str, float]
    individual_violations: pd.DataFrame   # rule1..rule4 + any_violation
    mr_violations: pd.Series              # bool
    original_labels: pd.Index
    original_positions: np.ndarray
    n_original: int
    rule_config: dict[str, int]

    @property
    def any_violations(self) -> bool:
        return (
            bool(self.individual_violations["any_violation"].any())
            or bool(self.mr_violations.any())
        )

    @property
    def flagged_positions(self) -> list[int]:
        """Ascending integer positions of every flagged point (I or MR chart)."""
        combined = (
            self.individual_violations["any_violation"].to_numpy(dtype=bool)
            | self.mr_violations.to_numpy(dtype=bool)
        )
        return [int(i) for i in np.flatnonzero(combined)]


@dataclass
class PhaseIResult:
    """The certified baseline, after the analyst's decisions are applied."""

    final_values: pd.Series
    final_mr: pd.Series
    final_limits: dict[str, float]
    final_violations: pd.DataFrame
    final_mr_violations: pd.Series
    original_labels: pd.Index
    n_original: int
    n_final: int
    n_removed: int
    rule_config: dict[str, int]
    audit_log: pd.DataFrame
    n_passes: int
    final_pass_has_violations: bool

    @property
    def removal_rate(self) -> float:
        """Fraction of the original observations removed, 0..1."""
        return self.n_removed / self.n_original if self.n_original else 0.0


def run_phase_i_pass(
    values: pd.Series,
    *,
    mr_mask: "np.ndarray | None" = None,
    rule2_k: int = 2,
    rule2_window: int = 3,
    rule3_k: int = 8,
    rule4_k: int = 6,
) -> PassResult:
    """Evaluate one Phase I pass.

    Pure: *values* is never modified, and nothing is removed. Deciding what to
    remove belongs to the analyst, who must document an assignable cause first.

    Parameters
    ----------
    values:
        Time-ordered individual measurements. NaN entries are dropped; the
        original index is preserved as display labels.
    mr_mask:
        Passed through to :func:`~stats_core.spc.limits.compute_limits` to keep
        bridging moving ranges out of ``mr_bar``. :func:`finalise` builds this
        for pass 2 automatically.
    """
    rule_config = {
        "rule2_k": int(rule2_k),
        "rule2_window": int(rule2_window),
        "rule3_k": int(rule3_k),
        "rule4_k": int(rule4_k),
    }

    # Drop NaNs, remembering where each survivor came from, then reset to a
    # RangeIndex so the rules never have to care about the index type.
    keep = values.notna().to_numpy()
    original_labels: pd.Index = values.index[keep]
    original_positions: np.ndarray = np.flatnonzero(keep)
    clean = values.iloc[original_positions].reset_index(drop=True)
    n_original = len(clean)

    if n_original < 2:
        raise ValueError("At least 2 non-NaN observations are required.")

    limits = compute_limits(clean, mr_mask=mr_mask)
    mr = compute_moving_range(clean)

    return PassResult(
        values=clean,
        mr=mr,
        limits=limits,
        individual_violations=apply_all_rules(clean, limits, **rule_config),
        mr_violations=apply_mr_rules(
            mr, limits["mr_ucl"], limits["mr_uwl"],
            rule2_k=rule_config["rule2_k"], rule2_window=rule_config["rule2_window"],
        ),
        original_labels=original_labels,
        original_positions=original_positions,
        n_original=n_original,
        rule_config=rule_config,
    )


def finalise(
    first_pass: PassResult,
    values: pd.Series,
    decisions: "DecisionSet | None" = None,
) -> PhaseIResult:
    """Apply the analyst's rulings and certify the baseline.

    With no removals the pass-1 limits stand as the baseline. With removals, the
    points come out and pass 2 recomputes the limits on what remains - using a
    bridging mask so ``sigma_within`` still comes only from originally-adjacent
    pairs. Pass 2 is final either way; remaining violations are reported rather
    than pruned.

    Parameters
    ----------
    first_pass:
        The :class:`PassResult` the analyst reviewed.
    values:
        The same series that was fed to :func:`run_phase_i_pass`.
    decisions:
        The analyst's rulings. Validated first - a removal without a documented
        assignable cause raises
        :class:`~stats_core.spc.audit.AssignableCauseRequired`.
    """
    decisions = decisions or DecisionSet()
    decisions.validate(first_pass.original_labels)

    audit_log = build_audit_log(first_pass, decisions, pass_number=1)
    to_remove = decisions.positions_to_remove

    if not to_remove:
        return PhaseIResult(
            final_values=first_pass.values,
            final_mr=first_pass.mr,
            final_limits=first_pass.limits,
            final_violations=first_pass.individual_violations,
            final_mr_violations=first_pass.mr_violations,
            original_labels=first_pass.original_labels,
            n_original=first_pass.n_original,
            n_final=first_pass.n_original,
            n_removed=0,
            rule_config=first_pass.rule_config,
            audit_log=audit_log,
            n_passes=1,
            final_pass_has_violations=first_pass.any_violations,
        )

    # Remove by position in the *input* series: labels may repeat, positions
    # never do.
    removed = set(to_remove)
    drop_positions = {int(first_pass.original_positions[p]) for p in removed}
    keep_rows = np.array(
        [i not in drop_positions for i in range(len(values))], dtype=bool
    )
    survivors = values.iloc[keep_rows]

    kept_ranks = [r for r in range(first_pass.n_original) if r not in removed]
    mr_mask = bridging_mr_mask(kept_ranks)

    second_pass = run_phase_i_pass(survivors, mr_mask=mr_mask, **first_pass.rule_config)

    return PhaseIResult(
        final_values=second_pass.values,
        final_mr=second_pass.mr,
        final_limits=second_pass.limits,
        final_violations=second_pass.individual_violations,
        final_mr_violations=second_pass.mr_violations,
        original_labels=second_pass.original_labels,
        n_original=first_pass.n_original,
        n_final=second_pass.n_original,
        n_removed=len(to_remove),
        rule_config=first_pass.rule_config,
        audit_log=audit_log,
        n_passes=2,
        final_pass_has_violations=second_pass.any_violations,
    )


def control_lines_table(limits: dict[str, float]) -> pd.DataFrame:
    """The control lines as a display table, in top-to-bottom chart order."""
    return pd.DataFrame(
        {
            "chart": ["I"] * 5 + ["MR"] * 3,
            "line": [
                "UAL (action)", "UWL (warning)", "CL (x-bar)",
                "LWL (warning)", "LAL (action)",
                "UAL (action)", "CL (MR-bar)", "LAL",
            ],
            "value": [
                limits["i_ucl"], limits["i_uwl"], limits["i_cl"],
                limits["i_lwl"], limits["i_lcl"],
                limits["mr_ucl"], limits["mr_cl"], limits["mr_lcl"],
            ],
        }
    )


__all__ = [
    "PassResult",
    "PhaseIResult",
    "run_phase_i_pass",
    "finalise",
    "control_lines_table",
    "RULE_COLUMNS",
]
