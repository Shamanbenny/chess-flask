using System.Diagnostics;
using Chess;

namespace Engine.Core.V1;

public static partial class HistoricalEngines
{
    private const int V1_6TimeCheckInterval = 2048;
    private const int V1_6TtSizeBits = 18;
    private const int V1_6TtSize = 1 << V1_6TtSizeBits;
    private const int V1_6TtMask = V1_6TtSize - 1;
    private const int V1_6MateScore = 1_000_000;
    private const int V1_6MateScoreThreshold = 999_000;
    private const int V1_6PositiveInfinity = 1_000_000_000;
    private const int V1_6NegativeInfinity = -V1_6PositiveInfinity;
    private const int V1_6DrawBasePenalty = 120;
    private const int V1_6ThreefoldRepetitionPenalty = 90;
    private const int V1_6RepeatPositionPenalty = 35;
    private const int V1_6EndgameNonPawnMaterialThreshold = 1600;
    private const int V1_6EndgameMaterialAdvantageThreshold = 200;
    private const int V1_6EndgameMopUpScale = 8;
    private const int V1_6EndgameKingMobilityScale = 12;
    private const int V1_6EndgamePawnDangerScale = 70;
    private const int V1_6WinningEndgameRepeatPenalty = 1000;
    private const int V1_6DeltaPruningMargin = 200;
    private const int V1_6TtMoveBonus = 100_000;

    public static SearchResult SearchMoveV1_6(BoardState board, double timeLimitSeconds = 1.0, int? maxDepth = null)
    {
        if (timeLimitSeconds <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(timeLimitSeconds), "timeLimitSeconds must be greater than 0");
        }

        var startTimestamp = Stopwatch.GetTimestamp();
        var deadlineTimestamp = startTimestamp + (long)(timeLimitSeconds * Stopwatch.Frequency);
        var movesEvaluated = 0;
        var nodesSearched = 0;
        var ttProbes = 0;
        var ttHits = 0;
        var ttCutoffs = 0;
        var transpositionTable = new V1_6TranspositionTable();
        var currentIterationDepth = 0;

        void CheckTime()
        {
            if (Stopwatch.GetTimestamp() >= deadlineTimestamp)
            {
                throw new SearchTimeoutException();
            }
        }

        ulong PositionKey() => board.TranspositionKey;

        void VisitNode()
        {
            nodesSearched++;
            if ((nodesSearched & (V1_6TimeCheckInterval - 1)) == 0)
            {
                CheckTime();
            }
        }

        int ScoreToTt(int score, int ply)
        {
            if (score >= V1_6MateScoreThreshold)
            {
                return score + ply;
            }

            if (score <= -V1_6MateScoreThreshold)
            {
                return score - ply;
            }

            return score;
        }

        int ScoreFromTt(int score, int ply)
        {
            if (score >= V1_6MateScoreThreshold)
            {
                return score - ply;
            }

            if (score <= -V1_6MateScoreThreshold)
            {
                return score + ply;
            }

            return score;
        }

        int TerminalScore(int ply)
        {
            if (board.IsCheckmate)
            {
                return -V1_6MateScore + ply;
            }

            return Evaluate(board, board.WhiteToMove ? PieceColor.White : PieceColor.Black);
        }

        List<Move> OrderedSearchMoves(Move? ttMove = null, bool capturesOnly = false)
        {
            var moves = board.LegalMoves();
            if (capturesOnly && !board.IsCurrentSideInCheck())
            {
                moves.RemoveAll(move => !board.IsCapture(move));
            }

            OrderMoves(board, moves, ttMove);
            return moves;
        }

        int Quiescence(int alpha, int beta, int ply)
        {
            VisitNode();

            if (board.IsGameOver)
            {
                return TerminalScore(ply);
            }

            var standPat = Evaluate(board, board.WhiteToMove ? PieceColor.White : PieceColor.Black);
            if (!board.IsCurrentSideInCheck())
            {
                if (standPat >= beta)
                {
                    return beta;
                }

                alpha = Math.Max(alpha, standPat);
            }

            foreach (var move in OrderedSearchMoves(capturesOnly: true))
            {
                if (!board.IsCurrentSideInCheck())
                {
                    if (IsObviouslyLosingCapture(board, move))
                    {
                        continue;
                    }

                    if (IsDeltaPruned(board, move, standPat, alpha))
                    {
                        continue;
                    }
                }

                board.Push(move);
                try
                {
                    movesEvaluated++;
                    var moveEval = -Quiescence(-beta, -alpha, ply + 1);
                    if (moveEval >= beta)
                    {
                        return beta;
                    }

                    alpha = Math.Max(alpha, moveEval);
                }
                finally
                {
                    board.Pop();
                }
            }

            return alpha;
        }

        int Negamax(int remainingDepth, int alpha, int beta, int ply)
        {
            VisitNode();

            if (board.IsGameOver)
            {
                return TerminalScore(ply);
            }

            alpha = Math.Max(alpha, -V1_6MateScore + ply);
            beta = Math.Min(beta, V1_6MateScore - ply);
            if (alpha >= beta)
            {
                return alpha;
            }

            if (remainingDepth == 0)
            {
                return Quiescence(alpha, beta, ply);
            }

            var alphaOriginal = alpha;
            var key = PositionKey();
            ttProbes++;
            if (transpositionTable.TryProbe(key, out var entry))
            {
                ttHits++;
                if (entry.Depth >= remainingDepth)
                {
                    var ttScore = ScoreFromTt(entry.Score, ply);
                    if (entry.Bound == TtBound.Exact)
                    {
                        ttCutoffs++;
                        return ttScore;
                    }

                    if (entry.Bound == TtBound.Lower && ttScore >= beta)
                    {
                        ttCutoffs++;
                        return ttScore;
                    }

                    if (entry.Bound == TtBound.Upper && ttScore <= alpha)
                    {
                        ttCutoffs++;
                        return ttScore;
                    }
                }
            }

            Move? bestMove = entry.BestMove;
            var bestScore = V1_6NegativeInfinity;

            foreach (var move in OrderedSearchMoves(bestMove))
            {
                board.Push(move);
                try
                {
                    movesEvaluated++;
                    var moveEval = -Negamax(remainingDepth - 1, -beta, -alpha, ply + 1);
                    if (moveEval > bestScore)
                    {
                        bestScore = moveEval;
                        bestMove = move;
                    }

                    alpha = Math.Max(alpha, moveEval);
                    if (alpha >= beta)
                    {
                        break;
                    }
                }
                finally
                {
                    board.Pop();
                }
            }

            if (bestMove is null)
            {
                return TerminalScore(ply);
            }

            var bound = bestScore <= alphaOriginal
                ? TtBound.Upper
                : bestScore >= beta
                    ? TtBound.Lower
                    : TtBound.Exact;

            transpositionTable.Store(
                key,
                new V1_6TranspositionEntry(
                    key,
                    remainingDepth,
                    ScoreToTt(bestScore, ply),
                    bound,
                    bestMove,
                    currentIterationDepth));

            return bestScore;
        }

        var fallbackMoves = OrderedSearchMoves();
        if (fallbackMoves.Count == 0)
        {
            throw new InvalidOperationException("No legal moves available for v1.6 search");
        }

        var bestMove = fallbackMoves[0];
        var bestEval = V1_6NegativeInfinity;
        var completedDepth = 0;
        var timedOut = false;
        var depth = 1;

        while (!maxDepth.HasValue || depth <= maxDepth.Value)
        {
            currentIterationDepth = depth;
            Move? iterationBestMove = null;
            var iterationBestEval = V1_6NegativeInfinity;

            try
            {
                ttProbes++;
                var rootKey = PositionKey();
                if (transpositionTable.TryProbe(rootKey, out var rootEntry))
                {
                    ttHits++;
                }

                foreach (var move in OrderedSearchMoves(rootEntry.BestMove))
                {
                    CheckTime();
                    board.Push(move);
                    try
                    {
                        movesEvaluated++;
                        var moveEval = -Negamax(depth - 1, V1_6NegativeInfinity, V1_6PositiveInfinity, 1);
                        if (iterationBestMove is null || moveEval > iterationBestEval)
                        {
                            iterationBestEval = moveEval;
                            iterationBestMove = move;
                        }
                    }
                    finally
                    {
                        board.Pop();
                    }
                }

                if (iterationBestMove is null)
                {
                    break;
                }

                bestMove = iterationBestMove;
                bestEval = iterationBestEval;
                completedDepth = depth;
                transpositionTable.Store(
                    rootKey,
                    new V1_6TranspositionEntry(
                        rootKey,
                        depth,
                        ScoreToTt(bestEval, 0),
                        TtBound.Exact,
                        bestMove,
                        currentIterationDepth));
            }
            catch (SearchTimeoutException)
            {
                timedOut = true;
                if (completedDepth == 0 && iterationBestMove is not null)
                {
                    bestMove = iterationBestMove;
                    bestEval = iterationBestEval;
                }

                break;
            }

            depth++;
        }

        return new SearchResult(
            bestMove,
            board.GetSan(bestMove),
            bestEval,
            movesEvaluated,
            completedDepth,
            timedOut,
            transpositionTable.EntryCount,
            ttProbes,
            ttHits,
            ttCutoffs,
            nodesSearched);
    }

    private static void OrderMoves(BoardState board, List<Move> moves, Move? ttMove)
    {
        if (moves.Count < 2)
        {
            return;
        }

        Span<int> scores = moves.Count <= 256
            ? stackalloc int[moves.Count]
            : new int[moves.Count];

        for (var index = 0; index < moves.Count; index++)
        {
            scores[index] = ScoreMoveForOrdering(board, moves[index], ttMove);
        }

        for (var i = 1; i < moves.Count; i++)
        {
            var move = moves[i];
            var score = scores[i];
            var j = i - 1;

            while (j >= 0 && scores[j] < score)
            {
                moves[j + 1] = moves[j];
                scores[j + 1] = scores[j];
                j--;
            }

            moves[j + 1] = move;
            scores[j + 1] = score;
        }
    }

    private static int ScoreMoveForOrdering(BoardState board, Move move, Move? ttMove)
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

        if (ttMove is not null && MovesEqual(move, ttMove))
        {
            score += V1_6TtMoveBonus;
        }

        var defenderColor = board.WhiteToMove ? PieceColor.Black : PieceColor.White;
        if (char.ToLowerInvariant(move.Piece.ToFenChar()) != 'p' && board.IsAttackedByPawn(defenderColor, move.NewPosition))
        {
            score -= attackerValue;
        }

        return score;
    }

    private static int Evaluate(BoardState board, PieceColor perspective)
    {
        var snapshot = BuildEvalSnapshot(board);
        var materialScore = perspective == PieceColor.White
            ? snapshot.MaterialBalance
            : -snapshot.MaterialBalance;

        return materialScore
            + RepetitionDrawAdjustment(board, perspective, snapshot.MaterialBalance)
            + EndgameMopUpAdjustment(board, perspective, snapshot)
            + WinningEndgameRepetitionAdjustment(board, perspective, snapshot.MaterialBalance, snapshot.EndgameWeight);
    }

    private static EvalSnapshot BuildEvalSnapshot(BoardState board)
    {
        var whiteMaterial = 0;
        var blackMaterial = 0;
        var whiteNonPawnMaterial = 0;
        var blackNonPawnMaterial = 0;
        var whiteBishops = 0;
        var blackBishops = 0;
        var whiteKnights = 0;
        var blackKnights = 0;
        var whiteRooks = 0;
        var blackRooks = 0;
        var whiteQueens = 0;
        var blackQueens = 0;
        var whitePawnDanger = 0;
        var blackPawnDanger = 0;

        for (short rank = 0; rank < ChessBoard.MAX_ROWS; rank++)
        {
            for (short file = 0; file < ChessBoard.MAX_COLS; file++)
            {
                var piece = board.InnerBoard[file, rank];
                if (piece is null)
                {
                    continue;
                }

                var pieceType = char.ToLowerInvariant(piece.ToFenChar());
                var value = PieceValue(piece);
                var isWhite = piece.Color == PieceColor.White;

                if (isWhite)
                {
                    whiteMaterial += value;
                }
                else
                {
                    blackMaterial += value;
                }

                switch (pieceType)
                {
                    case 'p':
                        if (isWhite)
                        {
                            whitePawnDanger += rank;
                        }
                        else
                        {
                            blackPawnDanger += 7 - rank;
                        }
                        break;
                    case 'n':
                        if (isWhite)
                        {
                            whiteKnights++;
                            whiteNonPawnMaterial += value;
                        }
                        else
                        {
                            blackKnights++;
                            blackNonPawnMaterial += value;
                        }
                        break;
                    case 'b':
                        if (isWhite)
                        {
                            whiteBishops++;
                            whiteNonPawnMaterial += value;
                        }
                        else
                        {
                            blackBishops++;
                            blackNonPawnMaterial += value;
                        }
                        break;
                    case 'r':
                        if (isWhite)
                        {
                            whiteRooks++;
                            whiteNonPawnMaterial += value;
                        }
                        else
                        {
                            blackRooks++;
                            blackNonPawnMaterial += value;
                        }
                        break;
                    case 'q':
                        if (isWhite)
                        {
                            whiteQueens++;
                            whiteNonPawnMaterial += value;
                        }
                        else
                        {
                            blackQueens++;
                            blackNonPawnMaterial += value;
                        }
                        break;
                }
            }
        }

        var totalNonPawnMaterial = whiteNonPawnMaterial + blackNonPawnMaterial;
        var endgameWeight = 1.0 - (Math.Min(totalNonPawnMaterial, V1_6EndgameNonPawnMaterialThreshold) / (double)V1_6EndgameNonPawnMaterialThreshold);

        return new EvalSnapshot(
            whiteMaterial,
            blackMaterial,
            whiteNonPawnMaterial,
            blackNonPawnMaterial,
            whiteBishops,
            blackBishops,
            whiteKnights,
            blackKnights,
            whiteRooks,
            blackRooks,
            whiteQueens,
            blackQueens,
            whitePawnDanger,
            blackPawnDanger,
            Math.Clamp(endgameWeight, 0.0, 1.0));
    }

    private static int RepetitionDrawAdjustment(BoardState board, PieceColor perspective, int materialBalance)
    {
        var adjustment = 0;
        if (board.IsRepetition(2))
        {
            adjustment -= V1_6RepeatPositionPenalty;
        }

        if (board.CanClaimThreefoldRepetition())
        {
            adjustment -= V1_6ThreefoldRepetitionPenalty;
        }

        if (board.CanClaimDraw())
        {
            adjustment -= V1_6DrawBasePenalty;
        }

        if (board.IsGameOver && !board.IsCheckmate)
        {
            var materialEdge = perspective == PieceColor.White
                ? Math.Max(materialBalance, 0)
                : Math.Max(-materialBalance, 0);
            adjustment -= V1_6DrawBasePenalty + (materialEdge / 10);
        }

        return adjustment;
    }

    private static int EndgameMopUpAdjustment(BoardState board, PieceColor perspective, EvalSnapshot snapshot)
    {
        if (board.IsCheckmate || snapshot.EndgameWeight <= 0.0)
        {
            return 0;
        }

        var whiteBonus = 0;
        var blackBonus = 0;

        if (snapshot.MaterialBalance >= V1_6EndgameMaterialAdvantageThreshold && HasForcingMatingMaterial(snapshot, PieceColor.White))
        {
            whiteBonus = ForceKingToCornerEndgameEval(board, PieceColor.White, snapshot.EndgameWeight);
            whiteBonus += (8 - DefenderKingMobility(board, PieceColor.Black)) * V1_6EndgameKingMobilityScale;
            whiteBonus -= (int)(snapshot.BlackPawnDanger * V1_6EndgamePawnDangerScale * snapshot.EndgameWeight);
        }

        if (snapshot.MaterialBalance <= -V1_6EndgameMaterialAdvantageThreshold && HasForcingMatingMaterial(snapshot, PieceColor.Black))
        {
            blackBonus = ForceKingToCornerEndgameEval(board, PieceColor.Black, snapshot.EndgameWeight);
            blackBonus += (8 - DefenderKingMobility(board, PieceColor.White)) * V1_6EndgameKingMobilityScale;
            blackBonus -= (int)(snapshot.WhitePawnDanger * V1_6EndgamePawnDangerScale * snapshot.EndgameWeight);
        }

        var score = whiteBonus - blackBonus;
        return perspective == PieceColor.White ? score : -score;
    }

    private static int WinningEndgameRepetitionAdjustment(BoardState board, PieceColor perspective, int materialBalance, double endgameWeight)
    {
        var materialEdge = perspective == PieceColor.White ? materialBalance : -materialBalance;
        if (materialEdge <= V1_6EndgameMaterialAdvantageThreshold || endgameWeight <= 0.0)
        {
            return 0;
        }

        var adjustment = 0;
        if (board.IsRepetition(2))
        {
            adjustment -= V1_6WinningEndgameRepeatPenalty + (materialEdge / 20);
        }

        if (board.CanClaimThreefoldRepetition())
        {
            adjustment -= V1_6WinningEndgameRepeatPenalty + (materialEdge / 10);
        }

        return adjustment;
    }

    private static bool HasForcingMatingMaterial(EvalSnapshot snapshot, PieceColor color)
    {
        var queens = color == PieceColor.White ? snapshot.WhiteQueens : snapshot.BlackQueens;
        var rooks = color == PieceColor.White ? snapshot.WhiteRooks : snapshot.BlackRooks;
        var bishops = color == PieceColor.White ? snapshot.WhiteBishops : snapshot.BlackBishops;
        var knights = color == PieceColor.White ? snapshot.WhiteKnights : snapshot.BlackKnights;

        if (queens > 0 || rooks > 0)
        {
            return true;
        }

        return bishops >= 2 || (bishops >= 1 && knights >= 1);
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
        return (int)(rawScore * V1_6EndgameMopUpScale * weight);
    }

    private static int DefenderKingMobility(BoardState board, PieceColor losingSide)
    {
        var king = board.King(losingSide);
        if (king is null)
        {
            return 0;
        }

        var mobility = 0;
        var opponent = OtherColor(losingSide);
        for (var fileDelta = -1; fileDelta <= 1; fileDelta++)
        {
            for (var rankDelta = -1; rankDelta <= 1; rankDelta++)
            {
                if (fileDelta == 0 && rankDelta == 0)
                {
                    continue;
                }

                var file = king.Value.X + fileDelta;
                var rank = king.Value.Y + rankDelta;
                if (file < 0 || file >= ChessBoard.MAX_COLS || rank < 0 || rank >= ChessBoard.MAX_ROWS)
                {
                    continue;
                }

                var target = new Position((short)file, (short)rank);
                var occupant = board.PieceAt(target);
                if (occupant is not null && occupant.Color == losingSide)
                {
                    continue;
                }

                if (!board.IsAttackedBy(opponent, target))
                {
                    mobility++;
                }
            }
        }

        return mobility;
    }

    private static int CapturedPieceValue(BoardState board, Move move)
    {
        if (move.CapturedPiece is not null)
        {
            return PieceValue(move.CapturedPiece);
        }

        if (move.IsEnPassant)
        {
            return Shared.PieceValues['p'];
        }

        return 0;
    }

    private static bool IsObviouslyLosingCapture(BoardState board, Move move)
    {
        if (!board.IsCapture(move) || move.IsPromotion)
        {
            return false;
        }

        return PieceValue(move.Piece) > CapturedPieceValue(board, move);
    }

    private static bool IsDeltaPruned(BoardState board, Move move, int standPat, int alpha)
    {
        var materialSwing = CapturedPieceValue(board, move);
        if (move.IsPromotion && move.Promotion is not null)
        {
            materialSwing += PieceValue(move.Promotion) - Shared.PieceValues['p'];
        }

        return standPat + materialSwing + V1_6DeltaPruningMargin < alpha;
    }

    private static int PieceValue(Piece piece)
    {
        return Shared.PieceValues[char.ToLowerInvariant(piece.ToFenChar())];
    }

    private static int ManhattanDistance(Position left, Position right)
    {
        return Math.Abs(left.X - right.X) + Math.Abs(left.Y - right.Y);
    }

    private static int CenterManhattanDistance(Position position)
    {
        var best = int.MaxValue;
        foreach (var file in new[] { 3, 4 })
        {
            foreach (var rank in new[] { 3, 4 })
            {
                best = Math.Min(best, Math.Abs(position.X - file) + Math.Abs(position.Y - rank));
            }
        }

        return best;
    }

    private static PieceColor OtherColor(PieceColor color)
    {
        return color == PieceColor.White ? PieceColor.Black : PieceColor.White;
    }

    private static bool MovesEqual(Move left, Move right)
    {
        return left.OriginalPosition == right.OriginalPosition
            && left.NewPosition == right.NewPosition
            && left.IsPromotion == right.IsPromotion
            && (left.Promotion?.ToFenChar() ?? '\0') == (right.Promotion?.ToFenChar() ?? '\0');
    }

    private readonly record struct EvalSnapshot(
        int WhiteMaterial,
        int BlackMaterial,
        int WhiteNonPawnMaterial,
        int BlackNonPawnMaterial,
        int WhiteBishops,
        int BlackBishops,
        int WhiteKnights,
        int BlackKnights,
        int WhiteRooks,
        int BlackRooks,
        int WhiteQueens,
        int BlackQueens,
        int WhitePawnDanger,
        int BlackPawnDanger,
        double EndgameWeight)
    {
        public int MaterialBalance => WhiteMaterial - BlackMaterial;
    }

    private readonly record struct V1_6TranspositionEntry(
        ulong Key,
        int Depth,
        int Score,
        TtBound Bound,
        Move BestMove,
        int Age);

    private sealed class V1_6TranspositionTable
    {
        private readonly V1_6TranspositionSlot[] _entries = new V1_6TranspositionSlot[V1_6TtSize];
        private int _entryCount;

        public int EntryCount => _entryCount;

        public bool TryProbe(ulong key, out V1_6TranspositionEntry entry)
        {
            var slot = _entries[(int)(key & V1_6TtMask)];
            if (slot.IsOccupied && slot.Entry.Key == key)
            {
                entry = slot.Entry;
                return true;
            }

            entry = default;
            return false;
        }

        public void Store(ulong key, V1_6TranspositionEntry entry)
        {
            ref var slot = ref _entries[(int)(key & V1_6TtMask)];
            if (!slot.IsOccupied)
            {
                slot = new V1_6TranspositionSlot(true, entry);
                _entryCount++;
                return;
            }

            var existing = slot.Entry;
            var shouldReplace =
                entry.Depth > existing.Depth
                || entry.Age > existing.Age
                || (entry.Bound == TtBound.Exact && existing.Bound != TtBound.Exact);

            if (shouldReplace)
            {
                slot = new V1_6TranspositionSlot(true, entry);
            }
        }
    }

    private readonly record struct V1_6TranspositionSlot(bool IsOccupied, V1_6TranspositionEntry Entry);
}
