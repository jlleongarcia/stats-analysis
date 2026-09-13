/**
 * Every test in the app, generated from the registry.
 *
 * Deliberately not hand-written: the registry already declares each test's
 * name, description, required variables, parameters and assumptions, and it is
 * what the Analyze page builds its own UI from. Generating the reference from
 * the same source means a new test documents itself, and the documentation
 * cannot drift out of step with what the app actually does.
 */
import { useMemo, useState } from "react";
import { useApp } from "../state/store";
import type { TestSpec } from "../types";

const FAMILY_BLURB: Record<string, string> = {
  descriptive: "Summarise what is in the data before testing anything about it.",
  normality: "Check whether a variable is plausibly normal — the assumption behind most parametric tests.",
  "t-test": "Compare one or two means.",
  nonparametric: "Rank-based alternatives that make no normality assumption.",
  anova: "Compare three or more means, or several factors at once.",
  correlation: "Measure how two variables move together.",
  regression: "Model an outcome from one or more predictors.",
  categorical: "Test counts and contingency tables.",
  variance: "Check whether groups share a common spread.",
  multivariate: "Reduce or reshape many variables at once.",
  clustering: "Find groups in the data without knowing them in advance.",
  classification: "Predict a known group membership from measured variables.",
  reliability: "Assess whether a set of items measures one underlying construct.",
  spc: "Monitor a process over time and judge whether it can hold its specification.",
};

const DTYPE_LABEL: Record<string, string> = {
  numeric: "numeric",
  categorical: "categorical",
  any: "any type",
};

function TestCard({ spec }: { spec: TestSpec }) {
  return (
    <article className="testref__card" id={`test-${spec.id}`}>
      <header>
        <h4>{spec.name}</h4>
        <code className="testref__id">{spec.id}</code>
      </header>
      <p>{spec.description}</p>

      <dl className="testref__meta">
        <dt>Variables</dt>
        <dd>
          {spec.roles.length === 0 ? (
            <span className="muted">none</span>
          ) : (
            <ul>
              {spec.roles.map((r) => (
                <li key={r.key}>
                  <strong>{r.label}</strong>{" "}
                  <span className="muted">
                    ({DTYPE_LABEL[r.dtype] ?? r.dtype}
                    {r.multiple ? ", one or more" : ""}
                    {r.required ? "" : ", optional"})
                  </span>
                  {r.help && <div className="muted testref__help">{r.help}</div>}
                </li>
              ))}
            </ul>
          )}
        </dd>

        {spec.params.length > 0 && (
          <>
            <dt>Settings</dt>
            <dd>
              <ul>
                {spec.params.map((p) => (
                  <li key={p.key}>
                    {p.label}
                    {p.default !== null && p.default !== undefined && (
                      <span className="muted"> — default {String(p.default)}</span>
                    )}
                  </li>
                ))}
              </ul>
            </dd>
          </>
        )}

        {spec.assumptions.length > 0 && (
          <>
            <dt>Assumes</dt>
            <dd>
              <ul>
                {spec.assumptions.map((a) => (
                  <li key={a}>{a}</li>
                ))}
              </ul>
            </dd>
          </>
        )}

        {spec.min_n > 3 && (
          <>
            <dt>Minimum n</dt>
            <dd>{spec.min_n}</dd>
          </>
        )}
      </dl>
    </article>
  );
}

export function TestReference() {
  const registry = useApp((s) => s.registry);
  const engine = useApp((s) => s.engine);
  const [query, setQuery] = useState("");

  const families = useMemo(() => {
    if (!registry) return [];
    const needle = query.trim().toLowerCase();
    return registry.families
      .map((family) => ({
        family,
        tests: registry.tests.filter(
          (t) =>
            t.family === family &&
            (!needle ||
              t.name.toLowerCase().includes(needle) ||
              t.id.includes(needle) ||
              t.description.toLowerCase().includes(needle)),
        ),
      }))
      .filter((g) => g.tests.length > 0);
  }, [registry, query]);

  if (!registry) {
    return (
      <div className="markdown">
        <h1>Test reference</h1>
        <p className="muted">
          {engine === "error"
            ? "The statistics engine could not start, so the test list is unavailable."
            : "Waiting for the statistics engine to report which tests it provides…"}
        </p>
      </div>
    );
  }

  const total = registry.tests.length;
  const shown = families.reduce((n, g) => n + g.tests.length, 0);

  return (
    <div className="markdown testref">
      <h1>Test reference</h1>
      <p>
        All {total} tests this build provides, grouped by family. This page is generated from the
        same registry the Analyze page builds its forms from, so it always describes what the app
        actually does.
      </p>

      <input
        type="search"
        className="testref__search"
        placeholder="Filter by name, id or description…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        aria-label="Filter tests"
      />
      {query && (
        <p className="muted">
          {shown} of {total} tests match.
        </p>
      )}

      {families.map(({ family, tests }) => (
        <section key={family}>
          <h2 id={family}>{family}</h2>
          {FAMILY_BLURB[family] && <p className="muted">{FAMILY_BLURB[family]}</p>}
          <div className="testref__grid">
            {tests.map((spec) => (
              <TestCard key={spec.id} spec={spec} />
            ))}
          </div>
        </section>
      ))}

      {shown === 0 && <p className="muted">Nothing matches “{query}”.</p>}
    </div>
  );
}
