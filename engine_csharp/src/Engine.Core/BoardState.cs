using System.Globalization;
using Chess;

namespace Engine.Core;

public sealed class BoardState
{
    private readonly ChessBoard _board;
    private readonly List<ulong> _history;
    private string _currentFen = string.Empty;
    private string _normalizedFenKey = string.Empty;
    private ulong _transpositionKey;
    private int _halfMoveClock;

    public BoardState(string fen)
    {
        _board = ChessBoard.LoadFromFen(fen);
        _history = [];
        SyncCachedState();
        _history.Add(_transpositionKey);
    }

    public ChessBoard InnerBoard => _board;

    public bool WhiteToMove => _board.Turn == PieceColor.White;

    public bool IsGameOver => _board.IsEndGame || !HasAnyLegalMoves();

    public bool IsCheckmate => !HasAnyLegalMoves() && IsCurrentSideInCheck();

    public string Fen => _currentFen;

    public ulong TranspositionKey => _transpositionKey;

    public IReadOnlyList<ulong> History => _history;

    public List<Move> LegalMoves()
    {
        return _board.Moves().ToList();
    }

    public bool HasAnyLegalMoves()
    {
        return _board.Moves().Any();
    }

    public int LegalMoveCount()
    {
        return _board.Moves().Count();
    }

    public void Push(Move move)
    {
        _board.Move(move);
        SyncCachedState();
        _history.Add(_transpositionKey);
    }

    public void Pop()
    {
        if (_history.Count <= 1)
        {
            throw new InvalidOperationException("Cannot pop the root position.");
        }

        _board.Cancel();
        _history.RemoveAt(_history.Count - 1);
        SyncCachedState();
    }

    public bool IsCapture(Move move)
    {
        return move.CapturedPiece is not null || move.IsEnPassant;
    }

    public bool IsCurrentSideInCheck()
    {
        return WhiteToMove ? _board.WhiteKingChecked : _board.BlackKingChecked;
    }

    public string GetSan(Move move)
    {
        if (!string.IsNullOrWhiteSpace(move.San))
        {
            return move.San!;
        }

        Push(move);
        try
        {
            return move.San ?? move.ToString();
        }
        finally
        {
            Pop();
        }
    }

    public bool IsRepetition(int count)
    {
        var current = _transpositionKey;
        var seen = 0;
        foreach (var key in _history)
        {
            if (key == current)
            {
                seen++;
            }
        }

        return seen >= count;
    }

    public bool CanClaimThreefoldRepetition()
    {
        return IsRepetition(3);
    }

    public bool CanClaimDraw()
    {
        if (CanClaimThreefoldRepetition())
        {
            return true;
        }

        if (_halfMoveClock >= 100)
        {
            return true;
        }

        return _board.IsEndGame && !IsCheckmate;
    }

    public bool IsAttackedBy(PieceColor attackerColor, Position square)
    {
        for (short y = 0; y < ChessBoard.MAX_ROWS; y++)
        {
            for (short x = 0; x < ChessBoard.MAX_COLS; x++)
            {
                var piece = _board[x, y];
                if (piece is null || piece.Color != attackerColor)
                {
                    continue;
                }

                var from = new Position(x, y);
                if (AttacksSquare(from, piece, square))
                {
                    return true;
                }
            }
        }

        return false;
    }

    public bool IsAttackedByPawn(PieceColor attackerColor, Position square)
    {
        var pawnRankOffset = attackerColor == PieceColor.White ? -1 : 1;
        var pawnRank = square.Y + pawnRankOffset;
        if (pawnRank < 0 || pawnRank >= ChessBoard.MAX_ROWS)
        {
            return false;
        }

        foreach (var pawnFile in new[] { square.X - 1, square.X + 1 })
        {
            if (pawnFile < 0 || pawnFile >= ChessBoard.MAX_COLS)
            {
                continue;
            }

            var piece = _board[pawnFile, pawnRank];
            if (piece is not null
                && piece.Color == attackerColor
                && char.ToLowerInvariant(piece.ToFenChar()) == 'p')
            {
                return true;
            }
        }

        return false;
    }

    public IEnumerable<Position> SquaresWithPiece(char fenPieceLower, PieceColor color)
    {
        for (short y = 0; y < ChessBoard.MAX_ROWS; y++)
        {
            for (short x = 0; x < ChessBoard.MAX_COLS; x++)
            {
                var piece = _board[x, y];
                if (piece is null || piece.Color != color)
                {
                    continue;
                }

                if (char.ToLowerInvariant(piece.ToFenChar()) == fenPieceLower)
                {
                    yield return new Position(x, y);
                }
            }
        }
    }

    public Piece? PieceAt(Position square)
    {
        return _board[square];
    }

    public Position? King(PieceColor color)
    {
        return color == PieceColor.White ? _board.WhiteKing : _board.BlackKing;
    }

    public BoardState CloneWithTurn(PieceColor color)
    {
        var parts = ToFen().Split(' ', StringSplitOptions.RemoveEmptyEntries);
        if (parts.Length < 2)
        {
            throw new InvalidOperationException("Board FEN is missing the side-to-move field.");
        }

        parts[1] = color == PieceColor.White ? "w" : "b";
        return new BoardState(string.Join(" ", parts));
    }

    private string ToFen()
    {
        return _board.ToFen();
    }

    private void SyncCachedState()
    {
        _currentFen = ToFen();

        var parts = _currentFen.Split(' ', StringSplitOptions.RemoveEmptyEntries);
        _normalizedFenKey = parts.Length >= 4
            ? string.Join(" ", parts.Take(4))
            : _currentFen;
        _halfMoveClock = parts.Length >= 5 && int.TryParse(parts[4], NumberStyles.Integer, CultureInfo.InvariantCulture, out var value)
            ? value
            : 0;
        _transpositionKey = ZobristHash.Compute(_normalizedFenKey);
    }

    private bool AttacksSquare(Position from, Piece piece, Position target)
    {
        var fileDelta = target.X - from.X;
        var rankDelta = target.Y - from.Y;
        var absFile = Math.Abs(fileDelta);
        var absRank = Math.Abs(rankDelta);
        var pieceType = char.ToLowerInvariant(piece.ToFenChar());

        return pieceType switch
        {
            'p' => PawnAttacks(piece.Color, fileDelta, rankDelta),
            'n' => (absFile == 1 && absRank == 2) || (absFile == 2 && absRank == 1),
            'b' => absFile == absRank && ClearRay(from, target),
            'r' => (fileDelta == 0 || rankDelta == 0) && ClearRay(from, target),
            'q' => ((fileDelta == 0 || rankDelta == 0) || (absFile == absRank)) && ClearRay(from, target),
            'k' => absFile <= 1 && absRank <= 1,
            _ => false,
        };
    }

    private static bool PawnAttacks(PieceColor color, int fileDelta, int rankDelta)
    {
        var direction = color == PieceColor.White ? 1 : -1;
        return Math.Abs(fileDelta) == 1 && rankDelta == direction;
    }

    private bool ClearRay(Position from, Position to)
    {
        var dx = Math.Sign(to.X - from.X);
        var dy = Math.Sign(to.Y - from.Y);
        var x = from.X + dx;
        var y = from.Y + dy;

        while (x != to.X || y != to.Y)
        {
            if (_board[x, y] is not null)
            {
                return false;
            }

            x += (short)dx;
            y += (short)dy;
        }

        return true;
    }
}
