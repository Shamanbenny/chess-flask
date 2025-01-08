import chess
import random
from flask import Blueprint, request, jsonify

v0_blueprint = Blueprint('v0', __name__)

@v0_blueprint.route('/chess_v0', methods=['POST'])
def chess_v0():
    """
    [POST] /chess_v0 {RANDOM MOVE}
    Given a FEN string, return a random legal move.
    """
    try:
        # Extract FEN from the request JSON
        data = request.get_json()
        fen = data.get('fen', '')

        if not fen:
            return jsonify({"error": "FEN string is required"}), 400

        # Initialize the chess board with the given FEN
        board = chess.Board(fen)

        if board.is_game_over():
            if board.is_checkmate():
                return jsonify({"error": "Checkmate"}), 400
            elif board.is_stalemate():
                return jsonify({"error": "Stalemate"}), 400

        # Get all legal moves and choose one at random
        legal_moves = list(board.legal_moves)
        if not legal_moves:
            return jsonify({"error": "No legal moves available"}), 400

        random_move = random.choice(legal_moves)

        return jsonify({"move": board.san(random_move)})

    except Exception as e:
        return jsonify({"error": str(e)}), 500