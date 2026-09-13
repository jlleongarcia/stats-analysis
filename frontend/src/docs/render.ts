/**
 * Markdown + LaTeX rendering for the in-app documentation.
 *
 * KaTeX runs at render time rather than shipping pre-rendered HTML, so the
 * markdown under `docs/` stays the single source of truth and remains readable
 * on GitHub. Its CSS and fonts are bundled by Vite and served from our own
 * origin, so equations render with the app offline — the same constraint the
 * Pyodide runtime is held to.
 */
import { marked, type Tokens } from "marked";
import katex from "katex";
import "katex/dist/katex.min.css";

interface MathToken extends Tokens.Generic {
  type: "blockMath" | "inlineMath";
  text: string;
}

function render(text: string, displayMode: boolean): string {
  try {
    return katex.renderToString(text, {
      displayMode,
      // A malformed formula should show itself in red, not take the page down.
      throwOnError: false,
      strict: false,
      output: "htmlAndMathml",
    });
  } catch {
    return `<code>${text}</code>`;
  }
}

marked.use({
  extensions: [
    {
      name: "blockMath",
      level: "block",
      start: (src: string) => src.indexOf("$$"),
      tokenizer(src: string) {
        const match = /^\$\$([\s\S]+?)\$\$/.exec(src);
        if (!match) return undefined;
        return { type: "blockMath", raw: match[0], text: match[1].trim() } as MathToken;
      },
      renderer: (token: Tokens.Generic) =>
        `<div class="math-block">${render((token as MathToken).text, true)}</div>`,
    },
    {
      name: "inlineMath",
      level: "inline",
      start: (src: string) => src.indexOf("$"),
      tokenizer(src: string) {
        // Single line only: a stray dollar sign in prose must not swallow the
        // rest of the paragraph looking for its partner.
        const match = /^\$([^$\n]+?)\$/.exec(src);
        if (!match) return undefined;
        return { type: "inlineMath", raw: match[0], text: match[1].trim() } as MathToken;
      },
      renderer: (token: Tokens.Generic) => render((token as MathToken).text, false),
    },
  ],
});

// marked stopped emitting heading ids, so the table of contents would link to
// anchors that do not exist. Generate them with the same slug the TOC uses.
marked.use({
  renderer: {
    heading({ tokens, text, depth }: Tokens.Heading) {
      // Slug from the RAW markdown, not the rendered HTML: marked escapes an
      // apostrophe to &#39;, which would slug to "welch39s-t-test" and no
      // longer match the id the table of contents computed from the source.
      const id = slug(text);
      return `<h${depth} id="${id}">${this.parser.parseInline(tokens)}</h${depth}>\n`;
    },
  },
});

/** Render one documentation page to HTML. */
export function renderMarkdown(source: string): string {
  return marked.parse(source, { async: false }) as string;
}

/** Section headings, for building an in-page table of contents. */
export function headings(source: string): { id: string; text: string; level: number }[] {
  const out: { id: string; text: string; level: number }[] = [];
  for (const line of source.split("\n")) {
    const match = /^(#{2,3})\s+(.*)$/.exec(line);
    if (!match) continue;
    const text = match[2].replace(/[*`]/g, "").trim();
    out.push({ id: slug(match[2]), text, level: match[1].length });
  }
  return out;
}

/** Heading text to anchor id. Used by BOTH the renderer and the table of
 * contents - they must agree exactly or every contents link breaks. */
export function slug(text: string): string {
  return text
    .replace(/[*`_]/g, "")      // markdown emphasis and code marks
    .toLowerCase()
    .trim()
    .replace(/[^\w\s-]/g, "")  // punctuation, em dashes, symbols
    .replace(/\s+/g, "-");
}
