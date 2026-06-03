import argparse
import sys
import time

import chess

from api.v1 import search_move_for_version


DEFAULT_FEN = "8/8/6kp/3b4/1p1p4/1P1P3P/PK2N3/8 w - - 0 2"
EXPECTED_FIRST_WHITE = "Nf4+"
FORCED_BLACK_MOVE_UCI = "g6g7"
EXPECTED_SECOND_WHITE = "Nxd5"
DEFAULT_VERSIONS = ["v1", "v1.1", "v1.2", "v1.3"]


def timed_search(version: str, board: chess.Board, depth: int) -> tuple[dict, float]:
    started_at = time.perf_counter()
    result = search_move_for_version(version, board, depth)
    return result, time.perf_counter() - started_at


def run_experiment(versions: list[str], fen: str, depth: int) -> int:
    forced_black_move = chess.Move.from_uci(FORCED_BLACK_MOVE_UCI)

    for version in versions:
        board = chess.Board(fen)
        print(f"=== {version} experiment at depth {depth} ===")
        print(f"Start FEN: {fen}")

        first_result, first_elapsed = timed_search(version, board, depth)
        print(
            f"White 1: {first_result['move_san']} ({first_result['move'].uci()}) "
            f"| expected={EXPECTED_FIRST_WHITE} | match={first_result['move_san'] == EXPECTED_FIRST_WHITE} "
            f"| score={first_result['score']} | positions={first_result['moves_evaluated']} "
            f"| elapsed={first_elapsed:.6f}s"
        )

        if first_result["move_san"] != EXPECTED_FIRST_WHITE:
            print("Forced black move skipped because white did not find the target first move.")
            print()
            continue

        board.push(first_result["move"])
        if forced_black_move not in board.legal_moves:
            raise ValueError(f"Forced move Kg7 is illegal after {first_result['move_san']}")

        print(f"Black forced: {board.san(forced_black_move)} ({forced_black_move.uci()})")
        board.push(forced_black_move)

        second_result, second_elapsed = timed_search(version, board, depth)
        print(
            f"White 2: {second_result['move_san']} ({second_result['move'].uci()}) "
            f"| expected={EXPECTED_SECOND_WHITE} | match={second_result['move_san'] == EXPECTED_SECOND_WHITE} "
            f"| score={second_result['score']} | positions={second_result['moves_evaluated']} "
            f"| elapsed={second_elapsed:.6f}s"
        )
        print(
            f"White total: positions={first_result['moves_evaluated'] + second_result['moves_evaluated']} "
            f"| elapsed={first_elapsed + second_elapsed:.6f}s"
        )
        print()

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the fixed Nf4+ ... Kg7 ... Nxd5 historical-engine experiment."
    )
    parser.add_argument("--fen", default=DEFAULT_FEN, help="Starting FEN for the experiment.")
    parser.add_argument("--depth", type=int, default=4, help="Search depth for each historical engine.")
    parser.add_argument(
        "--versions",
        nargs="+",
        default=DEFAULT_VERSIONS,
        help="Historical engine versions to include, for example: v1 v1.1 v1.2 v1.3",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.depth < 1:
        parser.error("--depth must be at least 1")

    try:
        return run_experiment(args.versions, args.fen, args.depth)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
