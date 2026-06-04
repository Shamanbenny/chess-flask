using System.Text.Json;
using Chess;
using Engine.Core;
using Engine.Core.V1;

var exitCode = LocalTestingProgram.Run(args);
return exitCode;

internal static class LocalTestingProgram
{
    public static int Run(string[] args)
    {
        if (args.Length == 0)
        {
            PrintUsage();
            return 2;
        }

        try
        {
            return args[0] switch
            {
                "puzzle-1" => RunPuzzle1(args[1..]),
                "puzzle-2" => RunPuzzle2(args[1..]),
                "endgame-1" => RunEndgame("endgame_1", args[1..]),
                "endgame-2" => RunEndgame("endgame_2", args[1..]),
                _ => Fail($"Unknown command '{args[0]}'"),
            };
        }
        catch (Exception exception) when (exception is ArgumentException or InvalidOperationException or JsonException)
        {
            Console.Error.WriteLine(exception.Message);
            return 2;
        }
    }

    private static int RunPuzzle1(string[] args)
    {
        var scenario = LoadScenario<Puzzle1Scenario>("puzzle_1");
        var versions = new List<string>(scenario.DefaultVersions);
        var depth = scenario.DefaultDepth;
        var timeLimitSeconds = scenario.DefaultTimeLimitSeconds;

        for (var index = 0; index < args.Length; index++)
        {
            switch (args[index])
            {
                case "--depth":
                    depth = int.Parse(args[++index]);
                    break;
                case "--time-limit-seconds":
                    timeLimitSeconds = double.Parse(args[++index]);
                    break;
                case "--versions":
                    versions = [];
                    while (index + 1 < args.Length && !args[index + 1].StartsWith("--", StringComparison.Ordinal))
                    {
                        versions.Add(args[++index]);
                    }
                    break;
                default:
                    return Fail($"Unknown argument '{args[index]}'");
            }
        }

        foreach (var version in versions)
        {
            var board = new BoardState(scenario.StartFen);
            if (version.Equals("v1.5", StringComparison.OrdinalIgnoreCase)
                || version.Equals("1.5", StringComparison.OrdinalIgnoreCase)
                || version.Equals("v1.6", StringComparison.OrdinalIgnoreCase)
                || version.Equals("1.6", StringComparison.OrdinalIgnoreCase))
            {
                Console.WriteLine($"=== {version} local test at time_limit={timeLimitSeconds:F3}s ===");
            }
            else
            {
                Console.WriteLine($"=== {version} local test at depth {depth} ===");
            }

            Console.WriteLine($"Start FEN: {scenario.StartFen}");

            var firstStarted = DateTime.UtcNow;
            var firstResult = EngineVersions.SearchMoveForVersion(version, board, depth, timeLimitSeconds);
            var firstElapsed = DateTime.UtcNow - firstStarted;
            PrintSearchLine("White 1", firstResult, scenario.ExpectedFirstWhite, firstElapsed);
            PrintSearchDetail("White 1", firstResult);

            if (!string.Equals(firstResult.MoveSan, scenario.ExpectedFirstWhite, StringComparison.Ordinal))
            {
                Console.WriteLine("Forced black move skipped because white did not find the target first move.");
                Console.WriteLine();
                continue;
            }

            board.Push(firstResult.Move);
            var forcedBlackMove = board.LegalMoves().FirstOrDefault(move =>
                MoveToUci(move) == scenario.ForcedBlackMoveUci);
            if (forcedBlackMove is null)
            {
                throw new InvalidOperationException($"Forced move {scenario.ForcedBlackMoveUci} is illegal after {firstResult.MoveSan}");
            }

            Console.WriteLine($"Black forced: {board.GetSan(forcedBlackMove)} ({MoveToUci(forcedBlackMove)})");
            board.Push(forcedBlackMove);

            var secondStarted = DateTime.UtcNow;
            var secondResult = EngineVersions.SearchMoveForVersion(version, board, depth, timeLimitSeconds);
            var secondElapsed = DateTime.UtcNow - secondStarted;
            PrintSearchLine("White 2", secondResult, scenario.ExpectedSecondWhite, secondElapsed);
            PrintSearchDetail("White 2", secondResult);
            Console.WriteLine(
                $"White total: positions={PositionCount(firstResult) + PositionCount(secondResult)} | elapsed={(firstElapsed + secondElapsed).TotalSeconds:F6}s");
            Console.WriteLine();
        }

        return 0;
    }

    private static int RunPuzzle2(string[] args)
    {
        var scenario = LoadScenario<Puzzle2Scenario>("puzzle_2");
        var version = "v1.6";
        var timeLimitSeconds = scenario.DefaultTimeLimitSeconds;
        var maxPlies = scenario.DefaultMaxPlies;

        for (var index = 0; index < args.Length; index++)
        {
            switch (args[index])
            {
                case "--version":
                    version = args[++index];
                    break;
                case "--time-limit-seconds":
                    timeLimitSeconds = double.Parse(args[++index]);
                    break;
                case "--max-plies":
                    maxPlies = int.Parse(args[++index]);
                    break;
                default:
                    return Fail($"Unknown argument '{args[index]}'");
            }
        }

        var board = new BoardState(scenario.StartFen);
        Console.WriteLine($"=== {version} puzzle_2 local self-play at time_limit={timeLimitSeconds:F3}s ===");
        Console.WriteLine($"Start FEN: {scenario.StartFen}");
        Console.WriteLine($"Start turn: {(board.WhiteToMove ? "white" : "black")} | max_plies={maxPlies}");

        var firstStarted = DateTime.UtcNow;
        var firstResult = EngineVersions.SearchMoveForVersion(version, board, null, timeLimitSeconds);
        var firstElapsed = DateTime.UtcNow - firstStarted;
        PrintSearchLine("White 1", firstResult, scenario.ExpectedFirstWhite, firstElapsed);
        PrintSearchDetail("White 1", firstResult);

        if (!string.Equals(firstResult.MoveSan, scenario.ExpectedFirstWhite, StringComparison.Ordinal))
        {
            Console.WriteLine("Stopping: white did not find the target first move.");
            return 0;
        }

        board.Push(firstResult.Move);
        var totalPositions = PositionCount(firstResult);
        var totalTtProbes = firstResult.TtProbes ?? 0;
        var totalTtHits = firstResult.TtHits ?? 0;
        var totalTtCutoffs = firstResult.TtCutoffs ?? 0;
        var totalElapsed = firstElapsed;
        var repetitionDetected = false;

        for (var ply = 2; ply <= maxPlies; ply++)
        {
            if (board.IsGameOver)
            {
                break;
            }

            Console.WriteLine(
                $"Ply {ply}: {(board.WhiteToMove ? "white" : "black")} to move | legal_moves={board.LegalMoveCount()} | time_limit={timeLimitSeconds:F3}s | search started");
            var startedAt = DateTime.UtcNow;
            var result = EngineVersions.SearchMoveForVersion(version, board, null, timeLimitSeconds);
            var elapsed = DateTime.UtcNow - startedAt;

            totalPositions += PositionCount(result);
            totalTtProbes += result.TtProbes ?? 0;
            totalTtHits += result.TtHits ?? 0;
            totalTtCutoffs += result.TtCutoffs ?? 0;
            totalElapsed += elapsed;

            Console.WriteLine(
                $"Ply {ply}: {(board.WhiteToMove ? "white" : "black")} plays {result.MoveSan} ({MoveToUci(result.Move)}) | score={result.Score} | positions={PositionCount(result)} | elapsed={elapsed.TotalSeconds:F6}s");
            PrintSearchDetail($"Ply {ply}", result);
            board.Push(result.Move);

            if (board.CanClaimThreefoldRepetition() || board.IsRepetition(2))
            {
                repetitionDetected = true;
                Console.WriteLine($"Stopping after ply {ply}: repetition pressure detected at FEN {board.Fen}");
                break;
            }
        }

        Console.WriteLine();
        Console.WriteLine($"Final FEN: {board.Fen}");
        Console.WriteLine($"Total positions: {totalPositions}");
        Console.WriteLine($"Total elapsed: {totalElapsed.TotalSeconds:F6}s");
        Console.WriteLine($"Total TT probes: {totalTtProbes}");
        Console.WriteLine($"Total TT hits: {totalTtHits}");
        Console.WriteLine($"Total TT cutoffs: {totalTtCutoffs}");
        Console.WriteLine($"Outcome: {OutcomeLabel(board)}");
        Console.WriteLine($"Winner: {WinnerLabel(board)}");
        Console.WriteLine($"Repetition detected: {repetitionDetected}");
        Console.WriteLine(
            $"White delivered mate within ply limit: {board.IsCheckmate && WinnerLabel(board) == "white" && !repetitionDetected}");

        return 0;
    }

    private static int RunEndgame(string scenarioName, string[] args)
    {
        if (args.Length > 0)
        {
            return Fail($"Unknown argument '{args[0]}'");
        }

        var scenario = LoadScenario<EndgameScenario>(scenarioName);
        var board = new BoardState(scenario.StartFen);
        Console.WriteLine($"=== v1.4 endgame local self-play at depth {scenario.DefaultDepth} ===");
        Console.WriteLine($"Start FEN: {scenario.StartFen}");
        Console.WriteLine($"Start turn: {(board.WhiteToMove ? "white" : "black")} | max_plies={scenario.DefaultMaxPlies}");

        var totalPositions = 0;
        var repetitionDetected = false;

        for (var ply = 1; ply <= scenario.DefaultMaxPlies; ply++)
        {
            if (board.IsGameOver)
            {
                break;
            }

            Console.WriteLine(
                $"Ply {ply}: {(board.WhiteToMove ? "white" : "black")} to move | legal_moves={board.LegalMoves().Count} | depth={scenario.DefaultDepth} | search started");

            var startedAt = DateTime.UtcNow;
            var result = HistoricalEngines.SearchMoveV1_4(board, scenario.DefaultDepth);
            var elapsed = DateTime.UtcNow - startedAt;
            totalPositions += PositionCount(result);

            Console.WriteLine(
                $"Ply {ply}: {(board.WhiteToMove ? "white" : "black")} plays {result.MoveSan} ({MoveToUci(result.Move)}) | score={result.Score} | positions={PositionCount(result)} | elapsed={elapsed.TotalSeconds:F6}s");

            board.Push(result.Move);
            if (board.CanClaimThreefoldRepetition() || board.IsRepetition(2))
            {
                repetitionDetected = true;
                Console.WriteLine($"Stopping after ply {ply}: repetition pressure detected at FEN {board.Fen}");
                break;
            }
        }

        Console.WriteLine();
        Console.WriteLine($"Final FEN: {board.Fen}");
        Console.WriteLine($"Total positions: {totalPositions}");
        Console.WriteLine($"Outcome: {OutcomeLabel(board)}");
        Console.WriteLine($"Winner: {WinnerLabel(board)}");
        Console.WriteLine($"Repetition detected: {repetitionDetected}");
        Console.WriteLine($"Black delivered mate without repetition: {board.IsCheckmate && WinnerLabel(board) == "black" && !repetitionDetected}");
        return 0;
    }

    private static void PrintSearchLine(string label, SearchResult result, string expectedMoveSan, TimeSpan elapsed)
    {
        Console.WriteLine(
            $"{label}: {result.MoveSan} ({MoveToUci(result.Move)}) | expected={expectedMoveSan} | match={result.MoveSan == expectedMoveSan} | score={result.Score} | positions={PositionCount(result)} | elapsed={elapsed.TotalSeconds:F6}s");
    }

    private static void PrintSearchDetail(string label, SearchResult result)
    {
        if (result.CompletedDepth is null)
        {
            return;
        }

        var detail = $"{label} detail: completed_depth={result.CompletedDepth} | timed_out={result.TimedOut} | tt_entries={result.TtEntries}";
        if (result.TtProbes is not null && result.TtHits is not null && result.TtCutoffs is not null)
        {
            var ttHitRate = result.TtProbes.Value == 0 ? 0.0 : result.TtHits.Value / (double)result.TtProbes.Value;
            detail += $" | tt_probes={result.TtProbes} | tt_hits={result.TtHits} | tt_hit_rate={ttHitRate:F3} | tt_cutoffs={result.TtCutoffs}";
        }

        if (result.NodesSearched is not null)
        {
            detail += $" | moves_evaluated={result.MovesEvaluated} | nodes_searched={result.NodesSearched}";
        }

        Console.WriteLine(detail);
    }

    private static int PositionCount(SearchResult result)
    {
        return result.NodesSearched ?? result.MovesEvaluated;
    }

    private static string MoveToUci(Move move)
    {
        var promotion = move.Promotion is null
            ? string.Empty
            : char.ToLowerInvariant(move.Promotion.ToFenChar()).ToString();
        return $"{move.OriginalPosition}{move.NewPosition}{promotion}";
    }

    private static string WinnerLabel(BoardState board)
    {
        if (!board.IsCheckmate)
        {
            return "none";
        }

        return board.WhiteToMove ? "black" : "white";
    }

    private static string OutcomeLabel(BoardState board)
    {
        if (board.IsCheckmate)
        {
            return "checkmate";
        }

        if (board.CanClaimDraw())
        {
            return "draw";
        }

        return board.IsGameOver ? "game_over" : "unfinished";
    }

    private static T LoadScenario<T>(string scenarioName)
    {
        var scenariosRoot = FindScenariosRoot();
        var path = Path.Combine(scenariosRoot, $"{scenarioName}.json");
        var json = File.ReadAllText(path);
        return JsonSerializer.Deserialize<T>(json, new JsonSerializerOptions(JsonSerializerDefaults.Web))
            ?? throw new InvalidOperationException($"Unable to load scenario '{scenarioName}'");
    }

    private static string FindScenariosRoot()
    {
        var current = new DirectoryInfo(AppContext.BaseDirectory);
        while (current is not null)
        {
            var candidate = Path.Combine(current.FullName, "..", "..", "..", "..", "engine_scenarios");
            candidate = Path.GetFullPath(candidate);
            if (Directory.Exists(candidate))
            {
                return candidate;
            }

            current = current.Parent;
        }

        throw new DirectoryNotFoundException("Unable to locate engine_scenarios directory.");
    }

    private static int Fail(string message)
    {
        Console.Error.WriteLine(message);
        PrintUsage();
        return 2;
    }

    private static void PrintUsage()
    {
        Console.Error.WriteLine("Usage:");
        Console.Error.WriteLine("  dotnet run --project engine_csharp/src/LocalTesting -- puzzle-1 --versions v1 v1.1 v1.2 v1.3 v1.4 --depth 4");
        Console.Error.WriteLine("  dotnet run --project engine_csharp/src/LocalTesting -- puzzle-1 --versions v1.5 v1.6 --time-limit-seconds 1.0");
        Console.Error.WriteLine("  dotnet run --project engine_csharp/src/LocalTesting -- puzzle-2 --version v1.6 --time-limit-seconds 1.0 --max-plies 70");
        Console.Error.WriteLine("  dotnet run --project engine_csharp/src/LocalTesting -- endgame-1");
        Console.Error.WriteLine("  dotnet run --project engine_csharp/src/LocalTesting -- endgame-2");
    }

    private sealed record Puzzle1Scenario(
        string StartFen,
        string ExpectedFirstWhite,
        string ForcedBlackMoveUci,
        string ExpectedSecondWhite,
        int DefaultDepth,
        double DefaultTimeLimitSeconds,
        string[] DefaultVersions);

    private sealed record Puzzle2Scenario(
        string StartFen,
        string ExpectedFirstWhite,
        double DefaultTimeLimitSeconds,
        int DefaultMaxPlies);

    private sealed record EndgameScenario(
        string StartFen,
        int DefaultDepth,
        int DefaultMaxPlies);
}
