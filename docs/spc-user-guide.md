# SPC User Guide

How to run a control chart and establish a Phase I baseline in this app.

---

## What this is for

**Statistical Process Control** answers a question none of the other tests in this app can:
*is this process stable over time, and is it capable of meeting its specification?*

Everything else here is cross-sectional — compare these groups, model this relationship. SPC adds
the time axis.

Use it to:

- establish action limits and warning lines for a process for the first time
- validate a historical dataset before publishing official control limits
- produce a capability study (Cp, Cpk) backed by clean, verified data
- generate an audit trail of removed observations for a PPAP, control plan or GMP record

---

## Two ways in

| | **Analyze page** | **SPC Studio** |
|---|---|---|
| Route | `/analyze`, family **spc** | `/spc` |
| Shape | one-shot, like any other test | a workflow you step through |
| Gives you | a chart, limits, flagged points, capability | a **certified baseline** + audit trail |
| Removes points | never | only with a documented cause |
| Saved | as an analysis | as a study, in IndexedDB |

**Start on the Analyze page** to look at a process. **Move to the Studio** when you need limits
you will actually publish. The Analyze charts say so in their notes: they are a picture of the
data as supplied, not a baseline. Control limits computed from a process that was not stable are
wider than the process warrants.

---

## Preparing your data

One row per observation, in the order the measurements were taken.

- **Row order is the time axis.** The app never re-sorts. If your file is not in process order, sort it before importing.
- One or more **numeric** columns of measurements.
- Optionally a **label** column (date, batch ID, sample number) for the x axis. This is used for display only and never changes the order.

Import it on the **Data** page as CSV or Excel, then select it as the active dataset.

### How much data?

I-MR charts are valid from $n \ge 2$, but **$n \ge 30$** is the practical minimum for reliable limits.
Below about 20 retained points the app marks the baseline provisional.

---

## Choosing a chart

| Your data | Chart |
|---|---|
| One measurement per period | **Individuals & Moving Range** |
| Several per period, subgroup $n \le 8$ | **$\bar{X}$ & $R$** |
| Several per period, subgroup $n \ge 9$ | **$\bar{X}$ & $S$** |

Subgrouping is worth it when you have it: the within-subgroup spread estimates sigma directly, so
drift *between* subgroups cannot inflate the limits, and averaging tightens the limits by a factor
of $\sqrt{n}$. Tell the app which subgroup each row belongs to with a **Subgroup column**, or leave it empty
and set a **Subgroup size** to chunk consecutive rows.

Every subgroup must hold the same number of observations — Shewhart constants are defined per
subgroup size — and the app says so explicitly rather than silently averaging over ragged groups.
A partial trailing subgroup is dropped and reported.

The spread chart ($R$ or $S$) is checked on **both** sides once the subgroup reaches $n = 7$, where the
lower limit becomes non-zero. A subgroup that is suspiciously *tight* is a real signal: usually
non-independent measurements, or data that has been rounded or massaged.

---

## Quick look: the Analyze page

1. Go to **Analyze** and pick **Control chart (Individuals & Moving Range)**.
2. Map **Measurement** to your numeric column, and optionally **Observation label**.
3. Adjust rule thresholds under the parameters if you need to. Defaults: Rule 2 = 2-of-3, Rule 3 = 8, Rule 4 = 6.
4. Run.

You get the individuals chart, the moving range chart, a control-lines table, a table of flagged
points naming which rules fired, and a normality pre-check.

**Process capability (Cp, Cpk, Pp, Ppk)** works the same way, and additionally asks for the upper
and lower specification limits. If the data still shows rule violations it leads with a warning —
capability on an unstable process describes the past but predicts nothing.

### Reading the chart

| Element | Meaning |
|---|---|
| Solid green **CL** | the centre line, $\bar{x}$ |
| Dotted amber **UWL / LWL** | warning limits, $\pm 2\hat{\sigma}$ |
| Dashed red **UAL / LAL** | action limits, $\pm 3\hat{\sigma}$ |
| Shaded band | the $2$–$3\hat{\sigma}$ warning zone |
| Blue circle | in control |
| Red triangle | flagged by at least one rule |

Hover any point for its value and the rules that fired. Every line carries a dash pattern and a
label as well as a colour, so the chart stays readable without relying on colour vision.

---

## The Studio: establishing a baseline

Go to **SPC** with a dataset selected.

### 1. Set up

Choose the measurement column, optionally a label column, and adjust the rule thresholds under
**Rule thresholds**. Then **Run pass 1**.

### 2. Review what the rules flagged

You get the charts, the normality check, and a decision table of every flagged point.

**This is the part that matters.** The rules flag *candidates*, not confirmed special causes. For
each point, decide whether you can name what actually went wrong in the process:

- **You can** — tick Remove and write the cause: *"Chiller tripped 02:30, WO-2026-1142"*. Not "outlier" or "rule 1".
- **You cannot** — leave it. Retaining a flagged point is a valid decision and is recorded as one.

The **Remove** tick does nothing until a cause is typed. Certification stays disabled while any
removal lacks one, and the engine rejects the request independently even if the UI is bypassed.
This is deliberate: removing points because they are statistically inconvenient produces
artificially tight limits that the real process cannot hold.

If a single event explains every flag, the bulk field applies one cause to all of them.

### 3. Certify

**Certify** applies your decisions. If nothing was removed, the pass-1 limits stand. If anything
was removed, pass 2 recomputes the limits on what remains — excluding moving ranges that bridge
the gaps — and that is the certified baseline.

There is no pass 3. Iterating until no violations remain produces "utopia limits" that describe a
process you do not have. Violations remaining after pass 2 are reported, not pruned; treat them as
common-cause variation unless you have fresh process evidence.

You will see the final charts, plain-language verdicts, and warnings if the removal rate exceeded
20 % or too few points remain.

### 4. Capability

Enter the specification limits — what the process is *required* to meet, not the control limits,
which describe what it actually does. Capability is computed on the certified baseline, and
$\hat{\sigma}_{\text{within}}$ is taken from it so the numbers match the chart exactly.

### 5. Audit trail

Every flagged point with its rules, your decision, the documented cause, and the control limits as
they stood at review time. **Download audit log (CSV)** is the artefact an auditor asks for.

---

## Your work is saved

Each certified study is stored on your device (IndexedDB) and listed at the bottom of the Studio
page, per dataset. A page refresh mid-study does not lose it. Deleting a dataset deletes its
studies with it.

Nothing is uploaded. All computation runs in your browser.

---

## Common pitfalls

**"Everything is flagged."** Usually the process shifted partway through. If the mean moves
between two periods, the grand mean falls in the gap and points on both sides fall outside the
limits. That is not 30 special causes — it is one, and the answer is to pick a baseline period
rather than to prune.

**Removing points until the chart looks clean.** The fastest way to useless limits. Above a 20 %
removal rate the app warns you; the right response is almost always to reselect the baseline
period.

**Non-normality.** If the pre-check flags it, consider a transformation (log, Box-Cox), or ask
whether the data mixes sub-populations — two machines, two shifts, two material lots. Splitting is
usually better than transforming.

**Cp fine, Cpk poor.** The spread is adequate but the process is off-centre. Fix the set point;
reducing variation will not help.

**Pp well below Cp.** Long-term drift between subgroups. A healthy Cpk alone is not enough — find
the source of the drift.

**Capability on an uncertified process.** The indices assume stability. The app computes them with
a caveat rather than refusing, because the number is often needed before the baseline is final —
but the caveat is there for a reason.

---

## Not yet supported

- Attribute charts (p, np, c, u) for defect counts
- Nelson's 8 and Western Electric rule sets — the four Oakland rules are implemented and configurable
- Non-normal capability (Box-Cox / ISO 22514 percentile methods)
- Confidence intervals on Cpk, and Cpm
- Phase II monitoring against a frozen baseline
- Multi-variable studies with cross-variable flagging — the engine supports it; the Studio UI is single-variable
