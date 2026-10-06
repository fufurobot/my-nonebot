"""Smoke tests proving the test harness can load the chess plugin package."""

from __future__ import annotations


def test_plugin_package_loads(chess_package):
    assert chess_package is not None
    assert hasattr(chess_package, "games")


def test_game_module_exposes_chess_game(game_module):
    assert hasattr(game_module, "ChessGame")


def test_new_game_starts_from_initial_position(ChessGame):
    game = ChessGame(group_id=1)
    assert game.board.fen().startswith("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR")
    assert game.result is None
    assert game.game_over is False
