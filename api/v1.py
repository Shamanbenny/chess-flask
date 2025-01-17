import chess
import math
from flask import Blueprint, request, jsonify

v1_blueprint = Blueprint('v1', __name__)

@v1_blueprint.route('/chess_v1', methods=['POST'])
def chess_v1():
    """
    [POST] /chess_v1 {MINIMAX ALGORITHM}
    Given a FEN string, uses depth 2 recursive minimax algorithm to return the best move.
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

        def v1_minimax(depth: int, perspective: chess.Color, board: chess.Board):
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
                eval = -v1_minimax(depth - 1, perspective, board)
                board.pop()
                best_eval = max(best_eval, eval)
            
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
            eval = -v1_minimax(2, board.turn, board)
            board.pop()
            if eval > best_eval:
                best_eval = eval
                best_move = move
        
        return jsonify({"move": board.san(best_move)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@v1_blueprint.route('/chess_v1-1', methods=['POST'])
def chess_v1_1():
    """
    [POST] /chess_v1_1 {MINIMAX ALGORITHM WITH ALPHA-BETA PRUNING}
    Given a FEN string, use depth 3 recursive minimax algorithm with alpha-beta pruning to return the best move.
    [REFERENCE] https://en.wikipedia.org/wiki/Alpha%E2%80%93beta_pruning
    """
    try:
        # Extract FEN from the request JSON
        data = request.get_json()
        fen = data.get('fen', '')

        if not fen:
            return jsonify({"error": "FEN string is required"}), 400

        def evaluate_board(board: chess.Board, perspective: chess.Color):
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
            if perspective == chess.WHITE:
                return white_material - black_material
            else:
                return black_material - white_material

        def v1_1_alphabeta(depth: int, alpha: int, beta: int, maximizing_player: bool, board: chess.Board, perspective: chess.Color):
            if depth == 0 or board.is_game_over():
                if board.is_game_over():
                    if board.is_checkmate():
                        # If the current player is in checkmate, it's bad for them
                        return -math.inf if maximizing_player else math.inf
                    return 0  # Stalemate or draw
                return -evaluate_board(board, perspective) if maximizing_player else evaluate_board(board, perspective)
            
            legal_moves = list(board.legal_moves)

            if maximizing_player:
                eval = -math.inf
                for move in legal_moves:
                    board.push(move)
                    eval = max(eval, v1_1_alphabeta(depth - 1, alpha, beta, False, board, perspective))
                    board.pop()
                    if eval >= beta:
                        break  # Beta cutoff
                    alpha = max(alpha, eval)
                return eval
            else:
                eval = math.inf
                for move in legal_moves:
                    board.push(move)
                    eval = min(eval, v1_1_alphabeta(depth - 1, alpha, beta, True, board, perspective))
                    board.pop()
                    if eval <= alpha:
                        break  # Alpha cutoff
                    beta = min(beta, eval)
                return eval
        
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
            eval = v1_1_alphabeta(3, -math.inf, math.inf, False, board, board.turn)
            board.pop()
            if eval > best_eval:
                best_eval = eval
                best_move = move
        
        return jsonify({"move": board.san(best_move)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500