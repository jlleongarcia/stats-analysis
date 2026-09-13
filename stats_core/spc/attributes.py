"""Attribute control charts: p, np, c and u.

Variables charts (I-MR, X-bar/R, X-bar/S) plot a *measurement*. Attribute charts
plot a **count** — how many units were defective, how many defects were found —
and their limits come from the count's own distribution rather than from an
estimated sigma.

=========  ===================================  ==================
Chart      Plots                                Distribution
=========  ===================================  ==================
``p``      proportion defective                 binomial
``np``     number defective                     binomial
``c``      number of defects                    Poisson
``u``      defects per unit                     Poisson
=========  ===================================  ==================

**Defective vs defect.** A *defective* is a unit that failed; a *defect* is one
fault, and a unit can carry several. Counting defectives caps the count at the
number inspected (binomial); counting defects does not (Poisson). Choosing the
wrong family gives limits that are wrong in a way no amount of data reveals.

Where the sample size varies between points, so do the limits: a proportion from
1000 units is far better determined than one from 20, and a chart with constant
limits would flag the small samples relentlessly. The p and u charts therefore
return a limit *per point*, which the renderer draws as a stepped boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from stats_core._util import DataError

__all__ = ["AttributeChart", "p_chart", "np_chart", "c_chart", "u_chart"]

# Sigma multiplier for the action limits, matching the variables charts.
K = 3.0


@dataclass
class AttributeChart:
    """One attribute chart: the plotted statistic plus its limits."""

    kind: str                       # "p" | "np" | "c" | "u"
    labels: pd.Index
    values: pd.Series               # the plotted statistic
    centre: float
    ucl: pd.Series                  # per point; constant when the sample size is
    lcl: pd.Series                  # constant, but always returned per point
    sizes: pd.Series
    n_points: int
    y_title: str

    #: True when every point shares the same limits, so they can be drawn as
    #: plain horizontal lines instead of a stepped boundary.
    constant_limits: bool = field(init=False)

    def __post_init__(self) -> None:
        self.constant_limits = bool(
            np.allclose(self.ucl, self.ucl.iloc[0]) and np.allclose(self.lcl, self.lcl.iloc[0])
        )

    @property
    def violations(self) -> pd.Series:
        """Points outside their own limits."""
        return (self.values > self.ucl) | (self.values < self.lcl)


def _clean_counts(counts: pd.Series, sizes: "pd.Series | None", *, need_sizes: bool):
    values = pd.to_numeric(counts, errors="coerce")
    if sizes is not None:
        size_values = pd.to_numeric(sizes, errors="coerce")
        keep = values.notna() & size_values.notna() & (size_values > 0)
        values, size_values = values[keep], size_values[keep]
    elif need_sizes:
        raise DataError("This chart needs a sample-size column.")
    else:
        values = values.dropna()
        size_values = pd.Series(1.0, index=values.index)

    if len(values) < 2:
        raise DataError("At least 2 usable samples are required to compute limits.")
    if (values < 0).any():
        raise DataError("Counts cannot be negative.")
    return values.reset_index(drop=True), size_values.reset_index(drop=True), values.index


def _labels(index, fallback_name: str, n: int) -> pd.Index:
    if index is not None and len(index) == n:
        return pd.Index([str(v) for v in index], name=fallback_name)
    return pd.Index([str(i + 1) for i in range(n)], name=fallback_name)


def p_chart(defectives: pd.Series, sizes: pd.Series, labels=None) -> AttributeChart:
    """Proportion defective, with limits that follow the sample size."""
    counts, n, _ = _clean_counts(defectives, sizes, need_sizes=True)
    if (counts > n).any():
        raise DataError(
            "More defectives than units inspected. A p chart counts *defective "
            "units*, so the count cannot exceed the sample size - if a unit can "
            "carry several faults, use a c or u chart instead."
        )

    p_bar = float(counts.sum() / n.sum())
    spread = K * np.sqrt(p_bar * (1 - p_bar) / n)
    proportion = counts / n

    return AttributeChart(
        kind="p",
        labels=_labels(labels, "Sample", len(counts)),
        values=proportion,
        centre=p_bar,
        ucl=(p_bar + spread).clip(upper=1.0),
        lcl=(p_bar - spread).clip(lower=0.0),
        sizes=n,
        n_points=len(counts),
        y_title="proportion defective",
    )


def np_chart(defectives: pd.Series, sizes: pd.Series, labels=None) -> AttributeChart:
    """Number defective. Requires a constant sample size."""
    counts, n, _ = _clean_counts(defectives, sizes, need_sizes=True)
    if n.nunique() != 1:
        raise DataError(
            "An np chart plots a raw count, which is only comparable when every "
            f"sample is the same size; found sizes {sorted(n.unique().tolist())[:5]}. "
            "Use a p chart, which scales for the sample size."
        )
    size = float(n.iloc[0])
    p_bar = float(counts.sum() / n.sum())
    centre = size * p_bar
    spread = K * np.sqrt(centre * (1 - p_bar))

    return AttributeChart(
        kind="np",
        labels=_labels(labels, "Sample", len(counts)),
        values=counts,
        centre=centre,
        ucl=pd.Series(centre + spread, index=counts.index).clip(upper=size),
        lcl=pd.Series(max(centre - spread, 0.0), index=counts.index),
        sizes=n,
        n_points=len(counts),
        y_title="number defective",
    )


def c_chart(defects: pd.Series, labels=None) -> AttributeChart:
    """Number of defects per inspection unit, with a constant opportunity."""
    counts, n, _ = _clean_counts(defects, None, need_sizes=False)
    c_bar = float(counts.mean())
    spread = K * np.sqrt(c_bar)

    return AttributeChart(
        kind="c",
        labels=_labels(labels, "Unit", len(counts)),
        values=counts,
        centre=c_bar,
        ucl=pd.Series(c_bar + spread, index=counts.index),
        lcl=pd.Series(max(c_bar - spread, 0.0), index=counts.index),
        sizes=n,
        n_points=len(counts),
        y_title="defects per unit",
    )


def u_chart(defects: pd.Series, sizes: pd.Series, labels=None) -> AttributeChart:
    """Defects per unit, where the inspected amount varies between samples."""
    counts, n, _ = _clean_counts(defects, sizes, need_sizes=True)
    u_bar = float(counts.sum() / n.sum())
    spread = K * np.sqrt(u_bar / n)
    rate = counts / n

    return AttributeChart(
        kind="u",
        labels=_labels(labels, "Sample", len(counts)),
        values=rate,
        centre=u_bar,
        ucl=u_bar + spread,
        lcl=(u_bar - spread).clip(lower=0.0),
        sizes=n,
        n_points=len(counts),
        y_title="defects per unit",
    )


def small_count_warning(chart: AttributeChart) -> "str | None":
    """Flag the case where the normal approximation behind the limits is weak.

    The ±3-sigma limits assume the count is roughly normal. For a binomial that
    needs both ``np`` and ``n(1-p)`` above about 5; for a Poisson it needs a mean
    above about 5. Below that the limits are optimistic and the lower one is
    usually pinned at zero, so the chart can only ever signal upward.
    """
    if chart.kind in ("p", "np"):
        # For p the centre is a proportion, so the expected count is n * p-bar
        # and varies per sample. For np the centre already IS the expected count.
        expected = (
            float((chart.sizes * chart.centre).min())
            if chart.kind == "p"
            else float(chart.centre)
        )
        if expected < 5:
            return (
                f"The expected count per sample is {expected:.1f}, below about 5. "
                "The normal approximation behind +/-3 sigma limits is weak there, "
                "so the limits are approximate and the lower one may be pinned at "
                "zero - the chart can then only signal an increase."
            )
    elif chart.centre < 5:
        return (
            f"The average count is {chart.centre:.1f}, below about 5. The normal "
            "approximation behind +/-3 sigma limits is weak there; treat the "
            "limits as approximate, and prefer a larger inspection unit."
        )
    return None
