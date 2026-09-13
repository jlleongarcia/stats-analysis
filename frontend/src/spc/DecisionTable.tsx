/**
 * The analyst's review of every flagged point.
 *
 * The rule the whole workflow exists to protect: a point may only be removed
 * when a real-world assignable cause can be documented. Statistical
 * significance alone is never sufficient (Oakland, Ch. 4-5). So "Remove" is
 * inert until a cause is typed, and the engine rejects the request anyway if
 * the UI is ever bypassed.
 */
import { useState } from "react";
import type { SpcDecision, SpcPoint } from "../types";
import { fmtNum } from "../results/format";

interface Props {
  points: SpcPoint[];
  flagged: number[];
  decisions: Record<number, SpcDecision>;
  onChange: (position: number, patch: Partial<SpcDecision>) => void;
  onRemoveAll: (cause: string) => void;
  onClear: () => void;
  disabled: boolean;
}

export function DecisionTable({
  points,
  flagged,
  decisions,
  onChange,
  onRemoveAll,
  onClear,
  disabled,
}: Props) {
  const [bulkCause, setBulkCause] = useState("");
  const byPosition = new Map(points.map((p) => [p.position, p]));

  const pending = flagged.filter((p) => {
    const d = decisions[p];
    return d?.remove && !d.cause.trim();
  });

  return (
    <section className="spc-decisions">
      <header className="spc-decisions__head">
        <h3>Review {flagged.length} flagged point{flagged.length === 1 ? "" : "s"}</h3>
        <p className="muted">
          The rules flag <em>candidates</em>, not confirmed special causes. Remove a point
          only if you can name what went wrong in the process. If you cannot, keep it —
          retaining a flagged point is a valid, recorded decision.
        </p>
      </header>

      <div className="spc-bulk">
        <input
          type="text"
          value={bulkCause}
          disabled={disabled}
          placeholder="Cause applying to every flagged point, e.g. Chiller trip, WO-2026-1142"
          onChange={(e) => setBulkCause(e.target.value)}
        />
        <button
          className="btn"
          disabled={disabled || !bulkCause.trim()}
          onClick={() => onRemoveAll(bulkCause.trim())}
        >
          Remove all flagged
        </button>
        <button className="btn" disabled={disabled} onClick={onClear}>
          Clear decisions
        </button>
      </div>

      <div className="table-scroll">
        <table className="spc-table">
          <thead>
            <tr>
              <th>Observation</th>
              <th>Value</th>
              <th>Rules fired</th>
              <th>Remove</th>
              <th>Assignable cause</th>
            </tr>
          </thead>
          <tbody>
            {flagged.map((position) => {
              const point = byPosition.get(position);
              if (!point) return null;
              const decision = decisions[position] ?? { position, remove: false, cause: "" };
              const needsCause = decision.remove && !decision.cause.trim();
              return (
                <tr key={position} className={decision.remove ? "is-removing" : undefined}>
                  <td>{point.label}</td>
                  <td className="num">{fmtNum(point.value)}</td>
                  <td className="spc-rules">{point.rules.join(", ")}</td>
                  <td>
                    <input
                      type="checkbox"
                      checked={decision.remove}
                      disabled={disabled}
                      aria-label={`Remove observation ${point.label}`}
                      onChange={(e) => onChange(position, { remove: e.target.checked })}
                    />
                  </td>
                  <td>
                    <input
                      type="text"
                      className={needsCause ? "input--needed" : undefined}
                      value={decision.cause}
                      disabled={disabled}
                      placeholder={decision.remove ? "Required to remove" : "Optional note"}
                      aria-label={`Assignable cause for ${point.label}`}
                      onChange={(e) => onChange(position, { cause: e.target.value })}
                    />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {pending.length > 0 && (
        <p className="warn-box">
          {pending.length} point{pending.length === 1 ? " is" : "s are"} marked for removal
          without a documented cause. Add one, or untick the point.
        </p>
      )}
    </section>
  );
}
