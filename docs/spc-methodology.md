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

```
MR_i = |x_i − x_{i−1}|
```

It estimates short-term (within-subgroup) variation. **Row order is the time axis** — the app
never re-sorts your rows, and an optional label column supplies display labels only. Sorting by a
label would silently rewrite the sequence the moving ranges are computed from.

---

## 3. Control limit formulas

Short-term standard deviation, using the span-2 unbiasing constant `d₂ = 1.128`:

```
σ̂_within = MR̄ / d₂
```

**Individuals chart**

| Line | Formula |
|---|---|
| UAL (action) | x̄ + 3σ̂ |
| UWL (warning) | x̄ + 2σ̂ |
| CL | x̄ |
| LWL (warning) | x̄ − 2σ̂ |
| LAL (action) | x̄ − 3σ̂ |

**Moving range chart**

| Line | Formula |
|---|---|
| UAL | D₄ · MR̄  (D₄ = 3.267 at n = 2) |
| CL | MR̄ |
| LAL | 0 — always, because D₃ = 0 at n = 2 |

Constants for subgroup sizes 2–25 (`d2`, `d3`, `D3`, `D4`, `A2`, `A3`, `B3`, `B4`, `c4`) are
tabulated in `stats_core/spc/constants.py`, following ASTM E2587 / ISO 7870-2. Only the n = 2
column is used today; the rest is what makes X̄-R and X̄-S charts a small addition rather than a
re-derivation.

---

## 4. The four rules

Rules 1–4 apply to the individuals chart; rules 1–2 apply to the moving range chart.

### Rule 1 — Action limits
Any single point beyond ±3σ. Under normality the false-alarm rate on a single point is ≈ 0.27 %.

### Rule 2 — Warning zone (2-of-3)
2 or more of any 3 consecutive points in the *same* warning zone (between ±2σ and ±3σ on one
side). Upper and lower zones are counted separately — two points high and one low is not a
signal, because the two sides indicate opposite shifts.

This is the Western Electric formulation. It is preferred over the simpler "no point in the
warning zone" check because it controls the false-alarm rate while staying sensitive to real
shifts. Both `k` and the window are configurable.

### Rule 3 — Run
`k` or more consecutive points on the same side of the centre line (default 8). A sustained shift
too small to trip Rule 1 shows up as a run. Eight coin flips landing the same way has probability
0.78 %.

> Nelson (1984) uses k = 9; Western Electric uses k = 8. The default here is 8, configurable.

### Rule 4 — Trend
`k` or more consecutive points strictly rising or falling (default 6). `k` points define `k − 1`
successive differences, all of which must share a sign; a tie breaks the trend. A monotonic run of
6 has probability (1/2)⁵ ≈ 3 %.

### Flagging convention
Run- and trend-based rules (3 and 4) flag the point that **completes** the window, plus any
subsequent point while the run continues — not every point in the run retrospectively. An 8-point
run at k = 8 flags one point; a 9-point run flags two. This keeps a single long drift from filling
the decision table with a dozen rows describing one event. Rules 1 and 2 flag the offending point
itself. Every comparison is strict, so a point sitting exactly on a limit or the centre line is
not a violation.

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

## 6. Normality pre-check

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

## 7. Process capability

**σ_within** (short-term, from MR̄/d₂) captures only inherent point-to-point variation and drives
Cp and Cpk. **σ_overall** (the sample SD of retained values) also captures drift and shifts, and
drives Pp and Ppk.

```
Cp  = (USL − LSL) / (6 σ̂_within)
Cpk = min[(USL − x̄), (x̄ − LSL)] / (3 σ̂_within)
Pp  = (USL − LSL) / (6 σ̂_overall)
Ppk = min[(USL − x̄), (x̄ − LSL)] / (3 σ̂_overall)
RPI = 2T / (6 σ̂_within), where T = (USL − LSL)/2, so RPI ≡ Cp
```

| Index | Minimum | Enterprise target | Critical characteristics |
|---|---|---|---|
| Cp | 1.00 | 1.33 | 1.67 |
| Cpk | 1.00 | 1.33 | 1.67 |

Two gaps to read:

- **Cp vs Cpk.** Cp ≥ 1.33 with Cpk < 1.00 means the spread is adequate but the process is off-centre. Fix the set point, not the variation. The app flags Cpk/Cp < 0.85.
- **Cp vs Pp.** Pp materially below Cp means long-term drift between subgroups. A healthy Cpk alone is insufficient; the source of the drift has to be found.

Capability assumes a stable process. Computed on out-of-control data the numbers describe the past
but predict nothing, and the app says so prominently rather than refusing to compute — analysts
routinely need the figure before a baseline is certified.

---

## 8. Deliberate deviations from the original tool

Recorded so nobody has to rediscover them by diffing against
[SPC-analysis](https://github.com/jlleongarcia/SPC-analysis).

**At default thresholds the two implementations agree exactly** — verified across 300 randomised
series covering every control line, all four rules and the MR rules.

1. **Rule 2's `k`/`window` now reach the MR chart.** The original accepted these parameters on `apply_mr_rules` but never forwarded them from its Phase I pass, so the MR chart stayed at 2-of-3 however Rule 2 was configured. That read as missing wiring rather than intent: the setting is presented as one global threshold. At the default 2-of-3 the behaviour is identical.
2. **`mr_uwl` is a heuristic, not a published formula.** There is no standard warning limit for a range chart — the range statistic is skewed, so a "2σ" line has no clean closed form the way it does on the symmetric individuals chart. The value used is a linear interpolation two-thirds of the way from CL to UCL, `MR̄ · (1 + ⅔(D₄ − 1))`, carried over from the original so MR Rule 2 behaves consistently with I Rule 2. Treat it as a convention.
3. **`compute_capability` no longer recomputes MR̄ by default.** Passing `mr_bar` (or `mr_mask`) is now the expected path. The original's default recomputed moving ranges from the retained series, silently including ranges that bridge removal gaps; it was correct only because its single caller happened to pass `mr_bar`.
4. **The audit log's `observation` is a plain column, not the index.** As an index it silently collapsed duplicate labels — two batches sharing a date — which is exactly what an audit trail must not blur.
5. **Normality is surfaced as an `AssumptionCheck`** from the shared `stats_core` result schema rather than a bespoke dict, so it renders like every other assumption in the app.

---

## 9. References

- Oakland, J.S. *Statistical Process Control*, Ch. 4–5.
- Wheeler, D.J. *Understanding Statistical Process Control*.
- Montgomery, D.C. (2020). *Introduction to Statistical Quality Control*, 8th ed. Wiley.
- Nelson, L.S. (1984). The Shewhart control chart — tests for special causes. *Journal of Quality Technology*, 16(4), 237–239.
- Western Electric Co. (1956). *Statistical Quality Control Handbook*. AT&T Technologies.
- AIAG (2010). *Statistical Process Control Reference Manual*, 2nd ed.
- ASTM E2587 / ISO 7870-2 — control chart constants.
