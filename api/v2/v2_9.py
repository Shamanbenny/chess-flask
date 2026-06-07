"""Python port of the current C# V2.9 engine for the Flask route."""

import math
import time
from dataclasses import dataclass
from typing import Callable

import chess

from .v2_0 import (
    BOUND_EXACT,
    BOUND_LOWER,
    BOUND_UPPER,
    DEFAULT_TIME_LIMIT_SECONDS,
    DELTA_PRUNING_MARGIN,
    DRAW_BASE_PENALTY,
    ENDGAME_KING_MOBILITY_SCALE,
    ENDGAME_MATERIAL_ADVANTAGE_THRESHOLD,
    ENDGAME_MOP_UP_SCALE,
    ENDGAME_NON_PAWN_MATERIAL_THRESHOLD,
    ENDGAME_PAWN_DANGER_SCALE,
    MATE_SCORE,
    MATE_SCORE_THRESHOLD,
    PIECE_VALUES,
    REPEAT_POSITION_PENALTY,
    SearchTimeout,
    THREEFOLD_REPETITION_PENALTY,
    TIME_CHECK_INTERVAL,
    TranspositionTable,
    TT_MOVE_BONUS,
    WINNING_ENDGAME_REPEAT_PENALTY,
    _captured_piece_value,
    _is_repetition,
    _position_key,
    _promotion_piece_value,
    _score_from_tt,
    _score_to_tt,
)


ROOK_OPEN_FILE_BONUS = 18
ROOK_SEMI_OPEN_FILE_BONUS = 9
KNIGHT_OUTPOST_BONUS = 14

PAWN_PST = [
    0, 0, 0, 0, 0, 0, 0, 0,
    10, 10, 12, 0, 0, 12, 10, 10,
    6, 6, 10, 18, 18, 10, 6, 6,
    4, 4, 8, 20, 20, 8, 4, 4,
    4, 4, 8, 16, 16, 8, 4, 4,
    6, 8, 12, 18, 18, 12, 8, 6,
    12, 12, 16, 22, 22, 16, 12, 12,
    0, 0, 0, 0, 0, 0, 0, 0,
]
PASSED_PAWN_BONUS = [0, 0, 8, 16, 28, 45, 70, 0]
KNIGHT_PST = [
    -35, -20, -12, -10, -10, -12, -20, -35,
    -18, -6, 4, 8, 8, 4, -6, -18,
    -10, 6, 16, 20, 20, 16, 6, -10,
    -8, 10, 22, 28, 28, 22, 10, -8,
    -8, 10, 22, 28, 28, 22, 10, -8,
    -10, 6, 16, 20, 20, 16, 6, -10,
    -18, -6, 4, 8, 8, 4, -6, -18,
    -35, -20, -12, -10, -10, -12, -20, -35,
]
BISHOP_PST = [
    -14, -8, -8, -6, -6, -8, -8, -14,
    -6, 6, 8, 10, 10, 8, 6, -6,
    -4, 8, 12, 16, 16, 12, 8, -4,
    -2, 10, 14, 18, 18, 14, 10, -2,
    -2, 10, 14, 18, 18, 14, 10, -2,
    -4, 8, 12, 16, 16, 12, 8, -4,
    -6, 6, 8, 10, 10, 8, 6, -6,
    -14, -8, -8, -6, -6, -8, -8, -14,
]
ROOK_PST = [
    0, 0, 4, 8, 8, 4, 0, 0,
    2, 4, 8, 10, 10, 8, 4, 2,
    -2, 0, 2, 6, 6, 2, 0, -2,
    -2, 0, 2, 6, 6, 2, 0, -2,
    -2, 0, 2, 6, 6, 2, 0, -2,
    -2, 0, 2, 6, 6, 2, 0, -2,
    6, 8, 10, 12, 12, 10, 8, 6,
    0, 0, 4, 8, 8, 4, 0, 0,
]
QUEEN_PST = [
    -10, -6, -4, -2, -2, -4, -6, -10,
    -6, 0, 4, 6, 6, 4, 0, -6,
    -4, 4, 8, 10, 10, 8, 4, -4,
    -2, 6, 10, 12, 12, 10, 6, -2,
    -2, 6, 10, 12, 12, 10, 6, -2,
    -4, 4, 8, 10, 10, 8, 4, -4,
    -6, 0, 4, 6, 6, 4, 0, -6,
    -10, -6, -4, -2, -2, -4, -6, -10,
]
KING_MIDDLE_PST = [
    18, 24, 8, -8, -8, 8, 24, 18,
    12, 12, -4, -12, -12, -4, 12, 12,
    -8, -12, -20, -28, -28, -20, -12, -8,
    -18, -24, -32, -40, -40, -32, -24, -18,
    -24, -30, -38, -48, -48, -38, -30, -24,
    -30, -36, -44, -56, -56, -44, -36, -30,
    -36, -42, -50, -62, -62, -50, -42, -36,
    -42, -48, -56, -70, -70, -56, -48, -42,
]
KING_END_PST = [
    -28, -18, -10, -6, -6, -10, -18, -28,
    -18, -6, 4, 10, 10, 4, -6, -18,
    -10, 4, 14, 20, 20, 14, 4, -10,
    -6, 10, 20, 28, 28, 20, 10, -6,
    -6, 10, 20, 28, 28, 20, 10, -6,
    -10, 4, 14, 20, 20, 14, 4, -10,
    -18, -6, 4, 10, 10, 4, -6, -18,
    -28, -18, -10, -6, -6, -10, -18, -28,
]


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
    positional_balance: int
    endgame_weight: float


def _mirror_square(square: int) -> int:
    return chess.square(chess.square_file(square), 7 - chess.square_rank(square))


def _current_endgame_weight(board: chess.Board) -> float:
    total_non_pawn_material = 0
    for piece in board.piece_map().values():
        if piece.piece_type not in (chess.PAWN, chess.KING):
            total_non_pawn_material += PIECE_VALUES[piece.piece_type]
    weight = 1.0 - (
        min(total_non_pawn_material, ENDGAME_NON_PAWN_MATERIAL_THRESHOLD)
        / ENDGAME_NON_PAWN_MATERIAL_THRESHOLD
    )
    return max(0.0, min(1.0, weight))


def _positional_value(piece: chess.Piece, square: int, endgame_weight: float) -> int:
    lookup_square = square if piece.color == chess.WHITE else _mirror_square(square)
    if piece.piece_type == chess.PAWN:
        return PAWN_PST[lookup_square]
    if piece.piece_type == chess.KNIGHT:
        return KNIGHT_PST[lookup_square]
    if piece.piece_type == chess.BISHOP:
        return BISHOP_PST[lookup_square]
    if piece.piece_type == chess.ROOK:
        return ROOK_PST[lookup_square]
    if piece.piece_type == chess.QUEEN:
        return QUEEN_PST[lookup_square]
    if piece.piece_type == chess.KING:
        return int(
            (KING_MIDDLE_PST[lookup_square] * (1.0 - endgame_weight))
            + (KING_END_PST[lookup_square] * endgame_weight)
        )
    return 0


def _is_attacked_by_pawn(board: chess.Board, square: int, color: chess.Color) -> bool:
    return any(board.piece_type_at(attacker) == chess.PAWN for attacker in board.attackers(color, square))


def _is_knight_outpost(board: chess.Board, square: int, color: chess.Color) -> bool:
    rank = chess.square_rank(square)
    if color == chess.WHITE:
        if rank < 3 or rank > 5:
            return False
    elif rank < 2 or rank > 4:
        return False
    return _is_attacked_by_pawn(board, square, color) and not _is_attacked_by_pawn(board, square, not color)


def _is_passed_pawn(board: chess.Board, square: int, color: chess.Color) -> bool:
    file_index = chess.square_file(square)
    rank = chess.square_rank(square)
    enemy = not color
    rank_direction = 1 if color == chess.WHITE else -1
    for target_file in range(max(0, file_index - 1), min(7, file_index + 1) + 1):
        target_rank = rank + rank_direction
        while 0 <= target_rank < 8:
            piece = board.piece_at(chess.square(target_file, target_rank))
            if piece is not None and piece.color == enemy and piece.piece_type == chess.PAWN:
                return False
            target_rank += rank_direction
    return True


def _rook_file_bonus(rook_squares: list[int], own_pawn_files: list[int], enemy_pawn_files: list[int]) -> int:
    bonus = 0
    for rook_square in rook_squares:
        file_index = chess.square_file(rook_square)
        if own_pawn_files[file_index] != 0:
            continue
        bonus += ROOK_OPEN_FILE_BONUS if enemy_pawn_files[file_index] == 0 else ROOK_SEMI_OPEN_FILE_BONUS
    return bonus


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
    white_positional = 0
    black_positional = 0
    white_pawn_files = [0] * 8
    black_pawn_files = [0] * 8
    white_rook_squares: list[int] = []
    black_rook_squares: list[int] = []
    current_endgame_weight = _current_endgame_weight(board)

    for square, piece in board.piece_map().items():
        value = PIECE_VALUES[piece.piece_type]
        positional_value = _positional_value(piece, square, current_endgame_weight)
        if piece.color == chess.WHITE:
            white_material += value
            white_positional += positional_value
        else:
            black_material += value
            black_positional += positional_value

        if piece.piece_type == chess.PAWN:
            if piece.color == chess.WHITE:
                white_pawn_files[chess.square_file(square)] += 1
                white_pawn_danger += chess.square_rank(square)
                if _is_passed_pawn(board, square, chess.WHITE):
                    white_positional += PASSED_PAWN_BONUS[chess.square_rank(square)]
            else:
                black_pawn_files[chess.square_file(square)] += 1
                black_pawn_danger += 7 - chess.square_rank(square)
                if _is_passed_pawn(board, square, chess.BLACK):
                    black_positional += PASSED_PAWN_BONUS[7 - chess.square_rank(square)]
        elif piece.piece_type == chess.KNIGHT:
            if piece.color == chess.WHITE:
                white_knights += 1
                white_non_pawn_material += value
                if _is_knight_outpost(board, square, chess.WHITE):
                    white_positional += KNIGHT_OUTPOST_BONUS
            else:
                black_knights += 1
                black_non_pawn_material += value
                if _is_knight_outpost(board, square, chess.BLACK):
                    black_positional += KNIGHT_OUTPOST_BONUS
        elif piece.piece_type == chess.BISHOP:
            if piece.color == chess.WHITE:
                white_bishops += 1
                white_non_pawn_material += value
            else:
                black_bishops += 1
                black_non_pawn_material += value
        elif piece.piece_type == chess.ROOK:
            if piece.color == chess.WHITE:
                if len(white_rook_squares) < 10:
                    white_rook_squares.append(square)
                white_rooks += 1
                white_non_pawn_material += value
            else:
                if len(black_rook_squares) < 10:
                    black_rook_squares.append(square)
                black_rooks += 1
                black_non_pawn_material += value
        elif piece.piece_type == chess.QUEEN:
            if piece.color == chess.WHITE:
                white_queens += 1
                white_non_pawn_material += value
            else:
                black_queens += 1
                black_non_pawn_material += value

    white_positional += _rook_file_bonus(white_rook_squares, white_pawn_files, black_pawn_files)
    black_positional += _rook_file_bonus(black_rook_squares, black_pawn_files, white_pawn_files)
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
        positional_balance=white_positional - black_positional,
        endgame_weight=max(0.0, min(1.0, endgame_weight)),
    )


def _manhattan_distance(first: int, second: int) -> int:
    return abs(chess.square_file(first) - chess.square_file(second)) + abs(
        chess.square_rank(first) - chess.square_rank(second)
    )


def _center_manhattan_distance(square: int) -> int:
    file_index = chess.square_file(square)
    rank_index = chess.square_rank(square)
    return max(3 - file_index, file_index - 4) + max(3 - rank_index, rank_index - 4)


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


def evaluate_v2_9(board: chess.Board) -> int:
    snapshot = _build_eval_snapshot(board)
    material_score = snapshot.material_balance if board.turn == chess.WHITE else -snapshot.material_balance
    positional_score = snapshot.positional_balance if board.turn == chess.WHITE else -snapshot.positional_balance
    return (
        material_score
        + positional_score
        + _repetition_draw_adjustment(board)
        + _endgame_mop_up_adjustment(board, snapshot)
        + _winning_endgame_repetition_adjustment(board, snapshot.material_balance, snapshot.endgame_weight)
    )


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
        if _is_attacked_by_pawn(board, move.to_square, not board.turn):
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


def search_move_v2_9(
    board: chess.Board,
    time_limit_seconds: float = DEFAULT_TIME_LIMIT_SECONDS,
    max_depth: int | None = None,
    transposition_table: TranspositionTable | None = None,
    position_key_func: Callable[[chess.Board], object] | None = None,
) -> dict:
    if time_limit_seconds <= 0:
        raise ValueError("time_limit_seconds must be greater than 0")

    deadline = time.perf_counter() + time_limit_seconds
    transposition_table = transposition_table or TranspositionTable()
    position_key = position_key_func or _position_key
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

    def quiescence(alpha: int, beta: int, search_board: chess.Board, ply: int) -> int:
        nonlocal moves_evaluated

        visit_node()
        in_check = search_board.is_check()
        moves = _ordered_search_moves(search_board, captures_only=not in_check)
        if not moves:
            return -MATE_SCORE + ply if in_check else evaluate_v2_9(search_board)

        stand_pat = evaluate_v2_9(search_board)
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
        key = position_key(search_board)
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
            return -MATE_SCORE + ply if search_board.is_check() else evaluate_v2_9(search_board)

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
        raise ValueError("No legal moves available for v2.9 search")

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
            root_key = position_key(board)
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


def choose_move_v2_9(board: chess.Board, time_limit_seconds: float = DEFAULT_TIME_LIMIT_SECONDS) -> dict:
    result = search_move_v2_9(board, time_limit_seconds=time_limit_seconds)
    return {
        "move": result["move_san"],
        "debug": {
            "version": "v2.9",
            "engine": "python_v2_9",
            "selected_move_uci": result["move"].uci(),
            "selected_move_san": result["move_san"],
            "score": result["score"],
            "completed_depth": result["completed_depth"],
            "time_limit_seconds": result["time_limit_seconds"],
            "timed_out": result["timed_out"],
            "moves_evaluated": result["moves_evaluated"],
            "nodes_searched": result["nodes_searched"],
            "tt_entries": result["tt_entries"],
            "tt_probes": result["tt_probes"],
            "tt_hits": result["tt_hits"],
            "tt_cutoffs": result["tt_cutoffs"],
        },
    }
