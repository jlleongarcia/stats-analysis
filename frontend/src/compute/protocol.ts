/** Message contract between the UI and the Pyodide worker. */

import type { Registry, ParamValues, RoleMapping, TestResult } from "../types";

export type ColumnarData = Record<string, unknown[]>;

export type WorkerRequest =
  | { kind: "init"; id: string; wheelUrl: string }
  | { kind: "registry"; id: string }
  | {
      kind: "run";
      id: string;
      testId: string;
      data: ColumnarData;
      roles: RoleMapping;
      params: ParamValues;
    };

export type WorkerResponse =
  | { kind: "progress"; stage: string; detail?: string }
  | { kind: "ready"; id: string }
  | { kind: "registry"; id: string; registry: Registry }
  | { kind: "result"; id: string; result: TestResult }
  | { kind: "error"; id: string; message: string; kindHint?: "data" | "internal" };
