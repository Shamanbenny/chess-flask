using Chess;

namespace Engine.Core.V1;

public static partial class HistoricalEngines
{
    public static SearchResult SearchMoveV1_4(BoardState board, int depth = 4)
    {
        var movesEvaluated = 0;

        List<Move> OrderedQuiescenceMoves()
        {
            if (board.IsCurrentSideInCheck())
            {
                return Shared.OrderedLegalMoves(board);
            }

            return Shared.OrderedLegalMoves(board)
                .Where(board.IsCapture)
                .ToList();
        }

        int Quiescence(int alpha, int beta, PieceColor perspective)
        {
            if (board.IsGameOver)
            {
                if (board.IsCheckmate)
                {
                    return board.WhiteToMove == (perspective == PieceColor.White)
                        ? Shared.NegativeInfinity
                        : Shared.PositiveInfinity;
                }

                return Shared.EvaluateWithEndgameMopUp(board, perspective);
            }

            var standPat = Shared.EvaluateWithEndgameMopUp(board, perspective);
            if (!board.IsCurrentSideInCheck())
            {
                if (standPat >= beta)
                {
                    return beta;
                }

                alpha = Math.Max(alpha, standPat);
            }

            foreach (var move in OrderedQuiescenceMoves())
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
                movesEvaluated++;
                var moveEval = -Quiescence(-beta, -alpha, Opponent(perspective));
                board.Pop();

                if (moveEval >= beta)
                {
                    return beta;
                }

                alpha = Math.Max(alpha, moveEval);
            }

            return alpha;
        }

        int AlphaBeta(int remainingDepth, int alpha, int beta, PieceColor perspective)
        {
            if (board.IsGameOver)
            {
                return board.IsCheckmate ? Shared.NegativeInfinity : Shared.EvaluateWithEndgameMopUp(board, perspective);
            }

            if (remainingDepth == 0)
            {
                return Quiescence(alpha, beta, perspective);
            }

            var moveEval = Shared.NegativeInfinity;
            foreach (var move in Shared.OrderedLegalMoves(board))
            {
                board.Push(move);
                movesEvaluated++;
                moveEval = Math.Max(moveEval, -AlphaBeta(remainingDepth - 1, -beta, -alpha, Opponent(perspective)));
                board.Pop();

                if (moveEval >= beta)
                {
                    return beta;
                }

                alpha = Math.Max(alpha, moveEval);
            }

            return moveEval;
        }

        var perspective = board.WhiteToMove ? PieceColor.White : PieceColor.Black;
        return SearchRoot(board, Shared.OrderedLegalMoves(board), depth, move =>
        {
            board.Push(move);
            movesEvaluated++;
            var moveEval = -AlphaBeta(depth - 1, Shared.NegativeInfinity, Shared.PositiveInfinity, Opponent(perspective));
            board.Pop();
            return moveEval;
        }, () => movesEvaluated);
    }
}
