# Repository Guidelines

## What This Repo Is

This repository has two jobs:

1. Serve chess moves through a Flask backend on Vercel.
2. Act as a local research workspace for improving the chess engine.

The key architectural rule is stable across the docs: Python owns the deployed HTTP surface, while C# owns most local engine-performance experimentation. If a future engine is good enough for public use, it should be rewritten back into Python for the Flask/Vercel path rather than invoked from C# in production.

## Current Source of Truth

The repo docs contain some historical references that no longer match the tree exactly. In particular, `README.md` and `engine_csharp/README.md` still mention `local_v1_tests/`, but that directory is not present in the current repository. Use the live tree as the source of truth:

- `api/`: Flask app and Python engine implementations.
- `api/index.py`: app entrypoint, CORS setup, blueprint registration.
- `api/endpoint.py`: request validation, route handlers, engine dispatch.
- `api/v1/`: historical Python engine versions `v1` through `v1.5`.
- `engine_csharp/src/Engine.Core/`: C# engine core and versioned engine files.
- `engine_csharp/src/LocalTesting/Program.cs`: local scenario runner and evaluator.
- `engine_scenarios/`: puzzle/endgame scenario JSON plus reference images and sample output.
- `autoresearch/`: constrained `v2+` engine-improvement workflow and experiment history.

## Project Structure & Intent

Think of the repo as three layers:

- Serving layer: Flask routes accept a FEN and return a SAN move plus timing metadata.
- Historical engine layer: Python `api/v1/*.py` preserves the manual progression from `v1` to `v1.5`.
- Research layer: C# rewrites and `autoresearch/` exist to improve search speed and engine quality under fixed time budgets.

The public API is intentionally narrow. The current Flask code exposes:

- `POST /chess_v0`: random legal move baseline.
- `POST /chess_v1_5`: Python `v1.5` engine.

The docs discuss older `v1.x` engines extensively, but most of them are historical references or local-testing targets, not active public routes.

## Engine Version Timeline

`CHANGELOG.md` and `JOURNEY.md` matter because they explain why each engine exists

The strategic target is not “survive Vercel’s 30 second ceiling.” The target repeated across the docs is closer to useful move generation in about `1s`, and ideally much faster for local iteration.

## Build, Run, and Evaluation Commands

Python setup:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 serve.py
```

Optional local Vercel mirror:

```bash
vercel dev
```

C# local engine workflow:

```bash
dotnet build engine_csharp/ChessEngine.sln
dotnet run --project engine_csharp/src/LocalTesting -- puzzle-1 --versions v1 v1.1 v1.2 v1.3 v1.4 --depth 4
dotnet run --project engine_csharp/src/LocalTesting -- puzzle-1 --versions v1.5 v1.6 --time-limit-seconds 1.0
dotnet run --project engine_csharp/src/LocalTesting -- puzzle-2 --version v1.6 --time-limit-seconds 1.0 --max-plies 70
dotnet run --project engine_csharp/src/LocalTesting -- endgame-1
dotnet run --project engine_csharp/src/LocalTesting -- endgame-2
```

Use the C# `LocalTesting` commands for serious engine validation; that is the active direction described by the repo docs.

## Testing and Validation

There is no formal `pytest` or unit-test suite in the repo today. Validation is scenario-driven and benchmark-driven.

- For Flask changes, test `POST /chess_v0` and `POST /chess_v1_5` with valid and invalid FEN payloads.
- For engine changes, use `engine_csharp/src/LocalTesting`.
- For reproducible tactical/endgame checks, rely on `engine_scenarios/*.json` and the expectations documented in `engine_scenarios/console_output.md`.

When editing docs or code, distinguish between “historical explanation” and “current runnable workflow.” This repo contains both.

## Autoresearch Workflow

`autoresearch/` defines the `v2+` experimentation contract. Read these files before doing autonomous engine-iteration work:

- `autoresearch/PROGRAM.md`
- `autoresearch/EVALUATE.md`
- `autoresearch/ATTEMPTS.md`

Important rules:

- Only the latest approved engine is the baseline.
- New work happens in a newly cloned versioned engine file.
- The evaluator is fixed: `500` games, `100ms` per move, paired openings from `Book.txt`.
- Approval requires a clean build, a completed evaluator run, no illegal/crash failures, and `lcb95 > 0.5`.
- `ATTEMPTS.md` is append-only except for the “Latest Approved Baseline” section.

As of `2026-06-05`, the latest approved baseline recorded there is `v1.6` at `engine_csharp/src/Engine.Core/V1/V1_6Engine.cs`.

## Coding Style & Naming

- Python: 4-space indentation, `snake_case`, small route helpers, engine logic kept out of route bodies.
- C#: existing .NET conventions, `PascalCase` for types/methods, `camelCase` for locals, one engine version per file.
- Keep engine-version naming consistent with the repo: `v1_5.py`, `V1_5Engine.cs`, etc.
- Prefer small, contained changes. The docs consistently value measurable improvement over broad rewrites without evidence.

## Commit & PR Expectations

Recent commits use short imperative subjects such as `Add autoresearch paradigm to repo` and `Adjust time limit seconds for Version 1.5`. The first word must be a present tense verb, similar to how you would ask someone to "do something". Keep commits scoped to one area: Flask surface, engine core, evaluator workflow, or documentation. (On more commplex commit, feel free to use `;` to define a 2nd scoped area - E.g. `Update README.md; Refactor codebase for new paradigm shifts`)

Pull requests should state:

- which layer changed: `api`, `engine_csharp`, or `autoresearch`
- what commands were run to validate it
- whether the change affects public routes, local engine behavior, or experiment policy
- whether any doc references are historical rather than current
