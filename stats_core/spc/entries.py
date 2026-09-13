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
from stats_core.spc.capability import (
    compute_capability, compute_cpm, cpk_confidence_interval, percentile_capability,
    transform_to_normal,
)
from stats_core.spc.attributes import (
    c_chart, np_chart, p_chart, small_count_warning, u_chart,
)
from stats_core.spc.charts import (
    attribute_chart_specs, control_chart_specs, subgroup_chart_specs,
)
from stats_core.spc.phase_i import control_lines_table, run_phase_i_pass
from stats_core.spc.precheck import normality_precheck
from stats_core.spc.rules import (
    DEFAULT_RULE_CONFIG, RULE_LABELS, apply_all_rules, apply_spread_rules, rules_fired,
)
from stats_core.spc.rulesets import RULE_SETS, apply_rule_set, rule_labels
from stats_core.spc.subgroups import build_subgroups, xbar_r_limits, xbar_s_limits
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

    rule_set = str(params.get("rule_set", "oakland"))
    if rule_set not in RULE_SETS:
        raise DataError(
            f"Unknown rule set {rule_set!r}; choose one of {', '.join(RULE_SETS)}."
        )
    if rule_set != "oakland":
        # Oakland's four support configurable thresholds and live in rules.py;
        # the named sets are fixed by their standards, so they replace the
        # individuals-chart flags wholesale. MR-chart rules are unaffected.
        result.individual_violations = apply_rule_set(result.values, result.limits, rule_set)
        RULE_LABELS.update(rule_labels(rule_set))

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

    normality = normality_precheck(result.values)
    method = str(params.get("method", "normal"))
    extras: list[list] = []

    # Cpk is a point estimate from a sample; at typical SPC sample sizes it is
    # far less precise than three decimals suggest.
    lo, hi = cpk_confidence_interval(cap["cpk"], result.n_original)
    if lo == lo:  # not NaN
        extras.append(["Cpk 95% CI", f"{lo:.3f} to {hi:.3f}",
                       "sigma within", "Interval estimate (Bissell, 1990)"])

    target = params.get("target")
    if target is not None:
        cpm = compute_cpm(result.values, usl, lsl, float(target))
        extras.append(["Cpm", cpm, "sigma overall + offset",
                       f"Taguchi index against target {float(target):g}"])

    if method == "percentile":
        pc = percentile_capability(result.values, usl, lsl)
        extras.append(["Pp (percentile)", pc["pp_percentile"], "observed spread",
                       "ISO 22514-2, no normality assumption"])
        extras.append(["Ppk (percentile)", pc["ppk_percentile"], "observed spread",
                       "ISO 22514-2, no normality assumption"])
    elif method == "boxcox":
        t = transform_to_normal(result.values)
        extras.append(["Box-Cox lambda", t["lambda"], "transform",
                       f"Shapiro-Wilk p {t['p_before']:.2e} -> {t['p_after']:.3f}"])

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

    indices.rows.extend(extras)

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
        assumptions=[normality],
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
    if normality.passed is False and method == "normal":
        out.add_note(
            "The data is not normal, and Cp/Cpk convert a sigma into a tail "
            "probability - on skewed data that conversion is wrong, usually "
            "optimistic, because the long tail is the side producing defects. "
            "Re-run with the percentile method (ISO 22514-2, distribution-free) "
            "or Box-Cox to see how much it matters."
        )
    if not in_control:
        out.add_note(_NOT_A_BASELINE)
    return out


__all__ = [
    "control_chart_imr",
    "process_capability",
    "control_chart_xbar_r",
    "control_chart_xbar_s",
    "control_chart_p",
    "control_chart_np",
    "control_chart_c",
    "control_chart_u",
    "control_chart_phase_ii",
]


def _subgroup_chart(
    frame: pd.DataFrame, roles: dict, params: dict, *, variant: str
) -> TestResult:
    """Shared body for the X-bar/R and X-bar/S entries."""
    column = roles["values"]
    values = _ordered_series(frame, roles)
    rule_config = _rule_params(params)

    group_column = roles.get("subgroup")
    groups = None
    if group_column:
        if group_column not in frame.columns:
            raise DataError(f"Column {group_column!r} is not in the dataset.")
        if group_column == column:
            raise DataError("The subgroup column and the measurement must differ.")
        groups = pd.Series(frame[group_column].to_numpy(), index=values.index,
                           name=group_column)

    size = params.get("subgroup_size")
    sub = build_subgroups(
        values,
        groups=groups,
        size=None if groups is not None else int(size or 5),
    )

    is_range = variant == "r"
    limits = xbar_r_limits(sub) if is_range else xbar_s_limits(sub)
    key = "r" if is_range else "s"
    spread = sub.ranges if is_range else sub.sds

    mean_violations = apply_all_rules(sub.means, limits, **rule_config)
    spread_violations = apply_spread_rules(
        spread, limits[f"{key}_ucl"], limits[f"{key}_lcl"], limits[f"{key}_uwl"],
        rule2_k=rule_config["rule2_k"], rule2_window=rule_config["rule2_window"],
    )

    flagged = [
        i for i in range(sub.n_subgroups)
        if bool(mean_violations["any_violation"].iloc[i]) or bool(spread_violations.iloc[i])
    ]

    violations = ResultTable(
        title="Flagged subgroups",
        columns=["subgroup", "mean", "range" if is_range else "sd", "rules fired"],
        rows=[],
    )
    for position in flagged:
        fired = [
            RULE_LABELS.get(name, name) for name in ("rule1", "rule2", "rule3", "rule4")
            if bool(mean_violations.iloc[position][name])
        ]
        if bool(spread_violations.iloc[position]):
            fired.append(
                "Range chart - outside limits" if is_range
                else "S chart - outside limits"
            )
        violations.rows.append([
            str(sub.labels[position]),
            float(sub.means.iloc[position]),
            float(spread.iloc[position]),
            ", ".join(fired),
        ])

    spread_label = "R" if is_range else "S"
    out = TestResult(
        test_id=f"control_chart_xbar_{key}",
        test_name=f"Control chart (X-bar & {spread_label})",
        summary=(
            f"{column}: {sub.n_subgroups} subgroups of {sub.size}, grand mean "
            f"{limits['i_cl']:.4g}, action limits {limits['i_lcl']:.4g} to "
            f"{limits['i_ucl']:.4g}. "
            + ("No rule violations." if not flagged
               else f"{len(flagged)} subgroup(s) flagged.")
        ),
        statistic={
            "subgroups": float(sub.n_subgroups),
            "subgroup_size": float(sub.size),
            "grand_mean": limits["i_cl"],
            f"{key}_bar": limits[f"{key}_bar"],
            "sigma_within": limits["sigma_within"],
            "UAL": limits["i_ucl"],
            "LAL": limits["i_lcl"],
            "flagged": float(len(flagged)),
        },
        assumptions=[normality_precheck(sub.means)],
        plot_specs=subgroup_chart_specs(
            sub=sub, limits=limits, mean_violations=mean_violations,
            spread_violations=spread_violations, spread_key=key, column=column,
        ),
    )
    if violations.rows:
        out.tables.append(violations)

    if sub.n_dropped:
        out.add_note(
            f"{sub.n_dropped} trailing observation(s) did not fill a complete "
            f"subgroup of {sub.size} and were excluded. Shewhart constants are "
            "defined per subgroup size, so a partial subgroup cannot be charted."
        )
    if is_range and sub.size >= 9:
        out.add_note(
            f"At subgroup size {sub.size} the range uses only the two most "
            "extreme values and loses efficiency. An X-bar/S chart estimates "
            "sigma from every observation and is the better choice here."
        )
    out.add_note(_NOT_A_BASELINE)
    return out


def control_chart_xbar_r(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    """X-bar and R chart for subgrouped measurements."""
    return _subgroup_chart(frame, roles, params, variant="r")


def control_chart_xbar_s(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    """X-bar and S chart for subgrouped measurements."""
    return _subgroup_chart(frame, roles, params, variant="s")


_ATTRIBUTE_HELP = {
    "p": ("Proportion defective", "defective units", True),
    "np": ("Number defective", "defective units", True),
    "c": ("Defect count", "defects found", False),
    "u": ("Defects per unit", "defects found", True),
}


def _attribute_chart(frame: pd.DataFrame, roles: dict, params: dict, *, kind: str) -> TestResult:
    """Shared body for the p, np, c and u entries."""
    count_column = roles["values"]
    if count_column not in frame.columns:
        raise DataError(f"Column {count_column!r} is not in the dataset.")
    counts = pd.to_numeric(frame[count_column], errors="coerce")

    size_column = roles.get("size")
    sizes = None
    if size_column:
        if size_column not in frame.columns:
            raise DataError(f"Column {size_column!r} is not in the dataset.")
        if size_column == count_column:
            raise DataError("The count column and the sample-size column must differ.")
        sizes = pd.to_numeric(frame[size_column], errors="coerce")
    elif kind != "c":
        raise DataError(
            f"A {kind} chart needs a sample-size column - the count only means "
            "something relative to how many units were inspected."
        )

    label_column = roles.get("order")
    labels = None
    if label_column:
        if label_column not in frame.columns:
            raise DataError(f"Column {label_column!r} is not in the dataset.")
        labels = frame[label_column].astype(str)
        if sizes is not None:
            keep = counts.notna() & sizes.notna() & (sizes > 0)
        else:
            keep = counts.notna()
        labels = labels[keep]

    if kind == "p":
        chart = p_chart(counts, sizes, labels)
    elif kind == "np":
        chart = np_chart(counts, sizes, labels)
    elif kind == "c":
        chart = c_chart(counts, labels)
    else:
        chart = u_chart(counts, sizes, labels)

    violations = chart.violations
    flagged = [i for i in range(chart.n_points) if bool(violations.iloc[i])]

    table = ResultTable(
        title="Flagged samples",
        columns=["sample", "value", "sample size", "limit breached"],
        rows=[
            [
                str(chart.labels[i]),
                float(chart.values.iloc[i]),
                float(chart.sizes.iloc[i]),
                "above UAL" if chart.values.iloc[i] > chart.ucl.iloc[i] else "below LAL",
            ]
            for i in flagged
        ],
    )

    out = TestResult(
        test_id=f"control_chart_{kind}",
        test_name=f"Attribute control chart ({kind})",
        summary=(
            f"{count_column}: {chart.n_points} samples, centre line "
            f"{chart.centre:.4g}. "
            + ("No samples outside the limits." if not flagged
               else f"{len(flagged)} sample(s) outside the limits.")
        ),
        statistic={
            "samples": float(chart.n_points),
            "centre": float(chart.centre),
            "total_counted": float(chart.values.mul(chart.sizes).sum())
            if kind in ("p", "u") else float(chart.values.sum()),
            "flagged": float(len(flagged)),
        },
        plot_specs=attribute_chart_specs(chart, column=count_column, violations=violations),
    )
    if table.rows:
        out.tables.append(table)

    if not chart.constant_limits:
        out.add_note(
            "Sample sizes vary, so the control limits vary with them and are "
            "drawn as a stepped boundary. A proportion from a large sample is "
            "far better determined than one from a small sample, and constant "
            "limits would flag the small samples relentlessly."
        )
    warning = small_count_warning(chart)
    if warning:
        out.add_note(warning)
    out.add_note(_NOT_A_BASELINE)
    return out


def control_chart_p(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    """p chart - proportion defective."""
    return _attribute_chart(frame, roles, params, kind="p")


def control_chart_np(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    """np chart - number defective, constant sample size."""
    return _attribute_chart(frame, roles, params, kind="np")


def control_chart_c(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    """c chart - defect count per constant inspection unit."""
    return _attribute_chart(frame, roles, params, kind="c")


def control_chart_u(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    """u chart - defects per unit with a varying inspected amount."""
    return _attribute_chart(frame, roles, params, kind="u")


def control_chart_phase_ii(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    """Phase II: plot new data against a frozen baseline.

    Phase I asks "was this process stable, and what are its limits?". Phase II
    asks the different question "is it *still* behaving like that baseline?" -
    and it must never recompute the limits from the new data, or a process that
    has drifted will simply redraw its limits around the drift and look fine.

    So the limits come in as parameters, from a certified Phase I study, and are
    applied unchanged.
    """
    column = roles["values"]
    values = _ordered_series(frame, roles)
    rule_config = _rule_params(params)

    centre = params.get("center")
    sigma = params.get("sigma_within")
    if centre is None or sigma is None:
        raise DataError(
            "Phase II needs the centre line and sigma from a certified Phase I "
            "baseline. Run a Phase I study in the SPC Studio first - its "
            "certified baseline reports both."
        )
    centre, sigma = float(centre), float(sigma)
    if sigma <= 0:
        raise DataError("Sigma must be greater than zero.")

    clean = values.dropna()
    if len(clean) < 1:
        raise DataError(f"Column {column!r} has no numeric values to monitor.")

    limits = {
        "i_cl": centre,
        "i_ucl": centre + 3 * sigma,
        "i_uwl": centre + 2 * sigma,
        "i_lwl": centre - 2 * sigma,
        "i_lcl": centre - 3 * sigma,
        "sigma_within": sigma,
    }

    rule_set = str(params.get("rule_set", "oakland"))
    if rule_set not in RULE_SETS:
        raise DataError(f"Unknown rule set {rule_set!r}; choose one of {', '.join(RULE_SETS)}.")
    if rule_set == "oakland":
        violations = apply_all_rules(clean.reset_index(drop=True), limits, **rule_config)
    else:
        violations = apply_rule_set(clean.reset_index(drop=True), limits, rule_set)
        RULE_LABELS.update(rule_labels(rule_set))

    labels = [str(v) for v in clean.index]
    statuses, fired_text = [], []
    for i in range(len(clean)):
        fired = [
            RULE_LABELS.get(name, name)
            for name in violations.columns
            if name != "any_violation" and bool(violations.iloc[i][name])
        ]
        statuses.append("violation" if fired else "in control")
        fired_text.append("; ".join(fired))

    n_flagged = int(violations["any_violation"].sum())
    out_of_limits = int(((clean > limits["i_ucl"]) | (clean < limits["i_lcl"])).sum())
    shift = (float(clean.mean()) - centre) / sigma

    table = ResultTable(
        title="Flagged observations",
        columns=["observation", "value", "rules fired"],
        rows=[
            [labels[i], float(clean.iloc[i]), fired_text[i]]
            for i in range(len(clean)) if statuses[i] == "violation"
        ],
    )

    out = TestResult(
        test_id="control_chart_phase_ii",
        test_name="Phase II monitoring (frozen baseline)",
        summary=(
            f"{column}: {len(clean)} new observations against a baseline centred "
            f"on {centre:.4g} with sigma {sigma:.4g}. "
            + ("All within the baseline limits." if n_flagged == 0
               else f"{n_flagged} observation(s) flagged, {out_of_limits} beyond the action limits.")
        ),
        statistic={
            "n": float(len(clean)),
            "baseline_centre": centre,
            "baseline_sigma": sigma,
            "new_mean": float(clean.mean()),
            "shift_in_sigma": float(shift),
            "flagged": float(n_flagged),
        },
        plot_specs=[{
            "kind": "controlChart",
            "panel": "individuals",
            "title": f"Phase II - {column} against the frozen baseline",
            "data": {"x": labels, "y": [float(v) for v in clean],
                     "status": statuses, "rules": fired_text},
            "lines": [
                {"value": limits["i_ucl"], "label": "UAL", "kind": "action"},
                {"value": limits["i_uwl"], "label": "UWL", "kind": "warning"},
                {"value": limits["i_cl"], "label": "CL", "kind": "centre"},
                {"value": limits["i_lwl"], "label": "LWL", "kind": "warning"},
                {"value": limits["i_lcl"], "label": "LAL", "kind": "action"},
            ],
            "bands": [
                {"from": limits["i_uwl"], "to": limits["i_ucl"], "kind": "warning"},
                {"from": limits["i_lcl"], "to": limits["i_lwl"], "kind": "warning"},
            ],
            "encoding": {"x": {"field": "x", "title": str(clean.index.name or "Observation")},
                         "y": {"field": "y", "title": column}},
        }],
    )
    if table.rows:
        out.tables.append(table)

    out.add_note(
        "These limits come from the baseline and are NOT recomputed from this "
        "data. That is the whole point: a process that has drifted would "
        "otherwise redraw its limits around the drift and appear in control."
    )
    if abs(shift) > 1:
        out.add_note(
            f"The new mean sits {shift:+.2f} sigma from the baseline centre. A "
            "sustained shift of this size means the baseline no longer describes "
            "the process - investigate, then re-establish it."
        )
    return out
