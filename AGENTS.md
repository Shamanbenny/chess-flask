# Repository Guidelines

## What This Repo Is

This repository has two jobs:

1. Serve chess moves through a C# Azure Functions backend.
2. Act as a local research workspace for improving the C# chess engine.

The key architectural rule is now simple: C# owns both the deployed HTTP surface and engine-performance experimentation.

## Current Source of Truth

Use the live tree as the source of truth:

- `engine_csharp/src/Engine.Functions/`: Azure Functions HTTP API.
- `engine_csharp/src/Engine.Functions/ChessFunction.cs`: request validation, route handling, CORS headers, timing, context caching, and engine dispatch.
- `engine_csharp/src/Engine.Core/`: C# engine core and versioned engine files.
- `engine_csharp/src/LocalTesting/Program.cs`: local scenario runner and evaluator.
- `engine_scenarios/`: puzzle/endgame scenario JSON plus reference images and sample output.
- `autoresearch/`: constrained `v2+` engine-improvement workflow and experiment history.

Historical docs may still mention Flask, Vercel, Python, or deleted `api/` files. Treat those as historical context, not current runnable workflow.

## Project Structure & Intent

Think of the repo as three layers:

- Serving layer: Azure Functions routes accept a FEN and return a SAN move plus timing metadata.
- Engine layer: `Engine.Core` contains board/search infrastructure and one engine file per version lineage.
- Research layer: `LocalTesting` and `autoresearch/` exist to improve search speed and engine quality under fixed time budgets.

The public API is intentionally narrow:

- `POST /api/chess/{version}`
- Supported versions: `v0`, `v2.0`, `v2.9`, `v3.0`, and `v3.4`.

The strategic target is useful move generation in about `1s`, and ideally much faster for local iteration.

## Build, Run, and Evaluation Commands

Build:

```bash
dotnet build engine_csharp/ChessEngine.sln
```

Run the Azure Functions API locally:

```bash
cd engine_csharp/src/Engine.Functions
func start
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

For current autoresearch baseline and latest approved seed values, reference `autoresearch/ATTEMPTS.md` directly.

## Coding Style & Naming

- C#: existing .NET conventions, `PascalCase` for types/methods, `camelCase` for locals, one engine version per file.
- Keep engine-version naming consistent with the repo: `V3_4Engine.cs`, `V4_0Engine.cs`, etc.
- Prefer small, contained changes. The docs consistently value measurable improvement over broad rewrites without evidence.

## Commit & PR Expectations

Recent commits use short imperative subjects such as `Add autoresearch paradigm to repo` and `Adjust time limit seconds for Version 1.5`. The first word must be a present tense verb, similar to how you would ask someone to "do something". Keep commits scoped to one area: Azure Functions surface, engine core, evaluator workflow, or documentation. On more complex commits, use `;` to define a second scoped area, for example `Update README.md; Refactor codebase for Azure Functions`.

Pull requests should state:

- which layer changed: `Engine.Functions`, `Engine.Core`, `LocalTesting`, or `autoresearch`
- what commands were run to validate it
- whether the change affects public routes, local engine behavior, or experiment policy
- whether any doc references are historical rather than current
