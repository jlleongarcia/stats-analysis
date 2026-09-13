/** Message contract between the UI and the Pyodide worker. */

import type { Registry, ParamValues, RoleMapping, TestResult } from "../types";

export type ColumnarData = Record<string, unknown[]>;

export type WorkerRequest =
  | { kind: "init"; id: string; wheelUrl: string; pyodideUrl: string }
  | { kind: "registry"; id: string }
  | {
      kind: "run";
      id: string;
      testId: string;
      data: ColumnarData;
      roles: RoleMapping;
      params: ParamValues;
    }
  /**
   * One SPC Studio operation. Deliberately generic rather than a message per
   * operation: the Studio's workflow is stateful, but every call re-sends its
   * full exclusion set, so the Python side stays a pure function and this
   * channel never has to model a session.
   */
  | { kind: "spc"; id: string; fn: string; payload: unknown };

export type WorkerResponse =
  | { kind: "progress"; stage: string; detail?: string }
  | { kind: "ready"; id: string }
  | { kind: "registry"; id: string; registry: Registry }
  | { kind: "result"; id: string; result: TestResult }
  | { kind: "spc"; id: string; result: unknown }
  | { kind: "error"; id: string; message: string; kindHint?: "data" | "internal" };
