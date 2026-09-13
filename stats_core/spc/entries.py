"""Registry-facing SPC entries: the stateless half of the subpackage.

These two functions obey the ordinary ``func(frame, roles, params) -> TestResult``
contract, so they appear on the Analyze page alongside every other test. They
answer "show me the chart" and "what are the indices" in one shot.

What they deliberately do **not** do is establish a Phase I baseline. That needs
an analyst ruling on each flagged point with a documented assignable cause, and
it cannot be expressed as a one-shot test without either removing points
automatically or smuggling state through ``params``. The SPC Studio owns that
workflow; both functions say so in their notes rather than letting a user
mistake a raw chart for a certified baseline.
"""

from __future__ import annotations

import pandas as pd

from stats_core._util import DataError
from stats_core.results import ResultTable, TestResult
from stats_core.spc.capability import compute_capability
from stats_core.spc.charts import control_chart_specs
from stats_core.spc.phase_i import control_lines_table, run_phase_i_pass
from stats_core.spc.precheck import normality_precheck
from stats_core.spc.rules import DEFAULT_RULE_CONFIG, RULE_LABELS, rules_fired
from stats_core.spc.verdicts import capability_verdicts

_NOT_A_BASELINE = (
    "This is a chart of the data as supplied, not a certified Phase I baseline. "
    "Control limits computed from a process that was not stable are wider than "
    "the process truly warrants. Use the SPC Studio to review each flagged point "
    "and document an assignable cause before treating these limits as a baseline."
)


def _ordered_series(frame: pd.DataFrame, roles: dict) -> pd.Series:
    """The measurement column, indexed by its observation labels.

    Row order as supplied *is* the time axis - an SPC chart is meaningless
    without it. The optional ``order`` role only supplies display labels; it
    never re-sorts, because sorting by a label column would silently rewrite the
    sequence the moving ranges are computed from.
    """
    column = roles.get("values")
    if not column:
        raise DataError("Select the measurement column to chart.")
    if column not in frame.columns:
        raise DataError(f"Column {column!r} is not in the dataset.")

    values = pd.to_numeric(frame[column], errors="coerce")
    if values.notna().sum() < 2:
        raise DataError(f"Column {column!r} has fewer than 2 numeric values.")

    order_column = roles.get("order")
    if order_column:
        if order_column not in frame.columns:
            raise DataError(f"Column {order_column!r} is not in the dataset.")
        if order_column == column:
            raise DataError(
                "The observation label and the measurement must be different "
                "columns - a measurement cannot also be its own label."
            )
        values.index = pd.Index(frame[order_column].astype(str), name=order_column)
    else:
        values.index = pd.Index(
            [str(i) for i in range(1, len(frame) + 1)], name="Observation"
        )
    return values


def _rule_params(params: dict) -> dict[str, int]:
    return {key: int(params.get(key, default)) for key, default in DEFAULT_RULE_CONFIG.items()}


def control_chart_imr(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    """Individuals and Moving Range chart with rule violations flagged."""
    column = roles["values"]
    values = _ordered_series(frame, roles)
    rule_config = _rule_params(params)

    result = run_phase_i_pass(values, **rule_config)
    flagged = result.flagged_positions

    violations = ResultTable(
        title="Flagged points",
        columns=["observation", "value", "moving range", "rules fired"],
        rows=[],
    )
    for position in flagged:
        mr_value = result.mr.iloc[position]
        violations.rows.append(
            [
                str(result.original_labels[position]),
                float(result.values.iloc[position]),
                None if pd.isna(mr_value) else float(mr_value),
                ", ".join(
                    RULE_LABELS.get(name, name)
                    for name in rules_fired(
                        result.individual_violations, result.mr_violations, position
                    )
                ),
            ]
        )

    lines = control_lines_table(result.limits)
    limits = result.limits
    n_flagged = len(flagged)

    out = TestResult(
        test_id="control_chart_imr",
        test_name="Control chart (Individuals & Moving Range)",
        summary=(
            f"{column}: {result.n_original} observations, centre line "
            f"{limits['i_cl']:.4g}, action limits {limits['i_lcl']:.4g} to "
            f"{limits['i_ucl']:.4g}. "
            + (
                "No rule violations - the process appears to be in statistical control."
                if n_flagged == 0
                else f"{n_flagged} point(s) flagged by at least one rule."
            )
        ),
        statistic={
            "n": float(result.n_original),
            "x_bar": limits["x_bar"],
            "mr_bar": limits["mr_bar"],
            "sigma_within": limits["sigma_within"],
            "UAL": limits["i_ucl"],
            "LAL": limits["i_lcl"],
            "flagged": float(n_flagged),
        },
        assumptions=[normality_precheck(result.values)],
        tables=[
            ResultTable(
                title="Control lines",
                columns=[str(c) for c in lines.columns],
                rows=lines.to_dict(orient="split")["data"],
            )
        ],
        plot_specs=control_chart_specs(result, column),
    )

    if violations.rows:
        out.tables.append(violations)

    out.add_note(_NOT_A_BASELINE)
    if n_flagged:
        out.add_note(
            "A flagged point is a candidate for investigation, not proof of a "
            "special cause. Removing points without a documented process reason "
            "produces artificially tight limits."
        )
    return out


def process_capability(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    """Cp, Cpk, Pp and Ppk against a pair of specification limits."""
    column = roles["values"]
    values = _ordered_series(frame, roles)
    rule_config = _rule_params(params)

    usl, lsl = params.get("usl"), params.get("lsl")
    if usl is None or lsl is None:
        raise DataError("Both the upper and lower specification limits are required.")
    usl, lsl = float(usl), float(lsl)
    if usl <= lsl:
        raise DataError("The upper specification limit must be greater than the lower.")

    # The moving ranges that give sigma_within depend on the sequence, so the
    # chart pass is what defines them - and it also tells us whether the process
    # was stable enough for these indices to mean anything.
    result = run_phase_i_pass(values, **rule_config)
    in_control = not result.any_violations
    cap = compute_capability(result.values, usl, lsl, mr_bar=result.limits["mr_bar"])

    indices = ResultTable(
        title="Capability indices",
        columns=["index", "value", "based on", "meaning"],
        rows=[
            ["Cp", cap["cp"], "sigma within", "Potential capability - spread only"],
            ["Cpk", cap["cpk"], "sigma within", "Potential capability - spread and centring"],
            ["Pp", cap["pp"], "sigma overall", "Actual performance - spread only"],
            ["Ppk", cap["ppk"], "sigma overall", "Actual performance - spread and centring"],
            ["RPI", cap["rpi"], "sigma within", "Relative precision index (equals Cp)"],
        ],
    )

    out = TestResult(
        test_id="process_capability",
        test_name="Process capability (Cp, Cpk, Pp, Ppk)",
        summary=(
            f"{column}: Cp = {cap['cp']:.3f}, Cpk = {cap['cpk']:.3f}, "
            f"Pp = {cap['pp']:.3f}, Ppk = {cap['ppk']:.3f} against "
            f"specification limits {lsl:g} to {usl:g}."
        ),
        statistic={
            "Cp": cap["cp"],
            "Cpk": cap["cpk"],
            "Pp": cap["pp"],
            "Ppk": cap["ppk"],
            "x_bar": cap["x_bar"],
            "sigma_within": cap["sigma_within"],
            "sigma_overall": cap["sigma_overall"],
        },
        assumptions=[normality_precheck(result.values)],
        tables=[indices],
        plot_specs=[
            {
                "kind": "histogram",
                "data": {"x": [float(v) for v in result.values]},
                "encoding": {"x": {"field": "x", "title": column}},
                "overlay": "normal",
                "rules": [
                    {"value": lsl, "label": "LSL", "kind": "spec"},
                    {"value": usl, "label": "USL", "kind": "spec"},
                    {"value": cap["x_bar"], "label": "mean", "kind": "centre"},
                ],
            }
        ],
    )

    for note in capability_verdicts(cap, in_control=in_control):
        out.add_note(note)
    if not in_control:
        out.add_note(_NOT_A_BASELINE)
    return out


__all__ = ["control_chart_imr", "process_capability"]
