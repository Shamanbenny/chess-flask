using System.Reflection;
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
    public sealed record ResolvedEngineFile(
        string SourcePath,
        string EngineStem,
        string SearchMethodName,
        Func<BoardState, double, SearchResult> SearchMove);

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

    public static ResolvedEngineFile ResolveTimeLimitedEngineFromFilePath(string engineFilePath)
    {
        if (string.IsNullOrWhiteSpace(engineFilePath))
        {
            throw new ArgumentException("Engine file path is required.", nameof(engineFilePath));
        }

        var fullPath = Path.GetFullPath(engineFilePath);
        if (!File.Exists(fullPath))
        {
            throw new FileNotFoundException($"Engine file not found: {fullPath}", fullPath);
        }

        if (!string.Equals(Path.GetExtension(fullPath), ".cs", StringComparison.OrdinalIgnoreCase))
        {
            throw new ArgumentException($"Engine file must be a .cs file: {fullPath}", nameof(engineFilePath));
        }

        var engineStem = Path.GetFileNameWithoutExtension(fullPath);
        if (!engineStem.EndsWith("Engine", StringComparison.Ordinal))
        {
            throw new ArgumentException(
                $"Engine file name must end with 'Engine.cs' so it can be resolved to a search method: {fullPath}",
                nameof(engineFilePath));
        }

        var versionStem = engineStem[..^"Engine".Length];
        if (string.IsNullOrWhiteSpace(versionStem))
        {
            throw new ArgumentException($"Unable to derive engine version stem from file name: {fullPath}", nameof(engineFilePath));
        }

        var searchMethodName = $"SearchMove{versionStem}";
        var method = typeof(EngineVersions).Assembly
            .GetTypes()
            .Select(type => type.GetMethod(searchMethodName, BindingFlags.Public | BindingFlags.Static))
            .FirstOrDefault(CanUseAsTimeLimitedSearchMethod);

        if (method is null)
        {
            throw new ArgumentException(
                $"No compiled time-limited search method named '{searchMethodName}' was found for engine file '{fullPath}'. " +
                "Make sure the file is included in the build and exposes a public static SearchMove... method with a time-limit parameter.",
                nameof(engineFilePath));
        }

        SearchResult Search(BoardState board, double timeLimitSeconds)
        {
            var arguments = BuildInvocationArguments(method, board, timeLimitSeconds);
            return (SearchResult)method.Invoke(null, arguments)!;
        }

        return new ResolvedEngineFile(fullPath, engineStem, searchMethodName, Search);
    }

    private static bool CanUseAsTimeLimitedSearchMethod(MethodInfo? method)
    {
        if (method is null || method.ReturnType != typeof(SearchResult))
        {
            return false;
        }

        var parameters = method.GetParameters();
        if (parameters.Length == 0 || parameters[0].ParameterType != typeof(BoardState))
        {
            return false;
        }

        var hasTimeLimitParameter = false;
        foreach (var parameter in parameters[1..])
        {
            if (parameter.ParameterType == typeof(double) || parameter.ParameterType == typeof(double?))
            {
                hasTimeLimitParameter = true;
                continue;
            }

            if (!parameter.HasDefaultValue)
            {
                return false;
            }
        }

        return hasTimeLimitParameter;
    }

    private static object?[] BuildInvocationArguments(MethodInfo method, BoardState board, double timeLimitSeconds)
    {
        var parameters = method.GetParameters();
        var arguments = new object?[parameters.Length];
        arguments[0] = board;

        var assignedTimeLimit = false;
        for (var index = 1; index < parameters.Length; index++)
        {
            var parameter = parameters[index];
            if (!assignedTimeLimit && (parameter.ParameterType == typeof(double) || parameter.ParameterType == typeof(double?)))
            {
                arguments[index] = timeLimitSeconds;
                assignedTimeLimit = true;
                continue;
            }

            arguments[index] = parameter.DefaultValue;
        }

        return arguments;
    }
}
