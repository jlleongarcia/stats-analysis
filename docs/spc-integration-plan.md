# SPC Integration Plan

Folding [`SPC-analysis`](https://github.com/jlleongarcia/SPC-analysis) into `stats-analysis`,
after which the SPC repository is decommissioned.

**Status:** Phases 1-3 + 5 done, Phase 4 started (Phase 3 runtime check outstanding) · **Target:** SPC as a first-class capability of the PWA · **Endgame:** old repo deleted

---

## 1. Why this merge is worth doing

Every method in `stats_core` today is **cross-sectional** — compare groups, model relationships,
reduce dimensions. Nothing in it knows what *time order* means. SPC is precisely that missing
axis, and it arrives with the same input model the app already has (upload a table, pick numeric
columns). It is a capability expansion, not a bolt-on.

Concrete wins from the merge itself, beyond "one app instead of two":

- **Deduplication.** `src/spc/core/normality.py` is a strict subset of `stats_core/normality.py`. It deletes itself.
- **Durable audit trails.** Streamlit kept the Phase I decision log in `session_state`; a browser refresh destroyed it. In the PWA it becomes an IndexedDB record — survives reloads, exportable, and makes Phase II possible.
- **Real test coverage.** The SPC engine joins a pytest suite that already runs the identical code the browser runs.
- **Offline + installable.** SPC inherits the PWA shell for free.

---

## 2. What actually transfers

Of SPC-analysis's 2,458 lines:

| Component | LOC | Fate |
|---|---:|---|
| `src/spc/core/{limits,rules,capability,phase_i}.py` | ~540 | **Port** — pure pandas/numpy, framework-free |
| `tests/test_spc_core.py` | 197 | **Port** — drops into the existing pytest suite |
| `docs/{methodology,user_guide}.md` | 421 | **Port** — genuinely good; becomes in-app help |
| `src/spc/core/normality.py` | 71 | **Delete** — superseded by `stats_core/normality.py` |
| `src/spc/charts/imr.py` | 366 | **Discard** — Plotly; re-express as Vega-Lite |
| `pages/*.py` | 1,192 | **Discard** — Streamlit; rewrite as React |
| `app.py`, `main.py` | 62 | **Discard** |

### ⚠️ Domain logic stranded in the Streamlit pages

This is the part that gets silently lost if we only port `src/spc/core/`. Six pieces of real
domain logic live in `pages/`, not in the engine. **Each must be rescued into Python before the
old repo is deleted.**

| # | Logic | Currently at | Rescue to |
|---|---|---|---|
| 1 | **Bridging-MR mask derivation** — after removals, MRs spanning a gap must be excluded from MR̄ so σ̂_within uses only originally-adjacent pairs | `02_phase_i.py:133–147` | `spc/phase_i.py::bridging_mr_mask()` |
| 2 | **Audit-log schema & construction** (`pass`, `observation`, `value`, `rules_violated`, `decision`, `assignable_cause`, `x_bar`, `ual`, `lal`) | `02_phase_i.py:395–420` | `spc/audit.py` |
| 3 | **Two-pass finalisation** → `PhaseIResult` | `02_phase_i.py:_finalise()` | `spc/phase_i.py::finalise()` |
| 4 | **Cross-variable flagging** — an observation removed from variable A is surfaced as "suspect" in variable B | `02_phase_i.py:_cross_flagged_info()` | `spc/crossflag.py` |
| 5 | **Interpretation heuristics** — removal rate > 20 % warning; Cpk/Cp < 0.85 off-centring warning | `05_audit_trail.py`, `04_capability.py` | `spc/verdicts.py` |
| 6 | **Correlated sample-data generator** (two variables, shared injected OOC events) | `01_data_import.py` | `tests/` fixture + a demo dataset |

---

## 3. Architecture: the one real tension

The registry contract is **stateless and one-shot**:

```python
func(frame: DataFrame, roles: dict, params: dict) -> TestResult
```

Phase I is neither. It is iterative and human-in-the-loop *by design* — pass 1 flags candidates,
the analyst reviews each and documents an assignable cause, pass 2 produces the certified
baseline. `phase_i.py` is emphatic about it, citing Oakland: *"A point should be removed ONLY
when an assignable cause is identified. The analyst — not the algorithm — decides."*

Forcing that into a `TestSpec` gives one of two bad outcomes: auto-removal of flagged points
(destroying the methodological integrity that is the whole point of the original tool), or state
smuggled through `params`, which will rot.

### Resolution: split by statefulness, keep Python pure

**Key insight: the Python side never needs to hold state.** If the UI passes the full exclusion
set on every call, evaluation is a pure function of (data, exclusions, rule config). Workflow
state lives in the React store and Dexie — where it is already durable and inspectable.

```
                    ┌─────────────────────────────────────────┐
                    │  stats_core/spc/   (pure, stateless)    │
                    │  limits · rules · phase_i · capability  │
                    └──────────────┬──────────────────────────┘
                          ┌────────┴────────┐
              registry.py │                 │ spc/api.py
         (TestSpec entries)                 (JSON entry points)
                          │                 │
                    ┌─────▼─────┐     ┌─────▼──────────┐
                    │ /analyze  │     │ /spc  (Studio) │
                    │ one-shot  │     │ stateful flow  │
                    │ chart +   │     │ state in Dexie │
                    │ capability│     │ + audit trail  │
                    └───────────┘     └────────────────┘
```

- **Registry entries** (zero architectural change): `control_chart_imr`, `process_capability`. A fast "just show me the chart" path from the existing Analyze page.
- **SPC Studio** (`/spc`): a fourth workspace beside Guided/Analyze/Explore, owning the Phase I workflow through its own JSON protocol.

Same engine, two front doors. The registry stays pure.

### Package placement

`stats_core/spc/` as a **subpackage**, not a sibling `spc_core/`. This requires **no changes** to
`pyproject.toml` packaging, `Dockerfile`, or `scripts/copy-wheel.mjs` — the existing wheel picks
it up automatically. The stateless/stateful distinction is a matter of *contract*, expressed by
which module exposes what, not of distribution.

### Observation order

Control charts need row order. `Dataset` has no ordering concept, and it does not need one: order
is row order as imported (what the old app did), with an optional label/order column exposed as a
role — `Role("order", "Observation label (optional)", ANY, required=False)`. No schema change.

---

## 4. Phased implementation

### Phase 0 — Leave the source repo alone

**Decided:** `SPC-analysis` stays public, open and untouched for the duration of the merge. It is
the reference source — we read from it, we never modify it. It gets deleted once the merge is
complete and verified (owner's call; the archive-instead-of-delete tradeoff was raised and
declined).

No work items. Nothing in this plan writes to that repository.

### Phase 1 — Engine port ✅ complete

`stats_core/spc/` — 11 modules, all six rescued behaviours landed, 81 tests passing:

```
stats_core/spc/
  constants.py     # d2, d3, D3, D4, A2, A3, B3, B4, c4 for n = 2..25
  limits.py        # I-MR control lines + bridging_mr_mask()      [rescue 1]
  rules.py         # rules 1-4, MR rules, rules_fired()
  phase_i.py       # run_phase_i_pass() + finalise()              [rescue 3]
  audit.py         # DecisionSet, build_audit_log()               [rescue 2]
  capability.py    # Cp/Cpk/Pp/Ppk, mr_bar trap fixed
  crossflag.py     # cross_flags(), shared_removals()             [rescue 4]
  verdicts.py      # interpretation heuristics                    [rescue 5]
  precheck.py      # normality as an AssumptionCheck
  api.py           # spc_call(): evaluate / certify / capability / cross_variable
```

Rescue 6 (the correlated sample-data generator) is covered by test fixtures; a shipped demo
dataset is deferred to Phase 5.

Confirmed during the port:

- The wheel picks the subpackage up with **no** change to `pyproject.toml`, `Dockerfile` or `copy-wheel.mjs`, as predicted.
- `spc_call` is exported from `stats_core/__init__.py`, so Phase 3's worker wiring is a two-line `BOOTSTRAP` addition.
- The new tests need none of the gitignored `.XLS` fixtures, so they run in a clean checkout where much of the existing suite skips.

**Correction to the plan's earlier premise:** the bridging mask does *not* reliably shrink
`sigma_within`, and a test asserting so failed. It excludes a range that was never a valid
measurement of short-term variation — direction depends on the data. In the regression case the
bridging range is the *smallest* present, so masking raises `mr_bar` from 0.300 to 0.333. Both
directions are now pinned by tests.

Correctness items to fold in **during** the port, not after:

- **`compute_capability`'s `mr_bar` default is a trap.** When not supplied it recomputes MR from the retained series, silently including bridging ranges — the exact thing `mr_mask` exists to prevent. Today `04_capability.py` happens to pass `lim["mr_bar"]`, so it is correct by luck. Make the mask/`mr_bar` explicit and required.
- **`mr_uwl = mr_bar * (1 + ⅔(D4−1))`** is a pragmatic interpolation, not a standard formula. Keep it, but document it as a deliberate deviation in `methodology.md` — someone will check it against a textbook.
- **`d2 = 1.128` is hard-coded for n=2.** Move to `constants.py` as a table; this is the enabler for Phase 4's subgroup charts.
- **Run/trend rules flag only the point completing the window**, not every point in the run. Defensible, but undocumented — state the convention.
- Replace `spc.core.normality` calls with `stats_core.normality`, surfaced as an `AssumptionCheck`.

**Gate:** `uv run pytest` green, with `tests/test_spc_core.py` ported plus new tests for the six rescued behaviours.

### Phase 2 — Registry entries + control chart rendering ✅ complete

`stats_core/spc/entries.py` + family `"spc"`; `controlChart` renderer in `viz/buildSpec.ts`.
94 SPC tests passing, `tsc` clean, production build green.

- `control_chart_imr` — roles: measurement + optional label; params: the four rule thresholds. Emits limits in `statistic`, a control-lines table, a flagged-points table, normality as an `AssumptionCheck`, and two `controlChart` plot specs.
- `process_capability` — params `usl`/`lsl`. Cp/Cpk/Pp/Ppk in `statistic`, verdicts in `notes`, a spec-limit histogram.

Both carry a note that they are **not** a certified Phase I baseline, and `process_capability`
leads with the out-of-control caveat when the data still shows violations (decision 2 in §6).

**Design decisions made during the build:**

- **Two plot specs, not one `vconcat`.** Vega-Lite's responsive `width: "container"` is unsupported inside concatenations, and a control chart that cannot fill its panel is worse than one not pixel-aligned with the chart below it.
- **Which lines and zones each panel carries is decided in Python**, not the renderer — it is SPC domain knowledge and is covered by tests. `buildSpec.ts` only maps `kind` → colour/dash.
- **Colour is never the only cue.** The validator put warning-amber and centre-emerald ~3 ΔE apart under tritanopia, so every reference line also has a distinct dash pattern and a direct right-edge label, and violations differ in shape (triangle) and size as well as hue.
- **Centre-zone shading was tried and dropped.** On the dark ground the two tints were barely tellable apart; only the 2–3σ warning zones are shaded now.

**Three bugs that only rendering caught** (compiling was clean throughout):

1. **Y axis anchored at zero**, crushing a 92–120 series into the top fifth of the plot. Fatal for a chart whose job is resolving small excursions. Now `zero: false` on individuals, `true` on moving range (whose lower limit genuinely is zero).
2. **Limit labels stacked at the far left and the x axis reordered to `D50, D1, D2…`** — the label layers used `x: {datum: lastLabel}`, which injected that label into the shared ordinal domain *ahead of* the data layer. Labels are now positioned by pixel expression (`x: {expr: "width"}`), bypassing the scale.
3. **A point outside the action limit clipped against the axis edge** — the single point a reader most needs. Fixed with scale padding.

**Gate met:** both entries run end-to-end; charts verified by headless Vega render and visual inspection.

### Phase 3 — SPC Studio (`/spc`) ✅ built, runtime check outstanding

99 SPC tests passing, `tsc` clean, production build green, decision-table guard rail verified by
headless React render. **Not yet driven in a browser against a live engine** — see the gate below.

| File | Role |
|---|---|
| `compute/protocol.ts`, `pyodide.worker.ts`, `ComputeClient.ts` | the generic `spc` channel + `client.spc(fn, payload)` |
| `data/db.ts` | Dexie **v2**, `spcStudies` table, cascade delete with the dataset |
| `state/spcStore.ts` | the workflow: `setup → review → certified` |
| `pages/SpcPage.tsx` | the Studio, replacing all five old Streamlit pages |
| `spc/DecisionTable.tsx` | per-point ruling; removal inert until a cause is typed |
| `spc/AuditTrail.tsx` | decision log + CSV export |
| `stats_core/spc/charts.py` | **new** — chart builder shared by Analyze and the Studio |

Decisions made while building:

- **The chart builder moved to `stats_core/spc/charts.py`**, shared by the registry entries and the Studio protocol, so both render from one tested implementation rather than two.
- **`PhaseIResult` now carries `final_pass`** — the certified pass in `PassResult` form. Certified charts are drawn from the certified numbers instead of a recomputation that could quietly omit the pass-2 bridging mask.
- **Capability hands off `mrBar` from the certified baseline**, so `sigma_within` matches the control chart exactly rather than being re-derived across the removal gaps. Pinned by a test.
- **The assignable-cause rule is enforced twice**: the UI disables certification while any removal lacks a cause, and `finalise()` raises `AssignableCauseRequired` regardless. The UI check is a courtesy; the engine check is the guarantee.

**Gate:** ⚠️ partially met. Python protocol verified end-to-end with real payloads; React layer
typechecked, built, and its guard-rail component render-tested. Still to do: run the app with a
booted Pyodide engine and walk a study through pass 1 → decisions → certify → capability → export,
and confirm a mid-study page refresh loses nothing.

Original scope notes:

**Protocol.** Extend `compute/protocol.ts` with one generic message rather than one per operation:

```ts
| { kind: "spc"; id: string; fn: string; payload: unknown }
```

Worker `BOOTSTRAP` gains:

```python
from stats_core import spc_call as _sc
def _spc(fn, payload_json):
    return json.dumps(_sc(fn, json.loads(payload_json)))
```

`stats_core/spc/api.py` exposes `evaluate` and `capability`. `evaluate` takes
`{data, column, orderColumn, chartType, ruleConfig, excludedRows[]}` and returns limits, per-point
values with violation flags, MR series, and the flagged set — **recomputed from scratch each call**.

**Persistence.** Bump Dexie to version 2 with an `spcStudies` table:

```ts
interface SpcStudy {
  id: string; datasetId: string; column: string;
  orderColumn: string | null; chartType: "imr";
  ruleConfig: RuleConfig;
  decisions: Decision[];        // { rowIndex, label, value, rules[], remove, cause }
  baseline: Baseline | null;    // frozen limits once certified
  createdAt: number; updatedAt: number;
}
```

Wire `spcStudies` into `deleteDataset`'s cascade transaction alongside `analyses`.

**UI.** Reproduce the old workflow, improved:

- variable tabs (multi-variable studies, as before)
- rule-threshold controls
- normality pre-check panel
- Pass 1 → decision table (per-point remove + assignable cause, bulk mode, **cause required to remove**) → Pass 2 → certified baseline
- cross-variable suspect flagging
- audit trail view + CSV export, and an HTML report via the existing `results/report.ts` pattern

**Gate:** the complete old five-page workflow is reproducible end-to-end, and a page refresh mid-study loses nothing (it never survived in Streamlit).

### Phase 4 — Enhancements (each independently shippable) — 1 of 6 done

Ordered by value:

1. ✅ **X̄-R and X̄-S subgrouped charts** — `stats_core/spc/subgroups.py`, two registry entries, shared chart builder. Subgroups come from an explicit column or fixed-size chunking of consecutive rows. Ragged subgroups are refused with guidance rather than silently averaged, since the constants are defined per n; a partial trailing subgroup is dropped and reported. The means-chart limits use σ̂/√n and are pinned by test against both textbook shortcut factors (A2, A3). The spread chart is checked on **both** sides from n = 7, where D₃/B₃ become non-zero — an implausibly tight subgroup signals non-independent or massaged data. ⏳ Attribute charts (p, np, c, u) remain.
2. **Selectable rule sets.** Four Oakland rules are hard-coded. Offer Nelson's 8 and Western Electric alongside them, chosen rather than baked in.
3. **Non-normal capability.** Today `normality_check` warns and the analysis proceeds — but Cp/Cpk on skewed data are actively misleading. Add Box-Cox/Johnson transformation or the ISO 22514 percentile method. This is where the merge pays off concretely: SPC borrows `stats_core`'s normality machinery instead of duplicating it.
4. **Confidence intervals on Cpk**, plus Cpm (Taguchi). Point estimates at n=30 imply far more precision than exists.
5. **Phase II monitoring.** The old README called Phase I "the foundation step before deploying Phase II" — never built. With baselines persisted, applying frozen limits to incoming data is a natural next route.
6. **Guided flow entry.** Add a `goal: "monitor_process"` branch to `guided/decisionTree.ts` routing to SPC.

### Phase 5 — Documentation ✅ complete (including in-app)

- ✅ `docs/spc-methodology.md` — ported and updated; §8 records all five deliberate deviations from the original tool.
- ✅ `docs/spc-user-guide.md` — rewritten for the two front doors (Analyze entries, SPC Studio) rather than the old five Streamlit pages; ends with an explicit "not yet supported" list so the Phase 4 gaps are stated rather than discovered.
- ✅ `README.md` — SPC section, module tree, and the `pyodide-runtime.json` manifest.
- ✅ **In-app docs at `/docs`** — the markdown under `docs/` is imported `?raw` and bundled, so the page and the repo cannot disagree and the docs work offline in an installed PWA. Needed `server.fs.allow` for dev and a `COPY docs` in the frontend image stage.
- ✅ **Widened beyond SPC.** SPC is 4 of 47 tests and the docs were implying otherwise. Added `docs/getting-started.md` and `docs/statistical-methods.md` (all 14 families, with LaTeX formulas), plus a **generated test reference** built from the registry — so a new test documents itself and the reference can never drift from what the app does. KaTeX renders equations, bundled locally with its fonts so no CDN is involved.

**Fidelity check.** The port was compared against the original implementation across 300
randomised series — every control line, all four rules, the MR rules and the flagged-point list.
**At default thresholds: zero mismatches.** The single divergence is deviation 1 below.

### Phase 6 — Decommission

Only once every box above is ticked:

- [ ] Walk the §2 tables and confirm every "Port" row and all six rescued behaviours landed.
- [ ] Confirm no remaining reference to the old repo is load-bearing.
- [ ] Delete `SPC-analysis` — GitHub repo and the local clone at `~/Documents/Github_projects/SPC-analysis`.

---

## 5. Effort

| Phase | Estimate |
|---|---|
| 0 — Preserve | ~1 h |
| 1 — Engine port | ~0.5 day |
| 2 — Registry + control chart spec | ~1 day |
| 3 — SPC Studio | ~2–3 days |
| 4 — Enhancements | 0.5–1 day each, independent |
| 5 — Docs | ~0.5 day |
| 6 — Decommission | ~1 h |

Phases 1–3 are the merge; 4 is upside; 5–6 close it out. Phase 3 dominates and is where scope can
be trimmed if needed — a minimal Studio that only does single-variable I-MR still fully replaces
the old tool.

---

## 6. Decisions taken

1. **Docs: repo-only initially.** `methodology.md` and `user_guide.md` land in `docs/`. An in-app `/docs` route was a nice touch in the old tool but it bundles markdown into the PWA for no functional gain during the merge — deferred, not dropped.
2. **`process_capability` stands alone**, and emits a prominent `note` whenever the supplied data still shows rule violations. Capability on an out-of-control process is meaningless, but refusing to compute it is worse than computing it with the caveat attached — analysts routinely need the number before the baseline is certified.
3. **Studio v1 is single-variable.** Multi-variable tabs and cross-variable suspect flagging move to Phase 4. **This is a UI phasing decision only** — `crossflag.py` is still written and tested in Phase 1, because the logic dies with the old repo otherwise.
