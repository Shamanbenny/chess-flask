using Chess;

namespace Engine.Core.V1;

public static partial class HistoricalEngines
{
    public static SearchResult SearchMoveV1_2(BoardState board, int depth = 4)
    {
        var movesEvaluated = 0;

        int AlphaBeta(int remainingDepth, int alpha, int beta, bool maximizingPlayer, PieceColor perspective)
        {
            if (remainingDepth == 0 || board.IsGameOver)
            {
                if (board.IsGameOver)
                {
                    if (board.IsCheckmate)
                    {
                        return maximizingPlayer ? Shared.NegativeInfinity : Shared.PositiveInfinity;
                    }

                    return Shared.EvaluateWithDrawPenalty(board, perspective);
                }

                return maximizingPlayer
                    ? -Shared.EvaluateWithDrawPenalty(board, perspective)
                    : Shared.EvaluateWithDrawPenalty(board, perspective);
            }

            var legalMoves = Shared.OrderedLegalMoves(board);
            if (maximizingPlayer)
            {
                var moveEval = Shared.NegativeInfinity;
                foreach (var move in legalMoves)
                {
                    board.Push(move);
                    movesEvaluated++;
                    moveEval = Math.Max(moveEval, AlphaBeta(remainingDepth - 1, alpha, beta, false, perspective));
                    board.Pop();
                    if (moveEval >= beta)
                    {
                        break;
                    }

                    alpha = Math.Max(alpha, moveEval);
                }

                return moveEval;
            }

            var minEval = Shared.PositiveInfinity;
            foreach (var move in legalMoves)
            {
                board.Push(move);
                movesEvaluated++;
                minEval = Math.Min(minEval, AlphaBeta(remainingDepth - 1, alpha, beta, true, perspective));
                board.Pop();
                if (minEval <= alpha)
                {
                    break;
                }

                beta = Math.Min(beta, minEval);
            }

            return minEval;
        }

        return SearchRoot(board, Shared.OrderedLegalMoves(board), depth, move =>
        {
            board.Push(move);
            movesEvaluated++;
            var moveEval = AlphaBeta(depth - 1, Shared.NegativeInfinity, Shared.PositiveInfinity, false, board.WhiteToMove ? PieceColor.White : PieceColor.Black);
            board.Pop();
            return moveEval;
        }, () => movesEvaluated);
    }
}
