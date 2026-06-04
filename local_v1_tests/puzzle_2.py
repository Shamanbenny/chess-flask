import argparse
import pathlib
import sys
import time

import chess

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from api.v1 import search_move_v1_5


DEFAULT_FEN = "3k4/8/3p4/p2P1p2/P2P1P2/8/3K4/8 w - - 10 6"
EXPECTED_FIRST_WHITE = "Kc3"
DEFAULT_TIME_LIMIT_SECONDS = 1.0
DEFAULT_MAX_PLIES = 70


def timed_search(board: chess.Board, time_limit_seconds: float) -> tuple[dict, float]:
    started_at = time.perf_counter()
    result = search_move_v1_5(board, time_limit_seconds=time_limit_seconds)
    return result, time.perf_counter() - started_at


def print_search_start(board: chess.Board, ply: int, time_limit_seconds: float) -> None:
    mover = "white" if board.turn == chess.WHITE else "black"
    legal_moves = board.legal_moves.count()
    print(
        f"Ply {ply}: {mover} to move | legal_moves={legal_moves} "
        f"| time_limit={time_limit_seconds:.3f}s | search started",
        flush=True,
    )


def winner_label(board: chess.Board) -> str:
    if not board.is_checkmate():
        return "none"
    return "black" if board.turn == chess.WHITE else "white"


def run_puzzle(fen: str, time_limit_seconds: float, max_plies: int) -> int:
    board = chess.Board(fen)
    print(f"=== v1.5 puzzle_2 self-play at time_limit={time_limit_seconds:.3f}s ===", flush=True)
    print(f"Start FEN: {fen}", flush=True)
    print(
        f"Start turn: {'white' if board.turn == chess.WHITE else 'black'} | max_plies={max_plies}",
        flush=True,
    )

    first_result, first_elapsed = timed_search(board, time_limit_seconds)
    print(
        f"White 1: {first_result['move_san']} ({first_result['move'].uci()}) "
        f"| expected={EXPECTED_FIRST_WHITE} | match={first_result['move_san'] == EXPECTED_FIRST_WHITE} "
        f"| score={first_result['score']} | positions={first_result['moves_evaluated']} "
        f"| elapsed={first_elapsed:.6f}s",
        flush=True,
    )
    print(
        f"White 1 detail: completed_depth={first_result['completed_depth']} "
        f"| timed_out={first_result['timed_out']} | tt_entries={first_result['tt_entries']} "
        f"| tt_probes={first_result['tt_probes']} | tt_hits={first_result['tt_hits']} "
        f"| tt_cutoffs={first_result['tt_cutoffs']}",
        flush=True,
    )

    if first_result["move_san"] != EXPECTED_FIRST_WHITE:
        print("Stopping: white did not find the target first move.", flush=True)
        return 0

    board.push(first_result["move"])

    total_positions = first_result["moves_evaluated"]
    total_tt_probes = first_result["tt_probes"]
    total_tt_hits = first_result["tt_hits"]
    total_tt_cutoffs = first_result["tt_cutoffs"]
    total_elapsed = first_elapsed
    repetition_detected = False

    for ply in range(2, max_plies + 1):
        if board.is_game_over():
            break

        print_search_start(board, ply, time_limit_seconds)
        result, elapsed = timed_search(board, time_limit_seconds)
        total_positions += result["moves_evaluated"]
        total_tt_probes += result["tt_probes"]
        total_tt_hits += result["tt_hits"]
        total_tt_cutoffs += result["tt_cutoffs"]
        total_elapsed += elapsed
        mover = "white" if board.turn == chess.WHITE else "black"

        print(
            f"Ply {ply}: {mover} plays {result['move_san']} ({result['move'].uci()}) "
            f"| score={result['score']} | positions={result['moves_evaluated']} "
            f"| elapsed={elapsed:.6f}s",
            flush=True,
        )
        print(
            f"Ply {ply} detail: completed_depth={result['completed_depth']} "
            f"| timed_out={result['timed_out']} | tt_entries={result['tt_entries']} "
            f"| tt_probes={result['tt_probes']} | tt_hits={result['tt_hits']} "
            f"| tt_cutoffs={result['tt_cutoffs']}",
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
    print(f"Total elapsed: {total_elapsed:.6f}s", flush=True)
    print(f"Total TT probes: {total_tt_probes}", flush=True)
    print(f"Total TT hits: {total_tt_hits}", flush=True)
    print(f"Total TT cutoffs: {total_tt_cutoffs}", flush=True)
    print(f"Outcome: {board.outcome(claim_draw=True)}", flush=True)
    print(f"Winner: {winner_label(board)}", flush=True)
    print(f"Repetition detected: {repetition_detected}", flush=True)
    print(
        "White delivered mate within ply limit: "
        f"{board.is_checkmate() and winner_label(board) == 'white' and not repetition_detected}",
        flush=True,
    )

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the fixed Kb1 puzzle_2 test and continue v1.5 self-play."
    )
    parser.add_argument("--fen", default=DEFAULT_FEN, help="Starting FEN for the puzzle.")
    parser.add_argument(
        "--time-limit-seconds",
        type=float,
        default=DEFAULT_TIME_LIMIT_SECONDS,
        help="Think time budget per move for v1.5.",
    )
    parser.add_argument(
        "--max-plies",
        type=int,
        default=DEFAULT_MAX_PLIES,
        help="Maximum plies to allow while checking whether white can force mate.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.time_limit_seconds <= 0:
        parser.error("--time-limit-seconds must be greater than 0")
    if args.max_plies < 1:
        parser.error("--max-plies must be at least 1")

    try:
        return run_puzzle(args.fen, args.time_limit_seconds, args.max_plies)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
