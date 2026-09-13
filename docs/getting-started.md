# Getting started

Stats Analysis runs entirely in your browser. Your data is never uploaded — the Python engine
(CPython compiled to WebAssembly) runs in a background thread on your own machine, and the app
works with the network off once it has loaded.

---

## The four workspaces

| Page | What it is for |
|---|---|
| **Data** | Import a CSV or Excel file, check how columns were typed, pick the active dataset |
| **Guided** | Answer a few questions about your goal and get a recommended test |
| **Analyze** | Choose any test directly, map your variables, run it |
| **Explore** | Quick plots of two columns, no test involved |
| **SPC** | The Phase I control-chart workflow (see the SPC user guide) |

A typical session: import on **Data**, look around on **Explore**, use **Guided** if you are not
sure which test fits, then run it on **Analyze**.

---

## Importing data

Upload a `.csv`, `.xlsx` or `.xls` file on the **Data** page. One row per observation, one column
per variable, with variable names in the first row.

Each column is typed automatically as **numeric**, **categorical**, **datetime** or **boolean**.
The type decides which roles a column can fill — a numeric outcome, a categorical grouping
variable — so if something is typed wrongly, correct it on the Data page before running anything.
A numeric-looking code such as a batch number or a Likert response is often better treated as
categorical.

Missing values are handled per test and reported in the result. Most tests drop incomplete rows
for the variables they use, rather than dropping the row from the dataset entirely.

### Size

Everything happens in browser memory. Tens of thousands of rows are comfortable; beyond about
100,000 the app warns, and very wide datasets (hundreds of columns) will feel slow in the grid
before the statistics become a problem.

---

## Running a test

1. Pick a test. **Analyze** groups them by family; **Guided** narrows it down by asking about your goal, your groups, and whether the data looks normal.
2. Map your variables into the roles the test needs — the dropdowns only offer columns of a compatible type.
3. Adjust settings if needed (significance level, one- or two-sided, and so on).
4. Run.

You get a plain-language summary, an APA-style line you can paste into a write-up, the test
statistic and p-value, effect sizes with confidence intervals, assumption checks, tables and a
plot.

**Save to history** keeps a result with the dataset. Saved analyses can be reopened as a printable
report.

---

## What the engine is doing

The statistics are implemented in a framework-free Python package, `stats_core`, built on numpy,
pandas, scipy, statsmodels and scikit-learn. The browser installs that exact package and runs it
under Pyodide — and the same code runs under pytest on a normal Python interpreter.

That matters for trust: the code producing your result is the code the test suite checks, not a
reimplementation in JavaScript that happens to agree most of the time.

The first load downloads roughly 115 MB of runtime. After that it is cached and the app starts
offline.

---

## Interpreting results honestly

A few habits that matter more than any individual test:

**Decide before you look.** A test chosen after seeing the data is not testing a hypothesis, it is
describing one. That is fine — just call it exploratory, and confirm on new data.

**Read the effect size, not just the p-value.** With enough data everything is significant. With
too little, nothing is. Neither tells you whether the difference matters.

**Take assumption warnings seriously but not fatally.** Most have a robust alternative a click
away — Welch's instead of Student's t, a rank-based test instead of a parametric one.

**Remember multiple testing.** Twenty tests at $\alpha = 0.05$ give about a 64% chance of at least
one false positive. The app corrects within post-hoc comparisons; it cannot correct across the
tests you personally decide to run.

---

## Installing the app

It is a Progressive Web App: install it and it opens in its own window and runs with no network at
all. A banner offers installation where the browser supports it. See the project README for
per-platform detail — notably that Safari on macOS does not keep the runtime cached, so Chrome or
Edge is the better choice there.
