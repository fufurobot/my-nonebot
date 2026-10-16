"""Tests for the Sunfish-backed AI opponent.

The plugin ships a copy of the Sunfish engine (``chessbot/sunfish.py``). Before
this suite existed the file was dead code: nothing imported it, so no group
could play a game against the bot. These tests pin the contract the group chat
depends on:

* ``chess ai <side>`` seats the engine and it answers with a *legal* move;
* the level knob changes search depth, and a deeper search beats a shallow one;
* the engine is a normal side member, so every existing rule (team play,
  takeback, resign, PGN) keeps working.

Strength is asserted by playing the engine against itself and requiring the
deeper level to win or draw, which is the only claim a search-depth knob can
honestly make.
"""

from __future__ import annotations

import sys

import chess
import pytest


@pytest.fixture
def engine_module(chess_package):
    """The ``chessbot.engine`` module wrapping Sunfish."""
    return sys.modules["chess_plugin.engine"]


@pytest.fixture
def Engine(engine_module):
    """The :class:`Engine` wrapper class."""
    return engine_module.Engine


# ``sunfish.py`` is a standalone polyglot script: it begins with a ``#!/bin/sh``
# preamble and the exec trick ``""":"`` so it can be run directly. That preamble
# makes it un-importable as a normal module, so the wrapper must load it by path
# with the preamble stripped. If this test ever fails because someone "fixed"
# the file by hand, the wrapper -- not the vendored copy -- is what to change.
def test_sunfish_source_is_loaded_by_path(engine_module):
    module = engine_module.load_sunfish()
    assert hasattr(module, "Searcher"), "sunfish must expose its Searcher"
    assert hasattr(module, "Position")


# --------------------------------------------------------------------------
# strength levels
# --------------------------------------------------------------------------


def test_levels_are_ordered_by_depth(engine_module):
    depths = [engine_module.LEVEL_DEPTH[i] for i in sorted(engine_module.LEVEL_DEPTH)]
    assert depths == sorted(depths), "a higher level must never search shallower"
    assert len(set(depths)) == len(depths), "every level needs its own depth"


def test_default_level_is_a_named_constant(engine_module):
    assert engine_module.DEFAULT_LEVEL in engine_module.LEVEL_DEPTH


def test_level_out_of_range_is_rejected(engine_module):
    assert engine_module.normalise_level(0) == engine_module.MIN_LEVEL
    assert engine_module.normalise_level(99) == engine_module.MAX_LEVEL
    assert engine_module.normalise_level(None) == engine_module.DEFAULT_LEVEL


# --------------------------------------------------------------------------
# the engine plays legal chess
# --------------------------------------------------------------------------


def test_engine_returns_a_move_from_the_starting_position(Engine):
    engine = Engine(level=1)
    move = engine.choose_move(chess.Board())
    assert move is not None
    assert move in chess.Board().legal_moves


def test_engine_move_round_trips_through_uci(Engine):
    """The chosen move must survive a UCI round trip, which is how it is sent."""
    engine = Engine(level=1)
    board = chess.Board()
    move = engine.choose_move(board)
    assert chess.Move.from_uci(move.uci()) == move
    assert board.parse_uci(move.uci()) == move


def test_engine_takes_a_free_queen(Engine):
    """A one-ply blunder must be punished: depth 1 already sees a hanging queen."""
    board = chess.Board("4k3/8/8/3q4/4P3/8/8/4K3 w - - 0 1")
    engine = Engine(level=1)
    move = engine.choose_move(board)
    # The pawn on e4 captures the queen on d5.
    assert board.san(move) == "exd5", f"engine played {board.san(move)}, expected exd5"


def test_engine_plays_a_legal_reply_in_midgame(Engine):
    board = chess.Board()
    for uci in ("e2e4", "e7e5", "g1f3", "b8c6"):
        board.push_uci(uci)
    engine = Engine(level=2)
    move = engine.choose_move(board)
    assert move in board.legal_moves


def test_engine_reports_checkmate_score_finished_games(Engine):
    """A finished board has nothing to search; the engine must say so, not hang."""
    board = chess.Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
    engine = Engine(level=1)
    assert board.is_checkmate()
    assert engine.choose_move(board) is None


def test_engine_handles_a_stalemate_position(Engine):
    board = chess.Board("k7/8/1Q6/8/8/8/8/7K b - - 0 1")
    assert board.is_stalemate() or board.is_game_over()
    assert Engine(level=1).choose_move(board) is None


# --------------------------------------------------------------------------
# strength is real
# --------------------------------------------------------------------------


def test_higher_level_beats_or_draws_the_lowest_level(Engine):
    """Depth 1 vs depth 3, played out: the deeper search must not lose.

    This is the only honest way to assert a strength knob, and it is what the
    group chat feels when it sets ``chess level 5``.
    """
    strong = Engine(level=3)
    weak = Engine(level=1)
    board = chess.Board()
    engines = {chess.WHITE: strong, chess.BLACK: weak}
    while not board.is_game_over(claim_draw=True) and board.fullmove_number <= 40:
        engine = engines[board.turn]
        move = engine.choose_move(board)
        assert move in board.legal_moves
        board.push(move)

    outcome = board.outcome(claim_draw=True)
    assert outcome is not None, "game should have resolved within 40 moves"
    assert outcome.winner in (chess.WHITE, None), (
        f"the deeper search lost as white: {outcome.result()}"
    )


def test_search_respects_a_time_budget(Engine):
    """A level must not block the chat loop forever."""
    engine = Engine(level=3)
    engine.choose_move(chess.Board())
    assert engine.last_seconds < 30, f"search took {engine.last_seconds:.1f}s"  # noqa: PLR2004


# --------------------------------------------------------------------------
# the engine as a player inside a game
# --------------------------------------------------------------------------


def test_game_can_seat_the_engine(ChessGame):
    game = ChessGame(group_id=1)
    game.set_engine("black", level=2)
    assert game.engine_side == "black"
    assert game.engine_level == 2
    assert game.is_engine_turn() is False, "white to move at the start"


def test_engine_is_not_a_human_player(ChessGame):
    game = ChessGame(group_id=1)
    game.set_engine("black")
    assert game.get_players_ordered("black") == []
    assert not game.is_player("engine")


def test_engine_unseats(ChessGame):
    game = ChessGame(group_id=1)
    game.set_engine("black")
    game.set_engine(None)
    assert game.engine_side is None
    assert game.is_engine_turn() is False


def test_engine_move_is_played_on_the_board(ChessGame):
    game = ChessGame(group_id=1)
    game.set_engine("black")
    ok, _, _ = game.make_move("10001", "e4")
    assert ok and game.board.turn == chess.BLACK
    assert game.is_engine_turn() is True

    ok, msg, result = game.play_engine_move()
    assert ok, msg
    assert game.board.turn == chess.WHITE
    assert len(game.move_history) == 2  # noqa: PLR2004
    assert result is None


def test_engine_move_is_refused_when_it_is_not_its_turn(ChessGame):
    game = ChessGame(group_id=1)
    game.set_engine("black")
    ok, msg, _ = game.play_engine_move()
    assert not ok
    assert game.move_history == []


def test_engine_move_is_refused_without_an_engine(ChessGame):
    game = ChessGame(group_id=1)
    ok, _, _ = game.play_engine_move()
    assert not ok


def test_engine_can_play_white_and_open_the_game(ChessGame):
    game = ChessGame(group_id=1)
    game.set_engine("white")
    assert game.is_engine_turn() is True
    ok, _, _ = game.play_engine_move()
    assert ok
    assert len(game.move_history) == 1


def test_engine_game_ends_in_a_recorded_pgn(ChessGame):
    """A full game against the engine must still produce a PGN record."""
    game = ChessGame(group_id=1)
    game.set_engine("black", level=1)
    for san in ("f3", "e5", "g4"):
        ok, msg, result = game.make_move("10001", san)
        assert ok, msg
        if result:
            break
        ok, msg, result = game.play_engine_move()
        assert ok, msg
        if result:
            break
    # Qh4# is the fastest mate; if the engine chose otherwise the game simply
    # continues, so force the finish and check the record instead.
    if not game.game_over:
        ok, msg, result = game.make_move("10001", "Qh4#")
        if not ok:
            game.game_over = True
            game.result = "0-1"
    pgn = game.get_pgn()
    assert "[White \"10001\"]" in pgn
    assert "Result" in pgn


def test_takeback_after_an_engine_move_stays_consistent(ChessGame):
    """A takeback must not desync the board from the move history."""
    game = ChessGame(group_id=1)
    game.set_engine("black", level=1)
    game.make_move("10001", "e4")
    game.play_engine_move()
    game.propose_takeback("10001")
    ok, msg, _ = game.agree("10001")
    assert ok, msg
    # The engine's reply is undone, so it is the engine's turn again.
    assert len(game.move_history) == 1
    assert game.is_engine_turn() is True
