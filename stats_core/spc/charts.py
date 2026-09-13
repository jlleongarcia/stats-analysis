"""Vega-Lite payloads for control charts.

Shared by the registry entries (Analyze page) and the Studio protocol, so both
render the identical chart from the identical code. Which lines and shaded zones
each panel carries is SPC domain knowledge and belongs here, under test - the
TypeScript renderer only maps a line's ``kind`` to a colour and dash pattern.
"""

from __future__ import annotations

import pandas as pd

from stats_core.spc.rules import RULE_COLUMNS, RULE_LABELS, rules_fired

__all__ = ["control_chart_specs", "subgroup_chart_specs"]


def control_chart_specs(result, column: str) -> list[dict]:
    """Build the two ``controlChart`` payloads: individuals, then moving range.

    Two specs rather than one vertically concatenated pair, because Vega-Lite's
    responsive ``width: "container"`` is not supported inside ``vconcat`` - and a
    control chart that cannot fill its panel is worse than one that is not
    pixel-aligned with the chart below it.

    Which lines and shaded zones each panel carries is decided here rather than
    in the renderer: it is SPC domain knowledge, and it is covered by tests.
    """
    labels = [str(label) for label in result.original_labels]
    values = [float(v) for v in result.values]

    statuses: list[str] = []
    rule_text: list[str] = []
    for position in range(result.n_original):
        fired = rules_fired(result.individual_violations, result.mr_violations, position)
        statuses.append("violation" if fired else "in control")
        rule_text.append("; ".join(RULE_LABELS.get(name, name) for name in fired))

    mr_labels: list[str] = []
    mr_values: list[float] = []
    mr_status: list[str] = []
    for position in range(1, result.n_original):
        mr_value = result.mr.iloc[position]
        if pd.isna(mr_value):
            continue
        mr_labels.append(labels[position])
        mr_values.append(float(mr_value))
        mr_status.append(
            "violation" if bool(result.mr_violations.iloc[position]) else "in control"
        )

    limits = result.limits
    x_title = str(result.original_labels.name or "Observation")

    def line(value: float, label: str, kind: str) -> dict:
        return {"value": float(value), "label": label, "kind": kind}

    def band(low: float, high: float, kind: str) -> dict:
        return {"from": float(low), "to": float(high), "kind": kind}

    individuals = {
        "kind": "controlChart",
        "panel": "individuals",
        "title": f"Individuals chart - {column}",
        "data": {"x": labels, "y": values, "status": statuses, "rules": rule_text},
        "lines": [
            line(limits["i_ucl"], "UAL", "action"),
            line(limits["i_uwl"], "UWL", "warning"),
            line(limits["i_cl"], "CL", "centre"),
            line(limits["i_lwl"], "LWL", "warning"),
            line(limits["i_lcl"], "LAL", "action"),
        ],
        # Only the 2-3 sigma warning zones are shaded. Shading the centre band
        # too was tried and discarded: on a dark ground the two tints are barely
        # tellable apart, so the second band added noise without adding meaning.
        "bands": [
            band(limits["i_uwl"], limits["i_ucl"], "warning"),
            band(limits["i_lcl"], limits["i_lwl"], "warning"),
        ],
        "encoding": {"x": {"field": "x", "title": x_title}, "y": {"field": "y", "title": column}},
    }

    moving_range = {
        "kind": "controlChart",
        "panel": "movingRange",
        "title": f"Moving range chart - {column}",
        "data": {"x": mr_labels, "y": mr_values, "status": mr_status},
        "lines": [
            line(limits["mr_ucl"], "UAL", "action"),
            line(limits["mr_uwl"], "UWL", "warning"),
            line(limits["mr_cl"], "CL", "centre"),
        ],
        "bands": [band(limits["mr_uwl"], limits["mr_ucl"], "warning")],
        "encoding": {
            "x": {"field": "x", "title": x_title},
            "y": {"field": "y", "title": "moving range"},
        },
    }

    return [individuals, moving_range]


def _panel(
    *,
    panel: str,
    title: str,
    labels: list[str],
    values: list[float],
    statuses: list[str],
    lines: list[dict],
    bands: list[dict],
    x_title: str,
    y_title: str,
    rules: "list[str] | None" = None,
) -> dict:
    """One layered chart panel in the shape the TypeScript renderer expects."""
    data: dict[str, list] = {"x": labels, "y": values, "status": statuses}
    if rules is not None:
        data["rules"] = rules
    return {
        "kind": "controlChart",
        "panel": panel,
        "title": title,
        "data": data,
        "lines": lines,
        "bands": bands,
        "encoding": {
            "x": {"field": "x", "title": x_title},
            "y": {"field": "y", "title": y_title},
        },
    }


def subgroup_chart_specs(
    *,
    sub,
    limits: dict[str, float],
    mean_violations,
    spread_violations,
    spread_key: str,
    column: str,
) -> list[dict]:
    """Charts for an X-bar/R or X-bar/S pair.

    ``spread_key`` is ``"r"`` or ``"s"``; the limit dictionary uses that prefix
    for the spread chart's lines, while the means chart reuses the ``i_*`` keys
    so the shared rule code needs no special case.
    """
    labels = [str(label) for label in sub.labels]
    spread = sub.ranges if spread_key == "r" else sub.sds
    spread_name = "range" if spread_key == "r" else "standard deviation"

    mean_status, mean_rules = [], []
    for position in range(sub.n_subgroups):
        fired = [
            RULE_LABELS.get(name, name)
            for name in RULE_COLUMNS
            if bool(mean_violations.iloc[position][name])
        ]
        mean_status.append("violation" if fired else "in control")
        mean_rules.append("; ".join(fired))

    def line(value: float, label: str, kind: str) -> dict:
        return {"value": float(value), "label": label, "kind": kind}

    def band(low: float, high: float) -> dict:
        return {"from": float(low), "to": float(high), "kind": "warning"}

    means_panel = _panel(
        panel="individuals",
        title=f"X-bar chart - {column} (subgroups of {sub.size})",
        labels=labels,
        values=[float(v) for v in sub.means],
        statuses=mean_status,
        rules=mean_rules,
        lines=[
            line(limits["i_ucl"], "UAL", "action"),
            line(limits["i_uwl"], "UWL", "warning"),
            line(limits["i_cl"], "CL", "centre"),
            line(limits["i_lwl"], "LWL", "warning"),
            line(limits["i_lcl"], "LAL", "action"),
        ],
        bands=[
            band(limits["i_uwl"], limits["i_ucl"]),
            band(limits["i_lcl"], limits["i_lwl"]),
        ],
        x_title=str(sub.labels.name or "Subgroup"),
        y_title=f"mean {column}",
    )

    spread_lines = [
        line(limits[f"{spread_key}_ucl"], "UAL", "action"),
        line(limits[f"{spread_key}_uwl"], "UWL", "warning"),
        line(limits[f"{spread_key}_cl"], "CL", "centre"),
    ]
    spread_bands = [band(limits[f"{spread_key}_uwl"], limits[f"{spread_key}_ucl"])]
    # A non-zero lower limit only exists from n = 7; drawing a line at zero would
    # imply a boundary that is not there.
    if limits[f"{spread_key}_lcl"] > 0:
        spread_lines.append(line(limits[f"{spread_key}_lcl"], "LAL", "action"))

    spread_panel = _panel(
        panel="movingRange",
        title=f"{spread_name.capitalize()} chart - {column}",
        labels=labels,
        values=[float(v) for v in spread],
        statuses=[
            "violation" if bool(spread_violations.iloc[i]) else "in control"
            for i in range(sub.n_subgroups)
        ],
        lines=spread_lines,
        bands=spread_bands,
        x_title=str(sub.labels.name or "Subgroup"),
        y_title=f"subgroup {spread_name}",
    )

    return [means_panel, spread_panel]
