"""Tests for multi-player teams, last-leaver-resigns, and PGN identification.

Requirements under test
-----------------------
1. Several players may join one game on the same side, and one player may hold
   both sides at once (solo testing).
2. A player leaving does *not* end the game while teammates remain on that side.
3. The side is only resigned once its **last** player leaves.
4. The finishing PGN records the QQ numbers of the players on each side.
"""

from __future__ import annotations

import chess


def _started(ChessGame, **kwargs):
    game = ChessGame(group_id=1, **kwargs)
    return game


# --------------------------------------------------------------------------
# 1. multiple players per side
# --------------------------------------------------------------------------


def test_multiple_players_can_join_the_same_side(ChessGame):
    game = _started(ChessGame)
    assert game.add_player("10001", "white") is True
    assert game.add_player("10002", "white") is True
    assert game.add_player("10003", "white") is True
    assert game.get_players_ordered("white") == ["10001", "10002", "10003"]


def test_players_are_recorded_in_join_order(ChessGame):
    game = _started(ChessGame)
    for user in ("10003", "10001", "10002"):
        game.add_player(user, "black")
    assert game.get_players_ordered("black") == ["10003", "10001", "10002"]


def test_one_player_may_join_both_sides(ChessGame):
    game = _started(ChessGame)
    assert game.add_player("10001", "white") is True
    assert game.add_player("10001", "black") is True
    assert game.is_player("10001")
    assert game.get_side("10001") in {"white", "black"}


def test_joining_the_same_side_twice_is_rejected(ChessGame):
    game = _started(ChessGame)
    assert game.add_player("10001", "white") is True
    assert game.add_player("10001", "white") is False
    assert game.get_players_ordered("white") == ["10001"]


def test_any_side_member_may_move(ChessGame):
    game = _started(ChessGame)
    game.add_player("10001", "white")
    game.add_player("10002", "white")
    game.add_player("20001", "black")
    ok, msg, _ = game.make_move("10002", "e4")
    assert ok, msg
    assert game.board.piece_at(chess.E4) is not None


def test_non_side_member_cannot_move_for_that_side(ChessGame):
    game = _started(ChessGame)
    game.add_player("10001", "white")
    game.add_player("20001", "black")
    ok, msg, _ = game.make_move("20001", "e4")
    assert not ok
    assert "白" in msg


# --------------------------------------------------------------------------
# 2 + 3. leaving only resigns when the side is empty
# --------------------------------------------------------------------------


def test_leaving_with_a_teammate_left_keeps_the_game_alive(ChessGame):
    game = _started(ChessGame)
    game.add_player("10001", "white")
    game.add_player("10002", "white")
    game.add_player("20001", "black")

    removed, result = game.remove_player("10001")

    assert removed is True
    assert result is None, "game must continue while a teammate remains"
    assert game.game_over is False
    assert game.get_players_ordered("white") == ["10002"]


def test_last_player_leaving_resigns_that_side(ChessGame):
    game = _started(ChessGame)
    game.add_player("10001", "white")
    game.add_player("20001", "black")

    removed, result = game.remove_player("10001")

    assert removed is True
    assert result == "0-1", "white resigned, so black wins"
    assert game.game_over is True


def test_resign_after_teammates_have_all_left(ChessGame):
    game = _started(ChessGame)
    game.add_player("10001", "white")
    game.add_player("10002", "white")
    game.add_player("20001", "black")

    assert game.remove_player("10001")[1] is None
    removed, result = game.remove_player("10002")

    assert removed is True
    assert result == "0-1"
    assert game.game_over is True


def test_black_last_player_leaving_resigns_to_white(ChessGame):
    game = _started(ChessGame)
    game.add_player("10001", "white")
    game.add_player("20001", "black")

    removed, result = game.remove_player("20001")

    assert removed is True
    assert result == "1-0"
    assert game.game_over is True


def test_removing_an_unknown_player_reports_failure(ChessGame):
    game = _started(ChessGame)
    game.add_player("10001", "white")
    removed, result = game.remove_player("99999")
    assert removed is False
    assert result is None


def test_leaving_does_not_end_an_already_finished_game(ChessGame):
    game = _started(ChessGame)
    game.add_player("10001", "white")
    game.add_player("20001", "black")
    game.game_over = True
    game.result = "1-0"

    removed, result = game.remove_player("10001")

    assert removed is True
    assert game.result == "1-0", "the recorded result must not be overwritten"


def test_join_order_is_remembered_for_teams(ChessGame):
    game = _started(ChessGame)
    for user in ("1", "2", "3", "4"):
        game.add_player(user, "white")
    assert game.get_players_ordered("white") == ["1", "2", "3", "4"]


# --------------------------------------------------------------------------
# 4. QQ numbers in the endgame PGN
# --------------------------------------------------------------------------


def test_pgn_records_qq_numbers_for_both_sides(ChessGame):
    game = _started(ChessGame)
    game.add_player("10001", "white")
    game.add_player("10002", "white")
    game.add_player("20001", "black")
    game.make_move("10001", "e4")

    pgn = game.get_pgn()

    assert "10001" in pgn
    assert "10002" in pgn
    assert "20001" in pgn
    assert "White" in pgn
    assert "Black" in pgn


def test_pgn_lists_multiple_players_per_side(ChessGame):
    game = _started(ChessGame)
    game.add_player("10001", "white")
    game.add_player("10002", "white")
    game.add_player("20001", "black")
    game.add_player("20002", "black")

    pgn = game.get_pgn()
    white_line = next(ln for ln in pgn.splitlines() if ln.startswith('[White '))
    black_line = next(ln for ln in pgn.splitlines() if ln.startswith('[Black '))

    assert "10001" in white_line and "10002" in white_line
    assert "20001" in black_line and "20002" in black_line


def test_pgn_records_the_resign_result(ChessGame):
    game = _started(ChessGame)
    game.add_player("10001", "white")
    game.add_player("20001", "black")
    game.remove_player("10001")

    pgn = game.get_pgn()
    assert '[Result "0-1"]' in pgn
