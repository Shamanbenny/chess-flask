import random
import time

import chess
from flask import Blueprint, jsonify, request

from .v2 import choose_move_v2_0


endpoint_blueprint = Blueprint("endpoint", __name__)
ENGINE_TIME_LIMIT_SECONDS = 1.0


def validate_board_for_move(fen: str) -> tuple[chess.Board | None, tuple[dict, int] | None]:
    if not fen:
        return None, ({"error": "FEN string is required"}, 400)

    board = chess.Board(fen)
    if board.is_game_over():
        if board.is_checkmate():
            return None, ({"error": "Checkmate"}, 400)
        if board.is_stalemate():
            return None, ({"error": "Stalemate"}, 400)

    legal_moves = list(board.legal_moves)
    if not legal_moves:
        return None, ({"error": "No legal moves available"}, 400)

    return board, None


def choose_move_v0(board: chess.Board) -> dict:
    random_move = random.choice(list(board.legal_moves))
    return {"move": board.san(random_move)}


def generate_engine_response(version: str, fen: str) -> tuple[dict, int]:
    board, error = validate_board_for_move(fen)
    if error is not None:
        return error

    normalized_version = version.lower()
    if normalized_version == "v0":
        return choose_move_v0(board), 200
    if normalized_version == "v2.0":
        return choose_move_v2_0(board, time_limit_seconds=ENGINE_TIME_LIMIT_SECONDS), 200
    return {"error": f"Unsupported version '{version}'"}, 400


def timed_engine_response(version: str, fen: str) -> tuple[dict, int]:
    start_time = time.time()
    body, status = generate_engine_response(version, fen)
    if status == 200:
        body = {
            **body,
            "processing_time": time.time() - start_time,
        }
    return body, status


def handle_engine_request(version: str):
    data = request.get_json() or {}
    body, status = timed_engine_response(version, data.get("fen", ""))
    return jsonify(body), status


@endpoint_blueprint.route("/chess_v0", methods=["POST"])
def chess_v0():
    try:
        return handle_engine_request("v0")
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@endpoint_blueprint.route("/chess_v2_0", methods=["POST"])
def chess_v2_0():
    try:
        return handle_engine_request("v2.0")
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
