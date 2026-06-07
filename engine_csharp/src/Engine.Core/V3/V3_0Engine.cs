using System.Diagnostics;
using Chess;

namespace Engine.Core.V3;

public static class V3_0Engine
{
    private const int TimeCheckInterval = 1024;
    private const int TtSizeBits = 18;
    private const int TtSize = 1 << TtSizeBits;
    private const int TtMask = TtSize - 1;
    private const int MateScore = 1_000_000;
    private const int MateScoreThreshold = 999_000;
    private const int PositiveInfinity = 1_000_000_000;
    private const int NegativeInfinity = -PositiveInfinity;
    private const int DrawBasePenalty = 120;
    private const int ThreefoldRepetitionPenalty = 90;
    private const int RepeatPositionPenalty = 35;
    private const int EndgameNonPawnMaterialThreshold = 1600;
    private const int EndgameMaterialAdvantageThreshold = 200;
    private const int EndgameMopUpScale = 8;
    private const int EndgameKingMobilityScale = 12;
    private const int EndgamePawnDangerScale = 70;
    private const int WinningEndgameRepeatPenalty = 1000;
    private const int DeltaPruningMargin = 200;
    private const int TtMoveBonus = 100_000;
    private const int RookOpenFileBonus = 18;
    private const int RookSemiOpenFileBonus = 9;
    private const int KnightOutpostBonus = 14;

    public static SearchResult SearchMoveV3_0(
        BoardState board,
        double timeLimitSeconds = 1.0,
        int? maxDepth = null,
        V3_0SearchContext? searchContext = null)
    {
        if (timeLimitSeconds <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(timeLimitSeconds), "timeLimitSeconds must be greater than 0");
        }

        if (OpeningBook.TryGetMove(board, out var openingMove))
        {
            return openingMove;
        }

        var native = NativeBoard.FromFen(board.Fen);
        var search = new NativeSearch(native, timeLimitSeconds, maxDepth, searchContext);
        var result = search.Run();
        var uci = native.MoveToUci(result.BestMove);
        var legalMoves = board.LegalMoves();
        var selectedMove = legalMoves.FirstOrDefault(move => MoveToUci(move) == uci);
        if (selectedMove is null)
        {
            throw new InvalidOperationException($"Native v3.0 search returned an illegal root move: {uci}");
        }

        return new SearchResult(
            selectedMove,
            board.GetSan(selectedMove),
            result.Score,
            result.MovesEvaluated,
            result.CompletedDepth,
            result.TimedOut,
            result.TtEntries,
            result.TtProbes,
            result.TtHits,
            result.TtCutoffs,
            result.NodesSearched);
    }

    public static V3_0SearchContext CreateSearchContextV3_0()
    {
        return new V3_0SearchContext();
    }

    private static string MoveToUci(Move move)
    {
        var promotion = move.Promotion is null
            ? string.Empty
            : char.ToLowerInvariant(move.Promotion.ToFenChar()).ToString();
        return $"{move.OriginalPosition}{move.NewPosition}{promotion}";
    }

    public sealed class V3_0SearchContext
    {
        internal TtEntry[] TranspositionTable { get; } = new TtEntry[TtSize];
    }

    private sealed class NativeSearch
    {
        private readonly NativeBoard _board;
        private readonly long _deadlineTimestamp;
        private readonly int? _maxDepth;
        private readonly TtEntry[] _transpositionTable;
        private int _currentIterationDepth;
        private int _movesEvaluated;
        private int _nodesSearched;
        private int _ttEntries;
        private int _ttProbes;
        private int _ttHits;
        private int _ttCutoffs;

        public NativeSearch(NativeBoard board, double timeLimitSeconds, int? maxDepth, V3_0SearchContext? searchContext)
        {
            _board = board;
            _deadlineTimestamp = Stopwatch.GetTimestamp() + (long)(timeLimitSeconds * Stopwatch.Frequency);
            _maxDepth = maxDepth;
            _transpositionTable = searchContext?.TranspositionTable ?? new TtEntry[TtSize];
        }

        public NativeResult Run()
        {
            var fallbackMoves = OrderedSearchMoves();
            if (fallbackMoves.Count == 0)
            {
                throw new InvalidOperationException("No legal moves available for v3.0 search");
            }

            var bestMove = fallbackMoves[0];
            var bestEval = NegativeInfinity;
            var completedDepth = 0;
            var timedOut = false;

            for (var depth = 1; !_maxDepth.HasValue || depth <= _maxDepth.Value; depth++)
            {
                _currentIterationDepth = depth;
                ushort iterationBestMove = 0;
                var iterationBestEval = NegativeInfinity;

                try
                {
                    _ttProbes++;
                    var rootKey = _board.SearchKey;
                    var rootEntry = Probe(rootKey);
                    foreach (var move in OrderedSearchMoves(rootEntry.Move))
                    {
                        CheckTime();
                        var undo = _board.MakeMove(move);
                        _movesEvaluated++;
                        var moveEval = -Negamax(depth - 1, NegativeInfinity, PositiveInfinity, 1);
                        _board.UnmakeMove(move, undo);

                        if (iterationBestMove == 0 || moveEval > iterationBestEval)
                        {
                            iterationBestEval = moveEval;
                            iterationBestMove = move;
                        }
                    }

                    if (iterationBestMove == 0)
                    {
                        break;
                    }

                    bestMove = iterationBestMove;
                    bestEval = iterationBestEval;
                    completedDepth = depth;
                    Store(rootKey, depth, ScoreToTt(bestEval, 0), TtBound.Exact, bestMove);
                }
                catch (SearchTimeoutException)
                {
                    timedOut = true;
                    if (completedDepth == 0 && iterationBestMove != 0)
                    {
                        bestMove = iterationBestMove;
                        bestEval = iterationBestEval;
                    }

                    break;
                }
            }

            return new NativeResult(
                bestMove,
                bestEval,
                _movesEvaluated,
                completedDepth,
                timedOut,
                _ttEntries,
                _ttProbes,
                _ttHits,
                _ttCutoffs,
                _nodesSearched);
        }

        private int Negamax(int remainingDepth, int alpha, int beta, int ply)
        {
            VisitNode();

            alpha = Math.Max(alpha, -MateScore + ply);
            beta = Math.Min(beta, MateScore - ply);
            if (alpha >= beta)
            {
                return alpha;
            }

            if (remainingDepth == 0)
            {
                return Quiescence(alpha, beta, ply);
            }

            var alphaOriginal = alpha;
            var key = _board.SearchKey;
            _ttProbes++;
            var entry = Probe(key);
            if (entry.Key == key && entry.Depth >= remainingDepth)
            {
                var ttScore = ScoreFromTt(entry.Score, ply);
                if (entry.Bound == TtBound.Exact)
                {
                    _ttCutoffs++;
                    return ttScore;
                }

                if (entry.Bound == TtBound.Lower && ttScore >= beta)
                {
                    _ttCutoffs++;
                    return ttScore;
                }

                if (entry.Bound == TtBound.Upper && ttScore <= alpha)
                {
                    _ttCutoffs++;
                    return ttScore;
                }
            }

            var moves = OrderedSearchMoves(entry.Move);
            if (moves.Count == 0)
            {
                return _board.InCheck(_board.WhiteToMove) ? -MateScore + ply : _board.Evaluate();
            }

            var bestMove = entry.Move;
            var bestScore = NegativeInfinity;
            foreach (var move in moves)
            {
                var undo = _board.MakeMove(move);
                _movesEvaluated++;
                var moveEval = -Negamax(remainingDepth - 1, -beta, -alpha, ply + 1);
                _board.UnmakeMove(move, undo);

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

            var bound = bestScore <= alphaOriginal
                ? TtBound.Upper
                : bestScore >= beta
                    ? TtBound.Lower
                    : TtBound.Exact;
            Store(key, remainingDepth, ScoreToTt(bestScore, ply), bound, bestMove);
            return bestScore;
        }

        private int Quiescence(int alpha, int beta, int ply)
        {
            VisitNode();

            var inCheck = _board.InCheck(_board.WhiteToMove);
            var moves = OrderedSearchMoves(0, capturesOnly: !inCheck);
            if (moves.Count == 0)
            {
                return inCheck ? -MateScore + ply : _board.Evaluate();
            }

            var standPat = _board.Evaluate();
            if (!inCheck)
            {
                if (standPat >= beta)
                {
                    return beta;
                }

                alpha = Math.Max(alpha, standPat);
            }

            foreach (var move in moves)
            {
                if (!inCheck)
                {
                    if (_board.IsObviouslyLosingCapture(move))
                    {
                        continue;
                    }

                    if (_board.IsDeltaPruned(move, standPat, alpha))
                    {
                        continue;
                    }
                }

                var undo = _board.MakeMove(move);
                _movesEvaluated++;
                var moveEval = -Quiescence(-beta, -alpha, ply + 1);
                _board.UnmakeMove(move, undo);

                if (moveEval >= beta)
                {
                    return beta;
                }

                alpha = Math.Max(alpha, moveEval);
            }

            return alpha;
        }

        private List<ushort> OrderedSearchMoves(ushort ttMove = 0, bool capturesOnly = false)
        {
            var moves = _board.GenerateLegalMoves(capturesOnly);
            OrderMoves(moves, ttMove);
            return moves;
        }

        private void OrderMoves(List<ushort> moves, ushort ttMove)
        {
            if (moves.Count < 2)
            {
                return;
            }

            Span<int> scores = moves.Count <= 256 ? stackalloc int[moves.Count] : new int[moves.Count];
            for (var index = 0; index < moves.Count; index++)
            {
                scores[index] = _board.MoveOrderScore(moves[index], ttMove);
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

        private TtEntry Probe(ulong key)
        {
            var entry = _transpositionTable[key & TtMask];
            if (entry.Key == key)
            {
                _ttHits++;
            }

            return entry;
        }

        private void Store(ulong key, int depth, int score, TtBound bound, ushort move)
        {
            var index = key & TtMask;
            var existing = _transpositionTable[index];
            if (existing.Key == 0)
            {
                _ttEntries++;
            }
            else if (existing.Key != key && depth < existing.Depth && _currentIterationDepth <= existing.Age)
            {
                return;
            }

            _transpositionTable[index] = new TtEntry(key, depth, score, bound, move, _currentIterationDepth);
        }

        private static int ScoreToTt(int score, int ply)
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

        private static int ScoreFromTt(int score, int ply)
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

        private void VisitNode()
        {
            _nodesSearched++;
            if ((_nodesSearched & (TimeCheckInterval - 1)) == 0)
            {
                CheckTime();
            }
        }

        private void CheckTime()
        {
            if (Stopwatch.GetTimestamp() >= _deadlineTimestamp)
            {
                throw new SearchTimeoutException();
            }
        }
    }

    private sealed class SearchTimeoutException : Exception;

    internal enum TtBound
    {
        Exact,
        Lower,
        Upper,
    }

    internal readonly record struct TtEntry(ulong Key, int Depth, int Score, TtBound Bound, ushort Move, int Age);

    private readonly record struct NativeResult(
        ushort BestMove,
        int Score,
        int MovesEvaluated,
        int CompletedDepth,
        bool TimedOut,
        int TtEntries,
        int TtProbes,
        int TtHits,
        int TtCutoffs,
        int NodesSearched);

    private readonly record struct Undo(char Captured, byte Castling, int EpSquare, int HalfMove, ulong Key);

    private sealed class NativeBoard
    {
        private const int WhiteKingSide = 1;
        private const int WhiteQueenSide = 2;
        private const int BlackKingSide = 4;
        private const int BlackQueenSide = 8;
        private static readonly int[] PieceValues = new int[128];
        private static readonly int[] PawnPst =
        [
             0,  0,  0,  0,  0,  0,  0,  0,
            10, 10, 12,  0,  0, 12, 10, 10,
             6,  6, 10, 18, 18, 10,  6,  6,
             4,  4,  8, 20, 20,  8,  4,  4,
             4,  4,  8, 16, 16,  8,  4,  4,
             6,  8, 12, 18, 18, 12,  8,  6,
            12, 12, 16, 22, 22, 16, 12, 12,
             0,  0,  0,  0,  0,  0,  0,  0,
        ];
        private static readonly int[] PassedPawnBonus = [0, 0, 8, 16, 28, 45, 70, 0];
        private static readonly int[] KnightPst =
        [
            -35,-20,-12,-10,-10,-12,-20,-35,
            -18, -6,  4,  8,  8,  4, -6,-18,
            -10,  6, 16, 20, 20, 16,  6,-10,
             -8, 10, 22, 28, 28, 22, 10, -8,
             -8, 10, 22, 28, 28, 22, 10, -8,
            -10,  6, 16, 20, 20, 16,  6,-10,
            -18, -6,  4,  8,  8,  4, -6,-18,
            -35,-20,-12,-10,-10,-12,-20,-35,
        ];
        private static readonly int[] BishopPst =
        [
            -14, -8, -8, -6, -6, -8, -8,-14,
             -6,  6,  8, 10, 10,  8,  6, -6,
             -4,  8, 12, 16, 16, 12,  8, -4,
             -2, 10, 14, 18, 18, 14, 10, -2,
             -2, 10, 14, 18, 18, 14, 10, -2,
             -4,  8, 12, 16, 16, 12,  8, -4,
             -6,  6,  8, 10, 10,  8,  6, -6,
            -14, -8, -8, -6, -6, -8, -8,-14,
        ];
        private static readonly int[] RookPst =
        [
             0,  0,  4,  8,  8,  4,  0,  0,
             2,  4,  8, 10, 10,  8,  4,  2,
            -2,  0,  2,  6,  6,  2,  0, -2,
            -2,  0,  2,  6,  6,  2,  0, -2,
            -2,  0,  2,  6,  6,  2,  0, -2,
            -2,  0,  2,  6,  6,  2,  0, -2,
             6,  8, 10, 12, 12, 10,  8,  6,
             0,  0,  4,  8,  8,  4,  0,  0,
        ];
        private static readonly int[] QueenPst =
        [
            -10, -6, -4, -2, -2, -4, -6,-10,
             -6,  0,  4,  6,  6,  4,  0, -6,
             -4,  4,  8, 10, 10,  8,  4, -4,
             -2,  6, 10, 12, 12, 10,  6, -2,
             -2,  6, 10, 12, 12, 10,  6, -2,
             -4,  4,  8, 10, 10,  8,  4, -4,
             -6,  0,  4,  6,  6,  4,  0, -6,
            -10, -6, -4, -2, -2, -4, -6,-10,
        ];
        private static readonly int[] KingMiddlePst =
        [
             18, 24,  8, -8, -8,  8, 24, 18,
             12, 12, -4,-12,-12, -4, 12, 12,
             -8,-12,-20,-28,-28,-20,-12, -8,
            -18,-24,-32,-40,-40,-32,-24,-18,
            -24,-30,-38,-48,-48,-38,-30,-24,
            -30,-36,-44,-56,-56,-44,-36,-30,
            -36,-42,-50,-62,-62,-50,-42,-36,
            -42,-48,-56,-70,-70,-56,-48,-42,
        ];
        private static readonly int[] KingEndPst =
        [
            -28,-18,-10, -6, -6,-10,-18,-28,
            -18, -6,  4, 10, 10,  4, -6,-18,
            -10,  4, 14, 20, 20, 14,  4,-10,
             -6, 10, 20, 28, 28, 20, 10, -6,
             -6, 10, 20, 28, 28, 20, 10, -6,
            -10,  4, 14, 20, 20, 14,  4,-10,
            -18, -6,  4, 10, 10,  4, -6,-18,
            -28,-18,-10, -6, -6,-10,-18,-28,
        ];
        private static readonly ulong[,] PieceKeys = new ulong[12, 64];
        private static readonly ulong[] CastlingKeys = new ulong[16];
        private static readonly ulong[] EpKeys = new ulong[64];
        private static readonly ulong SideKey;
        private readonly char[] _squares = new char[64];
        private readonly List<ulong> _history = [];
        private bool _whiteToMove;
        private byte _castling;
        private int _epSquare = -1;
        private int _halfMove;
        private ulong _key;

        static NativeBoard()
        {
            PieceValues['P'] = PieceValues['p'] = 100;
            PieceValues['N'] = PieceValues['n'] = 320;
            PieceValues['B'] = PieceValues['b'] = 330;
            PieceValues['R'] = PieceValues['r'] = 500;
            PieceValues['Q'] = PieceValues['q'] = 900;

            var seed = 0x9E3779B97F4A7C15UL;
            ulong Next()
            {
                seed += 0x9E3779B97F4A7C15UL;
                var value = seed;
                value = (value ^ (value >> 30)) * 0xBF58476D1CE4E5B9UL;
                value = (value ^ (value >> 27)) * 0x94D049BB133111EBUL;
                return value ^ (value >> 31);
            }

            for (var piece = 0; piece < 12; piece++)
            {
                for (var square = 0; square < 64; square++)
                {
                    PieceKeys[piece, square] = Next();
                }
            }

            for (var i = 0; i < CastlingKeys.Length; i++)
            {
                CastlingKeys[i] = Next();
            }

            for (var i = 0; i < EpKeys.Length; i++)
            {
                EpKeys[i] = Next();
            }

            SideKey = Next();
        }

        public bool WhiteToMove => _whiteToMove;

        public ulong SearchKey => BuildSearchKey();

        public static NativeBoard FromFen(string fen)
        {
            var parts = fen.Split(' ', StringSplitOptions.RemoveEmptyEntries);
            if (parts.Length < 4)
            {
                throw new ArgumentException($"Invalid FEN: {fen}", nameof(fen));
            }

            var board = new NativeBoard();
            Array.Fill(board._squares, '.');
            var rank = 7;
            var file = 0;
            foreach (var ch in parts[0])
            {
                if (ch == '/')
                {
                    rank--;
                    file = 0;
                    continue;
                }

                if (char.IsDigit(ch))
                {
                    file += ch - '0';
                    continue;
                }

                board._squares[(rank * 8) + file] = ch;
                file++;
            }

            board._whiteToMove = parts[1] == "w";
            if (parts[2].Contains('K', StringComparison.Ordinal)) board._castling |= WhiteKingSide;
            if (parts[2].Contains('Q', StringComparison.Ordinal)) board._castling |= WhiteQueenSide;
            if (parts[2].Contains('k', StringComparison.Ordinal)) board._castling |= BlackKingSide;
            if (parts[2].Contains('q', StringComparison.Ordinal)) board._castling |= BlackQueenSide;
            board._epSquare = parts[3] == "-" ? -1 : SquareFromName(parts[3]);
            board._halfMove = parts.Length >= 5 && int.TryParse(parts[4], out var halfMove) ? halfMove : 0;
            board.RecomputeKey();
            board._history.Add(board._key);
            return board;
        }

        public List<ushort> GenerateLegalMoves(bool capturesOnly)
        {
            var pseudoMoves = new List<ushort>(96);
            GeneratePseudoMoves(pseudoMoves, capturesOnly);
            var legalMoves = new List<ushort>(pseudoMoves.Count);
            var movingWhite = _whiteToMove;

            foreach (var move in pseudoMoves)
            {
                var undo = MakeMove(move);
                var isLegal = !InCheck(movingWhite);
                UnmakeMove(move, undo);
                if (isLegal)
                {
                    legalMoves.Add(move);
                }
            }

            return legalMoves;
        }

        public Undo MakeMove(ushort move)
        {
            var from = From(move);
            var to = To(move);
            var flag = Flag(move);
            var piece = _squares[from];
            var epCaptureSquare = _whiteToMove ? to - 8 : to + 8;
            var captured = flag == 1 ? _squares[epCaptureSquare] : _squares[to];
            var undo = new Undo(captured, _castling, _epSquare, _halfMove, _key);

            _squares[from] = '.';
            if (flag == 1)
            {
                _squares[epCaptureSquare] = '.';
            }

            if (flag == 2)
            {
                MoveCastlingRook(to, makeMove: true);
            }

            _squares[to] = PromotionPiece(piece, flag);
            UpdateCastlingRights(from, to, piece, captured);
            _epSquare = flag == 7 ? (_whiteToMove ? from + 8 : from - 8) : -1;
            _halfMove = char.ToLowerInvariant(piece) == 'p' || captured != '.' ? 0 : _halfMove + 1;
            _whiteToMove = !_whiteToMove;
            RecomputeKey();
            _history.Add(_key);
            return undo;
        }

        public void UnmakeMove(ushort move, Undo undo)
        {
            _history.RemoveAt(_history.Count - 1);
            var from = From(move);
            var to = To(move);
            var flag = Flag(move);
            _whiteToMove = !_whiteToMove;
            var movedPiece = _squares[to];
            _squares[from] = flag is >= 3 and <= 6 ? (_whiteToMove ? 'P' : 'p') : movedPiece;
            _squares[to] = flag == 1 ? '.' : undo.Captured;

            if (flag == 1)
            {
                _squares[_whiteToMove ? to - 8 : to + 8] = undo.Captured;
            }

            if (flag == 2)
            {
                MoveCastlingRook(to, makeMove: false);
            }

            _castling = undo.Castling;
            _epSquare = undo.EpSquare;
            _halfMove = undo.HalfMove;
            _key = undo.Key;
        }

        public bool InCheck(bool white)
        {
            var king = -1;
            var kingPiece = white ? 'K' : 'k';
            for (var square = 0; square < 64; square++)
            {
                if (_squares[square] == kingPiece)
                {
                    king = square;
                    break;
                }
            }

            return king >= 0 && IsSquareAttacked(king, !white);
        }

        public int Evaluate()
        {
            var snapshot = BuildEvalSnapshot();
            var materialScore = _whiteToMove ? snapshot.MaterialBalance : -snapshot.MaterialBalance;
            var positionalScore = _whiteToMove ? snapshot.PositionalBalance : -snapshot.PositionalBalance;
            return materialScore
                + positionalScore
                + RepetitionDrawAdjustment(snapshot.MaterialBalance)
                + EndgameMopUpAdjustment(snapshot)
                + WinningEndgameRepetitionAdjustment(snapshot.MaterialBalance, snapshot.EndgameWeight);
        }

        public int MoveOrderScore(ushort move, ushort ttMove)
        {
            var score = 0;
            var movingPiece = _squares[From(move)];
            var attackerValue = PieceValues[movingPiece];
            if (IsCapture(move))
            {
                score += 10_000 + (10 * CapturedPieceValue(move)) - attackerValue;
            }

            if (IsPromotion(move))
            {
                score += 8_000 + PieceValues[PromotionPiece(movingPiece, Flag(move))];
            }

            if (move == ttMove)
            {
                score += TtMoveBonus;
            }

            if (char.ToLowerInvariant(movingPiece) != 'p' && IsAttackedByPawn(To(move), !_whiteToMove))
            {
                score -= attackerValue;
            }

            return score;
        }

        public bool IsObviouslyLosingCapture(ushort move)
        {
            return IsCapture(move) && !IsPromotion(move) && PieceValues[_squares[From(move)]] > CapturedPieceValue(move);
        }

        public bool IsDeltaPruned(ushort move, int standPat, int alpha)
        {
            var materialSwing = CapturedPieceValue(move);
            if (IsPromotion(move))
            {
                materialSwing += PieceValues[PromotionPiece(_squares[From(move)], Flag(move))] - PieceValues['p'];
            }

            return standPat + materialSwing + DeltaPruningMargin < alpha;
        }

        public string MoveToUci(ushort move)
        {
            var text = $"{NameFromSquare(From(move))}{NameFromSquare(To(move))}";
            return text + (Flag(move) switch
            {
                3 => "q",
                4 => "n",
                5 => "r",
                6 => "b",
                _ => string.Empty,
            });
        }

        private void GeneratePseudoMoves(List<ushort> moves, bool capturesOnly)
        {
            for (var from = 0; from < 64; from++)
            {
                var piece = _squares[from];
                if (piece == '.' || IsWhite(piece) != _whiteToMove)
                {
                    continue;
                }

                switch (char.ToLowerInvariant(piece))
                {
                    case 'p':
                        GeneratePawnMoves(moves, from, capturesOnly);
                        break;
                    case 'n':
                        GenerateKnightMoves(moves, from, capturesOnly);
                        break;
                    case 'b':
                        GenerateSlidingMoves(moves, from, capturesOnly, bishop: true, rook: false);
                        break;
                    case 'r':
                        GenerateSlidingMoves(moves, from, capturesOnly, bishop: false, rook: true);
                        break;
                    case 'q':
                        GenerateSlidingMoves(moves, from, capturesOnly, bishop: true, rook: true);
                        break;
                    case 'k':
                        GenerateKingMoves(moves, from, capturesOnly);
                        break;
                }
            }
        }

        private void GeneratePawnMoves(List<ushort> moves, int from, bool capturesOnly)
        {
            var rank = Rank(from);
            var file = File(from);
            var direction = _whiteToMove ? 1 : -1;
            var startRank = _whiteToMove ? 1 : 6;
            var promotionFromRank = _whiteToMove ? 6 : 1;
            var oneRank = rank + direction;

            if (!capturesOnly && IsInside(file, oneRank))
            {
                var one = Square(file, oneRank);
                if (_squares[one] == '.')
                {
                    AddPawnMove(moves, from, one, rank == promotionFromRank);
                    var twoRank = rank + (direction * 2);
                    if (rank == startRank && IsInside(file, twoRank) && _squares[Square(file, twoRank)] == '.')
                    {
                        moves.Add(Encode(from, Square(file, twoRank), 7));
                    }
                }
            }

            for (var fileDelta = -1; fileDelta <= 1; fileDelta += 2)
            {
                var targetFile = file + fileDelta;
                var targetRank = rank + direction;
                if (!IsInside(targetFile, targetRank))
                {
                    continue;
                }

                var to = Square(targetFile, targetRank);
                if (_squares[to] != '.' && IsWhite(_squares[to]) != _whiteToMove)
                {
                    AddPawnMove(moves, from, to, rank == promotionFromRank);
                }
                else if (to == _epSquare)
                {
                    moves.Add(Encode(from, to, 1));
                }
            }
        }

        private static void AddPawnMove(List<ushort> moves, int from, int to, bool promotion)
        {
            if (!promotion)
            {
                moves.Add(Encode(from, to, 0));
                return;
            }

            moves.Add(Encode(from, to, 3));
            moves.Add(Encode(from, to, 4));
            moves.Add(Encode(from, to, 5));
            moves.Add(Encode(from, to, 6));
        }

        private void GenerateKnightMoves(List<ushort> moves, int from, bool capturesOnly)
        {
            var file = File(from);
            var rank = Rank(from);
            ReadOnlySpan<(int File, int Rank)> deltas = [(-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1)];
            foreach (var delta in deltas)
            {
                AddStepMove(moves, from, file + delta.File, rank + delta.Rank, capturesOnly);
            }
        }

        private void GenerateKingMoves(List<ushort> moves, int from, bool capturesOnly)
        {
            var file = File(from);
            var rank = Rank(from);
            for (var df = -1; df <= 1; df++)
            {
                for (var dr = -1; dr <= 1; dr++)
                {
                    if (df != 0 || dr != 0)
                    {
                        AddStepMove(moves, from, file + df, rank + dr, capturesOnly);
                    }
                }
            }

            if (capturesOnly || InCheck(_whiteToMove))
            {
                return;
            }

            if (_whiteToMove)
            {
                AddCastleMove(moves, from, WhiteKingSide, "f1", "g1", "g1", attackedByWhite: false);
                if ((_castling & WhiteQueenSide) != 0
                    && Empty("d1")
                    && Empty("c1")
                    && Empty("b1")
                    && !IsSquareAttacked(SquareFromName("d1"), false)
                    && !IsSquareAttacked(SquareFromName("c1"), false))
                {
                    moves.Add(Encode(from, SquareFromName("c1"), 2));
                }
            }
            else
            {
                AddCastleMove(moves, from, BlackKingSide, "f8", "g8", "g8", attackedByWhite: true);
                if ((_castling & BlackQueenSide) != 0
                    && Empty("d8")
                    && Empty("c8")
                    && Empty("b8")
                    && !IsSquareAttacked(SquareFromName("d8"), true)
                    && !IsSquareAttacked(SquareFromName("c8"), true))
                {
                    moves.Add(Encode(from, SquareFromName("c8"), 2));
                }
            }
        }

        private void AddCastleMove(List<ushort> moves, int from, int right, string throughName, string targetName, string moveToName, bool attackedByWhite)
        {
            var through = SquareFromName(throughName);
            var target = SquareFromName(targetName);
            if ((_castling & right) != 0
                && _squares[through] == '.'
                && _squares[target] == '.'
                && !IsSquareAttacked(through, attackedByWhite)
                && !IsSquareAttacked(target, attackedByWhite))
            {
                moves.Add(Encode(from, SquareFromName(moveToName), 2));
            }
        }

        private void GenerateSlidingMoves(List<ushort> moves, int from, bool capturesOnly, bool bishop, bool rook)
        {
            if (bishop)
            {
                AddRayMoves(moves, from, 1, 1, capturesOnly);
                AddRayMoves(moves, from, 1, -1, capturesOnly);
                AddRayMoves(moves, from, -1, 1, capturesOnly);
                AddRayMoves(moves, from, -1, -1, capturesOnly);
            }

            if (rook)
            {
                AddRayMoves(moves, from, 1, 0, capturesOnly);
                AddRayMoves(moves, from, -1, 0, capturesOnly);
                AddRayMoves(moves, from, 0, 1, capturesOnly);
                AddRayMoves(moves, from, 0, -1, capturesOnly);
            }
        }

        private void AddRayMoves(List<ushort> moves, int from, int df, int dr, bool capturesOnly)
        {
            var file = File(from) + df;
            var rank = Rank(from) + dr;
            while (IsInside(file, rank))
            {
                var to = Square(file, rank);
                var target = _squares[to];
                if (target != '.')
                {
                    if (IsWhite(target) != _whiteToMove)
                    {
                        moves.Add(Encode(from, to, 0));
                    }

                    break;
                }

                if (!capturesOnly)
                {
                    moves.Add(Encode(from, to, 0));
                }

                file += df;
                rank += dr;
            }
        }

        private void AddStepMove(List<ushort> moves, int from, int file, int rank, bool capturesOnly)
        {
            if (!IsInside(file, rank))
            {
                return;
            }

            var to = Square(file, rank);
            var target = _squares[to];
            if (target != '.' && IsWhite(target) == _whiteToMove)
            {
                return;
            }

            if (!capturesOnly || target != '.')
            {
                moves.Add(Encode(from, to, 0));
            }
        }

        private bool IsSquareAttacked(int square, bool byWhite)
        {
            if (IsAttackedByPawn(square, byWhite))
            {
                return true;
            }

            var file = File(square);
            var rank = Rank(square);
            ReadOnlySpan<(int File, int Rank)> knightDeltas = [(-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1)];
            foreach (var delta in knightDeltas)
            {
                if (PieceAt(file + delta.File, rank + delta.Rank) == (byWhite ? 'N' : 'n'))
                {
                    return true;
                }
            }

            if (AttackedBySlider(square, byWhite, bishop: true, rook: false)
                || AttackedBySlider(square, byWhite, bishop: false, rook: true))
            {
                return true;
            }

            for (var df = -1; df <= 1; df++)
            {
                for (var dr = -1; dr <= 1; dr++)
                {
                    if ((df != 0 || dr != 0) && PieceAt(file + df, rank + dr) == (byWhite ? 'K' : 'k'))
                    {
                        return true;
                    }
                }
            }

            return false;
        }

        private bool IsAttackedByPawn(int square, bool byWhite)
        {
            var file = File(square);
            var rank = Rank(square);
            var pawnRank = rank + (byWhite ? -1 : 1);
            return PieceAt(file - 1, pawnRank) == (byWhite ? 'P' : 'p')
                || PieceAt(file + 1, pawnRank) == (byWhite ? 'P' : 'p');
        }

        private bool AttackedBySlider(int square, bool byWhite, bool bishop, bool rook)
        {
            if (bishop)
            {
                if (RayAttacked(square, byWhite, 1, 1, 'b') || RayAttacked(square, byWhite, 1, -1, 'b')
                    || RayAttacked(square, byWhite, -1, 1, 'b') || RayAttacked(square, byWhite, -1, -1, 'b'))
                {
                    return true;
                }
            }

            if (rook)
            {
                return RayAttacked(square, byWhite, 1, 0, 'r') || RayAttacked(square, byWhite, -1, 0, 'r')
                    || RayAttacked(square, byWhite, 0, 1, 'r') || RayAttacked(square, byWhite, 0, -1, 'r');
            }

            return false;
        }

        private bool RayAttacked(int square, bool byWhite, int df, int dr, char slider)
        {
            var file = File(square) + df;
            var rank = Rank(square) + dr;
            while (IsInside(file, rank))
            {
                var piece = _squares[Square(file, rank)];
                if (piece != '.')
                {
                    if (IsWhite(piece) != byWhite)
                    {
                        return false;
                    }

                    var lower = char.ToLowerInvariant(piece);
                    return lower == slider || lower == 'q';
                }

                file += df;
                rank += dr;
            }

            return false;
        }

        private EvalSnapshot BuildEvalSnapshot()
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
            var whitePositional = 0;
            var blackPositional = 0;
            Span<int> whitePawnFiles = stackalloc int[8];
            Span<int> blackPawnFiles = stackalloc int[8];
            Span<int> whiteRookSquares = stackalloc int[10];
            Span<int> blackRookSquares = stackalloc int[10];

            for (var square = 0; square < 64; square++)
            {
                var piece = _squares[square];
                if (piece == '.')
                {
                    continue;
                }

                var value = PieceValues[piece];
                var isWhite = IsWhite(piece);
                var positionalValue = PositionalValue(piece, square);
                if (isWhite)
                {
                    whiteMaterial += value;
                    whitePositional += positionalValue;
                }
                else
                {
                    blackMaterial += value;
                    blackPositional += positionalValue;
                }

                switch (char.ToLowerInvariant(piece))
                {
                    case 'p':
                        if (isWhite)
                        {
                            whitePawnFiles[File(square)]++;
                            whitePawnDanger += Rank(square);
                            if (IsPassedPawn(square, white: true))
                            {
                                whitePositional += PassedPawnBonus[Rank(square)];
                            }
                        }
                        else
                        {
                            blackPawnFiles[File(square)]++;
                            blackPawnDanger += 7 - Rank(square);
                            if (IsPassedPawn(square, white: false))
                            {
                                blackPositional += PassedPawnBonus[7 - Rank(square)];
                            }
                        }

                        break;
                    case 'n':
                        if (isWhite)
                        {
                            whiteKnights++;
                            whiteNonPawnMaterial += value;
                            if (IsKnightOutpost(square, white: true))
                            {
                                whitePositional += KnightOutpostBonus;
                            }
                        }
                        else
                        {
                            blackKnights++;
                            blackNonPawnMaterial += value;
                            if (IsKnightOutpost(square, white: false))
                            {
                                blackPositional += KnightOutpostBonus;
                            }
                        }
                        break;
                    case 'b':
                        if (isWhite) { whiteBishops++; whiteNonPawnMaterial += value; }
                        else { blackBishops++; blackNonPawnMaterial += value; }
                        break;
                    case 'r':
                        if (isWhite)
                        {
                            if (whiteRooks < whiteRookSquares.Length)
                            {
                                whiteRookSquares[whiteRooks] = square;
                            }

                            whiteRooks++;
                            whiteNonPawnMaterial += value;
                        }
                        else
                        {
                            if (blackRooks < blackRookSquares.Length)
                            {
                                blackRookSquares[blackRooks] = square;
                            }

                            blackRooks++;
                            blackNonPawnMaterial += value;
                        }
                        break;
                    case 'q':
                        if (isWhite) { whiteQueens++; whiteNonPawnMaterial += value; }
                        else { blackQueens++; blackNonPawnMaterial += value; }
                        break;
                }
            }

            whitePositional += RookFileBonus(whiteRookSquares, Math.Min(whiteRooks, whiteRookSquares.Length), whitePawnFiles, blackPawnFiles);
            blackPositional += RookFileBonus(blackRookSquares, Math.Min(blackRooks, blackRookSquares.Length), blackPawnFiles, whitePawnFiles);

            var totalNonPawnMaterial = whiteNonPawnMaterial + blackNonPawnMaterial;
            var endgameWeight = 1.0 - (Math.Min(totalNonPawnMaterial, EndgameNonPawnMaterialThreshold) / (double)EndgameNonPawnMaterialThreshold);
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
                whitePositional,
                blackPositional,
                Math.Clamp(endgameWeight, 0.0, 1.0));
        }

        private static int RookFileBonus(ReadOnlySpan<int> rookSquares, int rookCount, ReadOnlySpan<int> ownPawnFiles, ReadOnlySpan<int> enemyPawnFiles)
        {
            var bonus = 0;
            for (var index = 0; index < rookCount; index++)
            {
                var file = File(rookSquares[index]);
                if (ownPawnFiles[file] != 0)
                {
                    continue;
                }

                bonus += enemyPawnFiles[file] == 0 ? RookOpenFileBonus : RookSemiOpenFileBonus;
            }

            return bonus;
        }

        private bool IsKnightOutpost(int square, bool white)
        {
            var rank = Rank(square);
            if (white ? rank < 3 || rank > 5 : rank < 2 || rank > 4)
            {
                return false;
            }

            return IsAttackedByPawn(square, white) && !IsAttackedByPawn(square, !white);
        }

        private int PositionalValue(char piece, int square)
        {
            var lookupSquare = IsWhite(piece) ? square : MirrorSquare(square);
            return char.ToLowerInvariant(piece) switch
            {
                'p' => PawnPst[lookupSquare],
                'n' => KnightPst[lookupSquare],
                'b' => BishopPst[lookupSquare],
                'r' => RookPst[lookupSquare],
                'q' => QueenPst[lookupSquare],
                'k' => (int)((KingMiddlePst[lookupSquare] * (1.0 - CurrentEndgameWeight()))
                    + (KingEndPst[lookupSquare] * CurrentEndgameWeight())),
                _ => 0,
            };
        }

        private bool IsPassedPawn(int square, bool white)
        {
            var file = File(square);
            var rank = Rank(square);
            var enemyPawn = white ? 'p' : 'P';
            var rankDirection = white ? 1 : -1;

            for (var targetFile = Math.Max(0, file - 1); targetFile <= Math.Min(7, file + 1); targetFile++)
            {
                for (var targetRank = rank + rankDirection; targetRank >= 0 && targetRank < 8; targetRank += rankDirection)
                {
                    if (_squares[Square(targetFile, targetRank)] == enemyPawn)
                    {
                        return false;
                    }
                }
            }

            return true;
        }

        private double CurrentEndgameWeight()
        {
            var totalNonPawnMaterial = 0;
            for (var square = 0; square < 64; square++)
            {
                var piece = _squares[square];
                if (piece != '.' && char.ToLowerInvariant(piece) != 'p' && char.ToLowerInvariant(piece) != 'k')
                {
                    totalNonPawnMaterial += PieceValues[piece];
                }
            }

            return 1.0 - (Math.Min(totalNonPawnMaterial, EndgameNonPawnMaterialThreshold) / (double)EndgameNonPawnMaterialThreshold);
        }

        private int RepetitionDrawAdjustment(int materialBalance)
        {
            var adjustment = 0;
            if (IsRepetition(2))
            {
                adjustment -= RepeatPositionPenalty;
            }

            if (IsRepetition(3))
            {
                adjustment -= ThreefoldRepetitionPenalty;
            }

            if (_halfMove >= 100 || IsRepetition(3))
            {
                adjustment -= DrawBasePenalty;
            }

            return adjustment;
        }

        private int EndgameMopUpAdjustment(EvalSnapshot snapshot)
        {
            if (snapshot.EndgameWeight <= 0.0)
            {
                return 0;
            }

            var whiteBonus = 0;
            var blackBonus = 0;
            if (snapshot.MaterialBalance >= EndgameMaterialAdvantageThreshold && HasForcingMatingMaterial(snapshot, white: true))
            {
                whiteBonus = ForceKingToCornerEndgameEval(strongerWhite: true, snapshot.EndgameWeight);
                whiteBonus += (8 - DefenderKingMobility(losingWhite: false)) * EndgameKingMobilityScale;
                whiteBonus -= (int)(snapshot.BlackPawnDanger * EndgamePawnDangerScale * snapshot.EndgameWeight);
            }

            if (snapshot.MaterialBalance <= -EndgameMaterialAdvantageThreshold && HasForcingMatingMaterial(snapshot, white: false))
            {
                blackBonus = ForceKingToCornerEndgameEval(strongerWhite: false, snapshot.EndgameWeight);
                blackBonus += (8 - DefenderKingMobility(losingWhite: true)) * EndgameKingMobilityScale;
                blackBonus -= (int)(snapshot.WhitePawnDanger * EndgamePawnDangerScale * snapshot.EndgameWeight);
            }

            var score = whiteBonus - blackBonus;
            return _whiteToMove ? score : -score;
        }

        private int WinningEndgameRepetitionAdjustment(int materialBalance, double endgameWeight)
        {
            var materialEdge = _whiteToMove ? materialBalance : -materialBalance;
            if (materialEdge <= EndgameMaterialAdvantageThreshold || endgameWeight <= 0.0)
            {
                return 0;
            }

            var adjustment = 0;
            if (IsRepetition(2))
            {
                adjustment -= WinningEndgameRepeatPenalty + (materialEdge / 20);
            }

            if (IsRepetition(3))
            {
                adjustment -= WinningEndgameRepeatPenalty + (materialEdge / 10);
            }

            return adjustment;
        }

        private static bool HasForcingMatingMaterial(EvalSnapshot snapshot, bool white)
        {
            var queens = white ? snapshot.WhiteQueens : snapshot.BlackQueens;
            var rooks = white ? snapshot.WhiteRooks : snapshot.BlackRooks;
            var bishops = white ? snapshot.WhiteBishops : snapshot.BlackBishops;
            var knights = white ? snapshot.WhiteKnights : snapshot.BlackKnights;
            return queens > 0 || rooks > 0 || bishops >= 2 || (bishops >= 1 && knights >= 1);
        }

        private int ForceKingToCornerEndgameEval(bool strongerWhite, double weight)
        {
            var friendlyKing = FindKing(strongerWhite);
            var opponentKing = FindKing(!strongerWhite);
            if (friendlyKing < 0 || opponentKing < 0)
            {
                return 0;
            }

            var losingKingCmd = CenterManhattanDistance(opponentKing);
            var kingsMd = ManhattanDistance(friendlyKing, opponentKing);
            var rawScore = (4.7 * losingKingCmd) + (1.6 * (14 - kingsMd));
            return (int)(rawScore * EndgameMopUpScale * weight);
        }

        private int DefenderKingMobility(bool losingWhite)
        {
            var king = FindKing(losingWhite);
            if (king < 0)
            {
                return 0;
            }

            var mobility = 0;
            var file = File(king);
            var rank = Rank(king);
            for (var df = -1; df <= 1; df++)
            {
                for (var dr = -1; dr <= 1; dr++)
                {
                    if (df == 0 && dr == 0)
                    {
                        continue;
                    }

                    var targetFile = file + df;
                    var targetRank = rank + dr;
                    if (!IsInside(targetFile, targetRank))
                    {
                        continue;
                    }

                    var target = Square(targetFile, targetRank);
                    var occupant = _squares[target];
                    if (occupant != '.' && IsWhite(occupant) == losingWhite)
                    {
                        continue;
                    }

                    if (!IsSquareAttacked(target, !losingWhite))
                    {
                        mobility++;
                    }
                }
            }

            return mobility;
        }

        private int FindKing(bool white)
        {
            var king = white ? 'K' : 'k';
            for (var square = 0; square < 64; square++)
            {
                if (_squares[square] == king)
                {
                    return square;
                }
            }

            return -1;
        }

        private bool IsRepetition(int count)
        {
            return CurrentPositionRepetitionCount() >= count;
        }

        private int CurrentPositionRepetitionCount()
        {
            var seen = 0;
            foreach (var key in _history)
            {
                if (key == _key)
                {
                    seen++;
                }
            }

            return seen;
        }

        private bool IsCapture(ushort move)
        {
            return Flag(move) == 1 || _squares[To(move)] != '.';
        }

        private int CapturedPieceValue(ushort move)
        {
            if (Flag(move) == 1)
            {
                return PieceValues['p'];
            }

            var captured = _squares[To(move)];
            return captured == '.' ? 0 : PieceValues[captured];
        }

        private static bool IsPromotion(ushort move) => Flag(move) is >= 3 and <= 6;

        private void MoveCastlingRook(int kingTo, bool makeMove)
        {
            if (kingTo == SquareFromName("g1"))
            {
                _squares[SquareFromName(makeMove ? "f1" : "h1")] = 'R';
                _squares[SquareFromName(makeMove ? "h1" : "f1")] = '.';
            }
            else if (kingTo == SquareFromName("c1"))
            {
                _squares[SquareFromName(makeMove ? "d1" : "a1")] = 'R';
                _squares[SquareFromName(makeMove ? "a1" : "d1")] = '.';
            }
            else if (kingTo == SquareFromName("g8"))
            {
                _squares[SquareFromName(makeMove ? "f8" : "h8")] = 'r';
                _squares[SquareFromName(makeMove ? "h8" : "f8")] = '.';
            }
            else if (kingTo == SquareFromName("c8"))
            {
                _squares[SquareFromName(makeMove ? "d8" : "a8")] = 'r';
                _squares[SquareFromName(makeMove ? "a8" : "d8")] = '.';
            }
        }

        private void UpdateCastlingRights(int from, int to, char piece, char captured)
        {
            if (piece == 'K') _castling = (byte)(_castling & ~(WhiteKingSide | WhiteQueenSide));
            if (piece == 'k') _castling = (byte)(_castling & ~(BlackKingSide | BlackQueenSide));
            if (from == SquareFromName("h1") || to == SquareFromName("h1")) _castling = (byte)(_castling & ~WhiteKingSide);
            if (from == SquareFromName("a1") || to == SquareFromName("a1")) _castling = (byte)(_castling & ~WhiteQueenSide);
            if (from == SquareFromName("h8") || to == SquareFromName("h8")) _castling = (byte)(_castling & ~BlackKingSide);
            if (from == SquareFromName("a8") || to == SquareFromName("a8")) _castling = (byte)(_castling & ~BlackQueenSide);
        }

        private ulong BuildSearchKey()
        {
            return _key
                ^ ((ulong)_halfMove * 0x9E3779B97F4A7C15UL)
                ^ ((ulong)CurrentPositionRepetitionCount() * 0xBF58476D1CE4E5B9UL);
        }

        private void RecomputeKey()
        {
            var key = _whiteToMove ? SideKey : 0UL;
            for (var square = 0; square < 64; square++)
            {
                var piece = _squares[square];
                if (piece != '.')
                {
                    key ^= PieceKeys[PieceIndex(piece), square];
                }
            }

            key ^= CastlingKeys[_castling];
            if (_epSquare >= 0)
            {
                key ^= EpKeys[_epSquare];
            }

            _key = key == 0 ? 1 : key;
        }

        private static int CenterManhattanDistance(int square)
        {
            return Math.Max(3 - File(square), File(square) - 4) + Math.Max(3 - Rank(square), Rank(square) - 4);
        }

        private static int ManhattanDistance(int a, int b)
        {
            return Math.Abs(File(a) - File(b)) + Math.Abs(Rank(a) - Rank(b));
        }

        private static char PromotionPiece(char pawn, int flag)
        {
            var white = IsWhite(pawn);
            return flag switch
            {
                3 => white ? 'Q' : 'q',
                4 => white ? 'N' : 'n',
                5 => white ? 'R' : 'r',
                6 => white ? 'B' : 'b',
                _ => pawn,
            };
        }

        private bool Empty(string squareName) => _squares[SquareFromName(squareName)] == '.';

        private char PieceAt(int file, int rank) => IsInside(file, rank) ? _squares[Square(file, rank)] : '.';

        private static bool IsWhite(char piece) => char.IsUpper(piece);

        private static bool IsInside(int file, int rank) => file is >= 0 and < 8 && rank is >= 0 and < 8;

        private static int File(int square) => square & 7;

        private static int Rank(int square) => square >> 3;

        private static int Square(int file, int rank) => (rank * 8) + file;

        private static int MirrorSquare(int square) => Square(File(square), 7 - Rank(square));

        private static ushort Encode(int from, int to, int flag) => (ushort)(from | (to << 6) | (flag << 12));

        private static int From(ushort move) => move & 63;

        private static int To(ushort move) => (move >> 6) & 63;

        private static int Flag(ushort move) => move >> 12;

        private static int SquareFromName(string name) => (name[0] - 'a') + ((name[1] - '1') * 8);

        private static string NameFromSquare(int square) => $"{(char)('a' + File(square))}{(char)('1' + Rank(square))}";

        private static int PieceIndex(char piece)
        {
            return piece switch
            {
                'P' => 0,
                'N' => 1,
                'B' => 2,
                'R' => 3,
                'Q' => 4,
                'K' => 5,
                'p' => 6,
                'n' => 7,
                'b' => 8,
                'r' => 9,
                'q' => 10,
                'k' => 11,
                _ => 0,
            };
        }
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
        int WhitePositional,
        int BlackPositional,
        double EndgameWeight)
    {
        public int MaterialBalance => WhiteMaterial - BlackMaterial;
        public int PositionalBalance => WhitePositional - BlackPositional;
    }
}
