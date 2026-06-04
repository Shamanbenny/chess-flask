import chess

from .v1_0 import choose_move_v1, search_move_v1
from .v1_1 import choose_move_v1_1, search_move_v1_1
from .v1_2 import choose_move_v1_2, search_move_v1_2
from .v1_3 import choose_move_v1_3, search_move_v1_3
from .v1_4 import choose_move_v1_4, search_move_v1_4
from .v1_5 import choose_move_v1_5, search_move_v1_5


def search_move_for_version(
    version: str,
    board: chess.Board,
    depth: int | None = None,
    time_limit_seconds: float | None = None,
) -> dict:
    normalized_version = version.lower()
    if normalized_version in {"1", "v1"}:
        return search_move_v1(board, 3 if depth is None else depth)
    if normalized_version in {"1.1", "v1.1"}:
        return search_move_v1_1(board, 4 if depth is None else depth)
    if normalized_version in {"1.2", "v1.2"}:
        return search_move_v1_2(board, 4 if depth is None else depth)
    if normalized_version in {"1.3", "v1.3"}:
        return search_move_v1_3(board, 4 if depth is None else depth)
    if normalized_version in {"1.4", "v1.4"}:
        return search_move_v1_4(board, 4 if depth is None else depth)
    if normalized_version in {"1.5", "v1.5"}:
        return search_move_v1_5(board, 1.0 if time_limit_seconds is None else time_limit_seconds)
    raise ValueError(f"Unsupported engine version '{version}'")


__all__ = [
    "choose_move_v1",
    "choose_move_v1_1",
    "choose_move_v1_2",
    "choose_move_v1_3",
    "choose_move_v1_4",
    "choose_move_v1_5",
    "search_move_for_version",
]
