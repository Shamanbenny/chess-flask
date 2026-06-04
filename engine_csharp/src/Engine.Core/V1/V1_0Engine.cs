using Chess;

namespace Engine.Core.V1;

public static partial class HistoricalEngines
{
    public static SearchResult SearchMoveV1_0(BoardState board, int depth = 3)
    {
        var movesEvaluated = 0;

        int Minimax(int remainingDepth, PieceColor perspective)
        {
            if (remainingDepth == 0)
            {
                return Shared.EvaluateWithDrawPenalty(board, perspective);
            }

            if (board.IsGameOver)
            {
                if (board.IsCheckmate)
                {
                    return board.WhiteToMove == (perspective == PieceColor.White)
                        ? Shared.NegativeInfinity
                        : Shared.PositiveInfinity;
                }

                return Shared.EvaluateWithDrawPenalty(board, perspective);
            }

            var bestEval = Shared.NegativeInfinity;
            foreach (var move in board.LegalMoves())
            {
                board.Push(move);
                movesEvaluated++;
                var moveEval = -Minimax(remainingDepth - 1, perspective);
                board.Pop();
                bestEval = Math.Max(bestEval, moveEval);
            }

            return bestEval;
        }

        return SearchRoot(board, board.LegalMoves(), depth, move =>
        {
            board.Push(move);
            movesEvaluated++;
            var moveEval = -Minimax(depth - 1, board.WhiteToMove ? PieceColor.White : PieceColor.Black);
            board.Pop();
            return moveEval;
        }, () => movesEvaluated);
    }
}
