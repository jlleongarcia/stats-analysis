"""stats_core - framework-free statistical test implementations.

Every public test function takes a :class:`pandas.DataFrame` plus a ``roles``
mapping (which columns play which part) and a ``params`` dict, and returns a
:class:`stats_core.results.TestResult`. Nothing in this package imports Pyodide,
the DOM, or any JS bridge, so the exact same code runs under CPython (pytest)
and inside the browser via Pyodide.
"""

from __future__ import annotations

from stats_core.results import AssumptionCheck, EffectSize, ResultTable, TestResult
from stats_core.registry import REGISTRY, Role, TestSpec, get_registry, get_spec, run_test

__all__ = [
    "AssumptionCheck",
    "EffectSize",
    "ResultTable",
    "TestResult",
    "REGISTRY",
    "Role",
    "TestSpec",
    "get_registry",
    "get_spec",
    "run_test",
]

__version__ = "0.1.0"
