import chess
import chess.pgn
import io
from typing import List, Set, Optional, Dict, Tuple
from dataclasses import dataclass, field

@dataclass
class Proposal:
    """表示一个待同意的提议（悔棋或和棋）"""
    type: str          # "takeback" 或 "draw"
    proposer: str      # 提议者的 QQ 号或昵称

class ChessGame:
    def __init__(self, group_id: int):
        self.group_id = group_id
        self.board = chess.Board()
        self.white_players: Set[str] = set()   # 存储用户 ID (str)
        self.black_players: Set[str] = set()
        self.move_history: List[str] = []      # 存储 SAN 格式的走法
        self.proposal: Optional[Proposal] = None
        self.game_over = False
        self.result = None   # "1-0", "0-1", "1/2-1/2"

    def add_player(self, user_id: str, side: str) -> bool:
        """加入游戏，side: 'white' 或 'black'，返回是否成功加入"""
        if self.game_over:
            return False
        if side == "white":
            if user_id in self.white_players:
                return False
            self.white_players.add(user_id)
        else:
            if user_id in self.black_players:
                return False
            self.black_players.add(user_id)
        return True

    def remove_player(self, user_id: str) -> Tuple[bool, Optional[str]]:
        """
        移除玩家，返回 (是否移除成功, 如果导致游戏结束，返回结果)
        """
        removed = False
        if user_id in self.white_players:
            self.white_players.remove(user_id)
            removed = True
        elif user_id in self.black_players:
            self.black_players.remove(user_id)
            removed = True
        if not removed:
            return False, None

        # 检查是否有一方无人，视为认输
        if not self.white_players and self.board.turn == chess.WHITE:
            # 白方无人，但轮到白方走，实际上如果游戏还未结束，白方无人即认输
            self.game_over = True
            self.result = "0-1"
            return True, self.result
        if not self.black_players and self.board.turn == chess.BLACK:
            self.game_over = True
            self.result = "1-0"
            return True, self.result

        # 也可能有一方无人但已经是另一方走完了？但通常认输是立即的
        # 更严谨：只要有一方玩家为空，且游戏还未结束，就判该方负
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
        """返回 Unicode 棋盘字符串"""
        return str(self.board)  # 默认就是 Unicode 字符

    def get_pgn(self) -> str:
        """生成完整的 PGN 字符串（包含最终结果）"""
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
        # 导出
        exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=False)
        return game.accept(exporter)

    def get_players_info(self) -> str:
        """返回当前玩家列表"""
        white = ", ".join(self.white_players) if self.white_players else "无"
        black = ", ".join(self.black_players) if self.black_players else "无"
        return f"白方: {white}\n黑方: {black}"

    def is_player(self, user_id: str) -> bool:
        return user_id in self.white_players or user_id in self.black_players

    def get_side(self, user_id: str) -> Optional[str]:
        if user_id in self.white_players:
            return "white"
        if user_id in self.black_players:
            return "black"
        return None