import chess
import chess.pgn
from typing import List, Optional, Tuple
from dataclasses import dataclass

from .board_render import render_board

@dataclass
class Proposal:
    """表示一个待同意的提议（悔棋或和棋）"""
    type: str          # "takeback" 或 "draw"
    proposer: str      # 提议者的 QQ 号或昵称

class ChessGame:
    def __init__(self, group_id: int):
        self.group_id = group_id
        self.board = chess.Board()
        # 玩家按加入顺序保存，便于在 PGN 中稳定输出 QQ 号
        self.white_players: List[str] = []
        self.black_players: List[str] = []
        self.move_history: List[str] = []      # 存储 SAN 格式的走法
        self.proposal: Optional[Proposal] = None
        self.game_over = False
        self.result = None   # "1-0", "0-1", "1/2-1/2"

    def _roster(self, side: str) -> List[str]:
        """返回某一方的玩家列表（按加入顺序）。"""
        return self.white_players if side == "white" else self.black_players

    def get_players_ordered(self, side: str) -> List[str]:
        """按加入顺序返回某一方的 QQ 号列表。"""
        return list(self._roster(side))

    def add_player(self, user_id: str, side: str) -> bool:
        """加入游戏，side: 'white' 或 'black'，返回是否成功加入。

        允许多名玩家加入同一方，也允许同一名玩家同时加入两方（便于自测）。
        """
        if self.game_over:
            return False
        roster = self._roster(side)
        if user_id in roster:
            return False
        roster.append(user_id)
        return True

    def remove_player(self, user_id: str) -> Tuple[bool, Optional[str]]:
        """移除玩家，返回 (是否移除成功, 如果导致游戏结束，返回结果)。

        只要该方还有队友，游戏就继续；只有**最后一名**玩家离开时，
        该方才按认输处理，此时的比分才是最终结果。
        """
        removed = False
        for roster in (self.white_players, self.black_players):
            if user_id in roster:
                roster.remove(user_id)
                removed = True
        if not removed:
            return False, None

        # 已经结束的对局不再改写结果
        if self.game_over:
            return True, None

        # 只有一方彻底没人时才算认输
        if not self.white_players:
            self.game_over = True
            self.result = "0-1"
            return True, self.result
        if not self.black_players:
            self.game_over = True
            self.result = "1-0"
            return True, self.result

        return True, None

    def make_move(self, user_id: str, move_str: str) -> Tuple[bool, str, Optional[str]]:
        """
        尝试走棋，返回 (成功, 信息, 如果导致游戏结束，返回结果)
        """
        if self.game_over:
            return False, "游戏已经结束", None

        # 判断当前轮到谁走
        turn = "white" if self.board.turn == chess.WHITE else "black"
        if turn == "white" and user_id not in self.white_players:
            return False, "现在轮到白方走棋，你不是白方玩家", None
        if turn == "black" and user_id not in self.black_players:
            return False, "现在轮到黑方走棋，你不是黑方玩家", None

        # 尝试解析走法：先尝试 SAN（如 "e4", "Nf3", "O-O"），再尝试 UCI（如 "e2e4"）
        move = None
        try:
            move = self.board.parse_san(move_str)
        except ValueError:
            try:
                move = self.board.parse_uci(move_str)
            except ValueError:
                return False, "无效的走法格式", None

        if move not in self.board.legal_moves:
            return False, "非法走法", None

        # 执行走法
        san = self.board.san(move)
        self.board.push(move)
        self.move_history.append(san)

        # 清除之前的提议（新的走法会使之前的提议失效）
        self.proposal = None

        # 检查游戏是否结束
        if self.board.is_checkmate():
            self.game_over = True
            self.result = "1-0" if self.board.turn == chess.BLACK else "0-1"  # 注意 turn 已经切换
            return True, f"将杀！{san}", self.result
        if self.board.is_stalemate():
            self.game_over = True
            self.result = "1/2-1/2"
            return True, f"逼和！{san}", self.result
        if self.board.is_insufficient_material():
            self.game_over = True
            self.result = "1/2-1/2"
            return True, f"子力不足，和棋！{san}", self.result
        if self.board.can_claim_draw():
            # 三次重复或五十回合规则，我们允许自动和棋
            self.game_over = True
            self.result = "1/2-1/2"
            return True, f"自动和棋（三次重复/五十回合）{san}", self.result

        return True, f"走法成功：{san}", None

    def propose_takeback(self, user_id: str) -> bool:
        """提议悔棋，覆盖之前的提议"""
        if self.game_over:
            return False
        if len(self.move_history) == 0:
            return False
        self.proposal = Proposal("takeback", user_id)
        return True

    def propose_draw(self, user_id: str) -> bool:
        """提议和棋，覆盖之前的提议"""
        if self.game_over:
            return False
        self.proposal = Proposal("draw", user_id)
        return True

    def agree(self, user_id: str) -> Tuple[bool, str, Optional[str]]:
        """
        同意当前的提议，返回 (成功, 信息, 如果游戏结束，结果)
        """
        if not self.proposal:
            return False, "当前没有待处理的提议", None
        if self.game_over:
            return False, "游戏已经结束", None

        if self.proposal.type == "takeback":
            if len(self.move_history) == 0:
                self.proposal = None
                return False, "没有可以悔的棋", None
            # 悔一步
            self.board.pop()
            self.move_history.pop()
            self.proposal = None
            # 游戏如果之前结束，现在可能重新开始（但此时游戏未结束）
            return True, "悔棋成功", None

        elif self.proposal.type == "draw":
            self.game_over = True
            self.result = "1/2-1/2"
            self.proposal = None
            return True, "和棋", self.result

        return False, "未知提议类型", None

    def get_board_str(self) -> str:
        """返回带 a-h / 1-8 坐标的 Unicode 棋盘字符串"""
        return render_board(self.board)

    def get_pgn(self) -> str:
        """生成完整的 PGN 字符串（包含最终结果与双方 QQ 号）"""
        game = chess.pgn.Game()
        node = game
        # 从初始棋盘重放走法，逐层挂到主线（mainline）上
        temp_board = chess.Board()
        for san in self.move_history:
            move = temp_board.parse_san(san)
            temp_board.push(move)
            node = node.add_main_variation(move)
        # 设置结果
        if self.result:
            game.headers["Result"] = self.result
        else:
            game.headers["Result"] = "*"
        # 添加其他头部
        game.headers["Event"] = "群聊对弈"
        game.headers["Site"] = f"群 {self.group_id}"
        # 双方 QQ 号（可能有多人），写入 PGN 便于赛后追溯
        game.headers["White"] = self.format_roster("white")
        game.headers["Black"] = self.format_roster("black")
        # 导出
        exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=False)
        return game.accept(exporter)

    def format_roster(self, side: str) -> str:
        """把某一方的 QQ 号列表格式化成 PGN 头部可用的字符串。"""
        players = self.get_players_ordered(side)
        return ", ".join(players) if players else "?"

    def get_players_info(self) -> str:
        """返回当前玩家列表"""
        white = "、".join(self.white_players) if self.white_players else "无"
        black = "、".join(self.black_players) if self.black_players else "无"
        return f"白方({len(self.white_players)}人): {white}\n黑方({len(self.black_players)}人): {black}"

    def is_player(self, user_id: str) -> bool:
        return user_id in self.white_players or user_id in self.black_players

    def get_side(self, user_id: str) -> Optional[str]:
        if user_id in self.white_players:
            return "white"
        if user_id in self.black_players:
            return "black"
        return None