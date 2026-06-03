import pathlib
import sys
import time

import chess

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from api.v1 import search_move_v1_4


DEFAULT_FEN = "3r4/8/3k4/8/3K4/8/8/8 b - - 1 1"
DEFAULT_DEPTH = 4
DEFAULT_MAX_PLIES = 60


def timed_search(board: chess.Board, depth: int) -> tuple[dict, float]:
    started_at = time.perf_counter()
    result = search_move_v1_4(board, depth)
    return result, time.perf_counter() - started_at


def print_search_start(board: chess.Board, ply: int) -> None:
    mover = "white" if board.turn == chess.WHITE else "black"
    legal_moves = board.legal_moves.count()
    print(
        f"Ply {ply}: {mover} to move | legal_moves={legal_moves} | depth={DEFAULT_DEPTH} | search started",
        flush=True,
    )


def winner_label(board: chess.Board) -> str:
    if not board.is_checkmate():
        return "none"
    return "black" if board.turn == chess.WHITE else "white"


def run_endgame() -> int:
    board = chess.Board(DEFAULT_FEN)
    print(f"=== v1.4 endgame self-play at depth {DEFAULT_DEPTH} ===", flush=True)
    print(f"Start FEN: {DEFAULT_FEN}", flush=True)
    print(
        f"Start turn: {'white' if board.turn == chess.WHITE else 'black'} | max_plies={DEFAULT_MAX_PLIES}",
        flush=True,
    )

    total_positions = 0
    repetition_detected = False

    for ply in range(1, DEFAULT_MAX_PLIES + 1):
        if board.is_game_over():
            break

        print_search_start(board, ply)
        result, elapsed = timed_search(board, DEFAULT_DEPTH)
        total_positions += result["moves_evaluated"]
        mover = "white" if board.turn == chess.WHITE else "black"

        print(
            f"Ply {ply}: {mover} plays {result['move_san']} ({result['move'].uci()}) "
            f"| score={result['score']} | positions={result['moves_evaluated']} "
            f"| elapsed={elapsed:.6f}s",
            flush=True,
        )

        board.push(result["move"])

        if board.can_claim_threefold_repetition() or board.is_repetition(2):
            repetition_detected = True
            print(
                f"Stopping after ply {ply}: repetition pressure detected at FEN {board.fen()}",
                flush=True,
            )
            break

    print(flush=True)
    print(f"Final FEN: {board.fen()}", flush=True)
    print(f"Total positions: {total_positions}", flush=True)
    print(f"Outcome: {board.outcome(claim_draw=True)}", flush=True)
    print(f"Winner: {winner_label(board)}", flush=True)
    print(f"Repetition detected: {repetition_detected}", flush=True)
    print(
        "Black delivered mate without repetition: "
        f"{board.is_checkmate() and winner_label(board) == 'black' and not repetition_detected}",
        flush=True,
    )

    return 0


def main() -> int:
    try:
        return run_endgame()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
