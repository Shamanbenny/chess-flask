using Chess;

namespace Engine.Core;

public static class OpeningBook
{
    private const string LookupFileName = "Openings.lookup.tsv";
    private const int StartingPieceCount = 32;
    private static readonly Lazy<string> LookupPath = new(FindLookupPath);
    private static readonly Lazy<Dictionary<string, string[]>> Lookup = new(LoadLookup);

    public static bool TryGetMove(BoardState board, out SearchResult result)
    {
        return TryGetMove(board, out result, out _);
    }

    public static bool TryGetMove(
        BoardState board,
        out SearchResult result,
        out IReadOnlyDictionary<string, object?> debugDetails)
    {
        result = null!;
        var pieceCount = CountPieces(board);
        var key = NormalizeFenKey(board.Fen);
        var lookup = Lookup.Value;
        var diagnostics = new Dictionary<string, object?>
        {
            ["enabled"] = true,
            ["lookup_file"] = LookupPath.Value,
            ["lookup_position_count"] = lookup.Count,
            ["fen_key"] = key,
            ["position_piece_count"] = pieceCount,
            ["requires_full_starting_piece_count"] = StartingPieceCount,
        };

        if (pieceCount != StartingPieceCount)
        {
            diagnostics["matched_position"] = false;
            diagnostics["candidate_move_count"] = 0;
            diagnostics["legal_candidate_move_count"] = 0;
            diagnostics["skipped_reason"] = "position_is_not_in_starting_setup";
            debugDetails = diagnostics;
            return false;
        }

        if (!lookup.TryGetValue(key, out var candidateMoves) || candidateMoves.Length == 0)
        {
            diagnostics["matched_position"] = false;
            diagnostics["candidate_move_count"] = 0;
            diagnostics["legal_candidate_move_count"] = 0;
            diagnostics["skipped_reason"] = "position_not_found_in_lookup";
            debugDetails = diagnostics;
            return false;
        }

        var legalMoves = board.LegalMoves();
        var legalByUci = legalMoves.ToDictionary(MoveToUci, StringComparer.Ordinal);
        var legalCandidates = candidateMoves
            .Where(legalByUci.ContainsKey)
            .Distinct(StringComparer.Ordinal)
            .ToArray();
        diagnostics["matched_position"] = true;
        diagnostics["candidate_move_count"] = candidateMoves.Length;
        diagnostics["legal_candidate_move_count"] = legalCandidates.Length;
        if (legalCandidates.Length == 0)
        {
            diagnostics["skipped_reason"] = "book_moves_not_legal_in_current_position";
            debugDetails = diagnostics;
            return false;
        }

        var selectedUci = legalCandidates[Random.Shared.Next(legalCandidates.Length)];
        var selectedMove = legalByUci[selectedUci];
        diagnostics["selected_move_uci"] = selectedUci;
        result = new SearchResult(
            selectedMove,
            board.GetSan(selectedMove),
            0,
            0,
            CompletedDepth: 0,
            TimedOut: false,
            NodesSearched: 0,
            OpeningBookDebug: diagnostics);
        debugDetails = diagnostics;
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
        var path = LookupPath.Value;
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
        return CountPieces(board) == StartingPieceCount;
    }

    private static int CountPieces(BoardState board)
    {
        var placement = board.Fen.Split(' ', StringSplitOptions.RemoveEmptyEntries)[0];
        return placement.Count(char.IsLetter);
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
