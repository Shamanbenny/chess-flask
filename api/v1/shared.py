import chess


PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 300,
    chess.BISHOP: 300,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

DRAW_BASE_PENALTY = 120
THREEFOLD_REPETITION_PENALTY = 90
REPEAT_POSITION_PENALTY = 35


def material_balance(board: chess.Board) -> int:
    white_material = sum(
        PIECE_VALUES[piece_type] * len(board.pieces(piece_type, chess.WHITE))
        for piece_type in PIECE_VALUES
    )
    black_material = sum(
        PIECE_VALUES[piece_type] * len(board.pieces(piece_type, chess.BLACK))
        for piece_type in PIECE_VALUES
    )
    return white_material - black_material


def evaluate_material(board: chess.Board, perspective: chess.Color) -> int:
    score = material_balance(board)
    return score if perspective == chess.WHITE else -score


def repetition_draw_adjustment(board: chess.Board, perspective: chess.Color) -> int:
    adjustment = 0

    try:
        if board.is_repetition(2):
            adjustment -= REPEAT_POSITION_PENALTY
    except TypeError:
        if board.is_repetition():
            adjustment -= THREEFOLD_REPETITION_PENALTY

    if board.can_claim_threefold_repetition():
        adjustment -= THREEFOLD_REPETITION_PENALTY

    if board.can_claim_draw():
        adjustment -= DRAW_BASE_PENALTY

    if board.is_game_over() and not board.is_checkmate():
        material_edge = max(evaluate_material(board, perspective), 0)
        adjustment -= DRAW_BASE_PENALTY + (material_edge // 10)

    return adjustment


def evaluate_with_draw_penalty(board: chess.Board, perspective: chess.Color) -> int:
    return evaluate_material(board, perspective) + repetition_draw_adjustment(board, perspective)


def score_move_for_ordering(move: chess.Move, board: chess.Board) -> int:
    score = 0

    attacker_piece = board.piece_at(move.from_square)
    attacker_value = PIECE_VALUES.get(attacker_piece.piece_type, 0) if attacker_piece else 0
    captured_piece = board.piece_at(move.to_square)

    if captured_piece is None and board.is_en_passant(move):
        captured_value = PIECE_VALUES[chess.PAWN]
    else:
        captured_value = PIECE_VALUES.get(captured_piece.piece_type, 0) if captured_piece else 0

    if board.is_capture(move):
        score += 10_000 + (10 * captured_value) - attacker_value

    if move.promotion:
        score += 8_000 + PIECE_VALUES.get(move.promotion, 0)

    board.push(move)
    if board.is_checkmate():
        score += 100_000
    elif board.is_check():
        score += 2_000

    attackers = board.attackers(board.turn, move.to_square)
    pawn_attackers = [sq for sq in attackers if board.piece_type_at(sq) == chess.PAWN]
    if pawn_attackers:
        score -= attacker_value
    board.pop()

    return score


def ordered_legal_moves(board: chess.Board) -> list[chess.Move]:
    return sorted(board.legal_moves, key=lambda move: -score_move_for_ordering(move, board))
