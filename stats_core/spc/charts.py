"""Vega-Lite payloads for control charts.

Shared by the registry entries (Analyze page) and the Studio protocol, so both
render the identical chart from the identical code. Which lines and shaded zones
each panel carries is SPC domain knowledge and belongs here, under test - the
TypeScript renderer only maps a line's ``kind`` to a colour and dash pattern.
"""

from __future__ import annotations

import pandas as pd

from stats_core.spc.rules import RULE_LABELS, rules_fired

__all__ = ["control_chart_specs"]


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
