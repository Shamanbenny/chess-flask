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
dotnet run --project engine_csharp/src/LocalTesting -- puzzle-1 --engine-file engine_csharp/src/Engine.Core/V3/V3_4Engine.cs --time-limit-seconds 1.0
dotnet run --project engine_csharp/src/LocalTesting -- puzzle-2 --engine-file engine_csharp/src/Engine.Core/V3/V3_4Engine.cs --time-limit-seconds 1.0 --max-plies 70
dotnet run --project engine_csharp/src/LocalTesting -- evaluate-match --engine-a-file engine_csharp/src/Engine.Core/V3/V3_4Engine.cs --engine-b-file engine_csharp/src/Engine.Core/V3/V3_0Engine.cs --games 20 --time-limit-ms 100 --max-plies 200 --workers 6
```

`LocalTesting` intentionally supports only V3+ engine files. Scenario and evaluator commands use engine source paths so future major versions can be tested without adding version-specific CLI flags.
