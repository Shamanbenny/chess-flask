using System.Diagnostics;
using System.Net;
using System.Text.Json;
using Chess;
using Engine.Core;
using Engine.Core.V2;
using Engine.Core.V3;
using Microsoft.Azure.Functions.Worker;
using Microsoft.Azure.Functions.Worker.Http;
using Microsoft.Extensions.Logging;

namespace Engine.Functions;

public sealed class ChessFunction
{
    private const double DefaultTimeLimitSeconds = 2.0;
    private static readonly TimeSpan ContextTtl = TimeSpan.FromMinutes(30);
    private static readonly HashSet<string> AllowedOrigins = new(StringComparer.OrdinalIgnoreCase)
    {
        "https://sneakyowl.net",
        "https://www.sneakyowl.net",
    };

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true,
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        WriteIndented = false,
    };

    private static readonly object ContextLock = new();
    private static readonly Dictionary<string, CachedSearchContext> Contexts = [];

    private readonly ILogger<ChessFunction> _logger;

    public ChessFunction(ILogger<ChessFunction> logger)
    {
        _logger = logger;
    }

    [Function("ChessMove")]
    public async Task<HttpResponseData> Run(
        [HttpTrigger(AuthorizationLevel.Anonymous, "post", "options", Route = "chess/{version}")] HttpRequestData request,
        string version)
    {
        if (string.Equals(request.Method, "OPTIONS", StringComparison.OrdinalIgnoreCase))
        {
            return await JsonResponse(request, HttpStatusCode.NoContent, new { });
        }

        var start = Stopwatch.GetTimestamp();
        var normalizedVersion = NormalizeVersion(version);

        try
        {
            var payload = await ReadPayload(request);
            var body = GenerateEngineResponse(normalizedVersion, payload);
            var processingTime = Stopwatch.GetElapsedTime(start).TotalSeconds;
            body["processing_time"] = processingTime;

            if (body.TryGetValue("debug", out var debugValue) && debugValue is Dictionary<string, object?> debug)
            {
                debug["processing_time"] = processingTime;
            }

            var status = body.ContainsKey("error") ? HttpStatusCode.BadRequest : HttpStatusCode.OK;
            return await JsonResponse(request, status, body);
        }
        catch (JsonException exc)
        {
            return await JsonResponse(
                request,
                HttpStatusCode.BadRequest,
                ErrorBody("Invalid JSON body", 400, normalizedVersion, ("exception", exc.Message)));
        }
        catch (Exception exc)
        {
            _logger.LogError(exc, "Unhandled engine error for version {Version}", normalizedVersion);
            return await JsonResponse(
                request,
                HttpStatusCode.InternalServerError,
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

        var result = version switch
        {
            "v0" => ChooseRandomMove(board, legalMoves),
            "v2.0" => V2_0Engine.SearchMoveV2_0(board, TimeLimitSeconds()),
            "v2.9" => V2_9Engine.SearchMoveV2_9(board, TimeLimitSeconds()),
            "v3.0" => V3_0Engine.SearchMoveV3_0(board, TimeLimitSeconds(), searchContext: V3_0Context(version, payload)),
            "v3.4" => V3_4Engine.SearchMoveV3_4(board, TimeLimitSeconds(), searchContext: V3_4Context(version, payload)),
            _ => null,
        };

        if (result is null)
        {
            return ErrorBody($"Unsupported version '{version}'", 400, version);
        }

        return SuccessBody(version, result);
    }

    private static SearchResult ChooseRandomMove(BoardState board, IReadOnlyList<Move> legalMoves)
    {
        var move = legalMoves[Random.Shared.Next(legalMoves.Count)];
        return new SearchResult(move, board.GetSan(move), 0, legalMoves.Count);
    }

    private static Dictionary<string, object?> SuccessBody(string version, SearchResult result)
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

    private static async Task<ChessRequest> ReadPayload(HttpRequestData request)
    {
        using var reader = new StreamReader(request.Body);
        var body = await reader.ReadToEndAsync();
        if (string.IsNullOrWhiteSpace(body))
        {
            return new ChessRequest();
        }

        return JsonSerializer.Deserialize<ChessRequest>(body, JsonOptions) ?? new ChessRequest();
    }

    private static async Task<HttpResponseData> JsonResponse(HttpRequestData request, HttpStatusCode status, object body)
    {
        var response = request.CreateResponse(status);
        AddCorsHeaders(request, response);

        if (status == HttpStatusCode.NoContent)
        {
            return response;
        }

        response.Headers.Add("Content-Type", "application/json");
        await response.WriteStringAsync(JsonSerializer.Serialize(body, JsonOptions));
        return response;
    }

    private static void AddCorsHeaders(HttpRequestData request, HttpResponseData response)
    {
        var origin = request.Headers.TryGetValues("Origin", out var origins)
            ? origins.FirstOrDefault()
            : null;
        if (origin is not null && AllowedOrigins.Contains(origin))
        {
            response.Headers.Add("Access-Control-Allow-Origin", origin);
            response.Headers.Add("Access-Control-Allow-Credentials", "false");
        }

        response.Headers.Add("Access-Control-Allow-Methods", "POST, OPTIONS");
        response.Headers.Add("Access-Control-Allow-Headers", "Content-Type");
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

    private static V3_0Engine.V3_0SearchContext? V3_0Context(string version, ChessRequest payload)
    {
        return ContextFor(
            version,
            payload,
            V3_0Engine.CreateSearchContextV3_0,
            value => value as V3_0Engine.V3_0SearchContext);
    }

    private static V3_4Engine.V3_4SearchContext? V3_4Context(string version, ChessRequest payload)
    {
        return ContextFor(
            version,
            payload,
            V3_4Engine.CreateSearchContextV3_4,
            value => value as V3_4Engine.V3_4SearchContext);
    }

    private static TContext? ContextFor<TContext>(
        string version,
        ChessRequest payload,
        Func<TContext> factory,
        Func<object, TContext?> cast)
        where TContext : class
    {
        var contextId = payload.ContextId ?? payload.GameId;
        if (string.IsNullOrWhiteSpace(contextId))
        {
            return null;
        }

        var key = $"{version}:{contextId}";
        var now = DateTimeOffset.UtcNow;
        lock (ContextLock)
        {
            PruneExpiredContexts(now);
            if (payload.ResetContext)
            {
                Contexts.Remove(key);
            }

            if (Contexts.TryGetValue(key, out var cached) && cast(cached.Context) is { } typed)
            {
                Contexts[key] = cached with { LastSeen = now };
                return typed;
            }

            var created = factory();
            Contexts[key] = new CachedSearchContext(created, now);
            return created;
        }
    }

    private static void PruneExpiredContexts(DateTimeOffset now)
    {
        foreach (var staleKey in Contexts
            .Where(pair => now - pair.Value.LastSeen > ContextTtl)
            .Select(pair => pair.Key)
            .ToArray())
        {
            Contexts.Remove(staleKey);
        }
    }

    private static string MoveToUci(Move move)
    {
        var promotion = move.Promotion is null
            ? string.Empty
            : char.ToLowerInvariant(move.Promotion.ToFenChar()).ToString();
        return $"{move.OriginalPosition}{move.NewPosition}{promotion}";
    }

    private sealed record CachedSearchContext(object Context, DateTimeOffset LastSeen);
}

public sealed class ChessRequest
{
    public string? Fen { get; init; }
    public string? GameId { get; init; }
    public string? ContextId { get; init; }
    public bool ResetContext { get; init; }
}
