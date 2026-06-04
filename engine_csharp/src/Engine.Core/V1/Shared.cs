using Chess;

namespace Engine.Core.V1;

internal static class Shared
{
    internal static readonly Dictionary<char, int> PieceValues = new()
    {
        ['p'] = 100,
        ['n'] = 300,
        ['b'] = 300,
        ['r'] = 500,
        ['q'] = 900,
        ['k'] = 0,
    };

    internal const int DrawBasePenalty = 120;
    internal const int ThreefoldRepetitionPenalty = 90;
    internal const int RepeatPositionPenalty = 35;
    internal const int EndgameNonPawnMaterialThreshold = 1600;
    internal const int EndgameMaterialAdvantageThreshold = 200;
    internal const int EndgameMopUpScale = 8;
    internal const int EndgameKingMobilityScale = 12;
    internal const int EndgamePawnDangerScale = 70;
    internal const int EndgamePromotionBonus = 120;
    internal const int WinningEndgameRepeatPenalty = 1000;
    internal const int DeltaPruningMargin = 200;
    internal const int PositiveInfinity = 1_000_000_000;
    internal const int NegativeInfinity = -PositiveInfinity;

    internal static int MaterialBalance(BoardState board)
    {
        var white = SumMaterial(board, PieceColor.White);
        var black = SumMaterial(board, PieceColor.Black);
        return white - black;
    }

    internal static int EvaluateMaterial(BoardState board, PieceColor perspective)
    {
        var score = MaterialBalance(board);
        return perspective == PieceColor.White ? score : -score;
    }

    internal static int EvaluateWithDrawPenalty(BoardState board, PieceColor perspective)
    {
        return EvaluateMaterial(board, perspective) + RepetitionDrawAdjustment(board, perspective);
    }

    internal static int EvaluateWithEndgameMopUp(BoardState board, PieceColor perspective)
    {
        return EvaluateWithDrawPenalty(board, perspective)
            + EndgameMopUpAdjustment(board, perspective)
            + WinningEndgameRepetitionAdjustment(board, perspective);
    }

    internal static List<Move> OrderedLegalMoves(BoardState board)
    {
        return board.LegalMoves()
            .OrderByDescending(move => ScoreMoveForOrdering(move, board))
            .ToList();
    }

    internal static int CapturedPieceValue(BoardState board, Move move)
    {
        if (move.CapturedPiece is not null)
        {
            return PieceValue(move.CapturedPiece);
        }

        if (move.IsEnPassant)
        {
            return PieceValues['p'];
        }

        return 0;
    }

    internal static int PromotionGain(Move move)
    {
        if (!move.IsPromotion || move.Promotion is null)
        {
            return 0;
        }

        return PieceValue(move.Promotion) - PieceValues['p'];
    }

    internal static bool IsObviouslyLosingCapture(BoardState board, Move move)
    {
        if (!board.IsCapture(move) || move.IsPromotion)
        {
            return false;
        }

        return PieceValue(move.Piece) > CapturedPieceValue(board, move);
    }

    internal static bool IsDeltaPruned(BoardState board, Move move, int standPat, int alpha)
    {
        var materialSwing = CapturedPieceValue(board, move) + PromotionGain(move);
        return standPat + materialSwing + DeltaPruningMargin < alpha;
    }

    private static int SumMaterial(BoardState board, PieceColor color)
    {
        var total = 0;
        foreach (var pieceType in new[] { 'p', 'n', 'b', 'r', 'q', 'k' })
        {
            total += PieceValues[pieceType] * board.SquaresWithPiece(pieceType, color).Count();
        }

        return total;
    }

    private static int SideNonPawnMaterial(BoardState board, PieceColor color)
    {
        return board.SquaresWithPiece('n', color).Count() * PieceValues['n']
            + board.SquaresWithPiece('b', color).Count() * PieceValues['b']
            + board.SquaresWithPiece('r', color).Count() * PieceValues['r']
            + board.SquaresWithPiece('q', color).Count() * PieceValues['q'];
    }

    private static int TotalNonPawnMaterial(BoardState board)
    {
        return SideNonPawnMaterial(board, PieceColor.White) + SideNonPawnMaterial(board, PieceColor.Black);
    }

    private static bool HasForcingMatingMaterial(BoardState board, PieceColor color)
    {
        var queens = board.SquaresWithPiece('q', color).Count();
        var rooks = board.SquaresWithPiece('r', color).Count();
        var bishops = board.SquaresWithPiece('b', color).Count();
        var knights = board.SquaresWithPiece('n', color).Count();

        if (queens > 0 || rooks > 0)
        {
            return true;
        }

        return bishops >= 2 || (bishops >= 1 && knights >= 1);
    }

    private static double EndgameWeight(BoardState board)
    {
        var remaining = TotalNonPawnMaterial(board);
        var weight = 1.0 - (Math.Min(remaining, EndgameNonPawnMaterialThreshold) / (double)EndgameNonPawnMaterialThreshold);
        return Math.Clamp(weight, 0.0, 1.0);
    }

    private static int EndgameMopUpAdjustment(BoardState board, PieceColor perspective)
    {
        if (board.IsCheckmate)
        {
            return 0;
        }

        var whiteMaterial = EvaluateMaterial(board, PieceColor.White);
        var whiteBonus = 0;
        var blackBonus = 0;
        var weight = EndgameWeight(board);

        if (whiteMaterial >= EndgameMaterialAdvantageThreshold && HasForcingMatingMaterial(board, PieceColor.White))
        {
            whiteBonus = ForceKingToCornerEndgameEval(board, PieceColor.White, weight);
            whiteBonus += (8 - DefenderKingMobility(board, PieceColor.Black)) * EndgameKingMobilityScale;
            whiteBonus -= WeakerSidePawnDanger(board, PieceColor.White, weight);
        }

        if (whiteMaterial <= -EndgameMaterialAdvantageThreshold && HasForcingMatingMaterial(board, PieceColor.Black))
        {
            blackBonus = ForceKingToCornerEndgameEval(board, PieceColor.Black, weight);
            blackBonus += (8 - DefenderKingMobility(board, PieceColor.White)) * EndgameKingMobilityScale;
            blackBonus -= WeakerSidePawnDanger(board, PieceColor.Black, weight);
        }

        var score = whiteBonus - blackBonus;
        return perspective == PieceColor.White ? score : -score;
    }

    private static int WinningEndgameRepetitionAdjustment(BoardState board, PieceColor perspective)
    {
        var materialEdge = EvaluateMaterial(board, perspective);
        if (materialEdge <= EndgameMaterialAdvantageThreshold || EndgameWeight(board) <= 0.0)
        {
            return 0;
        }

        var adjustment = 0;
        if (board.IsRepetition(2))
        {
            adjustment -= WinningEndgameRepeatPenalty + (materialEdge / 20);
        }

        if (board.CanClaimThreefoldRepetition())
        {
            adjustment -= WinningEndgameRepeatPenalty + (materialEdge / 10);
        }

        return adjustment;
    }

    private static int RepetitionDrawAdjustment(BoardState board, PieceColor perspective)
    {
        var adjustment = 0;

        if (board.IsRepetition(2))
        {
            adjustment -= RepeatPositionPenalty;
        }

        if (board.CanClaimThreefoldRepetition())
        {
            adjustment -= ThreefoldRepetitionPenalty;
        }

        if (board.CanClaimDraw())
        {
            adjustment -= DrawBasePenalty;
        }

        if (board.IsGameOver && !board.IsCheckmate)
        {
            var materialEdge = Math.Max(EvaluateMaterial(board, perspective), 0);
            adjustment -= DrawBasePenalty + (materialEdge / 10);
        }

        return adjustment;
    }

    private static int ForceKingToCornerEndgameEval(BoardState board, PieceColor strongerSide, double weight)
    {
        if (weight <= 0.0)
        {
            return 0;
        }

        var friendlyKing = board.King(strongerSide);
        var opponentKing = board.King(strongerSide == PieceColor.White ? PieceColor.Black : PieceColor.White);
        if (friendlyKing is null || opponentKing is null)
        {
            return 0;
        }

        var losingKingCmd = CenterManhattanDistance(opponentKing.Value);
        var kingsMd = ManhattanDistance(friendlyKing.Value, opponentKing.Value);
        var rawScore = (4.7 * losingKingCmd) + (1.6 * (14 - kingsMd));
        return (int)(rawScore * EndgameMopUpScale * weight);
    }

    private static int DefenderKingMobility(BoardState board, PieceColor losingSide)
    {
        var probeBoard = board.CloneWithTurn(losingSide);
        return probeBoard.LegalMoves().Count(move => char.ToLowerInvariant(move.Piece.ToFenChar()) == 'k');
    }

    private static int WeakerSidePawnDanger(BoardState board, PieceColor strongerSide, double weight)
    {
        if (weight <= 0.0)
        {
            return 0;
        }

        var weakerSide = strongerSide == PieceColor.White ? PieceColor.Black : PieceColor.White;
        var danger = 0;

        foreach (var square in board.SquaresWithPiece('p', weakerSide))
        {
            var rankFromPromotion = weakerSide == PieceColor.White ? 7 - square.Y : square.Y;
            danger += (6 - rankFromPromotion) * EndgamePawnDangerScale;
        }

        return (int)(danger * weight);
    }

    private static int ScoreMoveForOrdering(Move move, BoardState board)
    {
        var score = 0;
        var attackerValue = PieceValue(move.Piece);
        if (board.IsCapture(move))
        {
            score += 10_000 + (10 * CapturedPieceValue(board, move)) - attackerValue;
        }

        if (move.IsPromotion)
        {
            score += 8_000 + (move.Promotion is null ? 0 : PieceValue(move.Promotion));
        }

        board.Push(move);
        try
        {
            if (board.IsCheckmate)
            {
                score += 100_000;
            }
            else if (board.IsCurrentSideInCheck())
            {
                score += 2_000;
            }

            var defenderColor = board.WhiteToMove ? PieceColor.White : PieceColor.Black;
            if (board.IsAttackedByPawn(defenderColor, move.NewPosition))
            {
                score -= attackerValue;
            }
        }
        finally
        {
            board.Pop();
        }

        return score;
    }

    private static int PieceValue(Piece piece)
    {
        return PieceValues[char.ToLowerInvariant(piece.ToFenChar())];
    }

    private static int ManhattanDistance(Position left, Position right)
    {
        return Math.Abs(left.X - right.X) + Math.Abs(left.Y - right.Y);
    }

    private static int CenterManhattanDistance(Position position)
    {
        var files = new[] { 3, 4 };
        var ranks = new[] { 3, 4 };
        var best = int.MaxValue;

        foreach (var file in files)
        {
            foreach (var rank in ranks)
            {
                best = Math.Min(best, Math.Abs(position.X - file) + Math.Abs(position.Y - rank));
            }
        }

        return best;
    }
}
