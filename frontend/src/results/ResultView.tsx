import { useMemo } from "react";
import { specFromPlot } from "../viz/buildSpec";
import { VegaLiteChart } from "../viz/VegaLiteChart";
import type { TestResult } from "../types";
import { fmtNum, fmtP } from "./format";

export function ResultView({ result }: { result: TestResult }) {
  const specs = useMemo(() => result.plotSpecs.map(specFromPlot), [result.plotSpecs]);

  return (
    <div className="result">
      <header className="result__head">
        <h2>{result.testName}</h2>
        {result.pValue !== null && (
          <span className={`pill ${result.pValue < 0.05 ? "pill--sig" : "pill--ns"}`}>
            {fmtP(result.pValue)}
          </span>
        )}
      </header>

      <p className="result__summary">{result.summary}</p>
      {result.apa && <p className="result__apa">APA: {result.apa}</p>}

      <div className="stat-row">
        {Object.entries(result.statistic).map(([k, v]) => (
          <div key={k} className="stat-tile">
            <span className="stat-tile__k">{k}</span>
            <span className="stat-tile__v">{fmtNum(v)}</span>
          </div>
        ))}
      </div>

      {result.effectSizes.length > 0 && (
        <section>
          <h3>Effect size</h3>
          <ul className="effects">
            {result.effectSizes.map((e) => (
              <li key={e.name}>
                <strong>{e.name}</strong>: {fmtNum(e.value)}
                {e.ciLow !== null && e.ciHigh !== null && (
                  <span className="muted"> [{fmtNum(e.ciLow)}, {fmtNum(e.ciHigh)}]</span>
                )}
                {e.magnitude && <span className="tag">{e.magnitude}</span>}
              </li>
            ))}
          </ul>
        </section>
      )}

      {result.assumptions.length > 0 && (
        <section>
          <h3>Assumptions</h3>
          <ul className="assumptions">
            {result.assumptions.map((a) => (
              <li key={a.name} className={assumptionClass(a.passed)}>
                <span className="assumptions__dot" aria-hidden />
                <span><strong>{a.name}</strong> — {a.detail}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {specs.map((spec, i) => (
        <section key={i}>
          <h3>Plot</h3>
          <VegaLiteChart spec={spec} />
        </section>
      ))}

      {result.tables.map((t) => (
        <section key={t.title}>
          <h3>{t.title}</h3>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>{t.columns.map((c) => <th key={c}>{c || " "}</th>)}</tr>
              </thead>
              <tbody>
                {t.rows.map((row, i) => (
                  <tr key={i}>
                    {row.map((cell, j) => <td key={j}>{renderCell(cell)}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}

      {result.notes.length > 0 && (
        <section className="notes">
          <h3>Notes</h3>
          <ul>{result.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
        </section>
      )}
    </div>
  );
}

function assumptionClass(passed: boolean | null): string {
  if (passed === true) return "ok";
  if (passed === false) return "warn";
  return "info";
}

function renderCell(cell: unknown): string {
  if (cell === null || cell === undefined) return "—";
  if (typeof cell === "number") return fmtNum(cell);
  if (typeof cell === "boolean") return cell ? "yes" : "no";
  return String(cell);
}
