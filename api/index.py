from flask import Flask, request, jsonify
from flask_cors import CORS
import chess
import random
import math

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": ["https://sneakyowl.net", "https://www.sneakyowl.net"]}})

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

        def evaluate_board(board: chess.Board):
            PIECE_VALUES = {
                chess.PAWN: 100,
                chess.KNIGHT: 300,
                chess.BISHOP: 300,
                chess.ROOK: 500,
                chess.QUEEN: 900,
                chess.KING: 0
            }

            white_material = sum(PIECE_VALUES[piece_type] * len(board.pieces(piece_type, chess.WHITE)) for piece_type in PIECE_VALUES)
            black_material = sum(PIECE_VALUES[piece_type] * len(board.pieces(piece_type, chess.BLACK)) for piece_type in PIECE_VALUES)
            return white_material - black_material

        def v1_minimax(perspective: chess.Color, depth: int, board: chess.Board):
            if depth == 0:
                return evaluate_board(board) if perspective == chess.WHITE else -evaluate_board(board)
            
            if board.is_game_over():
                if board.is_checkmate():
                    return -math.inf if board.turn == perspective else math.inf
                elif board.is_stalemate():
                    # [Depends heavily on the bot's motivation]
                    # If the bot is already winning, then stalemate is bad
                    # If the bot is losing or equal, then stalemate is neutral
                    prev_board = board.copy()
                    prev_board.pop()
                    prev_eval = evaluate_board(prev_board) if perspective == chess.WHITE else -evaluate_board(prev_board)
                    if prev_eval > 0:
                        return -math.inf
                    else:
                        return 0
            
            best_eval = -math.inf

            legal_moves = list(board.legal_moves)
            for move in legal_moves:
                board.push(move)
                # Note the negation of the returned evaluation (This is what makes it a minimax algorithm)
                #   >> Minimize the opponent's evaluation, while Maximize the bot's evaluation
                eval = -v1_minimax(perspective, depth - 1, board)
                best_eval = max(best_eval, eval)
                board.pop()
            
            return best_eval
        
        board = chess.Board(fen)
        legal_moves = list(board.legal_moves)
        if board.is_game_over():
            if board.is_checkmate():
                return jsonify({"error": "Checkmate"}), 400
            elif board.is_stalemate():
                return jsonify({"error": "Stalemate"}), 400
        if not legal_moves:
            return jsonify({"error": "No legal moves available"}), 400
        
        best_move = None
        best_eval = -math.inf
        for move in legal_moves:
            board.push(move)
            eval = -v1_minimax(board.turn, 2, board)
            if eval > best_eval:
                best_eval = eval
                best_move = move
            board.pop()
        
        return jsonify({"move": board.san(best_move)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500