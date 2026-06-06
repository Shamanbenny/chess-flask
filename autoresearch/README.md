# Chess Autoresearch

This directory adapts the core `autoresearch` idea to a chess-engine improvement loop.

Credit for the original paradigm goes to Andrej Karpathy's [`karpathy/autoresearch`](https://github.com/karpathy/autoresearch), which framed a deliberately minimal autonomous research setup: let an agent modify a tightly scoped program, run a fixed evaluation, keep the change only if the metric improves, and repeat.

To get started, simply sign in to your CLI Model (and disable all permissions), then you can prompt something along the lines of: 

```
Start by looking at `autoresearch/PROGRAM.md` and let's kick off the experiment loop! Feel free to acquaint yourself with the repo before starting.
```

## Gist

The original upstream repo applies that pattern to neural-network training:

- one main mutable program file
- one fixed evaluator / preparation contract
- short autonomous experiment loops
- mechanical keep-or-reject decisions based on a single benchmark

This repo keeps that same spirit, but changes the object being optimized.

Instead of tuning `train.py` for a neural network, the agent here improves a versioned chess engine. Instead of asking whether validation bits-per-byte went down, the agent asks whether a newly cloned candidate engine actually beats a fixed Stockfish baseline under a fixed head-to-head match setup.

## What Is Different Here

This modified paradigm is chess-specific:

- The mutable unit is a newly cloned engine file, not a training script.
- The evaluator opponent is fixed at local `Stockfish` with `UCI_Elo=1350`.
- The seed engine for new candidates is still the latest approved in-repo engine recorded in `autoresearch/ATTEMPTS.md`.
- Evaluation is fixed at engine-vs-engine play under a strict time budget, not depth chasing and not ad hoc manual judgment.
- Promotion is based on a fixed statistical approval rule over paired games, not on a single anecdotal result.
- Every attempt, including failures, must leave behind an inferred conclusion so later runs can build on prior work instead of repeating it blindly.

The intended rhythm is:

1. Read prior attempts, the fixed Stockfish evaluator baseline, and the latest approved in-repo engine seed.
2. Form one concrete hypotheses.
3. Clone the approved in-repo engine seed into a new versioned file.
4. Change only that new engine.
5. Build it.
6. Run the fixed evaluator.
7. Keep the commit only if it clears the approval rule.
8. Append the result and conclusion to `ATTEMPTS.md`.

## Why This Shape

The point of this setup is not to create a general orchestration platform. The point is to make autonomous iteration cheap, comparable, and hard to game.

That means:

- the editable surface stays narrow
- the evaluator stays fixed
- the branch only advances on measured improvement
- failed experiments are still useful because they become memory for the next run

In other words, this directory is an attempt to port the upstream `autoresearch` philosophy from small ML training experiments to constrained chess-engine evolution.

## Files

- `PROGRAM.md`: the autonomous experiment loop and editing rules
- `EVALUATE.md`: the fixed match contract and approval rule
- `ATTEMPTS.md`: append-only experiment history, fixed evaluator metadata, and latest approved in-repo engine seed metadata

`AGENTS.md` is expected to be generated later once the workflow contract is stable.
