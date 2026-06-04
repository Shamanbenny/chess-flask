using Chess;

namespace Engine.Core.V1;

public static partial class HistoricalEngines
{
    public static SearchResult SearchMoveV1_3(BoardState board, int depth = 4)
    {
        const int MaxQuiescencePly = 8;
        var movesEvaluated = 0;

        List<Move> OrderedQuiescenceMoves()
        {
            if (board.IsCurrentSideInCheck())
            {
                return Shared.OrderedLegalMoves(board);
            }

            var forcing = new List<Move>();
            foreach (var move in Shared.OrderedLegalMoves(board))
            {
                if (board.IsCapture(move))
                {
                    forcing.Add(move);
                    continue;
                }

                board.Push(move);
                var givesCheck = board.IsCurrentSideInCheck();
                board.Pop();
                if (givesCheck)
                {
                    forcing.Add(move);
                }
            }

            return forcing;
        }

        int Quiescence(int alpha, int beta, PieceColor perspective, int quiescencePly)
        {
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

            if (quiescencePly >= MaxQuiescencePly || board.CanClaimDraw())
            {
                return Shared.EvaluateWithDrawPenalty(board, perspective);
            }

            var standPat = Shared.EvaluateWithDrawPenalty(board, perspective);
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
                board.Push(move);
                movesEvaluated++;
                var moveEval = -Quiescence(-beta, -alpha, Opponent(perspective), quiescencePly + 1);
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
                return board.IsCheckmate ? Shared.NegativeInfinity : Shared.EvaluateWithDrawPenalty(board, perspective);
            }

            if (remainingDepth == 0)
            {
                return Quiescence(alpha, beta, perspective, 0);
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
