#!/usr/bin/env python3
"""Open one pull request per feature branch, each closing its own issue."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = "fufurobot/my-nonebot"
GH = Path(__file__).with_name("gh.py")
PY = sys.executable

PRS = [
    {
        "head": "feat/unicode-emoji-board",
        "title": "feat(board): render a Unicode/emoji board with a-h and 1-8 coordinates",
        "body": """\
Closes #1.

## What changed

`get_board_str()` no longer returns `chess.Board`'s ASCII dump. A new
`board_render.render_board()` draws a bordered box-drawing grid:

- solid Unicode piece glyphs, which emoji-capable fonts render in colour;
- a light/dark checkerboard pattern so empty squares remain visible;
- file letters `a`-`h` above **and** below the grid;
- a rank digit `1`-`8` on every row;
- every line padded to a single display width, so the grid survives a
  proportional chat font.

```
┌───┬───┬───┬───┬───┬───┬───┬───┐
│ a │ b │ c │ d │ e │ f │ g │ h │
├───┼───┼───┼───┼───┼───┼───┼───┤
│ ♜ │ ♞ │ ♝ │ ♛ │ ♚ │ ♝ │ ♞ │ ♜ │ 8
│ ♟ │ ♟ │ ♟ │ ♟ │ ♟ │ ♟ │ ♟ │ ♟ │ 7
│   │ · │   │ · │   │ · │   │ · │ 6
│ · │   │ · │   │ · │   │ · │   │ 5
│   │ · │   │ · │   │ · │   │ · │ 4
│ · │   │ · │   │ · │   │ · │   │ 3
│ ♙ │ ♙ │ ♙ │ ♙ │ ♙ │ ♙ │ ♙ │ ♙ │ 2
│ ♖ │ ♘ │ ♗ │ ♕ │ ♔ │ ♗ │ ♘ │ ♖ │ 1
├───┼───┼───┼───┼───┼───┼───┼───┤
│ a │ b │ c │ d │ e │ f │ g │ h │
└───┴───┴───┴───┴───┴───┴───┴───┘
```

## TDD

- `13db8e6` **red** -- `[WIP] test:` adds `tests/test_board_render.py` only; the
  board tests fail against the old renderer.
- `2ea6ebd` **green** -- adds the renderer so they pass.

## Verification

`uv run pytest tests -q` -- 14 passed at this commit.
`uv run ruff format --check src tests` and `uv run ruff check src/plugins/chess tests` are clean.
""",
    },
    {
        "head": "feat/multiplayer-resign-pgn",
        "title": "feat(game): multi-player teams, last-leaver resigns, QQ numbers in the endgame PGN",
        "body": """\
Closes #2.

## What changed

Player state is an ordered `list` per side instead of a `set`:

- **Teams.** A side may hold any number of players, and one player may join both
  sides to test alone. Any member of the side to move may play its move.
  Re-joining the same side is refused.
- **Last leaver resigns.** `remove_player` keeps the game running while a
  teammate remains, and only ends it when a side's *last* player leaves. A
  finished game is never re-scored by a later leave.
- **Attribution.** `get_pgn()` now writes the `White` and `Black` headers from
  the rosters, so the endgame record identifies every player by QQ number.

```pgn
[Event "群聊对弈"]
[White "11111, 22222"]
[Black "33333"]
[Result "0-1"]
```

`chess leave` / `chess resign` now report whether the side resigned or the game
continues, and `chess help` documents the team rules.

## TDD

- `8d1ef84` **red** -- `[WIP] test:` adds `tests/test_multiplayer.py` only, with
  five failing expectations (join order, teammate survival, finished-game
  protection, PGN headers).
- `44d9c30` **green** -- implements the ordered rosters and PGN headers.

## Verification

`uv run pytest tests -q` -- 30 passed at this commit.
""",
    },
    {
        "head": "feat/ci-pipeline",
        "title": "ci: add GitHub Actions and GitLab pipelines plus .env.example",
        "body": """\
Closes #3.

## What changed

- `.github/workflows/ci.yml` -- lint, tests on Python 3.10-3.13, config
  validation, secret scan. Read-only (`permissions: contents: read`).
- `.gitlab-ci.yml` -- the same gates on four stages (`lint`, `test`, `config`,
  `package`), plus wheel building on the default branch and tags.
- `.env.example` -- every variable a contributor needs, documented, with empty
  values so copying it can never leak a working token.
- The secret-scan job fails the build if a token-shaped string
  (`github_pat_*`, `ghp_*`, `glpat-*`) reaches a tracked file.

Supporting changes needed to make the gates pass:

- `python -m pytest` wiring in `pyproject.toml` (testpaths, pythonpath,
  asyncio mode) and `pytest`, `pytest-asyncio`, `pyyaml` in the dev group;
- `target-version = "py310"` for ruff, matching the `requires-python = ">=3.10"`
  the project already declares (it was `py39`), plus per-path ignores so the
  annotation/naming rules stop fighting pytest fixtures;
- the lint fixes those rules then surfaced in `src/plugins/chess`;
- a README section covering the board, team play and CI.

No account numbers or credentials appear in any file added here.

## TDD

- `20a52a2` **red** -- `[WIP] test:` adds `tests/test_ci_config.py` only; 14
  assertions fail because no CI config or `.env.example` exists yet.
- `c69f48d` **green** -- adds both pipelines and the template.
- `bc52bab` -- README documentation.

## Verification

`uv run pytest tests -q` -- 46 passed.
`uv run ruff check src/plugins/chess tests` and `uv run ruff format --check src tests` are clean.
""",
    },
]


def _existing_pr_for(head: str) -> int | None:
    """Return the number of an open PR whose head is ``head``, if any."""
    proc = subprocess.run(
        [PY, str(GH), "GET", f"/repos/{REPO}/pulls?state=all&per_page=100"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if proc.returncode != 0:
        return None
    for pr in json.loads(proc.stdout):
        if pr.get("head", {}).get("ref") == head and pr.get("state") == "open":
            return int(pr["number"])
    return None


def main() -> int:
    tmp = Path(__file__).with_name("_payload.json")
    for pr in PRS:
        existing = _existing_pr_for(pr["head"])
        payload = {
            "title": pr["title"],
            "body": pr["body"],
            "base": "main",
        }
        if existing is None:
            payload["head"] = pr["head"]
            payload["draft"] = False
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        if existing is None:
            args = ["POST", f"/repos/{REPO}/pulls", f"@{tmp}"]
            verb = "opened"
        else:
            args = ["PATCH", f"/repos/{REPO}/pulls/{existing}", f"@{tmp}"]
            verb = "updated"

        proc = subprocess.run(
            [PY, str(GH), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if proc.returncode != 0:
            print(f"FAILED for {pr['head']}", file=sys.stderr)
            print(proc.stdout, file=sys.stderr)
            print(proc.stderr, file=sys.stderr)
            return 1
        data = json.loads(proc.stdout)
        print(f"{verb} PR #{data['number']}: {data['title']}")
        print(f"  {data['html_url']}")
    tmp.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
