import { useEffect, useRef } from "react";
import embed, { type Result as EmbedResult } from "vega-embed";
import type { TopLevelSpec } from "vega-lite";

interface Props {
  spec: TopLevelSpec;
  className?: string;
}

/** Renders a Vega-Lite spec, re-embedding on change and cleaning up the view. */
export function VegaLiteChart({ spec, className }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const view = useRef<EmbedResult | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (host.current) {
      embed(host.current, spec, {
        actions: { export: true, source: false, compiled: false, editor: false },
        renderer: "canvas",
        config: {
          background: "transparent",
          axis: { labelColor: "#94a3b8", titleColor: "#cbd5e1", gridColor: "#1e293b", domainColor: "#334155" },
          legend: { labelColor: "#94a3b8", titleColor: "#cbd5e1" },
          view: { stroke: "transparent" },
          range: { category: ["#38bdf8", "#818cf8", "#f472b6", "#fbbf24", "#34d399", "#fb7185"] },
        },
      })
        .then((res) => {
          if (cancelled) res.finalize();
          else view.current = res;
        })
        .catch((err) => console.error("[vega] embed failed", err));
    }
    return () => {
      cancelled = true;
      view.current?.finalize();
      view.current = null;
    };
  }, [spec]);

  return <div ref={host} className={className} style={{ width: "100%" }} />;
}
