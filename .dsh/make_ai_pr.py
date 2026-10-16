#!/usr/bin/env python3
"""Open the draft pull request for the AI-opponent sprint (issue #9)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ghapi import request  # noqa: E402

REPO = "fufurobot/my-nonebot"

BODY = """Closes #9

## What

Groups can now play a game against the bot itself, driven by the vendored
Sunfish engine.

| Command | Behaviour |
| --- | --- |
| `chess ai [white\\|black\\|off] [level]` | Seats the engine (defaults to the side with no humans), or `off` to unseat it |
| `chess level [1-5]` | Shows or sets the search depth, applied to a game in progress |

The engine replies **inside the same `chess move` turn**, so the board a group
reads is never one move stale. `chess ai white` followed by `chess join black`
lets the engine open with a single command.

## Bugs this found

Three defects were caught by tests rather than by a group:

1. **The suite was entirely broken.** The `chess` -> `chessbot` rename never
   reached `tests/conftest.py`, CI, or the README, so every test errored with
   `FileNotFoundError` and CI linted a directory that no longer existed.
2. **The engine played White's moves for Black.** Sunfish works in the mover's
   frame (only its uppercase pieces can move); feeding it a FEN-shaped board
   made it answer `d2d4` when it meant `d7d5`. Fixed by mirroring the eight
   playing rows and swapping case, then un-mirroring the reply.
3. **A fail-soft search can finish a depth with no stored best move**, even in
   a live position. That silently forfeited the engine's turn; it now falls
   back to a legal move.

A promotion crash (`InvalidMoveError` on uppercase `Q`) is also fixed and
pinned by a test.

## Tests

119 passing, up from 50. The 36 new tests came first, as a red `[WIP]` commit:

- `tests/test_engine.py` - the search contract, level ordering, mover-frame
  conversion, promotion, checkmate/stalemate handling, and a depth-3 vs
  depth-1 self-play game asserting the deeper search never loses.
- `tests/test_ai_commands.py` - drives `handle_chess` through a stubbed
  `Matcher`: seating, `off`, levels, and the same-turn auto-reply.
- `tests/test_ci_config.py` - fails on any stale `src/plugins/chess` reference
  so the rename cannot rot again.

`ruff check` and `ruff format --check` are clean. `sunfish.py` is excluded from
ruff because it is vendored verbatim and must stay diffable against upstream.
"""


def main() -> int:
    payload = {
        "title": "feat(chessbot): add a Sunfish AI opponent (chess ai / chess level)",
        "head": "feat/chessbot-engine",
        "base": "dev",
        "draft": True,
        "body": BODY,
    }
    status, body = request("POST", f"/repos/{REPO}/pulls", payload)
    if status >= 400:  # noqa: PLR2004 - HTTP error boundary
        print(json.dumps(body, ensure_ascii=False, indent=2))
        return 1
    print(body["number"], body["html_url"], "draft:", body["draft"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
