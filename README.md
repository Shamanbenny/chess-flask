# Chess Flask Backend

This repository hosts a Flask backend deployed on Vercel for serving chess bot moves.

The backend accepts a chess board state as a FEN string and returns the next move chosen by the currently exposed HTTP bot surface. It is intended to work alongside a separate frontend on `sneakyowl.net`, but that frontend is out of scope here.

The `v1.x` engines in this repository heavily reference Sebastian Lague's [Coding Adventure: Chess](https://www.youtube.com/watch?v=U4ogK0MIzqk) and his [YouTube channel](https://www.youtube.com/@SebastianLague). The project uses that series as a practical guide for the search progression from plain minimax to pruning, move ordering, and capture-search refinement.

## Current Backend Shape

- Runtime: Flask on Vercel serverless functions
- Entry point: [`api/index.py`](/home/benny/Desktop/_gitrepo/chess-flask/api/index.py:1)
- HTTP endpoint wrapper: [`api/endpoint.py`](/home/benny/Desktop/_gitrepo/chess-flask/api/endpoint.py:1)
- Historical search implementations: [`api/v1/__init__.py`](/home/benny/Desktop/_gitrepo/chess-flask/api/v1/__init__.py:1)
- Direct local test runners: [`local_v1_tests/puzzle_1.py`](/home/benny/Desktop/_gitrepo/chess-flask/local_v1_tests/puzzle_1.py:1) and [`local_v1_tests/endgame_1.py`](/home/benny/Desktop/_gitrepo/chess-flask/local_v1_tests/endgame_1.py:1)
- Legacy local simulation runner: [`simulation.py`](/home/benny/Desktop/_gitrepo/chess-flask/simulation.py:1)
- Rewrite rule: all requests are routed to `api/index`
- Function limit: Vercel `maxDuration` is currently set to `30` seconds
- Allowed CORS origins:
  - `https://sneakyowl.net`
  - `https://www.sneakyowl.net`

The HTTP surface is intentionally narrow right now. Only `v0` remains exposed as a route. The older `v1` through `v1.4` engines are still preserved in code as historical/manual search references, but they are currently used only through direct local tooling.

The `30` second limit is a temporary ceiling, not the product target. Real progress for this project means moving toward much faster move generation, ideally around `1` second or less in practical play and materially lower for serious local iteration.

## API

The deployed endpoint currently exposed by Flask is:

| Endpoint | Version | Summary |
| --- | --- | --- |
| `POST /chess_v0` | `v0` | Random legal move baseline |

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

The project still keeps the historical search family in [`api/v1/__init__.py`](/home/benny/Desktop/_gitrepo/chess-flask/api/v1/__init__.py:1):

- `v1`: minimax
- `v1.1`: minimax with alpha-beta pruning
- `v1.2`: alpha-beta pruning with move ordering
- `v1.3`: alpha-beta pruning with move ordering and quiescence-style capture search
- `v1.4`: `v1.3` plus endgame conversion evaluation and a tighter pruned quiescence search

These are preserved as the manual/reference phase of the project. They are still callable directly from local tooling for experiments and search comparisons, but they are not currently part of the public HTTP surface.

The implementation path is intentionally close to Sebastian Lague's staged chess-engine progression:

- `v1`: establish a plain minimax baseline
- `v1.1`: introduce alpha-beta pruning
- `v1.2`: improve pruning efficiency with move ordering
- `v1.3`: reduce horizon-effect mistakes by extending leaf evaluation through capture sequences
- `v1.4`: make shallow winning endgames more conversion-oriented while keeping quiescence from exploding on non-capture checking sequences

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

## Local V1 Tests

The active local workflow now lives under [`local_v1_tests/`](/home/benny/Desktop/_gitrepo/chess-flask/local_v1_tests).

[`local_v1_tests/puzzle_1.py`](/home/benny/Desktop/_gitrepo/chess-flask/local_v1_tests/puzzle_1.py:1) keeps the fixed tactical comparison harness.

It uses the fixed FEN:

```text
8/8/6kp/3b4/1p1p4/1P1P3P/PK2N3/8 w - - 0 2
```

For each requested historical version it will:

- search White's first move
- require the intended first move `Nf4+`
- force Black's exact reply `Kg7`
- search White's second move
- report chosen move, score, positions evaluated, and elapsed time

Example:

```bash
python3 local_v1_tests/puzzle_1.py --versions v1 v1.1 v1.2 v1.3 v1.4 --depth 4
```

`v1.4` exists because shallow search is often strong enough to know it is winning but not deep enough to see the mate yet. Its evaluation adds guarded endgame conversion terms in clearly winning, low-material positions so the engine prefers moves that compress the opposing king, bring its own king closer, respect dangerous advanced pawns, and avoid drifting into repetition. It also tightens quiescence so queen endgames do not burn large amounts of time chasing every quiet checking continuation.

[`local_v1_tests/endgame_1.py`](/home/benny/Desktop/_gitrepo/chess-flask/local_v1_tests/endgame_1.py:1) is a dedicated `v1.4` self-play conversion test for the winning endgame:

```bash
python3 local_v1_tests/endgame_1.py
```

It runs `v1.4` for both sides from `3r4/8/3k4/8/3K4/8/8/8 b - - 1 1` at the script's fixed `depth=4` and `max_plies=60`, and reports whether Black manages to checkmate without the game drifting into repetition pressure.

## Simulation Runner

The older local simulation harness has been moved to [`simulation.py`](/home/benny/Desktop/_gitrepo/chess-flask/simulation.py:1).

It is not the primary workflow right now, but it is still kept around for later engine-vs-engine evaluation work.

Example:

```bash
python3 simulation.py --mode simulate --versions v1 v1.1 v1.2 --games-per-pair 20 --max-plies 200 --openings-file openings.txt --output-dir results --simulation-transport direct --workers 4
```

That script also keeps the older single-request and HTTP benchmark paths, but the active project direction is the direct experiment workflow rather than large simulation runs.

The simulation command writes three CSV files and one text log into `results/`:

- `*_games.csv`
  - one row per game
  - useful for win-rate, game-length, and per-game latency charts
- `*_moves.csv`
  - one row per move
  - useful for latency and search-cost charts by ply or by engine version
- `*_summary.csv`
  - one row per ordered matchup
  - useful for quick blog-post tables and bar charts
- `*_output.txt`
  - mirrored live progress output from the simulator
  - useful for reviewing elapsed time, failures, and long-running matchups after the run completes

The repository includes a starter file at [`openings.txt`](/home/benny/Desktop/_gitrepo/chess-flask/openings.txt:1). The simulator can rotate through those FENs across games within each ordered matchup.

## Project Versions

The project history is intentionally split into two eras:

- `v0` to `v1.4`
  - Manual coding / direct reference era.
  - These versions are preserved as part of the project's original implementation path.
- `v2+`
  - Planned `autoresearch` era.
  - New versions should be accepted only when they measurably outperform the current accepted baseline.

## Roadmap for `v2+`

Future versions will use the `autoresearch` workflow pattern from Andrej Karpathy's [`karpathy/autoresearch`](https://github.com/karpathy/autoresearch): constrained code changes, a fast evaluation loop, and keep-or-reject decisions based on one mechanical metric.

For this repo, that does not mean copying the training setup from `autoresearch`. It means applying the same improvement loop to chess-engine development, but only after the baseline engine is fast enough that repeated evaluation is practical.

### Planned Acceptance Process

- Preserve `v0` through `v1.4` as historical manual milestones.
- Develop `v2+` locally, not on Vercel.
- Benchmark each candidate against the latest accepted version and against locked historical baselines such as `v1.3`.
- Promote a version only if the benchmark says it is better.
- Tighten the practical move-time budget as stronger and faster versions become available.
- Record accepted algorithm changes in `CHANGELOG.md`.

### Evaluation Direction

The initial evaluation direction is still local automated matches, not online bot play, but the project is explicitly not treating large simulation campaigns as the immediate inner loop while the historical engines remain slow.

Recommended rules for the future evaluation harness:

- Run offline engine-vs-engine matches locally.
- Use paired games from the same opening positions with colors swapped.
- Enforce a fixed per-move time budget.
- Track:
  - win/draw/loss
  - timeout rate
  - average move latency
  - throughput under configured concurrency
- Use the latest accepted version as the primary promotion gate.

This remains the preferred long-term direction because it is reproducible, automatable, cheaper to run repeatedly, and easier to use inside an `autoresearch` loop than online ladder play.

## Notes

- This repo currently documents the backend as it exists today.
- No unified `/move` or `/chess` endpoint exists yet.
- Only `v0` is exposed through Flask routes at the moment.
- Historical engines remain versioned under `api/v1/` for direct local use.
- No `v2` engine implementation exists yet in this repository.
- The current Vercel duration setting is a temporary operational choice, not a statement that `30` seconds per move is the desired long-term UX target.
