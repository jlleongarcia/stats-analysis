import { useMemo, useState } from "react";
import { VegaLiteChart } from "../viz/VegaLiteChart";
import { specForExplore } from "../viz/buildSpec";
import { useApp } from "../state/store";

type Mark = "point" | "line" | "bar";

export function ExplorePage() {
  const { activeDataset } = useApp();
  const [x, setX] = useState("");
  const [y, setY] = useState("");
  const [color, setColor] = useState("");
  const [mark, setMark] = useState<Mark>("point");

  const cols = activeDataset?.columns ?? [];
  const spec = useMemo(() => {
    if (!activeDataset || !x) return null;
    return specForExplore(activeDataset.rows, x, y || null, color || null, mark);
  }, [activeDataset, x, y, color, mark]);

  if (!activeDataset) {
    return <div className="page"><h1>Explore</h1><p className="muted">Select a dataset first.</p></div>;
  }

  return (
    <div className="page">
      <h1>Explore</h1>
      <p className="muted">Quick plots, no statistics. Leave Y empty for a distribution of X.</p>

      <div className="explore__controls">
        <label className="field">
          <span>X</span>
          <select value={x} onChange={(e) => setX(e.target.value)}>
            <option value="">—</option>
            {cols.map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}
          </select>
        </label>
        <label className="field">
          <span>Y (optional)</span>
          <select value={y} onChange={(e) => setY(e.target.value)}>
            <option value="">—</option>
            {cols.filter((c) => c.type === "numeric").map((c) => (
              <option key={c.name} value={c.name}>{c.name}</option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Colour (optional)</span>
          <select value={color} onChange={(e) => setColor(e.target.value)}>
            <option value="">—</option>
            {cols.map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}
          </select>
        </label>
        <label className="field">
          <span>Mark</span>
          <select value={mark} onChange={(e) => setMark(e.target.value as Mark)}>
            <option value="point">points</option>
            <option value="line">line</option>
            <option value="bar">bars</option>
          </select>
        </label>
      </div>

      {spec ? <VegaLiteChart spec={spec} /> : <p className="muted">Pick an X column to draw a chart.</p>}
    </div>
  );
}
