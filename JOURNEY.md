# Journey

This document captures the reasoning behind major project decisions, especially where the current implementation is intentionally temporary.

## Current Position

This repository hosts the backend chess-move service on Vercel using Flask.

Today, the backend exposes versioned endpoints for:

- `v0`: random legal move
- `v1`: minimax
- `v1.1`: minimax with alpha-beta pruning
- `v1.2`: alpha-beta pruning with move ordering

These versions are preserved as the manual/reference phase of the project.

## Why Vercel and Why `30` Seconds

The backend is currently deployed on Vercel as a serverless Flask app because it is simple to host, integrates cleanly with the existing web stack, and is sufficient for the current stage of the project.

The repo currently sets Vercel `maxDuration` to `30` seconds in [`vercel.json`](/home/benny/Desktop/_gitrepo/chess-flask/vercel.json:1).

This should be understood as a temporary ceiling, not an ideal move budget.

### Reasoning

- The current engine family is still weak relative to the intended long-term quality bar.
- The current engine family is also slow enough that a tighter cap would be restrictive too early.
- Keeping the `30` second ceiling allows experimentation without immediately forcing deeper infrastructure changes.
- This is an operational compromise while the engine is still immature.

### Important Clarification

For an interactive chess experience, `30` seconds per move is usually too slow as a product target.

Long term, the project should aim for something materially faster, with latency treated as part of engine quality rather than as a separate concern.

## Why Not Increase the Limit Further

Even if the hosting platform allows longer execution windows, increasing the duration cap is not the preferred path for this project.

### Reasoning

- Slower move generation degrades frontend responsiveness.
- Longer-running requests reduce practical concurrency and increase compute usage.
- A stronger engine that only wins by taking much longer is not the kind of improvement this project should optimize for.
- Large evaluation campaigns should run locally or on dedicated infrastructure, not through deployed serverless endpoints.

The current direction is therefore:

- keep the present `30` second cap for now
- improve the engine
- measure both strength and speed
- reduce the cap as the engine improves

## Transition to `v2+`

The next phase of the project starts at `v2+`.

This phase is planned around the workflow pattern used by [`karpathy/autoresearch`](https://github.com/karpathy/autoresearch):

- generate candidate changes
- evaluate them mechanically
- keep only changes that beat the current accepted baseline

For this repo, that means using `autoresearch` as an iteration framework for chess-engine improvement, not as a drop-in chess solution.

## Evaluation Direction

The accepted direction for future evaluation is local automated benchmarking first.

### What this means

- Candidate engines should be tested locally.
- They should be compared against the latest accepted version and locked historical baselines such as `v1.2`.
- Evaluation should include both playing strength and runtime cost.
- Online bot matches may be useful later, but they should not be the main acceptance gate.

### Metrics that matter

- win/draw/loss against baselines
- timeout rate
- average move latency
- throughput under concurrency

## Intended Evolution of the Time Budget

The current deployment uses `30` seconds because the engine still needs room.

That is not the endpoint.

As `v2+` work progresses, the project should move toward:

- a lower practical move-time budget
- faster average response times
- stronger play within stricter compute limits

The desired direction is to make new versions both better and cheaper to run, not just stronger in isolation.

## Documentation Policy

- [`README.md`](/home/benny/Desktop/_gitrepo/chess-flask/README.md:1) should describe the system as it exists now and the immediate roadmap.
- [`CHANGELOG.md`](/home/benny/Desktop/_gitrepo/chess-flask/CHANGELOG.md:1) should record accepted version changes.
- `JOURNEY.md` should preserve the reasoning behind key architectural and product decisions so later iterations do not lose context.
