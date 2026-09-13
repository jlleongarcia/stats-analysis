"""Rule-violation detectors for Individual and Moving Range charts.

Four rules, all with configurable thresholds:

Rule 1 - Action limits
    Any single point outside UCL/LCL.

Rule 2 - Warning zone
    ``k`` of ``window`` consecutive points beyond the same warning limit
    (default 2 of 3). The user-facing intent is often stated as "no more than
    one point in the warning zone", but 2-of-3 is used because it controls the
    false-alarm rate properly.

Rule 3 - Run
    ``k`` or more consecutive points on the same side of the centre line
    (default 8).

Rule 4 - Trend
    ``k`` or more consecutive points steadily rising or falling (default 6).

.. note:: Deliberate deviation from the original SPC-analysis tool

   Rule 2's ``k`` and ``window`` are applied to **both** the individuals chart
   and the moving-range chart. The original tool accepted those parameters on
   :func:`apply_mr_rules` but never forwarded them from its Phase I pass, so the
   MR chart silently stayed at 2-of-3 however the analyst configured Rule 2.
   That looked like missing wiring rather than intent: the setting is presented
   as one global threshold, and honouring it on one chart but not the other is
   surprising. At the default 2-of-3 the two implementations agree exactly.

.. note:: Flagging convention

   Run- and trend-based rules (3 and 4) flag the point that *completes* the
   window, plus any subsequent point while the run continues - not every point
   in the run retrospectively. So an 8-point run with ``k=8`` flags one point;
   a 9-point run flags two. This keeps a long drift from swamping the decision
   table with a dozen rows describing a single event, and it matches how the
   original tool behaved. Rules 1 and 2 flag the offending point itself.

   Points sitting exactly *on* a limit or the centre line are not violations:
   every comparison is strict.
"""

from __future__ import annotations

import pandas as pd

RULE_COLUMNS = ("rule1", "rule2", "rule3", "rule4")

RULE_LABELS: dict[str, str] = {
    "rule1": "Rule 1 - outside action limits",
    "rule2": "Rule 2 - warning zone",
    "rule3": "Rule 3 - run on one side of centre",
    "rule4": "Rule 4 - trend",
    "mr_rule1": "MR Rule 1 - moving range above UCL",
    "mr_rule2": "MR Rule 2 - moving range warning zone",
}

DEFAULT_RULE_CONFIG: dict[str, int] = {
    "rule2_k": 2,
    "rule2_window": 3,
    "rule3_k": 8,
    "rule4_k": 6,
}


def rule1_action_limits(values: pd.Series, ucl: float, lcl: float) -> pd.Series:
    """Rule 1: point outside the action limits."""
    return (values > ucl) | (values < lcl)


def rule2_warning_zone(
    values: pd.Series,
    cl: float,
    uwl: float,
    lwl: float,
    *,
    k: int = 2,
    window: int = 3,
) -> pd.Series:
    """Rule 2: *k* of *window* consecutive points in the same warning zone.

    Upper and lower zones are counted separately - two points above UWL and one
    below LWL is not a violation, because the two sides signal opposite shifts.
    """
    upper_zone = (values > uwl).astype(int)
    lower_zone = (values < lwl).astype(int)

    upper_violation = (upper_zone.rolling(window).sum() >= k) & (values > uwl)
    lower_violation = (lower_zone.rolling(window).sum() >= k) & (values < lwl)

    return (upper_violation | lower_violation).fillna(False).astype(bool)


def rule3_run_same_side(values: pd.Series, cl: float, *, k: int = 8) -> pd.Series:
    """Rule 3: *k* or more consecutive points on the same side of the centre."""
    above = (values > cl).astype(int)
    below = (values < cl).astype(int)

    # A rolling sum equal to the window means every point in it is on that side.
    upper_run = above.rolling(k).sum() == k
    lower_run = below.rolling(k).sum() == k

    return (upper_run | lower_run).fillna(False).astype(bool)


def rule4_trend(values: pd.Series, *, k: int = 6) -> pd.Series:
    """Rule 4: *k* or more consecutive points steadily rising or falling.

    ``k`` points define ``k - 1`` successive differences, all of which must
    share a sign. A tie (difference of exactly zero) breaks the trend.
    """
    diffs = values.diff()
    rising = (diffs > 0).astype(int)
    falling = (diffs < 0).astype(int)

    n = k - 1
    up_trend = rising.rolling(n).sum() == n
    down_trend = falling.rolling(n).sum() == n

    return (up_trend | down_trend).fillna(False).astype(bool)


def apply_all_rules(
    values: pd.Series,
    limits: dict[str, float],
    *,
    rule2_k: int = 2,
    rule2_window: int = 3,
    rule3_k: int = 8,
    rule4_k: int = 6,
) -> pd.DataFrame:
    """Apply rules 1-4 to the individuals chart.

    Returns
    -------
    DataFrame indexed like *values*, with boolean columns ``rule1``..``rule4``
    plus ``any_violation``.
    """
    df = pd.DataFrame(
        {
            "rule1": rule1_action_limits(values, limits["i_ucl"], limits["i_lcl"]),
            "rule2": rule2_warning_zone(
                values, limits["i_cl"], limits["i_uwl"], limits["i_lwl"],
                k=rule2_k, window=rule2_window,
            ),
            "rule3": rule3_run_same_side(values, limits["i_cl"], k=rule3_k),
            "rule4": rule4_trend(values, k=rule4_k),
        },
        index=values.index,
    )
    df["any_violation"] = df[list(RULE_COLUMNS)].any(axis=1)
    return df


def apply_mr_rule1(mr_values: pd.Series, mr_ucl: float) -> pd.Series:
    """Rule 1 on the moving-range chart.

    Only the upper limit is checked: the MR chart's LCL is 0 at n=2, so no
    range can fall below it.
    """
    return (mr_values > mr_ucl).fillna(False).astype(bool)


def apply_mr_rules(
    mr_values: pd.Series,
    mr_ucl: float,
    mr_uwl: float,
    *,
    rule2_k: int = 2,
    rule2_window: int = 3,
) -> pd.Series:
    """Rules 1 and 2 on the moving-range chart, combined into one flag Series.

    See :mod:`stats_core.spc.limits` on why ``mr_uwl`` is a heuristic.
    """
    r1 = apply_mr_rule1(mr_values, mr_ucl)
    upper_zone = (mr_values > mr_uwl).astype(float)
    r2 = (
        (upper_zone.rolling(rule2_window).sum() >= rule2_k) & (mr_values > mr_uwl)
    ).fillna(False).astype(bool)
    return r1 | r2


def rules_fired(
    individual_violations: pd.DataFrame,
    mr_violations: pd.Series,
    position: int,
) -> list[str]:
    """Names of every rule that fired at integer *position*.

    Used to build the decision table and the audit log, both of which need the
    same "which rules fired here" answer.
    """
    row = individual_violations.iloc[position]
    fired = [name for name in RULE_COLUMNS if bool(row[name])]
    if bool(mr_violations.iloc[position]):
        fired.append("mr_rule1")
    return fired
