# C# Engine Workspace

This directory contains the deployed Azure Functions backend, the reusable engine core, and local engine validation tools.

## Projects

- `src/Engine.Functions`: .NET 8 isolated Azure Functions HTTP API.
- `src/Engine.Core`: shared board/search infrastructure plus versioned engine files.
- `src/LocalTesting`: scenario runner, benchmarks, and evaluator commands.

## Serving Intent

The public backend is now C# end to end. `Engine.Functions` accepts HTTP requests, validates FEN input, dispatches to exact compiled engines in `Engine.Core`, and returns SAN moves with timing/debug metadata.

Supported public route shape:

```text
POST /api/chess/{version}
```

Supported versions are `v0`, `v2.0`, `v2.9`, `v3.0`, and `v3.4`.

## Commands

```bash
dotnet build engine_csharp/ChessEngine.sln
cd engine_csharp/src/Engine.Functions
func start
```

Local engine validation:

```bash
dotnet run --project engine_csharp/src/LocalTesting -- puzzle-1 --versions v1 v1.1 v1.2 v1.3 v1.4 --depth 4
dotnet run --project engine_csharp/src/LocalTesting -- puzzle-1 --versions v1.5 v1.6 v2.0 --time-limit-seconds 1.0
dotnet run --project engine_csharp/src/LocalTesting -- evaluate-match --engine-a-file engine_csharp/src/Engine.Core/V3/V3_0Engine.cs --engine-b-file engine_csharp/src/Engine.Core/V2/V2_9Engine.cs --games 20 --time-limit-ms 100 --max-plies 200 --workers 6
```
