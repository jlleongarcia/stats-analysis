/** Shared types: dataset shape, registry metadata, and the standard result. */

export type ColumnType = "numeric" | "categorical" | "datetime" | "boolean";

export interface ColumnMeta {
  name: string;
  /** Inferred (and user-overridable) semantic type. */
  type: ColumnType;
  /** Fraction of non-missing values, 0..1. */
  fill: number;
  /** A few example values for the UI. */
  sample: string[];
}

export interface Dataset {
  id: string;
  name: string;
  createdAt: number;
  columns: ColumnMeta[];
  /** Row-oriented records. Values are strings, numbers, booleans or null. */
  rows: Record<string, unknown>[];
  rowCount: number;
}

/** ---- Registry metadata (mirrors stats_core.registry) --------------------- */

export interface RoleSpec {
  key: string;
  label: string;
  dtype: "numeric" | "categorical" | "any";
  multiple: boolean;
  required: boolean;
  help: string;
}

export interface ParamSpec {
  key: string;
  label: string;
  type: "number" | "select" | "bool" | "list";
  default: unknown;
  choices: string[];
  help: string;
}

export interface TestSpec {
  id: string;
  name: string;
  family: string;
  description: string;
  roles: RoleSpec[];
  params: ParamSpec[];
  assumptions: string[];
  min_n: number;
}

export interface Registry {
  version: number;
  families: string[];
  tests: TestSpec[];
}

/** ---- Standard result (mirrors stats_core.results.TestResult.to_dict) ----- */

export interface AssumptionCheck {
  name: string;
  passed: boolean | null;
  detail: string;
  statistic: number | null;
  pValue: number | null;
}

export interface EffectSize {
  name: string;
  value: number | null;
  ciLow: number | null;
  ciHigh: number | null;
  magnitude: string | null;
}

export interface ResultTable {
  title: string;
  columns: string[];
  rows: unknown[][];
}

export interface PlotSpec {
  kind: "histogram" | "box" | "scatter" | "bar" | "heatmap" | "interaction"
      | "line" | "dendrogram" | "tree";
  data: Record<string, unknown[]>;
  encoding?: Record<string, { field: string; title?: string }>;
  [k: string]: unknown;
}

export interface TestResult {
  testId: string;
  testName: string;
  summary: string;
  apa: string;
  statistic: Record<string, number>;
  pValue: number | null;
  effectSizes: EffectSize[];
  assumptions: AssumptionCheck[];
  tables: ResultTable[];
  plotSpecs: PlotSpec[];
  notes: string[];
}

export type RoleMapping = Record<string, string | string[]>;
export type ParamValues = Record<string, unknown>;

export interface SavedAnalysis {
  id: string;
  datasetId: string;
  datasetName: string;
  testId: string;
  testName: string;
  roles: RoleMapping;
  params: ParamValues;
  result: TestResult;
  createdAt: number;
}
