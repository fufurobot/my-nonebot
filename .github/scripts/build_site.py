#!/usr/bin/env python3
"""Render the repository documentation into a static site for GitHub Pages.

There is no web application to build -- the bot lives in QQ -- so the Pages
site is the documentation: ``README.md`` as the landing page. That is the only
thing in this repository a visitor can usefully read outside of GitHub itself.

The renderer is deliberately small and **standard-library only**. The Markdown
subset this project's README actually uses is headings, paragraphs, fenced
code, tables, lists and inline code/links/emphasis; pulling a full Markdown
package into CI to handle that would be a dependency for no benefit, and it
would fail the build whenever PyPI is unreachable.
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = REPO_ROOT / "site"

# Repository-relative links point at files a Pages visitor cannot browse, so
# they are rewritten to their GitHub blob URLs.
GITHUB_BLOB = "https://github.com/fufurobot/my-nonebot/blob/main"

STYLESHEET = """
:root { color-scheme: light dark; }
body {
  margin: 0 auto; max-width: 52rem; padding: 2rem 1.25rem 4rem;
  font: 16px/1.65 -apple-system, "Segoe UI", "Noto Sans CJK SC", sans-serif;
}
pre, code { font-family: ui-monospace, "Cascadia Code", Consolas, monospace; }
pre {
  padding: .8rem 1rem; overflow-x: auto; border-radius: 6px;
  background: rgba(127,127,127,.12);
}
code { background: rgba(127,127,127,.12); padding: .1em .3em; border-radius: 3px; }
pre code { background: none; padding: 0; }
table { border-collapse: collapse; width: 100%; margin: 1rem 0; }
th, td {
  border: 1px solid rgba(127,127,127,.35);
  padding: .4rem .6rem; text-align: left;
}
th { background: rgba(127,127,127,.12); }
footer { margin-top: 3rem; opacity: .7; font-size: .9rem; }
"""

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{stylesheet}</style>
</head>
<body>
{body}
<footer>Rendered from <a href="{blob}/README.md">README.md</a> by
<code>.github/scripts/build_site.py</code>.</footer>
</body>
</html>
"""

_FENCE = re.compile(r"^```(\w*)\s*$")
_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_ITALIC = re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)")
_CODE = re.compile(r"`([^`]+)`")


def inline(text: str) -> str:
    """Render the inline spans used by the README, escaping HTML first."""
    out = html.escape(text, quote=False)
    # Code spans are extracted before anything else so their contents are never
    # treated as emphasis or links.
    spans: list[str] = []

    def stash(match: re.Match[str]) -> str:
        spans.append(f"<code>{match.group(1)}</code>")
        return f"\x00{len(spans) - 1}\x00"

    out = _CODE.sub(stash, out)
    out = _LINK.sub(lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', out)
    out = _BOLD.sub(r"<strong>\1</strong>", out)
    out = _ITALIC.sub(r"<em>\1</em>", out)
    return re.sub(r"\x00(\d+)\x00", lambda m: spans[int(m.group(1))], out)


def rewrite_local_links(text: str) -> str:
    """Point repository-relative links at GitHub, where they resolve."""
    for target in (".env.example", "LICENSE"):
        text = text.replace(f"]({target})", f"]({GITHUB_BLOB}/{target})")
        text = text.replace(f"](./{target})", f"]({GITHUB_BLOB}/{target})")
    return text


def render_table(rows: list[str]) -> str:
    """Turn a Markdown table into HTML, dropping the alignment separator row."""
    header = [c.strip() for c in rows[0].strip().strip("|").split("|")]
    body_rows = []
    for row in rows[1:]:
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        # The `|---|---|` separator is not data.
        if all(set(cell) <= set("-: ") and cell for cell in cells):
            continue
        body_rows.append(cells)

    out = ["<table>", "<thead><tr>"]
    out += [f"<th>{inline(c)}</th>" for c in header]
    out += ["</tr></thead>", "<tbody>"]
    for cells in body_rows:
        out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in cells) + "</tr>")
    out += ["</tbody>", "</table>"]
    return "\n".join(out)


# A block parser is a state machine over lines; splitting it per construct would
# scatter the shared cursor state that makes it correct.
def to_html(markdown_text: str) -> str:  # noqa: C901, PLR0915
    """Convert the Markdown subset the README uses into HTML."""
    lines = rewrite_local_links(markdown_text).splitlines()
    out: list[str] = []
    paragraph: list[str] = []
    table: list[str] = []
    list_items: list[str] = []
    quote: list[str] = []
    fence: list[str] | None = None
    fence_lang = ""

    def flush_paragraph() -> None:
        if paragraph:
            out.append(f"<p>{inline(' '.join(paragraph))}</p>")
            paragraph.clear()

    def flush_table() -> None:
        if table:
            out.append(render_table(table))
            table.clear()

    def flush_list() -> None:
        if list_items:
            out.append(
                "<ul>" + "".join(f"<li>{inline(i)}</li>" for i in list_items) + "</ul>"
            )
            list_items.clear()

    def flush_quote() -> None:
        if quote:
            out.append(f"<blockquote>{inline(' '.join(quote))}</blockquote>")
            quote.clear()

    def flush_all() -> None:
        flush_paragraph()
        flush_table()
        flush_list()
        flush_quote()

    for raw in lines:
        fence_match = _FENCE.match(raw)
        if fence is not None:
            if fence_match:
                body = html.escape("\n".join(fence))
                klass = f' class="language-{fence_lang}"' if fence_lang else ""
                out.append(f"<pre><code{klass}>{body}</code></pre>")
                fence = None
                fence_lang = ""
            else:
                fence.append(raw)
            continue
        if fence_match:
            flush_all()
            fence, fence_lang = [], fence_match.group(1)
            continue

        stripped = raw.strip()
        if not stripped:
            flush_all()
            continue

        heading = _HEADING.match(stripped)
        if heading:
            flush_all()
            level = len(heading.group(1))
            out.append(f"<h{level}>{inline(heading.group(2))}</h{level}>")
            continue

        if stripped.startswith("|") and stripped.endswith("|"):
            flush_paragraph()
            flush_list()
            flush_quote()
            table.append(stripped)
            continue
        flush_table()

        if stripped.startswith(("- ", "* ")):
            flush_paragraph()
            list_items.append(stripped[2:])
            continue
        if re.match(r"^\d+\.\s", stripped):
            flush_paragraph()
            list_items.append(re.sub(r"^\d+\.\s", "", stripped))
            continue
        flush_list()

        if stripped.startswith(">"):
            flush_paragraph()
            quote.append(stripped.lstrip("> ").strip())
            continue
        flush_quote()

        paragraph.append(stripped)

    if fence is not None:  # an unterminated fence still gets rendered
        out.append(f"<pre><code>{html.escape(chr(10).join(fence))}</code></pre>")
    flush_all()
    return "\n".join(out)


def main() -> int:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    body = to_html(readme)
    page = PAGE.format(
        title="dsh-bot — NoneBot2 chess bot",
        stylesheet=STYLESHEET,
        body=body,
        blob=GITHUB_BLOB,
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "index.html").write_text(page, encoding="utf-8")
    # Pages serves 404.html for unknown paths; the site is a single page, so
    # send visitors back to it rather than to GitHub's default.
    (OUT_DIR / "404.html").write_text(
        page.replace("<title>", "<title>Not found — "), encoding="utf-8"
    )
    # `nojekyll` stops Pages from running Jekyll, which ignores files and
    # directories whose names begin with an underscore.
    (OUT_DIR / ".nojekyll").write_text("", encoding="utf-8")
    print(f"rendered {OUT_DIR / 'index.html'}")  # noqa: T201 - CI log line
    return 0


if __name__ == "__main__":
    sys.exit(main())
