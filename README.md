# Chess Azure Functions Backend

This repository serves chess moves through a C# Azure Functions backend and acts as a local research workspace for improving the C# chess engine.

The backend accepts a chess board state as a FEN string and returns a SAN move plus timing/debug metadata. It is intended to work alongside the frontend on `sneakyowl.net`; that frontend is out of scope here.

## Architecture

- `engine_csharp/src/Engine.Functions/`: Azure Functions HTTP API.
- `engine_csharp/src/Engine.Core/`: shared board/search infrastructure and versioned engines.
- `engine_csharp/src/LocalTesting/`: local scenario runner, benchmarks, and evaluator workflow.
- `engine_scenarios/`: puzzle/endgame scenario JSON plus reference images and sample output.
- `autoresearch/`: constrained `v2+` engine-improvement workflow and experiment history.

The public serving path is now C# end to end. Engine changes can be made directly in `Engine.Core` and exposed through `Engine.Functions` without a Python rewrite.

## API

The Azure Function exposes one versioned endpoint:

| Endpoint | Summary |
| --- | --- |
| `POST /api/chess/v0` | Random legal move baseline |
| `POST /api/chess/v2.0` | C# `V2_0Engine` |
| `POST /api/chess/v2.9` | C# `V2_9Engine` |
| `POST /api/chess/v3.0` | C# `V3_0Engine` with opening book and optional warm-instance search context |
| `POST /api/chess/v3.4` | C# `V3_4Engine` with opening book and optional warm-instance search context |

Route versions also accept underscores, for example `/api/chess/v3_4`.

Request body:

```json
{
  "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
  "game_id": "optional-stable-game-key",
  "reset_context": false
}
```

For `v3.0` and `v3.4`, pass either `game_id` or `context_id` to allow warm Azure Functions instances to reuse a per-game transposition table across requests. This is an optimization only: cold starts, scale-out, or instance recycling may start with an empty context. Use `reset_context: true` when starting a new game with the same key.

Successful responses include:

```json
{
  "move": "e4",
  "processing_time": 0.123,
  "debug": {
    "version": "v3.4",
    "engine": "csharp_v3_4",
    "selected_move_uci": "e2e4",
    "score": 32,
    "completed_depth": 5,
    "moves_evaluated": 24584,
    "nodes_searched": 39362,
    "tt_entries": 3407,
    "tt_probes": 6607,
    "tt_hits": 3155,
    "tt_cutoffs": 1240,
    "timed_out": true
  }
}
```

Errors return JSON with an `error` field and debug context for missing/invalid FEN, checkmate, stalemate, no legal moves, unsupported versions, and unhandled engine failures.

The server-controlled move budget is read from `ENGINE_TIME_LIMIT_SECONDS` and defaults to `2.0`.

## Local Development

Install the .NET 8 SDK and Azure Functions Core Tools v4.

Build everything:

```bash
dotnet build engine_csharp/ChessEngine.sln
```

Run the Azure Functions API locally:

```bash
cd engine_csharp/src/Engine.Functions
func start
```

Example request:

```bash
curl -X POST http://localhost:7071/api/chess/v3.4 \
  -H "Content-Type: application/json" \
  -d '{"fen":"rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"}'
```

Allowed browser origins are:

- `https://sneakyowl.net`
- `https://www.sneakyowl.net`

## Deployment Notes

Deploy `engine_csharp/src/Engine.Functions` as a .NET 8 isolated Azure Functions app. `Openings.lookup.tsv` is copied into the function output during build so opening-book lookup works in published deployments.

Configure `ENGINE_TIME_LIMIT_SECONDS` in Azure App Settings when the default `2.0` second budget should change.

## Native Engine Workflow

Use the C# `LocalTesting` commands for V3+ engine validation and research. These commands resolve compiled engines by source file path and reject pre-V3 engine files.

```bash
dotnet run --project engine_csharp/src/LocalTesting -- puzzle-1 --engine-file engine_csharp/src/Engine.Core/V3/V3_4Engine.cs --time-limit-seconds 1.0
dotnet run --project engine_csharp/src/LocalTesting -- puzzle-2 --engine-file engine_csharp/src/Engine.Core/V3/V3_4Engine.cs --time-limit-seconds 1.0 --max-plies 70
dotnet run --project engine_csharp/src/LocalTesting -- endgame-1 --engine-file engine_csharp/src/Engine.Core/V3/V3_4Engine.cs --time-limit-seconds 1.0
dotnet run --project engine_csharp/src/LocalTesting -- endgame-2 --engine-file engine_csharp/src/Engine.Core/V3/V3_4Engine.cs --time-limit-seconds 1.0
dotnet run --project engine_csharp/src/LocalTesting -- evaluate-match --engine-a-file engine_csharp/src/Engine.Core/V3/V3_4Engine.cs --engine-b-file engine_csharp/src/Engine.Core/V3/V3_0Engine.cs --games 20 --time-limit-ms 100 --max-plies 200 --workers 6
```

For Stockfish evaluation, set `STOCKFISH_PATH` and use the evaluator contract in `autoresearch/README.md`.

## Autoresearch

`autoresearch/` defines the `v2+` experimentation contract. Read these before autonomous engine-iteration work:

- `autoresearch/README.md`
- `autoresearch/ATTEMPTS.md`

The fixed evaluator baseline is local `stockfish-1350`. The current evaluator command and approval rule are documented in `autoresearch/README.md`; latest approved seed metadata lives in `autoresearch/state.json` and the append-only history in `autoresearch/ATTEMPTS.md`.

Approval requires a clean build, a completed evaluator run, no illegal/crash failures, and `lcb95 > 0.5`.
