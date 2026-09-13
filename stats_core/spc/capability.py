"""Process capability indices: Cp, Cpk, Pp, Ppk and RPI.

Two standard-deviation estimates drive the whole family:

``sigma_within``
    Short-term spread, from the average moving range: ``mr_bar / d2``. It
    answers "how tight could this process hold if nothing drifted?", and feeds
    the *potential* indices Cp and Cpk.
``sigma_overall``
    Long-term spread, the plain sample SD of the retained measurements. It
    includes drift between subgroups, and feeds the *performance* indices
    Pp and Ppk.

::

    Cp  = (USL - LSL) / (6 * sigma_within)
    Cpk = min[(USL - x_bar), (x_bar - LSL)] / (3 * sigma_within)
    Pp  = (USL - LSL) / (6 * sigma_overall)
    Ppk = min[(USL - x_bar), (x_bar - LSL)] / (3 * sigma_overall)
    RPI = 2T / (6 * sigma_within), where T = (USL - LSL) / 2, so RPI == Cp

A wide Cp-to-Pp gap means the process drifts between subgroups. A wide Cp-to-Cpk
gap means it is off-centre.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from stats_core.spc.constants import D2
from stats_core.spc.limits import compute_moving_range

# Conventional thresholds. Cp >= 1 means the spread merely fits the tolerance
# band; Cpk >= 1.33 is the usual contractual minimum (IATF/automotive), and
# 1.67 is common for characteristics designated critical.
CP_CAPABLE = 1.00
CPK_CAPABLE = 1.33
CPK_CRITICAL = 1.67


def estimate_sigma_within(
    values: pd.Series,
    *,
    mr_mask: "np.ndarray | None" = None,
) -> float:
    """Short-term SD estimate from the average moving range.

    Pass *mr_mask* whenever points have been removed, so that ranges bridging
    the resulting gaps stay out of ``mr_bar``.
    """
    clean = values.dropna()
    mr = compute_moving_range(clean)
    if mr_mask is not None:
        mask = np.asarray(mr_mask, dtype=bool)
        selected = mr[mask & mr.notna()]
        mr = selected if len(selected) else mr.dropna()
    else:
        mr = mr.dropna()
    if mr.empty:
        raise ValueError("Cannot estimate sigma_within: no usable moving ranges.")
    return float(mr.mean()) / D2


def compute_capability(
    values: pd.Series,
    usl: float,
    lsl: float,
    *,
    mr_bar: "float | None" = None,
    mr_mask: "np.ndarray | None" = None,
) -> dict[str, float]:
    """Compute Cp, Cpk, Pp, Ppk and RPI for a set of individual measurements.

    Parameters
    ----------
    values:
        The retained (certified baseline) measurements.
    usl, lsl:
        Specification limits - the tolerance the process must meet. These are
        *not* control limits: control limits describe what the process does,
        specification limits describe what it is required to do.
    mr_bar:
        Average moving range from the Phase I baseline. **Prefer this**: it
        carries the bridging mask that was applied when the limits were
        computed, so ``sigma_within`` matches the control chart exactly.
    mr_mask:
        Alternative to *mr_bar* - the mask itself, when the caller has the mask
        but not the average. Ignored if *mr_bar* is given.

    Notes
    -----
    Supplying neither *mr_bar* nor *mr_mask* recomputes the moving ranges from
    *values* as-is. That is only correct when nothing was removed: after
    removals it silently includes ranges spanning the gaps, inflating
    ``sigma_within`` and understating Cp/Cpk. The original tool had this as its
    default path and avoided the bug only because its one caller happened to
    pass ``mr_bar``; the parameter is kept explicit here for that reason.
    """
    clean = values.dropna()
    if len(clean) < 2:
        raise ValueError("At least 2 observations are required.")
    if usl <= lsl:
        raise ValueError("USL must be strictly greater than LSL.")

    x_bar = float(clean.mean())
    sigma_overall = float(clean.std(ddof=1))

    if mr_bar is not None:
        sigma_within = float(mr_bar) / D2
    else:
        sigma_within = estimate_sigma_within(clean, mr_mask=mr_mask)

    def _ratio(numerator: float, sigma: float) -> float:
        return numerator / sigma if sigma > 0 else float("inf")

    cp = _ratio(usl - lsl, 6 * sigma_within)
    cpk = min(
        _ratio(usl - x_bar, 3 * sigma_within),
        _ratio(x_bar - lsl, 3 * sigma_within),
    )
    pp = _ratio(usl - lsl, 6 * sigma_overall)
    ppk = min(
        _ratio(usl - x_bar, 3 * sigma_overall),
        _ratio(x_bar - lsl, 3 * sigma_overall),
    )

    return {
        "usl": float(usl),
        "lsl": float(lsl),
        "tolerance_half_width": (usl - lsl) / 2,
        "x_bar": x_bar,
        "sigma_within": sigma_within,
        "sigma_overall": sigma_overall,
        "mr_bar": sigma_within * D2,
        "cp": cp,
        "cpk": cpk,
        "pp": pp,
        "ppk": ppk,
        "rpi": cp,  # (2T) / (6 sigma) == (USL - LSL) / (6 sigma) == Cp
        "capable_cp": cp >= CP_CAPABLE,
        "capable_cpk": cpk >= CPK_CAPABLE,
    }
