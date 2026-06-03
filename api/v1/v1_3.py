import math

import chess

from .shared import evaluate_with_draw_penalty, ordered_legal_moves


def search_move_v1_3(board: chess.Board, depth: int = 4) -> dict:
    moves_evaluated = 0

    # v1.3's defining change over v1.2 is quiescence search to avoid stopping on unstable leaf positions.
    def ordered_quiescence_moves(search_board: chess.Board) -> list[chess.Move]:
        if search_board.is_check():
            return ordered_legal_moves(search_board)

        forcing_moves: list[chess.Move] = []
        for move in ordered_legal_moves(search_board):
            if search_board.is_capture(move):
                forcing_moves.append(move)
                continue

            search_board.push(move)
            gives_check = search_board.is_check()
            search_board.pop()

            if gives_check:
                forcing_moves.append(move)

        return forcing_moves

    def quiescence(alpha: int, beta: int, search_board: chess.Board, perspective: chess.Color) -> int:
        nonlocal moves_evaluated

        if search_board.is_game_over():
            if search_board.is_checkmate():
                return -math.inf if search_board.turn == perspective else math.inf
            return evaluate_with_draw_penalty(search_board, perspective)

        stand_pat = evaluate_with_draw_penalty(search_board, perspective)
        if not search_board.is_check():
            if stand_pat >= beta:
                return beta
            alpha = max(alpha, stand_pat)

        for move in ordered_quiescence_moves(search_board):
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
            return evaluate_with_draw_penalty(search_board, perspective)

        if remaining_depth == 0:
            return quiescence(alpha, beta, search_board, perspective)

        move_eval = -math.inf
        for move in ordered_legal_moves(search_board):
            search_board.push(move)
            moves_evaluated += 1
            move_eval = max(
                move_eval,
                -alphabeta(remaining_depth - 1, -beta, -alpha, search_board, not perspective),
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
        if best_move is None or move_eval > best_eval:
            best_eval = move_eval
            best_move = move

    if best_move is None:
        raise ValueError("No legal moves available for v1.3 search")

    return {
        "move": best_move,
        "move_san": board.san(best_move),
        "score": best_eval,
        "moves_evaluated": moves_evaluated,
    }


def choose_move_v1_3(board: chess.Board, depth: int = 4) -> dict:
    result = search_move_v1_3(board, depth)
    return {
        "move": result["move_san"],
        "moves_evaluated": result["moves_evaluated"],
    }
