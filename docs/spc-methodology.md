# SPC Methodology

The statistical basis for the control charts, the Phase I workflow and the capability
indices in this app. Ported from the SPC-analysis project and updated where the
implementation deliberately differs — every such deviation is called out in §8.

---

## 1. Overview

This implements **Phase I Statistical Process Control** for individual measurements, using the
**I-MR (Individuals and Moving Range)** chart pair.

Phase I is retrospective. Given a historical dataset, the goal is to establish verified, stable
control limits that can then drive Phase II — ongoing monitoring. The central difficulty is that
historical data usually contains out-of-control periods, and those periods must not be allowed to
define what "normal" looks like.

---

## 2. Chart type: I-MR

Use I-MR when there is one measurement per time period — one sample per shift, per day, per
batch. Rational subgroups of size n = 1. Common in chemical, pharmaceutical, environmental and
discrete-part manufacturing.

The moving range of span 2 is the absolute successive difference:

$$MR_i = \lvert x_i - x_{i-1} \rvert$$

It estimates short-term (within-subgroup) variation. **Row order is the time axis** — the app
never re-sorts your rows, and an optional label column supplies display labels only. Sorting by a
label would silently rewrite the sequence the moving ranges are computed from.

---

## 3. Control limit formulas

Short-term standard deviation, using the span-2 unbiasing constant $d_2 = 1.128$:

$$\hat{\sigma}_{\text{within}} = \frac{\overline{MR}}{d_2}$$

**Individuals chart**

| Line | Formula |
|---|---|
| UAL (action) | $\bar{x} + 3\hat{\sigma}_{\text{within}}$ |
| UWL (warning) | $\bar{x} + 2\hat{\sigma}_{\text{within}}$ |
| CL | $\bar{x}$ |
| LWL (warning) | $\bar{x} - 2\hat{\sigma}_{\text{within}}$ |
| LAL (action) | $\bar{x} - 3\hat{\sigma}_{\text{within}}$ |

**Moving range chart**

| Line | Formula |
|---|---|
| UAL | $D_4 \cdot \overline{MR}$, with $D_4 = 3.267$ at $n = 2$ |
| CL | $\overline{MR}$ |
| LAL | $0$ — always, because $D_3 = 0$ at $n = 2$ |

Constants for subgroup sizes 2–25 ($d_2$, $d_3$, $D_3$, $D_4$, $A_2$, $A_3$, $B_3$, $B_4$, $c_4$) are
tabulated in `stats_core/spc/constants.py`, following ASTM E2587 / ISO 7870-2.

### Subgrouped charts

With $n > 1$ measurements per period, sigma is estimated from within-subgroup spread:

$$\text{X-bar/R:}\quad \hat{\sigma}_{\text{within}} = \frac{\overline{R}}{d_2}
\qquad\qquad
\text{X-bar/S:}\quad \hat{\sigma}_{\text{within}} = \frac{\bar{s}}{c_4}$$

and the means chart uses the standard error of a subgroup mean:

$$\bar{\bar{x}} \pm 3\,\frac{\hat{\sigma}_{\text{within}}}{\sqrt{n}}
\quad\text{(action)}\qquad
\bar{\bar{x}} \pm 2\,\frac{\hat{\sigma}_{\text{within}}}{\sqrt{n}}
\quad\text{(warning)}$$

This is algebraically identical to the classic shortcut factors, $A_2 = 3/(d_2\sqrt{n})$ and
$A_3 = 3/(c_4\sqrt{n})$, and the implementation is pinned against both by test. The
$\hat{\sigma}/\sqrt{n}$ form is used because it also yields the $2\sigma$ warning lines, which
$A_2$ and $A_3$ do not provide.

Spread charts run from $D_3\overline{R}$ to $D_4\overline{R}$, and from $B_3\bar{s}$ to
$B_4\bar{s}$. **The lower limit is real from $n = 7$**,
where D₃ and B₃ become non-zero, and is checked — a subgroup whose spread is implausibly small
usually signals non-independent measurements or massaged data, not an unusually good hour.

Choose R for n ≤ 8 and S from n ≥ 9, where the range starts discarding too much information; the
app emits a note when a range chart is used on large subgroups. Subgroups must be equal-sized,
since the constants are defined per n.

---

## 4. Rules: Oakland's four, and two named alternatives

Rules 1–4 apply to the individuals chart; rules 1–2 apply to the moving range chart. These are
**Oakland's rule set** — what this app has always used, and the default.

### Rule 1 — Action limits
Any single point beyond $\pm 3\sigma$. Under normality the false-alarm rate on a single point is $\approx 0.27\%$.

### Rule 2 — Warning zone (2-of-3)
2 or more of any 3 consecutive points in the *same* warning zone (between $\pm 2\sigma$ and $\pm 3\sigma$ on one
side). Upper and lower zones are counted separately — two points high and one low is not a
signal, because the two sides indicate opposite shifts.

This is the Western Electric formulation. It is preferred over the simpler "no point in the
warning zone" check because it controls the false-alarm rate while staying sensitive to real
shifts. Both `k` and the window are configurable.

### Rule 3 — Run
$k$ or more consecutive points on the same side of the centre line (default 8). A sustained shift
too small to trip Rule 1 shows up as a run. Eight coin flips landing the same way has probability
$(1/2)^7 \approx 0.78\%$.

> Nelson (1984) uses k = 9; Western Electric uses k = 8. The default here is 8, configurable.

### Rule 4 — Trend
$k$ or more consecutive points strictly rising or falling (default 6). $k$ points define $k - 1$
successive differences, all of which must share a sign; a tie breaks the trend. A monotonic run of
6 has probability $(1/2)^5 \approx 3\%$.

### Flagging convention
Run- and trend-based rules (3 and 4) flag the point that **completes** the window, plus any
subsequent point while the run continues — not every point in the run retrospectively. An 8-point
run at k = 8 flags one point; a 9-point run flags two. This keeps a single long drift from filling
the decision table with a dozen rows describing one event. Rules 1 and 2 flag the offending point
itself. Every comparison is strict, so a point sitting exactly on a limit or the centre line is
not a violation.

### Named alternatives: Western Electric and Nelson

Both build on the same **zone** decomposition of the chart — C (0–1σ), B (1–2σ), A (2–3σ), and
beyond — implemented once in `stats_core/spc/rulesets.py` and shared by every chart.

**Western Electric (1956)**, 4 fixed rules: point beyond 3σ; 2-of-3 beyond 2σ on one side; 4-of-5
beyond 1σ on one side; a run of 8. Unlike Oakland's set, these thresholds are not configurable —
they are the published standard.

**Nelson (1984)**, 8 rules: WECO's four action tests, plus a run of 9 (rather than 8), a trend of
6, 14 points alternating up and down (over-adjustment), and two pattern tests worth naming because
they catch something the others cannot:

- **Stratification** — 15 consecutive points all within 1σ. Counter-intuitively, spread that is *too small* is a signal: it usually means the subgroups are not independent, or the data has been averaged or massaged before charting.
- **Mixture** — 8 consecutive points all beyond 1σ on either side, none in zone C. The signature of two distinct populations (two machines, two operators) being plotted as one series.

More rules raise sensitivity and the false-alarm rate together. On a genuinely stable process,
simulation puts Western Electric at roughly 1.4 false signals per 100 points and Nelson at 1.9 —
confirmed against this implementation, not merely asserted. Choose the set your organisation
standardises on.

---

## 5. Phase I — the two-pass workflow

```
PASS 1
  1. Compute x̄, MR̄, σ̂ and all control lines from the full dataset (NaN excluded)
  2. Apply rules 1–4 to the I chart and rules 1–2 to the MR chart
  3. Present every flagged point to the analyst
  4. For each: the analyst decides remove / retain, and must document an
     assignable cause for any removal
  5. If nothing is removed, the pass-1 limits are the baseline — done

PASS 2  (only if points were removed)
  6. Drop the removed points
  7. Recompute the limits on what remains, excluding bridging moving ranges
  8. Re-apply the rules; any remaining violations are reported, not acted on
```

### Why two passes, not iteration to zero

Oakland (§5.4) warns that iterating until no violations remain produces **"utopia limits"** —
each removal tightens the limits, which exposes fresh violations, which triggers more removals,
until the baseline no longer describes the real process. Capping at two passes stops the cascade.

### The assignable-cause requirement

A point may be removed **only** when the analyst can document a specific, verifiable process-level
cause — "Chiller unit tripped at 02:30, maintenance log WO-2024-1142". A statistical rule
violation is *necessary but not sufficient*. This aligns with Oakland §5.1/§5.4, AIAG PPAP 4th ed.
(baseline studies must document sources of variation), and FDA 21 CFR Part 211 data-integrity
requirements.

The app enforces this in two places: the Studio will not certify while any removal lacks a cause,
and `finalise()` raises `AssignableCauseRequired` regardless of what the UI does. The UI check is
a courtesy; the engine check is the guarantee.

### Bridging moving ranges

When points are removed from the middle of a series, the moving range computed *across* the gap
spans observations that were never adjacent in the real process. Including those ranges in MR̄
corrupts σ̂_within, which is the entire basis of the control limits. Pass 2 therefore masks them
out (`bridging_mr_mask`).

Note this does **not** reliably make σ̂ smaller — it removes an invalid measurement, and the
direction depends on the data. If the bridging range happens to be the smallest one present,
excluding it raises MR̄. Both directions are covered by tests.

Rows containing NaN are not "removed" in this sense — they were never observations — so adjacency
is judged among the rows that actually hold a measurement.

### Over-pruning

Above a **20 %** removal rate the app warns that the baseline period itself is suspect. The right
response is to reselect the period, not to keep pruning. Below about 20 retained points the limits
are reported as provisional.

---

## 6. Attribute charts: p, np, c, u

Every chart so far plots a **measurement** and estimates sigma from it. Attribute charts plot a
**count**, and their limits come from the count's own distribution instead.

| Chart | Plots | Distribution | Sample size |
|---|---|---|---|
| **p** | proportion defective | binomial | may vary |
| **np** | number defective | binomial | constant |
| **c** | defect count | Poisson | one fixed unit |
| **u** | defects per unit | Poisson | may vary |

**Defective vs. defect.** A defective is a unit that failed inspection; a defect is one fault, and
a unit can carry more than one. Counting defectives caps the count at the sample size (binomial);
counting defects does not (Poisson). The two chart families are not interchangeable, and using the
wrong one produces limits that are wrong in a way no amount of data will reveal.

$$p\text{-chart: } \quad \bar{p} \pm 3\sqrt{\frac{\bar{p}(1-\bar{p})}{n_i}}
\qquad\qquad
np\text{-chart: } \quad n\bar{p} \pm 3\sqrt{n\bar{p}(1-\bar{p})}$$

$$c\text{-chart: } \quad \bar{c} \pm 3\sqrt{\bar{c}}
\qquad\qquad
u\text{-chart: } \quad \bar{u} \pm 3\sqrt{\frac{\bar{u}}{n_i}}$$

The subscript $i$ on $n$ matters: when the sample size varies between points, **so do the limits**
on the p and u charts — a proportion estimated from 1000 units is far better determined than one
from 20, and constant limits would flag the small samples relentlessly. The app draws a varying
limit as a stepped boundary rather than a straight line, so the changing precision is visible.

Both limit formulas assume the count is close enough to normal for a $\pm 3\sigma$ approximation
to hold, which needs an expected count of roughly 5 or more. Below that — a rare defect, a small
sample — the app flags the limits as approximate; the lower limit is frequently pinned at zero in
this regime, so the chart can then only ever signal an *increase*, never a decrease.

---

## 7. Normality pre-check

Shewhart limits assume approximately normal individual measurements; severe non-normality inflates
the false-alarm rate.

| n | Test |
|---|---|
| 3 – 5000 | Shapiro-Wilk |
| > 5000 | Anderson-Darling (Shapiro-Wilk is not valid above 5000) |

The result is **advisory** — it annotates the analysis and never blocks it. On confirmed
non-normality, consider a transformation (log, Box-Cox), or investigate whether the data mixes
sub-populations (two machines, two shifts, two material lots). Splitting is usually better than
transforming.

---

## 8. Process capability

$\hat{\sigma}_{\text{within}}$ (short-term, from $\overline{MR}/d_2$) captures only inherent
point-to-point variation and drives $C_p$ and $C_{pk}$. $\hat{\sigma}_{\text{overall}}$ (the
sample SD of retained values) also captures drift and shifts, and drives $P_p$ and $P_{pk}$.

$$\begin{aligned}
C_p   &= \frac{USL - LSL}{6\,\hat{\sigma}_{\text{within}}}
&\qquad
C_{pk} &= \frac{\min\!\left[\,USL - \bar{x},\; \bar{x} - LSL\,\right]}{3\,\hat{\sigma}_{\text{within}}} \\[6pt]
P_p   &= \frac{USL - LSL}{6\,\hat{\sigma}_{\text{overall}}}
&\qquad
P_{pk} &= \frac{\min\!\left[\,USL - \bar{x},\; \bar{x} - LSL\,\right]}{3\,\hat{\sigma}_{\text{overall}}}
\end{aligned}$$

The relative precision index is the same quantity as $C_p$, written from the half-tolerance
$T = (USL - LSL)/2$:

$$RPI = \frac{2T}{6\,\hat{\sigma}_{\text{within}}} = \frac{USL - LSL}{6\,\hat{\sigma}_{\text{within}}} \equiv C_p$$

| Index | Minimum | Enterprise target | Critical characteristics |
|---|---|---|---|
| $C_p$ | 1.00 | 1.33 | 1.67 |
| $C_{pk}$ | 1.00 | 1.33 | 1.67 |

Two gaps to read:

- **$C_p$ vs $C_{pk}$.** $C_p \ge 1.33$ with $C_{pk} < 1.00$ means the spread is adequate but the process is off-centre. Fix the set point, not the variation. The app flags $C_{pk}/C_p < 0.85$.
- **$C_p$ vs $P_p$.** $P_p$ materially below $C_p$ means long-term drift between subgroups. A healthy $C_{pk}$ alone is insufficient; the source of the drift has to be found.

Capability assumes a stable process. Computed on out-of-control data the numbers describe the past
but predict nothing, and the app says so prominently rather than refusing to compute — analysts
routinely need the figure before a baseline is certified.

### Interval estimate for Cpk

Every index above is a point estimate from a finite sample, and Cpk's sampling variability is
larger than its usual three decimal places suggest. An approximate 95% interval (Bissell, 1990):

$$SE(C_{pk}) \approx \sqrt{\frac{1}{9n} + \frac{C_{pk}^2}{2(n-1)}}
\qquad\qquad
C_{pk} \pm 1.96 \cdot SE(C_{pk})$$

At $n = 30$ a reported $C_{pk}$ of 1.33 is compatible with anything from roughly 1.0 to 1.7 — worth
knowing before treating the third decimal as meaningful.

### Cpm: penalising distance from target

Cp and Cpk both treat the tolerance band as the only thing that matters — a process centred
anywhere inside it scores the same as one dead on nominal, provided the spread is equal. Taguchi's
$C_{pm}$ folds a target $T$ into the denominator:

$$C_{pm} = \frac{USL - LSL}{6\sqrt{\sigma^2 + (\mu - T)^2}}$$

so drifting off-target costs capability even while remaining on-spec. Use it where being close to
nominal has value in itself — typically assembly, where individually-in-spec parts still stack
their deviations from nominal into a compounded error.

### Non-normal data: percentile method and Box-Cox

Cp and Cpk convert a sigma distance into a tail probability, which is only valid under normality.
On skewed data that conversion is usually **optimistic** — the long tail is normally the side
producing defects, and a normal-theory estimate underweights it. Two honest alternatives:

**Percentile capability (ISO 22514-2).** Replace the $\pm 3\sigma$ span with the *observed*
0.135th and 99.865th percentiles — the points a normal distribution would place three sigma out:

$$P_p^{\text{(pctl)}} = \frac{USL - LSL}{x_{99.865} - x_{0.135}}$$

No distributional assumption, at the cost of estimating an extreme percentile from a finite
sample, which is inherently noisy with only a few dozen points.

**Box-Cox transform.** Search for a power $\lambda$ such that $x^{(\lambda)}$ is closer to normal,
report the Shapiro-Wilk p-value before and after, and let the analyst judge whether transforming
and re-running the standard formulas in the transformed space is worthwhile.

Neither is applied automatically — the app surfaces both as options once the normality pre-check
fails, and states plainly that the default Cp/Cpk are questionable on that data rather than
silently reporting an optimistic number.

---

## 9. Phase II: monitoring against a frozen baseline

Phase I and Phase II ask different questions. Phase I: *was this process stable, and what are its
limits?* Phase II: *is it still behaving like that baseline?*

The distinction that matters is what happens to the limits. Phase II **never recomputes them from
the new data** — they are supplied from a certified Phase I baseline (its centre line and
$\hat{\sigma}_{\text{within}}$) and applied unchanged. Recomputing would be self-defeating: a
process that has drifted would redraw its own limits around the new mean and appear perfectly in
control, which is precisely the failure Phase II exists to catch.

Any of the three rule sets (§4) can be applied to the incoming stream. A sustained shift is also
reported directly, in sigma units:

$$\text{shift} = \frac{\bar{x}_{\text{new}} - \bar{x}_{\text{baseline}}}{\hat{\sigma}_{\text{within}}}$$

A shift beyond about 1$\sigma$ that persists is the app's cue that the baseline no longer
describes the process — the right response is to investigate, then re-establish Phase I on new
data, not to keep monitoring against limits that no longer apply.

---

## 10. Deliberate deviations from the original tool

Recorded so nobody has to rediscover them by diffing against
[SPC-analysis](https://github.com/jlleongarcia/SPC-analysis).

**At default thresholds the two implementations agree exactly** — verified across 300 randomised
series covering every control line, all four rules and the MR rules.

1. **Rule 2's `k`/`window` now reach the MR chart.** The original accepted these parameters on `apply_mr_rules` but never forwarded them from its Phase I pass, so the MR chart stayed at 2-of-3 however Rule 2 was configured. That read as missing wiring rather than intent: the setting is presented as one global threshold. At the default 2-of-3 the behaviour is identical.
2. **`mr_uwl` is a heuristic, not a published formula.** There is no standard warning limit for a range chart — the range statistic is skewed, so a "2σ" line has no clean closed form the way it does on the symmetric individuals chart. The value used is a linear interpolation two-thirds of the way from CL to UCL, $\overline{MR}\left(1 + \tfrac{2}{3}(D_4 - 1)\right)$, carried over from the original so MR Rule 2 behaves consistently with I Rule 2. Treat it as a convention.
3. **`compute_capability` no longer recomputes MR̄ by default.** Passing `mr_bar` (or `mr_mask`) is now the expected path. The original's default recomputed moving ranges from the retained series, silently including ranges that bridge removal gaps; it was correct only because its single caller happened to pass `mr_bar`.
4. **The audit log's `observation` is a plain column, not the index.** As an index it silently collapsed duplicate labels — two batches sharing a date — which is exactly what an audit trail must not blur.
5. **Normality is surfaced as an `AssumptionCheck`** from the shared `stats_core` result schema rather than a bespoke dict, so it renders like every other assumption in the app.

---

## 11. References

- Oakland, J.S. *Statistical Process Control*, Ch. 4–5.
- Wheeler, D.J. *Understanding Statistical Process Control*.
- Montgomery, D.C. (2020). *Introduction to Statistical Quality Control*, 8th ed. Wiley.
- Nelson, L.S. (1984). The Shewhart control chart — tests for special causes. *Journal of Quality Technology*, 16(4), 237–239.
- Western Electric Co. (1956). *Statistical Quality Control Handbook*. AT&T Technologies.
- AIAG (2010). *Statistical Process Control Reference Manual*, 2nd ed.
- ASTM E2587 / ISO 7870-2 — control chart constants.
- ISO 22514-2 — process capability, percentile method for non-normal distributions.
- Bissell, A.F. (1990). How reliable is your capability index? *Applied Statistics*, 39(3), 331–340.
