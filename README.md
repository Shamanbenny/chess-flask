# Chess Flask Backend

This repository hosts a Flask backend deployed on Vercel for serving chess bot moves.

The backend accepts a chess board state as a FEN string and returns the next move chosen by one of the versioned algorithms in this repo. It is intended to work alongside a separate frontend on `sneakyowl.net`, but that frontend is out of scope here.

## Current Backend Shape

- Runtime: Flask on Vercel serverless functions
- Entry point: [`api/index.py`](/home/benny/Desktop/_gitrepo/chess-flask/api/index.py:1)
- Rewrite rule: all requests are routed to `api/index`
- Function limit: Vercel `maxDuration` is currently set to `30` seconds
- Allowed CORS origins:
  - `https://sneakyowl.net`
  - `https://www.sneakyowl.net`

The app currently exposes separate versioned endpoints. There is no single endpoint that accepts a `version` field.

The `30` second limit is a temporary ceiling, not the long-term product target. It exists because the current engine family is still relatively weak and slow. As `v2+` development matures under `autoresearch`, the intention is to reduce the allowed move time and treat lower latency as part of the quality bar.

## API

All engine endpoints use `POST` and expect JSON like:

```json
{
  "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
}
```

Successful responses always include:

```json
{
  "move": "e4"
}
```

`v1` and later also return:

```json
{
  "processing_time": 0.123,
  "moves_evaluated": 4567
}
```

Errors return JSON with an `error` field, for example invalid/missing FEN, checkmate, stalemate, or other failures.

### Endpoints

| Endpoint | Version | Summary |
| --- | --- | --- |
| `POST /chess_v0` | `v0` | Random legal move baseline |
| `POST /chess_v1` | `v1` | Material-based minimax search |
| `POST /chess_v1-1` | `v1.1` | Minimax with alpha-beta pruning |
| `POST /chess_v1-2` | `v1.2` | Alpha-beta pruning plus move ordering |

Moves are returned in SAN notation.

### Example

```bash
curl -X POST http://localhost:3000/chess_v1-2 \
  -H "Content-Type: application/json" \
  -d '{"fen":"rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"}'
```

## Project Versions

The project history is intentionally split into two eras:

- `v0` to `v1.2`
  - Manual coding / direct reference era.
  - These versions are preserved as part of the project's original implementation path.
- `v2+`
  - Planned `autoresearch` era.
  - New versions should be accepted only when they measurably outperform the current accepted baseline.

See [CHANGELOG.md](/home/benny/Desktop/_gitrepo/chess-flask/CHANGELOG.md:1) for the accepted version history.

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

There is also a local helper script at [`local.py`](/home/benny/Desktop/_gitrepo/chess-flask/local.py:1) for testing the non-random search versions outside the HTTP layer.

## Roadmap for `v2+`

Future versions will use the `autoresearch` workflow pattern from Andrej Karpathy's [`karpathy/autoresearch`](https://github.com/karpathy/autoresearch): constrained code changes, a fast evaluation loop, and keep-or-reject decisions based on one mechanical metric.

For this repo, that does not mean copying the training setup from `autoresearch`. It means applying the same improvement loop to chess-engine development.

### Planned Acceptance Process

- Preserve `v0` through `v1.2` as historical manual milestones.
- Develop `v2+` locally, not on Vercel.
- Benchmark each candidate against the latest accepted version and against locked historical baselines such as `v1.2`.
- Promote a version only if the benchmark says it is better.
- Tighten the practical move-time budget as stronger and faster versions become available.
- Record accepted changes in `CHANGELOG.md`.

### Evaluation Direction

The initial evaluation direction is local automated matches, not online bot play.

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

This is the preferred direction because it is reproducible, automatable, cheaper to run repeatedly, and easier to use inside an `autoresearch` loop than online ladder play.

For now, the deployed backend will continue using the current `30` second serverless cap because the engine is not yet strong or fast enough to justify a stricter production ceiling. That cap should be revisited as part of `v2+` evaluation work, with the goal of driving it downward rather than upward.

### Tooling Direction

For future evaluation work:

- Prefer a local gauntlet harness over calling the deployed Vercel endpoints.
- Prefer established engine-match tooling such as `cutechess-cli`, or a dedicated local harness built with `python-chess`.
- Treat online bot matches as optional external validation, not as the acceptance gate.

## Notes

- This repo currently documents the deployed backend as it exists today.
- No unified `/move` or `/chess` endpoint exists yet.
- No `v2` engine implementation exists yet in this repository.
- The current Vercel duration setting is a temporary operational choice, not a statement that `30` seconds per move is the desired long-term UX target.
