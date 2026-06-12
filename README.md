# Chess Render Docker Backend

This repository serves chess moves through a Dockerized C#/.NET 8 web backend and acts as a local research workspace for improving the C# chess engine.

The backend accepts a chess board state as a FEN string and returns a SAN move plus timing/debug metadata. It is intended to work alongside the frontend on [`sneakyowl.net`](https://www.sneakyowl.net/chess); that frontend is out of scope here.

## Historical Python Engine Reference

If you are looking for the earlier `chess-flask` era of this repository, including the historical Python code where the chess engine was manually evolved from `V1.0` through `V1.6`, use this commit as the reference point:

- Historical repo state: <https://github.com/Shamanbenny/autoresearch-chess/blob/4b3a3a13a811314241e50b7dd9f7880e4f14da92/README.md>

That commit is the important entry point for the older Flask/Python architecture and the manual engine progression that no longer exists in the live tree. Regardless, shoutout to [Sebastian Lague](https://www.youtube.com/@SebastianLague)'s video on [Coding Adventure: Chess](https://www.youtube.com/watch?v=U4ogK0MIzqk) for inspiring me to start on my own coding adventure in the world of Chess Engine!

## Architecture

- `engine_csharp/src/Engine.Functions/`: ASP.NET Core HTTP API packaged for Docker/Render.
- `engine_csharp/src/Engine.Core/`: shared board/search infrastructure and versioned engines.
- `engine_csharp/src/LocalTesting/`: local scenario runner, benchmarks, and evaluator workflow.
- `engine_scenarios/`: puzzle/endgame scenario JSON plus reference images and sample output.
- `autoresearch/`: constrained `v2+` engine-improvement workflow and experiment history.

The public serving path is now C# end to end. Engine changes can be made directly in `Engine.Core` and exposed through `Engine.Functions` without a Python rewrite.

## API

The web service exposes one versioned endpoint:

| Endpoint | Summary |
| --- | --- |
| `GET /api/chess/metadata` | Engine metadata used by the frontend to render served versions and version information |
| `POST /api/chess/v0` | Random legal move baseline |
| `POST /api/chess/{version}` | Any compiled V2+ C# engine marked with `"served": true` in `CHANGELOG.json`, plus the special `v0` random baseline |

Route versions also accept underscores, for example `/api/chess/v3_4`.

`GET /api/chess/metadata` returns `CHANGELOG.json` as JSON. That file is the
frontend contract for V2+ C# engine metadata. Each entry records whether the
engine is currently served, its route version, summary, hypotheses,
limitations, engine file path, and standardized Stockfish 1350 score text. The
`summary` field is copied from autoresearch's `implementation_summary`. A
version can exist in `engine_csharp/src/Engine.Core/` with `"served": false`;
only compiled versions intended for public route dispatch should be marked
served.

For V2+ engines, `Engine.Functions` does not use a hard-coded version switch.
It reads served entries from `CHANGELOG.json` and resolves the compiled engine by
convention: `vX.Y` maps to `Engine.Core.VX.VX_YEngine.SearchMoveVX_Y(...)`, with
optional `CreateSearchContextVX_Y()` for warm-instance context reuse. A
`CHANGELOG.json` edit therefore becomes active after the commit is built and
deployed, provided the engine source file is included in `Engine.Core`.

Example metadata response:

```json
{
  "schema_version": 1,
  "stockfish_baseline": {
    "name": "Stockfish",
    "elo": 1350
  },
  "versions": [
    {
      "version": "v3.4",
      "api_version": "v3_4",
      "engine_file": "engine_csharp/src/Engine.Core/V3/V3_4Engine.cs",
      "served": true,
      "summary": "Cloned v3.0 into v3.4 and changed RepetitionDrawAdjustment so materially worse positions receive bounded draw-saving bonuses while equal-or-better positions retain repetition and draw penalties.",
      "implementation_summary": "Cloned v3.0 into v3.4 and changed RepetitionDrawAdjustment so materially worse positions receive bounded draw-saving bonuses while equal-or-better positions retain repetition and draw penalties.",
      "hypotheses": [
        "Making draw/repetition contempt material-aware will improve score by letting materially worse positions prefer repetition or 50-move draw chances instead of steering away from saves."
      ],
      "stockfish_1350": {
        "text": "C# v3.4 scored 323.0/500 against Stockfish (1350 Elo): 277 wins, 92 draws, 131 losses, score rate 0.6460."
      },
      "limitations": []
    }
  ]
}
```

Request body:

```json
{
  "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
  "game_id": "optional-stable-game-key",
  "reset_context": false
}
```

For `v3.0` and `v3.4`, pass either `game_id` or `context_id` to allow warm service instances to reuse a per-game transposition table across requests. This is an optimization only: cold starts, scale-out, or instance recycling may start with an empty context. Use `reset_context: true` when starting a new game with the same key.

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

Install the .NET 8 SDK.

Build everything:

```bash
dotnet build engine_csharp/ChessEngine.sln
```

Run the API locally:

```bash
dotnet run --project engine_csharp/src/Engine.Functions
```

Example request:

```bash
curl http://localhost:8080/api/chess/metadata

curl -X POST http://localhost:8080/api/chess/v3.4 \
  -H "Content-Type: application/json" \
  -d '{"fen":"rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"}'
```

Build and run the Docker image locally:

```bash
docker build -t autoresearch-chess-api .
docker run --rm -p 8080:8080 -e PORT=8080 autoresearch-chess-api
```

Allowed browser origins are:

- `https://sneakyowl.net`
- `https://www.sneakyowl.net`

## Deployment Notes

Deploy as a Render Web Service with the Docker runtime. The root `Dockerfile` publishes `engine_csharp/src/Engine.Functions`, and `render.yaml` configures the Dockerfile path, build context, health check, and default engine time budget.

Render supplies `PORT`; the app binds to `0.0.0.0:$PORT` and falls back to `8080` for local runs. Configure `ENGINE_TIME_LIMIT_SECONDS` in Render environment variables when the default `2.0` second budget should change.

## Native Engine Workflow

Use the C# `LocalTesting` commands for V3+ engine validation and research. These commands resolve compiled engines by source file path and reject pre-V3 engine files.

```bash
dotnet run --project engine_csharp/src/LocalTesting -- puzzle-1 --engine-file engine_csharp/src/Engine.Core/V3/V3_4Engine.cs --time-limit-seconds 1.0
dotnet run --project engine_csharp/src/LocalTesting -- puzzle-2 --engine-file engine_csharp/src/Engine.Core/V3/V3_4Engine.cs --time-limit-seconds 1.0 --max-plies 70
dotnet run --project engine_csharp/src/LocalTesting -- endgame-1 --engine-file engine_csharp/src/Engine.Core/V3/V3_4Engine.cs --time-limit-seconds 1.0
dotnet run --project engine_csharp/src/LocalTesting -- endgame-2 --engine-file engine_csharp/src/Engine.Core/V3/V3_4Engine.cs --time-limit-seconds 1.0
dotnet run --project engine_csharp/src/LocalTesting -- evaluate-match --engine-a-file engine_csharp/src/Engine.Core/V3/V3_4Engine.cs --engine-b-file engine_csharp/src/Engine.Core/V3/V3_0Engine.cs --games 20 --time-limit-ms 100 --max-plies 200 --workers 6
dotnet run --project engine_csharp/src/LocalTesting -- evaluate-stock --engine-file engine_csharp/src/Engine.Core/V3/V3_4Engine.cs --stockfish-path "$STOCKFISH_PATH" --stockfish-elo 1350 --games 500 --time-limit-ms 100 --max-plies 200 --workers 6 --log --short-sha 1a2b3c4
```

For Stockfish evaluation, point `--stockfish-path` at a local Stockfish binary, usually through `STOCKFISH_PATH`. The standard autoresearch evaluator contract uses `stockfish-1350`, `500` games, `100ms` per move, `200` max plies, `6` workers, `--log`, and a unique `--short-sha` attempt id. See `autoresearch/README.md` for the current approval contract and any workflow-specific overrides.

## Autoresearch

The repository also includes a chess-specific `autoresearch` paradigm inspired by Andrej Karpathy's [`karpathy/autoresearch`](https://github.com/karpathy/autoresearch), taking what was meant for a neural network autonomous training & improvement workflow to feature: 

- **Constrained Sandbox Environment** for Codex to implement code changes
- **Fixed Local Evaluator** handled by higher-layer Python Script to **keep-or-reject** experiment based on **Strict and Consistent Evaluation Contract**
- **Reduces Token Usage** by unnecessarily spawning Codex on Root Project Directory, but rather a **minimal sandbox environment**
- **Consistent Agentic Workflow** that does not rely on *Codex's mood on whether he wants to "stay" or "stop work"* when faced with 500 games of Chess Evaluation...

`autoresearch/` defines the `v2+` experimentation contract. Read these before autonomous engine-iteration work:

- `autoresearch/README.md`
- `autoresearch/ATTEMPTS.md`

The fixed evaluator baseline is local `stockfish-1350`. The current evaluator command and approval rule are documented in `autoresearch/README.md`; latest approved seed metadata lives in `autoresearch/state.json` and the append-only history in `autoresearch/ATTEMPTS.md`.

Approved V2+ frontend-facing metadata lives in `CHANGELOG.json`. When
`autoresearch/run_autoresearch.py` approves a candidate, it appends or updates
that file with `summary`/`implementation_summary`, hypotheses, standardized
Stockfish score text, and empty limitations by default. New approved candidates are recorded with
`"served": false` until the HTTP API is explicitly wired to expose that version.

Approval requires a clean build, a completed evaluator run, no illegal/crash failures, and `lcb95 > 0.5`.
