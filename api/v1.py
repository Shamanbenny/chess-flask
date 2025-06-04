import time
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
        start_time = time.time()
        moves_evaluated = 0
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
            nonlocal moves_evaluated

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
                moves_evaluated += 1
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
            moves_evaluated += 1
            eval = -v1_minimax(2, board.turn, board)
            board.pop()
            if eval > best_eval:
                best_eval = eval
                best_move = move
        
        return jsonify({"move": board.san(best_move),
                        "processing_time": time.time() - start_time,
                        "moves_evaluated": moves_evaluated
                        })
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
        start_time = time.time()
        moves_evaluated = 0
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
            nonlocal moves_evaluated
            
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
                    moves_evaluated += 1
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
                    moves_evaluated += 1
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
            moves_evaluated += 1
            eval = v1_1_alphabeta(3, -math.inf, math.inf, False, board, board.turn)
            board.pop()
            if eval > best_eval:
                best_eval = eval
                best_move = move
        
        return jsonify({"move": board.san(best_move),
                        "processing_time": time.time() - start_time,
                        "moves_evaluated": moves_evaluated
                        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@v1_blueprint.route('/chess_v1-2', methods=['POST'])
def chess_v1_2():
    """
    [POST] /chess_v1_2 {MINIMAX ALGORITHM WITH ALPHA-BETA PRUNING AND MOVE ORDERING}
    Given a FEN string, use depth 3 recursive minimax algorithm with alpha-beta pruning to return the best move.
    [REFERENCE] https://en.wikipedia.org/wiki/Alpha%E2%80%93beta_pruning
    """
    try:
        start_time = time.time()
        moves_evaluated = 0
        # Extract FEN from the request JSON
        data = request.get_json()
        fen = data.get('fen', '')

        if not fen:
            return jsonify({"error": "FEN string is required"}), 400
        
        PIECE_VALUES = {
            chess.PAWN: 100,
            chess.KNIGHT: 300,
            chess.BISHOP: 300,
            chess.ROOK: 500,
            chess.QUEEN: 900,
            chess.KING: 0
        }

        def evaluate_board(board: chess.Board, perspective: chess.Color):
            white_material = sum(PIECE_VALUES[piece_type] * len(board.pieces(piece_type, chess.WHITE)) for piece_type in PIECE_VALUES)
            black_material = sum(PIECE_VALUES[piece_type] * len(board.pieces(piece_type, chess.BLACK)) for piece_type in PIECE_VALUES)
            if perspective == chess.WHITE:
                return white_material - black_material
            else:
                return black_material - white_material
            
        def get_move_score(move: chess.Move, board: chess.Board):
            score = 0

            # [PART 1] Basic move scoring based on current board state
            captured_piece = board.piece_at(move.to_square)
            captured_value = PIECE_VALUES.get(captured_piece.piece_type, 0) if captured_piece else 0
            attacker_piece = board.piece_at(move.from_square)
            attacker_value = PIECE_VALUES.get(attacker_piece.piece_type, 0) if attacker_piece else 0

            # Capture heuristic
            if board.is_capture(move):
                score += captured_value - attacker_value
            # Promotion heuristic
            if move.promotion:
                score += PIECE_VALUES.get(move.promotion, 0)
            
            # [PART 2] Slightly advanced move scoring based on the potential state of the board given the move
            board_copy = board.copy()
            board_copy.push(move)
            
            # Penalize moving our pieces to squares where they can be captured by an opponent's pawn
            to_square = move.to_square
            color_after_move = board_copy.turn
            attackers = board_copy.attackers(color_after_move, to_square)
            pawn_attackers = [sq for sq in attackers if board_copy.piece_type_at(sq) == chess.PAWN]
            if pawn_attackers:
                score -= attacker_value
            
            return score

        def v1_2_alphabeta(depth: int, alpha: int, beta: int, maximizing_player: bool, board: chess.Board, perspective: chess.Color):
            nonlocal moves_evaluated

            if depth == 0 or board.is_game_over():
                if board.is_game_over():
                    if board.is_checkmate():
                        # If the current player is in checkmate, it's bad for them
                        return -math.inf if maximizing_player else math.inf
                    return 0  # Stalemate or draw
                return -evaluate_board(board, perspective) if maximizing_player else evaluate_board(board, perspective)
            
            # Order moves by heuristic score
            legal_moves = sorted(board.legal_moves, key=lambda m: -get_move_score(m, board))

            if maximizing_player:
                eval = -math.inf
                for move in legal_moves:
                    board.push(move)
                    moves_evaluated += 1
                    eval = max(eval, v1_2_alphabeta(depth - 1, alpha, beta, False, board, perspective))
                    board.pop()
                    if eval >= beta:
                        break  # Beta cutoff
                    alpha = max(alpha, eval)
                return eval
            else:
                eval = math.inf
                for move in legal_moves:
                    board.push(move)
                    moves_evaluated += 1
                    eval = min(eval, v1_2_alphabeta(depth - 1, alpha, beta, True, board, perspective))
                    board.pop()
                    if eval <= alpha:
                        break  # Alpha cutoff
                    beta = min(beta, eval)
                return eval
        
        board = chess.Board(fen)
        legal_moves = sorted(board.legal_moves, key=lambda m: -get_move_score(m, board))
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
            moves_evaluated += 1
            eval = v1_2_alphabeta(3, -math.inf, math.inf, False, board, board.turn)
            board.pop()
            if eval > best_eval:
                best_eval = eval
                best_move = move
        
        return jsonify({"move": board.san(best_move),
                        "processing_time": time.time() - start_time,
                        "moves_evaluated": moves_evaluated
                        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500