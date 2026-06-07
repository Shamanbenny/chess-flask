import random
import time

import chess
from flask import Blueprint, jsonify, request

from .v2 import choose_move_v2_0, choose_move_v2_9
from .v3.v3_0 import choose_move_v3_0


endpoint_blueprint = Blueprint("endpoint", __name__)
ENGINE_TIME_LIMIT_SECONDS = 1.0


def error_response(message: str, status: int, **debug: object) -> tuple[dict, int]:
    return {
        "error": message,
        "debug": {
            "status": status,
            "reason": message,
            **debug,
        },
    }, status


def validate_board_for_move(fen: str) -> tuple[chess.Board | None, tuple[dict, int] | None]:
    if not fen:
        return None, error_response("FEN string is required", 400, fen_present=False)

    try:
        board = chess.Board(fen)
    except ValueError as exc:
        return None, error_response("Invalid FEN string", 400, fen=fen, exception=str(exc))

    if board.is_game_over():
        if board.is_checkmate():
            return None, error_response("Checkmate", 400, fen=fen, game_over=True, outcome="checkmate")
        if board.is_stalemate():
            return None, error_response("Stalemate", 400, fen=fen, game_over=True, outcome="stalemate")

    legal_moves = list(board.legal_moves)
    if not legal_moves:
        return None, error_response("No legal moves available", 400, fen=fen, legal_move_count=0)

    return board, None


def choose_move_v0(board: chess.Board) -> dict:
    random_move = random.choice(list(board.legal_moves))
    return {
        "move": board.san(random_move),
        "debug": {
            "version": "v0",
            "engine": "random_legal_move",
            "selected_move_uci": random_move.uci(),
            "legal_move_count": board.legal_moves.count(),
        },
    }


def generate_engine_response(version: str, fen: str, payload: dict | None = None) -> tuple[dict, int]:
    normalized_version = version.lower()
    payload = payload or {}
    board, error = validate_board_for_move(fen)
    if error is not None:
        body, status = error
        body["debug"] = {
            **body.get("debug", {}),
            "version": normalized_version,
        }
        return body, status

    if normalized_version == "v0":
        return choose_move_v0(board), 200
    if normalized_version == "v2.0":
        return choose_move_v2_0(board, time_limit_seconds=ENGINE_TIME_LIMIT_SECONDS), 200
    if normalized_version == "v2.9":
        return choose_move_v2_9(board, time_limit_seconds=ENGINE_TIME_LIMIT_SECONDS), 200
    if normalized_version == "v3.0":
        return choose_move_v3_0(
            board,
            time_limit_seconds=ENGINE_TIME_LIMIT_SECONDS,
            context_id=payload.get("context_id") or payload.get("game_id"),
            reset_context=bool(payload.get("reset_context", False)),
        ), 200
    return error_response(f"Unsupported version '{version}'", 400, version=normalized_version)


def timed_engine_response(version: str, fen: str, payload: dict | None = None) -> tuple[dict, int]:
    start_time = time.time()
    body, status = generate_engine_response(version, fen, payload)
    processing_time = time.time() - start_time
    body = {
        **body,
        "processing_time": processing_time,
        "debug": {
            **body.get("debug", {}),
            "processing_time": processing_time,
        },
    }
    return body, status


def unhandled_error_response(version: str, exc: Exception):
    return jsonify({
        "error": str(exc),
        "debug": {
            "version": version,
            "status": 500,
            "reason": "Unhandled engine error",
            "exception": type(exc).__name__,
        },
    }), 500


def handle_engine_request(version: str):
    data = request.get_json() or {}
    body, status = timed_engine_response(version, data.get("fen", ""), data)
    return jsonify(body), status


@endpoint_blueprint.route("/chess_v0", methods=["POST"])
def chess_v0():
    try:
        return handle_engine_request("v0")
    except Exception as exc:
        return unhandled_error_response("v0", exc)


@endpoint_blueprint.route("/chess_v2_9", methods=["POST"])
def chess_v2_9():
    try:
        return handle_engine_request("v2.9")
    except Exception as exc:
        return unhandled_error_response("v2.9", exc)


@endpoint_blueprint.route("/chess_v2_0", methods=["POST"])
def chess_v2_0():
    try:
        return handle_engine_request("v2.0")
    except Exception as exc:
        return unhandled_error_response("v2.0", exc)


@endpoint_blueprint.route("/chess_v3_0", methods=["POST"])
def chess_v3_0():
    try:
        return handle_engine_request("v3.0")
    except Exception as exc:
        return unhandled_error_response("v3.0", exc)
