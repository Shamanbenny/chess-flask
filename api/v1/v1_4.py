import math

import chess

from .shared import (
    PIECE_VALUES,
    evaluate_with_endgame_mop_up,
    ordered_legal_moves,
)


DELTA_PRUNING_MARGIN = 200


def search_move_v1_4(board: chess.Board, depth: int = 4) -> dict:
    moves_evaluated = 0

    # v1.4 keeps v1.3's search skeleton but narrows qsearch to captures/evasions in quiet positions.
    def ordered_quiescence_moves(search_board: chess.Board) -> list[chess.Move]:
        if search_board.is_check():
            return ordered_legal_moves(search_board)

        return [move for move in ordered_legal_moves(search_board) if search_board.is_capture(move)]

    # These helpers support v1.4's extra qsearch pruning so queen endgames do not explode on checks.
    def captured_piece_value(search_board: chess.Board, move: chess.Move) -> int:
        captured_piece = search_board.piece_at(move.to_square)
        if captured_piece is None and search_board.is_en_passant(move):
            return PIECE_VALUES[chess.PAWN]
        return PIECE_VALUES.get(captured_piece.piece_type, 0) if captured_piece else 0

    def promotion_gain(move: chess.Move) -> int:
        if not move.promotion:
            return 0
        return PIECE_VALUES.get(move.promotion, 0) - PIECE_VALUES[chess.PAWN]

    def is_obviously_losing_capture(search_board: chess.Board, move: chess.Move) -> bool:
        attacker_piece = search_board.piece_at(move.from_square)
        if attacker_piece is None or move.promotion:
            return False

        return PIECE_VALUES.get(attacker_piece.piece_type, 0) > captured_piece_value(search_board, move)

    def is_delta_pruned(search_board: chess.Board, move: chess.Move, stand_pat: int, alpha: int) -> bool:
        material_swing = captured_piece_value(search_board, move) + promotion_gain(move)
        return stand_pat + material_swing + DELTA_PRUNING_MARGIN < alpha

    def quiescence(
        alpha: int,
        beta: int,
        search_board: chess.Board,
        perspective: chess.Color,
    ) -> int:
        nonlocal moves_evaluated

        if search_board.is_game_over():
            if search_board.is_checkmate():
                return -math.inf if search_board.turn == perspective else math.inf
            return evaluate_with_endgame_mop_up(search_board, perspective)

        # v1.4's other defining change is the endgame mop-up evaluation layered onto leaf scoring.
        stand_pat = evaluate_with_endgame_mop_up(search_board, perspective)
        if not search_board.is_check():
            if stand_pat >= beta:
                return beta
            alpha = max(alpha, stand_pat)

        for move in ordered_quiescence_moves(search_board):
            if not search_board.is_check():
                if is_obviously_losing_capture(search_board, move):
                    continue
                if is_delta_pruned(search_board, move, stand_pat, alpha):
                    continue

            search_board.push(move)
            moves_evaluated += 1
            move_eval = -quiescence(-beta, -alpha, search_board, not perspective)
            search_board.pop()

            if move_eval >= beta:
                return beta
            alpha = max(alpha, move_eval)

        return alpha

    def alphabeta(
        remaining_depth: int,
        alpha: int,
        beta: int,
        search_board: chess.Board,
        perspective: chess.Color,
    ) -> int:
        nonlocal moves_evaluated

        if search_board.is_game_over():
            if search_board.is_checkmate():
                return -math.inf
            return evaluate_with_endgame_mop_up(search_board, perspective)

        if remaining_depth == 0:
            return quiescence(alpha, beta, search_board, perspective)

        move_eval = -math.inf
        for move in ordered_legal_moves(search_board):
            search_board.push(move)
            moves_evaluated += 1
            move_eval = max(
                move_eval,
                -alphabeta(
                    remaining_depth - 1,
                    -beta,
                    -alpha,
                    search_board,
                    not perspective,
                ),
            )
            search_board.pop()

            if move_eval >= beta:
                return beta
            alpha = max(alpha, move_eval)

        return move_eval

    best_move = None
    best_eval = -math.inf
    perspective = board.turn
    for move in ordered_legal_moves(board):
        board.push(move)
        moves_evaluated += 1
        move_eval = -alphabeta(depth - 1, -math.inf, math.inf, board, not perspective)
        board.pop()
        # Always keep the first legal move as a fallback so forced-loss positions still return a move.
        if best_move is None or move_eval > best_eval:
            best_eval = move_eval
            best_move = move

    if best_move is None:
        raise ValueError("No legal moves available for v1.4 search")

    return {
        "move": best_move,
        "move_san": board.san(best_move),
        "score": best_eval,
        "moves_evaluated": moves_evaluated,
    }


def choose_move_v1_4(board: chess.Board, depth: int = 4) -> dict:
    result = search_move_v1_4(board, depth)
    return {
        "move": result["move_san"],
        "moves_evaluated": result["moves_evaluated"],
    }
