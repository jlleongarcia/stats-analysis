import type { ColumnMeta, ColumnType } from "../types";

interface Props {
  columns: ColumnMeta[];
  onChange: (name: string, type: ColumnType) => void;
}

const TYPES: ColumnType[] = ["numeric", "categorical", "datetime", "boolean"];

export function ColumnTypePanel({ columns, onChange }: Props) {
  return (
    <div className="coltypes">
      {columns.map((c) => (
        <div key={c.name} className="coltypes__row">
          <div className="coltypes__name">
            <strong>{c.name}</strong>
            <span className="muted">
              {(c.fill * 100).toFixed(0)}% filled · e.g. {c.sample.slice(0, 3).join(", ") || "—"}
            </span>
          </div>
          <select
            value={c.type}
            onChange={(e) => onChange(c.name, e.target.value as ColumnType)}
          >
            {TYPES.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>
      ))}
    </div>
  );
}
