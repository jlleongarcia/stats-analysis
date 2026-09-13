"""JSON entry points for the SPC Studio.

The Studio is a stateful, human-in-the-loop workflow, but **nothing here holds
state**. The caller passes the full exclusion set on every call and the engine
recomputes from scratch, which means:

* the Python side stays pure and unit-testable;
* a worker restart loses nothing;
* the workflow state lives in the browser, where it is already persisted.

Every function takes and returns plain JSON-safe structures, so the worker can
hand payloads across the boundary as strings without leaking proxy handles.
"""

from __future__ import annotations

from typing import Any, Callable

import numpy as np
import pandas as pd

from stats_core._util import DataError
from stats_core.results import _clean
from stats_core.spc.audit import AUDIT_COLUMNS, DecisionSet
from stats_core.spc.capability import compute_capability
from stats_core.spc.crossflag import shared_removals
from stats_core.spc.limits import bridging_mr_mask
from stats_core.spc.phase_i import control_lines_table, finalise, run_phase_i_pass
from stats_core.spc.precheck import normality_precheck, normality_summary
from stats_core.spc.rules import DEFAULT_RULE_CONFIG, rules_fired
from stats_core.spc.verdicts import capability_verdicts, phase_i_verdicts


# --------------------------------------------------------------------------
# payload plumbing
# --------------------------------------------------------------------------

def _frame(data: Any) -> pd.DataFrame:
    if isinstance(data, pd.DataFrame):
        return data
    if isinstance(data, dict):
        return pd.DataFrame({k: list(v) for k, v in data.items()})
    raise DataError("data must be a DataFrame or a {column: values} mapping.")


def _rule_config(raw: "dict[str, Any] | None") -> dict[str, int]:
    config = dict(DEFAULT_RULE_CONFIG)
    for key, value in (raw or {}).items():
        if key in config:
            config[key] = int(value)
    return config


def _series(payload: dict) -> pd.Series:
    """The measurement column, indexed by its display labels."""
    frame = _frame(payload.get("data"))
    column = payload.get("column")
    if not column:
        raise DataError("No measurement column selected.")
    if column not in frame.columns:
        raise DataError(f"Column {column!r} is not in the dataset.")

    values = pd.to_numeric(frame[column], errors="coerce")
    if values.notna().sum() < 2:
        raise DataError(f"Column {column!r} has fewer than 2 numeric values.")

    order_column = payload.get("orderColumn")
    if order_column:
        if order_column not in frame.columns:
            raise DataError(f"Order column {order_column!r} is not in the dataset.")
        if order_column == column:
            raise DataError(
                "The order column and the measurement column must differ - a "
                "measurement cannot also be its own observation label."
            )
        labels = frame[order_column].astype(str)
    else:
        # No label column: observations are numbered by row order as imported,
        # which is the control chart's time axis.
        labels = pd.Index(range(1, len(frame) + 1), name="Observation").astype(str)

    values.index = pd.Index(labels, name=order_column or "Observation")
    return values


def _excluded(payload: dict) -> set[int]:
    return {int(p) for p in payload.get("excluded") or []}


def _apply_exclusions(
    values: pd.Series, excluded: set[int]
) -> tuple[pd.Series, "np.ndarray | None"]:
    """Drop excluded rows and build the matching bridging mask.

    Rows carrying NaN are not "removed" in the SPC sense - they were never
    observations - so adjacency is judged among the rows that actually hold a
    measurement.
    """
    if not excluded:
        return values, None

    valid_positions = np.flatnonzero(values.notna().to_numpy())
    kept_ranks = [
        rank for rank, position in enumerate(valid_positions)
        if int(position) not in excluded
    ]
    if len(kept_ranks) < 2:
        raise DataError(
            "Fewer than 2 observations remain after exclusions; there is "
            "nothing left to establish a baseline from."
        )

    keep = np.array(
        [i not in excluded for i in range(len(values))], dtype=bool
    )
    return values.iloc[keep], bridging_mr_mask(kept_ranks)


def _points(pass_result) -> list[dict[str, Any]]:
    """Per-observation records for the chart and the decision table."""
    mr_values = pass_result.mr
    out: list[dict[str, Any]] = []
    for position in range(pass_result.n_original):
        fired = rules_fired(
            pass_result.individual_violations, pass_result.mr_violations, position
        )
        mr_value = mr_values.iloc[position]
        out.append(
            {
                "position": position,
                "label": str(pass_result.original_labels[position]),
                "sourceRow": int(pass_result.original_positions[position]),
                "value": float(pass_result.values.iloc[position]),
                "mr": None if pd.isna(mr_value) else float(mr_value),
                "rules": fired,
                "flagged": bool(fired),
            }
        )
    return out


def _table(frame: pd.DataFrame) -> dict[str, Any]:
    return {
        "columns": [str(c) for c in frame.columns],
        "rows": frame.to_dict(orient="split")["data"],
    }


# --------------------------------------------------------------------------
# operations
# --------------------------------------------------------------------------

def evaluate(payload: dict) -> dict:
    """Run one Phase I pass over the data minus the caller's exclusions.

    Payload: ``data``, ``column``, optional ``orderColumn``, optional
    ``ruleConfig``, optional ``excluded`` (source row indices).
    """
    values = _series(payload)
    rule_config = _rule_config(payload.get("ruleConfig"))
    excluded = _excluded(payload)
    retained, mr_mask = _apply_exclusions(values, excluded)

    result = run_phase_i_pass(retained, mr_mask=mr_mask, **rule_config)
    points = _points(result)

    return _clean(
        {
            "column": payload.get("column"),
            "orderColumn": payload.get("orderColumn"),
            "ruleConfig": rule_config,
            "limits": result.limits,
            "points": points,
            "flagged": result.flagged_positions,
            "anyViolations": result.any_violations,
            "nEvaluated": result.n_original,
            "nExcluded": len(excluded),
            "controlLines": _table(control_lines_table(result.limits)),
            "normality": normality_summary(normality_precheck(result.values)),
        }
    )


def certify(payload: dict) -> dict:
    """Apply the analyst's decisions and return the certified baseline.

    Payload: as :func:`evaluate`, plus ``decisions`` - a list of
    ``{position, remove, cause}`` records against the pass being reviewed.
    Removing without a documented cause is rejected.
    """
    values = _series(payload)
    rule_config = _rule_config(payload.get("ruleConfig"))
    excluded = _excluded(payload)
    retained, mr_mask = _apply_exclusions(values, excluded)

    first_pass = run_phase_i_pass(retained, mr_mask=mr_mask, **rule_config)
    decisions = DecisionSet.from_records(payload.get("decisions"))
    result = finalise(first_pass, retained, decisions)

    removed_rows = [
        int(first_pass.original_positions[p]) for p in decisions.positions_to_remove
    ]

    return _clean(
        {
            "column": payload.get("column"),
            "ruleConfig": rule_config,
            "limits": result.final_limits,
            "nOriginal": result.n_original,
            "nFinal": result.n_final,
            "nRemoved": result.n_removed,
            "removalRate": result.removal_rate,
            "nPasses": result.n_passes,
            "finalPassHasViolations": result.final_pass_has_violations,
            "removedSourceRows": removed_rows,
            "auditLog": _table(result.audit_log),
            "auditColumns": list(AUDIT_COLUMNS),
            "controlLines": _table(control_lines_table(result.final_limits)),
            "verdicts": phase_i_verdicts(result),
            "normality": normality_summary(normality_precheck(result.final_values)),
        }
    )


def capability(payload: dict) -> dict:
    """Capability indices for the retained measurements.

    Payload: as :func:`evaluate`, plus ``usl`` and ``lsl``. Optionally
    ``mrBar`` - pass the certified baseline's value so ``sigma_within`` matches
    the control chart exactly.
    """
    values = _series(payload)
    rule_config = _rule_config(payload.get("ruleConfig"))
    excluded = _excluded(payload)
    retained, mr_mask = _apply_exclusions(values, excluded)

    if payload.get("usl") is None or payload.get("lsl") is None:
        raise DataError("Both USL and LSL are required to compute capability.")
    usl, lsl = float(payload["usl"]), float(payload["lsl"])

    result = run_phase_i_pass(retained, mr_mask=mr_mask, **rule_config)
    mr_bar = payload.get("mrBar")
    cap = compute_capability(
        result.values,
        usl,
        lsl,
        mr_bar=float(mr_bar) if mr_bar is not None else result.limits["mr_bar"],
    )

    return _clean(
        {
            "column": payload.get("column"),
            "capability": cap,
            "inControl": not result.any_violations,
            "verdicts": capability_verdicts(cap, in_control=not result.any_violations),
            "normality": normality_summary(normality_precheck(result.values)),
        }
    )


def cross_variable(payload: dict) -> dict:
    """Observations removed from two or more variables.

    Payload: ``auditLogs`` - ``{variable: {columns, rows}}`` as returned by
    :func:`certify`.
    """
    logs: dict[str, pd.DataFrame] = {}
    for variable, table in (payload.get("auditLogs") or {}).items():
        logs[variable] = pd.DataFrame(
            table.get("rows") or [], columns=table.get("columns") or list(AUDIT_COLUMNS)
        )

    shared = shared_removals(logs)
    return _clean(
        {
            "shared": [
                {"label": label, "removedFrom": list(variables)}
                for label, variables in shared.items()
            ],
            "variables": sorted(logs),
        }
    )


_OPERATIONS: dict[str, Callable[[dict], dict]] = {
    "evaluate": evaluate,
    "certify": certify,
    "capability": capability,
    "cross_variable": cross_variable,
}


def spc_call(fn: str, payload: "dict | None" = None) -> dict:
    """Dispatch one Studio operation by name.

    Raises :class:`~stats_core._util.DataError` for an unknown operation or a
    malformed payload, which the worker turns into a structured UI message.
    """
    try:
        operation = _OPERATIONS[fn]
    except KeyError:
        known = ", ".join(sorted(_OPERATIONS))
        raise DataError(f"Unknown SPC operation {fn!r}; expected one of: {known}") from None
    return operation(dict(payload or {}))


__all__ = ["spc_call", "evaluate", "certify", "capability", "cross_variable"]
