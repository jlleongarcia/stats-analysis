from __future__ import annotations

import numpy as np
import pytest
from scipy.cluster.hierarchy import fcluster, linkage
from sklearn.cluster import KMeans

from stats_core import run_test


def _num(df):
    return [c for c in df.columns if df[c].dtype.kind in "fi"]


def _standardized(df, cols):
    sub = df[cols].dropna()
    X = sub.to_numpy(float)
    sd = X.std(axis=0, ddof=1)
    return (X - X.mean(axis=0)) / sd


def test_hierarchical_cluster_sizes_match_scipy(ceras):
    cols = _num(ceras)[:5]
    X = _standardized(ceras, cols)
    Z = linkage(X, method="ward")
    ref_labels = fcluster(Z, t=3, criterion="maxclust")
    ref_sizes = sorted(np.bincount(ref_labels)[1:].tolist())

    out = run_test("hierarchical_cluster", ceras, {"columns": cols}, {"n_clusters": 3})
    sizes_table = next(t for t in out["tables"] if t["title"] == "Cluster sizes")
    got_sizes = sorted(r[1] for r in sizes_table["rows"])
    assert got_sizes == ref_sizes


def test_hierarchical_cluster_dendrogram_segment_count(ceras):
    cols = _num(ceras)[:5]
    n = ceras[cols].dropna().shape[0]
    out = run_test("hierarchical_cluster", ceras, {"columns": cols}, {})
    dendro = next(p for p in out["plotSpecs"] if p["kind"] == "dendrogram")
    n_segments = len(set(dendro["data"]["segment"]))
    assert n_segments == n - 1


def test_kmeans_inertia_close_to_sklearn(ceras):
    cols = _num(ceras)[:5]
    X = _standardized(ceras, cols)
    ref = KMeans(n_clusters=3, n_init=10, random_state=0).fit(X)

    out = run_test("kmeans_cluster", ceras, {"columns": cols}, {"k": 3, "seed": 0})
    # Different init strategies (scipy k-means++ vs sklearn's) can land in different
    # local optima, so compare inertia loosely rather than requiring an exact match.
    assert out["statistic"]["withinClusterSS"] == pytest.approx(ref.inertia_, rel=0.5)


def test_kmeans_cluster_sizes_sum_to_n(ceras):
    cols = _num(ceras)[:4]
    n = ceras[cols].dropna().shape[0]
    out = run_test("kmeans_cluster", ceras, {"columns": cols}, {"k": 4})
    sizes_table = next(t for t in out["tables"] if t["title"] == "Cluster sizes")
    assert sum(r[1] for r in sizes_table["rows"]) == n
