/** Column type inference + a single place to coerce cells for analysis. */
import type { ColumnMeta, ColumnType } from "../types";

const BOOL_TOKENS = new Set(["true", "false", "yes", "no", "y", "n", "t", "f", "0", "1"]);
const SAMPLE_LIMIT = 200;

export function inferColumns(
  columns: string[],
  rows: Record<string, unknown>[],
): ColumnMeta[] {
  return columns.map((name) => {
    const values = rows.map((r) => r[name]);
    const present = values.filter((v) => v !== null && v !== undefined && v !== "");
    const fill = rows.length ? present.length / rows.length : 0;
    const probe = present.slice(0, SAMPLE_LIMIT);

    return {
      name,
      type: classify(probe),
      fill,
      sample: probe.slice(0, 5).map((v) => String(v)),
    };
  });
}

function classify(values: unknown[]): ColumnType {
  if (values.length === 0) return "categorical";

  const numeric = values.filter((v) => isFiniteNumber(v)).length / values.length;
  if (numeric >= 0.85) {
    const distinct = new Set(values.map((v) => Number(v)));
    // 0/1 or 1/2 columns are more useful treated as categorical groups
    if (distinct.size <= 2 && [...distinct].every((n) => n === 0 || n === 1)) return "boolean";
    return "numeric";
  }

  const bool = values.filter((v) => BOOL_TOKENS.has(String(v).toLowerCase())).length / values.length;
  if (bool >= 0.9) return "boolean";

  const date = values.filter((v) => isDateLike(v)).length / values.length;
  if (date >= 0.85) return "datetime";

  return "categorical";
}

export function isFiniteNumber(v: unknown): boolean {
  if (typeof v === "number") return Number.isFinite(v);
  if (typeof v === "string" && v.trim() !== "") return Number.isFinite(Number(v.replace(",", ".")));
  return false;
}

function isDateLike(v: unknown): boolean {
  if (v instanceof Date) return true;
  if (typeof v !== "string") return false;
  return /\d{4}-\d{2}-\d{2}/.test(v) || !Number.isNaN(Date.parse(v));
}

/** Numeric columns with enough fill, for role pickers. */
export function numericColumns(meta: ColumnMeta[]): ColumnMeta[] {
  return meta.filter((c) => c.type === "numeric" && c.fill > 0);
}

export function categoricalColumns(meta: ColumnMeta[]): ColumnMeta[] {
  return meta.filter((c) => c.type !== "numeric" && c.type !== "datetime");
}

export function columnsForRole(meta: ColumnMeta[], dtype: "numeric" | "categorical" | "any"): ColumnMeta[] {
  if (dtype === "numeric") return numericColumns(meta);
  if (dtype === "categorical") return meta.filter((c) => c.fill > 0);
  return meta;
}
