using System.Diagnostics;
using System.Reflection;
using System.Text.Json;
using System.Text.Json.Serialization;
using Chess;
using Engine.Core;
using Microsoft.Extensions.Logging;

namespace Engine.Functions;

public sealed class ChessMoveHandler
{
    private const double DefaultTimeLimitSeconds = 1.0;
    private const string ChangelogFileName = "CHANGELOG.json";
    private static readonly TimeSpan ContextTtl = TimeSpan.FromMinutes(30);

    private static readonly object ContextLock = new();
    private static readonly Dictionary<string, CachedSearchContext> Contexts = [];
    private static readonly Lazy<IReadOnlyDictionary<string, ResolvedServedEngine>> ServedEngines = new(LoadServedEngines);

    private readonly ILogger<ChessMoveHandler> _logger;

    public ChessMoveHandler(ILogger<ChessMoveHandler> logger)
    {
        _logger = logger;
    }

    public static ChessResponse InvalidJsonResponse(string version, string exception)
    {
        var normalizedVersion = NormalizeVersion(version);
        return new ChessResponse(
            StatusCodes.Status400BadRequest,
            ErrorBody("Invalid JSON body", 400, normalizedVersion, ("exception", exception)));
    }

    public ChessResponse Generate(string version, ChessRequest payload)
    {
        var start = Stopwatch.GetTimestamp();
        var normalizedVersion = NormalizeVersion(version);

        try
        {
            var body = GenerateEngineResponse(normalizedVersion, payload);
            var processingTime = Stopwatch.GetElapsedTime(start).TotalSeconds;
            body["processing_time"] = processingTime;

            if (body.TryGetValue("debug", out var debugValue) && debugValue is Dictionary<string, object?> debug)
            {
                debug["processing_time"] = processingTime;
            }

            var status = body.ContainsKey("error") ? StatusCodes.Status400BadRequest : StatusCodes.Status200OK;
            return new ChessResponse(status, body);
        }
        catch (Exception exc)
        {
            _logger.LogError(exc, "Unhandled engine error for version {Version}", normalizedVersion);
            return new ChessResponse(
                StatusCodes.Status500InternalServerError,
                ErrorBody(
                    exc.Message,
                    500,
                    normalizedVersion,
                    ("reason", "Unhandled engine error"),
                    ("exception", exc.GetType().Name)));
        }
    }

    private static Dictionary<string, object?> GenerateEngineResponse(string version, ChessRequest payload)
    {
        if (string.IsNullOrWhiteSpace(payload.Fen))
        {
            return ErrorBody("FEN string is required", 400, version, ("fen_present", false));
        }

        BoardState board;
        try
        {
            board = new BoardState(payload.Fen);
        }
        catch (Exception exc)
        {
            return ErrorBody("Invalid FEN string", 400, version, ("fen", payload.Fen), ("exception", exc.Message));
        }

        if (board.IsGameOver)
        {
            if (board.IsCheckmate)
            {
                return ErrorBody("Checkmate", 400, version, ("fen", payload.Fen), ("game_over", true), ("outcome", "checkmate"));
            }

            return ErrorBody("Stalemate", 400, version, ("fen", payload.Fen), ("game_over", true), ("outcome", "stalemate"));
        }

        var legalMoves = board.LegalMoves();
        if (legalMoves.Count == 0)
        {
            return ErrorBody("No legal moves available", 400, version, ("fen", payload.Fen), ("legal_move_count", 0));
        }

        var searchOutcome = version == "v0"
            ? new ServedSearchOutcome(ChooseRandomMove(board, legalMoves), null)
            : SearchServedEngine(version, board, payload);

        if (searchOutcome is null)
        {
            return ErrorBody($"Unsupported version '{version}'", 400, version);
        }

        return SuccessBody(version, searchOutcome.Result, searchOutcome.TtContextDebug);
    }

    private static SearchResult ChooseRandomMove(BoardState board, IReadOnlyList<Move> legalMoves)
    {
        var move = legalMoves[Random.Shared.Next(legalMoves.Count)];
        return new SearchResult(move, board.GetSan(move), 0, legalMoves.Count);
    }

    private static ServedSearchOutcome? SearchServedEngine(string version, BoardState board, ChessRequest payload)
    {
        if (!ServedEngines.Value.TryGetValue(version, out var engine))
        {
            return null;
        }

        var contextResolution = ContextFor(version, payload, engine.ContextFactory);
        var arguments = BuildSearchArguments(
            engine.SearchMethod,
            board,
            TimeLimitSeconds(),
            contextResolution.Context);

        var result = (SearchResult)engine.SearchMethod.Invoke(null, arguments)!;
        if (result.OpeningBookDebug is null && version.StartsWith("v3.", StringComparison.Ordinal))
        {
            OpeningBook.TryGetMove(board, out _, out var openingBookDebug);
            result = result with { OpeningBookDebug = openingBookDebug };
        }

        FinalizeContextDebug(contextResolution, result);
        return new ServedSearchOutcome(result, contextResolution.Debug);
    }

    private static Dictionary<string, object?> SuccessBody(
        string version,
        SearchResult result,
        Dictionary<string, object?>? ttContextDebug)
    {
        var selectedMoveUci = MoveToUci(result.Move);
        var debug = new Dictionary<string, object?>
        {
            ["version"] = version,
            ["engine"] = version == "v0" ? "random_legal_move" : $"csharp_{version.Replace(".", "_")}",
            ["selected_move_uci"] = selectedMoveUci,
            ["score"] = result.Score,
            ["moves_evaluated"] = result.MovesEvaluated,
        };

        AddIfPresent(debug, "completed_depth", result.CompletedDepth);
        AddIfPresent(debug, "timed_out", result.TimedOut);
        AddIfPresent(debug, "tt_entries", result.TtEntries);
        AddIfPresent(debug, "tt_probes", result.TtProbes);
        AddIfPresent(debug, "tt_hits", result.TtHits);
        AddIfPresent(debug, "tt_cutoffs", result.TtCutoffs);
        AddIfPresent(debug, "nodes_searched", result.NodesSearched);
        AddIfPresent(debug, "opening_book", result.OpeningBookDebug);
        AddIfPresent(debug, "tt_context", ttContextDebug);

        return new Dictionary<string, object?>
        {
            ["move"] = result.MoveSan,
            ["debug"] = debug,
        };
    }

    private static void AddIfPresent<T>(Dictionary<string, object?> target, string key, T? value)
        where T : struct
    {
        if (value.HasValue)
        {
            target[key] = value.Value;
        }
    }

    private static void AddIfPresent(
        Dictionary<string, object?> target,
        string key,
        IReadOnlyDictionary<string, object?>? value)
    {
        if (value is not null)
        {
            target[key] = value;
        }
    }

    private static void AddIfPresent(
        Dictionary<string, object?> target,
        string key,
        Dictionary<string, object?>? value)
    {
        if (value is not null)
        {
            target[key] = value;
        }
    }

    private static Dictionary<string, object?> ErrorBody(
        string message,
        int status,
        string version,
        params (string Key, object? Value)[] debugValues)
    {
        var debug = new Dictionary<string, object?>
        {
            ["version"] = version,
            ["status"] = status,
            ["reason"] = message,
        };

        foreach (var (key, value) in debugValues)
        {
            debug[key] = value;
        }

        return new Dictionary<string, object?>
        {
            ["error"] = message,
            ["debug"] = debug,
        };
    }

    private static double TimeLimitSeconds()
    {
        var raw = Environment.GetEnvironmentVariable("ENGINE_TIME_LIMIT_SECONDS");
        return double.TryParse(raw, out var value) && value > 0 ? value : DefaultTimeLimitSeconds;
    }

    private static string NormalizeVersion(string version)
    {
        var normalized = version.Trim().ToLowerInvariant().Replace('_', '.');
        return normalized.StartsWith('v') ? normalized : $"v{normalized}";
    }

    private static ContextResolution ContextFor(string version, ChessRequest payload, MethodInfo? factory)
    {
        if (factory is null)
        {
            return new ContextResolution(null, null, null);
        }

        var debug = new Dictionary<string, object?>
        {
            ["enabled"] = true,
            ["reset_requested"] = payload.ResetContext,
        };
        var contextId = payload.ContextId ?? payload.GameId;
        if (string.IsNullOrWhiteSpace(contextId))
        {
            debug["enabled"] = false;
            debug["skipped_reason"] = "missing_context_id";
            return new ContextResolution(null, null, debug);
        }

        debug["context_id"] = contextId;
        var key = $"{version}:{contextId}";
        var now = DateTimeOffset.UtcNow;
        lock (ContextLock)
        {
            var evictedContextCount = PruneExpiredContexts(now);
            debug["evicted_context_count"] = evictedContextCount;

            var contextReset = false;
            if (payload.ResetContext)
            {
                contextReset = Contexts.Remove(key);
            }
            debug["context_reset"] = contextReset;

            if (Contexts.TryGetValue(key, out var cached))
            {
                debug["context_found"] = true;
                debug["context_created"] = false;
                debug["search_count_before"] = cached.SearchCount;
                debug["cache_size_after"] = Contexts.Count;
                Contexts[key] = cached with { LastSeen = now };
                return new ContextResolution(key, cached.Context, debug);
            }

            var created = factory.Invoke(null, null)
                ?? throw new InvalidOperationException($"Context factory '{factory.Name}' returned null.");
            Contexts[key] = new CachedSearchContext(created, now, 0);
            debug["context_found"] = false;
            debug["context_created"] = true;
            debug["search_count_before"] = 0;
            debug["cache_size_after"] = Contexts.Count;
            return new ContextResolution(key, created, debug);
        }
    }

    private static void FinalizeContextDebug(ContextResolution resolution, SearchResult result)
    {
        if (resolution.Key is null || resolution.Debug is null)
        {
            return;
        }

        lock (ContextLock)
        {
            if (!Contexts.TryGetValue(resolution.Key, out var cached))
            {
                return;
            }

            var updated = cached with
            {
                LastSeen = DateTimeOffset.UtcNow,
                SearchCount = cached.SearchCount + 1,
            };
            Contexts[resolution.Key] = updated;
            resolution.Debug["search_count_after"] = updated.SearchCount;
            resolution.Debug["cache_size_after"] = Contexts.Count;

            if (result.TtEntries.HasValue)
            {
                resolution.Debug["tt_entries_after"] = result.TtEntries.Value;
            }
        }
    }

    private static int PruneExpiredContexts(DateTimeOffset now)
    {
        var removedCount = 0;
        foreach (var staleKey in Contexts
            .Where(pair => now - pair.Value.LastSeen > ContextTtl)
            .Select(pair => pair.Key)
            .ToArray())
        {
            Contexts.Remove(staleKey);
            removedCount += 1;
        }

        return removedCount;
    }

    private static string MoveToUci(Move move)
    {
        var promotion = move.Promotion is null
            ? string.Empty
            : char.ToLowerInvariant(move.Promotion.ToFenChar()).ToString();
        return $"{move.OriginalPosition}{move.NewPosition}{promotion}";
    }

    private static IReadOnlyDictionary<string, ResolvedServedEngine> LoadServedEngines()
    {
        // Serving contract:
        // - CHANGELOG.json is the route registry for V2+ engines. Autoresearch can mark a
        //   newly approved compiled engine with "served": true and no Engine.Functions switch
        //   edit is needed.
        // - This still only selects among engines compiled into Engine.Core at deploy time.
        //   CHANGELOG.json cannot load source code that was not included in the built assembly.
        // - The convention is vX.Y -> VX_YEngine.SearchMoveVX_Y, with an optional
        //   CreateSearchContextVX_Y factory for per-game warm-instance context reuse.
        // - v0 remains special-cased because it is a random legal-move baseline, not a
        //   versioned C# engine file.
        var changelogPath = FindChangelogPath();
        if (!File.Exists(changelogPath))
        {
            return new Dictionary<string, ResolvedServedEngine>(StringComparer.Ordinal);
        }

        var changelog = JsonSerializer.Deserialize<Changelog>(
            File.ReadAllText(changelogPath),
            new JsonSerializerOptions { PropertyNameCaseInsensitive = true });
        if (changelog?.Versions is null)
        {
            return new Dictionary<string, ResolvedServedEngine>(StringComparer.Ordinal);
        }

        var registry = new Dictionary<string, ResolvedServedEngine>(StringComparer.Ordinal);
        foreach (var version in changelog.Versions.Where(item => item.Served))
        {
            var normalizedVersion = NormalizeVersion(version.Version);
            if (normalizedVersion == "v0")
            {
                continue;
            }

            registry[normalizedVersion] = ResolveServedEngine(version, normalizedVersion);
        }

        return registry;
    }

    private static ResolvedServedEngine ResolveServedEngine(ChangelogVersion version, string normalizedVersion)
    {
        var versionStem = EngineStemFromMetadata(version, normalizedVersion);
        var searchMethodName = $"SearchMove{versionStem}";
        var searchMethod = typeof(EngineVersions).Assembly
            .GetTypes()
            .Select(type => type.GetMethod(searchMethodName, BindingFlags.Public | BindingFlags.Static))
            .FirstOrDefault(CanUseAsTimeLimitedSearchMethod)
            ?? throw new InvalidOperationException(
                $"CHANGELOG.json marks {normalizedVersion} as served, but no compiled search method named '{searchMethodName}' was found. " +
                "The source file must be committed, included in Engine.Core, and deployed after compilation.");

        var contextFactoryName = $"CreateSearchContext{versionStem}";
        var contextFactory = searchMethod.DeclaringType?.GetMethod(contextFactoryName, BindingFlags.Public | BindingFlags.Static);
        if (contextFactory is not null && contextFactory.GetParameters().Length != 0)
        {
            throw new InvalidOperationException(
                $"Context factory '{contextFactory.Name}' must not require parameters.");
        }

        return new ResolvedServedEngine(searchMethod, contextFactory);
    }

    private static string EngineStemFromMetadata(ChangelogVersion version, string normalizedVersion)
    {
        if (!string.IsNullOrWhiteSpace(version.EngineFile))
        {
            var stem = Path.GetFileNameWithoutExtension(version.EngineFile);
            if (stem.EndsWith("Engine", StringComparison.Ordinal))
            {
                return stem[..^"Engine".Length];
            }
        }

        var match = System.Text.RegularExpressions.Regex.Match(
            normalizedVersion,
            @"^v(?<major>\d+)\.(?<minor>\d+)$",
            System.Text.RegularExpressions.RegexOptions.IgnoreCase);
        if (!match.Success)
        {
            throw new InvalidOperationException($"Unsupported served engine version format: {normalizedVersion}");
        }

        return $"V{match.Groups["major"].Value}_{match.Groups["minor"].Value}";
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

    private static object?[] BuildSearchArguments(
        MethodInfo method,
        BoardState board,
        double timeLimitSeconds,
        object? searchContext)
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

            if (searchContext is not null
                && parameter.ParameterType.IsInstanceOfType(searchContext)
                && parameter.Name is not null
                && parameter.Name.Contains("context", StringComparison.OrdinalIgnoreCase))
            {
                arguments[index] = searchContext;
                continue;
            }

            arguments[index] = parameter.DefaultValue;
        }

        return arguments;
    }

    private static string FindChangelogPath()
    {
        var outputPath = Path.Combine(AppContext.BaseDirectory, ChangelogFileName);
        if (File.Exists(outputPath))
        {
            return outputPath;
        }

        var current = new DirectoryInfo(AppContext.BaseDirectory);
        while (current is not null)
        {
            var candidate = Path.GetFullPath(Path.Combine(current.FullName, "..", "..", "..", ".."));
            var changelogPath = Path.Combine(candidate, ChangelogFileName);
            if (File.Exists(changelogPath)
                && File.Exists(Path.Combine(candidate, "README.md"))
                && Directory.Exists(Path.Combine(candidate, "engine_csharp")))
            {
                return changelogPath;
            }

            current = current.Parent;
        }

        return Path.Combine(Directory.GetCurrentDirectory(), ChangelogFileName);
    }

    private sealed record CachedSearchContext(object Context, DateTimeOffset LastSeen, int SearchCount);

    private sealed record ContextResolution(
        string? Key,
        object? Context,
        Dictionary<string, object?>? Debug);

    private sealed record ResolvedServedEngine(MethodInfo SearchMethod, MethodInfo? ContextFactory);

    private sealed record ServedSearchOutcome(
        SearchResult Result,
        Dictionary<string, object?>? TtContextDebug);

    private sealed record Changelog(
        [property: JsonPropertyName("versions")] ChangelogVersion[]? Versions);

    private sealed record ChangelogVersion(
        [property: JsonPropertyName("version")] string Version,
        [property: JsonPropertyName("engine_file")] string? EngineFile,
        [property: JsonPropertyName("served")] bool Served);
}

public sealed record ChessResponse(int StatusCode, Dictionary<string, object?> Body);

public sealed class ChessRequest
{
    public string? Fen { get; init; }
    public string? GameId { get; init; }
    public string? ContextId { get; init; }
    public bool ResetContext { get; init; }
}
