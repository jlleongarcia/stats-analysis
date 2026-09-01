"""Cluster analysis: agglomerative hierarchical clustering (with dendrogram
coordinates) and k-means."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import dendrogram, fcluster, linkage
from scipy.cluster.vq import kmeans2

from stats_core._util import DataError
from stats_core.results import ResultTable, TestResult

_METHODS = {"ward", "complete", "average", "single"}


def _prepared(frame: pd.DataFrame, roles: dict, params: dict) -> tuple[pd.DataFrame, np.ndarray]:
    cols = roles.get("columns") or []
    if len(cols) < 2:
        raise DataError("Cluster analysis needs at least 2 numeric columns.")
    sub = frame[cols].apply(pd.to_numeric, errors="coerce").dropna()
    if len(sub) < 3:
        raise DataError("Fewer than 3 complete rows across the selected columns.")
    X = sub.to_numpy(float)
    if bool(params.get("standardize", True)):
        sd = X.std(axis=0, ddof=1)
        sd[sd == 0] = 1.0
        X = (X - X.mean(axis=0)) / sd
    return sub, X


def _scatter_by_cluster(X: np.ndarray, labels: np.ndarray, roles: dict) -> dict:
    x = X[:, 0].tolist()
    if X.shape[1] >= 2:
        y = X[:, 1].tolist()
        x_title, y_title = (roles.get("columns") or [])[:2]
    else:
        y = [0.0] * len(x)
        x_title, y_title = (roles.get("columns") or ["x"])[0], ""
    return {
        "kind": "scatter",
        "data": {"x": x, "y": y, "group": [f"cluster {c}" for c in labels]},
        "encoding": {"x": {"field": "x", "title": x_title}, "y": {"field": "y", "title": y_title}},
    }


def hierarchical_cluster(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    sub, X = _prepared(frame, roles, params)
    method = params.get("method", "ward")
    if method not in _METHODS:
        raise DataError(f"method must be one of {sorted(_METHODS)}.")
    n_clusters = max(2, min(int(params.get("n_clusters", 3)), len(sub) - 1))

    Z = linkage(X, method=method)
    dn = dendrogram(Z, no_plot=True, labels=[str(i) for i in sub.index])
    labels = fcluster(Z, t=n_clusters, criterion="maxclust")

    segments = []
    for seg_idx, (xs, ys) in enumerate(zip(dn["icoord"], dn["dcoord"])):
        for order, (x, y) in enumerate(zip(xs, ys)):
            segments.append((seg_idx, order, x, y))

    sizes = pd.Series(labels).value_counts().sort_index()
    return TestResult(
        test_id="hierarchical_cluster",
        test_name=f"Hierarchical cluster analysis ({method} linkage)",
        summary=(
            f"{len(sub)} cases, {len(roles.get('columns') or [])} variables, {method} linkage; "
            f"cut into {n_clusters} clusters."
        ),
        p_value=None,
        statistic={"nClusters": float(n_clusters)},
        tables=[
            ResultTable("Cluster sizes", ["cluster", "n"],
                        [[int(c), int(n)] for c, n in sizes.items()]),
            ResultTable("Cluster assignments", ["row", "cluster"],
                        [[str(i), int(c)] for i, c in zip(sub.index, labels)]),
        ],
        plot_specs=[
            {
                "kind": "dendrogram",
                "data": {
                    "segment": [s[0] for s in segments],
                    "order": [s[1] for s in segments],
                    "x": [s[2] for s in segments],
                    "y": [s[3] for s in segments],
                },
            },
            _scatter_by_cluster(X, labels, roles),
        ],
        notes=["Variables were standardized before clustering." if params.get("standardize", True)
               else "Clustering used the raw (unstandardized) variable scale."],
    )


def kmeans_cluster(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    sub, X = _prepared(frame, roles, params)
    k = max(2, min(int(params.get("k", 3)), len(sub) - 1))
    seed = int(params.get("seed", 0))

    centers, labels = kmeans2(X, k, minit="++", seed=seed)
    inertia = float(sum(np.sum((X[labels == c] - centers[c]) ** 2) for c in range(k)))

    cols = roles.get("columns") or []
    sizes = pd.Series(labels).value_counts().sort_index()
    return TestResult(
        test_id="kmeans_cluster",
        test_name="K-means cluster analysis",
        summary=f"{len(sub)} cases partitioned into k = {k} clusters; within-cluster SS = {inertia:.3f}.",
        p_value=None,
        statistic={"k": float(k), "withinClusterSS": inertia},
        tables=[
            ResultTable("Cluster sizes", ["cluster", "n"],
                        [[int(c), int(n)] for c, n in sizes.items()]),
            ResultTable("Cluster centers", ["cluster", *cols],
                        [[int(c), *[float(v) for v in centers[c]]] for c in range(k)]),
        ],
        plot_specs=[_scatter_by_cluster(X, labels, roles)],
        notes=["Variables were standardized before clustering." if params.get("standardize", True)
               else "Clustering used the raw (unstandardized) variable scale."],
    )
