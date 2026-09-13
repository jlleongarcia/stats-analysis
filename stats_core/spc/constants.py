"""Shewhart control-chart constants by subgroup size.

The individuals (I-MR) chart only ever needs the ``n = 2`` column, because a
span-2 moving range *is* a subgroup of two. The rest of the table is what makes
X-bar/R and X-bar/S charts possible without re-deriving anything, so it lives
here from the start rather than being bolted on later.

Columns
-------
``d2``
    E(R / sigma) - the unbiasing constant that turns an average range into a
    standard-deviation estimate: ``sigma_within = R_bar / d2``.
``d3``
    SD(R / sigma); used for the R-chart limits at ``n < 7`` where D3 > 0.
``D3``, ``D4``
    Lower/upper R-chart limit factors: ``LCL = D3 * R_bar``, ``UCL = D4 * R_bar``.
``A2``
    X-bar chart limit factor from the range: ``x_bar +/- A2 * R_bar``.
``A3``
    X-bar chart limit factor from the pooled SD: ``x_bar +/- A3 * s_bar``.
``B3``, ``B4``
    S-chart limit factors: ``LCL = B3 * s_bar``, ``UCL = B4 * s_bar``.
``c4``
    E(s / sigma) - unbiases the average sample SD: ``sigma = s_bar / c4``.

Values follow ASTM E2587 / ISO 7870-2, rounded to the three decimals that are
conventional in the SPC literature.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SubgroupConstants:
    """The full set of Shewhart factors for one subgroup size."""

    n: int
    d2: float
    d3: float
    D3: float
    D4: float
    A2: float
    A3: float
    B3: float
    B4: float
    c4: float


# n: (d2, d3, D3, D4, A2, A3, B3, B4, c4)
_TABLE: dict[int, tuple[float, ...]] = {
    2:  (1.128, 0.853, 0.000, 3.267, 1.880, 2.659, 0.000, 3.267, 0.7979),
    3:  (1.693, 0.888, 0.000, 2.574, 1.023, 1.954, 0.000, 2.568, 0.8862),
    4:  (2.059, 0.880, 0.000, 2.282, 0.729, 1.628, 0.000, 2.266, 0.9213),
    5:  (2.326, 0.864, 0.000, 2.114, 0.577, 1.427, 0.000, 2.089, 0.9400),
    6:  (2.534, 0.848, 0.000, 2.004, 0.483, 1.287, 0.030, 1.970, 0.9515),
    7:  (2.704, 0.833, 0.076, 1.924, 0.419, 1.182, 0.118, 1.882, 0.9594),
    8:  (2.847, 0.820, 0.136, 1.864, 0.373, 1.099, 0.185, 1.815, 0.9650),
    9:  (2.970, 0.808, 0.184, 1.816, 0.337, 1.032, 0.239, 1.761, 0.9693),
    10: (3.078, 0.797, 0.223, 1.777, 0.308, 0.975, 0.284, 1.716, 0.9727),
    11: (3.173, 0.787, 0.256, 1.744, 0.285, 0.927, 0.321, 1.679, 0.9754),
    12: (3.258, 0.778, 0.283, 1.717, 0.266, 0.886, 0.354, 1.646, 0.9776),
    13: (3.336, 0.770, 0.307, 1.693, 0.249, 0.850, 0.382, 1.618, 0.9794),
    14: (3.407, 0.763, 0.328, 1.672, 0.235, 0.817, 0.406, 1.594, 0.9810),
    15: (3.472, 0.756, 0.347, 1.653, 0.223, 0.789, 0.428, 1.572, 0.9823),
    16: (3.532, 0.750, 0.363, 1.637, 0.212, 0.763, 0.448, 1.552, 0.9835),
    17: (3.588, 0.744, 0.378, 1.622, 0.203, 0.739, 0.466, 1.534, 0.9845),
    18: (3.640, 0.739, 0.391, 1.608, 0.194, 0.718, 0.482, 1.518, 0.9854),
    19: (3.689, 0.734, 0.403, 1.597, 0.187, 0.698, 0.497, 1.503, 0.9862),
    20: (3.735, 0.729, 0.415, 1.585, 0.180, 0.680, 0.510, 1.490, 0.9869),
    21: (3.778, 0.724, 0.425, 1.575, 0.173, 0.663, 0.523, 1.477, 0.9876),
    22: (3.819, 0.720, 0.434, 1.566, 0.167, 0.647, 0.534, 1.466, 0.9882),
    23: (3.858, 0.716, 0.443, 1.557, 0.162, 0.633, 0.545, 1.455, 0.9887),
    24: (3.895, 0.712, 0.451, 1.548, 0.157, 0.619, 0.555, 1.445, 0.9892),
    25: (3.931, 0.708, 0.459, 1.541, 0.153, 0.606, 0.565, 1.435, 0.9896),
}

MIN_SUBGROUP = min(_TABLE)
MAX_SUBGROUP = max(_TABLE)


def constants_for(n: int) -> SubgroupConstants:
    """Return the Shewhart factors for subgroup size *n*.

    Raises
    ------
    ValueError
        If *n* is outside the tabulated range (2..25). Beyond n=25 the range
        chart loses efficiency badly enough that an S chart is the right answer,
        so extrapolating the table would be a disservice rather than a courtesy.
    """
    try:
        row = _TABLE[int(n)]
    except (KeyError, ValueError, TypeError):
        raise ValueError(
            f"No Shewhart constants for subgroup size {n!r}; "
            f"tabulated sizes are {MIN_SUBGROUP}..{MAX_SUBGROUP}. "
            "For larger subgroups use an X-bar/S chart."
        ) from None
    return SubgroupConstants(int(n), *row)


# The individuals chart is the n=2 case: a span-2 moving range is a subgroup of
# two. Bound at import so the hot path never does a dict lookup, and so the old
# `from spc.core.limits import D2` call sites keep working after the port.
_N2 = constants_for(2)
D2: float = _N2.d2       # 1.128
D3: float = _N2.D3       # 0.0  -> MR chart LCL is always 0 at n=2
D4: float = _N2.D4       # 3.267
