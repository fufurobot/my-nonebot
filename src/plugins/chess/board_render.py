"""Unicode board rendering for the chess plugin.

The renderer draws a bordered, monospace grid so the board stays readable in a
QQ chat window:

* a light/dark square pattern carries the checkerboard;
* pieces are solid Unicode chess glyphs (emoji-capable fonts render them in
  colour);
* the header and footer both carry the file letters ``a``-``h`` and every row
  carries its rank digit ``1``-``8``, so players can name a square by looking at
  the picture instead of counting.

Every produced line is padded to the same display width, because QQ renders a
message in a proportional font and ragged lines destroy the grid.
"""

from __future__ import annotations

import chess

# Unicode chess pieces, indexed by (is_white, piece_type).
PIECES: dict[tuple[bool, int], str] = {
    (True, chess.PAWN): "♙",
    (True, chess.KNIGHT): "♘",
    (True, chess.BISHOP): "♗",
    (True, chess.ROOK): "♖",
    (True, chess.QUEEN): "♕",
    (True, chess.KING): "♔",
    (False, chess.PAWN): "♟",
    (False, chess.KNIGHT): "♞",
    (False, chess.BISHOP): "♝",
    (False, chess.ROOK): "♜",
    (False, chess.QUEEN): "♛",
    (False, chess.KING): "♚",
}

LIGHT_SQUARE = " "
DARK_SQUARE = "·"
EMPTY = " "

# Box-drawing characters for the frame.
TOP_LEFT, TOP_MID, TOP_RIGHT = "┌", "┬", "┐"
BOT_LEFT, BOT_MID, BOT_RIGHT = "└", "┴", "┘"
MID_LEFT, MID_MID, MID_RIGHT = "├", "┼", "┤"
HORIZONTAL, VERTICAL = "─", "│"

FILES = "abcdefgh"
RANKS = "12345678"


def _square_glyph(board: chess.Board, square: int) -> str:
    """Return the single character that represents ``square``."""
    piece = board.piece_at(square)
    if piece is not None:
        return PIECES[(piece.color == chess.WHITE, piece.piece_type)]
    is_light = (chess.square_file(square) + chess.square_rank(square)) % 2 == 1
    return LIGHT_SQUARE if is_light else DARK_SQUARE


def render_board(board: chess.Board) -> str:
    """Render ``board`` as a bordered Unicode grid with coordinates.

    Args:
        board: The position to draw. It is not modified.

    Returns:
        A multi-line string of equal-width lines.
    """
    cell = 3  # one glyph plus one space of padding on each side
    span = HORIZONTAL * cell
    # The rank digits occupy a two-character gutter to the right of the grid.
    gutter = " " * 2

    header = TOP_LEFT + TOP_MID.join(span for _ in FILES) + TOP_RIGHT + gutter
    footer = BOT_LEFT + BOT_MID.join(span for _ in FILES) + BOT_RIGHT + gutter
    files_row = VERTICAL + VERTICAL.join(f" {f} " for f in FILES) + VERTICAL + gutter
    separator = MID_LEFT + MID_MID.join(span for _ in FILES) + MID_RIGHT + gutter

    lines = [header, files_row, separator]

    for rank_index in range(7, -1, -1):
        cells = []
        for file_index in range(8):
            square = chess.square(file_index, rank_index)
            cells.append(f" {_square_glyph(board, square)} ")
        row = VERTICAL + VERTICAL.join(cells) + VERTICAL + f" {rank_index + 1}"
        lines.append(row)

    lines.append(separator)
    lines.append(files_row)
    lines.append(footer)
    return "\n".join(lines)
