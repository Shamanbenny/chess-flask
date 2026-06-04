import math
import time
from dataclasses import dataclass

import chess

from .shared import PIECE_VALUES, evaluate_with_endgame_mop_up, ordered_legal_moves


DELTA_PRUNING_MARGIN = 200
MATE_SCORE = 1_000_000
MATE_SCORE_THRESHOLD = 999_000
DEFAULT_TIME_LIMIT_SECONDS = 1.0
DEFAULT_TT_SIZE_BITS = 18
BOUND_EXACT = "exact"
BOUND_LOWER = "lower"
BOUND_UPPER = "upper"


class SearchTimeout(Exception):
    pass


@dataclass(slots=True)
class TranspositionEntry:
    key: object
    depth: int
    score: int
    bound: str
    best_move: chess.Move | None
    age: int


class TranspositionTable:
    def __init__(self, size_bits: int = DEFAULT_TT_SIZE_BITS):
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

        should_replace = (
            existing is None
            or existing.key != key
            or depth > existing.depth
            or age > existing.age
            or (best_move is not None and existing.best_move is None)
        )
        if not should_replace:
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


def search_move_v1_5(
    board: chess.Board,
    time_limit_seconds: float = DEFAULT_TIME_LIMIT_SECONDS,
    max_depth: int | None = None,
) -> dict:
    if time_limit_seconds <= 0:
        raise ValueError("time_limit_seconds must be greater than 0")

    moves_evaluated = 0
    nodes_searched = 0
    tt_probes = 0
    tt_hits = 0
    tt_cutoffs = 0
    # v1.5's first defining change from v1.4 is that search is budgeted by think time, not fixed depth.
    deadline = time.perf_counter() + time_limit_seconds
    # v1.5's other major change is a transposition table reused across iterative-deepening passes.
    transposition_table = TranspositionTable()

    def check_time() -> None:
        if time.perf_counter() >= deadline:
            raise SearchTimeout

    def position_key(search_board: chess.Board) -> object:
        if hasattr(search_board, "_transposition_key"):
            return search_board._transposition_key()
        return search_board.fen()

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

    def score_to_tt(score: int, ply: int) -> int:
        if score >= MATE_SCORE_THRESHOLD:
            return score + ply
        if score <= -MATE_SCORE_THRESHOLD:
            return score - ply
        return score

    def score_from_tt(score: int, ply: int) -> int:
        if score >= MATE_SCORE_THRESHOLD:
            return score - ply
        if score <= -MATE_SCORE_THRESHOLD:
            return score + ply
        return score

    def terminal_score(search_board: chess.Board, ply: int) -> int:
        if search_board.is_checkmate():
            return -MATE_SCORE + ply
        return evaluate_with_endgame_mop_up(search_board, search_board.turn)

    def ordered_search_moves(
        search_board: chess.Board,
        tt_move: chess.Move | None = None,
        captures_only: bool = False,
    ) -> list[chess.Move]:
        moves = ordered_legal_moves(search_board)
        if captures_only and not search_board.is_check():
            moves = [move for move in moves if search_board.is_capture(move)]

        if tt_move is None or not search_board.is_legal(tt_move):
            return moves

        # Re-searching the stored hash move first is v1.5's main TT-based move-ordering gain.
        return [tt_move] + [move for move in moves if move != tt_move]

    def quiescence(alpha: int, beta: int, search_board: chess.Board, ply: int) -> int:
        nonlocal moves_evaluated
        nonlocal nodes_searched
        nonlocal tt_probes
        nonlocal tt_hits

        check_time()
        nodes_searched += 1

        if search_board.is_game_over():
            return terminal_score(search_board, ply)

        stand_pat = evaluate_with_endgame_mop_up(search_board, search_board.turn)
        if not search_board.is_check():
            if stand_pat >= beta:
                return beta
            alpha = max(alpha, stand_pat)

        tt_probes += 1
        entry = transposition_table.probe(position_key(search_board))
        if entry is not None:
            tt_hits += 1
        tt_move = entry.best_move if entry is not None else None

        for move in ordered_search_moves(search_board, tt_move=tt_move, captures_only=True):
            if not search_board.is_check():
                if is_obviously_losing_capture(search_board, move):
                    continue
                if is_delta_pruned(search_board, move, stand_pat, alpha):
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
        nonlocal nodes_searched
        nonlocal tt_probes
        nonlocal tt_hits
        nonlocal tt_cutoffs

        check_time()
        nodes_searched += 1

        if search_board.is_game_over():
            return terminal_score(search_board, ply)

        if remaining_depth == 0:
            return quiescence(alpha, beta, search_board, ply)

        alpha_original = alpha
        key = position_key(search_board)
        tt_probes += 1
        entry = transposition_table.probe(key)
        if entry is not None:
            tt_hits += 1
        tt_move = entry.best_move if entry is not None else None

        # v1.5 adds TT cutoffs when an entry was searched deeply enough and carries a usable bound.
        if entry is not None and entry.depth >= remaining_depth:
            tt_score = score_from_tt(entry.score, ply)
            if entry.bound == BOUND_EXACT:
                tt_cutoffs += 1
                return tt_score
            if entry.bound == BOUND_LOWER and tt_score >= beta:
                tt_cutoffs += 1
                return tt_score
            if entry.bound == BOUND_UPPER and tt_score <= alpha:
                tt_cutoffs += 1
                return tt_score

        best_move = tt_move if tt_move is not None and search_board.is_legal(tt_move) else None
        best_score = -math.inf

        for move in ordered_search_moves(search_board, tt_move=tt_move):
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

        if best_move is None:
            return terminal_score(search_board, ply)

        if best_score <= alpha_original:
            bound = BOUND_UPPER
        elif best_score >= beta:
            bound = BOUND_LOWER
        else:
            bound = BOUND_EXACT

        transposition_table.store(
            key=key,
            depth=remaining_depth,
            score=score_to_tt(best_score, ply),
            bound=bound,
            best_move=best_move,
            age=current_iteration_depth,
        )
        return best_score

    fallback_moves = ordered_legal_moves(board)
    if not fallback_moves:
        raise ValueError("No legal moves available for v1.5 search")

    best_move = fallback_moves[0]
    best_eval = -math.inf
    completed_depth = 0
    timed_out = False
    current_iteration_depth = 0

    # Iterative deepening ensures v1.5 can always return the best move from the last completed pass.
    depth = 1
    while max_depth is None or depth <= max_depth:
        current_iteration_depth = depth
        iteration_best_move: chess.Move | None = None
        iteration_best_eval = -math.inf

        try:
            tt_probes += 1
            root_entry = transposition_table.probe(position_key(board))
            if root_entry is not None:
                tt_hits += 1
            root_tt_move = root_entry.best_move if root_entry is not None else None

            for move in ordered_search_moves(board, tt_move=root_tt_move):
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
                key=position_key(board),
                depth=depth,
                score=score_to_tt(best_eval, 0),
                bound=BOUND_EXACT,
                best_move=best_move,
                age=current_iteration_depth,
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


def choose_move_v1_5(board: chess.Board, time_limit_seconds: float = DEFAULT_TIME_LIMIT_SECONDS) -> dict:
    result = search_move_v1_5(board, time_limit_seconds=time_limit_seconds)
    return {
        "move": result["move_san"],
        "moves_evaluated": result["moves_evaluated"],
        "completed_depth": result["completed_depth"],
    }
