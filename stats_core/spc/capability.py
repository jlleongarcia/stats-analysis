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

from stats_core._util import DataError
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


# --------------------------------------------------------------------------
# non-normal data, interval estimates and the Taguchi index
# --------------------------------------------------------------------------

def cpk_confidence_interval(
    cpk: float, n: int, *, confidence: float = 0.95
) -> tuple[float, float]:
    """Approximate confidence interval for Cpk (Bissell, 1990).

    Capability indices are point estimates from a sample, and at the sample
    sizes SPC studies typically run on they are far less precise than their
    three decimal places suggest. The standard error

    .. math:: SE(C_{pk}) \\approx \\sqrt{\\frac{1}{9n} + \\frac{C_{pk}^2}{2(n-1)}}

    makes that concrete: at n = 30 a reported Cpk of 1.33 is compatible with
    anything from roughly 1.0 to 1.7.
    """
    from scipy import stats as _stats

    if n < 2 or not np.isfinite(cpk):
        return (float("nan"), float("nan"))
    se = np.sqrt(1.0 / (9 * n) + cpk**2 / (2 * (n - 1)))
    z = _stats.norm.ppf(0.5 + confidence / 2)
    return (float(cpk - z * se), float(cpk + z * se))


def compute_cpm(values: pd.Series, usl: float, lsl: float, target: float) -> float:
    """Taguchi's Cpm, which penalises departure from a target.

    Cp and Cpk both treat the tolerance band as the only thing that matters. Cpm
    adds the target into the denominator

    .. math:: C_{pm} = \\frac{USL - LSL}{6\\sqrt{\\sigma^2 + (\\mu - T)^2}}

    so a process that is on-spec but off-target scores lower. Use it when being
    close to nominal has value in itself - which is the usual case in assembly,
    where tolerances stack.
    """
    clean = values.dropna()
    mu = float(clean.mean())
    sigma = float(clean.std(ddof=1))
    denominator = np.sqrt(sigma**2 + (mu - target) ** 2)
    if denominator <= 0:
        return float("inf")
    return float((usl - lsl) / (6 * denominator))


def transform_to_normal(values: pd.Series) -> dict:
    """Find a Box-Cox power transform that makes *values* closer to normal.

    Cp and Cpk assume normality: they convert a sigma into a tail probability,
    and on skewed data that conversion is simply wrong - typically optimistic,
    because the long tail is the side that generates defects.

    Two honest options exist. Transform the data, compute capability in the
    transformed space and transform the limits back (this function), or abandon
    sigma entirely and read the percentiles directly
    (:func:`percentile_capability`). This one needs strictly positive data.
    """
    from scipy import stats as _stats

    clean = values.dropna()
    if (clean <= 0).any():
        raise DataError(
            "Box-Cox needs strictly positive values. Shift the data, or use the "
            "percentile method, which makes no distributional assumption."
        )
    transformed, lam = _stats.boxcox(clean.to_numpy(float))
    _, p_before = _stats.shapiro(clean)
    _, p_after = _stats.shapiro(transformed)
    return {
        "lambda": float(lam),
        "values": pd.Series(transformed, index=clean.index),
        "p_before": float(p_before),
        "p_after": float(p_after),
        "improved": bool(p_after > p_before),
    }


def percentile_capability(
    values: pd.Series, usl: float, lsl: float
) -> dict[str, float]:
    """Capability from observed percentiles - the ISO 22514-2 approach.

    Replaces the +/-3 sigma span with the actual 0.135th and 99.865th
    percentiles, which are the points a normal distribution would place three
    sigma out. No distributional assumption is made, so it stays valid on skewed
    data; the cost is that estimating a 0.135th percentile from a few dozen
    points is inherently noisy.
    """
    clean = values.dropna().to_numpy(float)
    if clean.size < 2:
        raise ValueError("At least 2 observations are required.")
    if usl <= lsl:
        raise ValueError("USL must be strictly greater than LSL.")

    lo, median, hi = np.percentile(clean, [0.135, 50, 99.865])
    spread = hi - lo
    pp = (usl - lsl) / spread if spread > 0 else float("inf")
    upper = (usl - median) / (hi - median) if hi > median else float("inf")
    lower = (median - lsl) / (median - lo) if median > lo else float("inf")

    return {
        "pp_percentile": float(pp),
        "ppk_percentile": float(min(upper, lower)),
        "p0_135": float(lo),
        "median": float(median),
        "p99_865": float(hi),
    }
