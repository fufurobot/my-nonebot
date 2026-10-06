"""Tests for the Jinja board templates and the compact rendering mode.

Two formats are required:

``normal``
    The existing bordered Unicode grid with ``a``-``h`` / ``1``-``8``
    coordinates.

``compact``
    A strictly bounded format. Every line must fit in **13 fullwidth
    characters** (26 display units), assuming a fixed-width font where the
    pieces and the supplied fullwidth characters each occupy two units. It may
    use only:

    * the chess pieces ``♙♘♗♖♕♔`` / ``♟♞♝♜♛♚``,
    * the fullwidth file letters ``ａｂｃｄｅｆｇｈ``,
    * the ideographic space ``U+3000``,
    * the black square ``■``.

    No ASCII and no box-drawing characters are permitted, because those are one
    unit wide and would break the two-column grid.
"""

from __future__ import annotations

import sys

import chess
import pytest

# --------------------------------------------------------------------------
# the character contract
# --------------------------------------------------------------------------

COMPACT_LIMIT = 13  # fullwidth characters, i.e. 26 display units

PIECES = set("♙♘♗♖♕♔♟♞♝♜♛♚")
FULLWIDTH_FILES = set("ａｂｃｄｅｆｇｈ")
IDEOGRAPHIC_SPACE = "\u3000"
BLACK_SQUARE = "■"

ALLOWED_COMPACT_CHARS = PIECES | FULLWIDTH_FILES | {IDEOGRAPHIC_SPACE, BLACK_SQUARE}


def _compact_lines(game):
    return game.get_board_str(mode="compact").splitlines()


# --------------------------------------------------------------------------
# the hard width limit
# --------------------------------------------------------------------------


def test_compact_lines_never_exceed_thirteen_characters(ChessGame):
    lines = _compact_lines(ChessGame(group_id=1))
    for line in lines:
        assert len(line) <= COMPACT_LIMIT, (
            f"compact line is {len(line)} chars, limit is {COMPACT_LIMIT}: {line!r}"
        )


def test_compact_width_holds_in_a_midgame_position(ChessGame):
    game = ChessGame(group_id=1)
    game.add_player("1", "white")
    game.add_player("2", "black")
    for san in ("e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Ba4", "Nf6", "O-O", "Be7"):
        mover = "1" if game.board.turn == chess.WHITE else "2"
        ok, msg, _ = game.make_move(mover, san)
        assert ok, msg
    for line in _compact_lines(game):
        assert len(line) <= COMPACT_LIMIT, f"line too wide: {line!r}"


def test_compact_width_holds_in_an_endgame_with_promotions(ChessGame):
    game = ChessGame(group_id=1)
    game.add_player("1", "white")
    game.add_player("2", "black")
    # Walk into a promotion so queens appear on the board.
    for san in ("d4", "d5", "c4", "dxc4", "e3", "b5", "a4", "c3", "axb5", "cxb2"):
        mover = "1" if game.board.turn == chess.WHITE else "2"
        ok, msg, _ = game.make_move(mover, san)
        assert ok, msg
    for line in _compact_lines(game):
        assert len(line) <= COMPACT_LIMIT, f"line too wide: {line!r}"


# --------------------------------------------------------------------------
# the character contract
# --------------------------------------------------------------------------


def test_compact_uses_only_allowed_characters(ChessGame):
    text = ChessGame(group_id=1).get_board_str(mode="compact")
    offending = {ch for ch in str(text) if ch not in ALLOWED_COMPACT_CHARS}
    assert not offending, f"compact mode used disallowed characters: {offending!r}"


def test_compact_contains_no_ascii_letters_or_digits(ChessGame):
    text = ChessGame(group_id=1).get_board_str(mode="compact")
    assert not any(ch.isascii() and ch.isalnum() for ch in text), (
        f"compact mode must not use ASCII alphanumerics: {text!r}"
    )


def test_compact_uses_no_box_drawing_characters(ChessGame):
    text = ChessGame(group_id=1).get_board_str(mode="compact")
    box = set("┌┬┐├┼┤└┴┘│─┏┓┗┛╔╗╚╝")
    assert not (set(text) & box), "compact mode must not draw a table"


def test_compact_has_no_middot_or_ascii_space(ChessGame):
    text = ChessGame(group_id=1).get_board_str(mode="compact")
    assert "·" not in text, "middot is not in the allowed compact character set"
    assert " " not in text, "ASCII space is 1 unit wide; use U+3000 instead"


# --------------------------------------------------------------------------
# readability
# --------------------------------------------------------------------------


def test_compact_shows_coordinates(ChessGame):
    text = ChessGame(group_id=1).get_board_str(mode="compact")
    assert any(f in text for f in FULLWIDTH_FILES), "no fullwidth file letter found"
    assert any(d in text for d in "１２３４５６７８"), "no fullwidth rank digit found"


def test_compact_shows_all_eight_file_letters(ChessGame):
    text = ChessGame(group_id=1).get_board_str(mode="compact")
    missing = FULLWIDTH_FILES - set(text)
    assert not missing, f"file letters missing from compact board: {missing!r}"


def test_compact_shows_all_eight_rank_digits(ChessGame):
    text = ChessGame(group_id=1).get_board_str(mode="compact")
    missing = set("１２３４５６７８") - set(text)
    assert not missing, f"rank digits missing from compact board: {missing!r}"


def test_compact_renders_the_starting_pieces(ChessGame):
    text = ChessGame(group_id=1).get_board_str(mode="compact")
    # 16 pieces at the start: eight white, eight black.
    assert sum(text.count(p) for p in "♙♘♗♖♕♔") >= 8
    assert sum(text.count(p) for p in "♟♞♝♜♛♚") >= 8


def test_compact_has_one_line_per_rank(ChessGame):
    lines = _compact_lines(ChessGame(group_id=1))
    # At minimum one rendered line per rank.
    assert len(lines) >= 8, f"expected >= 8 lines, got {len(lines)}"


# --------------------------------------------------------------------------
# the template engine
# --------------------------------------------------------------------------


def test_templates_module_exposes_the_two_modes(chess_package):
    module = sys.modules["chess_plugin.board_templates"]
    assert set(module.AVAILABLE_MODES) >= {"normal", "compact"}


def test_default_mode_is_compact(ChessGame):
    game = ChessGame(group_id=1)
    assert game.get_board_str() == game.get_board_str(mode="compact")


def test_normal_mode_still_uses_the_unicode_table(ChessGame):
    text = ChessGame(group_id=1).get_board_str(mode="normal")
    assert "┌" in text and "│" in text, "normal mode must keep the bordered grid"
    assert "♙" in text


def test_unknown_mode_is_rejected(ChessGame):
    game = ChessGame(group_id=1)
    with pytest.raises(ValueError, match="compact|normal|unknown"):
        game.get_board_str(mode="definitely-not-a-mode")


def test_templates_are_loaded_from_disk(chess_package):
    module = sys.modules["chess_plugin.board_templates"]
    for mode in module.AVAILABLE_MODES:
        path = module.template_path(mode)
        assert path.is_file(), f"missing template file for {mode!r}: {path}"


def test_templates_render_without_jinja_syntax_leftovers(ChessGame):
    for mode in ("normal", "compact"):
        text = ChessGame(group_id=1).get_board_str(mode=mode)
        assert "{{" not in text and "{%" not in text, (
            f"{mode} template left unrendered Jinja syntax: {text!r}"
        )


def test_render_context_is_exposed_for_templates(ChessGame):
    """Templates receive ranks/files/pieces data rather than a prebuilt string."""
    module = sys.modules["chess_plugin.board_templates"]
    board = chess.Board()
    ctx = module.build_context(board)
    assert ctx["files"] == list("ａｂｃｄｅｆｇｈ")
    assert len(ctx["rows"]) == 8
    assert ctx["rows"][0]["rank"] == "８"
    assert len(ctx["rows"][0]["cells"]) == 8
