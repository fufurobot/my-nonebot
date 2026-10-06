"""Jinja-backed board rendering.

Board formats live in ``templates/`` as Jinja files rather than as string
concatenation in Python, so a format can be changed without touching logic and a
new format is just a new file. ``AVAILABLE_MODES`` is discovered from the
directory, and :func:`render` picks the template by name.

Context contract
----------------
Every template receives the same context; see :func:`build_context`. Rows are
emitted top rank first, so ``rows[0]`` is rank 8, and each row carries a
``rank`` label plus eight ``cells``.

Character widths
----------------
The compact format exists because CJK fonts render the characters in
:data:`~chess_plugin.board_render.COMPACT_PIECES` and the supplied fullwidth
characters as two display units wide. Every character a compact template emits
must therefore be one of those two-unit characters; ASCII would break the grid.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

import chess

if TYPE_CHECKING:
    from collections.abc import Iterable

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

#: Fullwidth file letters, in board order. Each is two display units wide.
FULLWIDTH_FILES: tuple[str, ...] = tuple("ａｂｃｄｅｆｇｈ")

#: Fullwidth rank digits, index 0 == rank 1.
FULLWIDTH_RANKS: tuple[str, ...] = tuple("１２３４５６７８")

#: ASCII file letters for the normal format, which is not width-constrained.
ASCII_FILES: tuple[str, ...] = tuple("abcdefgh")

#: ASCII rank digits, index 0 == rank 1.
ASCII_RANKS: tuple[str, ...] = tuple("12345678")

#: The ideographic space, the only permitted blank in the compact format.
IDEOGRAPHIC_SPACE = "\u3000"

#: The black square, used as the compact blank/dark-square marker.
BLACK_SQUARE = "■"


def _discover_modes() -> tuple[str, ...]:
    """Return the available modes, sorted with ``compact`` first."""
    if not TEMPLATE_DIR.is_dir():
        return ()
    names = {p.stem for p in TEMPLATE_DIR.glob("*.j2")}
    ordered = [m for m in ("compact", "normal") if m in names]
    return tuple(ordered + sorted(names - set(ordered)))


AVAILABLE_MODES: tuple[str, ...] = _discover_modes()

DEFAULT_MODE = (
    "compact"
    if "compact" in AVAILABLE_MODES
    else (AVAILABLE_MODES[0] if AVAILABLE_MODES else "normal")
)

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    undefined=StrictUndefined,
    # Keep the output byte-exact: no stray blank lines around block tags.
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=False,
    autoescape=False,
)


def template_path(mode: str) -> Path:
    """Return the on-disk path of a mode's template."""
    return TEMPLATE_DIR / f"{mode}.j2"


def build_context(board: chess.Board) -> dict[str, Any]:
    """Build the template context for ``board``.

    Args:
        board: The position to describe. It is not modified.

    Returns:
        A dict with ``files`` (the fullwidth file letters), ``rows`` (top rank
        first, each with ``rank`` and ``cells``), and the raw ``board``.
    """
    rows: list[dict[str, Any]] = [
        {
            "rank": FULLWIDTH_RANKS[rank_index],
            "ascii_rank": ASCII_RANKS[rank_index],
            "rank_index": rank_index,
            "cells": [
                _cell(board, chess.square(file_index, rank_index))
                for file_index in range(8)
            ],
        }
        for rank_index in range(7, -1, -1)
    ]
    return {
        "board": board,
        "files": list(FULLWIDTH_FILES),
        "ranks": list(FULLWIDTH_RANKS),
        "ascii_files": list(ASCII_FILES),
        "ascii_ranks": list(ASCII_RANKS),
        "rows": rows,
        "space": IDEOGRAPHIC_SPACE,
        "blank": BLACK_SQUARE,
        "empty": IDEOGRAPHIC_SPACE,
    }


def _cell(board: chess.Board, square: int) -> dict[str, Any]:
    """Describe a single square for the templates."""
    piece = board.piece_at(square)
    is_light = (chess.square_file(square) + chess.square_rank(square)) % 2 == 1
    return {
        "square": square,
        "name": chess.square_name(square),
        "piece": piece,
        "glyph": _glyph(piece),
        "ascii_glyph": _ascii_glyph(piece, is_light=is_light),
        "is_white": bool(piece and piece.color == chess.WHITE),
        "is_light": is_light,
        "is_dark": not is_light,
    }


def _glyph(piece: chess.Piece | None) -> str:
    """The two-unit glyph for a square: a piece, or the black square marker."""
    from .board_render import PIECES

    if piece is None:
        return BLACK_SQUARE
    return PIECES[(piece.color == chess.WHITE, piece.piece_type)]


def _ascii_glyph(piece: chess.Piece | None, *, is_light: bool) -> str:
    """The normal-format glyph: a piece, or a light/dark square marker."""
    from .board_render import DARK_SQUARE, LIGHT_SQUARE, PIECES

    if piece is None:
        return LIGHT_SQUARE if is_light else DARK_SQUARE
    return PIECES[(piece.color == chess.WHITE, piece.piece_type)]


def render(board: chess.Board, mode: str | None = None) -> str:
    """Render ``board`` with the template named ``mode``.

    Args:
        board: The position to draw.
        mode: A key of :data:`AVAILABLE_MODES`; defaults to ``DEFAULT_MODE``.

    Raises:
        ValueError: if ``mode`` is not an available template.
    """
    chosen = mode or DEFAULT_MODE
    if chosen not in AVAILABLE_MODES:
        available = ", ".join(AVAILABLE_MODES)
        msg = f"unknown board mode {chosen!r}; available modes: {available}"
        raise ValueError(msg)
    template = _env.get_template(f"{chosen}.j2")
    return template.render(**build_context(board))


def modes() -> Iterable[str]:
    """Return the available mode names."""
    return AVAILABLE_MODES
