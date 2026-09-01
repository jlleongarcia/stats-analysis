"""The test registry: metadata + dispatch.

The frontend calls :func:`get_registry` once to build its UI (families, the
variable-role form for each test, default params) and :func:`run_test` to
execute one. Adding a test = importing its function and appending one
:class:`TestSpec` below.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable

import pandas as pd

from stats_core import anova, categorical, classification_tree, cluster_analysis
from stats_core import correlation, descriptives, discriminant
from stats_core import location_tests as loc
from stats_core import multivariate as mv
from stats_core import nonparametric as npar
from stats_core import normality, regression, reliability, variance_tests
from stats_core._util import DataError
from stats_core.results import TestResult

NUMERIC = "numeric"
CATEGORICAL = "categorical"
ANY = "any"


@dataclass(frozen=True)
class Role:
    key: str
    label: str
    dtype: str = NUMERIC
    multiple: bool = False
    required: bool = True
    help: str = ""


@dataclass(frozen=True)
class Param:
    key: str
    label: str
    type: str  # "number" | "select" | "bool" | "list"
    default: Any = None
    choices: tuple[str, ...] = ()
    help: str = ""


@dataclass(frozen=True)
class TestSpec:
    id: str
    name: str
    family: str
    description: str
    func: Callable[[pd.DataFrame, dict, dict], TestResult]
    roles: tuple[Role, ...] = ()
    params: tuple[Param, ...] = ()
    assumptions: tuple[str, ...] = ()
    min_n: int = 3

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("func")
        return d


_ALPHA = Param("alpha", "Significance level (alpha)", "number", 0.05)
_ALT = Param(
    "alternative", "Alternative hypothesis", "select", "two-sided",
    ("two-sided", "less", "greater"),
)


def _v(help_="Numeric outcome variable"):
    return Role("values", "Variable", NUMERIC, help=help_)


REGISTRY: tuple[TestSpec, ...] = (
    # ---- descriptive ---------------------------------------------------------
    TestSpec(
        "descriptives", "Descriptive statistics", "descriptive",
        "Counts, central tendency, spread, quantiles, skew/kurtosis and 95% CI "
        "of the mean for one or more numeric columns, optionally split by a group.",
        descriptives.describe,
        roles=(
            Role("columns", "Numeric columns", NUMERIC, multiple=True),
            Role("group", "Split by (optional)", CATEGORICAL, required=False),
        ),
    ),
    # ---- normality ---------------------------------------------------------
    TestSpec(
        "shapiro_wilk", "Shapiro-Wilk normality test", "normality",
        "Tests whether a single numeric variable could plausibly have come from "
        "a normal distribution. Best power for small-to-moderate samples.",
        normality.shapiro_wilk, roles=(_v("Variable to test for normality"),),
        params=(_ALPHA,), assumptions=("Independent observations",),
    ),
    TestSpec(
        "dagostino_pearson", "D'Agostino-Pearson omnibus test", "normality",
        "Omnibus normality test combining skewness and kurtosis. Needs n >= 8.",
        normality.normaltest, roles=(_v(),), params=(_ALPHA,), min_n=8,
    ),
    TestSpec(
        "ks_normal", "Kolmogorov-Smirnov (vs normal)", "normality",
        "Compares the empirical distribution to a normal fitted from the sample "
        "mean and SD. Conservative; prefer Shapiro-Wilk for n < 5000.",
        normality.ks_normal, roles=(_v(),), params=(_ALPHA,),
    ),
    TestSpec(
        "anderson_darling", "Anderson-Darling normality test", "normality",
        "Normality test that gives extra weight to the distribution tails.",
        normality.anderson_darling, roles=(_v(),),
    ),
    # ---- one/two sample location -----------------------------------------
    TestSpec(
        "one_sample_t", "One-sample t-test", "t-test",
        "Tests whether the mean of one numeric variable differs from a fixed "
        "reference value.",
        loc.one_sample_t, roles=(_v(),),
        params=(Param("popmean", "Reference mean", "number", 0.0), _ALT, _ALPHA),
        assumptions=("Variable is approximately normal", "Independent observations"),
    ),
    TestSpec(
        "welch_t", "Welch's t-test (independent)", "t-test",
        "Compares the means of two independent groups without assuming equal "
        "variances. The safe default two-group mean comparison.",
        loc.welch_t,
        roles=(_v(), Role("group", "Grouping variable (2 levels)", CATEGORICAL)),
        params=(_ALT, _ALPHA),
        assumptions=("Each group approximately normal", "Independent observations"),
    ),
    TestSpec(
        "student_t", "Student's t-test (independent, equal var.)", "t-test",
        "Compares two independent group means assuming equal population "
        "variances. Use only when Levene's test is non-significant.",
        loc.student_t,
        roles=(_v(), Role("group", "Grouping variable (2 levels)", CATEGORICAL)),
        params=(_ALT, _ALPHA),
        assumptions=("Equal variances", "Each group approximately normal"),
    ),
    TestSpec(
        "paired_t", "Paired-samples t-test", "t-test",
        "Compares two measurements taken on the same units (e.g. before/after).",
        loc.paired_t,
        roles=(
            Role("first", "First measurement", NUMERIC),
            Role("second", "Second measurement", NUMERIC),
        ),
        params=(_ALT, _ALPHA),
        assumptions=("Difference scores approximately normal",),
    ),
    # ---- nonparametric --------------------------------------------------
    TestSpec(
        "mann_whitney", "Mann-Whitney U test", "nonparametric",
        "Rank-based comparison of two independent groups. Non-parametric "
        "alternative to Welch's t-test.",
        npar.mann_whitney,
        roles=(_v(), Role("group", "Grouping variable (2 levels)", CATEGORICAL)),
        params=(_ALT, _ALPHA),
    ),
    TestSpec(
        "wilcoxon", "Wilcoxon signed-rank test", "nonparametric",
        "Rank-based comparison of two paired measurements. Non-parametric "
        "alternative to the paired t-test.",
        npar.wilcoxon_signed_rank,
        roles=(Role("first", "First measurement", NUMERIC),
               Role("second", "Second measurement", NUMERIC)),
        params=(_ALT, _ALPHA),
    ),
    TestSpec(
        "kruskal_wallis", "Kruskal-Wallis H test", "nonparametric",
        "Rank-based comparison of three or more independent groups. "
        "Non-parametric alternative to one-way ANOVA.",
        npar.kruskal_wallis,
        roles=(_v(), Role("group", "Grouping variable (>= 2 levels)", CATEGORICAL)),
        params=(_ALPHA,),
    ),
    TestSpec(
        "friedman", "Friedman test", "nonparametric",
        "Rank-based comparison of three or more repeated measurements on the "
        "same units. Non-parametric alternative to repeated-measures ANOVA.",
        npar.friedman,
        roles=(Role("columns", "Repeated-measure columns (>= 3)", NUMERIC, multiple=True),),
    ),
    # ---- ANOVA family --------------------------------------------------
    TestSpec(
        "one_way_anova", "One-way ANOVA", "anova",
        "Tests whether the mean of a numeric variable differs across the levels "
        "of a single categorical factor.",
        anova.one_way_anova,
        roles=(_v(), Role("group", "Factor (>= 2 levels)", CATEGORICAL)),
        params=(_ALPHA,),
        assumptions=("Homogeneity of variance", "Residuals approximately normal"),
    ),
    TestSpec(
        "welch_anova", "Welch's ANOVA", "anova",
        "One-way ANOVA that does not assume equal variances across groups.",
        anova.welch_anova,
        roles=(_v(), Role("group", "Factor (>= 2 levels)", CATEGORICAL)),
    ),
    TestSpec(
        "two_way_anova", "Two-way ANOVA", "anova",
        "Tests the main effects of two categorical factors and their "
        "interaction on a numeric outcome.",
        anova.two_way_anova,
        roles=(
            _v(), Role("factor_a", "Factor A", CATEGORICAL),
            Role("factor_b", "Factor B", CATEGORICAL),
        ),
        params=(Param("anova_type", "Sum-of-squares type", "select", "2", ("1", "2", "3")),),
    ),
    TestSpec(
        "rm_anova", "Repeated-measures ANOVA", "anova",
        "One within-subjects factor: compares 2+ repeated measurements on the "
        "same units.",
        anova.rm_anova,
        roles=(Role("columns", "Condition columns (>= 2)", NUMERIC, multiple=True),),
    ),
    TestSpec(
        "ancova", "ANCOVA", "anova",
        "Compares group means on a numeric outcome after adjusting for one or "
        "more numeric covariates.",
        anova.ancova,
        roles=(
            _v(), Role("group", "Factor (>= 2 levels)", CATEGORICAL),
            Role("covariates", "Covariate(s)", NUMERIC, multiple=True),
        ),
    ),
    TestSpec(
        "posthoc_tukey", "Tukey HSD (post-hoc)", "anova",
        "All pairwise group comparisons with family-wise error control. Follows "
        "a significant one-way ANOVA (equal variances).",
        anova.posthoc_tukey,
        roles=(_v(), Role("group", "Factor", CATEGORICAL)), params=(_ALPHA,),
    ),
    TestSpec(
        "posthoc_games_howell", "Games-Howell (post-hoc)", "anova",
        "All pairwise comparisons that do not assume equal variances. Follows a "
        "significant Welch's ANOVA.",
        anova.posthoc_games_howell,
        roles=(_v(), Role("group", "Factor", CATEGORICAL)), params=(_ALPHA,),
    ),
    # ---- correlation --------------------------------------------------
    TestSpec(
        "pearson", "Pearson correlation", "correlation",
        "Strength and direction of the linear association between two numeric "
        "variables.",
        correlation.pearson,
        roles=(Role("x", "Variable X", NUMERIC), Role("y", "Variable Y", NUMERIC)),
        params=(_ALPHA,),
        assumptions=("Linear relationship", "Bivariate normality"),
    ),
    TestSpec(
        "spearman", "Spearman rank correlation", "correlation",
        "Strength and direction of the monotonic association between two "
        "variables. Robust to outliers and non-linearity.",
        correlation.spearman,
        roles=(Role("x", "Variable X", NUMERIC), Role("y", "Variable Y", NUMERIC)),
    ),
    TestSpec(
        "kendall", "Kendall's tau", "correlation",
        "Rank concordance between two variables. Preferred over Spearman for "
        "small samples or many ties.",
        correlation.kendall,
        roles=(Role("x", "Variable X", NUMERIC), Role("y", "Variable Y", NUMERIC)),
    ),
    TestSpec(
        "correlation_matrix", "Correlation matrix", "correlation",
        "Pairwise correlations (and p-values) among several numeric variables.",
        correlation.correlation_matrix,
        roles=(Role("columns", "Numeric columns (>= 2)", NUMERIC, multiple=True),),
        params=(Param("method", "Method", "select", "pearson",
                      ("pearson", "spearman", "kendall")),),
    ),
    # ---- regression --------------------------------------------------
    TestSpec(
        "linear_regression", "Linear regression (OLS)", "regression",
        "Models a numeric outcome as a linear function of one or more numeric "
        "predictors; reports coefficients, R^2 and diagnostics.",
        regression.linear_regression,
        roles=(
            Role("outcome", "Outcome (Y)", NUMERIC),
            Role("predictors", "Predictor(s) (X)", NUMERIC, multiple=True),
        ),
        assumptions=("Linearity", "Independent, homoscedastic, normal residuals"),
    ),
    TestSpec(
        "logistic_regression", "Binary logistic regression", "regression",
        "Models the probability of a binary outcome from one or more numeric "
        "predictors; reports odds ratios.",
        regression.logistic_regression,
        roles=(
            Role("outcome", "Binary outcome", ANY),
            Role("predictors", "Predictor(s)", NUMERIC, multiple=True),
        ),
    ),
    # ---- categorical --------------------------------------------------
    TestSpec(
        "chi_square_independence", "Chi-square test of independence", "categorical",
        "Tests whether two categorical variables are associated, using a "
        "contingency table.",
        categorical.chi_square_independence,
        roles=(
            Role("rows", "Row variable", CATEGORICAL),
            Role("columns", "Column variable", CATEGORICAL),
        ),
        params=(Param("yates", "Yates continuity correction (2x2)", "bool", True),),
        assumptions=("Expected count >= 5 in most cells", "Independent observations"),
    ),
    TestSpec(
        "chi_square_gof", "Chi-square goodness-of-fit", "categorical",
        "Tests whether the category frequencies of one variable match an "
        "expected (default: uniform) distribution.",
        categorical.chi_square_goodness_of_fit,
        roles=(Role("values", "Categorical variable", CATEGORICAL),),
        params=(Param("expected", "Expected proportions (comma-separated, optional)",
                      "list", None),),
    ),
    TestSpec(
        "fisher_exact", "Fisher's exact test (2x2)", "categorical",
        "Exact test of association for a 2x2 table. Valid for small samples "
        "where chi-square is unreliable.",
        categorical.fisher_exact,
        roles=(Role("rows", "Row variable (2 levels)", CATEGORICAL),
               Role("columns", "Column variable (2 levels)", CATEGORICAL)),
        params=(_ALT,),
    ),
    TestSpec(
        "mcnemar", "McNemar's test", "categorical",
        "Tests for a change in a paired binary measurement (e.g. same subjects "
        "classified before and after).",
        categorical.mcnemar_test,
        roles=(Role("first", "Before (binary)", CATEGORICAL),
               Role("second", "After (binary)", CATEGORICAL)),
    ),
    # ---- variance --------------------------------------------------
    TestSpec(
        "levene", "Levene's test (equal variances)", "variance",
        "Tests whether two or more groups have equal variance. Robust to "
        "non-normality; use before Student's t-test / classic ANOVA.",
        variance_tests.levene,
        roles=(_v(), Role("group", "Grouping variable", CATEGORICAL)),
        params=(Param("center", "Center", "select", "median", ("median", "mean", "trimmed")),
                _ALPHA),
    ),
    TestSpec(
        "bartlett", "Bartlett's test (equal variances)", "variance",
        "Tests equality of variance across groups assuming normality. More "
        "powerful than Levene when data are normal.",
        variance_tests.bartlett,
        roles=(_v(), Role("group", "Grouping variable", CATEGORICAL)),
        params=(_ALPHA,),
    ),
    # ---- multivariate / data reduction ---------------------------------
    TestSpec(
        "pca", "Principal component analysis", "multivariate",
        "Reduces several correlated numeric variables to a small number of "
        "uncorrelated components that capture most of the variance.",
        mv.pca,
        roles=(Role("columns", "Numeric columns (>= 2)", NUMERIC, multiple=True),),
        params=(
            Param("standardize", "Standardize variables first", "bool", True),
            Param("n_components", "Components to retain (blank = all)", "number", None),
        ),
    ),
    TestSpec(
        "factor_analysis", "Factor analysis", "multivariate",
        "Models several observed variables as linear combinations of a smaller "
        "number of unobserved (latent) factors plus unique variance.",
        mv.factor_analysis,
        roles=(Role("columns", "Numeric columns (>= 3)", NUMERIC, multiple=True),),
        params=(
            Param("n_factors", "Number of factors", "number", 2),
            Param("method", "Extraction method", "select", "pa", ("pa", "ml"),
                  "pa = principal axis, ml = maximum likelihood"),
            Param("rotation", "Rotation", "select", "varimax", ("varimax", "none")),
        ),
        assumptions=("Variables are linearly related", "Adequate sample size relative to variable count"),
    ),
    TestSpec(
        "canonical_correlation", "Canonical correlation analysis", "multivariate",
        "Finds linear combinations of two variable sets that are maximally "
        "correlated with each other.",
        mv.canonical_correlation,
        roles=(
            Role("set_a", "Variable set A (>= 2)", NUMERIC, multiple=True),
            Role("set_b", "Variable set B (>= 2)", NUMERIC, multiple=True),
        ),
        assumptions=("Linear relationships", "Multivariate normality (for the significance test)"),
    ),
    TestSpec(
        "correspondence_analysis", "Correspondence analysis", "multivariate",
        "Maps the categories of two categorical variables into a low-dimensional "
        "space that visualizes their association, from a contingency table.",
        mv.correspondence_analysis,
        roles=(
            Role("rows", "Row variable", CATEGORICAL),
            Role("columns", "Column variable", CATEGORICAL),
        ),
    ),
    TestSpec(
        "mds", "Multidimensional scaling", "multivariate",
        "Places cases in a low-dimensional space so that distances between "
        "points approximate their dissimilarity in the original variables.",
        mv.mds,
        roles=(
            Role("columns", "Numeric columns (>= 2)", NUMERIC, multiple=True),
            Role("group", "Color by (optional)", CATEGORICAL, required=False),
        ),
        params=(
            Param("standardize", "Standardize variables first", "bool", True),
            Param("n_components", "Dimensions to retain", "number", 2),
        ),
    ),
    # ---- clustering -----------------------------------------------------
    TestSpec(
        "hierarchical_cluster", "Hierarchical cluster analysis", "clustering",
        "Agglomerative clustering that builds a tree (dendrogram) of nested "
        "groupings of cases, cut into a chosen number of clusters.",
        cluster_analysis.hierarchical_cluster,
        roles=(Role("columns", "Numeric columns (>= 2)", NUMERIC, multiple=True),),
        params=(
            Param("method", "Linkage method", "select", "ward",
                  ("ward", "complete", "average", "single")),
            Param("n_clusters", "Number of clusters to cut", "number", 3),
            Param("standardize", "Standardize variables first", "bool", True),
        ),
    ),
    TestSpec(
        "kmeans_cluster", "K-means cluster analysis", "clustering",
        "Partitions cases into k clusters by minimizing within-cluster "
        "variance around iteratively updated centers.",
        cluster_analysis.kmeans_cluster,
        roles=(Role("columns", "Numeric columns (>= 2)", NUMERIC, multiple=True),),
        params=(
            Param("k", "Number of clusters (k)", "number", 3),
            Param("standardize", "Standardize variables first", "bool", True),
            Param("seed", "Random seed", "number", 0),
        ),
    ),
    # ---- classification ---------------------------------------------------
    TestSpec(
        "discriminant_analysis", "Discriminant analysis", "classification",
        "Finds the linear combination(s) of predictors that best separate "
        "groups, and classifies cases by their nearest group centroid.",
        discriminant.discriminant_analysis,
        roles=(
            Role("group", "Grouping variable (>= 2 levels)", CATEGORICAL),
            Role("predictors", "Predictor(s)", NUMERIC, multiple=True),
        ),
        assumptions=("Multivariate normality within groups", "Homogeneity of covariance matrices"),
    ),
    TestSpec(
        "general_discriminant_analysis", "General discriminant analysis", "classification",
        "Discriminant analysis with predictors first adjusted for one or more "
        "continuous covariates (ANCOVA-style), then discriminated as usual.",
        discriminant.general_discriminant_analysis,
        roles=(
            Role("group", "Grouping variable (>= 2 levels)", CATEGORICAL),
            Role("predictors", "Predictor(s)", NUMERIC, multiple=True),
            Role("covariates", "Covariate(s) (optional)", NUMERIC, multiple=True, required=False),
        ),
        assumptions=("Multivariate normality within groups", "Homogeneity of covariance matrices",
                     "Linear predictor-covariate relationship"),
    ),
    TestSpec(
        "classification_tree", "Classification tree", "classification",
        "Recursively splits cases on predictor thresholds to classify a "
        "categorical outcome; reports the tree, importances and accuracy.",
        classification_tree.classification_tree,
        roles=(
            Role("outcome", "Outcome (categorical)", ANY),
            Role("predictors", "Predictor(s)", NUMERIC, multiple=True),
        ),
        params=(
            Param("max_depth", "Max tree depth", "number", 3),
            Param("min_samples_leaf", "Min samples per leaf", "number", 5),
            Param("criterion", "Split criterion", "select", "gini", ("gini", "entropy", "log_loss")),
        ),
    ),
    # ---- reliability ------------------------------------------------------
    TestSpec(
        "reliability_analysis", "Reliability / item analysis", "reliability",
        "Cronbach's alpha and item-total statistics for a set of items "
        "measuring the same underlying construct (e.g. a survey scale).",
        reliability.reliability_analysis,
        roles=(Role("columns", "Items (>= 3 numeric columns)", NUMERIC, multiple=True),),
    ),
)

_BY_ID: dict[str, TestSpec] = {spec.id: spec for spec in REGISTRY}

FAMILIES: tuple[str, ...] = (
    "descriptive", "normality", "t-test", "nonparametric",
    "anova", "correlation", "regression", "categorical", "variance",
    "multivariate", "clustering", "classification", "reliability",
)


def get_spec(test_id: str) -> TestSpec:
    try:
        return _BY_ID[test_id]
    except KeyError:
        raise DataError(f"Unknown test id: {test_id!r}") from None


def get_registry() -> dict[str, Any]:
    """JSON-serializable description of every test, grouped by family."""
    return {
        "version": 1,
        "families": list(FAMILIES),
        "tests": [spec.to_dict() for spec in REGISTRY],
    }


def _coerce_frame(data: Any) -> pd.DataFrame:
    if isinstance(data, pd.DataFrame):
        return data
    if isinstance(data, dict):
        return pd.DataFrame({k: list(v) for k, v in data.items()})
    raise DataError("data must be a pandas DataFrame or a {column: values} mapping.")


def run_test(
    test_id: str,
    data: Any,
    roles: dict[str, Any],
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute one test and return its :meth:`TestResult.to_dict` payload.

    Raises :class:`DataError` (a ``ValueError``) for bad inputs; the worker
    turns that into a structured error message for the UI.
    """
    spec = get_spec(test_id)
    frame = _coerce_frame(data)
    params = dict(params or {})
    # apply declared param defaults
    for p in spec.params:
        params.setdefault(p.key, p.default)
    result = spec.func(frame, roles, params)
    return result.to_dict()
