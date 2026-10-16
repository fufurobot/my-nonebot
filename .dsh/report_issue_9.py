#!/usr/bin/env python3
"""Post a progress report on issue #9."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ghapi import request  # noqa: E402

REPO = "fufurobot/my-nonebot"
ISSUE = 9

BODY = """## Progress: implemented, in review

Branch `feat/chessbot-engine`, draft PR #10 targeting `dev`.

### Delivered

| Command | Behaviour |
| --- | --- |
| `chess ai [white\\|black\\|off] [level]` | Seats the engine (defaults to the side with no humans), or `off` to unseat it |
| `chess level [1-5]` | Shows or sets search depth, applied to a game already in progress |

- The engine answers **inside the same `chess move` turn**, so the board a
  group reads is never a move stale.
- `chess ai white` + `chess join black` is enough to start: the engine opens.
- Human and AI moves share `ChessGame._apply_move`, so the engine obeys the same
  checkmate/stalemate/draw rules, the same move history, and the same PGN.

### Three real bugs the tests caught

1. **The suite was completely broken.** The `chess` -> `chessbot` rename never
   reached `tests/conftest.py`, so all 50 tests errored with
   `FileNotFoundError`. CI also linted `src/plugins/chess`, a directory that no
   longer exists, and the README documented it. All three are fixed, and
   `tests/test_ci_config.py` now fails on any stale reference.
2. **The engine played White's moves for Black.** Sunfish works in the mover's
   frame -- only its uppercase pieces generate moves -- so a FEN-shaped board
   made it answer `d2d4` when it meant `d7d5`. The wrapper now mirrors the eight
   playing rows and swaps case (`to_sunfish_board`), then mirrors the reply back
   (`from_sunfish_move`).
3. **A fail-soft search can complete a depth with no stored best move**, even in
   a perfectly playable position. That silently forfeited the engine's turn; it
   now falls back to a legal move.

A promotion crash is also fixed: Sunfish emits `"NBRQ"` while UCI requires
`"nbrq"`, and parsing `Q` raised `InvalidMoveError` mid-game.

### Tests and CI

119 tests pass, up from 50. The 36 new tests were written first as a red
`[WIP]` commit (`3f95e87`), covering the search contract, mover-frame
conversion, promotion, terminal positions, the `chess ai` / `chess level`
dispatch, and the same-turn auto-reply.

`ruff check` and `ruff format --check` are clean. `sunfish.py` is excluded from
ruff in `pyproject.toml` because it is vendored verbatim and must stay diffable
against upstream; `engine.py` is the adapter around it.

GitHub Actions is green on the first two commits
(run [38860417861](https://github.com/fufurobot/my-nonebot/actions/runs/38860417861));
the run for the tooling commit is still in progress. This comment will be
followed by the merge once the final run is green.
"""


def main() -> int:
    status, body = request("POST", f"/repos/{REPO}/issues/{ISSUE}/comments", {"body": BODY})
    if status >= 400:  # noqa: PLR2004 - HTTP error boundary
        print(json.dumps(body, ensure_ascii=False, indent=2))
        return 1
    print("comment:", body["html_url"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
