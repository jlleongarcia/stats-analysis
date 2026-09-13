"""Named rule sets: Oakland's four, Western Electric's four, Nelson's eight.

The four rules in :mod:`stats_core.spc.rules` are the set the original
SPC-analysis tool implemented, and they stay the default. This module adds the
two other sets in common use, built on the standard **zone** decomposition of
the chart:

===== ===============================
Zone  Distance from the centre line
===== ===============================
C     0 to 1 sigma
B     1 to 2 sigma
A     2 to 3 sigma
beyond  more than 3 sigma
===== ===============================

Every additional rule raises sensitivity to small shifts and *also* raises the
false-alarm rate. Running all eight Nelson rules on a genuinely stable process
produces a signal roughly every 90 points by chance alone. That is the trade:
more rules find real shifts sooner and cry wolf more often. Pick the set your
organisation standardises on rather than the one that flags the most.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

__all__ = ["RULE_SETS", "RuleSet", "apply_rule_set", "zone_of"]


def zone_of(values: pd.Series, centre: float, sigma: float) -> pd.Series:
    """Signed zone index: +/-1, +/-2, +/-3 for zones C, B, A, +/-4 beyond 3 sigma."""
    if sigma <= 0:
        return pd.Series(0, index=values.index)
    z = (values - centre) / sigma
    magnitude = np.minimum(np.floor(np.abs(z)) + 1, 4).astype(int)
    return pd.Series(np.sign(z).astype(int) * magnitude, index=values.index)


def _k_of_m_beyond(z: pd.Series, level: int, k: int, m: int) -> pd.Series:
    """*k* of *m* consecutive points beyond ``level`` sigma on the SAME side."""
    out = np.zeros(len(z), dtype=bool)
    zv = z.to_numpy()
    for side in (1, -1):
        qualifies = (np.sign(zv) == side) & (np.abs(zv) > level)
        for i in range(m - 1, len(zv)):
            window = qualifies[i - m + 1 : i + 1]
            if window.sum() >= k and qualifies[i]:
                out[i] = True
    return pd.Series(out, index=z.index)


def _run_same_side(values: pd.Series, centre: float, k: int) -> pd.Series:
    above = (values > centre).astype(int)
    below = (values < centre).astype(int)
    return ((above.rolling(k).sum() == k) | (below.rolling(k).sum() == k)).fillna(False)


def _trend(values: pd.Series, k: int) -> pd.Series:
    d = values.diff()
    n = k - 1
    up = (d > 0).astype(int).rolling(n).sum() == n
    down = (d < 0).astype(int).rolling(n).sum() == n
    return (up | down).fillna(False)


def _alternating(values: pd.Series, k: int) -> pd.Series:
    """*k* points alternating up and down - a sawtooth, often over-adjustment."""
    d = values.diff()
    flips = (np.sign(d) * np.sign(d.shift(1)) < 0).astype(int)
    return (flips.rolling(k - 2).sum() == k - 2).fillna(False)


def _hugging(z: pd.Series, k: int) -> pd.Series:
    """*k* consecutive points all within 1 sigma - suspiciously little spread."""
    inner = (z.abs() <= 1).astype(int)
    return (inner.rolling(k).sum() == k).fillna(False)


def _mixture(z: pd.Series, k: int) -> pd.Series:
    """*k* consecutive points all outside 1 sigma, on either side."""
    outer = (z.abs() > 1).astype(int)
    return (outer.rolling(k).sum() == k).fillna(False)


@dataclass(frozen=True)
class Rule:
    key: str
    label: str
    detect: Callable[[pd.Series, pd.Series, float, float], pd.Series]


@dataclass(frozen=True)
class RuleSet:
    key: str
    name: str
    description: str
    rules: tuple[Rule, ...]


def _beyond_limits(values, z, centre, sigma):
    return z.abs() > 3


_WECO = (
    Rule("weco1", "1 point beyond 3 sigma", _beyond_limits),
    Rule("weco2", "2 of 3 points beyond 2 sigma, same side",
         lambda v, z, c, s: _k_of_m_beyond(z, 2, 2, 3)),
    Rule("weco3", "4 of 5 points beyond 1 sigma, same side",
         lambda v, z, c, s: _k_of_m_beyond(z, 1, 4, 5)),
    Rule("weco4", "8 consecutive points on one side of centre",
         lambda v, z, c, s: _run_same_side(v, c, 8)),
)

_NELSON = (
    Rule("nelson1", "1 point beyond 3 sigma", _beyond_limits),
    Rule("nelson2", "9 consecutive points on one side of centre",
         lambda v, z, c, s: _run_same_side(v, c, 9)),
    Rule("nelson3", "6 consecutive points steadily rising or falling",
         lambda v, z, c, s: _trend(v, 6)),
    Rule("nelson4", "14 consecutive points alternating up and down",
         lambda v, z, c, s: _alternating(v, 14)),
    Rule("nelson5", "2 of 3 points beyond 2 sigma, same side",
         lambda v, z, c, s: _k_of_m_beyond(z, 2, 2, 3)),
    Rule("nelson6", "4 of 5 points beyond 1 sigma, same side",
         lambda v, z, c, s: _k_of_m_beyond(z, 1, 4, 5)),
    Rule("nelson7", "15 consecutive points within 1 sigma (too little spread)",
         lambda v, z, c, s: _hugging(z, 15)),
    Rule("nelson8", "8 consecutive points beyond 1 sigma, either side (mixture)",
         lambda v, z, c, s: _mixture(z, 8)),
)

RULE_SETS: dict[str, RuleSet] = {
    "oakland": RuleSet(
        "oakland", "Oakland (4 rules)",
        "Action limits, warning zone, run and trend. The default, and what the "
        "original SPC-analysis tool implemented. Thresholds are configurable.",
        (),  # handled by stats_core.spc.rules, which supports custom thresholds
    ),
    "weco": RuleSet(
        "weco", "Western Electric (4 rules)",
        "The classic zone tests from the 1956 handbook: beyond 3 sigma, 2-of-3 "
        "beyond 2 sigma, 4-of-5 beyond 1 sigma, and a run of 8.",
        _WECO,
    ),
    "nelson": RuleSet(
        "nelson", "Nelson (8 rules)",
        "Nelson's 1984 set. Adds tests for alternation, stratification and "
        "mixtures, catching patterns the others miss - at a higher false-alarm "
        "rate.",
        _NELSON,
    ),
}


def apply_rule_set(
    values: pd.Series, limits: dict[str, float], rule_set: str
) -> pd.DataFrame:
    """Apply a named rule set, returning one boolean column per rule.

    The centre line and sigma come from ``limits``, so this works identically on
    an individuals chart and on the means chart of a subgrouped study.
    """
    spec = RULE_SETS.get(rule_set)
    if spec is None or not spec.rules:
        raise KeyError(rule_set)

    centre = limits["i_cl"]
    # Recover sigma from the action limit rather than trusting a separate key:
    # on a subgrouped means chart the relevant sigma is sigma/sqrt(n), and the
    # limits already carry it.
    sigma = (limits["i_ucl"] - centre) / 3.0
    z = zone_of(values, centre, sigma) if sigma > 0 else pd.Series(0, index=values.index)
    z_exact = (values - centre) / sigma if sigma > 0 else pd.Series(0.0, index=values.index)

    frame = pd.DataFrame(index=values.index)
    for rule in spec.rules:
        frame[rule.key] = rule.detect(values, z_exact, centre, sigma).astype(bool)
    frame["any_violation"] = frame.any(axis=1)
    return frame


def rule_labels(rule_set: str) -> dict[str, str]:
    spec = RULE_SETS.get(rule_set)
    return {r.key: r.label for r in spec.rules} if spec else {}
