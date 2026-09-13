/**
 * The certified baseline's decision log.
 *
 * Every point the rules flagged appears here, removed or not — "reviewed and
 * retained" is itself a decision worth recording. The CSV export is the
 * artefact an auditor actually asks for.
 */
import type { SpcBaseline } from "../types";
import { fmtNum } from "../results/format";

function toCsv(columns: string[], rows: unknown[][]): string {
  const cell = (v: unknown) => {
    if (v === null || v === undefined) return "";
    const s = String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [columns.map(cell).join(","), ...rows.map((r) => r.map(cell).join(","))].join("\n");
}

export function AuditTrail({ baseline }: { baseline: SpcBaseline }) {
  const { auditLog } = baseline;

  const download = () => {
    const blob = new Blob([toCsv(auditLog.columns, auditLog.rows)], {
      type: "text/csv;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `phase-i-audit-${baseline.column}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <section className="spc-audit">
      <header className="spc-decisions__head">
        <h3>Audit trail</h3>
        <p className="muted">
          Every flagged point and what was decided about it, with the control limits as they
          stood at review time.
        </p>
      </header>

      {auditLog.rows.length === 0 ? (
        <p className="muted">No points were flagged, so no decisions were called for.</p>
      ) : (
        <>
          <div className="table-scroll">
            <table className="spc-table">
              <thead>
                <tr>
                  {auditLog.columns.map((c) => (
                    <th key={c}>{c.replace(/_/g, " ")}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {auditLog.rows.map((row, i) => (
                  <tr key={i} className={row[4] === "Removed" ? "is-removing" : undefined}>
                    {row.map((cell, j) => (
                      <td key={j} className={typeof cell === "number" ? "num" : undefined}>
                        {typeof cell === "number" ? fmtNum(cell) : String(cell ?? "—")}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <button className="btn" onClick={download}>
            Download audit log (CSV)
          </button>
        </>
      )}
    </section>
  );
}
