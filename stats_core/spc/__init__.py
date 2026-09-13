"""Statistical Process Control: control charts, Phase I baselines, capability.

Everything in the rest of ``stats_core`` is cross-sectional - compare groups,
model relationships, reduce dimensions. This subpackage adds the axis none of
that has: **time order**.

Two contracts live here, deliberately separated:

*Stateless* (``stats_core.registry``)
    ``control_chart_imr`` and ``process_capability`` are ordinary registry
    entries - one shot, one :class:`~stats_core.results.TestResult`, no
    workflow. Good for "show me the chart".

*Stateful* (:mod:`stats_core.spc.api`)
    Phase I is iterative and human-in-the-loop by design: the rules flag
    candidates, the analyst documents an assignable cause for each removal, and
    only then is a baseline certified. That cannot be expressed as a
    ``TestSpec`` without either removing points automatically - which would
    destroy the method's entire premise - or smuggling state through ``params``.
    The Studio drives :func:`~stats_core.spc.api.spc_call` instead, and even
    then the Python side stays pure: the caller re-sends its exclusion set on
    every call.
"""

from __future__ import annotations

from stats_core.spc.api import spc_call
from stats_core.spc.audit import (
    AssignableCauseRequired,
    Decision,
    DecisionSet,
    build_audit_log,
)
from stats_core.spc.capability import compute_capability, estimate_sigma_within
from stats_core.spc.constants import D2, D4, SubgroupConstants, constants_for
from stats_core.spc.crossflag import cross_flags, shared_removals
from stats_core.spc.limits import bridging_mr_mask, compute_limits, compute_moving_range
from stats_core.spc.phase_i import (
    PassResult,
    PhaseIResult,
    control_lines_table,
    finalise,
    run_phase_i_pass,
)
from stats_core.spc.precheck import normality_precheck
from stats_core.spc.rules import (
    DEFAULT_RULE_CONFIG,
    RULE_COLUMNS,
    RULE_LABELS,
    apply_all_rules,
    apply_mr_rule1,
    apply_mr_rules,
    rule1_action_limits,
    rule2_warning_zone,
    rule3_run_same_side,
    rule4_trend,
    rules_fired,
)
from stats_core.spc.verdicts import capability_verdicts, phase_i_verdicts

__all__ = [
    # constants
    "D2",
    "D4",
    "SubgroupConstants",
    "constants_for",
    # limits
    "compute_limits",
    "compute_moving_range",
    "bridging_mr_mask",
    # rules
    "DEFAULT_RULE_CONFIG",
    "RULE_COLUMNS",
    "RULE_LABELS",
    "rule1_action_limits",
    "rule2_warning_zone",
    "rule3_run_same_side",
    "rule4_trend",
    "apply_all_rules",
    "apply_mr_rule1",
    "apply_mr_rules",
    "rules_fired",
    # phase I
    "PassResult",
    "PhaseIResult",
    "run_phase_i_pass",
    "finalise",
    "control_lines_table",
    # audit
    "AssignableCauseRequired",
    "Decision",
    "DecisionSet",
    "build_audit_log",
    # capability
    "compute_capability",
    "estimate_sigma_within",
    # interpretation
    "phase_i_verdicts",
    "capability_verdicts",
    "normality_precheck",
    # cross-variable
    "cross_flags",
    "shared_removals",
    # studio protocol
    "spc_call",
]
