#!/usr/bin/env python3
"""Open the issue and pull request for the Jinja templates / compact mode work."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = "fufurobot/my-nonebot"
GH = Path(__file__).with_name("gh.py")
PY = sys.executable

BRANCH = "feat/jinja-templates-compact-mode"

ISSUE = {
    "title": "Boards: load Jinja templates and add a width-bounded compact mode",
    "labels": ["enhancement"],
    "body": """\
## Problem

Board output is built by concatenating strings in `board_render.py`. There is
exactly one format, and changing it means editing Python.

There is also no format that survives a fixed-width CJK chat font. The existing
bordered grid is ~35 columns of mixed-width characters, so in a client that
renders CJK glyphs two columns wide it wraps and the grid collapses.

## Proposal

1. **Jinja templates.** Move formats into `src/plugins/chess/templates/*.j2`
   and render them through `board_templates.py`. `AVAILABLE_MODES` is discovered
   from the directory, so a new format is a new file. `build_context()` is the
   shared context contract.
2. **`compact` mode, default.** A strictly bounded format for fixed-width CJK
   fonts, where every character occupies **two columns**. Every line is at most
   **13 characters wide** and the format uses *only* two-column characters.
3. **`normal` mode.** The existing bordered grid, kept unchanged, including its
   ASCII `a-h` / `1-8` labels and light/dark square markers.
4. **`chess mode [name]`** switches the template per group; `chess help` lists
   the available modes.

### The compact character set

| Purpose | Characters |
| --- | --- |
| Pieces | `♙♘♗♖♕♔` / `♟♞♝♜♛♚` |
| File letters | `ａｂｃｄｅｆｇｈ` |
| Rank digits | `１２３４５６７８` |
| Blank | `　` (U+3000) |
| Empty square | `■` |

No ASCII and no box-drawing characters, because those are one column wide and
would break the two-column grid.

## Acceptance criteria

- [x] Compact lines never exceed 13 characters, in the opening, a midgame and a
      position with promotions
- [x] Compact output contains only the allowed characters
- [x] Compact shows all eight file letters and all eight rank digits
- [x] Normal mode keeps the bordered grid with ASCII coordinates
- [x] Templates load from disk and leave no unrendered Jinja syntax
- [x] `chess mode` switches per group, is advertised in help, and falls back
      safely if a stored mode no longer exists

Tests: `tests/test_board_templates.py`, `tests/test_board_modes.py`
""",
}

PR = {
    "title": "feat(board): load boards from Jinja templates and add a compact mode",
    "head": BRANCH,
    "base": "main",
    "body": """\
Closes the board-templates issue.

## What changed

**Templates.** Formats live in `src/plugins/chess/templates/` and render through
`board_templates.py`. `AVAILABLE_MODES` is discovered from that directory, so
adding a format is adding a `.j2` file. `build_context()` is the single context
contract: `files`, `ranks`, `ascii_files`, `ascii_ranks`, `space`, `blank` and
`rows` (each with `rank`, `ascii_rank` and eight `cells` carrying `glyph` and
`ascii_glyph`).

**`compact` (new default).** Bounded for fixed-width CJK fonts, where every
character is two columns. At most **13 characters per line**:

```
♜♞♝♛♚♝♞♜　８
♟♟♟♟♟♟♟♟　７
■■■■■■■■　６
■■■■■■■■　５
■■■■■■■■　４
■■■■■■■■　３
♙♙♙♙♙♙♙♙　２
♖♘♗♕♔♗♘♖　１
ａｂｃｄｅｆｇｈ
```

Only two-column characters are used: the pieces, fullwidth `ａ`-`ｈ` and
`１`-`８`, U+3000, and `■`. No ASCII, no box-drawing.

**`normal`.** The bordered grid, unchanged, with its ASCII `a-h` / `1-8` labels
and light/dark markers — it is not width-constrained so it keeps the richer
form.

**`chess mode [name]`** switches the template per group; every board reply
(`join`, `board`, `move`) honours it, and an unknown or stale mode falls back to
the default instead of raising.

## TDD

- `44b67ba` **red** — `[WIP] test:` adds `tests/test_board_templates.py` only.
  `get_board_str()` had no `mode` parameter and `board_templates` did not exist,
  so the width and character-whitelist assertions could not pass.
- `af558c2` **green** — adds the templates module, both templates, and the mode
  parameter.
- `f1a73c2` — `tests/test_board_modes.py` pins per-group selection.

`tests/test_board_render.py` now requests `mode="normal"` explicitly, because
the default moved to `compact`; its assertions are unchanged.

## Verification

`uv run pytest tests -q` — 77 passed.
`uv run ruff check src/plugins/chess tests` and
`uv run ruff format --check src tests` are clean.

`ruff`'s `RUF001/002` ambiguous-character warnings are suppressed for the
fullwidth characters in `allowed-confusables`: they are deliberate here, not
typos.
""",
}


def call(method: str, path: str, payload: dict | None = None) -> dict:
    tmp = Path(__file__).with_name("_payload.json")
    args = [PY, str(GH), method, path]
    if payload is not None:
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        args.append(f"@{tmp}")
    proc = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        print(proc.stdout, file=sys.stderr)
        print(proc.stderr, file=sys.stderr)
        raise SystemExit(f"{method} {path} failed")
    tmp.unlink(missing_ok=True)
    return json.loads(proc.stdout)


def main() -> int:
    issue = call("POST", f"/repos/{REPO}/issues", ISSUE)
    print(f"opened issue #{issue['number']}: {issue['html_url']}")

    body = PR["body"].replace(
        "Closes the board-templates issue.", f"Closes #{issue['number']}."
    )
    pull = call(
        "POST",
        f"/repos/{REPO}/pulls",
        {
            "title": PR["title"],
            "body": body,
            "head": PR["head"],
            "base": PR["base"],
            "draft": False,
        },
    )
    print(f"opened PR #{pull['number']}: {pull['html_url']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
