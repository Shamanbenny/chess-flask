from flask import Flask, request, jsonify
import chess
import random

app = Flask(__name__)

@app.route('/')
def home():
    return 'Welcome to Shamanbenny/chess-flask/api!'

@app.route('/get_best_move', methods=['POST'])
def get_best_move():
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

        return jsonify({"best_move": board.san(random_move)})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    