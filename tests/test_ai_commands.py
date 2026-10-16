"""Tests for the group-chat wiring of the AI opponent.

``test_engine.py`` covers the search itself; this file covers what a group
actually types. The engine is driven through ``Matcher`` directly -- no running
bot and no QQ client -- so the assertions are about the plugin's dispatch, not
about the network.

The auto-reply is the part worth pinning hardest: after a human moves, the
engine must answer **in the same command** before the handler returns. If the
reply were queued as a background task the board in the next message would be
stale, and the group would see the engine's move and the next human move out of
order.
"""

from __future__ import annotations

import chess
import pytest
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message
from nonebot.exception import FinishedException
from nonebot.matcher import Matcher

GROUP_ID = 726525232
HUMAN = "1362015219"


@pytest.fixture
def plugin(chess_package):
    """The chessbot plugin module, freshly stripped of group state."""
    chess_package.games.clear()
    chess_package.board_modes.clear()
    yield chess_package
    chess_package.games.clear()
    chess_package.board_modes.clear()


@pytest.fixture
def bot():
    """A real ``Bot`` instance; ``call_api`` is never reached in these tests."""
    return Bot(adapter=None, self_id="369319889")  # type: ignore[arg-type]


def make_event(text: str, user_id: str = HUMAN) -> GroupMessageEvent:
    """Build the group message event the dispatcher receives."""
    return GroupMessageEvent(
        time=1790480000,
        self_id=369319889,
        post_type="message",
        sub_type="normal",
        user_id=int(user_id),
        message_type="group",
        message_id=9001,
        group_id=GROUP_ID,
        message=Message(text),
        raw_message=text,
        font=0,
        sender={
            "user_id": int(user_id),
            "nickname": "ASIMO",
            "role": "member",
        },
    )


async def run_command(plugin, bot, text: str, user_id: str = HUMAN) -> list[str]:
    """Invoke the chess handler and collect every message it sent.

    ``Matcher.finish`` raises ``FinishedException`` to unwind the handler, which
    is normal control flow here, not a failure.
    """
    sent: list[str] = []

    async def fake_send(self, message, **_kwargs: object):
        sent.append(str(message))

    async def fake_finish(self, message=None, **_kwargs: object):
        if message is not None:
            sent.append(str(message))
        raise FinishedException

    matcher = Matcher()
    matcher.send = fake_send.__get__(matcher, Matcher)  # type: ignore[method-assign]
    matcher.finish = fake_finish.__get__(matcher, Matcher)  # type: ignore[method-assign]

    # The handler is written against the module-global ``chess`` matcher, so the
    # stub has to be installed there for the duration of the call. ``arg`` is
    # passed directly: ``CommandArg`` is a dependency marker resolved by
    # NoneBot, not something a test can call.
    original = plugin.chess
    plugin.chess = matcher
    try:
        await plugin.handle_chess(
            bot,
            make_event(text, user_id),
            Message(text.split(" ", 1)[-1]),
        )
    except FinishedException:
        pass
    finally:
        plugin.chess = original
    return sent


# --------------------------------------------------------------------------
# chess ai
# --------------------------------------------------------------------------


async def test_ai_command_seats_the_engine(plugin, bot):
    sent = await run_command(plugin, bot, "/chess ai black")
    assert any("黑" in part or "black" in part for part in sent), sent
    game = plugin.games[GROUP_ID]
    assert game.engine_side == "black"


async def test_ai_defaults_to_the_empty_side(plugin, bot):
    await run_command(plugin, bot, "/chess join white")
    await run_command(plugin, bot, "/chess ai")
    game = plugin.games[GROUP_ID]
    assert game.engine_side == "black", "the side with no humans should get the AI"


async def test_ai_off_unseats_the_engine(plugin, bot):
    await run_command(plugin, bot, "/chess ai black")
    await run_command(plugin, bot, "/chess ai off")
    assert plugin.games[GROUP_ID].engine_side is None


async def test_ai_rejects_an_unknown_side(plugin, bot):
    await run_command(plugin, bot, "/chess join white")
    sent = await run_command(plugin, bot, "/chess ai purple")
    assert any("purple" in part or "white" in part or "black" in part for part in sent)
    assert plugin.games[GROUP_ID].engine_side is None


async def test_ai_level_argument_is_honoured(plugin, bot):
    await run_command(plugin, bot, "/chess ai black 5")
    assert plugin.games[GROUP_ID].engine_level == 5


async def test_ai_is_listed_in_help(plugin, bot):
    sent = await run_command(plugin, bot, "/chess help")
    assert any("ai" in part for part in sent), sent


async def test_level_command_reports_and_sets(plugin, bot):
    sent = await run_command(plugin, bot, "/chess level")
    assert sent, "chess level with no argument must report the current level"
    await run_command(plugin, bot, "/chess level 4")
    assert plugin.board_levels[GROUP_ID] == 4


async def test_level_command_clamps_out_of_range(plugin, bot):
    await run_command(plugin, bot, "/chess level 99")
    assert plugin.board_levels[GROUP_ID] == plugin.MAX_LEVEL


# --------------------------------------------------------------------------
# the auto-reply
# --------------------------------------------------------------------------


async def test_engine_replies_after_a_human_move(plugin, bot):
    await run_command(plugin, bot, "/chess join white")
    await run_command(plugin, bot, "/chess ai black 1")
    sent = await run_command(plugin, bot, "/chess move e4")

    game = plugin.games[GROUP_ID]
    assert len(game.move_history) == 2, (
        f"the engine did not answer in the same turn: {game.move_history}"
    )
    assert game.board.turn == chess.WHITE
    assert any("e4" in part for part in sent)


async def test_engine_does_not_reply_before_the_game_starts(plugin, bot):
    """Seating the AI alone must not start the game or move for the absent side.

    With nobody on the other side there is no game yet, so the engine must wait
    rather than open against an empty seat.
    """
    sent = await run_command(plugin, bot, "/chess ai white 1")
    game = plugin.games[GROUP_ID]
    assert game.engine_side == "white"
    assert game.move_history == [], "the engine moved before anyone was seated"
    assert any("join" in part for part in sent), sent


async def test_engine_does_not_reply_when_it_is_not_its_turn(plugin, bot):
    """The engine moves only on its own turn, not after every human command."""
    await run_command(plugin, bot, "/chess ai black 1")
    await run_command(plugin, bot, "/chess join white")
    game = plugin.games[GROUP_ID]
    assert game.is_engine_turn() is False, "White is to move, so the AI must wait"

    # Non-move commands must never advance the board.
    before = list(game.move_history)
    await run_command(plugin, bot, "/chess players")
    await run_command(plugin, bot, "/chess board")
    assert game.move_history == before, "the engine moved without being asked"


async def test_join_as_black_lets_the_engine_white_open(plugin, bot):
    """Playing black should be a single command: join, and the AI opens."""
    await run_command(plugin, bot, "/chess ai white 1")
    await run_command(plugin, bot, "/chess join black")
    game = plugin.games[GROUP_ID]
    assert len(game.move_history) == 1, (
        f"the engine should have opened as white: {game.move_history}"
    )
    assert game.board.turn == chess.BLACK


async def test_engine_moves_are_flagged_in_the_reply(plugin, bot):
    await run_command(plugin, bot, "/chess join white")
    await run_command(plugin, bot, "/chess ai black 1")
    sent = await run_command(plugin, bot, "/chess move e4")
    joined = "\n".join(sent)
    assert "AI" in joined or "引擎" in joined, (
        f"the group cannot tell the engine moved without a marker: {joined!r}"
    )


async def test_a_finished_game_stops_the_engine(plugin, bot):
    """A game that ends while the engine is seated must not keep playing.

    Once ``game_over`` is set the engine has no legal obligation to move, and
    the handler must not schedule one -- otherwise a finished PGN would be
    followed by extra moves and a corrupted record.
    """
    await run_command(plugin, bot, "/chess join white")
    await run_command(plugin, bot, "/chess ai black 1")
    game = plugin.games[GROUP_ID]
    game.game_over = True
    game.result = "0-1"

    ok, _, _ = game.play_engine_move()
    assert not ok, "a finished game must not accept an engine move"
    assert game.move_history == []
