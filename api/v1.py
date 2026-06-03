import time
import chess
import math
from flask import Blueprint, request, jsonify

v1_blueprint = Blueprint('v1', __name__)

@v1_blueprint.route('/chess_v1', methods=['POST'])
def chess_v1():
    """
    [POST] /chess_v1 {MINIMAX ALGORITHM}
    Given a FEN string, search one root move plus 2 recursive plies using
    minimax to return the best move.
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
    Given a FEN string, search one root move plus 3 recursive plies using
    minimax with alpha-beta pruning to return the best move.
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
    Given a FEN string, search one root move plus 3 recursive plies using
    alpha-beta pruning and heuristic move ordering to return the best move.
    [REFERENCE] https://en.wikipedia.org/wiki/Alpha%E2%80%93beta_pruning#Heuristic_improvements
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

        def score_move_for_ordering(move: chess.Move, board: chess.Board):
            # Move ordering only affects search efficiency, not the final
            # evaluation formula. The goal is to search "likely good" moves
            # first so alpha-beta pruning can cut off more branches earlier.
            score = 0

            attacker_piece = board.piece_at(move.from_square)
            attacker_value = PIECE_VALUES.get(attacker_piece.piece_type, 0) if attacker_piece else 0
            captured_piece = board.piece_at(move.to_square)

            # En passant captures land on an empty square, so the captured pawn
            # must be inferred manually.
            if captured_piece is None and board.is_en_passant(move):
                captured_value = PIECE_VALUES[chess.PAWN]
            else:
                captured_value = PIECE_VALUES.get(captured_piece.piece_type, 0) if captured_piece else 0

            # MVV-LVA style ordering: prefer winning captures first.
            # [REFERENCE] https://www.chessprogramming.org/MVV-LVA
            if board.is_capture(move):
                score += 10_000 + (10 * captured_value) - attacker_value

            # Promotions often change the position drastically and should be
            # searched early even when they are not captures.
            if move.promotion:
                score += 8_000 + PIECE_VALUES.get(move.promotion, 0)

            # We briefly make the move on the current board, inspect the
            # resulting tactical features, then undo it. This avoids copying
            # the board for every ordering score.
            board.push(move)

            # Checking and mating moves are usually strong forcing moves and
            # give alpha-beta more opportunities to prune.
            if board.is_checkmate():
                score += 100_000
            elif board.is_check():
                score += 2_000

            # Penalize moves that place the moved piece on a square immediately
            # attacked by an enemy pawn. Pawn attacks are cheap to detect and
            # often punish naive material grabs.
            attackers = board.attackers(board.turn, move.to_square)
            pawn_attackers = [sq for sq in attackers if board.piece_type_at(sq) == chess.PAWN]
            if pawn_attackers:
                score -= attacker_value

            board.pop()
            return score

        def ordered_legal_moves(board: chess.Board):
            return sorted(board.legal_moves, key=lambda move: -score_move_for_ordering(move, board))

        def v1_2_alphabeta(depth: int, alpha: int, beta: int, maximizing_player: bool, board: chess.Board, perspective: chess.Color):
            nonlocal moves_evaluated

            if depth == 0 or board.is_game_over():
                if board.is_game_over():
                    if board.is_checkmate():
                        # If the current player is in checkmate, it's bad for them
                        return -math.inf if maximizing_player else math.inf
                    return 0  # Stalemate or draw
                return -evaluate_board(board, perspective) if maximizing_player else evaluate_board(board, perspective)
            
            # Search promising moves first so alpha-beta can cut off more of
            # the remaining move list.
            legal_moves = ordered_legal_moves(board)

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
        legal_moves = ordered_legal_moves(board)
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
            # The root loop is also ordered so we spend time on stronger
            # candidates first instead of only ordering inside recursion.
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
