"""Cross-variable suspect flagging.

When several characteristics are measured on the same units, an observation
removed from one variable is evidence about the others. A chiller tripping at
02:30 perturbs every measurement taken at 02:30, but the rules may only clear
the threshold on one of them.

So: surface the evidence, never act on it. A cross-flag pre-suggests removal in
the UI and still demands a documented assignable cause, exactly like any other
flagged point. Anything else would be automatic removal via the back door.
"""

from __future__ import annotations

from dataclasses import dataclass

from stats_core.spc.audit import DECISION_REMOVED


@dataclass(frozen=True)
class CrossFlag:
    """One observation label removed from one or more *other* variables."""

    label: str
    removed_from: tuple[str, ...]

    @property
    def note(self) -> str:
        return f"also removed from: {', '.join(self.removed_from)}"


def removed_labels(audit_log) -> set[str]:
    """Observation labels marked ``Removed`` in one variable's audit log."""
    if audit_log is None or len(audit_log) == 0:
        return set()
    removed = audit_log[audit_log["decision"] == DECISION_REMOVED]
    return {str(label) for label in removed["observation"]}


def cross_flags(
    audit_logs: "dict[str, object]",
    target: str,
) -> dict[str, CrossFlag]:
    """Labels removed from variables *other than* ``target``.

    Parameters
    ----------
    audit_logs:
        ``{variable_name: audit_log DataFrame}`` for every completed study.
    target:
        The variable currently under review; its own removals are excluded.

    Returns
    -------
    ``{label: CrossFlag}``, keyed by observation label for direct lookup while
    rendering the decision table.
    """
    collected: dict[str, list[str]] = {}
    for variable, log in audit_logs.items():
        if variable == target:
            continue
        for label in removed_labels(log):
            collected.setdefault(label, []).append(variable)

    return {
        label: CrossFlag(label, tuple(sorted(variables)))
        for label, variables in sorted(collected.items())
    }


def shared_removals(audit_logs: "dict[str, object]", *, min_variables: int = 2) -> dict[str, tuple[str, ...]]:
    """Labels removed from at least *min_variables* variables.

    These are the highest-priority investigation targets: a disturbance large
    enough to register on several independent characteristics is a process
    event, not a measurement artefact.
    """
    collected: dict[str, list[str]] = {}
    for variable, log in audit_logs.items():
        for label in removed_labels(log):
            collected.setdefault(label, []).append(variable)

    return {
        label: tuple(sorted(variables))
        for label, variables in sorted(collected.items())
        if len(variables) >= min_variables
    }
