#!/usr/bin/env python3
"""Open the public GitHub issues that describe the three implemented features."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = "fufurobot/my-nonebot"
GH = Path(__file__).with_name("gh.py")
PY = sys.executable

BOARD_BODY = """\
## Problem

`ChessGame.get_board_str()` returns `str(chess.Board())`, which is the library's \
plain ASCII dump:

```
r n b q k b n r
p p p p p p p p
. . . . . . . .
```

There are no square coordinates, so a player must count rows and columns to name a \
square, and the `.` markers make empty squares hard to tell apart. In a proportional \
chat font the output also drifts out of alignment.

## Proposal

Render the position explicitly:

- Unicode chess glyphs (U+2654..U+265F) that emoji-capable fonts draw in colour;
- a light/dark checkerboard pattern so empty squares stay visible;
- file letters `a`-`h` above **and** below the grid;
- a rank digit `1`-`8` on every row;
- every line padded to one display width so the grid survives chat rendering.

## Acceptance criteria

- [x] Files `a`-`h` and ranks `1`-`8` are both readable from the output
- [x] Every produced line has the same display width
- [x] The board refreshes after a move and after castling
- [x] Covering tests exist

Tests: `tests/test_board_render.py`
"""

MULTIPLAYER_BODY = """\
## Problem

Player state is a `set` per side, and `remove_player` resigns a side as soon as \
*anyone* leaves it:

- Several players cannot meaningfully share one side.
- One person cannot hold both sides to test the plugin.
- A player leaving ends the whole game even when teammates remain.
- The endgame PGN has no idea who played: `White`/`Black` stay `?`.

## Proposal

1. **Teams.** Keep an ordered roster per side. A side may hold any number of \
players, and one player may join both sides. Any member of the side to move may play \
its move. Re-joining the same side is refused.
2. **Last leaver resigns.** Leaving only resigns a side once its *last* player \
leaves; the game continues while a teammate remains. A game that already finished \
keeps its recorded result.
3. **Attribution.** Write both rosters into the PGN `White` and `Black` headers, so \
the finished game identifies every player by their QQ number.

The bot should say which of the two happened, and `chess help` should document the \
team rules.

## Acceptance criteria

- [x] Multiple players can join one side and share its moves
- [x] Leaving with a teammate left does not end the game
- [x] The last player leaving resigns that side, with the correct score
- [x] A finished game is never re-scored by a later leave
- [x] The PGN carries the QQ numbers of every player on both sides
- [x] Covering tests exist

Tests: `tests/test_multiplayer.py`
"""

CI_BODY = """\
## Problem

The repository has no CI at all, so nothing verifies that the test suite passes, \
that the code is formatted, or that the deployment configuration stays intact. There \
is also no `.env.example`, so a contributor must reconstruct the required environment \
variables by reading the source, and a pasted token can slip into a commit unnoticed.

## Proposal

Add pipelines that run the same gates on both hosts:

- **GitHub Actions** (`.github/workflows/ci.yml`) -- lint, tests across Python \
3.10-3.13, config validation and a secret scan.
- **GitLab CI** (`.gitlab-ci.yml`) -- the same gates, plus wheel building on the \
default branch and on tags.
- **`.env.example`** -- every variable a contributor needs, documented, with empty \
values.
- A **secret-scan** job that fails the build if a credential-shaped string is ever \
committed to a tracked file.

The workflows are read-only (`permissions: contents: read`) because they only verify \
code.

## Acceptance criteria

- [x] Both pipelines trigger on push and pull request
- [x] Lint and tests both run, across the supported Python versions
- [x] `.env.example` documents the required keys and contains no real values
- [x] CI fails on a committed credential
- [x] The configuration itself is covered by tests, so a gate cannot silently disappear

Tests: `tests/test_ci_config.py`
"""

ISSUES = [
    {
        "title": "Chess board: render a Unicode board with a-h / 1-8 coordinates",
        "body": BOARD_BODY,
        "labels": ["enhancement"],
    },
    {
        "title": (
            "Multiplayer games: several players per side, last leaver resigns, "
            "QQ numbers in the PGN"
        ),
        "body": MULTIPLAYER_BODY,
        "labels": ["enhancement"],
    },
    {
        "title": (
            "CI: add GitHub Actions and GitLab pipelines, plus a .env.example "
            "for contributors"
        ),
        "body": CI_BODY,
        "labels": ["enhancement", "ci"],
    },
]


def main() -> int:
    created: list[tuple[int, str]] = []
    for issue in ISSUES:
        payload = json.dumps(issue, ensure_ascii=False)
        proc = subprocess.run(
            [PY, str(GH), "POST", f"/repos/{REPO}/issues", payload],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if proc.returncode != 0:
            print(f"FAILED to create {issue['title']!r}", file=sys.stderr)
            print(proc.stdout, file=sys.stderr)
            print(proc.stderr, file=sys.stderr)
            return 1
        data = json.loads(proc.stdout)
        created.append((data["number"], data["html_url"]))
        print(f"created #{data['number']}: {data['title']}")
        print(f"  {data['html_url']}")

    print("\nsummary:")
    for number, url in created:
        print(f"  #{number} {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
