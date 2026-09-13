/**
 * SPC Studio — Phase I baseline establishment.
 *
 * The one workflow in this app that is not request/response. It replaces five
 * Streamlit pages from the original SPC-analysis project: import, Phase I,
 * final charts, capability and audit trail.
 */
import { useEffect, useMemo } from "react";
import { DecisionTable } from "../spc/DecisionTable";
import { AuditTrail } from "../spc/AuditTrail";
import { VegaLiteChart } from "../viz/VegaLiteChart";
import { specFromPlot } from "../viz/buildSpec";
import { fmtNum } from "../results/format";
import { useApp } from "../state/store";
import { useSpc } from "../state/spcStore";
import type { PlotSpec, SpcNormality } from "../types";

function Charts({ specs }: { specs?: PlotSpec[] }) {
  // Tolerate a payload without charts rather than taking the page down with it:
  // the app shell is service-worker cached, so it can outlive the wheel version
  // it was written against.
  const engine = useApp((s) => s.registry?.engine);
  const built = useMemo(() => (specs ?? []).map(specFromPlot), [specs]);
  if (built.length === 0) {
    const stale = !engine || !engine.spcModules.includes("charts");
    return (
      <div className="warn-box">
        <p>No charts came back from the engine.</p>
        {stale ? (
          <>
            <p>
              The Python engine your browser loaded is <strong>older than this page</strong>. It is
              missing <code>stats_core.spc.charts</code>, so the response has no chart data.
            </p>
            <p className="muted">
              Loaded engine: {engine
                ? `stats_core ${engine.version}, ${engine.testCount} tests, spc modules: ${engine.spcModules.join(", ")}`
                : "too old to report its contents"}
            </p>
            <p className="muted">
              Rebuild and force the browser to re-fetch the wheel — the app shell and the wheel are
              cached separately and the wheel URL never changes, so a plain reload can keep serving
              the old one. See docs/spc-user-guide.md.
            </p>
          </>
        ) : (
          <p className="muted">
            The engine looks current, so this is unexpected — check the browser console.
          </p>
        )}
      </div>
    );
  }
  return (
    <>
      {built.map((spec, i) => (
        <VegaLiteChart key={i} spec={spec} />
      ))}
    </>
  );
}

function Normality({ check }: { check: SpcNormality }) {
  const cls = check.passed === true ? "ok" : check.passed === false ? "warn" : "info";
  return (
    <ul className="assumptions">
      <li className={cls}>
        <span className="assumptions__dot" aria-hidden />
        <span>
          <strong>{check.name}</strong> — {check.detail}
        </span>
      </li>
    </ul>
  );
}

function Stats({ entries }: { entries: [string, number][] }) {
  return (
    <div className="stat-row">
      {entries.map(([k, v]) => (
        <div key={k} className="stat-tile">
          <span className="stat-tile__k">{k}</span>
          <span className="stat-tile__v">{fmtNum(v)}</span>
        </div>
      ))}
    </div>
  );
}

export function SpcPage() {
  const dataset = useApp((s) => s.activeDataset);
  const engine = useApp((s) => s.engine);
  const spc = useSpc();

  useEffect(() => {
    void spc.refreshStudies(dataset?.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataset?.id]);

  if (!dataset) {
    return (
      <div className="page">
        <h1>SPC Studio</h1>
        <p className="muted">Import and select a dataset first.</p>
      </div>
    );
  }

  const numeric = dataset.columns.filter((c) => c.type === "numeric");
  const ready = engine === "ready";
  const busy = spc.busy !== false;

  const blockedRemovals = spc.evaluation
    ? spc.evaluation.flagged.filter((p) => {
        const d = spc.decisions[p];
        return d?.remove && !d.cause.trim();
      }).length
    : 0;
  const plannedRemovals = Object.values(spc.decisions).filter((d) => d.remove).length;

  return (
    <div className="page spc">
      <header className="spc__head">
        <h1>SPC Studio</h1>
        <p className="muted">
          Establish a verified Phase I baseline for <strong>{dataset.name}</strong>. Row order
          is the time axis — the chart never re-sorts your data.
        </p>
      </header>

      {/* ---- setup ------------------------------------------------------- */}
      <section className="spc-setup">
        <label className="field">
          <span>Measurement</span>
          <select
            value={spc.column}
            disabled={busy}
            onChange={(e) => spc.setColumn(e.target.value)}
          >
            <option value="">— choose a column —</option>
            {numeric.map((c) => (
              <option key={c.name} value={c.name}>{c.name}</option>
            ))}
          </select>
        </label>

        <label className="field">
          <span>Observation label (optional)</span>
          <select
            value={spc.orderColumn ?? ""}
            disabled={busy}
            onChange={(e) => spc.setOrderColumn(e.target.value || null)}
          >
            <option value="">— row number —</option>
            {dataset.columns
              .filter((c) => c.name !== spc.column)
              .map((c) => (
                <option key={c.name} value={c.name}>{c.name}</option>
              ))}
          </select>
        </label>

        <details className="spc-rules-config">
          <summary>Rule thresholds</summary>
          <div className="spc-rules-grid">
            <label className="field">
              <span>Rule 2 — points in zone</span>
              <input
                type="number" min={1} max={5} value={spc.ruleConfig.rule2_k} disabled={busy}
                onChange={(e) => spc.setRuleConfig({ rule2_k: Number(e.target.value) })}
              />
            </label>
            <label className="field">
              <span>Rule 2 — window</span>
              <input
                type="number" min={2} max={10} value={spc.ruleConfig.rule2_window} disabled={busy}
                onChange={(e) => spc.setRuleConfig({ rule2_window: Number(e.target.value) })}
              />
            </label>
            <label className="field">
              <span>Rule 3 — run length</span>
              <input
                type="number" min={4} max={15} value={spc.ruleConfig.rule3_k} disabled={busy}
                onChange={(e) => spc.setRuleConfig({ rule3_k: Number(e.target.value) })}
              />
            </label>
            <label className="field">
              <span>Rule 4 — trend length</span>
              <input
                type="number" min={4} max={12} value={spc.ruleConfig.rule4_k} disabled={busy}
                onChange={(e) => spc.setRuleConfig({ rule4_k: Number(e.target.value) })}
              />
            </label>
          </div>
        </details>

        <button
          className="btn btn--primary"
          disabled={!ready || busy || !spc.column}
          onClick={() => void spc.evaluate(dataset)}
        >
          {spc.busy === "evaluating" ? "Evaluating…" : "Run pass 1"}
        </button>
      </section>

      {spc.error && <p className="error">{spc.error}</p>}

      {/* ---- review ------------------------------------------------------ */}
      {spc.stage === "review" && spc.evaluation && (
        <>
          <section className="spc-panel">
            <h2>Pass 1</h2>
            <Stats
              entries={[
                ["n", spc.evaluation.nEvaluated],
                ["x̄", spc.evaluation.limits.i_cl],
                ["UAL", spc.evaluation.limits.i_ucl],
                ["LAL", spc.evaluation.limits.i_lcl],
                ["σ̂ within", spc.evaluation.limits.sigma_within],
                ["flagged", spc.evaluation.flagged.length],
              ]}
            />
            <Normality check={spc.evaluation.normality} />
            <Charts specs={spc.evaluation.charts} />
          </section>

          {spc.evaluation.flagged.length === 0 ? (
            <section className="spc-panel">
              <p className="ok-box">
                No rule violations. All {spc.evaluation.nEvaluated} observations can stand as
                the baseline.
              </p>
              <button
                className="btn btn--primary"
                disabled={busy}
                onClick={() => void spc.certify(dataset)}
              >
                {spc.busy === "certifying" ? "Certifying…" : "Accept baseline"}
              </button>
            </section>
          ) : (
            <section className="spc-panel">
              <DecisionTable
                points={spc.evaluation.points}
                flagged={spc.evaluation.flagged}
                decisions={spc.decisions}
                onChange={spc.setDecision}
                onRemoveAll={spc.removeAllFlagged}
                onClear={spc.clearDecisions}
                disabled={busy}
              />
              <div className="spc-actions">
                <button
                  className="btn btn--primary"
                  disabled={busy || blockedRemovals > 0}
                  onClick={() => void spc.certify(dataset)}
                >
                  {spc.busy === "certifying"
                    ? "Certifying…"
                    : plannedRemovals > 0
                      ? `Remove ${plannedRemovals} and certify`
                      : "Certify with all points retained"}
                </button>
                <button className="btn" disabled={busy} onClick={spc.reset}>
                  Start over
                </button>
              </div>
            </section>
          )}
        </>
      )}

      {/* ---- certified --------------------------------------------------- */}
      {spc.stage === "certified" && spc.baseline && (
        <>
          <section className="spc-panel">
            <h2>Certified baseline</h2>
            <Stats
              entries={[
                ["n final", spc.baseline.nFinal],
                ["removed", spc.baseline.nRemoved],
                ["passes", spc.baseline.nPasses],
                ["x̄", spc.baseline.limits.i_cl],
                ["UAL", spc.baseline.limits.i_ucl],
                ["LAL", spc.baseline.limits.i_lcl],
                ["σ̂ within", spc.baseline.limits.sigma_within],
              ]}
            />
            <ul className="notes-list">
              {spc.baseline.verdicts.map((v, i) => (
                <li key={i}>{v}</li>
              ))}
            </ul>
            <Normality check={spc.baseline.normality} />
            <Charts specs={spc.baseline.charts} />
          </section>

          <section className="spc-panel">
            <AuditTrail baseline={spc.baseline} />
          </section>

          <section className="spc-panel">
            <h3>Process capability</h3>
            <p className="muted">
              Specification limits are what the process is <em>required</em> to meet — not the
              control limits above, which describe what it actually does.
            </p>
            <div className="spc-spec">
              <label className="field">
                <span>Lower specification limit (LSL)</span>
                <input
                  type="number" value={spc.lsl} disabled={busy}
                  onChange={(e) => spc.setSpec("lsl", e.target.value)}
                />
              </label>
              <label className="field">
                <span>Upper specification limit (USL)</span>
                <input
                  type="number" value={spc.usl} disabled={busy}
                  onChange={(e) => spc.setSpec("usl", e.target.value)}
                />
              </label>
              <button
                className="btn"
                disabled={busy}
                onClick={() => void spc.computeCapability(dataset)}
              >
                {spc.busy === "capability" ? "Computing…" : "Compute capability"}
              </button>
            </div>

            {spc.capability && (
              <>
                <Stats
                  entries={[
                    ["Cp", spc.capability.capability.cp as number],
                    ["Cpk", spc.capability.capability.cpk as number],
                    ["Pp", spc.capability.capability.pp as number],
                    ["Ppk", spc.capability.capability.ppk as number],
                  ]}
                />
                <ul className="notes-list">
                  {spc.capability.verdicts.map((v, i) => (
                    <li key={i}>{v}</li>
                  ))}
                </ul>
              </>
            )}
          </section>

          <div className="spc-actions">
            <button className="btn" onClick={spc.reset}>Start a new study</button>
          </div>
        </>
      )}

      {/* ---- saved studies ----------------------------------------------- */}
      {spc.studies.length > 0 && (
        <section className="history">
          <h3>Saved studies for “{dataset.name}”</h3>
          <ul>
            {spc.studies.map((study) => (
              <li key={study.id}>
                <span>
                  {study.column}
                  {study.baseline
                    ? ` — baseline, ${study.baseline.nRemoved} removed`
                    : " — in progress"}
                </span>
                <span className="muted">{new Date(study.updatedAt).toLocaleString()}</span>
                <button className="link" onClick={() => spc.loadStudy(study)}>Open</button>
                <button className="link" onClick={() => void spc.discardStudy(study.id, dataset.id)}>
                  Delete
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
