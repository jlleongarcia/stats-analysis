"""Standardized result schema shared by every test.

The whole point of this module: no matter which test ran, the UI receives the
same shape, so rendering, report export and the guided flow stay generic.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


def _clean(value: Any) -> Any:
    """Recursively convert NaN/inf and numpy scalars into JSON-safe values."""
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        try:
            value = value.item()
        except (ValueError, TypeError):
            pass
    if isinstance(value, float):
        if math.isnan(value):
            return None
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
    return value


@dataclass
class AssumptionCheck:
    """One precondition of a test and whether the data appears to satisfy it."""

    name: str
    passed: bool | None  # None => "could not be assessed / informational only"
    detail: str
    statistic: float | None = None
    p_value: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return _clean(
            {
                "name": self.name,
                "passed": self.passed,
                "detail": self.detail,
                "statistic": self.statistic,
                "pValue": self.p_value,
            }
        )


@dataclass
class EffectSize:
    name: str
    value: float
    ci_low: float | None = None
    ci_high: float | None = None
    magnitude: str | None = None  # "negligible" | "small" | "medium" | "large"

    def to_dict(self) -> dict[str, Any]:
        return _clean(
            {
                "name": self.name,
                "value": self.value,
                "ciLow": self.ci_low,
                "ciHigh": self.ci_high,
                "magnitude": self.magnitude,
            }
        )


@dataclass
class ResultTable:
    """A named tabular block (group descriptives, ANOVA table, coefficients...)."""

    title: str
    columns: list[str]
    rows: list[list[Any]]

    def to_dict(self) -> dict[str, Any]:
        return _clean({"title": self.title, "columns": self.columns, "rows": self.rows})


@dataclass
class TestResult:
    test_id: str
    test_name: str
    summary: str = ""  # plain-language, one or two sentences
    apa: str = ""  # APA-style statistical report line
    statistic: dict[str, float] = field(default_factory=dict)
    p_value: float | None = None
    effect_sizes: list[EffectSize] = field(default_factory=list)
    assumptions: list[AssumptionCheck] = field(default_factory=list)
    tables: list[ResultTable] = field(default_factory=list)
    plot_spec: dict[str, Any] | None = None
    notes: list[str] = field(default_factory=list)

    def add_note(self, note: str) -> "TestResult":
        self.notes.append(note)
        return self

    def to_dict(self) -> dict[str, Any]:
        return _clean(
            {
                "testId": self.test_id,
                "testName": self.test_name,
                "summary": self.summary,
                "apa": self.apa,
                "statistic": self.statistic,
                "pValue": self.p_value,
                "effectSizes": [e.to_dict() for e in self.effect_sizes],
                "assumptions": [a.to_dict() for a in self.assumptions],
                "tables": [t.to_dict() for t in self.tables],
                "plotSpec": self.plot_spec,
                "notes": self.notes,
            }
        )
