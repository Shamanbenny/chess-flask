/*
Purpose:
This LocalTesting helper measures whether running multiple backend workers can keep
independent self-play games progressing concurrently on the same Linux machine.

It accepts one compiled engine source file path, runs 20 self-play games from the
same starting board at 100ms per move with 1 worker, records each game's elapsed
time and plies, and then repeats the same workload with a configurable worker count
for the second experiment.

The output is intended to make worker-scaling behavior visible by showing:
1. Per-game elapsed time for every game in each batch.
2. Per-game ply counts and termination reasons.
3. Batch wall-clock duration and summary statistics for the 1-worker and configurable-worker runs.

Use --skip-1-worker only when you intentionally want to skip the baseline batch to
save time. The baseline batch remains enabled by default because it is required for
the direct 1-worker versus N-worker comparison.
*/

using System.Collections.Concurrent;
using System.Diagnostics;
using Chess;
using Engine.Core;

internal static class BackendWorkerExperiment
{
    private const int DefaultGames = 20;
    private const int DefaultMaxPlies = 200;
    private const double DefaultTimeLimitSeconds = 0.100;
    private const double MillisecondsPerPlyToleranceRatio = 0.10;
    private const int SingleWorkerCount = 1;
    private const int DefaultComparisonWorkerCount = 4;
    private const string DefaultStartFen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

    public static int Run(string[] args)
    {
        var options = ParseOptions(args);
        var engine = EngineFileSupport.ResolveV3PlusEngine(options.EngineFilePath);

        Console.WriteLine("=== BACKEND WORKER EXPERIMENT ===");
        Console.WriteLine($"Engine source: {engine.SourcePath}");
        Console.WriteLine($"Engine name: {engine.EngineStem}");
        Console.WriteLine($"Search method: {engine.SearchMethodName}");
        Console.WriteLine($"Start FEN: {options.StartFen}");
        Console.WriteLine($"Games per batch: {options.Games}");
        Console.WriteLine($"Time limit per move: {options.TimeLimitSeconds * 1000.0:F1}ms");
        Console.WriteLine($"Max plies per game: {options.MaxPlies}");
        Console.WriteLine($"Comparison workers: {options.ComparisonWorkers}");
        Console.WriteLine($"Skip 1-worker batch: {options.SkipSingleWorkerBatch}");
        Console.WriteLine();

        ExperimentBatchResult? singleWorkerBatch = null;
        if (!options.SkipSingleWorkerBatch)
        {
            singleWorkerBatch = RunBatch(engine, options, SingleWorkerCount);
            Console.WriteLine();
        }

        var multiWorkerBatch = RunBatch(engine, options, options.ComparisonWorkers);
        if (singleWorkerBatch is not null)
        {
            Console.WriteLine();
        }

        PrintComparison(singleWorkerBatch, multiWorkerBatch);
        return (singleWorkerBatch?.Failures ?? 0) > 0 || multiWorkerBatch.Failures > 0 ? 1 : 0;
    }

    private static BackendWorkerExperimentOptions ParseOptions(string[] args)
    {
        string? engineFilePath = null;
        var games = DefaultGames;
        var maxPlies = DefaultMaxPlies;
        var timeLimitSeconds = DefaultTimeLimitSeconds;
        var startFen = DefaultStartFen;
        var comparisonWorkers = DefaultComparisonWorkerCount;
        var skipSingleWorkerBatch = false;

        for (var index = 0; index < args.Length; index++)
        {
            switch (args[index])
            {
                case "--engine-file":
                    engineFilePath = args[++index];
                    break;
                case "--games":
                    games = int.Parse(args[++index]);
                    break;
                case "--max-plies":
                    maxPlies = int.Parse(args[++index]);
                    break;
                case "--time-limit-ms":
                    timeLimitSeconds = double.Parse(args[++index]) / 1000.0;
                    break;
                case "--start-fen":
                    startFen = args[++index];
                    break;
                case "--workers":
                    comparisonWorkers = int.Parse(args[++index]);
                    break;
                case "--skip-1-worker":
                    skipSingleWorkerBatch = true;
                    break;
                default:
                    throw new ArgumentException($"Unknown argument '{args[index]}'");
            }
        }

        if (string.IsNullOrWhiteSpace(engineFilePath))
        {
            throw new ArgumentException("--engine-file is required.");
        }

        if (games < 1)
        {
            throw new ArgumentException("--games must be at least 1.");
        }

        if (maxPlies < 1)
        {
            throw new ArgumentException("--max-plies must be at least 1.");
        }

        if (timeLimitSeconds <= 0)
        {
            throw new ArgumentException("--time-limit-ms must be greater than 0.");
        }

        if (comparisonWorkers < 1)
        {
            throw new ArgumentException("--workers must be at least 1.");
        }

        _ = new BoardState(startFen);

        return new BackendWorkerExperimentOptions(
            ResolveCliPath(engineFilePath),
            startFen,
            games,
            maxPlies,
            timeLimitSeconds,
            comparisonWorkers,
            skipSingleWorkerBatch);
    }

    private static ExperimentBatchResult RunBatch(
        EngineVersions.ResolvedEngineFile engine,
        BackendWorkerExperimentOptions options,
        int workers)
    {
        Console.WriteLine($"=== Batch start: workers={workers} ===");
        var wallClock = Stopwatch.StartNew();
        var results = new ConcurrentBag<ExperimentGameResult>();

        Parallel.ForEach(
            Enumerable.Range(1, options.Games),
            new ParallelOptions { MaxDegreeOfParallelism = workers },
            gameNumber =>
            {
                var result = PlayGame(gameNumber, options.StartFen, engine, options.TimeLimitSeconds, options.MaxPlies);
                results.Add(result);
            });

        wallClock.Stop();

        var orderedResults = results.OrderBy(result => result.GameNumber).ToArray();
        foreach (var result in orderedResults)
        {
            var millisecondsPerPly = CalculateMillisecondsPerPly(result.Elapsed, result.Plies);
            Console.WriteLine(
                $"Game {result.GameNumber}: workers={workers} | result={result.Result} | term={result.TerminationReason} | plies={result.Plies} | duration_ms={result.Elapsed.TotalMilliseconds:F3} | ms_per_ply={millisecondsPerPly:F3}");

            if (!string.IsNullOrWhiteSpace(result.FailureMessage))
            {
                Console.WriteLine($"  Failure: {result.FailureMessage}");
            }
        }

        var summary = BuildSummary(orderedResults, wallClock.Elapsed, workers);
        Console.WriteLine(
            $"Batch summary: workers={workers} | wall_clock_ms={summary.WallClock.TotalMilliseconds:F3} | avg_game_ms={summary.AverageGameMilliseconds:F3} | min_game_ms={summary.MinGameMilliseconds:F3} | max_game_ms={summary.MaxGameMilliseconds:F3} | avg_plies={summary.AveragePlies:F2} | total_plies={summary.TotalPlies} | avg_ms_per_ply={summary.AverageMillisecondsPerPly:F3} | total_ms_per_ply={summary.TotalMillisecondsPerPly:F3} | failures={summary.Failures}");

        return summary;
    }

    private static ExperimentGameResult PlayGame(
        int gameNumber,
        string startFen,
        EngineVersions.ResolvedEngineFile engine,
        double timeLimitSeconds,
        int maxPlies)
    {
        var board = new BoardState(startFen);
        var stopwatch = Stopwatch.StartNew();
        var plies = 0;

        while (!board.IsGameOver && plies < maxPlies)
        {
            SearchResult result;
            try
            {
                result = engine.SearchMove(board, timeLimitSeconds);
            }
            catch (Exception exception)
            {
                stopwatch.Stop();
                var rootCause = UnwrapInvocationException(exception);
                return new ExperimentGameResult(
                    gameNumber,
                    plies,
                    board.WhiteToMove,
                    ResultFromSideToMoveLoss(board.WhiteToMove),
                    "engine_exception",
                    stopwatch.Elapsed,
                    rootCause.Message);
            }

            if (!IsLegalReturnedMove(board, result.Move))
            {
                stopwatch.Stop();
                return new ExperimentGameResult(
                    gameNumber,
                    plies,
                    board.WhiteToMove,
                    ResultFromSideToMoveLoss(board.WhiteToMove),
                    "illegal_move",
                    stopwatch.Elapsed,
                    $"Illegal move returned: {result.MoveSan} ({MoveToUci(result.Move)})");
            }

            board.Push(result.Move);
            plies++;

            if (board.CanClaimDraw())
            {
                break;
            }
        }

        stopwatch.Stop();
        var terminationReason = GetTerminationReason(board, plies, maxPlies);
        var resultLabel = GetResultLabel(board, terminationReason);

        return new ExperimentGameResult(
            gameNumber,
            plies,
            board.WhiteToMove,
            resultLabel,
            terminationReason,
            stopwatch.Elapsed,
            null);
    }

    private static ExperimentBatchResult BuildSummary(
        IReadOnlyList<ExperimentGameResult> results,
        TimeSpan wallClock,
        int workers)
    {
        var durations = results.Select(result => result.Elapsed.TotalMilliseconds).ToArray();
        var plies = results.Select(result => result.Plies).ToArray();
        var averageMillisecondsPerPly = results.Count == 0
            ? 0.0
            : results.Average(result => CalculateMillisecondsPerPly(result.Elapsed, result.Plies));
        var totalPlies = plies.Sum();
        var totalMillisecondsPerPly = totalPlies == 0
            ? 0.0
            : durations.Sum() / totalPlies;
        var failures = results.Count(result => !string.IsNullOrWhiteSpace(result.FailureMessage));

        return new ExperimentBatchResult(
            workers,
            wallClock,
            results,
            durations.Length == 0 ? 0.0 : durations.Average(),
            durations.Length == 0 ? 0.0 : durations.Min(),
            durations.Length == 0 ? 0.0 : durations.Max(),
            plies.Length == 0 ? 0.0 : plies.Average(),
            totalPlies,
            averageMillisecondsPerPly,
            totalMillisecondsPerPly,
            failures);
    }

    private static void PrintComparison(ExperimentBatchResult? singleWorkerBatch, ExperimentBatchResult multiWorkerBatch)
    {
        if (singleWorkerBatch is null)
        {
            Console.WriteLine("=== Comparison ===");
            Console.WriteLine("1-worker batch was skipped; no direct comparison is available.");
            Console.WriteLine(
                $"Workers {multiWorkerBatch.Workers}: wall_clock_ms={multiWorkerBatch.WallClock.TotalMilliseconds:F3} | avg_game_ms={multiWorkerBatch.AverageGameMilliseconds:F3} | avg_plies={multiWorkerBatch.AveragePlies:F2} | total_plies={multiWorkerBatch.TotalPlies} | avg_ms_per_ply={multiWorkerBatch.AverageMillisecondsPerPly:F3} | total_ms_per_ply={multiWorkerBatch.TotalMillisecondsPerPly:F3}");
            return;
        }

        var averageGameDelta = multiWorkerBatch.AverageGameMilliseconds - singleWorkerBatch.AverageGameMilliseconds;
        var totalMillisecondsPerPlyDelta = multiWorkerBatch.TotalMillisecondsPerPly - singleWorkerBatch.TotalMillisecondsPerPly;
        var wallClockDelta = multiWorkerBatch.WallClock.TotalMilliseconds - singleWorkerBatch.WallClock.TotalMilliseconds;
        var withinTolerance = IsWithinTolerance(
            singleWorkerBatch.TotalMillisecondsPerPly,
            multiWorkerBatch.TotalMillisecondsPerPly,
            MillisecondsPerPlyToleranceRatio);

        Console.WriteLine("=== Comparison ===");
        Console.WriteLine(
            $"Workers 1: wall_clock_ms={singleWorkerBatch.WallClock.TotalMilliseconds:F3} | avg_game_ms={singleWorkerBatch.AverageGameMilliseconds:F3} | avg_plies={singleWorkerBatch.AveragePlies:F2} | total_plies={singleWorkerBatch.TotalPlies} | avg_ms_per_ply={singleWorkerBatch.AverageMillisecondsPerPly:F3} | total_ms_per_ply={singleWorkerBatch.TotalMillisecondsPerPly:F3}");
        Console.WriteLine(
            $"Workers 4: wall_clock_ms={multiWorkerBatch.WallClock.TotalMilliseconds:F3} | avg_game_ms={multiWorkerBatch.AverageGameMilliseconds:F3} | avg_plies={multiWorkerBatch.AveragePlies:F2} | total_plies={multiWorkerBatch.TotalPlies} | avg_ms_per_ply={multiWorkerBatch.AverageMillisecondsPerPly:F3} | total_ms_per_ply={multiWorkerBatch.TotalMillisecondsPerPly:F3}");
        Console.WriteLine($"Average game delta ms (4 - 1): {averageGameDelta:F3}");
        Console.WriteLine($"Total ms-per-ply delta (4 - 1): {totalMillisecondsPerPlyDelta:F3}");
        Console.WriteLine($"Wall clock delta ms (4 - 1): {wallClockDelta:F3}");
        Console.WriteLine(
            $"Within +/-10% total-ms-per-ply: {withinTolerance}");
    }

    private static double CalculateMillisecondsPerPly(TimeSpan elapsed, int plies)
    {
        return plies <= 0 ? 0.0 : elapsed.TotalMilliseconds / plies;
    }

    private static bool IsWithinTolerance(double baseline, double candidate, double toleranceRatio)
    {
        if (baseline == 0.0)
        {
            return candidate == 0.0;
        }

        var deltaRatio = Math.Abs(candidate - baseline) / baseline;
        return deltaRatio <= toleranceRatio;
    }

    private static string ResolveCliPath(string path)
    {
        return Path.IsPathRooted(path)
            ? Path.GetFullPath(path)
            : Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), path));
    }

    private static Exception UnwrapInvocationException(Exception exception)
    {
        if (exception is System.Reflection.TargetInvocationException invocationException
            && invocationException.InnerException is not null)
        {
            return UnwrapInvocationException(invocationException.InnerException);
        }

        return exception;
    }

    private static bool IsLegalReturnedMove(BoardState board, Move move)
    {
        var targetUci = MoveToUci(move);
        return board.LegalMoves().Any(legalMove => MoveToUci(legalMove) == targetUci);
    }

    private static string MoveToUci(Move move)
    {
        var promotion = move.Promotion is null
            ? string.Empty
            : char.ToLowerInvariant(move.Promotion.ToFenChar()).ToString();
        return $"{move.OriginalPosition}{move.NewPosition}{promotion}";
    }

    private static string ResultFromSideToMoveLoss(bool sideToMoveWasWhite)
    {
        return sideToMoveWasWhite ? "0-1" : "1-0";
    }

    private static string GetTerminationReason(BoardState board, int plies, int maxPlies)
    {
        if (board.IsCheckmate)
        {
            return "checkmate";
        }

        if (board.IsGameOver)
        {
            return board.CanClaimDraw() ? "draw" : "game_over";
        }

        if (board.CanClaimDraw())
        {
            return "claimable_draw";
        }

        return plies >= maxPlies ? "max_plies" : "unfinished";
    }

    private static string GetResultLabel(BoardState board, string terminationReason)
    {
        if (terminationReason == "checkmate")
        {
            return board.WhiteToMove ? "0-1" : "1-0";
        }

        return "1/2-1/2";
    }

    private sealed record BackendWorkerExperimentOptions(
        string EngineFilePath,
        string StartFen,
        int Games,
        int MaxPlies,
        double TimeLimitSeconds,
        int ComparisonWorkers,
        bool SkipSingleWorkerBatch);

    private sealed record ExperimentGameResult(
        int GameNumber,
        int Plies,
        bool SideToMoveWasWhite,
        string Result,
        string TerminationReason,
        TimeSpan Elapsed,
        string? FailureMessage);

    private sealed record ExperimentBatchResult(
        int Workers,
        TimeSpan WallClock,
        IReadOnlyList<ExperimentGameResult> Results,
        double AverageGameMilliseconds,
        double MinGameMilliseconds,
        double MaxGameMilliseconds,
        double AveragePlies,
        int TotalPlies,
        double AverageMillisecondsPerPly,
        double TotalMillisecondsPerPly,
        int Failures);
}

// dotnet run --project engine_csharp/src/LocalTesting -- backend-worker-experiment --engine-file engine_csharp/src/Engine.Core/V3/V3_4Engine.cs --games 20 --time-limit-ms 100 --workers 6

/*
=== BACKEND WORKER EXPERIMENT ===
Engine source: /home/benny/Desktop/_gitrepo/chess-flask/engine_csharp/src/Engine.Core/V3/V3_4Engine.cs
Engine name: V3_4Engine
Search method: SearchMoveV3_4
Start FEN: rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1
Games per batch: 20
Time limit per move: 100.0ms
Max plies per game: 200
Comparison workers: 6

=== Batch start: workers=1 ===
Game 1: workers=1 | result=1/2-1/2 | term=claimable_draw | plies=43 | duration_ms=4493.077 | ms_per_ply=104.490
Game 2: workers=1 | result=1/2-1/2 | term=claimable_draw | plies=43 | duration_ms=4463.628 | ms_per_ply=103.805
Game 3: workers=1 | result=1/2-1/2 | term=claimable_draw | plies=43 | duration_ms=4450.910 | ms_per_ply=103.510
Game 4: workers=1 | result=1/2-1/2 | term=claimable_draw | plies=43 | duration_ms=4447.005 | ms_per_ply=103.419
Game 5: workers=1 | result=1/2-1/2 | term=claimable_draw | plies=43 | duration_ms=4457.781 | ms_per_ply=103.669
Game 6: workers=1 | result=1/2-1/2 | term=claimable_draw | plies=43 | duration_ms=4456.114 | ms_per_ply=103.631
Game 7: workers=1 | result=1/2-1/2 | term=claimable_draw | plies=43 | duration_ms=4454.981 | ms_per_ply=103.604
Game 8: workers=1 | result=0-1 | term=checkmate | plies=120 | duration_ms=12442.318 | ms_per_ply=103.686
Game 9: workers=1 | result=1/2-1/2 | term=claimable_draw | plies=43 | duration_ms=4467.399 | ms_per_ply=103.893
Game 10: workers=1 | result=1/2-1/2 | term=claimable_draw | plies=43 | duration_ms=4448.655 | ms_per_ply=103.457
Game 11: workers=1 | result=0-1 | term=checkmate | plies=116 | duration_ms=12018.397 | ms_per_ply=103.607
Game 12: workers=1 | result=1/2-1/2 | term=claimable_draw | plies=43 | duration_ms=4469.675 | ms_per_ply=103.946
Game 13: workers=1 | result=1/2-1/2 | term=claimable_draw | plies=43 | duration_ms=4493.020 | ms_per_ply=104.489
Game 14: workers=1 | result=1/2-1/2 | term=claimable_draw | plies=43 | duration_ms=4454.882 | ms_per_ply=103.602
Game 15: workers=1 | result=1/2-1/2 | term=claimable_draw | plies=43 | duration_ms=4457.710 | ms_per_ply=103.668
Game 16: workers=1 | result=1/2-1/2 | term=claimable_draw | plies=43 | duration_ms=4469.392 | ms_per_ply=103.939
Game 17: workers=1 | result=1/2-1/2 | term=claimable_draw | plies=43 | duration_ms=4466.462 | ms_per_ply=103.871
Game 18: workers=1 | result=1/2-1/2 | term=claimable_draw | plies=43 | duration_ms=4470.470 | ms_per_ply=103.964
Game 19: workers=1 | result=1/2-1/2 | term=claimable_draw | plies=43 | duration_ms=4471.466 | ms_per_ply=103.988
Game 20: workers=1 | result=1/2-1/2 | term=claimable_draw | plies=43 | duration_ms=4437.602 | ms_per_ply=103.200
Batch summary: workers=1 | wall_clock_ms=104806.553 | avg_game_ms=5239.547 | min_game_ms=4437.602 | max_game_ms=12442.318 | avg_plies=50.50 | total_plies=1010 | avg_ms_per_ply=103.772 | total_ms_per_ply=103.753 | failures=0

=== Batch start: workers=6 ===
Game 1: workers=6 | result=0-1 | term=checkmate | plies=120 | duration_ms=12459.031 | ms_per_ply=103.825
Game 2: workers=6 | result=0-1 | term=checkmate | plies=112 | duration_ms=11633.906 | ms_per_ply=103.874
Game 3: workers=6 | result=0-1 | term=checkmate | plies=116 | duration_ms=12019.090 | ms_per_ply=103.613
Game 4: workers=6 | result=1/2-1/2 | term=claimable_draw | plies=43 | duration_ms=4458.595 | ms_per_ply=103.688
Game 5: workers=6 | result=1/2-1/2 | term=claimable_draw | plies=43 | duration_ms=4464.146 | ms_per_ply=103.817
Game 6: workers=6 | result=0-1 | term=checkmate | plies=120 | duration_ms=12430.322 | ms_per_ply=103.586
Game 7: workers=6 | result=1/2-1/2 | term=claimable_draw | plies=43 | duration_ms=4506.459 | ms_per_ply=104.801
Game 8: workers=6 | result=0-1 | term=checkmate | plies=112 | duration_ms=11618.627 | ms_per_ply=103.738
Game 9: workers=6 | result=0-1 | term=checkmate | plies=112 | duration_ms=11599.494 | ms_per_ply=103.567
Game 10: workers=6 | result=1/2-1/2 | term=claimable_draw | plies=43 | duration_ms=4476.523 | ms_per_ply=104.105
Game 11: workers=6 | result=0-1 | term=checkmate | plies=120 | duration_ms=12454.558 | ms_per_ply=103.788
Game 12: workers=6 | result=0-1 | term=checkmate | plies=116 | duration_ms=12024.197 | ms_per_ply=103.657
Game 13: workers=6 | result=0-1 | term=checkmate | plies=120 | duration_ms=12423.959 | ms_per_ply=103.533
Game 14: workers=6 | result=0-1 | term=checkmate | plies=120 | duration_ms=12457.489 | ms_per_ply=103.812
Game 15: workers=6 | result=1/2-1/2 | term=claimable_draw | plies=43 | duration_ms=4476.527 | ms_per_ply=104.105
Game 16: workers=6 | result=1/2-1/2 | term=claimable_draw | plies=43 | duration_ms=4502.793 | ms_per_ply=104.716
Game 17: workers=6 | result=0-1 | term=checkmate | plies=120 | duration_ms=12463.359 | ms_per_ply=103.861
Game 18: workers=6 | result=1/2-1/2 | term=claimable_draw | plies=43 | duration_ms=4450.930 | ms_per_ply=103.510
Game 19: workers=6 | result=0-1 | term=checkmate | plies=116 | duration_ms=12052.866 | ms_per_ply=103.904
Game 20: workers=6 | result=1/2-1/2 | term=claimable_draw | plies=43 | duration_ms=4448.110 | ms_per_ply=103.444
Batch summary: workers=6 | wall_clock_ms=37857.041 | avg_game_ms=9071.049 | min_game_ms=4448.110 | max_game_ms=12463.359 | avg_plies=87.40 | total_plies=1748 | avg_ms_per_ply=103.847 | total_ms_per_ply=103.788 | failures=0

=== Comparison ===
Workers 1: wall_clock_ms=104806.553 | avg_game_ms=5239.547 | avg_plies=50.50 | total_plies=1010 | avg_ms_per_ply=103.772 | total_ms_per_ply=103.753
Workers 4: wall_clock_ms=37857.041 | avg_game_ms=9071.049 | avg_plies=87.40 | total_plies=1748 | avg_ms_per_ply=103.847 | total_ms_per_ply=103.788
Average game delta ms (4 - 1): 3831.502
Total ms-per-ply delta (4 - 1): 0.034
Wall clock delta ms (4 - 1): -66949.512
Within +/-10% total-ms-per-ply: True
*/
