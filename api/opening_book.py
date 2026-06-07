"""Shared opening-book lookup loader for Python engines."""

from __future__ import annotations

import random
from functools import lru_cache
from pathlib import Path
from time import perf_counter

import chess


LOOKUP_FILE = "Openings.lookup.tsv"
STARTING_PIECE_COUNT = 32


def try_get_opening_move(board: chess.Board) -> chess.Move | None:
    """Return a random exact-match opening move, or None when search should run."""
    move, _debug = try_get_opening_move_with_debug(board)
    return move


def try_get_opening_move_with_debug(board: chess.Board) -> tuple[chess.Move | None, dict[str, object]]:
    """Return a random exact-match opening move plus cache/load diagnostics."""
    cache_before = _load_lookup.cache_info()
    lookup_was_loaded = cache_before.currsize > 0

    debug: dict[str, object] = {
        "enabled": True,
        "lookup_file": LOOKUP_FILE,
        "lookup_was_loaded_before_call": lookup_was_loaded,
        "lookup_loaded_during_call": False,
        "lookup_reused_from_process_cache": lookup_was_loaded,
        "position_piece_count": len(board.piece_map()),
        "requires_full_starting_piece_count": STARTING_PIECE_COUNT,
        "skipped_reason": None,
        "matched_position": False,
        "candidate_move_count": 0,
        "legal_candidate_move_count": 0,
        "selected_move_uci": None,
    }

    if len(board.piece_map()) != STARTING_PIECE_COUNT:
        debug["skipped_reason"] = "piece_count_not_starting_position_count"
        return None, debug

    load_started = perf_counter()
    lookup = _load_lookup()
    load_elapsed = perf_counter() - load_started
    cache_after = _load_lookup.cache_info()

    debug.update(
        {
            "lookup_loaded_during_call": not lookup_was_loaded and cache_after.currsize > 0,
            "lookup_reused_from_process_cache": lookup_was_loaded and cache_after.hits > cache_before.hits,
            "lookup_position_count": len(lookup),
            "lookup_load_elapsed_seconds": load_elapsed,
            "cache_hits_before": cache_before.hits,
            "cache_hits_after": cache_after.hits,
            "cache_misses_before": cache_before.misses,
            "cache_misses_after": cache_after.misses,
        }
    )

    if not lookup:
        debug["skipped_reason"] = "lookup_file_missing_or_empty"
        return None, debug

    fen_key = _normalize_fen_key(board.fen())
    debug["fen_key"] = fen_key

    candidates = lookup.get(fen_key)
    if not candidates:
        debug["skipped_reason"] = "position_not_in_lookup"
        return None, debug

    debug["matched_position"] = True
    debug["candidate_move_count"] = len(candidates)

    legal_uci = {move.uci(): move for move in board.legal_moves}
    legal_candidates = [uci for uci in candidates if uci in legal_uci]
    debug["legal_candidate_move_count"] = len(legal_candidates)
    if not legal_candidates:
        debug["skipped_reason"] = "lookup_moves_not_legal"
        return None, debug

    selected_uci = random.choice(legal_candidates)
    debug["selected_move_uci"] = selected_uci
    return legal_uci[selected_uci], debug


def _normalize_fen_key(fen: str) -> str:
    return " ".join(fen.split()[:4])


@lru_cache(maxsize=1)
def _load_lookup() -> dict[str, tuple[str, ...]]:
    path = _find_repo_root() / LOOKUP_FILE
    if not path.exists():
        return {}

    lookup: dict[str, tuple[str, ...]] = {}
    with path.open("r", encoding="utf-8") as file:
        for raw_line in file:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            try:
                fen_key, moves = line.split("\t", 1)
            except ValueError:
                continue

            parsed_moves = tuple(move for move in moves.split(",") if move)
            if parsed_moves:
                lookup[fen_key] = parsed_moves

    return lookup


def _find_repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in (current, *current.parents):
        if (parent / "README.md").exists() and (parent / "engine_csharp").is_dir():
            return parent

    return Path.cwd()
