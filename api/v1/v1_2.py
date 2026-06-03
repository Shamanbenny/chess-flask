import math

import chess

from .shared import evaluate_with_draw_penalty, ordered_legal_moves


def search_move_v1_2(board: chess.Board, depth: int = 4) -> dict:
    moves_evaluated = 0

    def alphabeta(
        remaining_depth: int,
        alpha: int,
        beta: int,
        maximizing_player: bool,
        search_board: chess.Board,
        perspective: chess.Color,
    ):
        nonlocal moves_evaluated

        if remaining_depth == 0 or search_board.is_game_over():
            if search_board.is_game_over():
                if search_board.is_checkmate():
                    return -math.inf if maximizing_player else math.inf
                return evaluate_with_draw_penalty(search_board, perspective)
            if maximizing_player:
                return -evaluate_with_draw_penalty(search_board, perspective)
            return evaluate_with_draw_penalty(search_board, perspective)

        legal_moves = ordered_legal_moves(search_board)
        if maximizing_player:
            move_eval = -math.inf
            for move in legal_moves:
                search_board.push(move)
                moves_evaluated += 1
                move_eval = max(
                    move_eval,
                    alphabeta(remaining_depth - 1, alpha, beta, False, search_board, perspective),
                )
                search_board.pop()
                if move_eval >= beta:
                    break
                alpha = max(alpha, move_eval)
            return move_eval

        move_eval = math.inf
        for move in legal_moves:
            search_board.push(move)
            moves_evaluated += 1
            move_eval = min(
                move_eval,
                alphabeta(remaining_depth - 1, alpha, beta, True, search_board, perspective),
            )
            search_board.pop()
            if move_eval <= alpha:
                break
            beta = min(beta, move_eval)
        return move_eval

    best_move = None
    best_eval = -math.inf
    for move in ordered_legal_moves(board):
        board.push(move)
        moves_evaluated += 1
        move_eval = alphabeta(depth - 1, -math.inf, math.inf, False, board, board.turn)
        board.pop()
        if move_eval > best_eval:
            best_eval = move_eval
            best_move = move

    if best_move is None:
        raise ValueError("No legal moves available for v1.2 search")

    return {
        "move": best_move,
        "move_san": board.san(best_move),
        "score": best_eval,
        "moves_evaluated": moves_evaluated,
    }


def choose_move_v1_2(board: chess.Board, depth: int = 4) -> dict:
    result = search_move_v1_2(board, depth)
    return {
        "move": result["move_san"],
        "moves_evaluated": result["moves_evaluated"],
    }
