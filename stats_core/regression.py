"""OLS linear regression (simple / multiple) and binary logistic regression."""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

from stats_core._util import DataError, eta_squared_magnitude, fmt_p, significance_phrase
from stats_core.results import AssumptionCheck, EffectSize, ResultTable, TestResult


def _design(frame: pd.DataFrame, y_col: str, x_cols: list[str]) -> tuple[np.ndarray, np.ndarray, list[str]]:
    if not x_cols:
        raise DataError("Select at least one predictor.")
    keep = [y_col, *x_cols]
    sub = frame[keep].apply(pd.to_numeric, errors="coerce").dropna()
    if len(sub) <= len(x_cols) + 1:
        raise DataError("Not enough complete rows for the number of predictors.")
    y = sub[y_col].to_numpy(float)
    X = sub[x_cols].to_numpy(float)
    return y, X, x_cols


def linear_regression(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    y_col = roles["outcome"]
    x_cols = roles.get("predictors") or []
    if isinstance(x_cols, str):
        x_cols = [x_cols]
    y, X, names = _design(frame, y_col, x_cols)
    Xc = sm.add_constant(X, has_constant="add")
    model = sm.OLS(y, Xc).fit()

    coef_rows = []
    for i, nm in enumerate(["(intercept)", *names]):
        coef_rows.append([
            nm, float(model.params[i]), float(model.bse[i]),
            float(model.tvalues[i]), float(model.pvalues[i]),
            float(model.conf_int()[i][0]), float(model.conf_int()[i][1]),
        ])
    resid = model.resid
    sh_p = stats.shapiro(resid).pvalue if 3 <= len(resid) <= 5000 else float("nan")
    # Breusch-Pagan for heteroscedasticity
    try:
        bp_p = sm.stats.diagnostic.het_breuschpagan(resid, Xc)[1]
    except Exception:  # pragma: no cover - defensive
        bp_p = float("nan")

    f_p = float(model.f_pvalue)
    return TestResult(
        test_id="linear_regression",
        test_name="Linear regression (OLS)",
        summary=(
            f"{y_col} ~ {' + '.join(names)}: R^2 = {model.rsquared:.3f}, "
            f"adj. R^2 = {model.rsquared_adj:.3f}, "
            f"F({int(model.df_model)}, {int(model.df_resid)}) = {model.fvalue:.3f}, "
            f"{fmt_p(f_p)} ({significance_phrase(f_p)})."
        ),
        apa=f"R^2 = {model.rsquared:.3f}, F({int(model.df_model)}, {int(model.df_resid)}) "
        f"= {model.fvalue:.3f}, {fmt_p(f_p)}",
        statistic={
            "rSquared": float(model.rsquared),
            "rSquaredAdj": float(model.rsquared_adj),
            "F": float(model.fvalue),
            "dfModel": float(model.df_model),
            "dfResid": float(model.df_resid),
            "aic": float(model.aic),
            "bic": float(model.bic),
        },
        p_value=f_p,
        effect_sizes=[EffectSize("R^2", float(model.rsquared), None, None,
                                 eta_squared_magnitude(float(model.rsquared)))],
        assumptions=[
            AssumptionCheck("Normality of residuals",
                            None if np.isnan(sh_p) else bool(sh_p >= 0.05),
                            f"Shapiro-Wilk {fmt_p(sh_p)}" if not np.isnan(sh_p) else "not assessed",
                            p_value=None if np.isnan(sh_p) else float(sh_p)),
            AssumptionCheck("Homoscedasticity (Breusch-Pagan)",
                            None if np.isnan(bp_p) else bool(bp_p >= 0.05),
                            f"Breusch-Pagan {fmt_p(bp_p)}" if not np.isnan(bp_p) else "not assessed",
                            p_value=None if np.isnan(bp_p) else float(bp_p)),
        ],
        tables=[ResultTable(
            "Coefficients",
            ["term", "estimate", "std_error", "t", "p", "ci95_low", "ci95_high"],
            coef_rows,
        )],
        plot_spec=(
            {
                "kind": "scatter",
                "data": {"x": X[:, 0].tolist(), "y": y.tolist()},
                "encoding": {"x": {"field": "x", "title": names[0]}, "y": {"field": "y", "title": y_col}},
                "regression": True,
            }
            if len(names) == 1
            else {
                "kind": "scatter",
                "data": {"x": model.fittedvalues.tolist(), "y": resid.tolist()},
                "encoding": {"x": {"field": "x", "title": "fitted"}, "y": {"field": "y", "title": "residual"}},
                "rule": 0,
            }
        ),
    )


def logistic_regression(frame: pd.DataFrame, roles: dict, params: dict) -> TestResult:
    y_col = roles["outcome"]
    x_cols = roles.get("predictors") or []
    if isinstance(x_cols, str):
        x_cols = [x_cols]
    if not x_cols:
        raise DataError("Select at least one predictor.")
    keep = [y_col, *x_cols]
    sub = frame[keep].dropna().copy()
    for c in x_cols:
        sub[c] = pd.to_numeric(sub[c], errors="coerce")
    sub = sub.dropna()

    raw = sub[y_col]
    levels = sorted(pd.unique(raw).tolist(), key=lambda v: str(v))
    if len(levels) != 2:
        raise DataError(
            f"Logistic regression needs a binary outcome; {y_col!r} has "
            f"{len(levels)} distinct values."
        )
    y = (raw == levels[1]).astype(int).to_numpy()
    raw_X = sub[x_cols].to_numpy(float)
    # standardize predictors: keeps the optimizer well-conditioned when columns
    # span very different scales; odds ratios are then "per 1 SD increase".
    mu = raw_X.mean(axis=0)
    sd = raw_X.std(axis=0, ddof=0)
    sd[sd == 0] = 1.0
    X = sm.add_constant((raw_X - mu) / sd, has_constant="add")
    try:
        model = sm.Logit(y, X).fit(disp=False, maxiter=200)
    except Exception as exc:  # pragma: no cover - perfect separation etc.
        raise DataError(f"Logistic regression failed to fit: {exc}") from None

    names = ["(intercept)", *x_cols]
    ci = model.conf_int()
    rows = [
        [nm, float(model.params[i]), float(np.exp(model.params[i])),
         float(model.bse[i]), float(model.pvalues[i]),
         float(np.exp(ci[i][0])), float(np.exp(ci[i][1]))]
        for i, nm in enumerate(names)
    ]
    return TestResult(
        test_id="logistic_regression",
        test_name="Binary logistic regression",
        summary=(
            f"P({y_col} = {levels[1]!r}) ~ {' + '.join(x_cols)}: "
            f"pseudo R^2 (McFadden) = {model.prsquared:.3f}; "
            f"LLR {fmt_p(model.llr_pvalue)} ({significance_phrase(model.llr_pvalue)})."
        ),
        apa=f"McFadden R^2 = {model.prsquared:.3f}, LLR chi^2({int(model.df_model)}) "
        f"= {model.llr:.3f}, {fmt_p(model.llr_pvalue)}",
        statistic={
            "pseudoRSquared": float(model.prsquared),
            "logLikelihood": float(model.llf),
            "llr": float(model.llr),
            "aic": float(model.aic),
        },
        p_value=float(model.llr_pvalue),
        effect_sizes=[EffectSize("McFadden pseudo R^2", float(model.prsquared))],
        assumptions=[
            AssumptionCheck("Binary outcome", True, f"Modelled P(outcome = {levels[1]!r})."),
            AssumptionCheck("Linearity of the logit", None,
                            "Assumed for continuous predictors; check with residual plots."),
        ],
        tables=[ResultTable(
            "Coefficients (odds ratios per 1 SD)",
            ["term", "log_odds", "odds_ratio", "std_error", "p", "or_ci95_low", "or_ci95_high"],
            rows,
        )],
    ).add_note("Predictors were standardized; odds ratios are per one standard "
               "deviation increase in each predictor.")
