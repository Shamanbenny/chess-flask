"""Retired Python reference implementation for v1.0."""

import math

import chess

from .shared import evaluate_with_draw_penalty


def search_move_v1(board: chess.Board, depth: int = 3) -> dict:
    moves_evaluated = 0

    def v1_minimax(remaining_depth: int, perspective: chess.Color, search_board: chess.Board):
        nonlocal moves_evaluated

        if remaining_depth == 0:
            return evaluate_with_draw_penalty(search_board, perspective)

        if search_board.is_game_over():
            if search_board.is_checkmate():
                return -math.inf if search_board.turn == perspective else math.inf
            return evaluate_with_draw_penalty(search_board, perspective)

        best_eval = -math.inf
        for move in list(search_board.legal_moves):
            search_board.push(move)
            moves_evaluated += 1
            move_eval = -v1_minimax(remaining_depth - 1, perspective, search_board)
            search_board.pop()
            best_eval = max(best_eval, move_eval)

        return best_eval

    best_move = None
    best_eval = -math.inf
    for move in list(board.legal_moves):
        board.push(move)
        moves_evaluated += 1
        move_eval = -v1_minimax(depth - 1, board.turn, board)
        board.pop()
        if best_move is None or move_eval > best_eval:
            best_eval = move_eval
            best_move = move

    if best_move is None:
        raise ValueError("No legal moves available for v1 search")

    return {
        "move": best_move,
        "move_san": board.san(best_move),
        "score": best_eval,
        "moves_evaluated": moves_evaluated,
    }


def choose_move_v1(board: chess.Board, depth: int = 3) -> dict:
    result = search_move_v1(board, depth)
    return {
        "move": result["move_san"],
        "moves_evaluated": result["moves_evaluated"],
    }
