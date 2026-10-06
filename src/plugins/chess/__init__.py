from nonebot import on_command
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent
from nonebot.params import CommandArg

import chess as chess_lib

from . import board_templates
from .game import ChessGame

# 存储每个群的游戏状态
games: dict[int, ChessGame] = {}

# 每个群选择的棋盘显示模板（默认紧凑模式）
board_modes: dict[int, str] = {}

# 创建命令处理器
chess = on_command("chess", priority=10, block=True)


def _mode_for(group_id: int) -> str:
    """返回该群当前使用的棋盘模板名。"""
    mode = board_modes.get(group_id, board_templates.DEFAULT_MODE)
    if mode not in board_templates.AVAILABLE_MODES:
        return board_templates.DEFAULT_MODE
    return mode


HELP_TEXT = f"""可用子命令：
chess join <white|black>  加入白方或黑方（同方可多人，可重复加入另一方）
chess leave / resign      离开游戏；本方最后一人离开即认输
chess players             查看双方玩家
chess board               显示当前棋盘
chess move <走法>         走棋，如 e4 / Nf3 / e2e4
chess takeback            提议悔棋（需对方 chess agree）
chess draw                提议和棋（需对方 chess agree）
chess agree               同意对方的提议
chess mode [模板]         查看或切换棋盘模板
                          （可选：{" / ".join(board_templates.AVAILABLE_MODES)}）
chess help                显示本帮助

规则：一方可有多名玩家共同操作；只要该方还有人，对局继续。
该方最后一名玩家离开时判负，结束时的 PGN 会记录双方 QQ 号。"""


@chess.handle()
async def handle_chess(  # noqa: C901, PLR0912, PLR0915
    bot: Bot,  # noqa: ARG001
    event: GroupMessageEvent,
    arg: Message = CommandArg(),
) -> None:
    """棋类插件的唯一入口：按子命令分发。

    ``bot`` 由 NoneBot 依赖注入提供，本处理器只回复当前会话，因此不直接使用它。
    子命令分发天然是一个长分支链，拆成多函数反而会隐藏各分支的差异。
    """
    group_id = event.group_id
    user_id = str(event.user_id)
    # 获取子命令和参数
    args = arg.extract_plain_text().strip().split()
    if not args:
        await chess.finish("chess 已就绪。\n" + HELP_TEXT)

    subcmd = args[0].lower()
    params = args[1:]

    if subcmd in ("help", "h", "?"):
        await chess.finish(HELP_TEXT)

    # 棋盘模板切换不依赖对局，单独处理
    if subcmd in ("mode", "template", "format"):
        if not params:
            current = _mode_for(group_id)
            options = " / ".join(board_templates.AVAILABLE_MODES)
            await chess.finish(f"当前棋盘模板：{current}\n可选：{options}")
        requested = params[0].lower()
        if requested not in board_templates.AVAILABLE_MODES:
            options = " / ".join(board_templates.AVAILABLE_MODES)
            await chess.finish(f"未知模板 {requested}，可选：{options}")
        board_modes[group_id] = requested
        demo = board_templates.render(chess_lib.Board(), requested)
        await chess.finish(f"棋盘模板已切换为 {requested}\n{demo}")

    # 获取或创建游戏
    game = games.get(group_id)
    if subcmd not in ["join", "players", "board"]:
        if game is None:
            await chess.finish("当前群没有进行中的游戏，请先使用 chess join 加入")
        if game.game_over:
            # 游戏已结束，但我们可以保留游戏对象以便查看 PGN，但这里我们清理后重新开始
            # 如果游戏结束，可以自动清理并提示
            del games[group_id]
            game = None
            await chess.finish("上一局游戏已结束，请使用 chess join 开始新游戏")

    # 使用当前群选择的模板
    mode = _mode_for(group_id)

    # 处理子命令
    if subcmd == "join":
        if game is None:
            game = ChessGame(group_id)
            games[group_id] = game
        if len(params) == 0:
            await chess.finish("请指定 side: white 或 black")
        side = params[0].lower()
        if side not in ["white", "black"]:
            await chess.finish("side 必须是 white 或 black")
        if game.game_over:
            await chess.finish("游戏已经结束，请等待新游戏")
        # 同一名玩家不能重复加入同一方，但可以加入另一方
        if user_id in game.get_players_ordered(side):
            await chess.finish(f"你已经在该游戏的 {side} 方了")
        # 加入
        success = game.add_player(user_id, side)
        if not success:
            await chess.finish(f"加入 {side} 失败，可能已存在")
        side_cn = "白方" if side == "white" else "黑方"
        # 双方都有人即可开始；同方可有多人
        if game.white_players and game.black_players:
            board_str = game.get_board_str(mode)
            turn = "白方" if game.board.turn == chess_lib.WHITE else "黑方"
            await chess.send(
                f"{user_id} 加入 {side_cn}。双方准备就绪，游戏开始！\n"
                f"{game.get_players_info()}\n"
                f"{board_str}\n轮到 {turn} 走棋"
            )
        else:
            await chess.finish(
                f"{user_id} 已加入 {side_cn}"
                f"（当前 {len(game.get_players_ordered(side))} 人），等待对手加入"
            )

    elif subcmd in ("leave", "resign"):
        if game is None:
            await chess.finish("当前没有游戏")
        if not game.is_player(user_id):
            await chess.finish("你不在游戏中")
        # 移除玩家
        success, result = game.remove_player(user_id)
        if not success:
            await chess.finish("你不在游戏中")
        if result:
            # 该方最后一人离开，游戏结束，输出带 QQ 号的 PGN
            pgn = game.get_pgn()
            await chess.finish(
                f"{user_id} 离开，其所在方无人应战，判负（认输）\n"
                f"最终结果：{result}\n{game.get_players_info()}\nPGN:\n{pgn}"
            )
            # 清理
            del games[group_id]
        else:
            side_key = game.get_side(user_id)
            remaining = len(game.get_players_ordered(side_key))
            side = "白方" if side_key == "white" else "黑方"
            await chess.finish(
                f"{user_id} 已离开游戏（{side}还剩 {remaining} 人，对局继续）"
            )

    elif subcmd == "players":
        if game is None:
            await chess.finish("当前没有游戏")
        info = game.get_players_info()
        await chess.finish(info)

    elif subcmd == "board":
        if game is None:
            await chess.finish("当前没有游戏")
        board_str = game.get_board_str(mode)
        turn = "白方" if game.board.turn == chess_lib.WHITE else "黑方"
        await chess.finish(f"{board_str}\n轮到 {turn} 走棋")

    elif subcmd == "move":
        if game is None:
            await chess.finish("当前没有游戏")
        if len(params) == 0:
            await chess.finish("请提供走法，如 'e4' 或 'e2e4'")
        move_str = params[0]
        success, msg, result = game.make_move(user_id, move_str)
        if not success:
            await chess.finish(msg)
        # 走法成功，输出新棋盘
        board_str = game.get_board_str(mode)
        if result:
            # 游戏结束
            pgn = game.get_pgn()
            await chess.finish(
                f"{msg}\n{board_str}\n游戏结束！结果：{result}\nPGN:\n{pgn}"
            )
            del games[group_id]
        else:
            # 继续
            turn = "白方" if game.board.turn == chess_lib.WHITE else "黑方"
            await chess.finish(f"{msg}\n{board_str}\n轮到 {turn} 走棋")

    elif subcmd == "takeback":
        if game is None:
            await chess.finish("当前没有游戏")
        # 提议悔棋，只有游戏中的玩家可以提议
        if not game.is_player(user_id):
            await chess.finish("你不是该游戏的玩家")
        if game.propose_takeback(user_id):
            await chess.finish("已提议悔棋，等待对方同意（使用 chess agree）")
        else:
            await chess.finish("悔棋提议失败（可能没有走棋历史）")

    elif subcmd == "draw":
        if game is None:
            await chess.finish("当前没有游戏")
        if not game.is_player(user_id):
            await chess.finish("你不是该游戏的玩家")
        if game.propose_draw(user_id):
            await chess.finish("已提议和棋，等待对方同意（使用 chess agree）")
        else:
            await chess.finish("和棋提议失败")

    elif subcmd == "agree":
        if game is None:
            await chess.finish("当前没有游戏")
        if not game.is_player(user_id):
            await chess.finish("你不是该游戏的玩家")
        success, msg, result = game.agree(user_id)
        if not success:
            await chess.finish(msg)
        if result:
            # 游戏结束
            pgn = game.get_pgn()
            await chess.finish(f"{msg}\n最终结果：{result}\nPGN:\n{pgn}")
            del games[group_id]
        else:
            # 如果是悔棋成功，显示新棋盘
            board_str = game.get_board_str(mode)
            turn = "白方" if game.board.turn == chess_lib.WHITE else "黑方"
            await chess.finish(f"{msg}\n{board_str}\n轮到 {turn} 走棋")

    else:
        await chess.finish(f"未知子命令: {subcmd}")
