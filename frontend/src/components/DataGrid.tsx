import { useMemo } from "react";
import type { Dataset } from "../types";

interface Props {
  dataset: Dataset;
  maxRows?: number;
}

const TYPE_GLYPH: Record<string, string> = {
  numeric: "#",
  categorical: "A",
  datetime: "◷",
  boolean: "◐",
};

export function DataGrid({ dataset, maxRows = 50 }: Props) {
  const rows = useMemo(() => dataset.rows.slice(0, maxRows), [dataset.rows, maxRows]);

  return (
    <div className="table-scroll">
      <table className="grid">
        <thead>
          <tr>
            <th className="grid__idx">#</th>
            {dataset.columns.map((c) => (
              <th key={c.name}>
                <span className="grid__type" title={c.type}>{TYPE_GLYPH[c.type] ?? "?"}</span>
                {c.name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              <td className="grid__idx">{i + 1}</td>
              {dataset.columns.map((c) => (
                <td key={c.name}>{cell(row[c.name])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {dataset.rowCount > rows.length && (
        <p className="muted grid__more">
          Showing {rows.length} of {dataset.rowCount.toLocaleString()} rows
        </p>
      )}
    </div>
  );
}

function cell(v: unknown): string {
  if (v === null || v === undefined || v === "") return "·";
  return String(v);
}
