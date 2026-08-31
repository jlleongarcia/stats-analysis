import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { nextQuestion, recommend } from "../guided/decisionTree";
import { useApp } from "../state/store";

export function GuidedPage() {
  const { registry, activeDataset } = useApp();
  const navigate = useNavigate();
  const [answers, setAnswers] = useState<Record<string, string>>({});

  const q = nextQuestion(answers);
  const rec = q ? null : recommend(answers);
  const nameOf = (id: string) => registry?.tests.find((t) => t.id === id)?.name ?? id;

  return (
    <div className="page guided">
      <h1>Guided choice</h1>
      {!activeDataset && <p className="muted">Tip: import a dataset so you can jump straight into the test.</p>}

      <ol className="guided__trail">
        {Object.entries(answers).map(([k, v]) => (
          <li key={k}>
            {k}: <b>{v}</b>{" "}
            <button className="link" onClick={() => setAnswers((a) => trimAfter(a, k))}>change</button>
          </li>
        ))}
      </ol>

      {q && (
        <div className="guided__q">
          <h2>{q.prompt}</h2>
          <div className="guided__opts">
            {q.options.map((o) => (
              <button
                key={o.value}
                className="btn"
                onClick={() => setAnswers((a) => ({ ...a, [q.id]: o.value }))}
              >
                {o.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {rec && (
        <div className="guided__rec">
          <h2>Recommended: {nameOf(rec.testId)}</h2>
          <p>{rec.rationale}</p>
          {rec.checkFirst && (
            <p className="muted">
              First run <b>{nameOf(rec.checkFirst.testId)}</b> — {rec.checkFirst.note}
            </p>
          )}
          {rec.alternatives.length > 0 && (
            <ul>
              {rec.alternatives.map((alt) => (
                <li key={alt.testId}>
                  <b>{nameOf(alt.testId)}</b> — use when {alt.when}
                </li>
              ))}
            </ul>
          )}
          <div className="guided__actions">
            <button className="btn btn--primary" onClick={() => navigate(`/analyze?test=${rec.testId}`)}>
              Set up this test
            </button>
            {rec.checkFirst && (
              <button className="btn" onClick={() => navigate(`/analyze?test=${rec.checkFirst!.testId}`)}>
                Run {nameOf(rec.checkFirst.testId)} first
              </button>
            )}
            <button className="btn" onClick={() => setAnswers({})}>Start over</button>
          </div>
        </div>
      )}
    </div>
  );
}

function trimAfter(answers: Record<string, string>, key: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const k of Object.keys(answers)) {
    if (k === key) break;
    out[k] = answers[k];
  }
  return out;
}
