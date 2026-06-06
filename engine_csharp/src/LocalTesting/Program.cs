using System.Diagnostics;
using System.Globalization;
using System.Text.Json;
using Chess;
using Engine.Core;
using Engine.Core.V1;

var exitCode = LocalTestingProgram.Run(args);
return exitCode;

internal static class LocalTestingProgram
{
    // This default serves as the ACTUAL final goal as we improve the engine. However, know that the arg. parameter
    // mentioned by `autoresearch/EVALUATE.md` serves as the single ground source of truth to abide by at all times
    private const int DefaultEvaluationGames = 500;
    private const int DefaultEvaluationMaxPlies = 200;
    private const double DefaultEvaluationTimeLimitSeconds = 0.100;
    private const string DefaultStockfishBinary = "stockfish";

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
                "evaluate-match" => RunEvaluateMatch(args[1..]),
                "evaluate-stock" or "--evaluate-stock" => RunEvaluateStock(args[1..]),
                "backend-worker-experiment" => BackendWorkerExperiment.Run(args[1..]),
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
                || version.Equals("1.6", StringComparison.OrdinalIgnoreCase)
                || version.Equals("v2.0", StringComparison.OrdinalIgnoreCase)
                || version.Equals("2.0", StringComparison.OrdinalIgnoreCase))
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
        var scenario = LoadScenario<EndgameScenario>(scenarioName);
        var version = "v1.4";
        var depth = scenario.DefaultDepth;
        double? timeLimitSeconds = null;

        for (var index = 0; index < args.Length; index++)
        {
            switch (args[index])
            {
                case "--version":
                    version = args[++index];
                    break;
                case "--depth":
                    depth = int.Parse(args[++index]);
                    break;
                case "--time-limit-seconds":
                    timeLimitSeconds = double.Parse(args[++index]);
                    break;
                default:
                    return Fail($"Unknown argument '{args[index]}'");
            }
        }

        var board = new BoardState(scenario.StartFen);
        var isTimeLimitedVersion =
            version.Equals("v1.5", StringComparison.OrdinalIgnoreCase)
            || version.Equals("1.5", StringComparison.OrdinalIgnoreCase)
            || version.Equals("v1.6", StringComparison.OrdinalIgnoreCase)
            || version.Equals("1.6", StringComparison.OrdinalIgnoreCase)
            || version.Equals("v2.0", StringComparison.OrdinalIgnoreCase)
            || version.Equals("2.0", StringComparison.OrdinalIgnoreCase);

        if (isTimeLimitedVersion)
        {
            Console.WriteLine($"=== {version} endgame local self-play at time_limit={(timeLimitSeconds ?? 1.0):F3}s ===");
        }
        else
        {
            Console.WriteLine($"=== {version} endgame local self-play at depth {depth} ===");
        }

        Console.WriteLine($"Start FEN: {scenario.StartFen}");
        Console.WriteLine($"Start turn: {(board.WhiteToMove ? "white" : "black")} | max_plies={scenario.DefaultMaxPlies}");

        var totalPositions = 0;
        var repetitionDetected = false;
        var totalTtProbes = 0;
        var totalTtHits = 0;
        var totalTtCutoffs = 0;
        var totalElapsed = TimeSpan.Zero;

        for (var ply = 1; ply <= scenario.DefaultMaxPlies; ply++)
        {
            if (board.IsGameOver)
            {
                break;
            }

            if (isTimeLimitedVersion)
            {
                Console.WriteLine(
                    $"Ply {ply}: {(board.WhiteToMove ? "white" : "black")} to move | legal_moves={board.LegalMoves().Count} | time_limit={(timeLimitSeconds ?? 1.0):F3}s | search started");
            }
            else
            {
                Console.WriteLine(
                    $"Ply {ply}: {(board.WhiteToMove ? "white" : "black")} to move | legal_moves={board.LegalMoves().Count} | depth={depth} | search started");
            }

            var startedAt = DateTime.UtcNow;
            var result = EngineVersions.SearchMoveForVersion(version, board, depth, timeLimitSeconds);
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
        Console.WriteLine($"Black delivered mate without repetition: {board.IsCheckmate && WinnerLabel(board) == "black" && !repetitionDetected}");
        return 0;
    }

    private static int RunEvaluateMatch(string[] args)
    {
        var options = ParseEvaluateMatchOptions(args);
        if (options.Games < 2 || options.Games % 2 != 0)
        {
            throw new ArgumentException("--games must be an even number greater than or equal to 2.");
        }

        if (options.TimeLimitSeconds <= 0)
        {
            throw new ArgumentException("--time-limit-ms must be greater than 0.");
        }

        if (options.MaxPlies < 1)
        {
            throw new ArgumentException("--max-plies must be at least 1.");
        }

        return RunEvaluationSeries(
            CreateEngineFileParticipantFactory(options.EngineAFilePath),
            CreateEngineFileParticipantFactory(options.EngineBFilePath),
            options.OpeningsFilePath,
            options.Games,
            options.MaxPlies,
            options.TimeLimitSeconds,
            options.Workers,
            options.Log,
            options.ShortSha);
    }

    private static int RunEvaluateStock(string[] args)
    {
        var options = ParseEvaluateStockOptions(args);
        if (options.Games < 2 || options.Games % 2 != 0)
        {
            throw new ArgumentException("--games must be an even number greater than or equal to 2.");
        }

        if (options.TimeLimitSeconds <= 0)
        {
            throw new ArgumentException("--time-limit-ms must be greater than 0.");
        }

        if (options.MaxPlies < 1)
        {
            throw new ArgumentException("--max-plies must be at least 1.");
        }

        return RunEvaluationSeries(
            CreateEngineFileParticipantFactory(options.EngineFilePath),
            CreateStockfishParticipantFactory(options.StockfishPath, options.StockfishElo),
            options.OpeningsFilePath,
            options.Games,
            options.MaxPlies,
            options.TimeLimitSeconds,
            options.Workers,
            options.Log,
            options.ShortSha);
    }

    private static EvaluateMatchOptions ParseEvaluateMatchOptions(string[] args)
    {
        string? engineAFilePath = null;
        string? engineBFilePath = null;
        var games = DefaultEvaluationGames;
        var maxPlies = DefaultEvaluationMaxPlies;
        var timeLimitSeconds = DefaultEvaluationTimeLimitSeconds;
        var openingsFilePath = FindDefaultOpeningSourceFile();
        var workers = 1;
        var log = false;
        string? shortSha = null;

        for (var index = 0; index < args.Length; index++)
        {
            switch (args[index])
            {
                case "--engine-a-file":
                    engineAFilePath = args[++index];
                    break;
                case "--engine-b-file":
                    engineBFilePath = args[++index];
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
                case "--openings-file":
                    openingsFilePath = ResolveCliPath(args[++index]);
                    break;
                case "--workers":
                    workers = int.Parse(args[++index]);
                    break;
                case "--log":
                    log = true;
                    break;
                case "--short-sha":
                    shortSha = args[++index];
                    break;
                default:
                    throw new ArgumentException($"Unknown argument '{args[index]}'");
            }
        }

        if (string.IsNullOrWhiteSpace(engineAFilePath) || string.IsNullOrWhiteSpace(engineBFilePath))
        {
            throw new ArgumentException("--engine-a-file and --engine-b-file are required.");
        }

        if (log && string.IsNullOrWhiteSpace(shortSha))
        {
            throw new ArgumentException("--short-sha is required when --log is enabled.");
        }

        if (workers < 1)
        {
            throw new ArgumentException("--workers must be at least 1.");
        }

        return new EvaluateMatchOptions(
            ResolveCliPath(engineAFilePath),
            ResolveCliPath(engineBFilePath),
            openingsFilePath,
            games,
            maxPlies,
            timeLimitSeconds,
            workers,
            log,
            shortSha);
    }

    private static EvaluateStockOptions ParseEvaluateStockOptions(string[] args)
    {
        string? engineFilePath = null;
        var stockfishPath = DefaultStockfishBinary;
        var stockfishElo = 1320;
        var games = DefaultEvaluationGames;
        var maxPlies = DefaultEvaluationMaxPlies;
        var timeLimitSeconds = DefaultEvaluationTimeLimitSeconds;
        var openingsFilePath = FindDefaultOpeningSourceFile();
        var workers = 1;
        var log = false;
        string? shortSha = null;

        for (var index = 0; index < args.Length; index++)
        {
            switch (args[index])
            {
                case "--engine-file":
                    engineFilePath = args[++index];
                    break;
                case "--stockfish-path":
                    stockfishPath = args[++index];
                    break;
                case "--stockfish-elo":
                    stockfishElo = int.Parse(args[++index]);
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
                case "--openings-file":
                    openingsFilePath = ResolveCliPath(args[++index]);
                    break;
                case "--workers":
                    workers = int.Parse(args[++index]);
                    break;
                case "--log":
                    log = true;
                    break;
                case "--short-sha":
                    shortSha = args[++index];
                    break;
                default:
                    throw new ArgumentException($"Unknown argument '{args[index]}'");
            }
        }

        if (string.IsNullOrWhiteSpace(engineFilePath))
        {
            throw new ArgumentException("--engine-file is required.");
        }

        if (log && string.IsNullOrWhiteSpace(shortSha))
        {
            throw new ArgumentException("--short-sha is required when --log is enabled.");
        }

        if (workers < 1)
        {
            throw new ArgumentException("--workers must be at least 1.");
        }

        return new EvaluateStockOptions(
            ResolveCliPath(engineFilePath),
            ResolveStockfishPath(stockfishPath),
            stockfishElo,
            openingsFilePath,
            games,
            maxPlies,
            timeLimitSeconds,
            workers,
            log,
            shortSha);
    }

    private static int RunEvaluationSeries(
        EvaluationParticipantFactory engineAFactory,
        EvaluationParticipantFactory engineBFactory,
        string openingsFilePath,
        int games,
        int maxPlies,
        double timeLimitSeconds,
        int workers,
        bool log,
        string? shortSha)
    {
        var openingFens = LoadOpeningPositions(openingsFilePath);
        var totalPairs = games / 2;
        using var engineAInfo = engineAFactory.Create();
        using var engineBInfo = engineBFactory.Create();
        var aggregate = new MatchAggregate(engineAInfo, engineBInfo);
        var csvLogger = log
            ? EvaluationCsvLogger.Create(shortSha!)
            : null;

        try
        {
            Console.WriteLine("=== EVALUATION START ===");
            Console.WriteLine($"Engine A source: {engineAInfo.SourcePath}");
            Console.WriteLine($"Engine A name: {engineAInfo.EngineStem}");
            Console.WriteLine($"Engine A details: {engineAInfo.Details}");
            Console.WriteLine($"Engine B source: {engineBInfo.SourcePath}");
            Console.WriteLine($"Engine B name: {engineBInfo.EngineStem}");
            Console.WriteLine($"Engine B details: {engineBInfo.Details}");
            Console.WriteLine($"Games: {games}");
            Console.WriteLine($"Pairs: {totalPairs}");
            Console.WriteLine($"Time limit per move: {timeLimitSeconds * 1000.0:F1}ms");
            Console.WriteLine($"Max plies: {maxPlies}");
            Console.WriteLine($"Workers: {workers}");
            Console.WriteLine($"Opening source file: {openingsFilePath}");
            Console.WriteLine($"Unique opening positions loaded: {openingFens.Count}");
            Console.WriteLine($"Logging enabled: {log}");
            if (csvLogger is not null)
            {
                Console.WriteLine($"Logging short SHA: {shortSha}");
                Console.WriteLine($"CSV log file: {csvLogger.FilePath}");
            }

            var outputLock = new object();
            Parallel.ForEach(
                Enumerable.Range(0, totalPairs),
                new ParallelOptions { MaxDegreeOfParallelism = workers },
                pairIndex =>
                {
                    var openingFen = openingFens[pairIndex % openingFens.Count];
                    var whiteGameNumber = pairIndex * 2 + 1;
                    var blackGameNumber = pairIndex * 2 + 2;
                    var pairNumber = pairIndex + 1;
                    var openingIndex = pairIndex % openingFens.Count + 1;

                    using var pairEngineA = engineAFactory.Create();
                    using var pairEngineB = engineBFactory.Create();

                    var gameAWhite = PlayEvaluationGame(
                        whiteGameNumber,
                        pairNumber,
                        openingIndex,
                        openingFen,
                        pairEngineA,
                        pairEngineB,
                        timeLimitSeconds,
                        maxPlies,
                        engineAWasWhite: true);

                    var gameBWhite = PlayEvaluationGame(
                        blackGameNumber,
                        pairNumber,
                        openingIndex,
                        openingFen,
                        pairEngineB,
                        pairEngineA,
                        timeLimitSeconds,
                        maxPlies,
                        engineAWasWhite: false);

                    var pairResult = new PairEvaluationResult(
                        pairNumber,
                        openingIndex,
                        gameAWhite,
                        gameBWhite,
                        (ScoreForEngine(gameAWhite) + ScoreForEngine(gameBWhite)) / 2.0);

                    lock (outputLock)
                    {
                        aggregate.Record(pairResult.FirstGame);
                        PrintGameSummary(pairResult.FirstGame);
                        csvLogger?.WriteGame(pairResult.FirstGame);

                        aggregate.Record(pairResult.SecondGame);
                        PrintGameSummary(pairResult.SecondGame);
                        csvLogger?.WriteGame(pairResult.SecondGame);

                        Console.WriteLine(
                            $"Pair {pairResult.PairNumber}/{totalPairs}: opening_index={pairResult.OpeningIndex} | engine_a_pair_score={pairResult.PairScore:F2}");
                    }
                });

            var aggregateMetrics = BuildAggregateMetrics(aggregate, totalPairs);
            PrintEvaluationSummary(aggregate, aggregateMetrics);
            Console.WriteLine("=== EVALUATION DONE ===");
            return aggregate.Failures > 0 ? 1 : 0;
        }
        finally
        {
            csvLogger?.Dispose();
        }
    }

    private static EvaluationGameResult PlayEvaluationGame(
        int gameNumber,
        int pairNumber,
        int openingIndex,
        string openingFen,
        EvaluationParticipant whiteEngine,
        EvaluationParticipant blackEngine,
        double timeLimitSeconds,
        int maxPlies,
        bool engineAWasWhite)
    {
        var board = new BoardState(openingFen);
        var whiteStats = new EngineGameStats();
        var blackStats = new EngineGameStats();
        string result;
        string terminationReason;
        string? failureEngineStem = null;
        string? failureMessage = null;
        var gameStopwatch = Stopwatch.StartNew();
        var plies = 0;

        while (!board.IsGameOver && plies < maxPlies)
        {
            var sideToMoveIsWhite = board.WhiteToMove;
            var activeEngine = sideToMoveIsWhite ? whiteEngine : blackEngine;
            var activeStats = sideToMoveIsWhite ? whiteStats : blackStats;

            SearchResult searchResult;
            var searchStopwatch = Stopwatch.StartNew();
            try
            {
                searchResult = activeEngine.SearchMove(board, timeLimitSeconds);
            }
            catch (Exception exception)
            {
                var rootCause = UnwrapInvocationException(exception);
                failureEngineStem = activeEngine.EngineStem;
                failureMessage = rootCause.Message;
                terminationReason = "engine_exception";
                result = sideToMoveIsWhite ? "0-1" : "1-0";
                gameStopwatch.Stop();
                return new EvaluationGameResult(
                    gameNumber,
                    pairNumber,
                    openingIndex,
                    openingFen,
                    whiteEngine.EngineStem,
                    blackEngine.EngineStem,
                    result,
                    terminationReason,
                    plies,
                    engineAWasWhite,
                    failureEngineStem,
                    failureMessage,
                    whiteStats,
                    blackStats,
                    gameStopwatch.Elapsed);
            }

            searchStopwatch.Stop();
            activeStats.RecordMove(searchStopwatch.Elapsed.TotalSeconds, searchResult);

            if (!IsLegalReturnedMove(board, searchResult.Move))
            {
                failureEngineStem = activeEngine.EngineStem;
                failureMessage = $"Illegal move returned: {searchResult.MoveSan} ({MoveToUci(searchResult.Move)})";
                terminationReason = "illegal_move";
                result = sideToMoveIsWhite ? "0-1" : "1-0";
                gameStopwatch.Stop();
                return new EvaluationGameResult(
                    gameNumber,
                    pairNumber,
                    openingIndex,
                    openingFen,
                    whiteEngine.EngineStem,
                    blackEngine.EngineStem,
                    result,
                    terminationReason,
                    plies,
                    engineAWasWhite,
                    failureEngineStem,
                    failureMessage,
                    whiteStats,
                    blackStats,
                    gameStopwatch.Elapsed);
            }

            board.Push(searchResult.Move);
            plies++;

            if (board.CanClaimDraw())
            {
                break;
            }
        }

        gameStopwatch.Stop();

        if (board.IsCheckmate)
        {
            result = WinnerLabel(board) == "white" ? "1-0" : "0-1";
            terminationReason = "checkmate";
        }
        else if (board.IsGameOver)
        {
            result = "1/2-1/2";
            terminationReason = OutcomeLabel(board);
        }
        else if (board.CanClaimDraw())
        {
            result = "1/2-1/2";
            terminationReason = "claimable_draw";
        }
        else
        {
            result = "1/2-1/2";
            terminationReason = "max_plies";
        }

        return new EvaluationGameResult(
            gameNumber,
            pairNumber,
            openingIndex,
            openingFen,
            whiteEngine.EngineStem,
            blackEngine.EngineStem,
            result,
            terminationReason,
            plies,
            engineAWasWhite,
            failureEngineStem,
            failureMessage,
            whiteStats,
            blackStats,
            gameStopwatch.Elapsed);
    }

    private static EvaluationParticipant ResolveParticipantFromEngineFile(string engineFilePath)
    {
        var engine = EngineVersions.ResolveTimeLimitedEngineFromFilePath(engineFilePath);
        return new EvaluationParticipant(
            engine.SourcePath,
            engine.EngineStem,
            engine.SearchMethodName,
            engine.SearchMove);
    }

    private static EvaluationParticipant CreateStockfishParticipant(string stockfishPath, int stockfishElo)
    {
        var stockfish = new StockfishEngine(stockfishPath, stockfishElo);
        return new EvaluationParticipant(
            stockfish.BinaryPath,
            $"stockfish-{stockfish.ConfiguredElo}",
            $"uci elo={stockfish.ConfiguredElo}",
            stockfish.SearchMove,
            stockfish);
    }

    private static EvaluationParticipantFactory CreateEngineFileParticipantFactory(string engineFilePath)
    {
        var resolvedPath = ResolveCliPath(engineFilePath);
        return new EvaluationParticipantFactory(() => ResolveParticipantFromEngineFile(resolvedPath));
    }

    private static EvaluationParticipantFactory CreateStockfishParticipantFactory(string stockfishPath, int stockfishElo)
    {
        var resolvedPath = ResolveStockfishPath(stockfishPath);
        return new EvaluationParticipantFactory(() => CreateStockfishParticipant(resolvedPath, stockfishElo));
    }

    private static void PrintGameSummary(EvaluationGameResult result)
    {
        var engineAScore = ScoreForEngine(result);
        Console.WriteLine(
            $"Game {result.GameNumber}: {result.WhiteEngineStem} vs {result.BlackEngineStem} => {result.Result} | term={result.TerminationReason} | plies={result.Plies} | engine_a_score={engineAScore:F1} | duration={result.Elapsed.TotalSeconds:F3}s");

        if (!string.IsNullOrWhiteSpace(result.FailureEngineStem))
        {
            Console.WriteLine(
                $"  Failure: engine={result.FailureEngineStem} | message={result.FailureMessage}");
        }
    }

    private static void PrintEvaluationSummary(MatchAggregate aggregate, AggregateMetrics metrics)
    {
        Console.WriteLine();
        Console.WriteLine("Summary:");
        Console.WriteLine($"Engine A: {aggregate.EngineA.EngineStem}");
        Console.WriteLine($"Engine B: {aggregate.EngineB.EngineStem}");
        Console.WriteLine($"Engine A wins: {aggregate.EngineAWins}");
        Console.WriteLine($"Draws: {aggregate.Draws}");
        Console.WriteLine($"Engine A losses: {aggregate.EngineALosses}");
        Console.WriteLine($"Engine A total score: {aggregate.EngineAScore:F1}/{aggregate.Games}");
        Console.WriteLine($"Engine A score rate: {aggregate.EngineAScore / aggregate.Games:F4}");
        Console.WriteLine($"Average plies per game: {aggregate.TotalPlies / (double)aggregate.Games:F2}");
        Console.WriteLine($"Failures: {aggregate.Failures}");
        Console.WriteLine($"Engine A average move time: {metrics.EngineAAverageMoveMs:F3}ms");
        Console.WriteLine($"Engine B average move time: {metrics.EngineBAverageMoveMs:F3}ms");
        Console.WriteLine($"Engine A average positions/nodes: {metrics.EngineAAveragePositions:F2}");
        Console.WriteLine($"Engine B average positions/nodes: {metrics.EngineBAveragePositions:F2}");

        if (metrics.PairMean is not null)
        {
            Console.WriteLine($"Engine A paired mean score: {metrics.PairMean.Value:F4}");
            Console.WriteLine($"Engine A paired score sd: {metrics.PairStandardDeviation!.Value:F4}");
            Console.WriteLine($"Engine A lcb95: {metrics.PairLcb95!.Value:F4}");
        }
    }

    private static AggregateMetrics BuildAggregateMetrics(MatchAggregate aggregate, int totalPairs)
    {
        var engineAAverageMoveMs = AverageOrZero(aggregate.EngineATotalMoveSeconds, aggregate.EngineATotalMoves) * 1000.0;
        var engineBAverageMoveMs = AverageOrZero(aggregate.EngineBTotalMoveSeconds, aggregate.EngineBTotalMoves) * 1000.0;
        var engineAAveragePositions = AverageOrZero(aggregate.EngineATotalPositions, aggregate.EngineATotalMoves);
        var engineBAveragePositions = AverageOrZero(aggregate.EngineBTotalPositions, aggregate.EngineBTotalMoves);

        if (totalPairs <= 0)
        {
            return new AggregateMetrics(
                engineAAverageMoveMs,
                engineBAverageMoveMs,
                engineAAveragePositions,
                engineBAveragePositions,
                null,
                null,
                null);
        }

        var mean = aggregate.PairScores.Average();
        var standardDeviation = SampleStandardDeviation(aggregate.PairScores, mean);
        var tCritical = OneSidedT95Critical(totalPairs - 1);
        var lcb95 = mean - tCritical * standardDeviation / Math.Sqrt(totalPairs);

        return new AggregateMetrics(
            engineAAverageMoveMs,
            engineBAverageMoveMs,
            engineAAveragePositions,
            engineBAveragePositions,
            mean,
            standardDeviation,
            lcb95);
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

    private static double ScoreForEngine(EvaluationGameResult result)
    {
        return result.Result switch
        {
            "1-0" when result.EngineAWasWhite => 1.0,
            "1-0" => 0.0,
            "0-1" when !result.EngineAWasWhite => 1.0,
            "0-1" => 0.0,
            _ => 0.5,
        };
    }

    private static List<string> LoadOpeningPositions(string openingsFilePath)
    {
        var fullPath = ResolveCliPath(openingsFilePath);
        if (!File.Exists(fullPath))
        {
            throw new FileNotFoundException($"Opening source file not found: {fullPath}", fullPath);
        }

        var lines = File.ReadAllLines(fullPath);
        var openings = lines.Any(line => line.TrimStart().StartsWith("pos ", StringComparison.Ordinal))
            ? LoadOpeningPositionsFromBook(lines, fullPath)
            : LoadOpeningPositionsFromFenList(lines, fullPath);

        if (openings.Count == 0)
        {
            throw new InvalidOperationException($"No usable opening positions found in {fullPath}.");
        }

        ShuffleInPlace(openings);
        return openings;
    }

    private static List<string> LoadOpeningPositionsFromFenList(IEnumerable<string> lines, string fullPath)
    {
        var openings = new List<string>();
        var seen = new HashSet<string>(StringComparer.Ordinal);

        foreach (var rawLine in lines)
        {
            var line = rawLine.Trim();
            if (string.IsNullOrWhiteSpace(line) || line.StartsWith('#'))
            {
                continue;
            }

            _ = new BoardState(line);
            if (seen.Add(line))
            {
                openings.Add(line);
            }
        }

        return openings;
    }

    private static List<string> LoadOpeningPositionsFromBook(IEnumerable<string> lines, string fullPath)
    {
        var openings = new List<string>();
        var seen = new HashSet<string>(StringComparer.Ordinal);
        var freshBoardFen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

        foreach (var rawLine in lines)
        {
            var line = rawLine.Trim();
            if (string.IsNullOrWhiteSpace(line))
            {
                continue;
            }

            if (!line.StartsWith("pos ", StringComparison.Ordinal))
            {
                continue;
            }

            var fenWithoutCounters = line["pos ".Length..].Trim();
            var fen = ExpandBookFen(fenWithoutCounters);
            _ = new BoardState(fen);

            if (string.Equals(fen, freshBoardFen, StringComparison.Ordinal))
            {
                continue;
            }

            if (seen.Add(fen))
            {
                openings.Add(fen);
            }
        }

        if (openings.Count == 0)
        {
            throw new InvalidOperationException(
                $"No usable non-initial 'pos' entries were found in opening book {fullPath}.");
        }

        return openings;
    }

    private static string ExpandBookFen(string fenWithoutCounters)
    {
        var parts = fenWithoutCounters.Split(' ', StringSplitOptions.RemoveEmptyEntries);
        if (parts.Length != 4)
        {
            throw new InvalidOperationException(
                $"Opening book FEN must contain exactly 4 fields before counters, but got: '{fenWithoutCounters}'");
        }

        return $"{fenWithoutCounters} 0 1";
    }

    private static void ShuffleInPlace<T>(IList<T> items)
    {
        for (var index = items.Count - 1; index > 0; index--)
        {
            var swapIndex = Random.Shared.Next(index + 1);
            (items[index], items[swapIndex]) = (items[swapIndex], items[index]);
        }
    }

    private static string FindDefaultOpeningSourceFile()
    {
        return Path.Combine(FindRepoRoot(), "Book.txt");
    }

    private static string ResolveCliPath(string path)
    {
        return Path.IsPathRooted(path)
            ? Path.GetFullPath(path)
            : Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), path));
    }

    private static string ResolveStockfishPath(string stockfishPath)
    {
        if (string.IsNullOrWhiteSpace(stockfishPath))
        {
            throw new ArgumentException("--stockfish-path must not be empty.");
        }

        return Path.IsPathRooted(stockfishPath)
            ? Path.GetFullPath(stockfishPath)
            : stockfishPath;
    }

    private static string FindRepoRoot()
    {
        var current = new DirectoryInfo(AppContext.BaseDirectory);
        while (current is not null)
        {
            var candidate = Path.Combine(current.FullName, "..", "..", "..", "..");
            candidate = Path.GetFullPath(candidate);
            if (File.Exists(Path.Combine(candidate, "README.md"))
                && File.Exists(Path.Combine(candidate, "Book.txt"))
                && Directory.Exists(Path.Combine(candidate, "engine_csharp")))
            {
                return candidate;
            }

            current = current.Parent;
        }

        throw new DirectoryNotFoundException("Unable to locate repository root.");
    }

    private static double AverageOrZero(double total, int count)
    {
        return count == 0 ? 0.0 : total / count;
    }

    private static double SampleStandardDeviation(IReadOnlyList<double> values, double mean)
    {
        if (values.Count <= 1)
        {
            return 0.0;
        }

        var sumSquares = 0.0;
        foreach (var value in values)
        {
            var delta = value - mean;
            sumSquares += delta * delta;
        }

        return Math.Sqrt(sumSquares / (values.Count - 1));
    }

    private static double OneSidedT95Critical(int degreesOfFreedom)
    {
        if (degreesOfFreedom <= 1)
        {
            return 6.314;
        }

        if (degreesOfFreedom <= 2)
        {
            return 2.920;
        }

        if (degreesOfFreedom <= 3)
        {
            return 2.353;
        }

        if (degreesOfFreedom <= 4)
        {
            return 2.132;
        }

        if (degreesOfFreedom <= 5)
        {
            return 2.015;
        }

        if (degreesOfFreedom <= 6)
        {
            return 1.943;
        }

        if (degreesOfFreedom <= 7)
        {
            return 1.895;
        }

        if (degreesOfFreedom <= 8)
        {
            return 1.860;
        }

        if (degreesOfFreedom <= 9)
        {
            return 1.833;
        }

        if (degreesOfFreedom <= 10)
        {
            return 1.812;
        }

        if (degreesOfFreedom <= 12)
        {
            return 1.782;
        }

        if (degreesOfFreedom <= 15)
        {
            return 1.753;
        }

        if (degreesOfFreedom <= 20)
        {
            return 1.725;
        }

        if (degreesOfFreedom <= 25)
        {
            return 1.708;
        }

        if (degreesOfFreedom <= 30)
        {
            return 1.697;
        }

        if (degreesOfFreedom <= 40)
        {
            return 1.684;
        }

        if (degreesOfFreedom <= 60)
        {
            return 1.671;
        }

        if (degreesOfFreedom <= 120)
        {
            return 1.658;
        }

        return 1.645;
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

    private static Move MoveFromUci(BoardState board, string uci)
    {
        if (string.IsNullOrWhiteSpace(uci))
        {
            throw new ArgumentException("UCI move must not be empty.", nameof(uci));
        }

        var legalMoves = board.LegalMoves();
        var selectedMove = legalMoves.FirstOrDefault(move => MoveToUci(move) == uci);
        if (selectedMove is not null)
        {
            return selectedMove;
        }

        throw new InvalidOperationException($"Stockfish returned a move that is not legal in the current position: {uci}");
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
        var repoRoot = FindRepoRoot();
        var candidate = Path.Combine(repoRoot, "engine_scenarios");
        if (Directory.Exists(candidate))
        {
            return candidate;
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
        Console.Error.WriteLine("  dotnet run --project engine_csharp/src/LocalTesting -- endgame-1 --version v2.0 --time-limit-seconds 1.0");
        Console.Error.WriteLine("  dotnet run --project engine_csharp/src/LocalTesting -- endgame-2 --version v2.0 --time-limit-seconds 1.0");
        Console.Error.WriteLine("  dotnet run --project engine_csharp/src/LocalTesting -- evaluate-match --engine-a-file engine_csharp/src/Engine.Core/V1/V1_6Engine.cs --engine-b-file engine_csharp/src/Engine.Core/V1/V1_6Engine.cs --workers 6 --log --short-sha 1a2b3c4");
        Console.Error.WriteLine("  dotnet run --project engine_csharp/src/LocalTesting -- evaluate-stock --engine-file engine_csharp/src/Engine.Core/V1/V1_6Engine.cs --stockfish-path /path/to/stockfish --stockfish-elo 1800 --games 20 --time-limit-ms 100 --workers 6 --log --short-sha 1a2b3c4");
        Console.Error.WriteLine("  dotnet run --project engine_csharp/src/LocalTesting -- backend-worker-experiment --engine-file engine_csharp/src/Engine.Core/V2/V2_5Engine.cs --games 20 --time-limit-ms 100 --workers 6 --skip-1-worker");
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

    private sealed record EvaluateMatchOptions(
        string EngineAFilePath,
        string EngineBFilePath,
        string OpeningsFilePath,
        int Games,
        int MaxPlies,
        double TimeLimitSeconds,
        int Workers,
        bool Log,
        string? ShortSha);

    private sealed record EvaluateStockOptions(
        string EngineFilePath,
        string StockfishPath,
        int StockfishElo,
        string OpeningsFilePath,
        int Games,
        int MaxPlies,
        double TimeLimitSeconds,
        int Workers,
        bool Log,
        string? ShortSha);

    private sealed record EvaluationParticipant(
        string SourcePath,
        string EngineStem,
        string Details,
        Func<BoardState, double, SearchResult> SearchMove,
        IDisposable? Disposable = null) : IDisposable
    {
        public void Dispose()
        {
            Disposable?.Dispose();
        }
    }

    private sealed record EvaluationParticipantFactory(
        Func<EvaluationParticipant> Create);

    private sealed record PairEvaluationResult(
        int PairNumber,
        int OpeningIndex,
        EvaluationGameResult FirstGame,
        EvaluationGameResult SecondGame,
        double PairScore);

    private sealed record AggregateMetrics(
        double EngineAAverageMoveMs,
        double EngineBAverageMoveMs,
        double EngineAAveragePositions,
        double EngineBAveragePositions,
        double? PairMean,
        double? PairStandardDeviation,
        double? PairLcb95);

    private sealed class EngineGameStats
    {
        public int Moves { get; private set; }

        public double TotalMoveSeconds { get; private set; }

        public int TotalPositions { get; private set; }

        public void RecordMove(double elapsedSeconds, SearchResult result)
        {
            Moves++;
            TotalMoveSeconds += elapsedSeconds;
            TotalPositions += PositionCount(result);
        }
    }

    private sealed record EvaluationGameResult(
        int GameNumber,
        int PairNumber,
        int OpeningIndex,
        string OpeningFen,
        string WhiteEngineStem,
        string BlackEngineStem,
        string Result,
        string TerminationReason,
        int Plies,
        bool EngineAWasWhite,
        string? FailureEngineStem,
        string? FailureMessage,
        EngineGameStats WhiteStats,
        EngineGameStats BlackStats,
        TimeSpan Elapsed);

    private sealed class EvaluationCsvLogger : IDisposable
    {
        private readonly StreamWriter _writer;
        private bool _disposed;

        private EvaluationCsvLogger(string filePath, StreamWriter writer, string commitShortSha)
        {
            FilePath = filePath;
            CommitShortSha = commitShortSha;
            _writer = writer;
        }

        public string FilePath { get; }

        public string CommitShortSha { get; }

        public static EvaluationCsvLogger Create(string commitShortSha)
        {
            var logsDirectory = Path.Combine(FindRepoRoot(), "autoresearch", "logs");
            Directory.CreateDirectory(logsDirectory);

            var filePath = Path.Combine(logsDirectory, $"{commitShortSha}-result.csv");
            var writer = new StreamWriter(filePath, append: false);
            var logger = new EvaluationCsvLogger(filePath, writer, commitShortSha);
            logger.WriteHeader();
            return logger;
        }

        public void WriteGame(EvaluationGameResult result)
        {
            ThrowIfDisposed();

            var engineAScore = ScoreForEngine(result);
            var whiteAverageMoveMs = AverageOrZero(result.WhiteStats.TotalMoveSeconds, result.WhiteStats.Moves) * 1000.0;
            var blackAverageMoveMs = AverageOrZero(result.BlackStats.TotalMoveSeconds, result.BlackStats.Moves) * 1000.0;
            var whiteAveragePositions = AverageOrZero(result.WhiteStats.TotalPositions, result.WhiteStats.Moves);
            var blackAveragePositions = AverageOrZero(result.BlackStats.TotalPositions, result.BlackStats.Moves);

            WriteFields(
                CommitShortSha,
                result.GameNumber,
                result.PairNumber,
                result.OpeningIndex,
                result.EngineAWasWhite,
                result.WhiteEngineStem,
                result.BlackEngineStem,
                result.Result,
                result.TerminationReason,
                result.Plies,
                engineAScore,
                result.WhiteStats.Moves,
                result.BlackStats.Moves,
                result.WhiteStats.TotalPositions,
                result.BlackStats.TotalPositions,
                whiteAveragePositions,
                blackAveragePositions,
                whiteAverageMoveMs,
                blackAverageMoveMs,
                result.Elapsed.TotalMilliseconds,
                result.FailureEngineStem ?? string.Empty,
                result.FailureMessage ?? string.Empty,
                result.OpeningFen);
        }

        public void Dispose()
        {
            if (_disposed)
            {
                return;
            }

            _writer.Dispose();
            _disposed = true;
        }

        private void WriteHeader()
        {
            WriteFields(
                "commit_short_sha",
                "game_number",
                "pair_number",
                "opening_index",
                "engine_a_was_white",
                "white_engine",
                "black_engine",
                "result",
                "termination_reason",
                "plies",
                "engine_a_score",
                "white_moves",
                "black_moves",
                "white_total_positions",
                "black_total_positions",
                "white_average_positions",
                "black_average_positions",
                "white_average_move_ms",
                "black_average_move_ms",
                "game_elapsed_ms",
                "failure_engine",
                "failure_message",
                "opening_fen");
        }

        private void WriteFields(params object[] values)
        {
            _writer.WriteLine(string.Join(",", values.Select(FormatCsvField)));
            _writer.Flush();
        }

        private static string FormatCsvField(object value)
        {
            var text = value switch
            {
                bool boolValue => boolValue ? "true" : "false",
                IFormattable formattable => formattable.ToString(null, CultureInfo.InvariantCulture),
                _ => value.ToString() ?? string.Empty,
            };

            if (text.Contains('"') || text.Contains(',') || text.Contains('\n') || text.Contains('\r'))
            {
                return $"\"{text.Replace("\"", "\"\"", StringComparison.Ordinal)}\"";
            }

            return text;
        }

        private void ThrowIfDisposed()
        {
            if (_disposed)
            {
                throw new ObjectDisposedException(nameof(EvaluationCsvLogger));
            }
        }
    }

    private sealed class MatchAggregate
    {
        private double? _pendingFirstGameScore;

        public MatchAggregate(EvaluationParticipant engineA, EvaluationParticipant engineB)
        {
            EngineA = engineA;
            EngineB = engineB;
        }

        public EvaluationParticipant EngineA { get; }

        public EvaluationParticipant EngineB { get; }

        public int Games { get; private set; }

        public int EngineAWins { get; private set; }

        public int EngineALosses { get; private set; }

        public int Draws { get; private set; }

        public int Failures { get; private set; }

        public double EngineAScore { get; private set; }

        public int TotalPlies { get; private set; }

        public int EngineATotalMoves { get; private set; }

        public int EngineBTotalMoves { get; private set; }

        public double EngineATotalMoveSeconds { get; private set; }

        public double EngineBTotalMoveSeconds { get; private set; }

        public double EngineATotalPositions { get; private set; }

        public double EngineBTotalPositions { get; private set; }

        public List<double> PairScores { get; } = [];

        public void Record(EvaluationGameResult game)
        {
            Games++;
            TotalPlies += game.Plies;

            var score = ScoreForEngine(game);
            EngineAScore += score;

            if (score == 1.0)
            {
                EngineAWins++;
            }
            else if (score == 0.0)
            {
                EngineALosses++;
            }
            else
            {
                Draws++;
            }

            if (!string.IsNullOrWhiteSpace(game.FailureEngineStem))
            {
                Failures++;
            }

            if (game.EngineAWasWhite)
            {
                EngineATotalMoves += game.WhiteStats.Moves;
                EngineATotalMoveSeconds += game.WhiteStats.TotalMoveSeconds;
                EngineATotalPositions += game.WhiteStats.TotalPositions;
                EngineBTotalMoves += game.BlackStats.Moves;
                EngineBTotalMoveSeconds += game.BlackStats.TotalMoveSeconds;
                EngineBTotalPositions += game.BlackStats.TotalPositions;
            }
            else
            {
                EngineATotalMoves += game.BlackStats.Moves;
                EngineATotalMoveSeconds += game.BlackStats.TotalMoveSeconds;
                EngineATotalPositions += game.BlackStats.TotalPositions;
                EngineBTotalMoves += game.WhiteStats.Moves;
                EngineBTotalMoveSeconds += game.WhiteStats.TotalMoveSeconds;
                EngineBTotalPositions += game.WhiteStats.TotalPositions;
            }

            if (_pendingFirstGameScore is null)
            {
                _pendingFirstGameScore = score;
            }
            else
            {
                PairScores.Add((_pendingFirstGameScore.Value + score) / 2.0);
                _pendingFirstGameScore = null;
            }
        }
    }

    private sealed class StockfishEngine : IDisposable
    {
        private readonly Process _process;
        private readonly StreamWriter _input;
        private readonly StreamReader _output;
        private bool _disposed;

        public StockfishEngine(string binaryPath, int requestedElo)
        {
            BinaryPath = binaryPath;

            try
            {
                _process = new Process
                {
                    StartInfo = new ProcessStartInfo
                    {
                        FileName = binaryPath,
                        RedirectStandardInput = true,
                        RedirectStandardOutput = true,
                        RedirectStandardError = true,
                        UseShellExecute = false,
                        CreateNoWindow = true,
                    }
                };
                _process.Start();
            }
            catch (Exception exception)
            {
                throw new InvalidOperationException(
                    $"Unable to start Stockfish from '{binaryPath}'. Provide a valid binary path with --stockfish-path.",
                    exception);
            }

            _input = _process.StandardInput;
            _output = _process.StandardOutput;

            SendCommand("uci");
            var uciHandshake = ReadUntil(line => line == "uciok");
            var eloOption = ParseUciEloOption(uciHandshake);
            if (eloOption is null)
            {
                throw new InvalidOperationException(
                    $"The Stockfish binary at '{binaryPath}' does not expose the UCI_Elo option needed for limited-strength evaluation.");
            }

            ConfiguredElo = Math.Clamp(requestedElo, eloOption.Value.Min, eloOption.Value.Max);
            if (ConfiguredElo != requestedElo)
            {
                Console.WriteLine(
                    $"Requested Stockfish Elo {requestedElo} is outside the supported range {eloOption.Value.Min}-{eloOption.Value.Max}; using {ConfiguredElo}.");
            }

            SendCommand("setoption name UCI_LimitStrength value true");
            SendCommand($"setoption name UCI_Elo value {ConfiguredElo}");
            SendCommand("isready");
            _ = ReadUntil(line => line == "readyok");
        }

        public string BinaryPath { get; }

        public int ConfiguredElo { get; }

        public SearchResult SearchMove(BoardState board, double timeLimitSeconds)
        {
            ThrowIfDisposed();

            var moveTimeMs = Math.Max(1, (int)Math.Round(timeLimitSeconds * 1000.0, MidpointRounding.AwayFromZero));
            SendCommand($"position fen {board.Fen}");
            SendCommand($"go movetime {moveTimeMs}");

            var searchLines = ReadUntil(line => line.StartsWith("bestmove ", StringComparison.Ordinal));
            var bestMoveLine = searchLines[^1];
            var bestMoveUci = ParseBestMove(bestMoveLine);
            var move = MoveFromUci(board, bestMoveUci);
            var lastInfo = searchLines.LastOrDefault(line => line.StartsWith("info ", StringComparison.Ordinal));
            var info = ParseSearchInfo(lastInfo);

            return new SearchResult(
                move,
                board.GetSan(move),
                info.ScoreCp,
                info.Nodes > int.MaxValue ? int.MaxValue : (int)info.Nodes,
                info.Depth,
                null,
                null,
                null,
                null,
                null,
                info.Nodes > int.MaxValue ? int.MaxValue : (int)info.Nodes);
        }

        public void Dispose()
        {
            if (_disposed)
            {
                return;
            }

            try
            {
                if (!_process.HasExited)
                {
                    SendCommand("quit");
                    if (!_process.WaitForExit(1000))
                    {
                        _process.Kill(entireProcessTree: true);
                    }
                }
            }
            catch
            {
                if (!_process.HasExited)
                {
                    _process.Kill(entireProcessTree: true);
                }
            }
            finally
            {
                _process.Dispose();
                _disposed = true;
            }
        }

        private void SendCommand(string command)
        {
            _input.WriteLine(command);
            _input.Flush();
        }

        private List<string> ReadUntil(Func<string, bool> predicate)
        {
            var lines = new List<string>();
            while (true)
            {
                var line = _output.ReadLine();
                if (line is null)
                {
                    throw new InvalidOperationException("Stockfish terminated unexpectedly while waiting for output.");
                }

                lines.Add(line);
                if (predicate(line))
                {
                    return lines;
                }
            }
        }

        private static (int Min, int Max)? ParseUciEloOption(IEnumerable<string> lines)
        {
            foreach (var line in lines)
            {
                if (!line.StartsWith("option name UCI_Elo type spin", StringComparison.Ordinal))
                {
                    continue;
                }

                var tokens = line.Split(' ', StringSplitOptions.RemoveEmptyEntries);
                int? min = null;
                int? max = null;
                for (var index = 0; index < tokens.Length - 1; index++)
                {
                    if (tokens[index] == "min")
                    {
                        min = int.Parse(tokens[index + 1], CultureInfo.InvariantCulture);
                    }
                    else if (tokens[index] == "max")
                    {
                        max = int.Parse(tokens[index + 1], CultureInfo.InvariantCulture);
                    }
                }

                if (min is not null && max is not null)
                {
                    return (min.Value, max.Value);
                }
            }

            return null;
        }

        private static string ParseBestMove(string bestMoveLine)
        {
            var tokens = bestMoveLine.Split(' ', StringSplitOptions.RemoveEmptyEntries);
            if (tokens.Length < 2 || tokens[1] == "(none)")
            {
                throw new InvalidOperationException($"Stockfish did not return a usable bestmove line: {bestMoveLine}");
            }

            return tokens[1];
        }

        private static ParsedStockfishInfo ParseSearchInfo(string? infoLine)
        {
            if (string.IsNullOrWhiteSpace(infoLine))
            {
                return new ParsedStockfishInfo(0, 0, null);
            }

            var tokens = infoLine.Split(' ', StringSplitOptions.RemoveEmptyEntries);
            long nodes = 0;
            int scoreCp = 0;
            int? depth = null;

            for (var index = 0; index < tokens.Length - 1; index++)
            {
                switch (tokens[index])
                {
                    case "depth":
                        depth = int.Parse(tokens[index + 1], CultureInfo.InvariantCulture);
                        break;
                    case "nodes":
                        nodes = long.Parse(tokens[index + 1], CultureInfo.InvariantCulture);
                        break;
                    case "score" when index + 2 < tokens.Length:
                        if (tokens[index + 1] == "cp")
                        {
                            scoreCp = int.Parse(tokens[index + 2], CultureInfo.InvariantCulture);
                        }
                        else if (tokens[index + 1] == "mate")
                        {
                            var mate = int.Parse(tokens[index + 2], CultureInfo.InvariantCulture);
                            scoreCp = mate > 0 ? 100000 - mate : -100000 - mate;
                        }
                        break;
                }
            }

            return new ParsedStockfishInfo(nodes, scoreCp, depth);
        }

        private void ThrowIfDisposed()
        {
            if (_disposed)
            {
                throw new ObjectDisposedException(nameof(StockfishEngine));
            }
        }
    }

    private sealed record ParsedStockfishInfo(long Nodes, int ScoreCp, int? Depth);
}
