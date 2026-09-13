"""Control-limit calculations for Individual (I) and Moving Range (MR) charts.

Control lines
-------------
Individuals chart::

    CL  = x_bar
    UCL = x_bar + 3 * sigma_within        (UAL, "action limit")
    LCL = x_bar - 3 * sigma_within        (LAL)
    UWL = x_bar + 2 * sigma_within        (warning limit)
    LWL = x_bar - 2 * sigma_within

Moving-range chart::

    CL  = mr_bar
    UCL = D4 * mr_bar                     (D4 = 3.267 at n=2)
    LCL = 0                               (always 0 at n=2, since D3 = 0)

where ``sigma_within = mr_bar / d2`` is the short-term (within-subgroup)
standard-deviation estimate.

.. note:: Deliberate deviation from the textbooks

   ``mr_uwl`` is set two thirds of the way from CL to UCL::

       mr_uwl = mr_bar * (1 + (2/3) * (D4 - 1))

   There is no standard warning limit for a range chart - the range statistic
   is skewed, so a "2-sigma" line has no clean closed form the way it does on
   the symmetric individuals chart. This linear interpolation is a pragmatic
   stand-in carried over from the original SPC tool, kept so that MR rule 2
   behaves consistently with I rule 2. Treat it as a heuristic, not a
   published formula.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from stats_core.spc.constants import D2, D4

__all__ = ["D2", "D4", "compute_moving_range", "compute_limits", "bridging_mr_mask"]


def compute_moving_range(values: pd.Series) -> pd.Series:
    """Absolute successive differences (span-2 moving range).

    The first entry is NaN - there is no range before the first observation.
    """
    return values.diff().abs()


def bridging_mr_mask(kept_positions: "list[int] | np.ndarray") -> np.ndarray:
    """Mark which moving ranges of a *filtered* series are non-bridging.

    When observations are removed from the middle of a series, the moving range
    computed across the gap spans points that were never adjacent in the real
    process. Including those inflated ranges in ``mr_bar`` corrupts
    ``sigma_within`` - which is the whole basis of the control limits.

    Parameters
    ----------
    kept_positions:
        The original positions (in the pre-removal series) of the observations
        that survived, in ascending order. For example, removing index 3 from a
        6-point series gives ``[0, 1, 2, 4, 5]``.

    Returns
    -------
    Boolean array, one entry per retained observation, aligned with the output
    of :func:`compute_moving_range`. Entry ``j`` is True when the moving range
    ending at retained point ``j`` was computed from an originally-adjacent
    pair. Entry 0 is True by convention (its MR is NaN and gets dropped anyway).

    Examples
    --------
    >>> bridging_mr_mask([0, 1, 2, 4, 5]).tolist()
    [True, True, True, False, True]
    """
    kept = [int(p) for p in kept_positions]
    return np.array(
        [j == 0 or kept[j] - kept[j - 1] == 1 for j in range(len(kept))],
        dtype=bool,
    )


def compute_limits(
    values: pd.Series,
    *,
    mr_mask: "np.ndarray | None" = None,
) -> dict[str, float]:
    """Compute every control line for an I-MR chart pair.

    Parameters
    ----------
    values:
        Time-ordered individual measurements. NaN entries are excluded.
    mr_mask:
        Optional boolean array of length ``len(values.dropna())`` selecting
        which moving ranges contribute to ``mr_bar``. Build it with
        :func:`bridging_mr_mask` after removing points, so that
        ``sigma_within`` is estimated only from originally-adjacent pairs.

    Returns
    -------
    dict with keys ``x_bar``, ``mr_bar``, ``sigma_within``, ``n``,
    ``i_ucl``, ``i_uwl``, ``i_cl``, ``i_lwl``, ``i_lcl``,
    ``mr_ucl``, ``mr_uwl``, ``mr_cl``, ``mr_lcl``.
    """
    clean = values.dropna()
    if len(clean) < 2:
        raise ValueError("At least 2 non-NaN values are required to compute limits.")

    mr = compute_moving_range(clean)

    if mr_mask is not None:
        mask = np.asarray(mr_mask, dtype=bool)
        if mask.size != len(clean):
            raise ValueError(
                f"mr_mask has length {mask.size} but there are {len(clean)} "
                "non-NaN observations; they must match."
            )
        mr_for_bar = mr[mask & mr.notna()]
        if len(mr_for_bar) == 0:
            # Every surviving pair bridges a gap. Falling back to all ranges is
            # wrong in principle but less wrong than dividing by zero; the
            # caller surfaces this via the returned n.
            mr_for_bar = mr.dropna()
    else:
        mr_for_bar = mr.dropna()

    x_bar = float(clean.mean())
    mr_bar = float(mr_for_bar.mean())
    sigma = mr_bar / D2

    return {
        "n": int(len(clean)),
        "x_bar": x_bar,
        "mr_bar": mr_bar,
        "sigma_within": sigma,
        # Individuals chart
        "i_ucl": x_bar + 3 * sigma,
        "i_uwl": x_bar + 2 * sigma,
        "i_cl": x_bar,
        "i_lwl": x_bar - 2 * sigma,
        "i_lcl": x_bar - 3 * sigma,
        # Moving-range chart (see the module docstring on mr_uwl)
        "mr_ucl": D4 * mr_bar,
        "mr_uwl": mr_bar * (1 + (2 / 3) * (D4 - 1)),
        "mr_cl": mr_bar,
        "mr_lcl": 0.0,
    }
