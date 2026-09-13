/** Convert a stats_core PlotSpec (or an explorer request) into a Vega-Lite spec. */
import type { TopLevelSpec } from "vega-lite";
import type { PlotSpec } from "../types";

const BASE = {
  $schema: "https://vega.github.io/schema/vega-lite/v5.json",
  width: "container" as const,
  height: 280,
  autosize: { type: "fit" as const, contains: "padding" as const },
};

/**
 * Control-chart semantics, drawn from the app's own status tokens (--err,
 * --warn, --ok, --accent) so a chart reads like the rest of the UI.
 *
 * Colour is never the only cue. Under tritanopia the warning amber and the
 * centre-line emerald sit ~3 ΔE apart, which is not separable, so each
 * reference line also carries a distinct dash pattern and a direct label at the
 * right edge, and violating points differ in shape and size as well as hue.
 */
const CONTROL_COLOR: Record<string, string> = {
  action: "#fb7185",
  warning: "#fbbf24",
  centre: "#34d399",
  spec: "#fb7185",
};
const CONTROL_DASH: Record<string, number[]> = {
  action: [7, 4],
  warning: [3, 3],
  centre: [],
  spec: [7, 4],
};
const BAND_OPACITY: Record<string, number> = { warning: 0.18, centre: 0.06 };

const POINT_IN_CONTROL = "#38bdf8";
const POINT_VIOLATION = "#fb7185";

interface ControlLine {
  value: number;
  label: string;
  kind: string;
}
interface ControlBand {
  from: number;
  to: number;
  kind: string;
}

/** One layered control-chart panel (individuals or moving range). */
function controlChartSpec(plot: PlotSpec): TopLevelSpec {
  const enc = plot.encoding ?? {};
  const values = records(plot.data);
  const lines = (plot.lines ?? []) as ControlLine[];
  const bands = (plot.bands ?? []) as ControlBand[];
  const hasRules = Array.isArray(plot.data.rules);

  const xTitle = enc.x?.title ?? "observation";
  const yTitle = enc.y?.title ?? "value";
  const xEnc = {
    field: "x",
    type: "ordinal" as const,
    title: xTitle,
    sort: null,
    axis: { labelOverlap: "greedy", labelAngle: -45 },
  };
  // An individuals chart must never include zero: it resolves small excursions
  // around the centre line, and anchoring at zero flattens them into a stripe.
  // A range chart is the opposite - its lower limit genuinely is zero.
  // `padding` keeps a point that sits outside the action limit from being
  // clipped against the axis - which is the one point the reader most needs.
  const yScale = { zero: plot.panel === "movingRange", padding: 14 };
  const yEnc = {
    field: "y",
    type: "quantitative" as const,
    title: yTitle,
    scale: yScale,
  };

  const layers: unknown[] = [];

  // Zone shading sits underneath everything, keyed to a one-row source so the
  // rect spans the full plot width without needing an x encoding.
  for (const band of bands) {
    layers.push({
      data: { values: [{}] },
      mark: {
        type: "rect",
        color: CONTROL_COLOR[band.kind] ?? "#64748b",
        opacity: BAND_OPACITY[band.kind] ?? 0.06,
      },
      encoding: { y: { datum: band.from }, y2: { datum: band.to } },
    });
  }

  for (const line of lines) {
    layers.push({
      data: { values: [{}] },
      mark: {
        type: "rule",
        color: CONTROL_COLOR[line.kind] ?? "#64748b",
        strokeDash: CONTROL_DASH[line.kind] ?? [],
        size: 1.5,
      },
      encoding: { y: { datum: line.value } },
    });
    // Direct label in the right-hand padding: the non-colour cue that keeps the
    // lines identifiable without a legend.
    //
    // Positioned by pixel expression, NOT by `x: {datum: lastLabel}`. Layers
    // share one ordinal x scale, so a datum-positioned label injects its label
    // into that scale's domain ahead of the data layer -- which both stacks the
    // labels at the left edge and reorders the axis to put the last observation
    // first. Anchoring to the view width sidesteps the scale entirely.
    layers.push({
      data: { values: [{}] },
      mark: {
        type: "text",
        x: { expr: "width" },
        align: "left",
        baseline: "middle",
        dx: 6,
        fontSize: 10,
        fontWeight: 600,
        color: CONTROL_COLOR[line.kind] ?? "#64748b",
        text: line.label,
      },
      encoding: { y: { datum: line.value } },
    });
  }

  // Per-point limits (p and u charts, where the sample size varies) are drawn
  // as a stepped boundary rather than a straight rule: the limit genuinely
  // changes between samples, and a straight line would misstate every one.
  const limitSeries = plot.limitSeries as { ucl?: number[]; lcl?: number[] } | undefined;
  for (const side of ["ucl", "lcl"] as const) {
    const series = limitSeries?.[side];
    if (!series) continue;
    layers.push({
      data: { values: values.map((row, i) => ({ ...row, limit: series[i] })) },
      mark: { type: "line", color: CONTROL_COLOR.action, strokeDash: CONTROL_DASH.action,
              strokeWidth: 1.5, interpolate: "step-after" },
      encoding: { x: xEnc, y: { field: "limit", type: "quantitative", scale: yScale } },
    });
  }

  // A single continuous line through every point in order: the chronology has
  // to stay readable regardless of which points are flagged.
  layers.push({
    mark: { type: "line", color: POINT_IN_CONTROL, strokeWidth: 2, opacity: 0.85 },
    encoding: { x: xEnc, y: yEnc },
  });

  layers.push({
    mark: { type: "point", filled: true, opacity: 1 },
    encoding: {
      x: xEnc,
      y: yEnc,
      color: {
        field: "status",
        type: "nominal",
        title: "Point",
        scale: {
          domain: ["in control", "violation"],
          range: [POINT_IN_CONTROL, POINT_VIOLATION],
        },
      },
      shape: {
        field: "status",
        type: "nominal",
        title: "Point",
        scale: { domain: ["in control", "violation"], range: ["circle", "triangle-up"] },
      },
      // A conditional rather than a scale over the nominal field: Vega-Lite
      // warns on size-over-discrete, and this says what is meant anyway.
      size: {
        condition: { test: "datum.status === 'violation'", value: 150 },
        value: 70,
      },
      tooltip: [
        { field: "x", type: "ordinal", title: xTitle },
        { field: "y", type: "quantitative", title: yTitle, format: ".4f" },
        ...(hasRules ? [{ field: "rules", type: "nominal", title: "Rules fired" }] : []),
      ],
    },
  });

  return {
    ...BASE,
    height: plot.panel === "movingRange" ? 170 : 300,
    padding: { left: 0, top: 0, bottom: 0, right: 34 },
    title: typeof plot.title === "string" ? plot.title : undefined,
    data: { values },
    layer: layers,
    resolve: { scale: { y: "shared" } },
  } as TopLevelSpec;
}

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
    case "controlChart":
      return controlChartSpec(plot);

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
      // Several labelled reference lines (capability: LSL, USL, mean). Each gets
      // its own dash pattern and a label pinned to the top of the plot, so the
      // three stay tellable apart without relying on hue.
      for (const line of (plot.rules ?? []) as ControlLine[]) {
        layers.push({
          mark: {
            type: "rule",
            color: CONTROL_COLOR[line.kind] ?? "#f472b6",
            strokeDash: CONTROL_DASH[line.kind] ?? [],
            size: 2,
          },
          encoding: { x: { datum: line.value } },
        });
        layers.push({
          mark: {
            type: "text",
            y: 6,
            align: "center",
            baseline: "top",
            fontSize: 10,
            fontWeight: 600,
            color: CONTROL_COLOR[line.kind] ?? "#f472b6",
            text: line.label,
          },
          encoding: { x: { datum: line.value } },
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
