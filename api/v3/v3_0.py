"""Python V3.0 wrapper: opening book plus warm-instance TT contexts."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

import chess

from ..opening_book import try_get_opening_move_with_debug
from ..v2.v2_0 import DEFAULT_TIME_LIMIT_SECONDS, TranspositionTable, _position_key
from ..v2.v2_9 import search_move_v2_9


MAX_CONTEXTS = 128
CONTEXT_TTL_SECONDS = 30 * 60


@dataclass(slots=True)
class EngineContext:
    transposition_table: TranspositionTable = field(default_factory=TranspositionTable)
    created_at: float = field(default_factory=time.monotonic)
    last_used_at: float = field(default_factory=time.monotonic)
    search_count: int = 0
    lock: threading.RLock = field(default_factory=threading.RLock)


_CONTEXTS: dict[str, EngineContext] = {}
_CONTEXTS_LOCK = threading.RLock()


def choose_move_v3_0(
    board: chess.Board,
    time_limit_seconds: float = DEFAULT_TIME_LIMIT_SECONDS,
    context_id: str | None = None,
    reset_context: bool = False,
) -> dict:
    opening_move, opening_debug = try_get_opening_move_with_debug(board)
    context: EngineContext | None = None
    context_debug: dict[str, object]
    if reset_context and context_id:
        context, context_debug = _get_context(context_id, reset_context)
    else:
        context_debug = _skipped_context_debug(context_id, reset_context, "opening_book_move")

    if opening_move is not None:
        return {
            "move": board.san(opening_move),
            "debug": {
                "version": "v3.0",
                "engine": "python_v3_0_opening_book",
                "selected_move_uci": opening_move.uci(),
                "selected_move_san": board.san(opening_move),
                "opening_book": opening_debug,
                "tt_context": context_debug,
            },
        }

    if context is None:
        context, context_debug = _get_context(context_id, reset_context)

    if context is None:
        result = search_move_v2_9(board, time_limit_seconds=time_limit_seconds)
    else:
        with context.lock:
            context_debug["tt_entries_before"] = context.transposition_table.entry_count
            result = search_move_v2_9(
                board,
                time_limit_seconds=time_limit_seconds,
                transposition_table=context.transposition_table,
                position_key_func=_history_aware_position_key,
            )
            context.search_count += 1
            context.last_used_at = time.monotonic()
            context_debug["tt_entries_after"] = context.transposition_table.entry_count
            context_debug["search_count_after"] = context.search_count

    return {
        "move": result["move_san"],
        "debug": {
            "version": "v3.0",
            "engine": "python_v3_0_v2_9_search_with_context",
            "selected_move_uci": result["move"].uci(),
            "selected_move_san": result["move_san"],
            "score": result["score"],
            "completed_depth": result["completed_depth"],
            "time_limit_seconds": result["time_limit_seconds"],
            "timed_out": result["timed_out"],
            "moves_evaluated": result["moves_evaluated"],
            "nodes_searched": result["nodes_searched"],
            "tt_entries": result["tt_entries"],
            "tt_probes": result["tt_probes"],
            "tt_hits": result["tt_hits"],
            "tt_cutoffs": result["tt_cutoffs"],
            "opening_book": opening_debug,
            "tt_context": context_debug,
        },
    }


def _get_context(context_id: str | None, reset_context: bool) -> tuple[EngineContext | None, dict[str, object]]:
    normalized_id = context_id.strip() if context_id else ""
    debug: dict[str, object] = {
        "enabled": bool(normalized_id),
        "context_id": normalized_id or None,
        "reset_requested": reset_context,
        "context_found": False,
        "context_created": False,
        "context_reset": False,
        "evicted_context_count": 0,
        "cache_size_after": None,
        "tt_entries_before": None,
        "tt_entries_after": None,
        "search_count_before": None,
        "search_count_after": None,
        "skipped_reason": None,
    }

    if not normalized_id:
        debug["skipped_reason"] = "missing_game_id_or_context_id"
        return None, debug

    now = time.monotonic()
    with _CONTEXTS_LOCK:
        evicted = _evict_expired_locked(now)
        context = _CONTEXTS.get(normalized_id)
        debug["context_found"] = context is not None

        if reset_context and context is not None:
            context = EngineContext()
            _CONTEXTS[normalized_id] = context
            debug["context_reset"] = True
        elif context is None:
            context = EngineContext()
            _CONTEXTS[normalized_id] = context
            debug["context_created"] = True

        evicted += _evict_over_limit_locked()
        debug["evicted_context_count"] = evicted
        debug["cache_size_after"] = len(_CONTEXTS)
        debug["search_count_before"] = context.search_count

    return context, debug


def _history_aware_position_key(board: chess.Board) -> object:
    return (
        _position_key(board),
        board.halfmove_clock,
        tuple(move.uci() for move in board.move_stack),
    )


def _skipped_context_debug(context_id: str | None, reset_context: bool, reason: str) -> dict[str, object]:
    return {
        "enabled": bool(context_id and context_id.strip()),
        "context_id": context_id.strip() if context_id else None,
        "reset_requested": reset_context,
        "context_found": None,
        "context_created": False,
        "context_reset": False,
        "tt_entries_before": None,
        "tt_entries_after": None,
        "skipped_reason": reason,
    }


def _evict_expired_locked(now: float) -> int:
    expired = [
        context_id
        for context_id, context in _CONTEXTS.items()
        if now - context.last_used_at > CONTEXT_TTL_SECONDS
    ]
    for context_id in expired:
        del _CONTEXTS[context_id]
    return len(expired)


def _evict_over_limit_locked() -> int:
    evicted = 0
    while len(_CONTEXTS) > MAX_CONTEXTS:
        oldest_id = min(_CONTEXTS, key=lambda key: _CONTEXTS[key].last_used_at)
        del _CONTEXTS[oldest_id]
        evicted += 1
    return evicted
