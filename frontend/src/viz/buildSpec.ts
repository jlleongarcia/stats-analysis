/** Convert a stats_core PlotSpec (or an explorer request) into a Vega-Lite spec. */
import type { TopLevelSpec } from "vega-lite";
import type { PlotSpec } from "../types";

const BASE = {
  $schema: "https://vega.github.io/schema/vega-lite/v5.json",
  width: "container" as const,
  height: 280,
  autosize: { type: "fit" as const, contains: "padding" as const },
};

function records(data: Record<string, unknown[]>): Record<string, unknown>[] {
  const keys = Object.keys(data);
  const n = keys.length ? data[keys[0]].length : 0;
  const rows: Record<string, unknown>[] = [];
  for (let i = 0; i < n; i++) {
    const r: Record<string, unknown> = {};
    for (const k of keys) r[k] = data[k][i];
    rows.push(r);
  }
  return rows;
}

export function specFromPlot(plot: PlotSpec): TopLevelSpec {
  const values = records(plot.data);
  const enc = plot.encoding ?? {};

  switch (plot.kind) {
    case "histogram": {
      const xTitle = enc.x?.title ?? "value";
      const layers: unknown[] = [
        {
          mark: { type: "bar", tooltip: true },
          encoding: {
            x: { field: "x", bin: { maxbins: 30 }, title: xTitle },
            y: { aggregate: "count", title: "count" },
          },
        },
      ];
      if (typeof plot.rule === "number") {
        layers.push({
          mark: { type: "rule", color: "#f472b6", size: 2 },
          encoding: { x: { datum: plot.rule } },
        });
      }
      return { ...BASE, data: { values }, layer: layers } as TopLevelSpec;
    }

    case "box":
      return {
        ...BASE,
        data: { values },
        mark: { type: "boxplot", extent: "min-max" },
        encoding: {
          x: { field: "group", type: "nominal", title: enc.x?.title ?? "group" },
          y: { field: "value", type: "quantitative", title: enc.y?.title ?? "value" },
          color: { field: "group", type: "nominal", legend: null },
        },
      } as TopLevelSpec;

    case "bar":
      return {
        ...BASE,
        data: { values },
        mark: { type: "bar", tooltip: true },
        encoding: {
          x: { field: "category", type: "nominal", title: enc.x?.title ?? "category" },
          y: { field: "value", type: "quantitative", title: enc.y?.title ?? "count" },
        },
      } as TopLevelSpec;

    case "scatter": {
      const layers: unknown[] = [
        { mark: { type: "point", filled: true, tooltip: true, opacity: 0.7 } },
      ];
      if (plot.regression) {
        layers.push({
          mark: { type: "line", color: "#f472b6" },
          transform: [{ regression: "y", on: "x" }],
        });
      }
      const encoding: Record<string, unknown> = {
        x: { field: "x", type: "quantitative", title: enc.x?.title ?? "x" },
        y: { field: "y", type: "quantitative", title: enc.y?.title ?? "y" },
      };
      if (Array.isArray(plot.data.group)) {
        encoding.color = { field: "group", type: "nominal", title: enc.color?.title ?? "group" };
      }
      return {
        ...BASE,
        data: { values },
        encoding,
        layer: layers,
      } as TopLevelSpec;
    }

    case "line":
      return {
        ...BASE,
        data: { values },
        mark: { type: "line", point: true, tooltip: true },
        encoding: {
          x: { field: "x", type: "ordinal", title: enc.x?.title ?? "x", sort: null },
          y: { field: "y", type: "quantitative", title: enc.y?.title ?? "y" },
        },
      } as TopLevelSpec;

    case "dendrogram":
      return {
        ...BASE,
        data: { values },
        mark: { type: "line", interpolate: "linear" },
        encoding: {
          x: { field: "x", type: "quantitative", axis: null },
          y: { field: "y", type: "quantitative", title: "distance" },
          detail: { field: "segment", type: "nominal" },
          order: { field: "order", type: "ordinal" },
        },
      } as TopLevelSpec;

    case "tree": {
      const nodeValues = records(plot.data);
      const edgesRaw = plot.edges as Record<string, unknown[]> | undefined;
      const edgeValues = edgesRaw ? records(edgesRaw) : [];
      return {
        ...BASE,
        height: 320,
        layer: [
          {
            data: { values: edgeValues },
            mark: { type: "rule", color: "#94a3b8" },
            encoding: {
              x: { field: "x0", type: "quantitative", axis: null },
              y: { field: "y0", type: "quantitative", axis: null, scale: { reverse: true } },
              x2: { field: "x1" },
              y2: { field: "y1" },
            },
          },
          {
            data: { values: nodeValues },
            mark: { type: "point", filled: true, size: 160, tooltip: true },
            encoding: {
              x: { field: "x", type: "quantitative", axis: null },
              y: { field: "y", type: "quantitative", axis: null, scale: { reverse: true } },
              color: { field: "leaf", type: "nominal", legend: null },
            },
          },
          {
            data: { values: nodeValues },
            mark: { type: "text", dy: 16, fontSize: 9, lineBreak: "\n" },
            encoding: {
              x: { field: "x", type: "quantitative" },
              y: { field: "y", type: "quantitative", scale: { reverse: true } },
              text: { field: "label" },
            },
          },
        ],
      } as TopLevelSpec;
    }

    case "heatmap":
      return {
        ...BASE,
        data: { values },
        mark: { type: "rect", tooltip: true },
        encoding: {
          x: { field: "col", type: "nominal", title: null },
          y: { field: "row", type: "nominal", title: null },
          color: { field: "value", type: "quantitative", scale: { scheme: "blueorange", domainMid: 0 } },
        },
      } as TopLevelSpec;

    case "interaction":
      return {
        ...BASE,
        data: { values },
        mark: { type: "line", point: true },
        encoding: {
          x: { field: "a", type: "nominal", title: enc.x?.title ?? "Factor A" },
          y: { field: "y", aggregate: "mean", type: "quantitative", title: enc.y?.title ?? "mean" },
          color: { field: "b", type: "nominal", title: "Factor B" },
        },
      } as TopLevelSpec;

    default:
      return { ...BASE, data: { values }, mark: "point" } as TopLevelSpec;
  }
}

/** Explorer: plain X vs Y from two dataset columns. */
export function specForExplore(
  rows: Record<string, unknown>[],
  x: string,
  y: string | null,
  color: string | null,
  mark: "point" | "line" | "bar",
): TopLevelSpec {
  const encoding: Record<string, unknown> = {
    x: { field: x, type: y ? "quantitative" : "nominal", title: x },
  };
  if (y) encoding.y = { field: y, type: "quantitative", title: y };
  else encoding.y = { aggregate: "count", title: "count" };
  if (color) encoding.color = { field: color, type: "nominal", title: color };

  return {
    ...BASE,
    height: 360,
    data: { values: rows },
    mark: { type: mark, tooltip: true, filled: mark === "point", opacity: 0.75 },
    encoding,
  } as TopLevelSpec;
}
