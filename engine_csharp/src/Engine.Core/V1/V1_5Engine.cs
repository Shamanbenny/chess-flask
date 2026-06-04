using Chess;

namespace Engine.Core.V1;

public static partial class HistoricalEngines
{
    private const int TimeCheckInterval = 1024;

    public static SearchResult SearchMoveV1_5(BoardState board, double timeLimitSeconds = 1.0, int? maxDepth = null)
    {
        if (timeLimitSeconds <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(timeLimitSeconds), "timeLimitSeconds must be greater than 0");
        }

        var movesEvaluated = 0;
        var nodesSearched = 0;
        var ttProbes = 0;
        var ttHits = 0;
        var ttCutoffs = 0;
        var deadline = DateTime.UtcNow + TimeSpan.FromSeconds(timeLimitSeconds);
        var transpositionTable = new TranspositionTable();
        var currentIterationDepth = 0;

        void CheckTime()
        {
            if (DateTime.UtcNow >= deadline)
            {
                throw new SearchTimeoutException();
            }
        }

        ulong PositionKey() => board.TranspositionKey;

        void VisitNode()
        {
            nodesSearched++;
            if ((nodesSearched & (TimeCheckInterval - 1)) == 0)
            {
                CheckTime();
            }
        }

        int ScoreToTt(int score, int ply)
        {
            if (score >= MateScoreThreshold)
            {
                return score + ply;
            }

            if (score <= -MateScoreThreshold)
            {
                return score - ply;
            }

            return score;
        }

        int ScoreFromTt(int score, int ply)
        {
            if (score >= MateScoreThreshold)
            {
                return score - ply;
            }

            if (score <= -MateScoreThreshold)
            {
                return score + ply;
            }

            return score;
        }

        int TerminalScore(int ply)
        {
            if (board.IsCheckmate)
            {
                return -MateScore + ply;
            }

            return Shared.EvaluateWithEndgameMopUp(board, board.WhiteToMove ? PieceColor.White : PieceColor.Black);
        }

        List<Move> OrderedSearchMoves(Move? ttMove = null, bool capturesOnly = false)
        {
            var moves = Shared.OrderedLegalMoves(board);
            if (capturesOnly && !board.IsCurrentSideInCheck())
            {
                moves = moves.Where(board.IsCapture).ToList();
            }

            if (ttMove is null)
            {
                return moves;
            }

            var first = moves.FirstOrDefault(move => SameMove(move, ttMove));
            if (first is null)
            {
                return moves;
            }

            return [first, .. moves.Where(move => !SameMove(move, ttMove))];
        }

        int Quiescence(int alpha, int beta, int ply)
        {
            VisitNode();

            if (board.IsGameOver)
            {
                return TerminalScore(ply);
            }

            var standPat = Shared.EvaluateWithEndgameMopUp(board, board.WhiteToMove ? PieceColor.White : PieceColor.Black);
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
                    if (Shared.IsObviouslyLosingCapture(board, move))
                    {
                        continue;
                    }

                    if (Shared.IsDeltaPruned(board, move, standPat, alpha))
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

            if (remainingDepth == 0)
            {
                return Quiescence(alpha, beta, ply);
            }

            var alphaOriginal = alpha;
            var key = PositionKey();
            ttProbes++;
            var entry = transpositionTable.Probe(key);
            if (entry is not null)
            {
                ttHits++;
            }

            if (entry is not null && entry.Depth >= remainingDepth)
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

            Move? bestMove = entry?.BestMove;
            var bestScore = Shared.NegativeInfinity;

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
                new TranspositionEntry(
                    remainingDepth,
                    ScoreToTt(bestScore, ply),
                    bound,
                    bestMove,
                    currentIterationDepth));

            return bestScore;
        }

        var fallbackMoves = Shared.OrderedLegalMoves(board);
        if (fallbackMoves.Count == 0)
        {
            throw new InvalidOperationException("No legal moves available for v1.5 search");
        }

        var bestMove = fallbackMoves[0];
        var bestEval = Shared.NegativeInfinity;
        var completedDepth = 0;
        var timedOut = false;
        var depth = 1;

        while (!maxDepth.HasValue || depth <= maxDepth.Value)
        {
            currentIterationDepth = depth;
            Move? iterationBestMove = null;
            var iterationBestEval = Shared.NegativeInfinity;

            try
            {
                ttProbes++;
                var rootEntry = transpositionTable.Probe(PositionKey());
                if (rootEntry is not null)
                {
                    ttHits++;
                }

                foreach (var move in OrderedSearchMoves(rootEntry?.BestMove))
                {
                    CheckTime();
                    board.Push(move);
                    try
                    {
                        movesEvaluated++;
                        var moveEval = -Negamax(depth - 1, Shared.NegativeInfinity, Shared.PositiveInfinity, 1);
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

                if (iterationBestMove is not null)
                {
                    bestMove = iterationBestMove;
                    bestEval = iterationBestEval;
                    completedDepth = depth;
                }

                depth++;
            }
            catch (SearchTimeoutException)
            {
                timedOut = true;
                break;
            }
        }

        return new SearchResult(
            bestMove,
            board.GetSan(bestMove),
            bestEval,
            movesEvaluated,
            CompletedDepth: completedDepth,
            TimedOut: timedOut,
            TtEntries: transpositionTable.EntryCount,
            TtProbes: ttProbes,
            TtHits: ttHits,
            TtCutoffs: ttCutoffs,
            NodesSearched: nodesSearched);
    }
}
