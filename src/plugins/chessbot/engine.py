"""The Sunfish-backed AI opponent.

``sunfish.py`` is vendored verbatim from the upstream project, so this module is
the only place that knows how to talk to it. Two details of that file drive the
whole design:

1. It opens with a polyglot preamble (a ``#!/bin/sh`` line plus a shell/Python
   exec trick) so it can be run as a script. That makes it un-importable through
   the normal import machinery, so :func:`load_sunfish` reads the source, strips
   the preamble and executes it under a private module name.
2. It represents a position as a 120-character padded board, whereas the plugin
   plays on a ``python-chess`` board. :func:`to_sunfish_board` is the bridge.

Sunfish always searches from the perspective of the side to move and rotates
the board after every move, so the conversion never has to flip for black --
:func:`to_sunfish_board` emits white-at-the-bottom and the search negates
internally.

Strength is expressed as *search depth*. A level is a promise about how many
plies are searched, which is why :data:`LEVEL_DEPTH` is a strictly increasing
map: level 5 searching shallower than level 4 would be a silent lie to the
group that typed the command.
"""

from __future__ import annotations

import time
import types
from pathlib import Path
from typing import TYPE_CHECKING

import chess

if TYPE_CHECKING:
    from types import ModuleType

SUNFISH_PATH = Path(__file__).resolve().parent / "sunfish.py"

#: Plies searched per level. Strictly increasing; see the module docstring.
LEVEL_DEPTH: dict[int, int] = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5}

MIN_LEVEL = min(LEVEL_DEPTH)
MAX_LEVEL = max(LEVEL_DEPTH)

#: The level used when a group does not pick one.
DEFAULT_LEVEL = 3

#: Hard ceiling on a single search. The handler runs inside the bot's event
#: loop, so an unbounded search would freeze every other group's commands.
DEFAULT_TIME_LIMIT = 10.0

#: Sunfish's padded board: two blank ranks, the eight real ranks, two blanks.
_PAD_ROW = " " * 9 + "\n"

_sunfish_module: ModuleType | None = None


def load_sunfish() -> ModuleType:
    """Import the vendored Sunfish source, cached for the process lifetime.

    The file cannot be imported normally because of its shell preamble, so the
    preamble is cut out and the remainder executed into a fresh module.
    """
    global _sunfish_module  # noqa: PLW0603 - one process-wide, immutable handle
    if _sunfish_module is not None:
        return _sunfish_module

    source = SUNFISH_PATH.read_text(encoding="utf-8")
    # The preamble is everything up to and including the module docstring, which
    # is the first ``"""..."""`` pair. Sunfish's own ``main()`` relies on the
    # same split when it is loaded as a module.
    start = source.index('"""')
    end = source.index('"""', start + 3) + 3
    body = source[:start] + source[end:]

    module = types.ModuleType("chessbot_sunfish")
    module.__file__ = str(SUNFISH_PATH)
    exec(compile(body, str(SUNFISH_PATH), "exec"), module.__dict__)
    _sunfish_module = module
    return module


def normalise_level(level: int | None) -> int:
    """Clamp ``level`` into the supported range, defaulting when it is absent."""
    if level is None:
        return DEFAULT_LEVEL
    return max(MIN_LEVEL, min(MAX_LEVEL, int(level)))


def to_sunfish_board(board: chess.Board) -> str:
    """Render ``board`` in Sunfish's board format, from the **mover's** side.

    Sunfish only ever generates moves for its uppercase pieces, and it assumes
    that side is playing *up* the board (towards rank 8). Handing it a raw
    FEN-shaped board therefore only works when White is to move: with Black to
    move it would generate White's moves instead.

    The conversion is exactly what :meth:`~sunfish.Position.rotate` does between
    moves -- mirror the eight playing rows vertically and swap the case of every
    piece -- which makes the side to move uppercase and at the bottom. Only the
    playing rows are mirrored; the blank padding rows stay put, because
    ``rotate()`` reverses the whole string and would otherwise move the padding
    into the board.

    :meth:`Engine.choose_move` undoes this with :func:`from_sunfish_move`.
    """
    rows = []
    for rank in range(7, -1, -1):
        line = ""
        for file in range(8):
            piece = board.piece_at(chess.square(file, rank))
            line += piece.symbol() if piece is not None else "."
        rows.append(line)

    if board.turn == chess.BLACK:
        rows = [row.swapcase() for row in reversed(rows)]

    return "".join(
        [_PAD_ROW, _PAD_ROW, *(f" {row}\n" for row in rows), _PAD_ROW, _PAD_ROW]
    )


def _flip_square(square: chess.Square) -> chess.Square:
    """Mirror a square across the middle of the board (a1 <-> a8)."""
    return chess.square(chess.square_file(square), 7 - chess.square_rank(square))


def from_sunfish_move(move: chess.Move, turn: chess.Color) -> chess.Move:
    """Map a move Sunfish produced back into absolute board coordinates.

    The inverse of the mirroring in :func:`to_sunfish_board`: when Black is to
    move the move comes back flipped vertically, so both squares are mirrored
    across the middle of the board. Without this the engine answers with a move
    that reads correctly only from its own point of view -- ``d2d4`` when it
    meant ``d7d5`` -- and the caller sees an illegal move.
    """
    if turn != chess.BLACK:
        return move
    return chess.Move(
        _flip_square(move.from_square),
        _flip_square(move.to_square),
        move.promotion,
    )


class Engine:
    """A thin, synchronous wrapper around one Sunfish search.

    An instance is cheap and stateless between calls apart from
    :attr:`last_seconds`, so the plugin creates one per move rather than keeping
    module-level engine state that could leak between groups.
    """

    def __init__(
        self, level: int | None = None, time_limit: float = DEFAULT_TIME_LIMIT
    ) -> None:
        self.level = normalise_level(level)
        self.time_limit = time_limit
        self.last_seconds = 0.0
        self.last_score = 0

    @property
    def depth(self) -> int:
        """Plies this engine searches at its current level."""
        return LEVEL_DEPTH[self.level]

    def choose_move(self, board: chess.Board) -> chess.Move | None:
        """Return the engine's move for ``board``, or ``None`` if the game is over.

        ``None`` is the honest answer for a finished position: there is no move
        to make, and callers must be able to distinguish "no move" from "the
        engine wants to play something illegal".
        """
        if board.is_game_over(claim_draw=True) or not any(board.legal_moves):
            self.last_seconds = 0.0
            return None

        sunfish = load_sunfish()
        history = [
            sunfish.Position(
                to_sunfish_board(board), 0, (False, False), (False, False), 0, 0
            )
        ]

        searcher = sunfish.Searcher()
        searcher.soft = time.time() + self.time_limit

        started = time.time()
        best = None
        try:
            for depth, _gamma, score, move in searcher.search(history):
                if move is not None:
                    best, self.last_score = move, score
                if depth >= self.depth:
                    break
        finally:
            self.last_seconds = time.time() - started

        if best is None:
            # A fail-soft search can complete a depth without ever storing a
            # best move, even in a perfectly playable position -- depth 1 hits
            # this often. Forfeiting the turn would be a silent, game-losing
            # bug, so fall back to the search's own move ordering: any legal
            # move keeps the game honest.
            return self._first_legal_move(board)

        # Sunfish yields the promotion piece as uppercase ("NBRQ"); UCI wants
        # the lowercase letter, so it has to be folded before parsing.
        played = from_sunfish_move(
            chess.Move.from_uci(
                sunfish.render(best.i) + sunfish.render(best.j) + best.prom.lower()
            ),
            board.turn,
        )
        if played not in board.legal_moves:
            # Sunfish and python-chess disagree about the position (a corrupt
            # board string, or a rules edge case). Refusing a specific move is
            # fine; refusing to move at all is not, so fall back.
            return self._first_legal_move(board)
        return played

    @staticmethod
    def _first_legal_move(board: chess.Board) -> chess.Move | None:
        """A guaranteed-legal move, used when the search offers nothing usable."""
        return next(iter(board.legal_moves), None)

    def choose_uci(self, board: chess.Board) -> str | None:
        """The engine's move as UCI, or ``None`` when the game is over."""
        move = self.choose_move(board)
        return move.uci() if move is not None else None
