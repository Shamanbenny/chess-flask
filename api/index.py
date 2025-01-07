from flask import Flask, request, jsonify
from flask_cors import CORS
import chess
import random

app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    return 'Why are you here? 0.0'

@app.route('/test', methods=['POST'])
def test():
    try:
        data = request.get_json()
        print(data)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/chess_v0', methods=['POST'])
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
            return jsonify({"error": "Game is already over"}), 400

        # Get all legal moves and choose one at random
        legal_moves = list(board.legal_moves)
        if not legal_moves:
            return jsonify({"error": "No legal moves available"}), 400

        random_move = random.choice(legal_moves)

        return jsonify({"move": board.san(random_move)})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/chess_v1', methods=['POST'])
def chess_v1():
    """
    [POST] /chess_v1 {MINIMAX ALGORITHM}
    Given a FEN string, uses depth 5 recursive minimax algorithm to return the best move.
    CURRENTLY: Returns a random legal move.
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
            return jsonify({"error": "Game is already over"}), 400

        # Get all legal moves and choose one at random
        legal_moves = list(board.legal_moves)
        if not legal_moves:
            return jsonify({"error": "No legal moves available"}), 400

        random_move = random.choice(legal_moves)

        return jsonify({"move": board.san(random_move)})

    except Exception as e:
        return jsonify({"error": str(e)}), 500