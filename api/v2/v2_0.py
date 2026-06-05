"""Python port of the current C# V2.0 engine for the Flask route."""

import math
import time
from dataclasses import dataclass

import chess


TIME_CHECK_INTERVAL = 1024
TT_SIZE_BITS = 18
MATE_SCORE = 1_000_000
MATE_SCORE_THRESHOLD = 999_000
DRAW_BASE_PENALTY = 120
THREEFOLD_REPETITION_PENALTY = 90
REPEAT_POSITION_PENALTY = 35
ENDGAME_NON_PAWN_MATERIAL_THRESHOLD = 1600
ENDGAME_MATERIAL_ADVANTAGE_THRESHOLD = 200
ENDGAME_MOP_UP_SCALE = 8
ENDGAME_KING_MOBILITY_SCALE = 12
ENDGAME_PAWN_DANGER_SCALE = 70
WINNING_ENDGAME_REPEAT_PENALTY = 1000
DELTA_PRUNING_MARGIN = 200
TT_MOVE_BONUS = 100_000
DEFAULT_TIME_LIMIT_SECONDS = 1.0

PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

BOUND_EXACT = "exact"
BOUND_LOWER = "lower"
BOUND_UPPER = "upper"


class SearchTimeout(Exception):
    pass


@dataclass(slots=True)
class EvalSnapshot:
    material_balance: int
    white_bishops: int
    black_bishops: int
    white_knights: int
    black_knights: int
    white_rooks: int
    black_rooks: int
    white_queens: int
    black_queens: int
    white_pawn_danger: int
    black_pawn_danger: int
    endgame_weight: float


@dataclass(slots=True)
class TranspositionEntry:
    key: object
    depth: int
    score: int
    bound: str
    best_move: chess.Move | None
    age: int


class TranspositionTable:
    def __init__(self, size_bits: int = TT_SIZE_BITS):
        self.mask = (1 << size_bits) - 1
        self.entries: list[TranspositionEntry | None] = [None] * (1 << size_bits)
        self.entry_count = 0

    def _index(self, key: object) -> int:
        return hash(key) & self.mask

    def probe(self, key: object) -> TranspositionEntry | None:
        entry = self.entries[self._index(key)]
        if entry is None or entry.key != key:
            return None
        return entry

    def store(
        self,
        key: object,
        depth: int,
        score: int,
        bound: str,
        best_move: chess.Move | None,
        age: int,
    ) -> None:
        index = self._index(key)
        existing = self.entries[index]
        if existing is not None and existing.key != key and depth < existing.depth and age <= existing.age:
            return

        if existing is None:
            self.entry_count += 1

        self.entries[index] = TranspositionEntry(
            key=key,
            depth=depth,
            score=score,
            bound=bound,
            best_move=best_move,
            age=age,
        )


def _position_key(board: chess.Board) -> object:
    if hasattr(board, "_transposition_key"):
        return board._transposition_key()
    return board.fen()


def _build_eval_snapshot(board: chess.Board) -> EvalSnapshot:
    white_material = 0
    black_material = 0
    white_non_pawn_material = 0
    black_non_pawn_material = 0
    white_bishops = 0
    black_bishops = 0
    white_knights = 0
    black_knights = 0
    white_rooks = 0
    black_rooks = 0
    white_queens = 0
    black_queens = 0
    white_pawn_danger = 0
    black_pawn_danger = 0

    for square, piece in board.piece_map().items():
        value = PIECE_VALUES[piece.piece_type]
        if piece.color == chess.WHITE:
            white_material += value
        else:
            black_material += value

        if piece.piece_type == chess.PAWN:
            if piece.color == chess.WHITE:
                white_pawn_danger += chess.square_rank(square)
            else:
                black_pawn_danger += 7 - chess.square_rank(square)
        elif piece.piece_type == chess.KNIGHT:
            if piece.color == chess.WHITE:
                white_knights += 1
                white_non_pawn_material += value
            else:
                black_knights += 1
                black_non_pawn_material += value
        elif piece.piece_type == chess.BISHOP:
            if piece.color == chess.WHITE:
                white_bishops += 1
                white_non_pawn_material += value
            else:
                black_bishops += 1
                black_non_pawn_material += value
        elif piece.piece_type == chess.ROOK:
            if piece.color == chess.WHITE:
                white_rooks += 1
                white_non_pawn_material += value
            else:
                black_rooks += 1
                black_non_pawn_material += value
        elif piece.piece_type == chess.QUEEN:
            if piece.color == chess.WHITE:
                white_queens += 1
                white_non_pawn_material += value
            else:
                black_queens += 1
                black_non_pawn_material += value

    total_non_pawn_material = white_non_pawn_material + black_non_pawn_material
    endgame_weight = 1.0 - (
        min(total_non_pawn_material, ENDGAME_NON_PAWN_MATERIAL_THRESHOLD)
        / ENDGAME_NON_PAWN_MATERIAL_THRESHOLD
    )
    return EvalSnapshot(
        material_balance=white_material - black_material,
        white_bishops=white_bishops,
        black_bishops=black_bishops,
        white_knights=white_knights,
        black_knights=black_knights,
        white_rooks=white_rooks,
        black_rooks=black_rooks,
        white_queens=white_queens,
        black_queens=black_queens,
        white_pawn_danger=white_pawn_danger,
        black_pawn_danger=black_pawn_danger,
        endgame_weight=max(0.0, min(1.0, endgame_weight)),
    )


def _manhattan_distance(first: int, second: int) -> int:
    return abs(chess.square_file(first) - chess.square_file(second)) + abs(
        chess.square_rank(first) - chess.square_rank(second)
    )


def _center_manhattan_distance(square: int) -> int:
    file_index = chess.square_file(square)
    rank_index = chess.square_rank(square)
    file_distance = min(abs(file_index - 3), abs(file_index - 4))
    rank_distance = min(abs(rank_index - 3), abs(rank_index - 4))
    return file_distance + rank_distance


def _has_forcing_mating_material(snapshot: EvalSnapshot, color: chess.Color) -> bool:
    if color == chess.WHITE:
        return (
            snapshot.white_queens > 0
            or snapshot.white_rooks > 0
            or snapshot.white_bishops >= 2
            or (snapshot.white_bishops >= 1 and snapshot.white_knights >= 1)
        )

    return (
        snapshot.black_queens > 0
        or snapshot.black_rooks > 0
        or snapshot.black_bishops >= 2
        or (snapshot.black_bishops >= 1 and snapshot.black_knights >= 1)
    )


def _force_king_to_corner_endgame_eval(board: chess.Board, stronger_side: chess.Color, weight: float) -> int:
    friendly_king = board.king(stronger_side)
    opponent_king = board.king(not stronger_side)
    if friendly_king is None or opponent_king is None:
        return 0

    losing_king_cmd = _center_manhattan_distance(opponent_king)
    kings_md = _manhattan_distance(friendly_king, opponent_king)
    raw_score = (4.7 * losing_king_cmd) + (1.6 * (14 - kings_md))
    return int(raw_score * ENDGAME_MOP_UP_SCALE * weight)


def _defender_king_mobility(board: chess.Board, losing_side: chess.Color) -> int:
    king = board.king(losing_side)
    if king is None:
        return 0

    mobility = 0
    for target in chess.SquareSet(chess.BB_KING_ATTACKS[king]):
        occupant = board.piece_at(target)
        if occupant is not None and occupant.color == losing_side:
            continue
        if not board.is_attacked_by(not losing_side, target):
            mobility += 1
    return mobility


def _is_repetition(board: chess.Board, count: int) -> bool:
    try:
        return board.is_repetition(count)
    except TypeError:
        return board.is_repetition() if count <= 3 else False


def _repetition_draw_adjustment(board: chess.Board) -> int:
    adjustment = 0
    if _is_repetition(board, 2):
        adjustment -= REPEAT_POSITION_PENALTY
    if _is_repetition(board, 3):
        adjustment -= THREEFOLD_REPETITION_PENALTY
    if board.halfmove_clock >= 100 or _is_repetition(board, 3):
        adjustment -= DRAW_BASE_PENALTY
    return adjustment


def _endgame_mop_up_adjustment(board: chess.Board, snapshot: EvalSnapshot) -> int:
    if snapshot.endgame_weight <= 0.0:
        return 0

    white_bonus = 0
    black_bonus = 0
    if (
        snapshot.material_balance >= ENDGAME_MATERIAL_ADVANTAGE_THRESHOLD
        and _has_forcing_mating_material(snapshot, chess.WHITE)
    ):
        white_bonus = _force_king_to_corner_endgame_eval(board, chess.WHITE, snapshot.endgame_weight)
        white_bonus += (8 - _defender_king_mobility(board, chess.BLACK)) * ENDGAME_KING_MOBILITY_SCALE
        white_bonus -= int(snapshot.black_pawn_danger * ENDGAME_PAWN_DANGER_SCALE * snapshot.endgame_weight)

    if (
        snapshot.material_balance <= -ENDGAME_MATERIAL_ADVANTAGE_THRESHOLD
        and _has_forcing_mating_material(snapshot, chess.BLACK)
    ):
        black_bonus = _force_king_to_corner_endgame_eval(board, chess.BLACK, snapshot.endgame_weight)
        black_bonus += (8 - _defender_king_mobility(board, chess.WHITE)) * ENDGAME_KING_MOBILITY_SCALE
        black_bonus -= int(snapshot.white_pawn_danger * ENDGAME_PAWN_DANGER_SCALE * snapshot.endgame_weight)

    score = white_bonus - black_bonus
    return score if board.turn == chess.WHITE else -score


def _winning_endgame_repetition_adjustment(board: chess.Board, material_balance: int, endgame_weight: float) -> int:
    material_edge = material_balance if board.turn == chess.WHITE else -material_balance
    if material_edge <= ENDGAME_MATERIAL_ADVANTAGE_THRESHOLD or endgame_weight <= 0.0:
        return 0

    adjustment = 0
    if _is_repetition(board, 2):
        adjustment -= WINNING_ENDGAME_REPEAT_PENALTY + (material_edge // 20)
    if _is_repetition(board, 3):
        adjustment -= WINNING_ENDGAME_REPEAT_PENALTY + (material_edge // 10)
    return adjustment


def evaluate_v2_0(board: chess.Board) -> int:
    snapshot = _build_eval_snapshot(board)
    material_score = snapshot.material_balance if board.turn == chess.WHITE else -snapshot.material_balance
    return (
        material_score
        + _repetition_draw_adjustment(board)
        + _endgame_mop_up_adjustment(board, snapshot)
        + _winning_endgame_repetition_adjustment(board, snapshot.material_balance, snapshot.endgame_weight)
    )


def _captured_piece_value(board: chess.Board, move: chess.Move) -> int:
    if board.is_en_passant(move):
        return PIECE_VALUES[chess.PAWN]
    captured_piece = board.piece_at(move.to_square)
    return PIECE_VALUES.get(captured_piece.piece_type, 0) if captured_piece else 0


def _promotion_piece_value(move: chess.Move) -> int:
    return PIECE_VALUES.get(move.promotion, 0) if move.promotion else 0


def _move_order_score(board: chess.Board, move: chess.Move, tt_move: chess.Move | None) -> int:
    score = 0
    moving_piece = board.piece_at(move.from_square)
    attacker_value = PIECE_VALUES.get(moving_piece.piece_type, 0) if moving_piece else 0

    if board.is_capture(move):
        score += 10_000 + (10 * _captured_piece_value(board, move)) - attacker_value

    if move.promotion:
        score += 8_000 + _promotion_piece_value(move)

    if tt_move is not None and move == tt_move:
        score += TT_MOVE_BONUS

    if moving_piece is not None and moving_piece.piece_type != chess.PAWN:
        if board.is_attacked_by(not board.turn, move.to_square):
            pawn_attackers = [
                square
                for square in board.attackers(not board.turn, move.to_square)
                if board.piece_type_at(square) == chess.PAWN
            ]
            if pawn_attackers:
                score -= attacker_value

    return score


def _ordered_search_moves(
    board: chess.Board,
    tt_move: chess.Move | None = None,
    captures_only: bool = False,
) -> list[chess.Move]:
    moves = list(board.generate_legal_captures()) if captures_only else list(board.legal_moves)
    return sorted(moves, key=lambda move: -_move_order_score(board, move, tt_move))


def _is_obviously_losing_capture(board: chess.Board, move: chess.Move) -> bool:
    moving_piece = board.piece_at(move.from_square)
    if moving_piece is None or move.promotion or not board.is_capture(move):
        return False
    return PIECE_VALUES[moving_piece.piece_type] > _captured_piece_value(board, move)


def _is_delta_pruned(board: chess.Board, move: chess.Move, stand_pat: int, alpha: int) -> bool:
    material_swing = _captured_piece_value(board, move)
    if move.promotion:
        material_swing += _promotion_piece_value(move) - PIECE_VALUES[chess.PAWN]
    return stand_pat + material_swing + DELTA_PRUNING_MARGIN < alpha


def _score_to_tt(score: int, ply: int) -> int:
    if score >= MATE_SCORE_THRESHOLD:
        return score + ply
    if score <= -MATE_SCORE_THRESHOLD:
        return score - ply
    return score


def _score_from_tt(score: int, ply: int) -> int:
    if score >= MATE_SCORE_THRESHOLD:
        return score - ply
    if score <= -MATE_SCORE_THRESHOLD:
        return score + ply
    return score


def search_move_v2_0(
    board: chess.Board,
    time_limit_seconds: float = DEFAULT_TIME_LIMIT_SECONDS,
    max_depth: int | None = None,
) -> dict:
    if time_limit_seconds <= 0:
        raise ValueError("time_limit_seconds must be greater than 0")

    deadline = time.perf_counter() + time_limit_seconds
    transposition_table = TranspositionTable()
    current_iteration_depth = 0
    moves_evaluated = 0
    nodes_searched = 0
    tt_probes = 0
    tt_hits = 0
    tt_cutoffs = 0

    def check_time() -> None:
        if time.perf_counter() >= deadline:
            raise SearchTimeout

    def visit_node() -> None:
        nonlocal nodes_searched
        nodes_searched += 1
        if (nodes_searched & (TIME_CHECK_INTERVAL - 1)) == 0:
            check_time()

    def terminal_score(search_board: chess.Board, ply: int) -> int:
        if search_board.is_checkmate():
            return -MATE_SCORE + ply
        return evaluate_v2_0(search_board)

    def quiescence(alpha: int, beta: int, search_board: chess.Board, ply: int) -> int:
        nonlocal moves_evaluated

        visit_node()
        in_check = search_board.is_check()
        moves = _ordered_search_moves(search_board, captures_only=not in_check)
        if not moves:
            return -MATE_SCORE + ply if in_check else evaluate_v2_0(search_board)

        stand_pat = evaluate_v2_0(search_board)
        if not in_check:
            if stand_pat >= beta:
                return beta
            alpha = max(alpha, stand_pat)

        for move in moves:
            if not in_check:
                if _is_obviously_losing_capture(search_board, move):
                    continue
                if _is_delta_pruned(search_board, move, stand_pat, alpha):
                    continue

            search_board.push(move)
            try:
                moves_evaluated += 1
                move_eval = -quiescence(-beta, -alpha, search_board, ply + 1)
            finally:
                search_board.pop()

            if move_eval >= beta:
                return beta
            alpha = max(alpha, move_eval)

        return alpha

    def negamax(remaining_depth: int, alpha: int, beta: int, search_board: chess.Board, ply: int) -> int:
        nonlocal moves_evaluated
        nonlocal tt_probes
        nonlocal tt_hits
        nonlocal tt_cutoffs

        visit_node()
        alpha = max(alpha, -MATE_SCORE + ply)
        beta = min(beta, MATE_SCORE - ply)
        if alpha >= beta:
            return alpha

        if remaining_depth == 0:
            return quiescence(alpha, beta, search_board, ply)

        alpha_original = alpha
        key = _position_key(search_board)
        tt_probes += 1
        entry = transposition_table.probe(key)
        if entry is not None:
            tt_hits += 1
            if entry.depth >= remaining_depth:
                tt_score = _score_from_tt(entry.score, ply)
                if entry.bound == BOUND_EXACT:
                    tt_cutoffs += 1
                    return tt_score
                if entry.bound == BOUND_LOWER and tt_score >= beta:
                    tt_cutoffs += 1
                    return tt_score
                if entry.bound == BOUND_UPPER and tt_score <= alpha:
                    tt_cutoffs += 1
                    return tt_score

        tt_move = entry.best_move if entry is not None else None
        moves = _ordered_search_moves(search_board, tt_move=tt_move)
        if not moves:
            return -MATE_SCORE + ply if search_board.is_check() else evaluate_v2_0(search_board)

        best_move = tt_move
        best_score = -math.inf
        for move in moves:
            search_board.push(move)
            try:
                moves_evaluated += 1
                move_eval = -negamax(remaining_depth - 1, -beta, -alpha, search_board, ply + 1)
            finally:
                search_board.pop()

            if move_eval > best_score:
                best_score = move_eval
                best_move = move

            alpha = max(alpha, move_eval)
            if alpha >= beta:
                break

        bound = BOUND_UPPER if best_score <= alpha_original else BOUND_LOWER if best_score >= beta else BOUND_EXACT
        transposition_table.store(
            key,
            remaining_depth,
            _score_to_tt(best_score, ply),
            bound,
            best_move,
            current_iteration_depth,
        )
        return best_score

    fallback_moves = _ordered_search_moves(board)
    if not fallback_moves:
        raise ValueError("No legal moves available for v2.0 search")

    best_move = fallback_moves[0]
    best_eval = -math.inf
    completed_depth = 0
    timed_out = False
    depth = 1

    while max_depth is None or depth <= max_depth:
        current_iteration_depth = depth
        iteration_best_move: chess.Move | None = None
        iteration_best_eval = -math.inf

        try:
            tt_probes += 1
            root_key = _position_key(board)
            root_entry = transposition_table.probe(root_key)
            if root_entry is not None:
                tt_hits += 1
            root_tt_move = root_entry.best_move if root_entry is not None else None

            for move in _ordered_search_moves(board, tt_move=root_tt_move):
                check_time()
                board.push(move)
                try:
                    moves_evaluated += 1
                    move_eval = -negamax(depth - 1, -math.inf, math.inf, board, 1)
                finally:
                    board.pop()

                if iteration_best_move is None or move_eval > iteration_best_eval:
                    iteration_best_eval = move_eval
                    iteration_best_move = move

            if iteration_best_move is None:
                break

            best_move = iteration_best_move
            best_eval = iteration_best_eval
            completed_depth = depth
            transposition_table.store(
                root_key,
                depth,
                _score_to_tt(best_eval, 0),
                BOUND_EXACT,
                best_move,
                current_iteration_depth,
            )
        except SearchTimeout:
            timed_out = True
            if completed_depth == 0 and iteration_best_move is not None:
                best_move = iteration_best_move
                best_eval = iteration_best_eval
            break

        depth += 1

    return {
        "move": best_move,
        "move_san": board.san(best_move),
        "score": best_eval,
        "moves_evaluated": moves_evaluated,
        "nodes_searched": nodes_searched,
        "completed_depth": completed_depth,
        "time_limit_seconds": time_limit_seconds,
        "timed_out": timed_out,
        "tt_entries": transposition_table.entry_count,
        "tt_probes": tt_probes,
        "tt_hits": tt_hits,
        "tt_cutoffs": tt_cutoffs,
    }


def choose_move_v2_0(board: chess.Board, time_limit_seconds: float = DEFAULT_TIME_LIMIT_SECONDS) -> dict:
    result = search_move_v2_0(board, time_limit_seconds=time_limit_seconds)
    return {
        "move": result["move_san"],
        "moves_evaluated": result["moves_evaluated"],
        "nodes_searched": result["nodes_searched"],
        "completed_depth": result["completed_depth"],
    }


# Running `v2_0.py` against the preliminary 4 scenarios...
"""
=== python v2.0 puzzle_1 at time_limit=1.000s ===
Start FEN: 8/8/6kp/3b4/1p1p4/1P1P3P/PK2N3/8 w - - 0 2
White 1: Nf4+ (e2f4) | expected=Nf4+ | match=True | score=420 | positions=37888 | elapsed=1.014078s
White 1 detail: completed_depth=5 | timed_out=True | tt_entries=4042 | tt_probes=7017 | tt_hits=2922 | tt_cutoffs=1544 | moves_evaluated=24252 | nodes_searched=37888
Black forced: Kg7 (g6g7)
White 2: Nxd5 (f4d5) | expected=Nxd5 | match=True | score=520 | positions=39362 | elapsed=1.001093s
White 2 detail: completed_depth=5 | timed_out=True | tt_entries=3407 | tt_probes=6607 | tt_hits=3155 | tt_cutoffs=1240 | moves_evaluated=24584 | nodes_searched=39362
White total: positions=77250

=== python v2.0 puzzle_2 self-play at time_limit=1.000s ===
Start FEN: 3k4/8/3p4/p2P1p2/P2P1P2/8/3K4/8 w - - 10 6
Start turn: white | max_plies=70
White 1: Kc3 (d2c3) | expected=Kc3 | match=True | score=200 | positions=48128 | elapsed=1.011481s
White 1 detail: completed_depth=16 | timed_out=True | tt_entries=2177 | tt_probes=32573 | tt_hits=30345 | tt_cutoffs=18649 | moves_evaluated=40654 | nodes_searched=48128
Ply 2: black to move | legal_moves=5 | time_limit=1.000s | search started
Ply 2: Kc7 (d8c7) | score=-200 | positions=49152 | elapsed=1.018672s
Ply 2 detail: completed_depth=15 | timed_out=True | tt_entries=3410 | tt_probes=29187 | tt_hits=25700 | tt_cutoffs=16163 | moves_evaluated=39653 | nodes_searched=49152
Ply 3: white to move | legal_moves=6 | time_limit=1.000s | search started
Ply 3: Kd3 (c3d3) | score=200 | positions=47070 | elapsed=1.001799s
Ply 3 detail: completed_depth=17 | timed_out=True | tt_entries=1919 | tt_probes=32775 | tt_hits=30817 | tt_cutoffs=18483 | moves_evaluated=40231 | nodes_searched=47070
Ply 4: black to move | legal_moves=6 | time_limit=1.000s | search started
Ply 4: Kb7 (c7b7) | score=-200 | positions=49152 | elapsed=1.007762s
Ply 4 detail: completed_depth=15 | timed_out=True | tt_entries=3241 | tt_probes=29411 | tt_hits=26126 | tt_cutoffs=16347 | moves_evaluated=39663 | nodes_searched=49152
Ply 5: white to move | legal_moves=6 | time_limit=1.000s | search started
Ply 5: Ke3 (d3e3) | score=200 | positions=47104 | elapsed=1.002345s
Ply 5 detail: completed_depth=17 | timed_out=True | tt_entries=2287 | tt_probes=33408 | tt_hits=31083 | tt_cutoffs=18798 | moves_evaluated=40611 | nodes_searched=47104
Ply 6: black to move | legal_moves=7 | time_limit=1.000s | search started
Ply 6: Kc8 (b7c8) | score=-200 | positions=52224 | elapsed=1.014308s
Ply 6 detail: completed_depth=19 | timed_out=True | tt_entries=3072 | tt_probes=33704 | tt_hits=30474 | tt_cutoffs=19113 | moves_evaluated=43424 | nodes_searched=52224
Ply 7: white to move | legal_moves=5 | time_limit=1.000s | search started
Ply 7: Kf3 (e3f3) | score=200 | positions=49152 | elapsed=1.003949s
Ply 7 detail: completed_depth=16 | timed_out=True | tt_entries=1828 | tt_probes=35185 | tt_hits=33328 | tt_cutoffs=20364 | moves_evaluated=42378 | nodes_searched=49152
Ply 8: black to move | legal_moves=5 | time_limit=1.000s | search started
Ply 8: Kd8 (c8d8) | score=-200 | positions=52224 | elapsed=1.015272s
Ply 8 detail: completed_depth=17 | timed_out=True | tt_entries=3318 | tt_probes=32216 | tt_hits=28636 | tt_cutoffs=17930 | moves_evaluated=42687 | nodes_searched=52224
Ply 9: white to move | legal_moves=5 | time_limit=1.000s | search started
Ply 9: Kg3 (f3g3) | score=200 | positions=49152 | elapsed=1.016876s
Ply 9 detail: completed_depth=16 | timed_out=True | tt_entries=2270 | tt_probes=32548 | tt_hits=30166 | tt_cutoffs=18043 | moves_evaluated=41209 | nodes_searched=49152
Ply 10: black to move | legal_moves=5 | time_limit=1.000s | search started
Ply 10: Ke7 (d8e7) | score=-200 | positions=49152 | elapsed=1.002768s
Ply 10 detail: completed_depth=16 | timed_out=True | tt_entries=3382 | tt_probes=29612 | tt_hits=25935 | tt_cutoffs=15867 | moves_evaluated=39952 | nodes_searched=49152
Ply 11: white to move | legal_moves=6 | time_limit=1.000s | search started
Ply 11: Kh4 (g3h4) | score=200 | positions=45056 | elapsed=1.007636s
Ply 11 detail: completed_depth=16 | timed_out=True | tt_entries=3012 | tt_probes=25973 | tt_hits=22899 | tt_cutoffs=13469 | moves_evaluated=36014 | nodes_searched=45056
Ply 12: black to move | legal_moves=6 | time_limit=1.000s | search started
Ply 12: Kf6 (e7f6) | score=-200 | positions=45056 | elapsed=1.005809s
Ply 12 detail: completed_depth=15 | timed_out=True | tt_entries=3949 | tt_probes=24882 | tt_hits=20828 | tt_cutoffs=12449 | moves_evaluated=35636 | nodes_searched=45056
Ply 13: white to move | legal_moves=3 | time_limit=1.000s | search started
Ply 13: Kh5 (h4h5) | score=200 | positions=45056 | elapsed=1.019059s
Ply 13 detail: completed_depth=15 | timed_out=True | tt_entries=4200 | tt_probes=24325 | tt_hits=19978 | tt_cutoffs=11838 | moves_evaluated=35355 | nodes_searched=45056
Ply 14: black to move | legal_moves=3 | time_limit=1.000s | search started
Ply 14: Kg7 (f6g7) | score=-200 | positions=46080 | elapsed=1.006393s
Ply 14 detail: completed_depth=15 | timed_out=True | tt_entries=4710 | tt_probes=22234 | tt_hits=17415 | tt_cutoffs=10584 | moves_evaluated=34939 | nodes_searched=46080
Ply 15: white to move | legal_moves=2 | time_limit=1.000s | search started
Ply 15: Kg5 (h5g5) | score=200 | positions=47104 | elapsed=1.006902s
Ply 15 detail: completed_depth=14 | timed_out=True | tt_entries=4606 | tt_probes=23004 | tt_hits=18286 | tt_cutoffs=10677 | moves_evaluated=35860 | nodes_searched=47104
Ply 16: black to move | legal_moves=5 | time_limit=1.000s | search started
Ply 16: Kf7 (g7f7) | score=-200 | positions=48128 | elapsed=1.003838s
Ply 16 detail: completed_depth=13 | timed_out=True | tt_entries=4826 | tt_probes=20548 | tt_hits=15623 | tt_cutoffs=9525 | moves_evaluated=35226 | nodes_searched=48128
Ply 17: white to move | legal_moves=4 | time_limit=1.000s | search started
Ply 17: Kxf5 (g5f5) | score=200 | positions=50176 | elapsed=1.018500s
Ply 17 detail: completed_depth=12 | timed_out=True | tt_entries=4720 | tt_probes=19162 | tt_hits=14354 | tt_cutoffs=8624 | moves_evaluated=35543 | nodes_searched=50176
Ply 18: black to move | legal_moves=5 | time_limit=1.000s | search started
Ply 18: Kg7 (f7g7) | score=-200 | positions=48128 | elapsed=1.017714s
Ply 18 detail: completed_depth=11 | timed_out=True | tt_entries=3988 | tt_probes=19931 | tt_hits=15819 | tt_cutoffs=9600 | moves_evaluated=34902 | nodes_searched=48128
Ply 19: white to move | legal_moves=4 | time_limit=1.000s | search started
Ply 19: Ke6 (f5e6) | score=200 | positions=48128 | elapsed=1.009159s
Ply 19 detail: completed_depth=10 | timed_out=True | tt_entries=4770 | tt_probes=17917 | tt_hits=13048 | tt_cutoffs=8449 | moves_evaluated=33853 | nodes_searched=48128
Ply 20: black to move | legal_moves=6 | time_limit=1.000s | search started
Ply 20: Kg8 (g7g8) | score=-994 | positions=48128 | elapsed=1.018423s
Ply 20 detail: completed_depth=10 | timed_out=True | tt_entries=4326 | tt_probes=17390 | tt_hits=12962 | tt_cutoffs=8242 | moves_evaluated=33695 | nodes_searched=48128
Ply 21: white to move | legal_moves=6 | time_limit=1.000s | search started
Ply 21: Kxd6 (e6d6) | score=994 | positions=46080 | elapsed=1.011888s
Ply 21 detail: completed_depth=9 | timed_out=True | tt_entries=4258 | tt_probes=21525 | tt_hits=17144 | tt_cutoffs=10771 | moves_evaluated=34439 | nodes_searched=46080
Ply 22: black to move | legal_moves=5 | time_limit=1.000s | search started
Ply 22: Kf7 (g8f7) | score=-981 | positions=48128 | elapsed=1.002990s
Ply 22 detail: completed_depth=9 | timed_out=True | tt_entries=3676 | tt_probes=20834 | tt_hits=17046 | tt_cutoffs=10775 | moves_evaluated=35149 | nodes_searched=48128
Ply 23: white to move | legal_moves=6 | time_limit=1.000s | search started
Ply 23: Kc7 (d6c7) | score=981 | positions=45984 | elapsed=1.010834s
Ply 23 detail: completed_depth=8 | timed_out=True | tt_entries=3730 | tt_probes=16949 | tt_hits=13132 | tt_cutoffs=8105 | moves_evaluated=32371 | nodes_searched=45984
Ply 24: black to move | legal_moves=7 | time_limit=1.000s | search started
Ply 24: Ke7 (f7e7) | score=-1145 | positions=45056 | elapsed=1.015907s
Ply 24 detail: completed_depth=9 | timed_out=True | tt_entries=3856 | tt_probes=20088 | tt_hits=16132 | tt_cutoffs=10341 | moves_evaluated=33117 | nodes_searched=45056
Ply 25: white to move | legal_moves=7 | time_limit=1.000s | search started
Ply 25: d6+ (d5d6) | score=1145 | positions=47104 | elapsed=1.014236s
Ply 25 detail: completed_depth=8 | timed_out=True | tt_entries=4147 | tt_probes=14315 | tt_hits=10078 | tt_cutoffs=5880 | moves_evaluated=31729 | nodes_searched=47104
Ply 26: black to move | legal_moves=5 | time_limit=1.000s | search started
Ply 26: Ke6 (e7e6) | score=-1145 | positions=45056 | elapsed=1.027351s
Ply 26 detail: completed_depth=7 | timed_out=True | tt_entries=2614 | tt_probes=8901 | tt_hits=6247 | tt_cutoffs=3217 | moves_evaluated=28137 | nodes_searched=45056
Ply 27: white to move | legal_moves=9 | time_limit=1.000s | search started
Ply 27: d7 (d6d7) | score=1169 | positions=37888 | elapsed=1.011012s
Ply 27 detail: completed_depth=7 | timed_out=True | tt_entries=4695 | tt_probes=9100 | tt_hits=4340 | tt_cutoffs=2370 | moves_evaluated=24798 | nodes_searched=37888
Ply 28: black to move | legal_moves=5 | time_limit=1.000s | search started
Ply 28: Kd5 (e6d5) | score=-1169 | positions=36864 | elapsed=1.018517s
Ply 28 detail: completed_depth=6 | timed_out=True | tt_entries=3552 | tt_probes=6707 | tt_hits=3109 | tt_cutoffs=1723 | moves_evaluated=23019 | nodes_searched=36864
Ply 29: white to move | legal_moves=10 | time_limit=1.000s | search started
Ply 29: d8=Q+ (d7d8q) | score=1272 | positions=33792 | elapsed=1.011234s
Ply 29 detail: completed_depth=6 | timed_out=True | tt_entries=3271 | tt_probes=5615 | tt_hits=2291 | tt_cutoffs=1245 | moves_evaluated=21097 | nodes_searched=33792
Ply 30: black to move | legal_moves=3 | time_limit=1.000s | search started
Ply 30: Kc4 (d5c4) | score=-1272 | positions=34816 | elapsed=1.013005s
Ply 30 detail: completed_depth=5 | timed_out=True | tt_entries=1972 | tt_probes=3833 | tt_hits=1832 | tt_cutoffs=1044 | moves_evaluated=20816 | nodes_searched=34816
Ply 31: white to move | legal_moves=23 | time_limit=1.000s | search started
Ply 31: Kb6 (c7b6) | score=1272 | positions=32566 | elapsed=1.019808s
Ply 31 detail: completed_depth=4 | timed_out=True | tt_entries=1553 | tt_probes=3087 | tt_hits=1514 | tt_cutoffs=778 | moves_evaluated=19697 | nodes_searched=32566
Ply 32: black to move | legal_moves=4 | time_limit=1.000s | search started
Ply 32: Kc3 (c4c3) | score=-1308 | positions=31744 | elapsed=1.019927s
Ply 32 detail: completed_depth=5 | timed_out=True | tt_entries=1874 | tt_probes=3877 | tt_hits=1982 | tt_cutoffs=1225 | moves_evaluated=19787 | nodes_searched=31744
Ply 33: white to move | legal_moves=25 | time_limit=1.000s | search started
Ply 33: Qd6 (d8d6) | score=1299 | positions=30720 | elapsed=1.011206s
Ply 33 detail: completed_depth=4 | timed_out=True | tt_entries=1464 | tt_probes=2778 | tt_hits=1299 | tt_cutoffs=603 | moves_evaluated=19036 | nodes_searched=30720
Ply 34: black to move | legal_moves=6 | time_limit=1.000s | search started
Ply 34: Kc4 (c3c4) | score=-1313 | positions=31744 | elapsed=1.009423s
Ply 34 detail: completed_depth=5 | timed_out=True | tt_entries=2549 | tt_probes=5226 | tt_hits=2621 | tt_cutoffs=1802 | moves_evaluated=20269 | nodes_searched=31744
Ply 35: white to move | legal_moves=24 | time_limit=1.000s | search started
Ply 35: Qe5 (d6e5) | score=1313 | positions=30720 | elapsed=1.024442s
Ply 35 detail: completed_depth=4 | timed_out=True | tt_entries=1328 | tt_probes=2557 | tt_hits=1201 | tt_cutoffs=558 | moves_evaluated=19040 | nodes_searched=30720
Ply 36: black to move | legal_moves=4 | time_limit=1.000s | search started
Ply 36: Kb4 (c4b4) | score=-1329 | positions=33339 | elapsed=1.005122s
Ply 36 detail: completed_depth=5 | timed_out=True | tt_entries=2153 | tt_probes=4548 | tt_hits=2330 | tt_cutoffs=1477 | moves_evaluated=20479 | nodes_searched=33339
Ply 37: white to move | legal_moves=27 | time_limit=1.000s | search started
Ply 37: Qe4 (e5e4) | score=1329 | positions=32768 | elapsed=1.020908s
Ply 37 detail: completed_depth=4 | timed_out=True | tt_entries=1200 | tt_probes=2686 | tt_hits=1449 | tt_cutoffs=659 | moves_evaluated=19595 | nodes_searched=32768
Ply 38: black to move | legal_moves=5 | time_limit=1.000s | search started
Ply 38: Kxa4 (b4a4) | score=-1329 | positions=36864 | elapsed=1.021087s
Ply 38 detail: completed_depth=5 | timed_out=True | tt_entries=2314 | tt_probes=5746 | tt_hits=3304 | tt_cutoffs=2283 | moves_evaluated=22985 | nodes_searched=36864
Ply 39: white to move | legal_moves=28 | time_limit=1.000s | search started
Ply 39: Qb1 (e4b1) | score=1329 | positions=32768 | elapsed=1.017280s
Ply 39 detail: completed_depth=4 | timed_out=True | tt_entries=1168 | tt_probes=2399 | tt_hits=1190 | tt_cutoffs=566 | moves_evaluated=19495 | nodes_searched=32768
Ply 40: black to move | legal_moves=1 | time_limit=1.000s | search started
Ply 40: Ka3 (a4a3) | score=-1333 | positions=35840 | elapsed=1.024803s
Ply 40 detail: completed_depth=6 | timed_out=True | tt_entries=3380 | tt_probes=8223 | tt_hits=4552 | tt_cutoffs=3513 | moves_evaluated=23283 | nodes_searched=35840
Ply 41: white to move | legal_moves=28 | time_limit=1.000s | search started
Ply 41: Kb5 (b6b5) | score=1333 | positions=34420 | elapsed=1.017517s
Ply 41 detail: completed_depth=4 | timed_out=True | tt_entries=1170 | tt_probes=2526 | tt_hits=1153 | tt_cutoffs=418 | moves_evaluated=20236 | nodes_searched=34420
Ply 42: black to move | legal_moves=1 | time_limit=1.000s | search started
Ply 42: a4 (a5a4) | score=-1361 | positions=57344 | elapsed=1.002105s
Ply 42 detail: completed_depth=7 | timed_out=True | tt_entries=3695 | tt_probes=11034 | tt_hits=6810 | tt_cutoffs=4406 | moves_evaluated=49646 | nodes_searched=57344
Ply 43: white to move | legal_moves=25 | time_limit=1.000s | search started
Ply 43: Qb4+ (b1b4) | score=1361 | positions=34816 | elapsed=1.024897s
Ply 43 detail: completed_depth=5 | timed_out=True | tt_entries=2735 | tt_probes=7376 | tt_hits=4361 | tt_cutoffs=3041 | moves_evaluated=22809 | nodes_searched=34816
Ply 44: black to move | legal_moves=1 | time_limit=1.000s | search started
Ply 44: Ka2 (a3a2) | score=-999994 | positions=93184 | elapsed=1.003457s
Ply 44 detail: completed_depth=15 | timed_out=True | tt_entries=785 | tt_probes=10222 | tt_hits=9226 | tt_cutoffs=1558 | moves_evaluated=91830 | nodes_searched=93184
Ply 45: white to move | legal_moves=23 | time_limit=1.000s | search started
Ply 45: Kxa4 (b5a4) | score=1361 | positions=34816 | elapsed=1.003192s
Ply 45 detail: completed_depth=4 | timed_out=True | tt_entries=1255 | tt_probes=2461 | tt_hits=1172 | tt_cutoffs=418 | moves_evaluated=20383 | nodes_searched=34816
Ply 46: black to move | legal_moves=1 | time_limit=1.000s | search started
Ply 46: Ka1 (a2a1) | score=-999996 | positions=105277 | elapsed=1.000213s
Ply 46 detail: completed_depth=209 | timed_out=True | tt_entries=44 | tt_probes=9710 | tt_hits=9047 | tt_cutoffs=0 | moves_evaluated=104819 | nodes_searched=105277
Ply 47: white to move | legal_moves=23 | time_limit=1.000s | search started
Ply 47: Kb3 (a4b3) | score=999997 | positions=39936 | elapsed=1.023174s
Ply 47 detail: completed_depth=6 | timed_out=True | tt_entries=2985 | tt_probes=9158 | tt_hits=5846 | tt_cutoffs=4444 | moves_evaluated=25947 | nodes_searched=39936
Ply 48: black to move | legal_moves=1 | time_limit=1.000s | search started
Ply 48: Kb1 (a1b1) | score=-999998 | positions=110105 | elapsed=1.000038s
Ply 48 detail: completed_depth=5005 | timed_out=True | tt_entries=2 | tt_probes=15013 | tt_hits=10008 | tt_cutoffs=0 | moves_evaluated=110089 | nodes_searched=110105
Ply 49: white to move | legal_moves=21 | time_limit=1.000s | search started
Ply 49: Qe1# (b4e1) | score=999999 | positions=55296 | elapsed=1.008979s
Ply 49 detail: completed_depth=6 | timed_out=True | tt_entries=2651 | tt_probes=9258 | tt_hits=6335 | tt_cutoffs=4330 | moves_evaluated=43332 | nodes_searched=55296

Final FEN: 8/8/8/8/3P1P2/1K6/8/1k2Q3 b - - 4 30
Total positions: 2278585
Outcome: checkmate
Winner: white
Repetition detected: False
White delivered mate within ply limit: True

=== python v2.0 endgame_1 self-play at time_limit=1.000s ===
Start FEN: 3r4/3r4/3k4/8/3K4/8/8/8 b - - 1 1
Start turn: black | max_plies=60
Ply 1: black to move | legal_moves=18 | time_limit=1.000s | search started
Ply 1: Ke6+ (d6e6) | score=1134 | positions=43008 | elapsed=1.008886s
Ply 1 detail: completed_depth=4 | timed_out=True | tt_entries=1561 | tt_probes=2694 | tt_hits=1104 | tt_cutoffs=490 | moves_evaluated=24571 | nodes_searched=43008
Ply 2: white to move | legal_moves=5 | time_limit=1.000s | search started
Ply 2: Ke3 (d4e3) | score=-1150 | positions=41984 | elapsed=1.006880s
Ply 2 detail: completed_depth=5 | timed_out=True | tt_entries=2669 | tt_probes=4767 | tt_hits=2044 | tt_cutoffs=1271 | moves_evaluated=24550 | nodes_searched=41984
Ply 3: black to move | legal_moves=27 | time_limit=1.000s | search started
Ply 3: Kf5 (e6f5) | score=1150 | positions=41984 | elapsed=1.007826s
Ply 3 detail: completed_depth=4 | timed_out=True | tt_entries=1838 | tt_probes=3132 | tt_hits=1254 | tt_cutoffs=551 | moves_evaluated=24101 | nodes_searched=41984
Ply 4: white to move | legal_moves=3 | time_limit=1.000s | search started
Ply 4: Kf2 (e3f2) | score=-999994 | positions=92160 | elapsed=1.002844s
Ply 4 detail: completed_depth=7 | timed_out=True | tt_entries=2263 | tt_probes=9377 | tt_hits=6953 | tt_cutoffs=2505 | moves_evaluated=88196 | nodes_searched=92160
Ply 5: black to move | legal_moves=28 | time_limit=1.000s | search started
Ply 5: Rd2+ (d7d2) | score=1179 | positions=41838 | elapsed=1.009985s
Ply 5 detail: completed_depth=4 | timed_out=True | tt_entries=2516 | tt_probes=3943 | tt_hits=1389 | tt_cutoffs=676 | moves_evaluated=24461 | nodes_searched=41838
Ply 6: white to move | legal_moves=6 | time_limit=1.000s | search started
Ply 6: Kg3 (f2g3) | score=-999996 | positions=108544 | elapsed=1.002177s
Ply 6 detail: completed_depth=32 | timed_out=True | tt_entries=245 | tt_probes=8094 | tt_hits=7676 | tt_cutoffs=654 | moves_evaluated=107417 | nodes_searched=108544
Ply 7: black to move | legal_moves=31 | time_limit=1.000s | search started
Ply 7: R8d3+ (d8d3) | score=999997 | positions=46080 | elapsed=1.003739s
Ply 7 detail: completed_depth=4 | timed_out=True | tt_entries=1791 | tt_probes=3066 | tt_hits=1218 | tt_cutoffs=340 | moves_evaluated=28992 | nodes_searched=46080
Ply 8: white to move | legal_moves=1 | time_limit=1.000s | search started
Ply 8: Kh4 (g3h4) | score=-999998 | positions=105485 | elapsed=1.000071s
Ply 8 detail: completed_depth=3907 | timed_out=True | tt_entries=2 | tt_probes=11719 | tt_hits=7812 | tt_cutoffs=0 | moves_evaluated=105465 | nodes_searched=105485
Ply 9: black to move | legal_moves=26 | time_limit=1.000s | search started
Ply 9: Rh2# (d2h2) | score=999999 | positions=54272 | elapsed=1.005169s
Ply 9 detail: completed_depth=6 | timed_out=True | tt_entries=3215 | tt_probes=6402 | tt_hits=3065 | tt_cutoffs=1472 | moves_evaluated=38116 | nodes_searched=54272

Final FEN: 8/8/8/5k2/7K/3r4/7r/8 w - - 10 6
Total positions: 575355
Outcome: checkmate
Winner: black
Repetition detected: False
Black delivered mate within ply limit: True

=== python v2.0 endgame_2 self-play at time_limit=1.000s ===
Start FEN: 3r4/8/3k4/8/3K4/8/8/8 b - - 1 1
Start turn: black | max_plies=60
Ply 1: black to move | legal_moves=13 | time_limit=1.000s | search started
Ply 1: Re8 (d8e8) | score=691 | positions=44032 | elapsed=1.003204s
Ply 1 detail: completed_depth=5 | timed_out=True | tt_entries=2949 | tt_probes=6361 | tt_hits=3262 | tt_cutoffs=2037 | moves_evaluated=26614 | nodes_searched=44032
Ply 2: white to move | legal_moves=3 | time_limit=1.000s | search started
Ply 2: Kc4 (d4c4) | score=-701 | positions=46080 | elapsed=1.018951s
Ply 2 detail: completed_depth=6 | timed_out=True | tt_entries=3094 | tt_probes=7508 | tt_hits=4231 | tt_cutoffs=2643 | moves_evaluated=27787 | nodes_searched=46080
Ply 3: black to move | legal_moves=20 | time_limit=1.000s | search started
Ply 3: Ke5 (d6e5) | score=693 | positions=43008 | elapsed=1.015859s
Ply 3 detail: completed_depth=5 | timed_out=True | tt_entries=2578 | tt_probes=5382 | tt_hits=2710 | tt_cutoffs=1424 | moves_evaluated=25518 | nodes_searched=43008
Ply 4: white to move | legal_moves=6 | time_limit=1.000s | search started
Ply 4: Kc3 (c4c3) | score=-717 | positions=41984 | elapsed=1.011973s
Ply 4 detail: completed_depth=6 | timed_out=True | tt_entries=2153 | tt_probes=5179 | tt_hits=2935 | tt_cutoffs=1523 | moves_evaluated=24626 | nodes_searched=41984
Ply 5: black to move | legal_moves=16 | time_limit=1.000s | search started
Ply 5: Kd5 (e5d5) | score=717 | positions=40960 | elapsed=1.001128s
Ply 5 detail: completed_depth=5 | timed_out=True | tt_entries=2763 | tt_probes=6007 | tt_hits=3171 | tt_cutoffs=1860 | moves_evaluated=24713 | nodes_searched=40960
Ply 6: white to move | legal_moves=6 | time_limit=1.000s | search started
Ply 6: Kd3 (c3d3) | score=-717 | positions=46080 | elapsed=1.018248s
Ply 6 detail: completed_depth=5 | timed_out=True | tt_entries=2104 | tt_probes=5375 | tt_hits=3174 | tt_cutoffs=1519 | moves_evaluated=26677 | nodes_searched=46080
Ply 7: black to move | legal_moves=19 | time_limit=1.000s | search started
Ply 7: Re4 (e8e4) | score=724 | positions=44216 | elapsed=1.001177s
Ply 7 detail: completed_depth=5 | timed_out=True | tt_entries=3529 | tt_probes=7870 | tt_hits=4138 | tt_cutoffs=2748 | moves_evaluated=27058 | nodes_searched=44216
Ply 8: white to move | legal_moves=3 | time_limit=1.000s | search started
Ply 8: Kc3 (d3c3) | score=-728 | positions=46080 | elapsed=1.005103s
Ply 8 detail: completed_depth=6 | timed_out=True | tt_entries=4327 | tt_probes=11315 | tt_hits=6735 | tt_cutoffs=4593 | moves_evaluated=29349 | nodes_searched=46080
Ply 9: black to move | legal_moves=19 | time_limit=1.000s | search started
Ply 9: Rd4 (e4d4) | score=743 | positions=45056 | elapsed=1.003737s
Ply 9 detail: completed_depth=5 | timed_out=True | tt_entries=4275 | tt_probes=9753 | tt_hits=5351 | tt_cutoffs=3512 | moves_evaluated=28116 | nodes_searched=45056
Ply 10: white to move | legal_moves=3 | time_limit=1.000s | search started
Ply 10: Kb3 (c3b3) | score=-760 | positions=47104 | elapsed=1.016639s
Ply 10 detail: completed_depth=7 | timed_out=True | tt_entries=4591 | tt_probes=12211 | tt_hits=7328 | tt_cutoffs=5111 | moves_evaluated=30247 | nodes_searched=47104
Ply 11: black to move | legal_moves=16 | time_limit=1.000s | search started
Ply 11: Rc4 (d4c4) | score=760 | positions=45056 | elapsed=1.001491s
Ply 11 detail: completed_depth=6 | timed_out=True | tt_entries=4717 | tt_probes=11082 | tt_hits=6193 | tt_cutoffs=4149 | moves_evaluated=28621 | nodes_searched=45056
Ply 12: white to move | legal_moves=3 | time_limit=1.000s | search started
Ply 12: Ka3 (b3a3) | score=-784 | positions=44032 | elapsed=1.003669s
Ply 12 detail: completed_depth=7 | timed_out=True | tt_entries=4207 | tt_probes=12650 | tt_hits=8138 | tt_cutoffs=5962 | moves_evaluated=28935 | nodes_searched=44032
Ply 13: black to move | legal_moves=21 | time_limit=1.000s | search started
Ply 13: Kd4 (d5d4) | score=772 | positions=43008 | elapsed=1.001711s
Ply 13 detail: completed_depth=5 | timed_out=True | tt_entries=4394 | tt_probes=12405 | tt_hits=7742 | tt_cutoffs=5793 | moves_evaluated=28352 | nodes_searched=43008
Ply 14: white to move | legal_moves=3 | time_limit=1.000s | search started
Ply 14: Kb2 (a3b2) | score=-801 | positions=45056 | elapsed=1.017402s
Ply 14 detail: completed_depth=7 | timed_out=True | tt_entries=3511 | tt_probes=10042 | tt_hits=6283 | tt_cutoffs=4124 | moves_evaluated=28869 | nodes_searched=45056
Ply 15: black to move | legal_moves=15 | time_limit=1.000s | search started
Ply 15: Rc3 (c4c3) | score=786 | positions=45645 | elapsed=1.007833s
Ply 15 detail: completed_depth=6 | timed_out=True | tt_entries=4070 | tt_probes=10453 | tt_hits=6117 | tt_cutoffs=4063 | moves_evaluated=28692 | nodes_searched=45645
Ply 16: white to move | legal_moves=3 | time_limit=1.000s | search started
Ply 16: Ka2 (b2a2) | score=-818 | positions=47104 | elapsed=1.006011s
Ply 16 detail: completed_depth=7 | timed_out=True | tt_entries=3503 | tt_probes=10982 | tt_hits=7258 | tt_cutoffs=5084 | moves_evaluated=29701 | nodes_searched=47104
Ply 17: black to move | legal_moves=21 | time_limit=1.000s | search started
Ply 17: Kc4 (d4c4) | score=818 | positions=46080 | elapsed=1.014577s
Ply 17 detail: completed_depth=6 | timed_out=True | tt_entries=3602 | tt_probes=10154 | tt_hits=6317 | tt_cutoffs=4142 | moves_evaluated=28815 | nodes_searched=46080
Ply 18: white to move | legal_moves=3 | time_limit=1.000s | search started
Ply 18: Kb2 (a2b2) | score=-856 | positions=50176 | elapsed=1.013783s
Ply 18 detail: completed_depth=7 | timed_out=True | tt_entries=2430 | tt_probes=8140 | tt_hits=5575 | tt_cutoffs=3041 | moves_evaluated=32655 | nodes_searched=50176
Ply 19: black to move | legal_moves=15 | time_limit=1.000s | search started
Ply 19: Kb4 (c4b4) | score=844 | positions=47104 | elapsed=1.020518s
Ply 19 detail: completed_depth=6 | timed_out=True | tt_entries=3003 | tt_probes=8966 | tt_hits=5832 | tt_cutoffs=3252 | moves_evaluated=30082 | nodes_searched=47104
Ply 20: white to move | legal_moves=3 | time_limit=1.000s | search started
Ply 20: Ka2 (b2a2) | score=-999992 | positions=58368 | elapsed=1.009728s
Ply 20 detail: completed_depth=7 | timed_out=True | tt_entries=3124 | tt_probes=12776 | tt_hits=9429 | tt_cutoffs=5663 | moves_evaluated=45909 | nodes_searched=58368
Ply 21: black to move | legal_moves=19 | time_limit=1.000s | search started
Ply 21: Rb3 (c3b3) | score=856 | positions=47104 | elapsed=1.016997s
Ply 21 detail: completed_depth=6 | timed_out=True | tt_entries=2891 | tt_probes=8851 | tt_hits=5835 | tt_cutoffs=3717 | moves_evaluated=28836 | nodes_searched=47104
Ply 22: white to move | legal_moves=1 | time_limit=1.000s | search started
Ply 22: Ka1 (a2a1) | score=-999994 | positions=95232 | elapsed=1.007065s
Ply 22 detail: completed_depth=31 | timed_out=True | tt_entries=408 | tt_probes=13249 | tt_hits=12623 | tt_cutoffs=1963 | moves_evaluated=93549 | nodes_searched=95232
Ply 23: black to move | legal_moves=16 | time_limit=1.000s | search started
Ply 23: Kc3 (b4c3) | score=999995 | positions=45056 | elapsed=1.016997s
Ply 23 detail: completed_depth=6 | timed_out=True | tt_entries=2439 | tt_probes=7262 | tt_hits=4678 | tt_cutoffs=2864 | moves_evaluated=27306 | nodes_searched=45056
Ply 24: white to move | legal_moves=1 | time_limit=1.000s | search started
Ply 24: Ka2 (a1a2) | score=-999996 | positions=99290 | elapsed=1.000985s
Ply 24 detail: completed_depth=440 | timed_out=True | tt_entries=30 | tt_probes=13566 | tt_hits=13100 | tt_cutoffs=0 | moves_evaluated=99248 | nodes_searched=99290
Ply 25: black to move | legal_moves=14 | time_limit=1.000s | search started
Ply 25: Kc2 (c3c2) | score=999997 | positions=69632 | elapsed=1.001094s
Ply 25 detail: completed_depth=9 | timed_out=True | tt_entries=2364 | tt_probes=14463 | tt_hits=11762 | tt_cutoffs=5036 | moves_evaluated=60149 | nodes_searched=69632
Ply 26: white to move | legal_moves=1 | time_limit=1.000s | search started
Ply 26: Ka1 (a2a1) | score=-999998 | positions=117374 | elapsed=1.000054s
Ply 26 detail: completed_depth=5869 | timed_out=True | tt_entries=2 | tt_probes=17605 | tt_hits=11736 | tt_cutoffs=0 | moves_evaluated=117361 | nodes_searched=117374
Ply 27: black to move | legal_moves=19 | time_limit=1.000s | search started
Ply 27: Ra3# (b3a3) | score=999999 | positions=108594 | elapsed=1.000268s
Ply 27 detail: completed_depth=43 | timed_out=True | tt_entries=307 | tt_probes=16172 | tt_hits=15106 | tt_cutoffs=3318 | moves_evaluated=107379 | nodes_searched=108594

Final FEN: 8/8/8/8/8/r7/2k5/K7 w - - 28 15
Total positions: 1498511
Outcome: checkmate
Winner: black
Repetition detected: False
Black delivered mate within ply limit: True

=== summary ===
puzzle-1: PASS
puzzle-2: PASS
endgame-1: PASS
endgame-2: PASS
"""