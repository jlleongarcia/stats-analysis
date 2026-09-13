/**
 * In-app documentation.
 *
 * The markdown under `docs/` is the single source of truth — imported raw at
 * build time rather than duplicated here, so the page and the repo cannot
 * disagree, and bundling (rather than fetching) keeps the docs readable offline
 * in an installed PWA.
 *
 * The test reference is not markdown at all: it is generated from the registry,
 * so adding a test documents it automatically.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { headings, renderMarkdown } from "../docs/render";
import { TestReference } from "../docs/TestReference";
import gettingStarted from "../../../docs/getting-started.md?raw";
import methods from "../../../docs/statistical-methods.md?raw";
import spcGuide from "../../../docs/spc-user-guide.md?raw";
import spcMethodology from "../../../docs/spc-methodology.md?raw";

interface Page {
  id: string;
  label: string;
  group: string;
  source?: string;
}

const PAGES: Page[] = [
  { id: "getting-started", label: "Getting started", group: "Using the app", source: gettingStarted },
  { id: "tests", label: "Test reference", group: "Using the app" },
  { id: "methods", label: "Statistical methods", group: "Reference", source: methods },
  { id: "spc-guide", label: "SPC user guide", group: "Process control", source: spcGuide },
  { id: "spc-methodology", label: "SPC methodology", group: "Process control", source: spcMethodology },
];

const GROUPS = [...new Set(PAGES.map((p) => p.group))];

export function DocsPage() {
  const [params, setParams] = useSearchParams();
  const requested = params.get("page") ?? "";
  const page = PAGES.find((p) => p.id === requested) ?? PAGES[0];
  const body = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState<string>("");

  const html = useMemo(
    () => (page.source ? renderMarkdown(page.source) : ""),
    [page.source],
  );
  const toc = useMemo(() => (page.source ? headings(page.source) : []), [page.source]);

  // Scroll to the top on navigation: without this, switching from halfway down
  // a long page drops you into the middle of the next one.
  useEffect(() => {
    body.current?.scrollTo?.({ top: 0 });
    window.scrollTo({ top: 0 });
    setActive("");
  }, [page.id]);

  // Highlight the section currently in view.
  useEffect(() => {
    if (!body.current || toc.length === 0) return;
    const nodes = Array.from(body.current.querySelectorAll<HTMLElement>("h2, h3"));
    if (nodes.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
        if (visible?.target.id) setActive(visible.target.id);
      },
      { rootMargin: "0px 0px -70% 0px", threshold: 0 },
    );
    nodes.forEach((n) => observer.observe(n));
    return () => observer.disconnect();
  }, [html, toc.length]);

  return (
    <div className="page docs">
      <aside className="docs__nav" aria-label="Documentation">
        {GROUPS.map((group) => (
          <div key={group} className="docs__group">
            <h3>{group}</h3>
            <ul>
              {PAGES.filter((p) => p.group === group).map((p) => (
                <li key={p.id}>
                  <button
                    className={`docs__link${p.id === page.id ? " is-active" : ""}`}
                    aria-current={p.id === page.id ? "page" : undefined}
                    onClick={() => setParams({ page: p.id })}
                  >
                    {p.label}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}

        {toc.length > 0 && (
          <div className="docs__group docs__toc">
            <h3>On this page</h3>
            <ul>
              {toc.map((h) => (
                <li key={h.id} className={h.level === 3 ? "is-sub" : undefined}>
                  <a
                    href={`#${h.id}`}
                    className={h.id === active ? "is-active" : undefined}
                    onClick={(e) => {
                      e.preventDefault();
                      document.getElementById(h.id)?.scrollIntoView({ behavior: "smooth" });
                    }}
                  >
                    {h.text}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        )}
      </aside>

      <div className="docs__body" ref={body}>
        {page.id === "tests" ? (
          <TestReference />
        ) : (
          <article className="markdown" dangerouslySetInnerHTML={{ __html: html }} />
        )}
      </div>
    </div>
  );
}
