using Chess;

namespace Engine.Core;

public static class OpeningBook
{
    private const string LookupFileName = "Openings.lookup.tsv";
    private const int StartingPieceCount = 32;
    private static readonly Lazy<Dictionary<string, string[]>> Lookup = new(LoadLookup);

    public static bool TryGetMove(BoardState board, out SearchResult result)
    {
        result = null!;
        if (!HasAllStartingPieces(board))
        {
            return false;
        }

        var key = NormalizeFenKey(board.Fen);
        if (!Lookup.Value.TryGetValue(key, out var candidateMoves) || candidateMoves.Length == 0)
        {
            return false;
        }

        var legalMoves = board.LegalMoves();
        var legalByUci = legalMoves.ToDictionary(MoveToUci, StringComparer.Ordinal);
        var legalCandidates = candidateMoves
            .Where(legalByUci.ContainsKey)
            .Distinct(StringComparer.Ordinal)
            .ToArray();
        if (legalCandidates.Length == 0)
        {
            return false;
        }

        var selectedUci = legalCandidates[Random.Shared.Next(legalCandidates.Length)];
        var selectedMove = legalByUci[selectedUci];
        result = new SearchResult(
            selectedMove,
            board.GetSan(selectedMove),
            0,
            0,
            CompletedDepth: 0,
            TimedOut: false,
            NodesSearched: 0);
        return true;
    }

    public static string NormalizeFenKey(string fen)
    {
        var parts = fen.Split(' ', StringSplitOptions.RemoveEmptyEntries);
        if (parts.Length < 4)
        {
            throw new InvalidOperationException($"FEN must contain at least 4 fields: {fen}");
        }

        return string.Join(" ", parts.Take(4));
    }

    private static Dictionary<string, string[]> LoadLookup()
    {
        var path = FindLookupPath();
        if (!File.Exists(path))
        {
            return new Dictionary<string, string[]>(StringComparer.Ordinal);
        }

        var lookup = new Dictionary<string, string[]>(StringComparer.Ordinal);
        foreach (var rawLine in File.ReadLines(path))
        {
            var line = rawLine.Trim();
            if (string.IsNullOrWhiteSpace(line) || line.StartsWith('#'))
            {
                continue;
            }

            var columns = line.Split('\t');
            if (columns.Length != 2)
            {
                continue;
            }

            var moves = columns[1]
                .Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
                .Distinct(StringComparer.Ordinal)
                .ToArray();
            if (moves.Length > 0)
            {
                lookup[columns[0]] = moves;
            }
        }

        return lookup;
    }

    private static bool HasAllStartingPieces(BoardState board)
    {
        var placement = board.Fen.Split(' ', StringSplitOptions.RemoveEmptyEntries)[0];
        var pieceCount = placement.Count(char.IsLetter);
        return pieceCount == StartingPieceCount;
    }

    private static string MoveToUci(Move move)
    {
        var promotion = move.Promotion is null
            ? string.Empty
            : char.ToLowerInvariant(move.Promotion.ToFenChar()).ToString();
        return $"{move.OriginalPosition}{move.NewPosition}{promotion}";
    }

    private static string FindLookupPath()
    {
        var outputPath = Path.Combine(AppContext.BaseDirectory, LookupFileName);
        if (File.Exists(outputPath))
        {
            return outputPath;
        }

        var current = new DirectoryInfo(AppContext.BaseDirectory);
        while (current is not null)
        {
            var candidate = Path.GetFullPath(Path.Combine(current.FullName, "..", "..", "..", ".."));
            var lookupPath = Path.Combine(candidate, LookupFileName);
            if (File.Exists(lookupPath)
                && File.Exists(Path.Combine(candidate, "README.md"))
                && Directory.Exists(Path.Combine(candidate, "engine_csharp")))
            {
                return lookupPath;
            }

            current = current.Parent;
        }

        return Path.Combine(Directory.GetCurrentDirectory(), LookupFileName);
    }
}
