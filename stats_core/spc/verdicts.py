"""Plain-language interpretation of Phase I and capability results.

These heuristics were embedded in the original tool's Streamlit pages, which
made them invisible to the test suite and impossible to reuse. They are
judgement calls rather than statistics - documented here so they can be
argued with, rather than rediscovered in a UI file.
"""

from __future__ import annotations

from stats_core.spc.capability import CP_CAPABLE, CPK_CAPABLE, CPK_CRITICAL

# Above this share of removed observations, the baseline period is more likely
# to be unstable than the individual points are to be special causes. The right
# response is to reselect the period, not to keep pruning.
OVER_PRUNING_RATE = 0.20

# Cpk/Cp below this means enough of the tolerance band is being eaten by
# off-centring that recentring beats variance reduction as the first move.
OFF_CENTRE_RATIO = 0.85

# Pp materially below Cp means long-term drift between subgroups.
DRIFT_RATIO = 0.75


def phase_i_verdicts(result) -> list[str]:
    """Narrate a :class:`~stats_core.spc.phase_i.PhaseIResult`."""
    notes: list[str] = []
    rate = result.removal_rate
    pct = 100 * rate

    if result.n_removed == 0 and not result.final_pass_has_violations:
        notes.append(
            f"Process in statistical control: no violations across all "
            f"{result.n_original} observations."
        )
    elif result.n_removed == 0:
        notes.append(
            "Baseline certified with all flagged points retained by analyst "
            "decision. Limits reflect the full dataset."
        )
    elif not result.final_pass_has_violations:
        notes.append(
            f"Pass 2 in statistical control: {result.n_removed} of "
            f"{result.n_original} observations removed ({pct:.1f}%)."
        )
    else:
        notes.append(
            f"Pass 2 removed {result.n_removed} of {result.n_original} "
            f"observations ({pct:.1f}%), and violations remain. Treat these as "
            "common-cause variation; do not prune further without fresh "
            "process evidence."
        )

    if rate > OVER_PRUNING_RATE:
        notes.append(
            f"{pct:.1f}% of observations were removed. Above "
            f"{OVER_PRUNING_RATE:.0%} the baseline period itself is suspect - "
            "consider reselecting the period rather than removing more points."
        )

    if result.n_final < 20:
        notes.append(
            f"Only {result.n_final} observations remain. Control limits from "
            "fewer than about 20 points are unstable; treat them as "
            "provisional and revisit once more data is available."
        )

    return notes


def capability_verdicts(cap: dict[str, float], *, in_control: bool | None = None) -> list[str]:
    """Narrate the output of
    :func:`~stats_core.spc.capability.compute_capability`."""
    notes: list[str] = []

    if in_control is False:
        notes.append(
            "The data still shows rule violations, so the process is not in "
            "statistical control. Capability indices assume a stable process - "
            "these numbers describe the past, not what the process will do "
            "next. Establish a Phase I baseline first."
        )

    cp, cpk, pp = cap["cp"], cap["cpk"], cap["pp"]

    if cap["capable_cp"]:
        notes.append(f"Cp = {cp:.3f}: the spread fits inside the tolerance band.")
    else:
        notes.append(
            f"Cp = {cp:.3f} is below {CP_CAPABLE:.2f}: variation exceeds the "
            "tolerance band, so the process cannot be made capable by "
            "recentring alone - the variation itself has to come down."
        )

    if cpk >= CPK_CRITICAL:
        notes.append(
            f"Cpk = {cpk:.3f} meets the {CPK_CRITICAL:.2f} threshold used for "
            "critical characteristics."
        )
    elif cap["capable_cpk"]:
        notes.append(
            f"Cpk = {cpk:.3f} meets the common {CPK_CAPABLE:.2f} minimum."
        )
    else:
        notes.append(
            f"Cpk = {cpk:.3f} is below the common {CPK_CAPABLE:.2f} minimum: "
            "the process is off-centre, short of margin, or both."
        )

    if cp > 0 and (cpk / cp) < OFF_CENTRE_RATIO:
        notes.append(
            f"Cpk/Cp = {cpk / cp:.2f}: the process is meaningfully off-centre. "
            "Recentring recovers capability more cheaply than reducing "
            "variation - investigate systematic bias first."
        )

    if cp > 0 and (pp / cp) < DRIFT_RATIO:
        notes.append(
            f"Pp = {pp:.3f} trails Cp = {cp:.3f}: long-term spread is well "
            "above short-term spread, which is the signature of drift between "
            "subgroups rather than excess within-subgroup noise."
        )

    return notes
