using Chess;

namespace Engine.Core.V1;

public static partial class HistoricalEngines
{
    private const int MateScore = 1_000_000;
    private const int MateScoreThreshold = 999_000;

    private static SearchResult SearchRoot(
        BoardState board,
        IReadOnlyList<Move> rootMoves,
        int depth,
        Func<Move, int> evalMove,
        Func<int> moveCounter)
    {
        Move? bestMove = null;
        var bestEval = Shared.NegativeInfinity;

        foreach (var move in rootMoves)
        {
            var moveEval = evalMove(move);
            if (bestMove is null || moveEval > bestEval)
            {
                bestEval = moveEval;
                bestMove = move;
            }
        }

        if (bestMove is null)
        {
            throw new InvalidOperationException($"No legal moves available for depth-{depth} search");
        }

        return new SearchResult(bestMove, board.GetSan(bestMove), bestEval, moveCounter());
    }

    private static PieceColor Opponent(PieceColor color)
    {
        return color == PieceColor.White ? PieceColor.Black : PieceColor.White;
    }

    private static bool SameMove(Move left, Move right)
    {
        return left.OriginalPosition == right.OriginalPosition
            && left.NewPosition == right.NewPosition
            && left.IsPromotion == right.IsPromotion
            && (left.Promotion?.ToFenChar() ?? '\0') == (right.Promotion?.ToFenChar() ?? '\0');
    }

    private sealed class SearchTimeoutException : Exception;

    private enum TtBound
    {
        Exact,
        Lower,
        Upper,
    }

    private sealed record TranspositionEntry(
        int Depth,
        int Score,
        TtBound Bound,
        Move BestMove,
        int Age);

    private sealed class TranspositionTable
    {
        private readonly Dictionary<ulong, TranspositionEntry> _entries = new();

        public int EntryCount => _entries.Count;

        public TranspositionEntry? Probe(ulong key)
        {
            return _entries.TryGetValue(key, out var entry) ? entry : null;
        }

        public void Store(ulong key, TranspositionEntry entry)
        {
            if (_entries.TryGetValue(key, out var existing))
            {
                var shouldReplace =
                    entry.Depth > existing.Depth
                    || entry.Age > existing.Age;

                if (!shouldReplace)
                {
                    return;
                }
            }

            _entries[key] = entry;
        }
    }
}
