"""Subgrouped variables charts: X-bar/R and X-bar/S.

The individuals chart treats every observation as its own subgroup of one. When
several measurements are taken per time period - five parts per hour, three
aliquots per batch - a subgrouped chart is strictly better: the within-subgroup
spread estimates sigma directly, and averaging shrinks the noise on the centre
line by sqrt(n).

Which spread statistic to use:

``R`` (range)
    Simple, and what the shop floor has always used. Loses efficiency as the
    subgroup grows because it ignores everything between the two extremes.
``s`` (standard deviation)
    Uses every observation. Preferred from about n >= 9, and the only sensible
    option past n = 25 where the range constants stop being tabulated.

Both charts put the *same* rules on the means chart, so everything in
:mod:`stats_core.spc.rules` applies unchanged - the limit dictionaries use the
same ``i_*`` keys as the individuals chart for exactly that reason.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from stats_core._util import DataError
from stats_core.spc.constants import MAX_SUBGROUP, MIN_SUBGROUP, constants_for

__all__ = ["Subgroups", "build_subgroups", "xbar_r_limits", "xbar_s_limits"]


@dataclass
class Subgroups:
    """Measurements collapsed into equal-sized rational subgroups."""

    labels: pd.Index        # one display label per subgroup
    means: pd.Series        # x-bar per subgroup, RangeIndex
    ranges: pd.Series       # max - min per subgroup
    sds: pd.Series          # sample SD (ddof=1) per subgroup
    size: int               # the common subgroup size
    n_subgroups: int
    n_dropped: int          # observations discarded as an incomplete tail

    @property
    def grand_mean(self) -> float:
        return float(self.means.mean())


def _validate_size(size: int) -> int:
    size = int(size)
    if size < MIN_SUBGROUP:
        raise DataError(
            f"A subgroup needs at least {MIN_SUBGROUP} observations; got {size}. "
            "For single measurements use the individuals (I-MR) chart."
        )
    if size > MAX_SUBGROUP:
        raise DataError(
            f"Subgroup size {size} is beyond the tabulated constants "
            f"({MIN_SUBGROUP}-{MAX_SUBGROUP})."
        )
    return size


def _from_chunks(values: pd.Series, size: int) -> Subgroups:
    """Consecutive fixed-size chunks, in row order."""
    size = _validate_size(size)
    clean = values.dropna()
    n_complete = len(clean) // size
    if n_complete < 2:
        raise DataError(
            f"Need at least 2 complete subgroups of {size}; the data yields "
            f"{n_complete} from {len(clean)} usable observations."
        )
    used = n_complete * size
    dropped = len(clean) - used

    block = clean.iloc[:used].to_numpy(float).reshape(n_complete, size)
    labels = pd.Index(
        [str(clean.index[i * size]) for i in range(n_complete)],
        name=clean.index.name or "Subgroup",
    )
    return Subgroups(
        labels=labels,
        means=pd.Series(block.mean(axis=1)),
        ranges=pd.Series(block.max(axis=1) - block.min(axis=1)),
        sds=pd.Series(block.std(axis=1, ddof=1)),
        size=size,
        n_subgroups=n_complete,
        n_dropped=dropped,
    )


def _from_column(values: pd.Series, groups: pd.Series) -> Subgroups:
    """Group by an explicit subgroup column, preserving first-appearance order."""
    frame = pd.DataFrame({"value": values, "group": groups.astype(str)}).dropna()
    if frame.empty:
        raise DataError("No complete observations after pairing values with subgroups.")

    order = list(dict.fromkeys(frame["group"]))  # order of first appearance, not sorted
    collected = [frame.loc[frame["group"] == g, "value"].to_numpy(float) for g in order]
    sizes = {len(a) for a in collected}

    if len(sizes) != 1:
        counts = ", ".join(
            f"{g} ({len(a)})" for g, a in list(zip(order, collected))[:6]
        )
        raise DataError(
            "Shewhart constants are defined per subgroup size, so every subgroup "
            f"must hold the same number of observations. Found sizes {sorted(sizes)} "
            f"- e.g. {counts}. Either trim the subgroups to a common size or use "
            "the individuals (I-MR) chart."
        )

    size = _validate_size(sizes.pop())
    if len(collected) < 2:
        raise DataError("Need at least 2 subgroups to compute control limits.")

    block = np.vstack(collected)
    return Subgroups(
        labels=pd.Index(order, name=groups.name or "Subgroup"),
        means=pd.Series(block.mean(axis=1)),
        ranges=pd.Series(block.max(axis=1) - block.min(axis=1)),
        sds=pd.Series(block.std(axis=1, ddof=1)),
        size=size,
        n_subgroups=len(order),
        n_dropped=0,
    )


def build_subgroups(
    values: pd.Series,
    *,
    groups: "pd.Series | None" = None,
    size: "int | None" = None,
) -> Subgroups:
    """Collapse measurements into rational subgroups.

    Supply either *groups* (a column naming each observation's subgroup) or
    *size* (chunk consecutive rows). A subgroup column is the honest option when
    the data records which batch each measurement came from; fixed chunking
    assumes row order already reflects the sampling plan.
    """
    if groups is not None:
        return _from_column(values, groups)
    if size is not None:
        return _from_chunks(values, size)
    raise DataError("Provide either a subgroup column or a subgroup size.")


def _means_chart(grand_mean: float, sigma_within: float, size: int) -> dict[str, float]:
    """Limits for the means chart, shared by both variants.

    Uses ``sigma_xbar = sigma_within / sqrt(n)`` directly rather than the A2/A3
    shortcuts. The two are algebraically identical (A2 = 3 / (d2 * sqrt(n))), but
    this form also yields the 2-sigma warning lines, which the shortcut factors
    do not provide.
    """
    sigma_xbar = sigma_within / np.sqrt(size)
    return {
        "i_cl": grand_mean,
        "i_ucl": grand_mean + 3 * sigma_xbar,
        "i_uwl": grand_mean + 2 * sigma_xbar,
        "i_lwl": grand_mean - 2 * sigma_xbar,
        "i_lcl": grand_mean - 3 * sigma_xbar,
        "sigma_xbar": float(sigma_xbar),
    }


def xbar_r_limits(sub: Subgroups) -> dict[str, float]:
    """X-bar and R chart limits, with sigma estimated from the average range."""
    c = constants_for(sub.size)
    r_bar = float(sub.ranges.mean())
    sigma_within = r_bar / c.d2

    limits = {
        "n": float(sub.n_subgroups),
        "subgroup_size": float(sub.size),
        "x_bar": sub.grand_mean,
        "r_bar": r_bar,
        "sigma_within": sigma_within,
        **_means_chart(sub.grand_mean, sigma_within, sub.size),
        "r_cl": r_bar,
        "r_ucl": c.D4 * r_bar,
        "r_lcl": c.D3 * r_bar,
    }
    # A range chart is skewed, so there is no principled 2-sigma line; keep the
    # same two-thirds interpolation the MR chart uses, for consistency.
    limits["r_uwl"] = r_bar + (2 / 3) * (limits["r_ucl"] - r_bar)
    return limits


def xbar_s_limits(sub: Subgroups) -> dict[str, float]:
    """X-bar and S chart limits, with sigma estimated from the average SD."""
    c = constants_for(sub.size)
    s_bar = float(sub.sds.mean())
    sigma_within = s_bar / c.c4

    limits = {
        "n": float(sub.n_subgroups),
        "subgroup_size": float(sub.size),
        "x_bar": sub.grand_mean,
        "s_bar": s_bar,
        "sigma_within": sigma_within,
        **_means_chart(sub.grand_mean, sigma_within, sub.size),
        "s_cl": s_bar,
        "s_ucl": c.B4 * s_bar,
        "s_lcl": c.B3 * s_bar,
    }
    limits["s_uwl"] = s_bar + (2 / 3) * (limits["s_ucl"] - s_bar)
    return limits
