"""CART classification tree (scikit-learn), with a simple depth-based layout so
the frontend can render the tree as a node-link diagram."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier

from stats_core._util import DataError
from stats_core.results import ResultTable, TestResult


def _layout(tree, feature_names: list[str]) -> tuple[list[dict], list[dict]]:
    """In-order leaf position for x, depth for y - a simple tidy-enough layout."""
    nodes: list[dict] = []
    edges: list[dict] = []
    next_x = [0]

    def visit(node_id: int, depth: int) -> float:
        left, right = tree.children_left[node_id], tree.children_right[node_id]
        is_leaf = left == -1
        if is_leaf:
            x = float(next_x[0])
            next_x[0] += 1
        else:
            xl = visit(left, depth + 1)
            xr = visit(right, depth + 1)
            x = (xl + xr) / 2
            edges.append({"x0": x, "y0": float(depth), "x1": xl, "y1": float(depth + 1)})
            edges.append({"x0": x, "y0": float(depth), "x1": xr, "y1": float(depth + 1)})

        values = tree.value[node_id][0]
        majority = int(np.argmax(values))
        if is_leaf:
            label = f"leaf: class {majority}\nn={int(tree.n_node_samples[node_id])}"
        else:
            fname = feature_names[tree.feature[node_id]]
            label = f"{fname} <= {tree.threshold[node_id]:.3g}\nn={int(tree.n_node_samples[node_id])}"
        nodes.append({"id": node_id, "x": x, "y": float(depth), "label": label, "leaf": is_leaf})
        return x

    visit(0, 0)
    return nodes, edges


def classification_tree(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    outcome_col = roles["outcome"]
    cols = roles.get("predictors") or []
    if len(cols) < 1:
        raise DataError("Classification tree needs at least 1 predictor.")
    sub = frame[[outcome_col, *cols]].dropna().copy()
    for c in cols:
        sub[c] = pd.to_numeric(sub[c], errors="coerce")
    sub = sub.dropna()
    if sub[outcome_col].nunique() < 2:
        raise DataError("The outcome needs at least 2 categories.")

    max_depth = int(params.get("max_depth", 3))
    min_samples_leaf = int(params.get("min_samples_leaf", 5))
    criterion = params.get("criterion", "gini")
    if criterion not in {"gini", "entropy", "log_loss"}:
        raise DataError("criterion must be 'gini', 'entropy' or 'log_loss'.")

    X = sub[cols].to_numpy(float)
    y = sub[outcome_col].astype(str).to_numpy()
    clf = DecisionTreeClassifier(
        max_depth=max_depth, min_samples_leaf=min_samples_leaf, criterion=criterion, random_state=0,
    ).fit(X, y)
    pred = clf.predict(X)
    accuracy = float(np.mean(pred == y))

    classes = clf.classes_.tolist()
    confusion = [
        [a, *[int(np.sum((pred == p) & (y == a))) for p in classes]]
        for a in classes
    ]

    nodes, edges = _layout(clf.tree_, cols)

    return TestResult(
        test_id="classification_tree",
        test_name="Classification tree (CART)",
        summary=(
            f"{outcome_col} ({len(classes)} classes) predicted from {len(cols)} variable(s), "
            f"n = {len(sub)}: {clf.get_n_leaves()} leaves, depth {clf.get_depth()}, "
            f"resubstitution accuracy = {accuracy * 100:.1f}%."
        ),
        p_value=None,
        statistic={"nLeaves": float(clf.get_n_leaves()), "depth": float(clf.get_depth()),
                   "resubstitutionAccuracy": accuracy},
        tables=[
            ResultTable("Classification results (resubstitution)", ["actual \\ predicted", *classes], confusion),
            ResultTable("Feature importances", ["variable", "importance"],
                        [[cols[i], float(v)] for i, v in enumerate(clf.feature_importances_)]),
        ],
        plot_specs=[{
            "kind": "tree",
            "data": {
                "nodeId": [n["id"] for n in nodes], "x": [n["x"] for n in nodes],
                "y": [n["y"] for n in nodes], "label": [n["label"] for n in nodes],
                "leaf": [n["leaf"] for n in nodes],
            },
            "edges": {
                "x0": [e["x0"] for e in edges], "y0": [e["y0"] for e in edges],
                "x1": [e["x1"] for e in edges], "y1": [e["y1"] for e in edges],
            },
        }],
        notes=[f"criterion = {criterion}, max_depth = {max_depth}, min_samples_leaf = {min_samples_leaf}. "
               "Accuracy is resubstitution (fit and evaluated on the same rows), not cross-validated."],
    )
