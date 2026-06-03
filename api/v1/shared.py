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
ENDGAME_NON_PAWN_MATERIAL_THRESHOLD = 1600
ENDGAME_MATERIAL_ADVANTAGE_THRESHOLD = 200
ENDGAME_MOP_UP_SCALE = 8
ENDGAME_KING_MOBILITY_SCALE = 12
ENDGAME_PAWN_DANGER_SCALE = 70
ENDGAME_PROMOTION_BONUS = 120
WINNING_ENDGAME_REPEAT_PENALTY = 1000


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


def side_non_pawn_material(board: chess.Board, color: chess.Color) -> int:
    return sum(
        PIECE_VALUES[piece_type] * len(board.pieces(piece_type, color))
        for piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)
    )


def total_non_pawn_material(board: chess.Board) -> int:
    return side_non_pawn_material(board, chess.WHITE) + side_non_pawn_material(board, chess.BLACK)


def has_forcing_mating_material(board: chess.Board, color: chess.Color) -> bool:
    queens = len(board.pieces(chess.QUEEN, color))
    rooks = len(board.pieces(chess.ROOK, color))
    bishops = len(board.pieces(chess.BISHOP, color))
    knights = len(board.pieces(chess.KNIGHT, color))

    if queens or rooks:
        return True

    return bishops >= 2 or (bishops >= 1 and knights >= 1)


def endgame_weight(board: chess.Board) -> float:
    remaining_non_pawn_material = total_non_pawn_material(board)
    weight = 1.0 - (
        min(remaining_non_pawn_material, ENDGAME_NON_PAWN_MATERIAL_THRESHOLD)
        / ENDGAME_NON_PAWN_MATERIAL_THRESHOLD
    )
    return max(0.0, min(1.0, weight))


def manhattan_distance(from_square: int, to_square: int) -> int:
    return abs(chess.square_file(from_square) - chess.square_file(to_square)) + abs(
        chess.square_rank(from_square) - chess.square_rank(to_square)
    )


def center_manhattan_distance(square: int) -> int:
    file_index = chess.square_file(square)
    rank_index = chess.square_rank(square)
    file_distance = min(abs(file_index - 3), abs(file_index - 4))
    rank_distance = min(abs(rank_index - 3), abs(rank_index - 4))
    return file_distance + rank_distance


def force_king_to_corner_endgame_eval(
    board: chess.Board,
    stronger_side: chess.Color,
    weight: float,
) -> int:
    if weight <= 0.0:
        return 0

    friendly_king_square = board.king(stronger_side)
    opponent_king_square = board.king(not stronger_side)
    if friendly_king_square is None or opponent_king_square is None:
        return 0

    losing_king_cmd = center_manhattan_distance(opponent_king_square)
    kings_md = manhattan_distance(friendly_king_square, opponent_king_square)
    raw_score = (4.7 * losing_king_cmd) + (1.6 * (14 - kings_md))
    return int(raw_score * ENDGAME_MOP_UP_SCALE * weight)


def defender_king_mobility(board: chess.Board, losing_side: chess.Color) -> int:
    probe_board = board.copy(stack=False)
    probe_board.turn = losing_side
    losing_king_square = probe_board.king(losing_side)
    if losing_king_square is None:
        return 0

    return sum(1 for move in probe_board.legal_moves if move.from_square == losing_king_square)


def promotion_square_for_pawn(square: int, color: chess.Color) -> int:
    return chess.square(chess.square_file(square), 7 if color == chess.WHITE else 0)


def is_passed_pawn(board: chess.Board, square: int, color: chess.Color) -> bool:
    enemy_color = not color
    file_index = chess.square_file(square)
    rank_index = chess.square_rank(square)

    for enemy_pawn in board.pieces(chess.PAWN, enemy_color):
        enemy_file = chess.square_file(enemy_pawn)
        enemy_rank = chess.square_rank(enemy_pawn)
        if abs(enemy_file - file_index) > 1:
            continue

        if color == chess.WHITE and enemy_rank > rank_index:
            return False
        if color == chess.BLACK and enemy_rank < rank_index:
            return False

    return True


def pawn_promotion_distance(square: int, color: chess.Color) -> int:
    rank_index = chess.square_rank(square)
    return 7 - rank_index if color == chess.WHITE else rank_index


def weaker_side_pawn_danger(board: chess.Board, stronger_side: chess.Color, weight: float) -> int:
    if weight <= 0.0:
        return 0

    weaker_side = not stronger_side
    stronger_king_square = board.king(stronger_side)
    weaker_king_square = board.king(weaker_side)
    if stronger_king_square is None or weaker_king_square is None:
        return 0

    danger = 0
    for pawn_square in board.pieces(chess.PAWN, weaker_side):
        promotion_distance = pawn_promotion_distance(pawn_square, weaker_side)
        advancement_bonus = max(0, 7 - promotion_distance) * ENDGAME_PAWN_DANGER_SCALE
        if promotion_distance <= 1:
            advancement_bonus += ENDGAME_PROMOTION_BONUS

        if is_passed_pawn(board, pawn_square, weaker_side):
            advancement_bonus += ENDGAME_PAWN_DANGER_SCALE

        promotion_square = promotion_square_for_pawn(pawn_square, weaker_side)
        if board.is_attacked_by(weaker_side, promotion_square):
            advancement_bonus += 40
        if board.is_attacked_by(stronger_side, pawn_square):
            advancement_bonus -= 40
        if board.is_attacked_by(stronger_side, promotion_square):
            advancement_bonus -= 60

        occupying_piece = board.piece_at(promotion_square)
        if occupying_piece is not None and occupying_piece.color == stronger_side:
            advancement_bonus -= ENDGAME_PROMOTION_BONUS

        stronger_king_distance_to_pawn = manhattan_distance(stronger_king_square, pawn_square)
        weaker_king_distance_to_pawn = manhattan_distance(weaker_king_square, pawn_square)
        stronger_king_distance_to_promotion = manhattan_distance(stronger_king_square, promotion_square)
        weaker_king_distance_to_promotion = manhattan_distance(weaker_king_square, promotion_square)

        advancement_bonus += max(
            0, stronger_king_distance_to_pawn - weaker_king_distance_to_pawn
        ) * 35
        advancement_bonus += max(
            0, stronger_king_distance_to_promotion - weaker_king_distance_to_promotion
        ) * 50

        danger += max(0, advancement_bonus)

    return int(danger * weight)


def endgame_mop_up_adjustment(board: chess.Board, perspective: chess.Color) -> int:
    if board.is_checkmate():
        return 0

    white_material = evaluate_material(board, chess.WHITE)
    white_bonus = 0
    black_bonus = 0
    weight = endgame_weight(board)

    if (
        white_material >= ENDGAME_MATERIAL_ADVANTAGE_THRESHOLD
        and has_forcing_mating_material(board, chess.WHITE)
    ):
        white_bonus = force_king_to_corner_endgame_eval(board, chess.WHITE, weight)
        white_bonus += (8 - defender_king_mobility(board, chess.BLACK)) * ENDGAME_KING_MOBILITY_SCALE
        white_bonus -= weaker_side_pawn_danger(board, chess.WHITE, weight)

    if (
        white_material <= -ENDGAME_MATERIAL_ADVANTAGE_THRESHOLD
        and has_forcing_mating_material(board, chess.BLACK)
    ):
        black_bonus = force_king_to_corner_endgame_eval(board, chess.BLACK, weight)
        black_bonus += (8 - defender_king_mobility(board, chess.WHITE)) * ENDGAME_KING_MOBILITY_SCALE
        black_bonus -= weaker_side_pawn_danger(board, chess.BLACK, weight)

    score = white_bonus - black_bonus
    return score if perspective == chess.WHITE else -score


def winning_endgame_repetition_adjustment(board: chess.Board, perspective: chess.Color) -> int:
    material_edge = evaluate_material(board, perspective)
    if material_edge <= ENDGAME_MATERIAL_ADVANTAGE_THRESHOLD or endgame_weight(board) <= 0.0:
        return 0

    adjustment = 0
    try:
        if board.is_repetition(2):
            adjustment -= WINNING_ENDGAME_REPEAT_PENALTY + (material_edge // 20)
    except TypeError:
        if board.is_repetition():
            adjustment -= WINNING_ENDGAME_REPEAT_PENALTY + (material_edge // 20)

    if board.can_claim_threefold_repetition():
        adjustment -= WINNING_ENDGAME_REPEAT_PENALTY + (material_edge // 10)

    return adjustment


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


def evaluate_with_endgame_mop_up(board: chess.Board, perspective: chess.Color) -> int:
    return (
        evaluate_with_draw_penalty(board, perspective)
        + endgame_mop_up_adjustment(board, perspective)
        + winning_endgame_repetition_adjustment(board, perspective)
    )


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
