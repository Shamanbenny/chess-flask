# C# Engine Workspace

This directory contains the Dockerized web backend, the reusable engine core, and local engine validation tools.

## Projects

- `src/Engine.Functions`: .NET 8 ASP.NET Core HTTP API packaged by the root Dockerfile.
- `src/Engine.Core`: shared board/search infrastructure plus versioned engine files.
- `src/LocalTesting`: scenario runner, benchmarks, and evaluator commands.

## Serving Intent

The public backend is C# end to end. `Engine.Functions` accepts HTTP requests, validates FEN input, dispatches to exact compiled engines in `Engine.Core`, and returns SAN moves with timing/debug metadata.

Supported public route shape:

```text
GET /api/chess/metadata
POST /api/chess/{version}
```

`v0` is a special random legal-move baseline. V2+ engine serving is driven by
the root `CHANGELOG.json` file:

- `GET /api/chess/metadata` returns `CHANGELOG.json` for the frontend.
- `POST /api/chess/{version}` normalizes route versions such as `v3_4` to
  `v3.4`, checks for a matching `CHANGELOG.json` entry with `"served": true`,
  and resolves the compiled engine by convention.
- The convention is `vX.Y` -> `Engine.Core.VX.VX_YEngine.SearchMoveVX_Y(...)`.
- If the engine type also exposes `CreateSearchContextVX_Y()`, `Engine.Functions`
  keeps a per-game context keyed by `game_id` or `context_id` for warm-instance
  transposition-table reuse.

This means autoresearch can approve a new C# engine file and set its
`CHANGELOG.json` entry to `"served": true` without editing the
`Engine.Functions` dispatch switch. The caveat is compile/deploy time: the new
source file still has to be committed, compiled into `Engine.Core`, and deployed.
`CHANGELOG.json` selects among compiled engines; it cannot load a source file
that is absent from the deployed assembly.

## Commands

```bash
dotnet build engine_csharp/ChessEngine.sln
dotnet run --project engine_csharp/src/Engine.Functions
docker build -t autoresearch-chess-api .
docker run --rm -p 8080:8080 -e PORT=8080 autoresearch-chess-api
```

Local engine validation:

```bash
dotnet run --project engine_csharp/src/LocalTesting -- puzzle-1 --engine-file engine_csharp/src/Engine.Core/V3/V3_4Engine.cs --time-limit-seconds 1.0
dotnet run --project engine_csharp/src/LocalTesting -- puzzle-2 --engine-file engine_csharp/src/Engine.Core/V3/V3_4Engine.cs --time-limit-seconds 1.0 --max-plies 70
dotnet run --project engine_csharp/src/LocalTesting -- evaluate-match --engine-a-file engine_csharp/src/Engine.Core/V3/V3_4Engine.cs --engine-b-file engine_csharp/src/Engine.Core/V3/V3_0Engine.cs --games 20 --time-limit-ms 100 --max-plies 200 --workers 6
```

`LocalTesting` intentionally supports only V3+ engine files. Scenario and evaluator commands use engine source paths so future major versions can be tested without adding version-specific CLI flags.
