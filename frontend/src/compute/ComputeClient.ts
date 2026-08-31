/**
 * Thin async facade over the Pyodide worker. The rest of the app depends only
 * on this interface, so a server-backed implementation could be dropped in
 * later without touching the UI.
 */
import type { Dataset, ParamValues, Registry, RoleMapping, TestResult } from "../types";
import type { ColumnarData, WorkerRequest, WorkerResponse } from "./protocol";

export type BootStage = { stage: string; detail?: string };

export class ComputeError extends Error {
  constructor(
    message: string,
    readonly kindHint: "data" | "internal" = "internal",
  ) {
    super(message);
    this.name = "ComputeError";
  }
}

type Pending = {
  resolve: (value: unknown) => void;
  reject: (err: Error) => void;
};

export class ComputeClient {
  private worker: Worker;
  private pending = new Map<string, Pending>();
  private seq = 0;
  private booted?: Promise<void>;

  onProgress: ((s: BootStage) => void) | null = null;

  constructor() {
    this.worker = new Worker(new URL("./pyodide.worker.ts", import.meta.url), {
      type: "module",
      name: "pyodide-compute",
    });
    this.worker.onmessage = (ev: MessageEvent<WorkerResponse>) => this.handle(ev.data);
    this.worker.onerror = (ev) => {
      const err = new ComputeError(ev.message || "Worker crashed");
      for (const p of this.pending.values()) p.reject(err);
      this.pending.clear();
    };
  }

  private nextId() {
    return `r${++this.seq}`;
  }

  private handle(msg: WorkerResponse) {
    if (msg.kind === "progress") {
      this.onProgress?.({ stage: msg.stage, detail: msg.detail });
      return;
    }
    const p = this.pending.get(msg.id);
    if (!p) return;
    this.pending.delete(msg.id);
    if (msg.kind === "error") {
      p.reject(new ComputeError(msg.message, msg.kindHint ?? "internal"));
    } else if (msg.kind === "ready") {
      p.resolve(undefined);
    } else if (msg.kind === "registry") {
      p.resolve(msg.registry);
    } else if (msg.kind === "result") {
      p.resolve(msg.result);
    }
  }

  private request<T>(make: (id: string) => WorkerRequest): Promise<T> {
    const id = this.nextId();
    return new Promise<T>((resolve, reject) => {
      this.pending.set(id, { resolve: resolve as (v: unknown) => void, reject });
      this.worker.postMessage(make(id));
    });
  }

  /** Idempotent: safe to call from multiple places; boot happens once. */
  init(): Promise<void> {
    if (!this.booted) {
      const asset = (path: string) =>
        new URL(`${import.meta.env.BASE_URL}${path}`, self.location.href).href;
      // Resolved here rather than in the worker: only the main thread knows
      // Vite's BASE_URL, and the worker's own location sits under /assets/.
      const wheelUrl = asset(`pyodide-packages/${__STATS_CORE_WHEEL__}`);
      const pyodideUrl = asset("pyodide/");
      this.booted = this.request<void>((id) => ({ kind: "init", id, wheelUrl, pyodideUrl }));
    }
    return this.booted;
  }

  async getRegistry(): Promise<Registry> {
    await this.init();
    return this.request<Registry>((id) => ({ kind: "registry", id }));
  }

  async run(
    dataset: Dataset,
    testId: string,
    roles: RoleMapping,
    params: ParamValues,
  ): Promise<TestResult> {
    await this.init();
    return this.request<TestResult>((id) => ({
      kind: "run",
      id,
      testId,
      data: toColumnar(dataset),
      roles,
      params,
    }));
  }

  terminate() {
    this.worker.terminate();
  }
}

function toColumnar(dataset: Dataset): ColumnarData {
  const cols = dataset.columns.map((c) => c.name);
  const out: ColumnarData = {};
  for (const c of cols) out[c] = new Array(dataset.rows.length);
  dataset.rows.forEach((row, i) => {
    for (const c of cols) {
      const v = row[c];
      (out[c] as unknown[])[i] = v === undefined ? null : v;
    }
  });
  return out;
}

/** Module-level singleton - one WASM runtime per tab is plenty. */
let singleton: ComputeClient | null = null;
export function getComputeClient(): ComputeClient {
  if (!singleton) singleton = new ComputeClient();
  return singleton;
}
