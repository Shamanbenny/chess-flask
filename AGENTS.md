# Repository Guidelines

## What This Repo Is

This repository has two jobs:

1. Serve chess moves through a Dockerized C#/.NET 8 web backend.
2. Act as a local research workspace for improving the C# chess engine.

The key architectural rule is now simple: C# owns both the deployed HTTP surface and engine-performance experimentation.

## Current Source of Truth

Use the live tree as the source of truth:

- `engine_csharp/src/Engine.Functions/`: ASP.NET Core HTTP API packaged for Docker/Render.
- `engine_csharp/src/Engine.Functions/Program.cs`: ASP.NET route mapping, JSON request parsing, Render `PORT` binding, and health check.
- `engine_csharp/src/Engine.Functions/ChessFunction.cs`: request validation, timing, context caching, and engine dispatch.
- `engine_csharp/src/Engine.Functions/CorsHeadersMiddleware.cs`: CORS headers for the public frontend origins.
- `Dockerfile`: .NET 8 multi-stage image for Render Web Services.
- `render.yaml`: Render web service blueprint.
- `CHANGELOG.json`: V2+ engine metadata served by `GET /api/chess/metadata` for the frontend.
- `engine_csharp/src/Engine.Core/`: C# engine core and versioned engine files.
- `engine_csharp/src/LocalTesting/Program.cs`: local scenario runner and evaluator.
- `engine_scenarios/`: puzzle/endgame scenario JSON plus reference images and sample output.
- `autoresearch/`: constrained `v2+` engine-improvement workflow and experiment history.

Historical docs may still mention Flask, Vercel, Python, or deleted `api/` files. Treat those as historical context, not current runnable workflow.

## Project Structure & Intent

Think of the repo as three layers:

- Serving layer: ASP.NET routes accept a FEN and return a SAN move plus timing metadata.
- Engine layer: `Engine.Core` contains board/search infrastructure and one engine file per version lineage.
- Research layer: `LocalTesting` and `autoresearch/` exist to improve search speed and engine quality under fixed time budgets.

The public API is intentionally narrow:

- `GET /api/chess/metadata`
- `POST /api/chess/{version}`
- Supported versions: `v0` plus compiled V2+ engines marked with `"served": true` in `CHANGELOG.json`.

`CHANGELOG.json` can contain V2+ engine files that are not served. Treat its
`served` flag as the frontend-facing route availability contract; do not infer
route availability from the presence of an engine file alone.

When a user asks to expose or serve a chess engine version, update both sides of
the contract in the same change: confirm the engine file follows the compiled
reflection convention and set that version's `CHANGELOG.json` entry to
`"served": true`. `Engine.Functions` resolves V2+ served engines by convention
at runtime after deployment; no per-version switch edit should be needed. If the
engine file exists but should not be publicly routed yet, leave `"served": false`.

The strategic target is useful move generation in about `1s`, and ideally much faster for local iteration.

## Build, Run, and Evaluation Commands

Build:

```bash
dotnet build engine_csharp/ChessEngine.sln
```

Run the API locally:

```bash
dotnet run --project engine_csharp/src/Engine.Functions
```

Build and run the Docker image:

```bash
docker build -t autoresearch-chess-api .
docker run --rm -p 8080:8080 -e PORT=8080 autoresearch-chess-api
```

C# local engine workflow:

```bash
dotnet run --project engine_csharp/src/LocalTesting -- puzzle-1 --engine-file engine_csharp/src/Engine.Core/V3/V3_4Engine.cs --time-limit-seconds 1.0
dotnet run --project engine_csharp/src/LocalTesting -- puzzle-2 --engine-file engine_csharp/src/Engine.Core/V3/V3_4Engine.cs --time-limit-seconds 1.0 --max-plies 70
dotnet run --project engine_csharp/src/LocalTesting -- evaluate-match --engine-a-file engine_csharp/src/Engine.Core/V3/V3_4Engine.cs --engine-b-file engine_csharp/src/Engine.Core/V3/V3_0Engine.cs --games 20 --time-limit-ms 100 --max-plies 200 --workers 6
```

`LocalTesting` is V3+ only. Use `--engine-file`/`--engine-a-file`/`--engine-b-file`; do not reintroduce version-list or pre-V3 scenario commands.

When you need the current exact testing or evaluation command shape, reference `README.md`, `autoresearch/README.md`, and `autoresearch/ATTEMPTS.md`.

## Testing and Validation

There is no formal unit-test suite in the repo today. Validation is scenario-driven and benchmark-driven.

- For serving changes, test `POST /api/chess/{version}` with valid and invalid FEN payloads.
- For metadata changes, test `GET /api/chess/metadata` and confirm served versions match `Engine.Functions`.
- For engine changes, use `engine_csharp/src/LocalTesting`.
- For reproducible tactical/endgame checks, rely on `engine_scenarios/*.json` and the expectations documented in `engine_scenarios/console_output.md`.

When editing docs or code, distinguish between historical explanation and current runnable workflow.

## Autoresearch Workflow

`autoresearch/` defines the `v2+` experimentation contract. Read these files before doing autonomous engine-iteration work:

- `autoresearch/README.md`
- `autoresearch/ATTEMPTS.md`

Important rules:

- The fixed evaluator baseline is local `stockfish-1350`.
- The latest approved in-repo engine is the seed for new candidate versions.
- New work happens in a newly cloned versioned engine file.
- The current fixed evaluator contract is documented in `autoresearch/README.md`; use that file, `autoresearch/state.json`, and `autoresearch/ATTEMPTS.md` for the current command, baseline, and latest approved seed values.
- Approval requires a clean build, a completed evaluator run, no illegal/crash failures, and `lcb95 > 0.5`.
- `ATTEMPTS.md` is append-only except for the “Latest Approved Engine Seed” section.
- Approved candidates are also appended to `CHANGELOG.json` with `served: false` by default.

For current autoresearch baseline and latest approved seed values, reference `autoresearch/ATTEMPTS.md` directly.

## Coding Style & Naming

- C#: existing .NET conventions, `PascalCase` for types/methods, `camelCase` for locals, one engine version per file.
- Keep engine-version naming consistent with the repo: `V3_4Engine.cs`, `V4_0Engine.cs`, etc.
- Prefer small, contained changes. The docs consistently value measurable improvement over broad rewrites without evidence.

## Commit & PR Expectations

Recent commits use short imperative subjects such as `Add autoresearch paradigm to repo` and `Adjust time limit seconds for Version 1.5`. The first word must be a present tense verb, similar to how you would ask someone to "do something". Keep commits scoped to one area: web serving surface, engine core, evaluator workflow, or documentation. On more complex commits, use `;` to define a second scoped area, for example `Update README.md; Refactor codebase for Render`.

Pull requests should state:

- which layer changed: `Engine.Functions`, `Engine.Core`, `LocalTesting`, or `autoresearch`
- what commands were run to validate it
- whether the change affects public routes, local engine behavior, or experiment policy
- whether any doc references are historical rather than current
