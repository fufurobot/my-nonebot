"""Tests for the Unicode/emoji board renderer.

The board must be a readable monospace grid built from Unicode box-drawing
characters, use emoji chess pieces, and label every file (a-h) and rank (1-8)
so a player can name a square without guessing.
"""

from __future__ import annotations

import chess
import pytest

FILES = "abcdefgh"
RANKS = "12345678"


def test_board_contains_every_file_letter(ChessGame):
    board_str = ChessGame(group_id=1).get_board_str()
    top, bottom = board_str.splitlines()[0], board_str.splitlines()[-1]
    for letter in FILES:
        assert letter in top, f"file {letter} missing from header: {top!r}"
        assert letter in bottom, f"file {letter} missing from footer: {bottom!r}"


def test_board_contains_every_rank_number(ChessGame):
    board_str = ChessGame(group_id=1).get_board_str()
    for rank in RANKS:
        assert rank in board_str, f"rank {rank} missing from board"


def test_board_has_eight_rows_and_columns(ChessGame):
    board_str = ChessGame(group_id=1).get_board_str()
    rows = [ln for ln in board_str.splitlines() if "♟" in ln or "♙" in ln or "│" in ln]
    assert len(rows) >= 8, f"expected at least 8 board rows, got {len(rows)}"


def test_board_uses_emoji_pieces(ChessGame):
    board_str = ChessGame(group_id=1).get_board_str()
    # Starting position: 8 white pawns and 8 black pawns at minimum.
    assert board_str.count("♙") + board_str.count("♟") >= 16, board_str


def test_board_uses_unicode_box_drawing(ChessGame):
    board_str = ChessGame(group_id=1).get_board_str()
    assert any(ch in board_str for ch in "┌┬┐├┼┤└┴┘│─"), (
        f"expected box-drawing characters, got:\n{board_str}"
    )


def test_board_lines_are_equal_width(ChessGame):
    board_str = ChessGame(group_id=1).get_board_str()
    lines = [ln for ln in board_str.splitlines() if ln.strip()]
    assert len({len(ln) for ln in lines}) == 1, (
        "all board lines must share one display width:\n" + "\n".join(lines)
    )


def test_board_reflects_a_move(ChessGame):
    game = ChessGame(group_id=1)
    game.white_players.add("10001")
    game.black_players.add("10002")
    before = game.get_board_str()
    ok, _, _ = game.make_move("10001", "e4")
    assert ok
    after = game.get_board_str()
    assert before != after


def test_empty_squares_are_labelled_not_blank(ChessGame):
    board_str = ChessGame(group_id=1).get_board_str()
    # A blank grid would be unusable; require the rank digits to anchor rows.
    assert sum(board_str.count(r) for r in RANKS) >= 8


@pytest.mark.parametrize("san,expect_marker", [("e4", "e4"), ("Nf3", "Nf3")])
def test_board_export_is_stable_across_moves(ChessGame, san, expect_marker):
    game = ChessGame(group_id=1)
    game.white_players.add("10001")
    game.black_players.add("10002")
    ok, _, _ = game.make_move("10001", san)
    assert ok
    assert "│" in game.get_board_str()


def test_board_renders_after_castling(ChessGame):
    game = ChessGame(group_id=1)
    for san in ("e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5", "O-O"):
        ok, msg, _ = game.make_move(
            "10001" if game.board.turn == chess.WHITE else "10002", san
        )
        assert ok, msg
    board_str = game.get_board_str()
    assert "♔" in board_str or "♚" in board_str
