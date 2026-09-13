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

/** What the loaded stats_core wheel actually contains — see registry._engine_info. */
export interface EngineInfo {
  version: string;
  testCount: number;
  spcModules: string[];
}

export interface Registry {
  version: number;
  families: string[];
  tests: TestSpec[];
  /** Absent on wheels built before this field existed — which is itself the signal. */
  engine?: EngineInfo;
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
      | "line" | "dendrogram" | "tree" | "controlChart";
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

/** ---- SPC Studio -------------------------------------------------------- */

export interface RuleConfig {
  rule2_k: number;
  rule2_window: number;
  rule3_k: number;
  rule4_k: number;
}

export const DEFAULT_RULE_CONFIG: RuleConfig = {
  rule2_k: 2,
  rule2_window: 3,
  rule3_k: 8,
  rule4_k: 6,
};

/** One observation as returned by the engine, for the decision table. */
export interface SpcPoint {
  position: number;
  label: string;
  /** Row index in the original dataset — the duplicate-label-safe handle. */
  sourceRow: number;
  value: number;
  mr: number | null;
  rules: string[];
  flagged: boolean;
}

export interface SpcTable {
  columns: string[];
  rows: unknown[][];
}

export interface SpcNormality {
  name: string;
  passed: boolean | null;
  detail: string;
  statistic: number | null;
  pValue: number | null;
}

/** Result of one evaluation pass (`spc_call("evaluate")`). */
export interface SpcEvaluation {
  column: string;
  orderColumn: string | null;
  ruleConfig: RuleConfig;
  limits: Record<string, number>;
  points: SpcPoint[];
  flagged: number[];
  anyViolations: boolean;
  nEvaluated: number;
  nExcluded: number;
  controlLines: SpcTable;
  charts: PlotSpec[];
  normality: SpcNormality;
}

/** Certified Phase I baseline (`spc_call("certify")`). */
export interface SpcBaseline {
  column: string;
  ruleConfig: RuleConfig;
  limits: Record<string, number>;
  nOriginal: number;
  nFinal: number;
  nRemoved: number;
  removalRate: number;
  nPasses: number;
  finalPassHasViolations: boolean;
  removedSourceRows: number[];
  auditLog: SpcTable;
  auditColumns: string[];
  controlLines: SpcTable;
  charts: PlotSpec[];
  verdicts: string[];
  normality: SpcNormality;
}

export interface SpcCapability {
  column: string;
  capability: Record<string, number | boolean>;
  inControl: boolean;
  verdicts: string[];
  normality: SpcNormality;
}

/** One analyst ruling on one flagged point. */
export interface SpcDecision {
  position: number;
  remove: boolean;
  cause: string;
}

/**
 * A saved Phase I study. This is the durable artefact the old Streamlit tool
 * never had: its decision log lived in `session_state` and a browser refresh
 * destroyed it.
 */
export interface SpcStudy {
  id: string;
  datasetId: string;
  datasetName: string;
  column: string;
  orderColumn: string | null;
  ruleConfig: RuleConfig;
  decisions: SpcDecision[];
  baseline: SpcBaseline | null;
  createdAt: number;
  updatedAt: number;
}
