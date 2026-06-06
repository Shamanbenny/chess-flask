# Chess Flask Backend

This repository hosts a Flask backend deployed on Vercel for serving chess bot moves.

The backend accepts a chess board state as a FEN string and returns the next move chosen by the currently exposed HTTP bot surface. It is intended to work alongside a separate frontend on `sneakyowl.net`, but that frontend is out of scope here.

The `v1.x` engines in this repository heavily reference Sebastian Lague's [Coding Adventure: Chess](https://www.youtube.com/watch?v=U4ogK0MIzqk) and his [YouTube channel](https://www.youtube.com/@SebastianLague). The project uses that series as a practical guide for the search progression from plain minimax to pruning, move ordering, and capture-search refinement.

## Architecture Direction

The repository now intentionally separates two concerns:

- Python/Flask remains the serving layer for public HTTP endpoints.
- C# is the local-development workspace for direct rewrites of the `v1.*` reference engines.

That split exists because the search code wants a faster local tooling loop than Python alone provides, while the website still needs a Vercel-hosted Python backend.

The important boundary is now very simple:

- C# files mirror the Python engine files for local engine development, timing, and algorithm experiments.
- Python is for the deployed Flask surface.
- If a final `v1.*` engine is promoted to the public site, it should be rewritten into Python for the Vercel-served Flask app rather than having Flask try to execute C# in production.

## Current Backend Shape

- Runtime: Flask on Vercel serverless functions
- Entry point: [`api/index.py`](/home/benny/Desktop/_gitrepo/chess-flask/api/index.py:1)
- HTTP endpoint wrapper: [`api/endpoint.py`](/home/benny/Desktop/_gitrepo/chess-flask/api/endpoint.py:1)
- Historical search implementations: [`api/v1/__init__.py`](/home/benny/Desktop/_gitrepo/chess-flask/api/v1/__init__.py:1)
- Direct Python reference runners: [`local_v1_tests/puzzle_1.py`](/home/benny/Desktop/_gitrepo/chess-flask/local_v1_tests/puzzle_1.py:1) and [`local_v1_tests/endgame_1.py`](/home/benny/Desktop/_gitrepo/chess-flask/local_v1_tests/endgame_1.py:1)
- Native workspace scaffold: [`engine_csharp/README.md`](/home/benny/Desktop/_gitrepo/chess-flask/engine_csharp/README.md:1)
- Rewrite rule: all requests are routed to `api/index`
- Function limit: Vercel `maxDuration` is currently set to `30` seconds
- Allowed CORS origins:
  - `https://sneakyowl.net`
  - `https://www.sneakyowl.net`

The HTTP surface is intentionally narrow right now. Only `v0` remains exposed as a route. The older `v1` through `v1.4` engines are still preserved in code as historical/manual search references, but they are currently used only through direct local tooling.

The new rule for the repo is:

- Flask route behavior stays in Python.
- `v1.*` local algorithm work happens in direct C# rewrites of the Python reference engines.
- Future public `v1.*` exposure should be rewritten into Python for Flask/Vercel once the final engine shape is accepted.

The `30` second limit is a temporary ceiling, not the product target. Real progress for this project means moving toward much faster move generation, ideally around `1` second or less in practical play and materially lower for serious local iteration.

## API

The deployed endpoints currently exposed by Flask are:

| Endpoint | Version | Summary |
| --- | --- | --- |
| `POST /chess_v0` | `v0` | Random legal move baseline |
| `POST /chess_v1_5` | `v1.5` | Python `v1.5` engine with iterative deepening and a transposition table |

It expects JSON like:

```json
{
  "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
}
```

Successful responses include:

```json
{
  "move": "e4",
  "processing_time": 0.123
}
```

Moves are returned in SAN notation. Errors return JSON with an `error` field, for example invalid or missing FEN, checkmate, stalemate, or no legal moves.

### Example

```bash
curl -X POST http://localhost:3000/chess_v0 \
  -H "Content-Type: application/json" \
  -d '{"fen":"rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"}'
```

## Historical Engines

The project still keeps the historical search family in [`api/v1/`](/home/benny/Desktop/_gitrepo/chess-flask/api/v1/):

- `v1`: minimax
- `v1.1`: minimax with alpha-beta pruning
- `v1.2`: alpha-beta pruning with move ordering
- `v1.3`: alpha-beta pruning with move ordering and quiescence-style leaf extension through captures and quiet checks
- `v1.4`: `v1.3` plus endgame conversion evaluation and a tighter pruned quiescence search
- `v1.5`: `v1.4` plus time-budgeted iterative deepening and a transposition table
- `v2.0`: keeps the broad `v1.6` search and evaluation shape, but moves the inner search onto an in-house board representation and in-house move generation to remove the remaining hot-path overhead from the library-backed board

See [CHANGELOG.md](/home/benny/Desktop/_gitrepo/chess-flask/CHANGELOG.md:1) for the accepted algorithm history.

## Local Development

Install Python dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run with Vercel locally:

```bash
npm i -g vercel
vercel dev
```

The app will then be available at `http://localhost:3000`.

If `vercel dev` fails because the current Vercel Python builder cannot install `uv` inside your active virtualenv, run the Flask app directly instead:

```bash
python3 serve.py
```

That direct runner exposes the same currently supported Flask route on `http://localhost:3000`.

### Native Engine Workspace

The C# workspace is scaffolded under [`engine_csharp/`](/home/benny/Desktop/_gitrepo/chess-flask/engine_csharp/README.md:1).

Once the .NET SDK is installed, the intended workflow is:

```bash
dotnet build engine_csharp/ChessEngine.sln
dotnet run --project engine_csharp/src/LocalTesting -- puzzle-1 --versions v1 v1.1 v1.2 v1.3 v1.4 --depth 4
dotnet run --project engine_csharp/src/LocalTesting -- puzzle-1 --versions v1.5 v1.6 v2.0 --time-limit-seconds 1.0
dotnet run --project engine_csharp/src/LocalTesting -- puzzle-2 --version v2.0 --time-limit-seconds 1.0 --max-plies 70
dotnet run --project engine_csharp/src/LocalTesting -- endgame-1 --version v2.0 --time-limit-seconds 1.0
dotnet run --project engine_csharp/src/LocalTesting -- endgame-2 --version v2.0 --time-limit-seconds 1.0
dotnet run --project engine_csharp/src/LocalTesting -- evaluate-match --engine-a-file engine_csharp/src/Engine.Core/V2/V2_0Engine.cs --engine-b-file engine_csharp/src/Engine.Core/V1/V1_6Engine.cs --games 50 --time-limit-ms 250 --max-plies 200
export STOCKFISH_PATH=/home/your-user/tools/stockfish/stockfish-ubuntu-x86-64-avx2
dotnet run --project engine_csharp/src/LocalTesting -- evaluate-stock --engine-file engine_csharp/src/Engine.Core/V2/V2_0Engine.cs --stockfish-path "$STOCKFISH_PATH" --stockfish-elo 1350 --games 20 --time-limit-ms 100 --log --short-sha 1a2b3c4
```

`evaluate-stock` runs the specified C# engine file against a local Stockfish binary. The recommended workflow is to store the executable location in a `STOCKFISH_PATH` environment variable and pass it into `--stockfish-path`. `--stockfish-elo` maps to [Stockfish's UCI limited-strength](./STOCKFISH-ELO.md) setting rather than a guaranteed live rating. `--log --short-sha <sha>` writes the same evaluator CSV format used by `evaluate-match`.

The C# workspace now exists to hold direct source engines and the local scenario runners. The active local runner project in this repo is `engine_csharp/src/LocalTesting`.

## Project Versions

The project history is intentionally split into two eras:

- `v0` to `v1.6`
  - Manual coding / direct reference era.
  - These versions are preserved as part of the project's original implementation path.
- `v2+`
  - `autoresearch` era.
  - New versions should be accepted only when they measurably outperform the current accepted baseline.

The language split does not create a new engine version by itself. `CHANGELOG.md` remains about accepted algorithm milestones, not about workspace layout.

## `v2+` Workflow

The repository now includes a chess-specific `autoresearch` workflow inspired by Andrej Karpathy's [`karpathy/autoresearch`](https://github.com/karpathy/autoresearch): constrained code changes, a fixed local evaluator, and keep-or-reject decisions based on one mechanical promotion rule.

For this repo, that does not mean copying the upstream training setup. It means applying the same improvement loop to chess-engine development through versioned local engine candidates.

The workflow contract lives in:

- [`autoresearch/README.md`](/home/benny/Desktop/_gitrepo/chess-flask/autoresearch/README.md:1)
- [`autoresearch/PROGRAM.md`](/home/benny/Desktop/_gitrepo/chess-flask/autoresearch/PROGRAM.md:1)
- [`autoresearch/EVALUATE.md`](/home/benny/Desktop/_gitrepo/chess-flask/autoresearch/EVALUATE.md:1)
- [`autoresearch/ATTEMPTS.md`](/home/benny/Desktop/_gitrepo/chess-flask/autoresearch/ATTEMPTS.md:1)

### Current Acceptance Process

- Preserve `v0` through `v1.6` as accepted pre-`v2` history.
- Develop `v2+` locally, not on Vercel.
- Clone the latest approved engine into a new candidate file and modify only that candidate.
- Evaluate the candidate only against the latest approved baseline under the fixed `autoresearch/EVALUATE.md` match contract.
- Promote a version only if that fixed evaluator approves it.
- Log every completed evaluation, including rejected attempts, in `autoresearch/ATTEMPTS.md`.
- Record accepted algorithm milestones in `CHANGELOG.md`.

### Evaluation Direction

The active `v2+` direction is local automated engine-vs-engine evaluation, not online bot play.

The fixed evaluator is centered on:

- offline head-to-head matches
- the latest approved engine as the sole promotion baseline
- a strict per-move time budget
- paired, repeatable results recorded under `autoresearch/logs/<short_sha>-result.csv` when `--log --short-sha <short_sha>` is used

That remains the preferred direction because it is reproducible, automatable, cheaper to run repeatedly, and easier to use inside an `autoresearch` loop than online ladder play.

## Notes

- This repo currently documents the backend as it exists today.
- No unified `/move` or `/chess` endpoint exists yet.
- `v0` and Python `v1.5` are currently exposed through Flask routes.
- Historical engines remain versioned under `api/v1/`, with `v1.5.py` also serving the public Flask route.
- The current accepted `v2+` engine baseline is [`engine_csharp/src/Engine.Core/V2/V2_0Engine.cs`](/home/benny/Desktop/_gitrepo/chess-flask/engine_csharp/src/Engine.Core/V2/V2_0Engine.cs:1).
- The current Vercel duration setting is a temporary operational choice, not a statement that `30` seconds per move is the desired long-term UX target.
