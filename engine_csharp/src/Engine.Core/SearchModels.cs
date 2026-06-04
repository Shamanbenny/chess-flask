using Chess;
using Engine.Core.V1;

namespace Engine.Core;

public sealed record SearchResult(
    Move Move,
    string MoveSan,
    int Score,
    int MovesEvaluated,
    int? CompletedDepth = null,
    bool? TimedOut = null,
    int? TtEntries = null,
    int? TtProbes = null,
    int? TtHits = null,
    int? TtCutoffs = null,
    int? NodesSearched = null);

public static class EngineVersions
{
    public static SearchResult SearchMoveForVersion(
        string version,
        BoardState board,
        int? depth = null,
        double? timeLimitSeconds = null)
    {
        var normalized = version.Trim().ToLowerInvariant();
        return normalized switch
        {
            "1" or "v1" => HistoricalEngines.SearchMoveV1_0(board, depth ?? 3),
            "1.1" or "v1.1" => HistoricalEngines.SearchMoveV1_1(board, depth ?? 4),
            "1.2" or "v1.2" => HistoricalEngines.SearchMoveV1_2(board, depth ?? 4),
            "1.3" or "v1.3" => HistoricalEngines.SearchMoveV1_3(board, depth ?? 4),
            "1.4" or "v1.4" => HistoricalEngines.SearchMoveV1_4(board, depth ?? 4),
            "1.5" or "v1.5" => HistoricalEngines.SearchMoveV1_5(board, timeLimitSeconds ?? 1.0),
            "1.6" or "v1.6" => HistoricalEngines.SearchMoveV1_6(board, timeLimitSeconds ?? 1.0),
            _ => throw new ArgumentException($"Unsupported engine version '{version}'", nameof(version)),
        };
    }
}
