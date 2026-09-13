"""The analyst decision log.

Every point the rules flag produces one audit row, whether or not the analyst
removed it - "reviewed and retained" is itself a decision worth recording, and
regulators reading the trail need to see that the judgement was made rather
than that the point was never noticed.

The column set is carried over unchanged from the original tool so historical
exports stay comparable, with one fix: ``observation`` is a plain column rather
than the index. As an index it silently collapsed duplicate labels (two batches
sharing a date), which is exactly the situation an audit trail must not blur.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from stats_core.spc.rules import RULE_LABELS, rules_fired

AUDIT_COLUMNS: tuple[str, ...] = (
    "pass",
    "observation",
    "value",
    "rules_violated",
    "decision",
    "assignable_cause",
    "x_bar",
    "ual",
    "lal",
)

DECISION_REMOVED = "Removed"
DECISION_RETAINED = "Retained (analyst decision)"


class AssignableCauseRequired(ValueError):
    """Raised when a removal is requested without a documented cause.

    This is the methodological guard rail, not a form-validation nicety: the
    whole premise of Phase I is that statistical significance alone never
    justifies deleting data (Oakland, Ch. 4-5).
    """


@dataclass(frozen=True)
class Decision:
    """One analyst ruling on one flagged point.

    ``position`` is the integer offset into the pass's retained values, which is
    duplicate-label-safe in a way that the observation label is not.
    """

    position: int
    remove: bool = False
    cause: str = ""

    @property
    def clean_cause(self) -> str:
        return self.cause.strip()


@dataclass
class DecisionSet:
    """The analyst's rulings for one pass, keyed by position."""

    decisions: dict[int, Decision] = field(default_factory=dict)

    @classmethod
    def from_records(cls, records: "list[dict[str, Any]] | None") -> "DecisionSet":
        out: dict[int, Decision] = {}
        for rec in records or []:
            position = int(rec["position"])
            out[position] = Decision(
                position=position,
                remove=bool(rec.get("remove", False)),
                cause=str(rec.get("cause", "") or ""),
            )
        return cls(out)

    def get(self, position: int) -> Decision:
        return self.decisions.get(position, Decision(position))

    @property
    def positions_to_remove(self) -> list[int]:
        return sorted(p for p, d in self.decisions.items() if d.remove)

    def validate(self, labels: "pd.Index | None" = None) -> None:
        """Reject any removal that carries no documented assignable cause."""
        missing = [
            p for p, d in sorted(self.decisions.items())
            if d.remove and not d.clean_cause
        ]
        if not missing:
            return
        named = [
            str(labels[p]) if labels is not None and p < len(labels) else f"position {p}"
            for p in missing
        ]
        raise AssignableCauseRequired(
            "An assignable cause is required before removing: " + ", ".join(named)
        )


def describe_rules(names: "list[str]") -> str:
    """Human-readable rule list for a decision table cell."""
    return ", ".join(RULE_LABELS.get(n, n) for n in names)


def build_audit_log(
    pass_result,
    decisions: DecisionSet,
    *,
    pass_number: int = 1,
) -> pd.DataFrame:
    """Build the decision log for every flagged point in *pass_result*.

    Points the rules never flagged are absent: the log records judgements, and
    no judgement was called for.
    """
    limits = pass_result.limits
    rows: list[dict[str, Any]] = []

    for position in pass_result.flagged_positions:
        decision = decisions.get(position)
        fired = rules_fired(
            pass_result.individual_violations, pass_result.mr_violations, position
        )
        rows.append(
            {
                "pass": pass_number,
                "observation": str(pass_result.original_labels[position]),
                "value": float(pass_result.values.iloc[position]),
                "rules_violated": ", ".join(fired),
                "decision": DECISION_REMOVED if decision.remove else DECISION_RETAINED,
                "assignable_cause": decision.clean_cause,
                "x_bar": limits["i_cl"],
                "ual": limits["i_ucl"],
                "lal": limits["i_lcl"],
            }
        )

    return pd.DataFrame(rows, columns=list(AUDIT_COLUMNS))
